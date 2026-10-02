#!/usr/bin/env python3
"""Replace Python definitions using AST locations and validate before writing."""
from __future__ import annotations

import ast
import hashlib
import os
import stat
import tempfile
import textwrap
from pathlib import Path


class ASTPatcher:
    """Apply validated, definition-scoped replacements to Python source."""

    def replace_symbol(
        self,
        source: str,
        name: str,
        replacement: str,
        *,
        line: int | None = None,
    ) -> str:
        tree = ast.parse(source)
        candidates = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == name
            and (line is None or node.lineno == line)
        ]
        if not candidates:
            raise LookupError(f"definition not found: {name}")
        if len(candidates) > 1:
            raise ValueError(f"definition is ambiguous: {name}; provide its line")

        target = candidates[0]
        replacement_text = textwrap.dedent(replacement).strip("\r\n")
        replacement_tree = ast.parse(replacement_text)
        if len(replacement_tree.body) != 1:
            raise ValueError("replacement must contain exactly one definition")
        new_node = replacement_tree.body[0]
        if not isinstance(new_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            raise ValueError("replacement must be a function or class definition")
        if new_node.name != name:
            raise ValueError(f"replacement name must be {name}")
        if isinstance(target, ast.ClassDef) != isinstance(new_node, ast.ClassDef):
            raise ValueError("replacement must preserve the definition kind")

        start_line = min(
            [target.lineno, *(decorator.lineno for decorator in target.decorator_list)]
        )
        definition_line = source.splitlines()[target.lineno - 1]
        indent = definition_line[: len(definition_line) - len(definition_line.lstrip(" \t"))]
        string_continuation: set[int] = set()
        for node in ast.walk(replacement_tree):
            if isinstance(node, (ast.Constant, ast.JoinedStr)) and (
                isinstance(node, ast.JoinedStr) or isinstance(node.value, (str, bytes))
            ):
                end = getattr(node, "end_lineno", None)
                if end and end > node.lineno:
                    string_continuation.update(range(node.lineno + 1, end + 1))
        replacement_lines = [
            indent + line_text if line_text and number not in string_continuation else line_text
            for number, line_text in enumerate(replacement_text.splitlines(), start=1)
        ]

        lines = source.splitlines()
        lines[start_line - 1 : target.end_lineno] = replacement_lines
        newline = "\r\n" if "\r\n" in source else "\n"
        updated = newline.join(lines)
        if source.endswith(("\n", "\r")):
            updated += newline
        ast.parse(updated)
        return updated

    def replace_file_symbol(
        self,
        path: str | os.PathLike[str],
        name: str,
        replacement: str,
        *,
        line: int | None = None,
        expected_sha256: str | None = None,
    ) -> str:
        source_path = Path(path).resolve()
        raw = source_path.read_bytes()
        if expected_sha256 and hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise RuntimeError(f"file changed since it was read: {source_path}")
        source = raw.decode("utf-8")
        updated = self.replace_symbol(source, name, replacement, line=line)
        original_mode = stat.S_IMODE(source_path.stat().st_mode)
        fd, temporary_path = tempfile.mkstemp(dir=source_path.parent, prefix=f".{source_path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as temporary_file:
                temporary_file.write(updated)
            os.chmod(temporary_path, original_mode)
            if source_path.read_bytes() != raw:
                raise RuntimeError(f"file changed during patch: {source_path}")
            os.replace(temporary_path, source_path)
        except BaseException:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            raise
        return updated


__all__ = ["ASTPatcher"]