#!/usr/bin/env python3
"""server.py source contract tests for GOPHER AI.

Reads server.py as text so tests never bind a port. Import is skipped because
module import chdir()s the process; compile() still checks syntax.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(ROOT, "server.py")


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(SERVER_PATH, encoding="utf-8") as f:
            cls.src = f.read()

    def test_source_compiles(self) -> None:
        compile(self.src, SERVER_PATH, "exec")

    def test_get_health(self) -> None:
        self.assertIn("/health", self.src)
        self.assertIn("do_GET", self.src)
        self.assertRegex(self.src, r'path == ["/\']\/health["\']')

    def test_get_api_scores(self) -> None:
        self.assertIn("/api/scores", self.src)
        self.assertRegex(self.src, r'path == ["/\']\/api/scores["\']')

    def test_get_api_champions(self) -> None:
        self.assertIn("/api/champions", self.src)
        self.assertRegex(self.src, r'path == ["/\']\/api/champions["\']')

    def test_get_api_status(self) -> None:
        self.assertIn("/api/status", self.src)
        self.assertIn("uptime_s", self.src)

    def test_get_api_orders(self) -> None:
        self.assertIn("/api/orders", self.src)

    def test_content_security_policy(self) -> None:
        self.assertIn("Content-Security-Policy", self.src)

    def test_max_post_bytes(self) -> None:
        self.assertIn("MAX_POST_BYTES", self.src)

    def test_twilio_routes(self) -> None:
        self.assertIn("/api/twilio/sms", self.src)
        self.assertIn("/api/twilio/voice", self.src)

    def test_doge_in_ticker_names(self) -> None:
        self.assertIn("TICKER_NAMES", self.src)
        self.assertIn('"DOGE"', self.src)
        self.assertIn("DOGE-USDT", self.src)

    def test_sla_false(self) -> None:
        self.assertIn('"sla": False', self.src)

    def test_twilio_parked_string(self) -> None:
        self.assertIn("twilio parked", self.src)


def main() -> int:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerTests)
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
