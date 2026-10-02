#!/usr/bin/env python3
"""Repository semantic indexing and symbol graph.

Builds a queryable index of:
- Symbol definitions (classes, functions, variables)
- Import relationships
- Call graphs (who calls whom)
- Dependency graph (file-level)
- Type hints and signatures
- Module hierarchy
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_SKIP_DIRS = {"node_modules", "venv", "env", "__pycache__", "site-packages", "dist", "build"}


@dataclass
class Symbol:
    """A named entity (class, function, variable) in code."""
    name: str
    kind: str  # "class", "function", "variable", "import"
    file: str
    line: int
    col: int
    doc: str = ""
    signature: str = ""
    scope: str = "module"  # "module", "class", "function"
    parent: str | None = None
    qualname: str = ""


@dataclass
class ImportEdge:
    """An import relationship: A imports B."""
    source_file: str
    target_module: str
    names: list[str] = field(default_factory=list)
    is_relative: bool = False


@dataclass
class CallEdge:
    """A call relationship: function A calls function B."""
    caller: str  # full name
    callee: str  # full name
    call_site_file: str
    call_site_line: int


class RepositoryIndex:
    """A queryable semantic index of a repository."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.symbols: dict[str, list[Symbol]] = {}  # name -> [Symbol]
        self.symbols_by_file: dict[str, list[Symbol]] = {}  # file -> [Symbol]
        self.imports: list[ImportEdge] = []
        self.calls: list[CallEdge] = []
        self.file_deps: dict[str, set[str]] = {}  # file -> {file deps}

    def index(self, file_path: str) -> None:
        """Index a single Python file."""
        rel_path = str(Path(file_path).relative_to(self.root))
        self._remove_file(rel_path)

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return

        symbols = self._extract_symbols(tree, rel_path, source)
        imports = self._extract_imports(tree, rel_path)
        calls = self._extract_calls(tree, rel_path)

        self.symbols_by_file[rel_path] = symbols
        for sym in symbols:
            if sym.name not in self.symbols:
                self.symbols[sym.name] = []
            self.symbols[sym.name].append(sym)

        self.imports.extend(imports)
        self.calls.extend(calls)

        # Build file-level dependency graph: store module names as dependencies
        deps = {imp.target_module for imp in imports}
        self.file_deps[rel_path] = deps

    def _remove_file(self, file: str) -> None:
        """Remove a file's previous records before reindexing it."""
        for symbol in self.symbols_by_file.pop(file, []):
            definitions = [item for item in self.symbols[symbol.name] if item.file != file]
            if definitions:
                self.symbols[symbol.name] = definitions
            else:
                del self.symbols[symbol.name]

        self.imports = [edge for edge in self.imports if edge.source_file != file]
        self.calls = [edge for edge in self.calls if edge.call_site_file != file]
        self.file_deps.pop(file, None)

    def index_all(self, extensions: list[str] | None = None) -> None:
        """Index all Python files in the repo."""
        if extensions is None:
            extensions = [".py"]
        indexed_files: set[str] = set()
        for file_path in self.root.rglob("*"):
            rel_parts = file_path.relative_to(self.root).parts
            if file_path.suffix not in extensions or not file_path.is_file():
                continue
            if any(part.startswith(".") or part in _SKIP_DIRS for part in rel_parts[:-1]):
                continue
            if file_path.is_symlink():
                continue
            self.index(str(file_path))
            indexed_files.add(str(file_path.relative_to(self.root)))

        for file in list(self.symbols_by_file):
            if Path(file).suffix in extensions and file not in indexed_files:
                self._remove_file(file)

    def find_symbol(self, name: str) -> list[Symbol]:
        """Find all definitions of a symbol by name."""
        return self.symbols.get(name, [])

    def find_in_file(self, file: str) -> list[Symbol]:
        """Find all symbols defined in a file."""
        return self.symbols_by_file.get(file, [])

    def find_calls_to(self, func_name: str) -> list[CallEdge]:
        """Find all call sites for a function (bare or qualified name)."""
        suffix = "." + func_name
        return [c for c in self.calls if c.callee == func_name or c.callee.endswith(suffix)]

    def find_calls_from(self, func_name: str) -> list[CallEdge]:
        """Find all functions called by a function (bare or qualified name)."""
        suffix = "." + func_name
        return [c for c in self.calls if c.caller == func_name or c.caller.endswith(suffix)]

    @staticmethod
    def _module_names(file: str) -> set[str]:
        parts = list(Path(file).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return {".".join(parts[i:]) for i in range(len(parts))}

    def dependents(self, file: str) -> set[str]:
        """Find files that import this file."""
        names = self._module_names(file)
        out: set[str] = set()
        for edge in self.imports:
            if edge.source_file == file:
                continue
            module = edge.target_module
            candidates = {module, *(f"{module}.{n}" if module else n for n in edge.names)}
            if candidates & names:
                out.add(edge.source_file)
        return out

    def dependencies(self, file: str) -> set[str]:
        """Find files that this file depends on."""
        return self.file_deps.get(file, set())

    def _extract_symbols(self, tree: ast.AST, file: str, source: str) -> list[Symbol]:
        """Extract all symbol definitions from an AST."""
        symbols: list[Symbol] = []
        lines = source.splitlines()

        def visit(node: ast.AST, scope: str, parent: str | None) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qual = f"{parent}.{child.name}" if parent else child.name
                    symbols.append(
                        Symbol(
                            name=child.name,
                            kind="class" if isinstance(child, ast.ClassDef) else "function",
                            file=file,
                            line=child.lineno or 0,
                            col=child.col_offset or 0,
                            doc=ast.get_docstring(child) or "",
                            signature=self._get_signature(child, lines),
                            scope=scope,
                            parent=parent,
                            qualname=qual,
                        )
                    )
                    visit(child, "class" if isinstance(child, ast.ClassDef) else "function", qual)
                else:
                    visit(child, scope, parent)

        visit(tree, "module", None)
        return symbols

    def _extract_imports(self, tree: ast.AST, file: str) -> list[ImportEdge]:
        """Extract import statements."""
        imports: list[ImportEdge] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportEdge(source_file=file, target_module=alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(
                    ImportEdge(
                        source_file=file,
                        target_module=module,
                        names=names,
                        is_relative=node.level > 0,
                    )
                )

        return imports

    def _extract_calls(self, tree: ast.AST, file: str) -> list[CallEdge]:
        """Extract direct and attribute-based call relationships."""
        calls: list[CallEdge] = []

        def resolve_callee(node: ast.AST) -> str | None:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                base = resolve_callee(node.value)
                if base is None:
                    return node.attr
                return f"{base}.{node.attr}"
            if isinstance(node, ast.Call):
                return resolve_callee(node.func)
            return None

        class CallVisitor(ast.NodeVisitor):
            def __init__(self, file: str):
                self.file = file
                self.stack: list[str] = []
                self.in_func = 0

            def _enter(self, node: ast.AST, is_func: bool) -> None:
                self.stack.append(node.name)  # type: ignore[attr-defined]
                self.in_func += is_func
                self.generic_visit(node)
                self.in_func -= is_func
                self.stack.pop()

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._enter(node, False)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._enter(node, True)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._enter(node, True)

            def visit_Call(self, node: ast.Call) -> None:
                if self.in_func:
                    callee = resolve_callee(node.func)
                    if callee:
                        classes = [s for s in self.stack[:-1] if s[:1].isupper()]
                        if callee.startswith("self.") and classes:
                            callee = f"{classes[-1]}.{callee[5:]}"
                        calls.append(
                            CallEdge(
                                caller=".".join(self.stack),
                                callee=callee,
                                call_site_file=self.file,
                                call_site_line=node.lineno or 0,
                            )
                        )
                self.generic_visit(node)

        visitor = CallVisitor(file)
        visitor.visit(tree)
        return calls

    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, lines: list[str]) -> str:
        """Extract the function/class signature."""
        if node.lineno is None or node.lineno < 1:
            return ""
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            return f"class {node.name}({bases}):" if bases else f"class {node.name}:"
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{prefix} {node.name}({ast.unparse(node.args)}){ret}:"


__all__ = ["RepositoryIndex", "Symbol", "ImportEdge", "CallEdge"]
