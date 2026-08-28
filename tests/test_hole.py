#!/usr/bin/env python3
"""hole.json contract tests for GOPHER AI."""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOLE_PATH = os.path.join(ROOT, "hole.json")

REQUIRED_HOLES = (
    "/docs",
    "/fetch",
    "/privacy",
    "/pricing",
    "/terms",
    "/faq",
    "/ship",
    "/scores",
    "/play",
)
BANNED = ("grok", "cursor", "spacexai")
TEXT_KEYS = ("copy", "caps", "note", "title")


def load_hole() -> dict:
    with open(HOLE_PATH, encoding="utf-8") as f:
        return json.load(f)


def flatten_text(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(flatten_text(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(flatten_text(item))
        return out
    return []


def collect_marked_text(obj) -> list[str]:
    texts: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in TEXT_KEYS:
                texts.extend(flatten_text(value))
            else:
                texts.extend(collect_marked_text(value))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(collect_marked_text(item))
    return texts


def catalog_paths(data: dict) -> set[str]:
    paths: set[str] = set()
    holes = data.get("holes") or {}
    paths.update(holes)
    alias = data.get("alias") or {}
    for dest in alias.values():
        if isinstance(dest, str):
            paths.add(dest)
    for hole in holes.values():
        if not isinstance(hole, dict):
            continue
        for item in hole.get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                paths.add(item["path"])
    return paths


class HoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_hole()
        cls.holes = cls.data.get("holes") or {}
        cls.alias = cls.data.get("alias") or {}

    def test_json_parses(self) -> None:
        self.assertIsInstance(self.data, dict)
        self.assertIn("holes", self.data)
        self.assertIn("alias", self.data)
        self.assertIsInstance(self.holes, dict)
        self.assertIsInstance(self.alias, dict)

    def test_home_selector_5_is_fetch(self) -> None:
        home = self.holes.get("/")
        self.assertIsInstance(home, dict, "holes['/'] missing")
        items = home.get("items") or []
        match = None
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("n")) == "5":
                match = item
                break
        self.assertIsNotNone(match, "holes['/'] has no selector n=5")
        name = str(match.get("name") or "")
        self.assertTrue(
            name.rstrip("/").upper() == "FETCH" or "FETCH/" in name.upper() or name.upper() == "FETCH/",
            f"selector n=5 name is {name!r}, expected FETCH/",
        )
        self.assertEqual(match.get("path"), "/fetch")

    def test_aliases_fetch_and_play_map_to_fetch(self) -> None:
        self.assertEqual(self.alias.get("fetch"), "/fetch")
        self.assertEqual(self.alias.get("play"), "/fetch")

    def test_required_holes_exist(self) -> None:
        known = catalog_paths(self.data)
        missing = [path for path in REQUIRED_HOLES if path not in known]
        self.assertEqual(missing, [], f"required holes missing: {missing}")

    def test_no_banned_vendor_copy(self) -> None:
        texts = collect_marked_text(self.data)
        hits = []
        for text in texts:
            lower = text.lower()
            for token in BANNED:
                if token in lower:
                    hits.append((token, text[:120]))
        self.assertEqual(hits, [], f"banned vendor text in copy/caps/note/title: {hits}")


def main() -> int:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(HoleTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    except AssertionError as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
