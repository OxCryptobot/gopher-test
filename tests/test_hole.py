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
    "/dig",
    "/privacy",
    "/pricing",
    "/terms",
    "/faq",
    "/ship",
    "/scores",
    "/play",
    "/blueprint",
    "/plugins",
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

    def test_brain_empty_default(self) -> None:
        self.assertIn("brain", self.data)
        self.assertEqual(self.data.get("brain"), "")

    def test_home_selector_5_is_play(self) -> None:
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
        upper = name.rstrip("/").upper()
        self.assertTrue(
            upper in ("PLAY", "SEARCH") or name.upper() in ("PLAY/", "SEARCH/"),
            f"selector n=5 name is {name!r}, expected Play/ or Search/",
        )
        self.assertNotIn("FETCH", name.upper())
        self.assertIn(match.get("path"), ("/games", "/", "/play"))

    def test_aliases_maze_burrow_and_play(self) -> None:
        self.assertEqual(self.alias.get("fetch"), "/fetch")
        self.assertEqual(self.alias.get("maze"), "/fetch")
        self.assertEqual(self.alias.get("burrow"), "/dig")
        self.assertEqual(self.alias.get("dig"), "/dig")
        self.assertEqual(self.alias.get("play"), "/games")

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

    def test_tasks_json(self) -> None:
        path = os.path.join(ROOT, "tasks.json")
        self.assertTrue(os.path.isfile(path), "tasks.json missing")
        with open(path, encoding="utf-8") as f:
            raw = f.read()
            data = json.loads(raw)
        tasks = data.get("tasks")
        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 100, "tasks.json must have exactly 100 tasks")
        ids = []
        for task in tasks:
            self.assertIsInstance(task, dict)
            self.assertTrue(task.get("id"), "task missing id")
            self.assertTrue(task.get("q"), "task missing q")
            self.assertIn(task.get("kind"), ("nav", "fetch", "game", "queue", "set", "parked"))
            self.assertIn(task.get("run"), ("nav", "ask", "queue", "set", "parked"))
            ids.append(task["id"])
            if task.get("kind") == "parked" or task.get("run") == "parked":
                self.assertIs(task.get("live"), False, task.get("id") + " parked must be live false")
        self.assertEqual(len(ids), len(set(ids)), "task ids must be unique")
        for need in ("ask", "favorites", "usage", "search", "tasks", "waitlist"):
            self.assertIn(need, ids, "missing skill " + need)
        parked = [t for t in tasks if t.get("live") is False]
        self.assertEqual(len(parked), 9, "tasks.json must keep 9 parked")
        lower = raw.lower()
        hits = [token for token in BANNED if token in lower]
        self.assertEqual(hits, [], "banned vendor text in tasks.json: " + str(hits))

    def test_tasks_hole_exists(self) -> None:
        self.assertIn("/tasks", self.holes)
        self.assertEqual(self.alias.get("tasks"), "/tasks")
        hole = self.holes.get("/tasks") or {}
        blob = " ".join(flatten_text(hole)).lower()
        self.assertTrue(
            any(w in blob for w in ("catalog", "skills", "skill", "tap")),
            "/tasks should mention catalog/skills/tap, got: " + blob[:200],
        )
        self.assertNotIn("dig is do a task", blob)

    def test_public_price_nineteen(self) -> None:
        hole = self.holes.get("/pricing") or {}
        blob = " ".join(flatten_text(hole))
        low = blob.lower()
        self.assertIn("$19", blob)
        self.assertIn("month", low)
        self.assertIn("waitlist", low)
        self.assertTrue("parked" in low or "checkout" in low, blob[:240])
        for bad in ("$29", "$49", "$99/", "from $"):
            self.assertNotIn(bad, blob)
        self.assertNotIn("prices are not public yet", low)

    def test_prices_skill_is_public(self) -> None:
        path = os.path.join(ROOT, "tasks.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tasks = {t["id"]: t for t in data["tasks"]}
        pricing = tasks["pricing"]
        self.assertTrue(pricing.get("live"))
        self.assertIn("$19", pricing.get("hint") or "")
        self.assertEqual(pricing.get("path"), "/pricing")
        self.assertNotIn("prices", tasks)
        telegram = tasks["telegram"]
        self.assertIs(telegram.get("live"), False)
        self.assertEqual(telegram.get("kind"), "parked")

    def test_ship_marks_price_not_billing(self) -> None:
        text = open(os.path.join(ROOT, "SHIP.md"), encoding="utf-8").read()
        self.assertIn("Progress: 83/100", text)
        self.assertIn("phase 3 9/25", text)
        self.assertIn("82. [x] Published prices", text)
        self.assertIn("81. [ ] Billing", text)
        self.assertIn("78. [ ] SMS", text)
        self.assertIn("79. [ ] Voice", text)
        self.assertNotIn("78. [x]", text)
        self.assertNotIn("79. [x]", text)
        self.assertNotIn("81. [x]", text)

    def test_install_demo_distribution_holes(self) -> None:
        self.assertEqual(self.alias.get("install"), "/install")
        self.assertEqual(self.alias.get("pwa"), "/install")
        self.assertEqual(self.alias.get("demo"), "/demo")
        self.assertEqual(self.alias.get("distribution"), "/distribution")
        self.assertEqual(self.alias.get("dist"), "/distribution")
        install = self.holes.get("/install") or {}
        blob = " ".join(flatten_text(install)).lower()
        self.assertIn("pwa", blob)
        self.assertIn("waitlist", blob)
        self.assertIn("$19", " ".join(flatten_text(install)))
        self.assertIn("home screen", blob)
        demo = self.holes.get("/demo") or {}
        dblob = " ".join(flatten_text(demo)).lower()
        self.assertIn("video not yet", dblob)
        self.assertIn("shots/", dblob)
        self.assertIn("share-card", dblob)
        dist = self.holes.get("/distribution") or {}
        xblob = " ".join(flatten_text(dist)).lower()
        self.assertIn("phase d", xblob)
        self.assertIn("promote", xblob)
        self.assertIn("pwa", xblob)



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
