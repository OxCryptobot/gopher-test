#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_runtime import (
    AgentRuntime,
    InMemoryEventStore,
    JsonlEventStore,
    MemoryStore,
    TaskGraph,
    TaskState,
    Verifier,
)


class AgentRuntimeTests(unittest.TestCase):
    def test_task_state_machine(self) -> None:
        graph = TaskGraph()
        graph.add_task("t1", "investigate")
        graph.update_status("t1", TaskState.planned)
        self.assertEqual(graph.get_status("t1"), TaskState.planned)

        with self.assertRaises(ValueError):
            graph.update_status("t1", TaskState.completed)

        graph.update_status("t1", TaskState.executing)
        graph.update_status("t1", TaskState.verifying)
        graph.update_status("t1", TaskState.completed)
        self.assertEqual(graph.get_status("t1"), TaskState.completed)

    def test_task_graph_dependency_order(self) -> None:
        graph = TaskGraph()
        graph.add_task("explore", "inspect root")
        graph.add_task("plan", "design patch")
        graph.add_task("verify", "check result")
        graph.add_dependency("plan", "explore")
        graph.add_dependency("verify", "plan")

        order = graph.topological_order()
        self.assertEqual(order[:2], ["explore", "plan"])
        self.assertEqual(order[-1], "verify")

        ready = graph.next_ready_tasks()
        self.assertEqual(ready, ["explore"])

    def test_task_graph_rejects_unknown_dependencies_and_cycles(self) -> None:
        graph = TaskGraph()
        graph.add_task("first", "first task")
        graph.add_task("second", "second task")

        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            graph.add_task("orphan", "missing prerequisite", dependencies=["missing"])

        graph.add_dependency("second", "first")
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.add_dependency("first", "second")

        self.assertEqual(graph.topological_order(), ["first", "second"])

    def test_task_graph_records_immutable_ordered_events(self) -> None:
        graph = TaskGraph()
        graph.add_task("first", "first task")
        graph.add_task("second", "second task")
        graph.add_dependency("second", "first")
        graph.add_dependency("second", "first")
        graph.update_status("first", TaskState.planned)
        graph.update_status("first", TaskState.planned)

        events = graph.events()
        self.assertEqual([event.sequence for event in events], [1, 2, 3, 4])
        self.assertEqual(
            [event.event_type for event in events],
            ["task_created", "task_created", "dependency_added", "status_changed"],
        )
        self.assertEqual(events[-1].previous_state, TaskState.queued)
        self.assertEqual(events[-1].new_state, TaskState.planned)
        self.assertEqual(graph.events("second"), [events[1], events[2]])

        events.clear()
        self.assertEqual(len(graph.events()), 4)

    def test_task_graph_defaults_to_in_memory_event_store(self) -> None:
        graph = TaskGraph()
        graph.add_task("first", "first task")
        self.assertIsInstance(graph._store, InMemoryEventStore)  # type: ignore[attr-defined]

    def test_jsonl_event_store_replays_full_graph_state_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")

            graph = TaskGraph(event_store=JsonlEventStore(path))
            graph.add_task("explore", "inspect root", priority=2, metadata={"kind": "analysis"})
            graph.add_task("plan", "design patch")
            graph.add_dependency("plan", "explore")
            graph.update_status("explore", TaskState.planned)
            graph.update_status("explore", TaskState.executing)
            graph.update_status("explore", TaskState.verifying)
            graph.update_status("explore", TaskState.completed)

            # A fresh TaskGraph over the same durable store reconstructs identical state,
            # simulating a process restart or crash recovery.
            restarted = TaskGraph(event_store=JsonlEventStore(path))
            self.assertEqual(sorted(restarted.tasks()), ["explore", "plan"])
            self.assertEqual(restarted.get_status("explore"), TaskState.completed)
            self.assertEqual(restarted.get_status("plan"), TaskState.queued)
            self.assertEqual(restarted.tasks()["plan"].dependencies, {"explore"})
            self.assertEqual(restarted.tasks()["explore"].metadata, {"kind": "analysis"})
            self.assertEqual(restarted.tasks()["explore"].priority, 2)
            self.assertEqual(restarted.topological_order(), ["explore", "plan"])
            self.assertEqual(len(restarted.events()), len(graph.events()))

            # Continuing to mutate the restarted graph appends to the same durable log.
            restarted.update_status("plan", TaskState.planned)
            third = TaskGraph(event_store=JsonlEventStore(path))
            self.assertEqual(third.get_status("plan"), TaskState.planned)
            self.assertEqual(len(third.events()), len(restarted.events()))

    def test_jsonl_event_store_survives_concurrent_appends(self) -> None:
        import threading as _threading

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            graph = TaskGraph(event_store=JsonlEventStore(path))
            graph.add_task("root", "root task")

            errors: list[Exception] = []

            def worker(i: int) -> None:
                try:
                    graph.add_task(f"child-{i}", "child task", dependencies=["root"])
                except Exception as exc:  # pragma: no cover - failure path only
                    errors.append(exc)

            threads = [_threading.Thread(target=worker, args=(i,)) for i in range(16)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            reloaded = TaskGraph(event_store=JsonlEventStore(path))
            self.assertEqual(len(reloaded.tasks()), 17)
            self.assertEqual(len(reloaded.events()), 17)
            self.assertEqual(len({event.sequence for event in reloaded.events()}), 17)

    def test_jsonl_event_store_tolerates_truncated_trailing_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            graph = TaskGraph(event_store=JsonlEventStore(path))
            graph.add_task("explore", "inspect root")
            graph.update_status("explore", TaskState.planned)

            # Simulate a crash mid-write: a truncated, non-JSON trailing line.
            with open(path, "a", encoding="utf-8") as handle:
                handle.write('{"sequence": 3, "task_id": "explore", "event_typ')

            recovered = TaskGraph(event_store=JsonlEventStore(path))
            self.assertEqual(sorted(recovered.tasks()), ["explore"])
            self.assertEqual(recovered.get_status("explore"), TaskState.planned)
            self.assertEqual(len(recovered.events()), 2)

    def test_jsonl_event_store_round_trips_task_event_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            store = JsonlEventStore(path)
            graph = TaskGraph(event_store=store)
            graph.add_task("explore", "inspect root", priority=3, dependencies=[], metadata={"k": "v"})

            with open(path, encoding="utf-8") as handle:
                lines = handle.readlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event_type"], "task_created")
            self.assertEqual(record["payload"]["description"], "inspect root")
            self.assertEqual(record["payload"]["priority"], 3)
            self.assertEqual(record["payload"]["metadata"], {"k": "v"})

    def test_emit_does_not_mutate_state_when_store_append_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            store = JsonlEventStore(path)
            graph = TaskGraph(event_store=store)
            graph.add_task("explore", "inspect root")

            with patch.object(store, "append", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    graph.add_task("plan", "design patch")

            # The failed task_created event must not have been applied in-process,
            # since it was never made durable.
            self.assertEqual(sorted(graph.tasks()), ["explore"])
            self.assertEqual(len(graph.events()), 1)

            with patch.object(store, "append", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    graph.update_status("explore", TaskState.planned)

            self.assertEqual(graph.get_status("explore"), TaskState.queued)
            self.assertEqual(len(graph.events()), 1)

            # The store itself only has the one durably persisted event.
            reloaded = TaskGraph(event_store=JsonlEventStore(path))
            self.assertEqual(sorted(reloaded.tasks()), ["explore"])
            self.assertEqual(reloaded.get_status("explore"), TaskState.queued)

    def test_jsonl_event_store_fsyncs_parent_directory_on_first_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "events.jsonl")
            store = JsonlEventStore(path)

            with patch("os.fsync") as mock_fsync, patch("os.open", wraps=os.open) as mock_open:
                graph = TaskGraph(event_store=store)
                graph.add_task("explore", "inspect root")

            # The parent directory is opened (read-only) and fsynced exactly once,
            # for the first write that creates the file.
            dir_opens = [
                call
                for call in mock_open.call_args_list
                if call.args and call.args[0] == str(Path(path).parent)
            ]
            self.assertEqual(len(dir_opens), 1)
            # One fsync for the file's data, one for the parent directory entry.
            self.assertEqual(mock_fsync.call_count, 2)

            with patch("os.fsync") as mock_fsync, patch("os.open", wraps=os.open) as mock_open:
                graph.add_task("plan", "design patch")

            # The file already exists, so only the file's data is fsynced again.
            dir_opens = [
                call
                for call in mock_open.call_args_list
                if call.args and call.args[0] == str(Path(path).parent)
            ]
            self.assertEqual(dir_opens, [])
            self.assertEqual(mock_fsync.call_count, 1)

    def test_memory_store_expiration(self) -> None:
        memory = MemoryStore()
        memory.remember("alpha", {"value": 1}, ttl=0.05)
        self.assertEqual(memory.recall("alpha")["value"], 1)
        time.sleep(0.12)
        self.assertIsNone(memory.recall("alpha"))

    def test_verifier_runs_commands(self) -> None:
        verifier = Verifier()
        with tempfile.TemporaryDirectory() as tmp:
            result = verifier.run(["python", "-c", "print('ok')"], cwd=tmp)
            self.assertTrue(result.passed)
            self.assertIn("ok", result.stdout)

        result = verifier.run(["python", "-c", "raise SystemExit(3)"])
        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 3)

    def test_verifier_changes_only_disposable_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = os.path.join(tmp, "marker.txt")
            with open(marker, "w", encoding="utf-8") as file:
                file.write("original")

            result = Verifier().run(
                [
                    "python",
                    "-c",
                    "from pathlib import Path; Path('marker.txt').write_text('changed'); print(Path('marker.txt').read_text())",
                ],
                cwd=tmp,
            )

            self.assertTrue(result.passed, result.stderr)
            self.assertIn("changed", result.stdout)
            with open(marker, encoding="utf-8") as file:
                self.assertEqual(file.read(), "original")

    def test_verifier_hides_env_files_and_parent_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as file:
                file.write("PRIVATE=value")
            with open(os.path.join(tmp, ".envrc"), "w", encoding="utf-8") as file:
                file.write("PRIVATE=value")
            with open(os.path.join(tmp, ".env.example"), "w", encoding="utf-8") as file:
                file.write("PUBLIC=example")

            command = [
                "python",
                "-c",
                "import os; from pathlib import Path; print(os.getenv('VERIFIER_PARENT_SECRET', 'absent')); print(Path('.env').exists(), Path('.envrc').exists(), Path('.env.example').exists())",
            ]
            with patch.dict(os.environ, {"VERIFIER_PARENT_SECRET": "hidden"}):
                result = Verifier().run(command, cwd=tmp)

            self.assertTrue(result.passed, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["absent", "False False True"])

    def test_verifier_cannot_reach_parent_loopback_listener(self) -> None:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        self.addCleanup(listener.close)

        with tempfile.TemporaryDirectory() as tmp:
            result = Verifier().run(
                [
                    "python",
                    "-c",
                    "import socket,sys; s=socket.socket(); s.settimeout(1); "
                    "exec('try:\\n s.connect((\"127.0.0.1\", '+sys.argv[1]+'))\\n print(\"connected\")\\nexcept OSError:\\n print(\"isolated\")')",
                    str(listener.getsockname()[1]),
                ],
                cwd=tmp,
            )

            self.assertTrue(result.passed, result.stderr)
            self.assertIn("isolated", result.stdout)

    def test_verifier_fails_closed_without_bubblewrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("agent_runtime.shutil.which", return_value=None):
            result = Verifier().run(["python", "-c", "print('must not run')"], cwd=tmp)

        self.assertFalse(result.passed)
        self.assertEqual(result.exit_code, 126)
        self.assertIn("bubblewrap, prlimit, and libseccomp are required", result.stderr)

    def test_verifier_applies_resource_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = Verifier().run(
                [
                    "python",
                    "-c",
                    "import json,resource; print(json.dumps([resource.getrlimit(r) for r in "
                    "(resource.RLIMIT_CPU, resource.RLIMIT_AS, resource.RLIMIT_FSIZE, "
                    "resource.RLIMIT_NOFILE, resource.RLIMIT_CORE)]))",
                ],
                cwd=tmp,
            )

        self.assertTrue(result.passed, result.stderr)
        limits = json.loads(result.stdout)
        self.assertEqual(limits[0], [30, 30])
        self.assertEqual(limits[1], [2147483648, 2147483648])
        self.assertEqual(limits[2], [536870912, 536870912])
        self.assertEqual(limits[3], [256, 256])
        self.assertEqual(limits[4], [0, 0])

    def test_verifier_installs_seccomp_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = Verifier().run(
                [
                    "python",
                    "-c",
                    "import ctypes; libc=ctypes.CDLL(None, use_errno=True); "
                    "mode=libc.prctl(21, 0, 0, 0, 0); denied=libc.ptrace(0, 0, 0, 0); "
                    "print(mode, denied, ctypes.get_errno())",
                ],
                cwd=tmp,
            )

        self.assertTrue(result.passed, result.stderr)
        self.assertEqual(result.stdout.strip(), "2 -1 1")

    def test_agent_runtime_orchestrates_success(self) -> None:
        runtime = AgentRuntime()
        task = runtime.create_task(
            "readme-check",
            "Ensure README mentions project",
            dependencies=[],
            priority=5,
        )
        task_id = task["id"]
        runtime.plan([task_id])
        runtime.update_status(task_id, TaskState.planned)
        runtime.update_status(task_id, TaskState.executing)
        runtime.update_status(task_id, TaskState.verifying)
        runtime.update_status(task_id, TaskState.completed)
        self.assertEqual(runtime.get_status(task_id), TaskState.completed)

    def test_plan_goal_imports_planner_tasks_and_dependencies(self) -> None:
        runtime = AgentRuntime()
        plan = runtime.plan_goal("add a feature")
        runtime_tasks = runtime.graph.tasks()

        self.assertEqual(set(runtime_tasks), {task["id"] for task in plan["tasks"]})
        self.assertTrue(all(task.status == TaskState.planned for task in runtime_tasks.values()))

        ready = runtime.graph.next_ready_tasks()
        self.assertEqual(len(ready), 1)
        first_task = runtime_tasks[ready[0]]
        self.assertEqual(first_task.metadata["kind"], "investigate")

        runtime.update_status(first_task.id, TaskState.executing)
        runtime.update_status(first_task.id, TaskState.verifying)
        runtime.update_status(first_task.id, TaskState.completed)

        ready = runtime.graph.next_ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(runtime_tasks[ready[0]].metadata["kind"], "plan")


if __name__ == "__main__":
    unittest.main()
