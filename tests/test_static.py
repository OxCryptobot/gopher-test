#!/usr/bin/env python3
"""Static asset contract tests for GOPHER AI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


class StaticTests(unittest.TestCase):
    def test_index_has_play_fetch_and_hash(self) -> None:
        html = read("index.html")
        self.assertIn("PLAY FETCH", html)
        self.assertIn("#/fetch", html)

    def test_manifest_is_gopher_ai_with_icons(self) -> None:
        raw = read("manifest.json")
        data = json.loads(raw)
        self.assertEqual(data.get("name"), "GOPHER AI")
        icons = data.get("icons")
        self.assertIsInstance(icons, list)
        self.assertTrue(icons, "manifest.json icons is empty")

    def test_sw_cache_name(self) -> None:
        self.assertIn("gopher-v5", read("sw.js"))

    def test_game_exports(self) -> None:
        src = read("game.js")
        self.assertIn("pauseToggle", src)
        self.assertIn("FetchGame", src)

    def test_dig_js_exists_and_exports_diggame(self) -> None:
        path = os.path.join(ROOT, "dig.js")
        self.assertTrue(os.path.isfile(path), "dig.js should exist")
        src = read("dig.js")
        self.assertIn("DigGame", src)

    def test_game_maze_rewrite_strings(self) -> None:
        """Asserts the FETCH maze rewrite. Passes after game.js lands; ok to fail until then."""
        src = read("game.js")
        self.assertIn("fox", src.lower())
        self.assertIn("maze", src.lower())
        self.assertIn("Huzaaa", src)
        self.assertIn("Clunk", src)
        self.assertIn("Ouchies", src)
        self.assertIn("TIME OVER", src)
        self.assertIn("GOPHER CHAMPION", src)
        self.assertTrue(
            "maxLvl" in src or "100" in src,
            "game.js should mention maxLvl or 100 stages",
        )

    def test_server_py_compile(self) -> None:
        path = os.path.join(ROOT, "server.py")
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            proc.stderr or proc.stdout or "py_compile failed",
        )

    def test_404_links_to_fetch(self) -> None:
        self.assertIn("#/fetch", read("404.html"))

    def test_no_banned_vendor_copy(self) -> None:
        banned = ("grok", "spacexai")
        for name in ("index.html", "app.js", "sw.js"):
            src = read(name).lower()
            for token in banned:
                self.assertNotIn(token, src, name + " has " + token)
            self.assertNotIn("cursor", src, name + " has cursor")


def main() -> int:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(StaticTests)
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
