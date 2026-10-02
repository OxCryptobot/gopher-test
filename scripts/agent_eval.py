#!/usr/bin/env python3
"""Offline agent evals for orchestration and safety (not model quality)."""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_loop import Agent
from agent_providers import Reply, ScriptedProvider, ToolCall
from agent_store import Store
from agent_tools import ToolRegistry, Workspace


@dataclass
class CaseResult:
    name: str
    passed: bool
    steps: int
    tool_errors: int
    detail: str


def call(tool_name: str, **args: object) -> ToolCall:
    return ToolCall(f"eval-{tool_name}", tool_name, args)


def run_case(name: str, scenario) -> CaseResult:
    try:
        steps, errors, detail = scenario()
        return CaseResult(name, True, steps, errors, detail)
    except AssertionError as exc:
        return CaseResult(name, False, 0, 0, str(exc) or "expectation failed")


def edit_workflow() -> tuple[int, int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = "def add(a, b):\n    return a - b\n"
        target = root / "maths.py"
        target.write_text(source)
        provider = ScriptedProvider([
            Reply(tool_calls=[call("read_file", path="maths.py")]),
            Reply(tool_calls=[call("edit_symbol", path="maths.py", name="add",
                                  replacement="def add(a, b):\n    return a + b\n")]),
            Reply(tool_calls=[call("finish", summary="fixed add")]),
        ])
        registry = ToolRegistry(allow={"read", "write"})
        Workspace(str(root)).register_all(registry)
        store = Store()
        result = Agent(provider, registry, store).run("Fix add in maths.py")
        assert result.ok and result.summary == "fixed add", result.summary
        assert "return a + b" in target.read_text(), "edit was not applied"
        assert result.tools_used == ["read_file", "edit_symbol"], result.tools_used
        errors = sum(bool(event["data"].get("error")) for event in store.events(result.run_id)
                     if event["kind"] == "tool")
        assert errors == 0, f"unexpected tool errors: {errors}"
        return result.steps, errors, "repair applied and finished"


def write_permission_denied() -> tuple[int, int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original = "def add(a, b):\n    return a - b\n"
        target = root / "maths.py"
        target.write_text(original)
        provider = ScriptedProvider([
            Reply(tool_calls=[call("edit_symbol", path="maths.py", name="add",
                                  replacement="def add(a, b):\n    return a + b\n")]),
            Reply(tool_calls=[call("finish", summary="write blocked")]),
        ])
        registry = ToolRegistry(allow={"read"})
        Workspace(str(root)).register_all(registry)
        store = Store()
        result = Agent(provider, registry, store).run("Try to edit maths.py")
        events = [event for event in store.events(result.run_id) if event["kind"] == "tool"]
        errors = sum(bool(event["data"].get("error")) for event in events)
        assert result.ok and result.summary == "write blocked", result.summary
        assert target.read_text() == original, "read-only run changed a file"
        assert errors == 1, f"expected one denied tool call, got {errors}"
        return result.steps, errors, "read-only permission held"


def path_traversal_blocked() -> tuple[int, int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        root = base / "workspace"
        root.mkdir()
        (base / "outside.txt").write_text("SECRET_SENTINEL")

        class LeakCheckingProvider:
            def __init__(self) -> None:
                self.script = ScriptedProvider([
                    Reply(tool_calls=[call("read_file", path="../outside.txt")]),
                    Reply(tool_calls=[call("finish", summary="path blocked")]),
                ])
                self.leaked = False

            def complete(self, messages, tools):
                self.leaked |= any("SECRET_SENTINEL" in str(message.get("content", ""))
                                   for message in messages)
                return self.script.complete(messages, tools)

        provider = LeakCheckingProvider()
        registry = ToolRegistry(allow={"read"})
        Workspace(str(root)).register_all(registry)
        store = Store()
        result = Agent(provider, registry, store).run("Read ../outside.txt")
        events = [event for event in store.events(result.run_id) if event["kind"] == "tool"]
        errors = sum(bool(event["data"].get("error")) for event in events)
        assert result.ok and result.summary == "path blocked", result.summary
        assert not provider.leaked, "outside file content reached the provider"
        assert errors == 1, f"expected one rejected tool call, got {errors}"
        return result.steps, errors, "outside content stayed inaccessible"


def repeated_call_stops() -> tuple[int, int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry(allow={"read"})
        Workspace(tmp).register_all(registry)
        provider = ScriptedProvider([Reply(tool_calls=[call("list_dir")]) for _ in range(8)])
        result = Agent(provider, registry, Store(), max_repeat=2).run("Keep listing")
        assert not result.ok and "loop detected" in result.summary, result.summary
        assert len(result.tools_used) == 2, result.tools_used
        return result.steps, 0, "identical calls stopped before another execution"


def step_budget_stops() -> tuple[int, int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "notes.txt").write_text("one\ntwo\n")
        registry = ToolRegistry(allow={"read"})
        Workspace(str(root)).register_all(registry)
        provider = ScriptedProvider([
            Reply(tool_calls=[call("read_file", path="notes.txt", start=1, end=1)]),
            Reply(tool_calls=[call("read_file", path="notes.txt", start=2, end=2)]),
            Reply(tool_calls=[call("finish", summary="should not run")]),
        ])
        result = Agent(provider, registry, Store(), max_steps=2).run("Read both lines")
        assert not result.ok and result.summary == "step budget exhausted", result.summary
        assert result.steps == 2, result.steps
        return result.steps, 0, "run stopped at configured step budget"


def run_suite() -> dict[str, object]:
    cases = [
        run_case("repair_workflow", edit_workflow),
        run_case("write_permission", write_permission_denied),
        run_case("path_traversal", path_traversal_blocked),
        run_case("repeated_call_guard", repeated_call_stops),
        run_case("step_budget", step_budget_stops),
    ]
    passed = sum(case.passed for case in cases)
    safety = [case for case in cases if case.name in {"write_permission", "path_traversal"}]
    steps = [case.steps for case in cases if case.passed]
    return {
        "passed": passed,
        "total": len(cases),
        "pass_rate": round(passed / len(cases), 3),
        "safety_passed": sum(case.passed for case in safety),
        "safety_total": len(safety),
        "mean_steps": round(sum(steps) / len(steps), 2) if steps else 0,
        "cases": [asdict(case) for case in cases],
        "scope": "Scripted-provider orchestration and safety only; does not measure model quality.",
    }


def main() -> int:
    report = run_suite()
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())