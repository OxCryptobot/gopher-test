#!/usr/bin/env python3
"""Foundational runtime for a best-in-class coding agent.

This module is intentionally small but structurally strong: it models task state,
repo execution planning, memory retention, and validation. It is designed to be
extended into a full agent operating system without reworking the core model.
"""
from __future__ import annotations

import ctypes
import ctypes.util
from dataclasses import dataclass, field
from enum import Enum
import errno
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Protocol

from planner import Planner


_MAX_OUTPUT = 64_000


def _clip(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        data = data.decode("utf-8", "replace")
    if len(data) <= _MAX_OUTPUT:
        return data
    return data[: _MAX_OUTPUT // 2] + "\n...[truncated]...\n" + data[-_MAX_OUTPUT // 2 :]


class TaskState(str, Enum):
    queued = "queued"
    analyzing = "analyzing"
    planned = "planned"
    executing = "executing"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"
    cancelled = "cancelled"


_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.queued: {TaskState.analyzing, TaskState.planned, TaskState.blocked, TaskState.cancelled},
    TaskState.analyzing: {TaskState.planned, TaskState.blocked, TaskState.failed, TaskState.cancelled},
    TaskState.planned: {TaskState.executing, TaskState.blocked, TaskState.failed, TaskState.cancelled},
    TaskState.executing: {TaskState.verifying, TaskState.failed, TaskState.blocked, TaskState.cancelled},
    TaskState.verifying: {TaskState.completed, TaskState.failed, TaskState.blocked, TaskState.cancelled},
    TaskState.failed: {TaskState.queued, TaskState.analyzing, TaskState.planned},
    TaskState.blocked: {TaskState.queued, TaskState.planned, TaskState.cancelled},
    TaskState.cancelled: set(),
    TaskState.completed: set(),
}


@dataclass
class Task:
    id: str
    name: str
    description: str
    dependencies: set[str] = field(default_factory=set)
    priority: int = 0
    status: TaskState = TaskState.queued
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    command: list[str] | None = None


@dataclass(frozen=True)
class TaskEvent:
    sequence: int
    task_id: str
    event_type: str
    timestamp: float
    previous_state: TaskState | None = None
    new_state: TaskState | None = None
    dependency_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for a durable event store."""
        return {
            "sequence": self.sequence,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "new_state": self.new_state.value if self.new_state else None,
            "dependency_id": self.dependency_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskEvent":
        return cls(
            sequence=data["sequence"],
            task_id=data["task_id"],
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            previous_state=TaskState(data["previous_state"]) if data.get("previous_state") else None,
            new_state=TaskState(data["new_state"]) if data.get("new_state") else None,
            dependency_id=data.get("dependency_id"),
            payload=dict(data.get("payload") or {}),
        )


class EventStore(Protocol):
    """Durable storage for a TaskGraph's append-only event log."""

    def append(self, event: TaskEvent) -> None: ...

    def load(self) -> list[TaskEvent]: ...


class InMemoryEventStore:
    """Process-local, non-durable event store; the default TaskGraph backend.

    Matches the original behaviour: events live only as long as the process.
    """

    def __init__(self) -> None:
        self._events: list[TaskEvent] = []

    def append(self, event: TaskEvent) -> None:
        self._events.append(event)

    def load(self) -> list[TaskEvent]:
        return list(self._events)


class JsonlEventStore:
    """Durable, append-only event store backed by a JSON Lines file.

    Each event is written as its own line and fsynced before ``append``
    returns, so a crash mid-write can lose at most the last, not-yet-synced
    event rather than corrupting earlier history. ``load`` stops at (and
    discards) a truncated or corrupt trailing line instead of failing the
    whole replay, so a graph can always be reconstructed up to the last
    durable event.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: TaskEvent) -> None:
        line = json.dumps(event.to_dict(), separators=(",", ":"), sort_keys=True)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def load(self) -> list[TaskEvent]:
        with self._lock:
            if not self.path.exists():
                return []
            raw = self.path.read_text(encoding="utf-8")
        events: list[TaskEvent] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                break  # truncated/corrupt trailing write from a crash; stop here
            events.append(TaskEvent.from_dict(data))
        return events


class TaskGraph:
    """A dependency-aware task graph with explicit task-state transitions.

    State is event-sourced: every mutation is captured as an immutable
    ``TaskEvent``, folded into in-memory state via :meth:`_apply`, and handed
    to an ``EventStore``. By default the store is process-local
    (``InMemoryEventStore``), matching the original in-memory-only behaviour.
    Pass a ``JsonlEventStore`` (or any ``EventStore``) to make the graph
    durable: its full history is replayed from the store on construction, so
    a new ``TaskGraph`` pointed at the same store reconstructs identical
    state after a process restart or crash.
    """

    def __init__(self, event_store: EventStore | None = None) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[str, Task] = {}
        self._events: list[TaskEvent] = []
        self._store = event_store or InMemoryEventStore()
        for event in self._store.load():
            self._apply(event)
            self._events.append(event)

    def _apply(self, event: TaskEvent) -> None:
        """Fold a single event into in-memory task state.

        This is the sole source of truth for how an event type changes the
        graph; both live mutation (via :meth:`_emit`) and replay from a
        durable store call it, so the two can never drift out of sync.
        """
        if event.event_type == "task_created":
            payload = event.payload
            self._tasks[event.task_id] = Task(
                id=event.task_id,
                name=event.task_id,
                description=payload.get("description", ""),
                dependencies=set(payload.get("dependencies") or ()),
                priority=payload.get("priority", 0),
                status=TaskState.queued,
                metadata=dict(payload.get("metadata") or {}),
            )
        elif event.event_type == "dependency_added":
            self._tasks[event.task_id].dependencies.add(event.dependency_id)
        elif event.event_type == "status_changed":
            self._tasks[event.task_id].status = event.new_state
        else:
            raise ValueError(f"cannot apply unknown event type: {event.event_type!r}")

    def _emit(self, task_id: str, event_type: str, **details: Any) -> TaskEvent:
        event = TaskEvent(
            sequence=len(self._events) + 1,
            task_id=task_id,
            event_type=event_type,
            timestamp=time.time(),
            **details,
        )
        self._apply(event)
        self._events.append(event)
        self._store.append(event)
        return event

    def add_task(
        self,
        task_id: str,
        description: str,
        *,
        priority: int = 0,
        dependencies: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"task already exists: {task_id}")
            dependency_ids = set(dependencies or ())
            missing = dependency_ids - self._tasks.keys()
            if missing:
                raise ValueError(f"unknown dependency: {min(missing)}")
            self._emit(
                task_id,
                "task_created",
                payload={
                    "description": description,
                    "priority": priority,
                    "dependencies": sorted(dependency_ids),
                    "metadata": dict(metadata or {}),
                },
            )
            return self._tasks[task_id]

    def add_dependency(self, task_id: str, dependency_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"unknown task: {task_id}")
            if dependency_id not in self._tasks:
                raise KeyError(f"unknown dependency: {dependency_id}")
            if dependency_id in task.dependencies:
                return
            task.dependencies.add(dependency_id)
            try:
                self.topological_order()
            except ValueError:
                task.dependencies.remove(dependency_id)
                raise
            task.dependencies.discard(dependency_id)  # _emit re-applies it via _apply
            self._emit(task_id, "dependency_added", dependency_id=dependency_id)

    def update_status(self, task_id: str, new_state: TaskState) -> TaskState:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"unknown task: {task_id}")
            if task.status == new_state:
                return task.status
            allowed = _TRANSITIONS.get(task.status, set())
            if new_state not in allowed:
                raise ValueError(
                    f"invalid state transition for {task_id}: {task.status.value} -> {new_state.value}"
                )
            previous_state = task.status
            self._emit(
                task_id,
                "status_changed",
                previous_state=previous_state,
                new_state=new_state,
            )
            return new_state

    def get_status(self, task_id: str) -> TaskState:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"unknown task: {task_id}")
            return task.status

    def next_ready_tasks(self) -> list[str]:
        with self._lock:
            ready: list[str] = []
            for task_id, task in sorted(self._tasks.items(), key=lambda item: (-item[1].priority, item[0])):
                if task.status not in {TaskState.queued, TaskState.planned}:
                    continue
                if all(self._tasks[dep].status == TaskState.completed for dep in task.dependencies):
                    ready.append(task_id)
            return ready

    def topological_order(self) -> list[str]:
        with self._lock:
            in_degree = {task_id: len(task.dependencies) for task_id, task in self._tasks.items()}
            dependents = {task_id: [] for task_id in self._tasks}
            for task_id, task in self._tasks.items():
                missing = task.dependencies - self._tasks.keys()
                if missing:
                    raise ValueError(f"unknown dependency: {min(missing)}")
                for dependency_id in task.dependencies:
                    dependents[dependency_id].append(task_id)

            queue = deque(sorted(task_id for task_id, degree in in_degree.items() if degree == 0))
            out: list[str] = []
            while queue:
                current = queue.popleft()
                out.append(current)
                for dependent_id in sorted(dependents[current]):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)
            if len(out) != len(self._tasks):
                raise ValueError("task graph contains a cycle")
            return out

    def tasks(self) -> dict[str, Task]:
        with self._lock:
            return {
                k: Task(
                    id=v.id,
                    name=v.name,
                    description=v.description,
                    dependencies=set(v.dependencies),
                    priority=v.priority,
                    status=v.status,
                    metadata=dict(v.metadata),
                )
                for k, v in self._tasks.items()
            }

    def events(self, task_id: str | None = None) -> list[TaskEvent]:
        with self._lock:
            if task_id is None:
                return list(self._events)
            return [event for event in self._events if event.task_id == task_id]


class MemoryStore:
    """Persistent, lightweight memory with TTL and simple policy-based retention."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def remember(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        with self._lock:
            self._entries[key] = {
                "value": value,
                "expires_at": None if ttl is None else time.monotonic() + ttl,
                "created_at": time.time(),
            }

    def recall(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry["expires_at"] is not None and time.monotonic() > entry["expires_at"]:
                del self._entries[key]
                return None
            return entry["value"]

    def remove(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)


class Verifier:
    """Run validation commands in a disposable, network-isolated workspace."""

    _SYSCALLS_TO_DENY = (
        "acct",
        "add_key",
        "bpf",
        "delete_module",
        "finit_module",
        "init_module",
        "io_uring_setup",
        "kexec_file_load",
        "kexec_load",
        "keyctl",
        "mount",
        "move_mount",
        "open_by_handle_at",
        "perf_event_open",
        "pivot_root",
        "process_vm_readv",
        "process_vm_writev",
        "ptrace",
        "reboot",
        "request_key",
        "setns",
        "swapon",
        "swapoff",
        "umount2",
        "unshare",
        "userfaultfd",
    )

    @classmethod
    def _export_seccomp_policy(cls, file_descriptor: int, library_path: str) -> None:
        library = ctypes.CDLL(library_path, use_errno=True)
        library.seccomp_init.argtypes = [ctypes.c_uint32]
        library.seccomp_init.restype = ctypes.c_void_p
        library.seccomp_release.argtypes = [ctypes.c_void_p]
        library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
        library.seccomp_rule_add.restype = ctypes.c_int
        library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        library.seccomp_syscall_resolve_name.restype = ctypes.c_int
        library.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
        library.seccomp_export_bpf.restype = ctypes.c_int

        action_allow = 0x7FFF0000
        action_errno = 0x00050000 | errno.EPERM
        context = library.seccomp_init(action_allow)
        if not context:
            raise OSError("libseccomp could not initialize a filter")
        try:
            for name in cls._SYSCALLS_TO_DENY:
                syscall = library.seccomp_syscall_resolve_name(name.encode("ascii"))
                if syscall < 0:
                    continue
                result = library.seccomp_rule_add(context, action_errno, syscall, 0)
                if result < 0:
                    raise OSError(-result, f"could not filter syscall: {name}")
            result = library.seccomp_export_bpf(context, file_descriptor)
            if result < 0:
                raise OSError(-result, "could not export seccomp policy")
        finally:
            library.seccomp_release(context)

    def run(
        self,
        command: list[str] | str,
        *,
        cwd: str | None = None,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> VerificationResult:
        argv = command if isinstance(command, list) else shlex.split(command)
        bwrap = shutil.which("bwrap")
        prlimit = shutil.which("prlimit")
        seccomp_library = ctypes.util.find_library("seccomp")
        if bwrap is None or prlimit is None or seccomp_library is None:
            return VerificationResult(
                passed=False,
                exit_code=126,
                stderr="bubblewrap, prlimit, and libseccomp are required for sandboxed verification",
                command=argv,
            )

        source_root = Path(cwd or os.getcwd()).resolve()
        if not source_root.is_dir():
            return VerificationResult(
                passed=False,
                exit_code=126,
                stderr=f"verification workspace is not a directory: {source_root}",
                command=argv,
            )

        def ignore_sensitive(directory: str, names: list[str]) -> set[str]:
            del directory
            return {
                name
                for name in names
                if name == ".git"
                or name == ".env"
                or name == ".envrc"
                or (name.startswith(".env.") and name != ".env.example")
            }

        try:
            with tempfile.TemporaryDirectory(prefix="agent-verify-") as temporary_root:
                sandbox_workspace = Path(temporary_root) / "workspace"
                shutil.copytree(source_root, sandbox_workspace, symlinks=True, ignore=ignore_sensitive)
                sandbox_path = ["/usr/local/bin", "/usr/bin", "/bin"]
                for search_path in os.environ.get("PATH", "").split(os.pathsep):
                    if not search_path:
                        continue
                    resolved_path = Path(search_path).resolve()
                    if resolved_path == Path("/usr") or Path("/usr") in resolved_path.parents:
                        sandbox_path.append(str(resolved_path))
                    elif resolved_path == source_root or source_root in resolved_path.parents:
                        relative_path = resolved_path.relative_to(source_root)
                        sandbox_path.append(str(Path("/workspace") / relative_path))

                with tempfile.TemporaryFile() as seccomp_file:
                    self._export_seccomp_policy(seccomp_file.fileno(), seccomp_library)
                    seccomp_file.seek(0)
                    sandbox_command = [
                        bwrap,
                        "--die-with-parent",
                        "--unshare-all",
                        "--seccomp",
                        str(seccomp_file.fileno()),
                        "--clearenv",
                        "--ro-bind",
                        "/usr",
                        "/usr",
                        "--symlink",
                        "usr/bin",
                        "/bin",
                        "--symlink",
                        "usr/sbin",
                        "/sbin",
                        "--symlink",
                        "usr/lib",
                        "/lib",
                        "--symlink",
                        "usr/lib64",
                        "/lib64",
                        "--ro-bind",
                        "/etc/ld.so.cache",
                        "/etc/ld.so.cache",
                        "--ro-bind",
                        "/etc/ssl/certs",
                        "/etc/ssl/certs",
                        "--ro-bind",
                        "/etc/passwd",
                        "/etc/passwd",
                        "--ro-bind",
                        "/etc/group",
                        "/etc/group",
                        "--ro-bind",
                        "/etc/nsswitch.conf",
                        "/etc/nsswitch.conf",
                        "--dev",
                        "/dev",
                        "--proc",
                        "/proc",
                        "--dir",
                        "/workspace",
                        "--bind",
                        str(sandbox_workspace),
                        "/workspace",
                        "--tmpfs",
                        "/tmp",
                        "--dir",
                        "/tmp/home",
                        "--chdir",
                        "/workspace",
                        "--setenv",
                        "HOME",
                        "/tmp/home",
                        "--setenv",
                        "TMPDIR",
                        "/tmp",
                        "--setenv",
                        "PATH",
                        os.pathsep.join(dict.fromkeys(sandbox_path)),
                        "--setenv",
                        "LANG",
                        "C.UTF-8",
                    ]
                    for key, value in (env or {}).items():
                        sandbox_command.extend(("--setenv", key, value))
                    sandbox_command.extend(("--", *argv))

                    cpu_limit = max(1, min(int(timeout), 60))
                    limited_command = [
                        prlimit,
                        f"--cpu={cpu_limit}:{cpu_limit}",
                        "--as=2147483648:2147483648",
                        "--fsize=536870912:536870912",
                        "--nofile=256:256",
                        "--nproc=256:256",
                        "--core=0:0",
                        "--",
                        *sandbox_command,
                    ]
                    proc = subprocess.run(
                        limited_command,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        pass_fds=(seccomp_file.fileno(),),
                    )
        except subprocess.TimeoutExpired as exc:
            return VerificationResult(
                passed=False,
                exit_code=124,
                stdout=_clip(exc.stdout),
                stderr=_clip(exc.stderr) + f"\ntimed out after {timeout}s",
                command=argv,
            )
        except (OSError, ValueError) as exc:
            return VerificationResult(
                passed=False,
                exit_code=126,
                stderr=f"could not initialize verification sandbox: {exc}",
                command=argv,
            )
        return VerificationResult(
            passed=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=_clip(proc.stdout),
            stderr=_clip(proc.stderr),
            command=argv,
        )


class AgentRuntime:
    """A minimal but production-oriented runtime shell.

    The goal is to impose order on otherwise chaotic agent behavior: explicit
    states, dependency checks, memory retention, validation, and task execution.
    """

    def __init__(self, event_store: EventStore | None = None) -> None:
        self.graph = TaskGraph(event_store=event_store)
        self.memory = MemoryStore()
        self.verifier = Verifier()
        self._lock = threading.RLock()

    def create_task(
        self,
        task_id: str | None = None,
        description: str = "",
        *,
        dependencies: Iterable[str] | None = None,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            generated = task_id or uuid.uuid4().hex[:12]
            task = self.graph.add_task(
                generated,
                description,
                priority=priority,
                dependencies=dependencies,
                metadata=metadata,
            )
            return {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "dependencies": sorted(task.dependencies),
                "priority": task.priority,
                "status": task.status.value,
            }

    def plan_goal(self, goal: str, *, planner: Planner | None = None) -> dict[str, Any]:
        """Create runtime tasks from a planner's dependency-aware goal plan."""
        with self._lock:
            plan = (planner or Planner()).plan(goal)
            tasks = plan["tasks"]
            for task in tasks:
                self.create_task(
                    task["id"],
                    task["description"],
                    dependencies=task["dependencies"],
                    metadata={
                        "kind": task["kind"],
                        "confidence": task["confidence"],
                        "risk": task["risk"],
                    },
                )
            self.plan(task["id"] for task in tasks)
            return plan

    def plan(self, task_ids: Iterable[str]) -> list[str]:
        ordered = list(task_ids)
        for task_id in ordered:
            self.graph.update_status(task_id, TaskState.planned)
        return ordered

    def update_status(self, task_id: str, new_state: TaskState) -> TaskState:
        with self._lock:
            return self.graph.update_status(task_id, new_state)

    def get_status(self, task_id: str) -> TaskState:
        with self._lock:
            return self.graph.get_status(task_id)

    def remember(self, key: str, value: Any, *, ttl: float | None = None) -> None:
        self.memory.remember(key, value, ttl=ttl)

    def recall(self, key: str) -> Any | None:
        return self.memory.recall(key)

    def validate(self, command: list[str] | str, *, cwd: str | None = None, timeout: int = 30) -> VerificationResult:
        return self.verifier.run(command, cwd=cwd, timeout=timeout)


__all__ = [
    "AgentRuntime",
    "EventStore",
    "InMemoryEventStore",
    "JsonlEventStore",
    "MemoryStore",
    "TaskGraph",
    "TaskEvent",
    "TaskState",
    "Verifier",
    "VerificationResult",
]
