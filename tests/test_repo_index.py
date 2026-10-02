#!/usr/bin/env python3
"""Tests for repository semantic indexing."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from repo_index import CallEdge, ImportEdge, RepositoryIndex, Symbol


class RepositoryIndexTests(unittest.TestCase):
    def test_extract_functions_and_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "module.py").write_text(
                """
class MyClass:
    '''A test class.'''
    pass

def my_function(x: int) -> int:
    '''A test function.'''
    return x + 1
"""
            )

            idx = RepositoryIndex(tmp)
            idx.index(str(tmp_path / "module.py"))

            symbols = idx.find_symbol("MyClass")
            self.assertEqual(len(symbols), 1)
            self.assertEqual(symbols[0].kind, "class")
            self.assertIn("test class", symbols[0].doc)

            functions = idx.find_symbol("my_function")
            self.assertEqual(len(functions), 1)
            self.assertEqual(functions[0].kind, "function")

    def test_extract_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "importer.py").write_text(
                """
import os
import sys
from pathlib import Path
from typing import Any, Dict
"""
            )

            idx = RepositoryIndex(tmp)
            idx.index(str(tmp_path / "importer.py"))

            self.assertGreater(len(idx.imports), 0)
            modules = {imp.target_module for imp in idx.imports}
            self.assertIn("os", modules)
            self.assertIn("pathlib", modules)
            self.assertIn("typing", modules)

    def test_file_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("import os\n")
            (tmp_path / "b.py").write_text("from a import something\n")

            idx = RepositoryIndex(tmp)
            idx.index_all()

            # a.py depends on os module
            deps_of_a = idx.dependencies("a.py")
            self.assertIn("os", deps_of_a)

    def test_find_calls_to_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "callers.py").write_text(
                """
def helper():
    pass

def func_a():
    helper()

def func_b():
    helper()
    helper()
"""
            )

            idx = RepositoryIndex(tmp)
            idx.index(str(tmp_path / "callers.py"))

            calls_to_helper = idx.find_calls_to("helper")
            self.assertEqual(len(calls_to_helper), 3)  # 1 in func_a, 2 in func_b
            self.assertTrue(all(c.callee == "helper" for c in calls_to_helper))

    def test_index_all_finds_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "file1.py").write_text("def func1(): pass\n")
            (tmp_path / "file2.py").write_text("def func2(): pass\n")
            subdir = tmp_path / "sub"
            subdir.mkdir()
            (subdir / "file3.py").write_text("def func3(): pass\n")

            idx = RepositoryIndex(tmp)
            idx.index_all()

            self.assertIn("func1", idx.symbols)
            self.assertIn("func2", idx.symbols)
            self.assertIn("func3", idx.symbols)

    def test_reindex_replaces_stale_file_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "module.py"
            file_path.write_text("import old_module\ndef old_function(): pass\n")
            idx = RepositoryIndex(tmp)

            idx.index(str(file_path))
            idx.index(str(file_path))

            self.assertEqual(len(idx.find_symbol("old_function")), 1)

            file_path.write_text("import new_module\ndef new_function(): pass\n")
            idx.index(str(file_path))

            self.assertEqual(idx.find_symbol("old_function"), [])
            self.assertEqual(len(idx.find_symbol("new_function")), 1)
            self.assertEqual(idx.dependencies("module.py"), {"new_module"})

    def test_index_all_removes_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "module.py"
            file_path.write_text("def old_function(): pass\n")
            idx = RepositoryIndex(tmp)

            idx.index_all()
            file_path.unlink()
            idx.index_all()

            self.assertEqual(idx.find_symbol("old_function"), [])
            self.assertEqual(idx.find_in_file("module.py"), [])


if __name__ == "__main__":
    unittest.main()
