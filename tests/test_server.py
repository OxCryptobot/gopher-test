#!/usr/bin/env python3
"""server.py source contract tests for GOPHER AI.

Reads server.py as text so tests never bind a port. Import is skipped because
module import chdir()s the process; compile() still checks syntax.
Live hook/reply tests import once and bind 127.0.0.1 only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(ROOT, "server.py")

_MOD = None
ENV_KEYS = (
    "GOPHER_LLM_HOOK",
    "GOPHER_LLM_KEY",
    "GOPHER_PUBLIC_URL",
    "GOPHER_REPLY_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "GOPHER_TELEGRAM_API",
    "RESEND_API_KEY",
    "GOPHER_MAIL_FROM",
    "RESEND_FROM",
    "GOPHER_MAIL_HOOK",
    "GOPHER_RESEND_API",
)


def load_server():
    global _MOD
    if _MOD is None:
        spec = importlib.util.spec_from_file_location("gopher_server", SERVER_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MOD = mod
    return _MOD


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 8):
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None
            return resp.status, raw, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, raw, parsed


class _EnvGuard:
    def __init__(self) -> None:
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}

    def restore(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


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

    def test_get_api_tasks(self) -> None:
        self.assertIn("/api/tasks", self.src)

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

    def test_telegram_parked_route(self) -> None:
        self.assertIn("/api/telegram/webhook", self.src)
        self.assertIn("telegram parked", self.src)
        self.assertIn("TELEGRAM_BOT_TOKEN", self.src)
        self.assertIn("sendMessage", self.src)
        self.assertIn("TELEGRAM_WEBHOOK_SECRET", self.src)
        self.assertIn("telegram_is_start", self.src)
        self.assertIn("TELEGRAM_HELP", self.src)
        self.assertIn("RESEND_API_KEY", self.src)
        self.assertIn("api.resend.com", self.src)
        self.assertIn("waitlist_mail_bodies", self.src)
        self.assertIn("send_waitlist_mail", self.src)
        self.assertIn("mail parked", self.src)
        self.assertIn("/api/mail", self.src)
        self.assertIn("orders.jsonl", self.src)
        self.assertIn("load_orders", self.src)
        self.assertIn("looks_market", self.src)
        self.assertIn("looks_trending", self.src)
        self.assertIn("fetch_market_summary", self.src)
        self.assertIn("fetch_trending", self.src)
        self.assertIn("coinbase_spot", self.src)
        self.assertIn('"done": 83', self.src)
        self.assertIn("$19/month", self.src)

    def test_brain_reply_route(self) -> None:
        self.assertIn("/api/brain/reply", self.src)
        self.assertIn("GOPHER_LLM_KEY", self.src)
        self.assertIn("X-Webhook-Key", self.src)
        self.assertIn("X-Webhook-Secret", self.src)
        self.assertIn("brain parked", self.src)

    def test_no_banned_vendor_copy(self) -> None:
        lower = self.src.lower()
        for token in ("grok", "spacexai"):
            self.assertNotIn(token, lower)
        self.assertNotIn("cursor", lower)

    def test_env_hidden_and_loader(self) -> None:
        self.assertIn('".env"', self.src)
        self.assertIn('".env.local"', self.src)
        self.assertIn("load_env_file", self.src)
        self.assertIn("load_dotenv", self.src)
        self.assertIn("Never log values", self.src)

    def test_cors_options(self) -> None:
        self.assertIn("do_OPTIONS", self.src)
        self.assertIn("Access-Control-Allow-Origin", self.src)
        self.assertIn("Access-Control-Allow-Methods", self.src)
        self.assertIn("Content-Type, Accept, Authorization", self.src)
        self.assertIn("cors_origin_ok", self.src)


class CaptureHandler(BaseHTTPRequestHandler):
    last_headers: dict = {}
    last_body: dict = {}
    last_path = ""

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        CaptureHandler.last_headers = {k: v for k, v in self.headers.items()}
        CaptureHandler.last_path = self.path
        try:
            CaptureHandler.last_body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            CaptureHandler.last_body = {}
        self.send_response(204)
        self.end_headers()


class PostLlmHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = _EnvGuard()
        CaptureHandler.last_headers = {}
        CaptureHandler.last_body = {}
        CaptureHandler.last_path = ""

    def tearDown(self) -> None:
        self.guard.restore()

    def test_post_llm_hook_sends_key_headers(self) -> None:
        mod = load_server()
        port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            os.environ["GOPHER_LLM_HOOK"] = "http://127.0.0.1:%s/hook" % port
            os.environ["GOPHER_LLM_KEY"] = "test-sender-key"
            os.environ["GOPHER_PUBLIC_URL"] = "http://127.0.0.1:9"
            os.environ.pop("GOPHER_REPLY_URL", None)
            fired, text = mod.post_llm_hook("ping brain", "abc123")
            self.assertTrue(fired)
            self.assertIsNone(text)
            hdrs = CaptureHandler.last_headers
            self.assertEqual(hdrs.get("Authorization"), "Bearer test-sender-key")
            self.assertEqual(hdrs.get("X-Webhook-Key"), "test-sender-key")
            self.assertEqual(hdrs.get("X-Webhook-Secret"), "test-sender-key")
            self.assertEqual(hdrs.get("Content-Type"), "application/json")
            self.assertEqual(hdrs.get("User-Agent"), "GOPHER/0.1")
            self.assertEqual(hdrs.get("Accept"), "application/json")
            body = CaptureHandler.last_body
            self.assertEqual(body.get("q"), "ping brain")
            self.assertEqual(body.get("text"), "ping brain")
            self.assertEqual(body.get("order_id"), "abc123")
            self.assertEqual(body.get("channel"), "web")
            self.assertEqual(body.get("reply_url"), "http://127.0.0.1:9/api/brain/reply")
            self.assertEqual(CaptureHandler.last_path, "/hook")
        finally:
            httpd.shutdown()
            httpd.server_close()


class BrainReplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_server()
        cls.mod.Handler.log_message = lambda self, fmt, *args: None
        cls.port = free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), cls.mod.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%s" % cls.port
        deadline = time.time() + 8
        last = "not started"
        while time.time() < deadline:
            try:
                code, raw, _ = http("GET", cls.base + "/health")
                if code == 200:
                    return
                last = "health %s %r" % (code, raw)
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
        raise RuntimeError("hole did not start: " + last)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self) -> None:
        self.guard = _EnvGuard()

    def tearDown(self) -> None:
        self.guard.restore()

    def test_brain_reply_503_without_key(self) -> None:
        os.environ.pop("GOPHER_LLM_KEY", None)
        payload = json.dumps({"id": "x", "q": "hi", "text": "yo", "ok": True}).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/brain/reply",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(code, 503)
        self.assertIsInstance(body, dict)
        self.assertIs(body.get("ok"), False)
        self.assertEqual(body.get("error"), "brain parked")
        blob = json.dumps(body).lower() + raw.lower()
        self.assertNotIn("test-sender-key", blob)

    def test_brain_reply_401_wrong_key(self) -> None:
        os.environ["GOPHER_LLM_KEY"] = "hole-key"
        payload = json.dumps({"id": "x", "q": "hi", "text": "yo", "ok": True}).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/brain/reply",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer wrong-key",
            },
        )
        self.assertEqual(code, 401)
        self.assertIsInstance(body, dict)
        self.assertIs(body.get("ok"), False)
        self.assertEqual(body.get("error"), "unauthorized")
        blob = json.dumps(body).lower() + raw.lower()
        self.assertNotIn("hole-key", blob)
        self.assertNotIn("wrong-key", blob)

    def test_brain_reply_200_matching_key(self) -> None:
        os.environ["GOPHER_LLM_KEY"] = "hole-key"
        payload = json.dumps(
            {"id": "ord1", "q": "ping brain", "text": "ok from bot", "ok": True}
        ).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/brain/reply",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Key": "hole-key",
            },
        )
        self.assertEqual(code, 200)
        self.assertIsInstance(body, dict)
        self.assertIs(body.get("ok"), True)
        blob = json.dumps(body).lower() + raw.lower()
        self.assertNotIn("hole-key", blob)


class OrderPollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_server()
        cls.mod.Handler.log_message = lambda self, fmt, *args: None
        cls.port = free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), cls.mod.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%s" % cls.port
        deadline = time.time() + 8
        last = "not started"
        while time.time() < deadline:
            try:
                code, raw, _ = http("GET", cls.base + "/health")
                if code == 200:
                    return
                last = "health %s %r" % (code, raw)
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
        raise RuntimeError("hole did not start: " + last)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self) -> None:
        self.guard = _EnvGuard()

    def tearDown(self) -> None:
        self.guard.restore()

    def test_ask_orders_include_id(self) -> None:
        os.environ.pop("GOPHER_LLM_HOOK", None)
        payload = json.dumps({"q": "hole poll id"}).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/ask",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(code, 200)
        self.assertEqual(body.get("kind"), "queued")
        self.assertTrue(body.get("id"), "queued ask must return id")
        code, raw, orders = http("GET", self.base + "/api/orders")
        self.assertEqual(code, 200)
        self.assertIsInstance(orders, list)
        hits = [r for r in orders if isinstance(r, dict) and r.get("id") == body.get("id")]
        self.assertTrue(hits, "GET /api/orders should include the ask id")
        self.assertIn("q", hits[0])

    def test_brain_reply_then_get_orders_shows_out(self) -> None:
        os.environ.pop("GOPHER_LLM_HOOK", None)
        os.environ["GOPHER_LLM_KEY"] = "hole-key"
        payload = json.dumps({"q": "what lives in a hole"}).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/ask",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(code, 200)
        oid = body.get("id")
        self.assertTrue(oid)
        reply = json.dumps(
            {"id": oid, "q": "what lives in a hole", "text": "a gopher. it fetches.", "ok": True}
        ).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/brain/reply",
            data=reply,
            headers={"Content-Type": "application/json", "X-Webhook-Key": "hole-key"},
        )
        self.assertEqual(code, 200)
        code, raw, orders = http("GET", self.base + "/api/orders")
        self.assertEqual(code, 200)
        hits = [r for r in orders if isinstance(r, dict) and r.get("id") == oid]
        self.assertTrue(hits)
        self.assertIn("gopher", (hits[0].get("out") or "").lower())
        code, raw, one = http("GET", self.base + "/api/order?id=" + oid)
        self.assertEqual(code, 200)
        self.assertIn("gopher", (one.get("out") or "").lower())

    def test_empty_hook_then_brain_reply_on_orders(self) -> None:
        port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            os.environ["GOPHER_LLM_HOOK"] = "http://127.0.0.1:%s/hook" % port
            os.environ["GOPHER_LLM_KEY"] = "hole-key"
            os.environ["GOPHER_PUBLIC_URL"] = self.base
            payload = json.dumps({"q": "ping empty hook"}).encode("utf-8")
            code, raw, body = http(
                "POST",
                self.base + "/api/ask",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(code, 200)
            self.assertEqual(body.get("kind"), "queued")
            oid = body.get("id")
            self.assertTrue(oid)
            reply = json.dumps(
                {"id": oid, "q": "ping empty hook", "text": "brain says hi from the hole", "ok": True}
            ).encode("utf-8")
            code, raw, body = http(
                "POST",
                self.base + "/api/brain/reply",
                data=reply,
                headers={"Content-Type": "application/json", "X-Webhook-Key": "hole-key"},
            )
            self.assertEqual(code, 200)
            code, raw, orders = http("GET", self.base + "/api/orders")
            hits = [r for r in orders if isinstance(r, dict) and r.get("id") == oid]
            self.assertTrue(hits)
            self.assertEqual(hits[0].get("out"), "brain says hi from the hole")
        finally:
            httpd.shutdown()
            httpd.server_close()


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_skips_existing_and_comments(self) -> None:
        mod = load_server()
        os.environ["GOPHER_ENV_TEST_X"] = "keep"
        os.environ.pop("GOPHER_ENV_TEST_Y", None)
        fd, path = tempfile.mkstemp(prefix="gopher-env-", suffix=".env")
        try:
            os.write(
                fd,
                b"# comment\n\nGOPHER_ENV_TEST_X=new\nGOPHER_ENV_TEST_Y=fromfile\nexport GOPHER_ENV_TEST_Z=quoted\n",
            )
            os.close(fd)
            fd = None
            mod.load_env_file(path)
            self.assertEqual(os.environ.get("GOPHER_ENV_TEST_X"), "keep")
            self.assertEqual(os.environ.get("GOPHER_ENV_TEST_Y"), "fromfile")
            self.assertEqual(os.environ.get("GOPHER_ENV_TEST_Z"), "quoted")
        finally:
            if fd is not None:
                os.close(fd)
            os.environ.pop("GOPHER_ENV_TEST_X", None)
            os.environ.pop("GOPHER_ENV_TEST_Y", None)
            os.environ.pop("GOPHER_ENV_TEST_Z", None)
            try:
                os.unlink(path)
            except OSError:
                pass


class CorsLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_server()
        cls.mod.Handler.log_message = lambda self, fmt, *args: None
        cls.port = free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), cls.mod.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%s" % cls.port
        deadline = time.time() + 8
        last = "not started"
        while time.time() < deadline:
            try:
                code, raw, _ = http("GET", cls.base + "/health")
                if code == 200:
                    return
                last = "health %s %r" % (code, raw)
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
        raise RuntimeError("hole did not start: " + last)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _hdrs(self, method: str, path: str, headers: dict | None = None):
        hdrs = {"Accept": "application/json"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(self.base + path, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            return exc.code, {k.lower(): v for k, v in exc.headers.items()}

    def test_options_api_status_cors(self) -> None:
        code, hdrs = self._hdrs(
            "OPTIONS",
            "/api/status",
            {"Origin": "https://oxcryptobot.github.io"},
        )
        self.assertIn(code, (200, 204))
        self.assertEqual(hdrs.get("access-control-allow-origin"), "https://oxcryptobot.github.io")
        allow = (hdrs.get("access-control-allow-methods") or "").upper()
        self.assertIn("GET", allow)
        self.assertIn("POST", allow)
        self.assertIn("OPTIONS", allow)
        ah = hdrs.get("access-control-allow-headers") or ""
        self.assertIn("Content-Type", ah)
        self.assertIn("Accept", ah)
        self.assertIn("Authorization", ah)

    def test_get_api_status_cors(self) -> None:
        code, hdrs = self._hdrs(
            "GET",
            "/api/status",
            {"Origin": "https://oxcryptobot.github.io"},
        )
        self.assertEqual(code, 200)
        self.assertEqual(hdrs.get("access-control-allow-origin"), "https://oxcryptobot.github.io")

    def test_env_not_served(self) -> None:
        code, hdrs = self._hdrs("GET", "/.env")
        self.assertEqual(code, 404)
        code, hdrs = self._hdrs("GET", "/.env.local")
        self.assertEqual(code, 404)

    def test_status_plugins_and_mail_parked(self) -> None:
        code, raw, status = http("GET", self.base + "/api/status")
        self.assertEqual(code, 200)
        plugins = status.get("plugins") or {}
        self.assertIs(plugins.get("ticker"), True)
        self.assertIs(plugins.get("fng"), True)
        self.assertIs(plugins.get("market"), True)
        self.assertIs(plugins.get("trending"), True)
        self.assertIs(plugins.get("telegram"), False)
        self.assertEqual(status.get("telegram"), "parked")
        code, raw, body = http("GET", self.base + "/api/mail")
        self.assertEqual(code, 503)
        self.assertEqual(body.get("error"), "mail parked")


class TelegramWebhookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_server()
        cls.mod.Handler.log_message = lambda self, fmt, *args: None
        cls.port = free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), cls.mod.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%s" % cls.port
        deadline = time.time() + 8
        last = "not started"
        while time.time() < deadline:
            try:
                code, raw, _ = http("GET", cls.base + "/health")
                if code == 200:
                    return
                last = "health %s %r" % (code, raw)
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
        raise RuntimeError("hole did not start: " + last)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self) -> None:
        self.guard = _EnvGuard()
        for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "GOPHER_TELEGRAM_API", "GOPHER_LLM_HOOK"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self.guard.restore()

    def test_parked_503(self) -> None:
        code, raw, body = http(
            "POST",
            self.base + "/api/telegram/webhook",
            data=b"{}",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self.assertEqual(code, 503)
        self.assertEqual(body.get("error"), "telegram parked")
        self.assertIs(body.get("telegram"), False)

    def test_update_maps_to_fulfill_and_send(self) -> None:
        cap_port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", cap_port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        CaptureHandler.last_headers = {}
        CaptureHandler.last_body = {}
        CaptureHandler.last_path = ""
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
            os.environ["GOPHER_TELEGRAM_API"] = "http://127.0.0.1:%s" % cap_port
            payload = json.dumps({"message": {"chat": {"id": 42}, "text": "hello gopher"}}).encode("utf-8")
            code, raw, body = http(
                "POST",
                self.base + "/api/telegram/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            self.assertEqual(code, 200, raw)
            self.assertIs(body.get("ok"), True)
            self.assertIs(body.get("sent"), True)
            self.assertEqual(CaptureHandler.last_path, "/bottest-token/sendMessage")
            self.assertEqual(CaptureHandler.last_body.get("chat_id"), 42)
            self.assertTrue(str(CaptureHandler.last_body.get("text") or ""))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_start_sends_help_no_fake_username(self) -> None:
        cap_port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", cap_port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        CaptureHandler.last_body = {}
        CaptureHandler.last_path = ""
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
            os.environ["GOPHER_TELEGRAM_API"] = "http://127.0.0.1:%s" % cap_port
            payload = json.dumps(
                {"message": {"chat": {"id": 7}, "text": "/start@SomeBotName"}}
            ).encode("utf-8")
            code, raw, body = http(
                "POST",
                self.base + "/api/telegram/webhook",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            self.assertEqual(code, 200, raw)
            self.assertIs(body.get("help"), True)
            text = str(CaptureHandler.last_body.get("text") or "")
            self.assertIn("GOPHER AI", text)
            self.assertIn("$19/month", text)
            self.assertIn("fetch btc", text.lower())
            low = text.lower()
            self.assertNotIn("@somebotname", low)
            self.assertNotIn("t.me/", low)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_webhook_secret_required(self) -> None:
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
        os.environ["TELEGRAM_WEBHOOK_SECRET"] = "hole-secret"
        payload = json.dumps({"message": {"chat": {"id": 1}, "text": "hi"}}).encode("utf-8")
        code, raw, body = http(
            "POST",
            self.base + "/api/telegram/webhook",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self.assertEqual(code, 403)
        self.assertEqual(body.get("error"), "bad signature")
        code, raw, body = http(
            "POST",
            self.base + "/api/telegram/webhook",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": "hole-secret",
            },
        )
        self.assertEqual(code, 200, raw)


class ResendMailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_server()
        cls.mod.Handler.log_message = lambda self, fmt, *args: None
        cls.port = free_port()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", cls.port), cls.mod.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%s" % cls.port
        deadline = time.time() + 8
        last = "not started"
        while time.time() < deadline:
            try:
                code, raw, _ = http("GET", cls.base + "/health")
                if code == 200:
                    return
                last = "health %s %r" % (code, raw)
            except Exception as exc:
                last = str(exc)
                time.sleep(0.05)
        raise RuntimeError("hole did not start: " + last)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self) -> None:
        self.guard = _EnvGuard()
        for key in (
            "RESEND_API_KEY",
            "GOPHER_MAIL_FROM",
            "RESEND_FROM",
            "GOPHER_MAIL_HOOK",
            "GOPHER_RESEND_API",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self.guard.restore()

    def test_mail_parked_503(self) -> None:
        code, raw, body = http("GET", self.base + "/api/mail")
        self.assertEqual(code, 503)
        self.assertEqual(body.get("error"), "mail parked")
        self.assertIs(body.get("mail"), False)

    def test_resend_happy_path_html_and_text(self) -> None:
        cap_port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", cap_port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        CaptureHandler.last_body = {}
        CaptureHandler.last_path = ""
        try:
            os.environ["RESEND_API_KEY"] = "re_test"
            os.environ["GOPHER_MAIL_FROM"] = "waitlist@example.com"
            os.environ["GOPHER_RESEND_API"] = "http://127.0.0.1:%s" % cap_port
            email = "join-test@example.com"
            ok = self.mod.post_resend_mail(email, "joined")
            self.assertTrue(ok)
            self.assertEqual(CaptureHandler.last_path, "/emails")
            body = CaptureHandler.last_body
            self.assertEqual(body.get("from"), "waitlist@example.com")
            self.assertEqual(body.get("to"), [email])
            self.assertIn("$19/month", body.get("text") or "")
            self.assertIn("Waitlist confirmed", body.get("text") or "")
            self.assertIn("<!DOCTYPE html>", body.get("html") or "")
            self.assertIn("$19/month", body.get("html") or "")
            self.assertNotIn("checkout is live", (body.get("text") or "").lower())
            code, raw, status = http("GET", self.base + "/api/mail")
            self.assertEqual(code, 200)
            self.assertIs(status.get("mail"), True)
            self.assertEqual(status.get("via"), "resend")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_prefer_resend_over_hook(self) -> None:
        cap_port = free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", cap_port), CaptureHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        CaptureHandler.last_path = ""
        try:
            os.environ["RESEND_API_KEY"] = "re_test"
            os.environ["GOPHER_MAIL_FROM"] = "waitlist@example.com"
            os.environ["GOPHER_RESEND_API"] = "http://127.0.0.1:%s" % cap_port
            os.environ["GOPHER_MAIL_HOOK"] = "http://127.0.0.1:%s/hook-should-not-hit" % cap_port
            self.mod.send_waitlist_mail("a@example.com", "joined")
            self.assertEqual(CaptureHandler.last_path, "/emails")
        finally:
            httpd.shutdown()
            httpd.server_close()


class PluginOrderLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_server()
        self.guard = _EnvGuard()
        os.environ.pop("GOPHER_LLM_HOOK", None)

    def tearDown(self) -> None:
        self.guard.restore()

    def test_looks_helpers(self) -> None:
        self.assertTrue(self.mod.looks_market("market"))
        self.assertTrue(self.mod.looks_market("crypto summary"))
        self.assertFalse(self.mod.looks_market("fetch btc"))
        self.assertTrue(self.mod.looks_trending("trending"))
        self.assertTrue(self.mod.looks_trending("hot movers"))
        self.assertFalse(self.mod.looks_trending("fetch btc"))

    def test_fulfill_market_soft_fail(self) -> None:
        real = self.mod.fetch_market_summary
        self.mod.fetch_market_summary = lambda: None
        try:
            result = self.mod.fulfill_order("market")
            self.assertEqual(result.get("log_kind"), "market")
            self.assertEqual(result.get("http_code"), 200)
            self.assertIs(result["http"].get("ok"), False)
        finally:
            self.mod.fetch_market_summary = real

    def test_fulfill_trending_soft_fail(self) -> None:
        real = self.mod.fetch_trending
        self.mod.fetch_trending = lambda: None
        try:
            result = self.mod.fulfill_order("trending")
            self.assertEqual(result.get("log_kind"), "trending")
            self.assertIs(result["http"].get("ok"), False)
        finally:
            self.mod.fetch_trending = real

    def test_fulfill_market_happy(self) -> None:
        real = self.mod.fetch_market_summary
        self.mod.fetch_market_summary = lambda: "Market summary\n\nBTC    1\nsource    okx"
        try:
            result = self.mod.fulfill_order("market summary")
            self.assertEqual(result.get("log_kind"), "market")
            self.assertIs(result["http"].get("ok"), True)
            self.assertIn("Market", result["http"].get("title") or "")
        finally:
            self.mod.fetch_market_summary = real

    def test_order_log_jsonl_roundtrip(self) -> None:
        fd, path = tempfile.mkstemp(prefix="gopher-orders-", suffix=".jsonl")
        os.close(fd)
        old_path = self.mod.ORDERS_PATH
        old_legacy = self.mod.ORDERS_LEGACY_PATH
        try:
            self.mod.ORDERS_PATH = path
            self.mod.ORDERS_LEGACY_PATH = path + ".legacy-missing"
            self.mod.save_orders([])
            self.mod.log_order("probe order log", "ask", "queued in the hole.", order_id="abc123deadbeef")
            rows = self.mod.load_orders()
            self.assertTrue(rows)
            self.assertEqual(rows[-1].get("q"), "probe order log")
            self.assertEqual(rows[-1].get("id"), "abc123deadbeef")
            with open(path, encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            self.assertTrue(lines)
            parsed = json.loads(lines[-1])
            self.assertEqual(parsed.get("q"), "probe order log")
            self.assertNotIn("email", parsed)
        finally:
            self.mod.ORDERS_PATH = old_path
            self.mod.ORDERS_LEGACY_PATH = old_legacy
            try:
                os.unlink(path)
            except OSError:
                pass


def main() -> int:
    try:
        loader = unittest.defaultTestLoader
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromTestCase(ServerTests))
        suite.addTests(loader.loadTestsFromTestCase(PostLlmHookTests))
        suite.addTests(loader.loadTestsFromTestCase(BrainReplyTests))
        suite.addTests(loader.loadTestsFromTestCase(OrderPollTests))
        suite.addTests(loader.loadTestsFromTestCase(EnvLoaderTests))
        suite.addTests(loader.loadTestsFromTestCase(CorsLiveTests))
        suite.addTests(loader.loadTestsFromTestCase(TelegramWebhookTests))
        suite.addTests(loader.loadTestsFromTestCase(ResendMailTests))
        suite.addTests(loader.loadTestsFromTestCase(PluginOrderLogTests))
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
