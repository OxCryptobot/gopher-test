#!/usr/bin/env python3
"""Live HTTP smoke against a local GOPHER python hole. No Twilio secrets."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 8


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = TIMEOUT):
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            ctype = resp.headers.get("Content-Type") or ""
            parsed = None
            if "json" in ctype or (raw[:1] in "{["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
            return resp.status, raw, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        return exc.code, raw, parsed


class LiveTests(unittest.TestCase):
    def test_live_smoke(self) -> None:
        port = free_port()
        env = os.environ.copy()
        env["GOPHER_HOST"] = "127.0.0.1"
        env["GOPHER_PORT"] = str(port)
        for key in (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_NUMBER",
            "GOPHER_MAIL_HOOK",
            "GOPHER_LLM_HOOK",
            "GOPHER_LLM_KEY",
            "GOPHER_PUBLIC_URL",
            "GOPHER_REPLY_URL",
            "SENDGRID_API_KEY",
            "GOPHER_TWILIO_SKIP_SIG",
        ):
            env[key] = ""
        log_path = "/tmp/gopher-live-test.log"
        proc = None
        logf = open(log_path, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                [sys.executable, "server.py"],
                cwd=ROOT,
                env=env,
                stdout=logf,
                stderr=logf,
            )
            base = "http://127.0.0.1:%s" % port
            deadline = time.time() + TIMEOUT
            last_err = "not started"
            while time.time() < deadline:
                if proc.poll() is not None:
                    logf.flush()
                    raise RuntimeError("server exited early; see " + log_path)
                try:
                    req = urllib.request.Request(base + "/health")
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        if resp.status == 200 and raw.strip() == "ok":
                            break
                        last_err = "health %s %r" % (resp.status, raw)
                except Exception as exc:
                    last_err = str(exc)
                    time.sleep(0.1)
            else:
                raise RuntimeError("server did not start: " + last_err)

            req = urllib.request.Request(base + "/health")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read().decode("utf-8", errors="replace").strip(), "ok")

            code, raw, status = http("GET", base + "/api/status")
            self.assertEqual(code, 200)
            self.assertIsInstance(status, dict)
            print("LIVE_STATUS_JSON " + json.dumps(status, sort_keys=True))

            req = urllib.request.Request(
                base + "/api/status",
                method="OPTIONS",
                headers={"Origin": "https://oxcryptobot.github.io", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                self.assertIn(resp.status, (200, 204))
                self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://oxcryptobot.github.io")

            req = urllib.request.Request(
                base + "/api/status",
                headers={"Origin": "https://oxcryptobot.github.io", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://oxcryptobot.github.io")

            for hidden in ("/.env", "/.env.local"):
                try:
                    urllib.request.urlopen(urllib.request.Request(base + hidden), timeout=TIMEOUT)
                    self.fail(hidden + " should not be served")
                except urllib.error.HTTPError as exc:
                    self.assertEqual(exc.code, 404)
            self.assertIs(status.get("sla"), False)
            plugins = status.get("plugins") or {}
            self.assertIs(plugins.get("ticker"), True)
            self.assertIs(plugins.get("sms"), False)
            self.assertEqual(status.get("twilio"), "parked")
            self.assertIs(plugins.get("voice"), False)
            self.assertIs(status.get("sms_number"), None)
            self.assertEqual(status.get("mail"), "parked")
            if "llm" in status:
                self.assertEqual(status.get("llm"), "parked")
            self.assertEqual((status.get("progress") or {}).get("done"), 82)

            code, raw, tasks = http("GET", base + "/api/tasks")
            self.assertEqual(code, 200)
            self.assertIsInstance(tasks, dict)
            self.assertIs(tasks.get("ok"), True)
            self.assertEqual(tasks.get("n"), 100)
            self.assertEqual(len(tasks.get("tasks") or []), 100)

            code, raw, body = http("POST", base + "/api/twilio/sms", data=b"")
            self.assertEqual(code, 503)
            self.assertIsInstance(body, dict)
            self.assertEqual(body.get("error"), "twilio parked")
            self.assertIs(body.get("sms"), False)
            self.assertIs(body.get("ok"), False)

            email = "live-%s@example.com" % uuid.uuid4().hex
            payload = json.dumps({"email": email}).encode("utf-8")
            code, raw, body = http(
                "POST",
                base + "/api/waitlist",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            self.assertEqual(code, 200)
            self.assertIn(body.get("status"), ("joined", "duplicate"))

            ask_q = "ping hole"
            payload = json.dumps({"q": ask_q}).encode("utf-8")
            code, raw, body = http(
                "POST",
                base + "/api/ask",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            self.assertEqual(code, 200)
            self.assertEqual(body.get("kind"), "queued")
            oid = body.get("id")
            self.assertTrue(oid, "queued ask must return id")

            code, raw, orders = http("GET", base + "/api/orders")
            self.assertEqual(code, 200)
            self.assertIsInstance(orders, list)
            qs = [row.get("q") for row in orders if isinstance(row, dict)]
            self.assertIn(ask_q, qs)
            hits = [row for row in orders if isinstance(row, dict) and row.get("id") == oid]
            self.assertTrue(hits, "GET /api/orders should include the ask id")
        finally:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            logf.close()


def main() -> int:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(LiveTests)
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
