#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ast_patcher import ASTPatcher


class ASTPatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = ASTPatcher()

    def test_replaces_decorated_nested_method_and_preserves_other_source(self) -> None:
        source = (
            "class Service:\n"
            "    @staticmethod\n"
            "    def run(value):\n"
            "        return value + 1\n"
            "\n"
            "    def keep(self):\n"
            "        return 'untouched'\n"
        )

        updated = self.patcher.replace_symbol(
            source,
            "run",
            "@staticmethod\ndef run(value):\n    return value + 2",
        )

        self.assertEqual(
            updated,
            "class Service:\n"
            "    @staticmethod\n"
            "    def run(value):\n"
            "        return value + 2\n"
            "\n"
            "    def keep(self):\n"
            "        return 'untouched'\n",
        )

    def test_preserves_tab_indentation(self) -> None:
        source = "class Service:\n\tdef run(self):\n\t\treturn 1\n"

        updated = self.patcher.replace_symbol(
            source,
            "run",
            "def run(self):\n    return 2",
        )

        self.assertEqual(updated, "class Service:\n\tdef run(self):\n\t    return 2\n")

    def test_duplicate_names_require_line_selector(self) -> None:
        source = "def render():\n    return 1\n\ndef render():\n    return 2\n"

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.patcher.replace_symbol(source, "render", "def render():\n    return 3")

        updated = self.patcher.replace_symbol(
            source,
            "render",
            "def render():\n    return 3",
            line=4,
        )
        self.assertIn("def render():\n    return 1", updated)
        self.assertIn("def render():\n    return 3", updated)

    def test_invalid_replacement_does_not_change_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "module.py"
            original = "def target():\n    return 1\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(SyntaxError):
                self.patcher.replace_file_symbol(
                    path,
                    "target",
                    "def target(:\n    return 2",
                )

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_file_replacement_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "module.py"
            path.write_text("def target():\n    return 1\n", encoding="utf-8")

            updated = self.patcher.replace_file_symbol(
                path,
                "target",
                "def target():\n    return 2",
            )

            self.assertEqual(path.read_text(encoding="utf-8"), updated)
            self.assertIn("return 2", updated)

    def test_file_replacement_preserves_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "module.py"
            path.write_bytes(b"def target():\r\n    return 1\r\n")

            self.patcher.replace_file_symbol(
                path,
                "target",
                "def target():\n    return 2",
            )

            self.assertEqual(path.read_bytes(), b"def target():\r\n    return 2\r\n")


if __name__ == "__main__":
    unittest.main()