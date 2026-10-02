"""Tool registry (schemas, validation, permissions, timeouts) and workspace-scoped builtin tools."""
from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_runtime import Verifier
from ast_patcher import ASTPatcher

_TYPES = {"string": str, "integer": int, "boolean": bool, "number": (int, float)}
_SKIP = {".git", "node_modules", "__pycache__", "venv", ".venv"}


class ToolError(Exception):
    pass


@dataclass
class Tool:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: list[str]
    fn: Callable[..., str]
    permission: str = "read"  # read | write | exec
    timeout: float = 30.0

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": self.properties, "required": self.required},
        }


class ToolRegistry:
    def __init__(self, allow: set[str] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.allow = allow if allow is not None else {"read"}
        self._pool = ThreadPoolExecutor(max_workers=4)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values() if t.permission in self.allow]

    def call(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool: {name}")
        if tool.permission not in self.allow:
            raise ToolError(f"permission denied: {name} needs '{tool.permission}'")
        for key in tool.required:
            if key not in args:
                raise ToolError(f"missing argument: {key}")
        for key, value in args.items():
            prop = tool.properties.get(key)
            if prop is None:
                raise ToolError(f"unexpected argument: {key}")
            expected = _TYPES.get(prop.get("type", ""))
            if expected and (not isinstance(value, expected) or (expected is int and isinstance(value, bool))):
                raise ToolError(f"argument {key} must be {prop['type']}")
        future = self._pool.submit(tool.fn, **args)
        try:
            return str(future.result(timeout=tool.timeout))
        except FutureTimeout as exc:
            future.cancel()
            raise ToolError(f"{name} timed out after {tool.timeout}s") from exc
        except ToolError:
            raise
        except Exception as exc:  # tool bugs must not crash the loop
            raise ToolError(f"{name} failed: {type(exc).__name__}: {exc}") from exc


class Workspace:
    """Filesystem tools confined to a root directory."""

    def __init__(self, root: str, verifier: Verifier | None = None) -> None:
        self.root = Path(root).resolve()
        self.verifier = verifier or Verifier()
        self.patcher = ASTPatcher()
        self._undo: list[tuple[Path, str]] = []

    def _safe(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if path != self.root and self.root not in path.parents:
            raise ToolError("path escapes workspace")
        parts = path.relative_to(self.root).parts
        if any(p == ".git" or p == ".env" or p.startswith(".env.") for p in parts):
            raise ToolError("path is protected")
        return path

    def read_file(self, path: str, start: int = 1, end: int = 200) -> str:
        p = self._safe(path)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start, end = max(1, start), min(len(lines), max(start, end))
        return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))

    def list_dir(self, path: str = ".") -> str:
        p = self._safe(path)
        return "\n".join(sorted(c.name + ("/" if c.is_dir() else "") for c in p.iterdir() if c.name not in _SKIP))

    def grep(self, pattern: str, path: str = ".") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"bad regex: {exc}") from exc
        base, hits = self._safe(path), []
        files = [base] if base.is_file() else sorted(base.rglob("*"))
        for f in files:
            if len(hits) >= 50:
                break
            if not f.is_file() or f.is_symlink() or any(part in _SKIP for part in f.relative_to(self.root).parts):
                continue
            if f.name.startswith(".env"):
                continue
            try:
                for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f.relative_to(self.root)}:{n}: {line.strip()[:160]}")
                        if len(hits) >= 50:
                            break
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(hits) or "no matches"

    def edit_symbol(self, path: str, name: str, replacement: str) -> str:
        p = self._safe(path)
        before = p.read_text(encoding="utf-8")
        digest = hashlib.sha256(before.encode()).hexdigest()
        try:
            self.patcher.replace_file_symbol(p, name, replacement, expected_sha256=digest)
        except (LookupError, ValueError, SyntaxError) as exc:
            raise ToolError(f"edit rejected: {exc}") from exc
        self._undo.append((p, before))
        return f"replaced {name} in {path}"

    def undo_last_edit(self) -> str:
        if not self._undo:
            return "nothing to undo"
        p, text = self._undo.pop()
        p.write_text(text, encoding="utf-8")
        return f"restored {p.relative_to(self.root)}"

    def run_tests(self, command: str = "python3 -m pytest -q") -> str:
        result = self.verifier.run(command, cwd=str(self.root), timeout=60)
        status = "PASSED" if result.passed else f"FAILED (exit {result.exit_code})"
        return f"{status}\n{result.stdout[-3000:]}\n{result.stderr[-1500:]}".strip()

    def register_all(self, registry: ToolRegistry) -> None:
        s, i = {"type": "string"}, {"type": "integer"}
        registry.register(Tool("read_file", "Read numbered lines of a file.",
                               {"path": s, "start": i, "end": i}, ["path"], self.read_file))
        registry.register(Tool("list_dir", "List a directory.", {"path": s}, [], self.list_dir))
        registry.register(Tool("grep", "Regex search across files.", {"pattern": s, "path": s}, ["pattern"], self.grep))
        registry.register(Tool("edit_symbol", "Replace one Python function/class by name; validated before write.",
                               {"path": s, "name": s, "replacement": s}, ["path", "name", "replacement"],
                               self.edit_symbol, permission="write"))
        registry.register(Tool("undo_last_edit", "Revert the most recent edit.", {}, [],
                               self.undo_last_edit, permission="write"))
        registry.register(Tool("run_tests", "Run tests in the sandbox.", {"command": s}, [],
                               self.run_tests, permission="exec", timeout=90))
