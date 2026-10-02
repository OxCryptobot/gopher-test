"""Regression tests for audit findings W2, W5, W9, W10, W11, W12, W15."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import subprocess

from agent_runtime import Verifier, _clip
from ast_patcher import ASTPatcher
from planner import Planner, TaskKind
from repo_index import RepositoryIndex


class VerifierTests(unittest.TestCase):
    def test_timeout_returns_124_not_exception(self) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1, b"out", b"err")):
            with mock.patch("agent_runtime.shutil.which", return_value="/bin/true"), mock.patch(
                "agent_runtime.ctypes.util.find_library", return_value="libseccomp.so.2"
            ), mock.patch.object(Verifier, "_export_seccomp_policy"):
                result = Verifier().run(["sleep", "9"], timeout=1)
        self.assertEqual(result.exit_code, 124)
        self.assertFalse(result.passed)

    def test_clip_limits_output(self) -> None:
        self.assertLessEqual(len(_clip("x" * 500_000)), 70_000)
        self.assertEqual(_clip(None), "")


class PlannerRecoveryTests(unittest.TestCase):
    def test_failed_edit_does_not_unblock_verify(self) -> None:
        planner = Planner()
        plan = planner.plan("fix bug")
        by_kind = {t["kind"]: t["id"] for t in plan["tasks"]}
        for kind in ("investigate", "plan"):
            planner.mark_executed(by_kind[kind])
        planner.replan_after_failure(by_kind["edit"], "boom")
        self.assertNotIn(by_kind["verify"], planner.next_ready_tasks())

    def test_verify_runs_after_retry_succeeds(self) -> None:
        planner = Planner()
        plan = planner.plan("fix bug")
        by_kind = {t["kind"]: t["id"] for t in plan["tasks"]}
        for kind in ("investigate", "plan"):
            planner.mark_executed(by_kind[kind])
        recovery = planner.replan_after_failure(by_kind["edit"], "boom")
        for node in recovery:
            self.assertIn(node.id, planner.next_ready_tasks())
            planner.mark_executed(node.id)
        self.assertIn(by_kind["verify"], planner.next_ready_tasks())
        self.assertEqual(recovery[-1].kind, TaskKind.edit)


class PatcherTests(unittest.TestCase):
    def test_multiline_string_content_is_preserved(self) -> None:
        src = "class A:\n    def m(self):\n        return 1\n"
        new = 'def m(self):\n    return """a\nb"""\n'
        out = ASTPatcher().replace_symbol(src, "m", new)
        self.assertIn('return """a\nb"""', out)

    def test_hash_precondition_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.py"
            real.write_text("def f():\n    return 1\n")
            link = Path(tmp) / "link.py"
            link.symlink_to(real)
            patcher = ASTPatcher()
            with self.assertRaises(RuntimeError):
                patcher.replace_file_symbol(link, "f", "def f():\n    return 2\n", expected_sha256="0" * 64)
            good = hashlib.sha256(real.read_bytes()).hexdigest()
            patcher.replace_file_symbol(link, "f", "def f():\n    return 2\n", expected_sha256=good)
            self.assertTrue(link.is_symlink())
            self.assertIn("return 2", real.read_text())


class IndexTests(unittest.TestCase):
    def test_dependents_resolve_to_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("def x(): pass\n")
            (Path(tmp) / "b.py").write_text("from a import x\n")
            (Path(tmp) / "c.py").write_text("import a\n")
            idx = RepositoryIndex(tmp)
            idx.index_all()
            self.assertEqual(idx.dependents("a.py"), {"b.py", "c.py"})

    def test_root_under_dot_directory_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".hidden" / "proj"
            root.mkdir(parents=True)
            (root / "m.py").write_text("def f(): pass\n")
            idx = RepositoryIndex(str(root))
            idx.index_all()
            self.assertTrue(idx.find_symbol("f"))

    def test_vendor_dirs_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "venv").mkdir()
            (Path(tmp) / "venv" / "v.py").write_text("def vendored(): pass\n")
            idx = RepositoryIndex(tmp)
            idx.index_all()
            self.assertFalse(idx.find_symbol("vendored"))

    def test_methods_are_qualified_and_self_calls_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "m.py").write_text(
                "class A:\n    def run(self):\n        self.go()\n    def go(self): pass\n"
                "class B:\n    def run(self): pass\n"
            )
            idx = RepositoryIndex(tmp)
            idx.index_all()
            runs = {s.qualname for s in idx.find_symbol("run")}
            self.assertEqual(runs, {"A.run", "B.run"})
            self.assertEqual([c.caller for c in idx.find_calls_to("go")], ["A.run"])

    def test_multiline_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "m.py").write_text("def f(\n    a: int,\n    b=(1, 2),\n) -> int:\n    return a\n")
            idx = RepositoryIndex(tmp)
            idx.index_all()
            self.assertIn("b=(1, 2)", idx.find_symbol("f")[0].signature)


if __name__ == "__main__":
    unittest.main()
