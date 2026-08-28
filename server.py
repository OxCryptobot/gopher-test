#!/usr/bin/env python3
"""GOPHER landing + waitlist + ask/score. Tiny static server. No extra deps."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
WAITLIST_PATH = os.path.join(ROOT, "waitlist.json")
ORDERS_PATH = os.path.join(ROOT, "orders.json")
SCORES_PATH = os.path.join(ROOT, "scores.json")
CHAMPIONS_PATH = os.path.join(ROOT, "champions.json")


def load_env_file(path: str) -> None:
    """Parse KEY=VALUE lines. Skip comments/blank. Do not override os.environ. Never log values."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw[7:].strip()
        if "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in os.environ:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        os.environ[key] = val


def load_dotenv() -> None:
    for name in (".env", ".env.local"):
        path = os.path.join(ROOT, name)
        if os.path.isfile(path):
            load_env_file(path)


load_dotenv()

HOST = os.environ.get("GOPHER_HOST", "0.0.0.0")
PORT = int(os.environ.get("GOPHER_PORT", "7070"))
EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.I)
MAX_POST_BYTES = 8000
WAITLIST_RATE_MAX = 8
WAITLIST_RATE_WINDOW = 3600.0
HIDDEN = {
    "waitlist.json",
    "orders.json",
    "scores.json",
    "champions.json",
    "server.py",
    "README.md",
    ".gitignore",
    ".env",
    ".env.local",
}
# SHA-1 ETag for these GET static files (and other .html/.css/.js).
ETAG_FILES = {
    "hole.json",
    "tasks.json",
    "index.html",
    "style.css",
    "app.js",
    "game.js",
    "sw.js",
}
ETAG_EXTS = {".html", ".css", ".js"}
CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self' https://api.coinbase.com https://www.okx.com; "
    "media-src 'none'; "
    "object-src 'none'; "
    "base-uri 'self'"
)
LOCK = threading.Lock()
WAITLIST_HITS: dict[str, list[float]] = {}
STARTED_AT = time.time()
REQS = 0

TICKER_NAMES = {
    "BTC": "BTC-USDT",
    "BITCOIN": "BTC-USDT",
    "ETH": "ETH-USDT",
    "ETHEREUM": "ETH-USDT",
    "SOL": "SOL-USDT",
    "SOLANA": "SOL-USDT",
    "XRP": "XRP-USDT",
    "RIPPLE": "XRP-USDT",
    "DOGE": "DOGE-USDT",
    "DOGECOIN": "DOGE-USDT",
    "ADA": "ADA-USDT",
    "CARDANO": "ADA-USDT",
    "LINK": "LINK-USDT",
    "UNI": "UNI-USDT",
    "AVAX": "AVAX-USDT",
    "MATIC": "MATIC-USDT",
    "DOT": "DOT-USDT",
    "ATOM": "ATOM-USDT",
    "NEAR": "NEAR-USDT",
    "APT": "APT-USDT",
    "SUI": "SUI-USDT",
    "TON": "TON-USDT",
}
FETCH_WORDS = {"PRICE", "TICKER", "FETCH", "QUOTE", "SPOT", "PX"}
SKIP_WORDS = FETCH_WORDS | {
    "OF", "THE", "A", "AN", "FOR", "US", "USD", "USDT", "PLEASE", "GET", "SHOW", "ME", "LIVE",
    "FG", "FNG", "FEAR", "GREED", "INDEX",
}

os.chdir(ROOT)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_list(path: str, entries: list) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def load_waitlist() -> list:
    return load_list(WAITLIST_PATH)


def save_waitlist(entries: list) -> None:
    save_list(WAITLIST_PATH, entries)


def cors_origin_ok(origin: str) -> bool:
    origin = (origin or "").strip()
    if not origin:
        return False
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1"):
        return True
    if host == "oxcryptobot.github.io":
        return True
    return False


def wants_json(handler: SimpleHTTPRequestHandler) -> bool:
    accept = handler.headers.get("Accept", "")
    ctype = handler.headers.get("Content-Type", "")
    return "application/json" in accept or "application/json" in ctype


def parse_crypto(q: str) -> str | None:
    s = q.strip().upper().replace("$", " ")
    if not s:
        return None
    m = re.search(r"\b([A-Z0-9]{2,10}-USDT)\b", s)
    if m:
        return m.group(1)
    words = re.findall(r"[A-Z0-9]+", s)
    for w in words:
        if w in TICKER_NAMES:
            return TICKER_NAMES[w]
    fetchy = any(w in FETCH_WORDS for w in words)
    if fetchy:
        for w in words:
            if w not in SKIP_WORDS and 2 <= len(w) <= 10 and w.isalpha():
                return w + "-USDT"
        return "BTC-USDT"
    return None


def okx_ticker(inst_id: str) -> dict | None:
    url = "https://www.okx.com/api/v5/market/ticker?instId=" + inst_id
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GOPHER/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    if str(payload.get("code")) != "0":
        return None
    data = payload.get("data") or []
    if not data or not isinstance(data, list) or not isinstance(data[0], dict):
        return None
    return data[0]


def format_ticker(tick: dict) -> str:
    inst = tick.get("instId") or "TICKER"
    last = tick.get("last") or "?"
    bid = tick.get("bidPx") or "?"
    ask = tick.get("askPx") or "?"
    high = tick.get("high24h") or "?"
    low = tick.get("low24h") or "?"
    vol = tick.get("vol24h") or "?"
    ts = tick.get("ts") or ""
    lines = [
        inst,
        "",
        "last      " + str(last),
        "bid       " + str(bid),
        "ask       " + str(ask),
        "24h high  " + str(high),
        "24h low   " + str(low),
        "24h vol   " + str(vol),
        "",
        "source    okx public ticker",
    ]
    if ts:
        lines.append("ts        " + str(ts))
    return "\n".join(lines)


def looks_fng(q: str) -> bool:
    s = re.sub(r"[^a-z0-9]+", " ", (q or "").lower()).strip()
    words = s.split()
    if not words:
        return False
    if "fng" in words:
        return True
    if "fear" in words and "greed" in words:
        return True
    if "fg" in words:
        return True
    return False


def fetch_fng() -> dict | None:
    url = "https://api.alternative.me/fng/?limit=1"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GOPHER/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    data = payload.get("data") or []
    if not data or not isinstance(data, list) or not isinstance(data[0], dict):
        return None
    return data[0]


def format_fng(row: dict) -> str:
    value = row.get("value") or "?"
    klass = row.get("value_classification") or "?"
    ts = row.get("timestamp") or ""
    lines = [
        "Fear and Greed Index",
        "",
        "value     " + str(value),
        "class     " + str(klass),
        "",
        "source    alternative.me fng",
    ]
    if ts:
        lines.append("ts        " + str(ts))
    return "\n".join(lines)


def mail_ready() -> bool:
    return bool(os.environ.get("GOPHER_MAIL_HOOK") or os.environ.get("SENDGRID_API_KEY"))


def llm_ready() -> bool:
    return bool((os.environ.get("GOPHER_LLM_HOOK") or "").strip())


def llm_key() -> str:
    return (os.environ.get("GOPHER_LLM_KEY") or "").strip()


def llm_reply_url() -> str | None:
    explicit = (os.environ.get("GOPHER_REPLY_URL") or "").strip()
    if explicit:
        return explicit
    public = (os.environ.get("GOPHER_PUBLIC_URL") or "").strip().rstrip("/")
    if public:
        return public + "/api/brain/reply"
    return None


def new_order_id() -> str:
    return uuid.uuid4().hex[:16]


def _parse_llm_body(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:8000]
    if isinstance(data, dict):
        for key in ("text", "answer", "out", "doc"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:8000]
        return None
    if isinstance(data, str) and data.strip():
        return data.strip()[:8000]
    return None


def post_llm_hook(q: str, order_id: str = "") -> tuple[bool, str | None]:
    """POST the live bot webhook. Never log the key or hook query string.

    Returns (fired, text). fired is True on HTTP 2xx. text is a parsed
    answer, or None when the body is empty / has no text keys.
    """
    url = (os.environ.get("GOPHER_LLM_HOOK") or "").strip()
    if not url:
        return False, None
    body: dict = {
        "q": q,
        "text": q,
        "order_id": order_id or "",
        "channel": "web",
    }
    reply_url = llm_reply_url()
    if reply_url:
        body["reply_url"] = reply_url
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "GOPHER/0.1",
        "Accept": "application/json",
    }
    key = llm_key()
    if key:
        headers["Authorization"] = "Bearer " + key
        headers["X-Webhook-Key"] = key
        headers["X-Webhook-Secret"] = key
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False, None
    return True, _parse_llm_body(raw)


def _header_bearer(headers) -> str:
    auth = headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _brain_keys(headers, body: dict) -> list[str]:
    keys: list[str] = []
    bearer = _header_bearer(headers)
    if bearer:
        keys.append(bearer)
    for name in ("X-Webhook-Key", "X-Webhook-Secret"):
        val = (headers.get(name) or "").strip()
        if val:
            keys.append(val)
    body_key = body.get("key") if isinstance(body, dict) else None
    if isinstance(body_key, str) and body_key.strip():
        keys.append(body_key.strip())
    return keys


def brain_key_ok(headers, body: dict) -> bool:
    expected = llm_key()
    if not expected:
        return False
    for got in _brain_keys(headers, body):
        if not got:
            continue
        try:
            if hmac.compare_digest(got, expected):
                return True
        except (TypeError, ValueError):
            continue
    return False


def apply_brain_reply(order_id: str, q: str, text: str) -> None:
    oid = (order_id or "").strip()[:64]
    qn = (q or "").strip()[:280]
    snippet = re.sub(r"\s+", " ", (text or "")).strip()[:8000]
    with LOCK:
        orders = load_list(ORDERS_PATH)
        match = None
        if oid:
            for row in reversed(orders):
                if isinstance(row, dict) and str(row.get("id") or "") == oid:
                    match = row
                    break
        if match is None and qn:
            for row in reversed(orders):
                if isinstance(row, dict) and (row.get("q") or "").strip() == qn:
                    match = row
                    break
        if match is None:
            row = {"q": qn or "reply", "at": _now(), "kind": "ask"}
            if oid:
                row["id"] = oid
            if snippet:
                row["out"] = snippet
            orders.append(row)
        else:
            if snippet:
                match["out"] = snippet
            match["at"] = _now()
        save_list(ORDERS_PATH, orders)


def twilio_ready() -> bool:
    return bool(os.environ.get("TWILIO_NUMBER") and os.environ.get("TWILIO_AUTH_TOKEN"))


def mask_sms_number() -> str | None:
    raw = (os.environ.get("TWILIO_NUMBER") or "").strip()
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 4:
        return "***" + digits[-4:]
    return "***"


def skip_twilio_sig() -> bool:
    v = (os.environ.get("GOPHER_TWILIO_SKIP_SIG") or "").strip().lower()
    return v in ("1", "true", "yes")


def twilio_sig_ok(url: str, params: dict[str, str], token: str, signature: str) -> bool:
    if not token or not signature:
        return False
    buf = url
    for key in sorted(params):
        buf += key + params[key]
    digest = hmac.new(token.encode("utf-8"), buf.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    try:
        return hmac.compare_digest(expected, signature)
    except (TypeError, ValueError):
        return False


def log_order(q: str, kind: str, out: str = "", order_id: str = "") -> None:
    q = (q or "").strip()[:280]
    if not q:
        return
    k = (kind or "ask")[:24]
    snippet = re.sub(r"\s+", " ", (out or "")).strip()[:8000]
    row = {"q": q, "at": _now(), "kind": k}
    oid = (order_id or "").strip()[:64]
    if oid:
        row["id"] = oid
    if snippet:
        row["out"] = snippet
    with LOCK:
        orders = load_list(ORDERS_PATH)
        orders.append(row)
        save_list(ORDERS_PATH, orders)


def fulfill_order(q: str) -> dict:
    q = (q or "").strip()
    if len(q) > 280:
        q = q[:280]
    if not q:
        return {
            "q": "",
            "log_kind": "ask",
            "http_code": 400,
            "http": {"ok": False, "error": "empty order"},
            "short": "empty order",
            "out": "",
        }
    if looks_fng(q):
        row = fetch_fng()
        if row:
            text = format_fng(row)
            short = (
                "Fear and Greed "
                + str(row.get("value") or "?")
                + " "
                + str(row.get("value_classification") or "")
            ).strip()
            return {
                "q": q,
                "log_kind": "fng",
                "http_code": 200,
                "http": {"ok": True, "kind": "doc", "title": "0 Fear and Greed", "text": text},
                "short": short,
                "out": short,
            }
        text = "could not fetch fear/greed from the public index."
        return {
            "q": q,
            "log_kind": "fng",
            "http_code": 200,
            "http": {"ok": False, "kind": "doc", "title": "3 Error", "text": text},
            "short": text,
            "out": text,
        }
    inst = parse_crypto(q)
    if inst:
        tick = okx_ticker(inst)
        if tick:
            text = format_ticker(tick)
            short = inst + " last " + str(tick.get("last") or "?") + " (okx)"
            return {
                "q": q,
                "log_kind": "ticker",
                "http_code": 200,
                "http": {"ok": True, "kind": "doc", "title": "0 " + inst, "text": text},
                "short": short,
                "out": short,
            }
        text = "could not fetch " + inst + " from the ticker hole."
        return {
            "q": q,
            "log_kind": "ticker",
            "http_code": 200,
            "http": {"ok": False, "kind": "doc", "title": "3 Error", "text": text},
            "short": text,
            "out": text,
        }
    order_id = new_order_id()
    if llm_ready():
        fired, hooked = post_llm_hook(q, order_id)
        if hooked:
            return {
                "q": q,
                "id": order_id,
                "log_kind": "ask",
                "http_code": 200,
                "http": {"ok": True, "kind": "doc", "title": "0 GOPHER", "text": hooked, "id": order_id},
                "short": hooked[:120],
                "out": hooked,
            }
        if fired:
            text = "sent to GOPHER…"
            return {
                "q": q,
                "id": order_id,
                "log_kind": "ask",
                "http_code": 200,
                "http": {"ok": True, "kind": "queued", "text": text, "id": order_id},
                "short": text,
                "out": text,
            }
    text = "queued in the hole."
    return {
        "q": q,
        "id": order_id,
        "log_kind": "ask",
        "http_code": 200,
        "http": {"ok": True, "kind": "queued", "text": text, "id": order_id},
        "short": text,
        "out": text,
    }


def post_mail_hook(email: str, status: str) -> None:
    url = (os.environ.get("GOPHER_MAIL_HOOK") or "").strip()
    if not url or status != "joined":
        return
    payload = json.dumps({"email": email, "status": status, "at": _now()}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GOPHER/0.1",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return


def waitlist_rate_limited(ip: str) -> bool:
    now = time.time()
    cutoff = now - WAITLIST_RATE_WINDOW
    with LOCK:
        times = [t for t in WAITLIST_HITS.get(ip, []) if t > cutoff]
        if len(times) >= WAITLIST_RATE_MAX:
            WAITLIST_HITS[ip] = times
            return True
        times.append(now)
        WAITLIST_HITS[ip] = times
        return False


def _sha1_etag(path: str) -> str | None:
    """Strong ETag from SHA-1 of file bytes. Changes when content changes."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if name not in ETAG_FILES and ext not in ETAG_EXTS:
        return None
    try:
        with open(path, "rb") as f:
            digest = hashlib.sha1(f.read()).hexdigest()
    except OSError:
        return None
    return '"' + digest + '"'


def _if_none_match(header: str | None, etag: str) -> bool:
    if not header:
        return False
    raw = header.strip()
    if raw == "*":
        return True
    want = etag.strip()
    if want.startswith("W/"):
        want = want[2:].strip()
    for part in raw.split(","):
        tag = part.strip()
        if tag.startswith("W/"):
            tag = tag[2:].strip()
        if tag == want:
            return True
    return False


class Handler(SimpleHTTPRequestHandler):
    server_version = "GOPHER/0.1"

    def log_message(self, fmt: str, *args) -> None:
        safe = []
        for a in args:
            if isinstance(a, str) and "?" in a:
                a = a.split("?", 1)[0]
            safe.append(a)
        try:
            msg = fmt % tuple(safe)
        except (TypeError, ValueError):
            msg = fmt
        print(f"[gopher] {self.log_date_time_string()} {msg}", file=sys.stderr)

    def list_directory(self, path: str):
        self.send_error(404, "Not found")
        return None

    def end_headers(self) -> None:
        etag = getattr(self, "_etag", None)
        if etag:
            self.send_header("ETag", etag)
        self.send_header(
            "Content-Security-Policy",
            CSP,
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", self._cache_control())
        self._cors_headers()
        super().end_headers()

    def _cors_headers(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api"):
            return
        origin = (self.headers.get("Origin") or "").strip()
        if not cors_origin_ok(origin):
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization")
        self.send_header("Vary", "Origin")

    def send_head(self):
        path = self.translate_path(self.path)
        self._etag = None
        if os.path.isfile(path) and not path.endswith("/"):
            etag = _sha1_etag(path)
            if etag:
                self._etag = etag
                if _if_none_match(self.headers.get("If-None-Match"), etag):
                    self.send_response(304)
                    self.end_headers()
                    return None
        return super().send_head()

    def _cache_control(self) -> str:
        path = urlparse(self.path).path.lower()
        base = os.path.basename(path)
        if base in ("index.html", "hole.json", "tasks.json") or path in ("/", "/index.html", "/hole.json", "/tasks.json"):
            return "no-cache"
        if base.endswith((".png", ".css", ".js")):
            return "public, max-age=3600"
        return "no-store"

    def translate_path(self, path: str) -> str:
        mapped = super().translate_path(path)
        name = os.path.basename(mapped)
        if name in HIDDEN or name.endswith(".tmp") or name.startswith(".env"):
            return os.path.join(ROOT, "__no_such_file__")
        try:
            rel = os.path.relpath(mapped, ROOT)
        except ValueError:
            return os.path.join(ROOT, "__no_such_file__")
        if rel.startswith("..") or ".git" in rel.split(os.sep):
            return os.path.join(ROOT, "__no_such_file__")
        return mapped

    def do_GET(self) -> None:
        global REQS
        REQS += 1
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if path == "/health":
            self._health()
            return
        if path == "/api/status":
            self._status()
            return
        if path == "/api/tasks":
            self._tasks()
            return
        if path == "/api/orders":
            self._orders()
            return
        if path == "/api/order":
            self._order_one(parse_qs(parsed.query or ""))
            return
        if path == "/api/scores":
            self._scores()
            return
        if path == "/api/champions":
            self._champions()
            return
        if path == "/api/waitlist":
            self._json(405, {"ok": False, "error": "POST an email to join."})
            return
        if path in ("/api/ask", "/api/score", "/api/champions", "/api/brain/reply"):
            self._json(405, {"ok": False, "error": "POST only."})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        global REQS
        REQS += 1
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length > MAX_POST_BYTES:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if path == "/api/waitlist":
                self._fail(413, "payload too large")
            else:
                self._json(413, {"ok": False, "error": "payload too large"})
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/api/waitlist":
            self._waitlist()
            return
        if path == "/api/ask":
            self._ask()
            return
        if path == "/api/score":
            self._score()
            return
        if path == "/api/champions":
            self._champion_add()
            return
        if path == "/api/twilio/sms":
            self._twilio_sms()
            return
        if path == "/api/twilio/voice":
            self._twilio_voice()
            return
        if path == "/api/twilio/voice/order":
            self._twilio_voice_order()
            return
        if path == "/api/brain/reply":
            self._brain_reply()
            return
        self.send_error(404, "Not found")

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api"):
            self.send_error(404, "Not found")
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _status(self) -> None:
        up = max(0, int(time.time() - STARTED_AT))
        sms = twilio_ready()
        mail = mail_ready()
        self._json(
            200,
            {
                "ok": True,
                "hole": "python",
                "uptime_s": up,
                "started": datetime.fromtimestamp(STARTED_AT, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "requests": REQS,
                "sla": False,
                "progress": {"done": 82, "total": 100},
                "plugins": {
                    "ticker": True,
                    "fng": True,
                    "tasks": True,
                    "mail": mail,
                    "sms": sms,
                    "voice": sms,
                    "billing": False,
                },
                "twilio": "ready" if sms else "parked",
                "sms_number": mask_sms_number(),
                "mail": "ready" if mail else "parked",
                "llm": "ready" if llm_ready() else "parked",
            },
        )

    def _tasks(self) -> None:
        path = os.path.join(ROOT, "tasks.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        tasks = data.get("tasks") if isinstance(data, dict) else None
        if not isinstance(tasks, list):
            tasks = []
        payload = {
            "ok": True,
            "n": len(tasks),
            "hole": "python",
            "version": data.get("version", 1) if isinstance(data, dict) else 1,
            "tasks": tasks,
        }
        self._json(200, payload)

    def _orders(self) -> None:
        with LOCK:
            rows = load_list(ORDERS_PATH)
        out = []
        for entry in rows[-20:]:
            if not isinstance(entry, dict):
                continue
            q = entry.get("q")
            if not isinstance(q, str) or not q.strip():
                continue
            row = {"q": q.strip()[:280], "kind": "queued"}
            at = entry.get("at")
            if isinstance(at, str):
                row["at"] = at
            k = entry.get("kind")
            if isinstance(k, str) and k:
                row["kind"] = k[:24]
            oid = entry.get("id")
            if isinstance(oid, str) and oid.strip():
                row["id"] = oid.strip()[:64]
            snippet = entry.get("out")
            if isinstance(snippet, str) and snippet.strip():
                row["out"] = snippet.strip()[:8000]
            out.append(row)
        self._json(200, out)

    def _order_one(self, qs: dict) -> None:
        oid = ""
        vals = qs.get("id") if isinstance(qs, dict) else None
        if vals:
            oid = str(vals[0] or "").strip()[:64]
        if not oid:
            self._json(400, {"ok": False, "error": "missing id"})
            return
        with LOCK:
            rows = load_list(ORDERS_PATH)
        for entry in reversed(rows):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "") != oid:
                continue
            q = entry.get("q")
            row = {"ok": True, "id": oid, "kind": "queued"}
            if isinstance(q, str) and q.strip():
                row["q"] = q.strip()[:280]
            at = entry.get("at")
            if isinstance(at, str):
                row["at"] = at
            k = entry.get("kind")
            if isinstance(k, str) and k:
                row["kind"] = k[:24]
            snippet = entry.get("out")
            if isinstance(snippet, str) and snippet.strip():
                row["out"] = snippet.strip()[:8000]
            self._json(200, row)
            return
        self._json(404, {"ok": False, "error": "not found", "id": oid})

    def _health(self) -> None:
        if wants_json(self):
            self._json(200, {"ok": True, "uptime_s": max(0, int(time.time() - STARTED_AT))})
            return
        data = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _scores(self) -> None:
        with LOCK:
            scores = load_list(SCORES_PATH)
        ranked = []
        for entry in scores:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            score = entry.get("score")
            if not isinstance(name, str):
                continue
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                continue
            row = {"name": name, "score": int(score)}
            stage = entry.get("stage")
            if not isinstance(stage, bool) and isinstance(stage, (int, float)):
                row["stage"] = int(stage)
            champ = entry.get("champion")
            if isinstance(champ, bool):
                row["champion"] = champ
            ranked.append(row)
        ranked.sort(key=lambda item: (item["score"], item.get("stage") or 0), reverse=True)
        self._json(200, ranked[:10])

    def _read_json(self, max_len: int = MAX_POST_BYTES):
        length = int(self.headers.get("Content-Length") or 0)
        if length > max_len:
            return None, "payload too large"
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        except json.JSONDecodeError:
            return None, "bad json"
        if not isinstance(data, dict):
            return None, "bad json"
        return data, None

    def _waitlist(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_POST_BYTES:
            self._fail(413, "payload too large")
            return
        ip = self.client_address[0] if self.client_address else ""
        if waitlist_rate_limited(ip):
            if length:
                self.rfile.read(length)
            self._fail(429, "too many requests")
            return
        raw = self.rfile.read(length) if length else b""
        email = self._extract_email(raw)
        if email is None:
            self._fail(400, "that doesn't look like an email. try again.")
            return
        email = email.strip()
        if not EMAIL_RE.match(email) or len(email) > 254:
            self._fail(400, "that doesn't look like an email. try again.")
            return

        now = _now()
        with LOCK:
            entries = load_waitlist()
            existing = {e.get("email", "").lower() for e in entries if isinstance(e, dict)}
            if email.lower() in existing:
                status = "duplicate"
            else:
                entries.append({"email": email, "joined_at": now})
                save_waitlist(entries)
                status = "joined"

        body = {"ok": True, "status": status, "email": email}
        if status == "joined":
            post_mail_hook(email, status)
        if wants_json(self):
            self._json(200, body)
        else:
            self._html_result(body)

    def _ask(self) -> None:
        data, err = self._read_json()
        if err == "payload too large":
            self._json(413, {"ok": False, "error": err})
            return
        if data is None:
            self._json(400, {"ok": False, "error": err or "bad json"})
            return
        q = data.get("q")
        if not isinstance(q, str):
            q = ""
        result = fulfill_order(q)
        if result["q"]:
            log_order(
                result["q"],
                result["log_kind"],
                result.get("out") or "",
                order_id=result.get("id") or "",
            )
        self._json(result["http_code"], result["http"])


    def _champions(self) -> None:
        with LOCK:
            rows = load_list(CHAMPIONS_PATH)
        out = []
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            row = {"name": name}
            score = entry.get("score")
            if not isinstance(score, bool) and isinstance(score, (int, float)):
                row["score"] = int(score)
            at = entry.get("at")
            if isinstance(at, str):
                row["at"] = at
            out.append(row)
        self._json(200, out)

    def _champion_add(self) -> None:
        data, err = self._read_json()
        if err == "payload too large":
            self._json(413, {"ok": False, "error": err})
            return
        if data is None:
            self._json(400, {"ok": False, "error": err or "bad json"})
            return
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            name = "guest"
        name = re.sub(r"[^a-z0-9._-]", "", name.strip().lower())[:24] or "guest"
        score = data.get("score")
        score_n = 0
        if not isinstance(score, bool) and isinstance(score, (int, float)):
            score_n = int(score)
            if score_n < 0:
                score_n = 0
            if score_n > 9999999:
                score_n = 9999999
        now = _now()
        with LOCK:
            rows = load_list(CHAMPIONS_PATH)
            names = {
                e.get("name")
                for e in rows
                if isinstance(e, dict) and isinstance(e.get("name"), str)
            }
            if name not in names:
                rows.append({"name": name, "score": score_n, "at": now, "eternal": True})
                save_list(CHAMPIONS_PATH, rows)
        self._json(200, {"ok": True, "name": name})

    def _score(self) -> None:
        data, err = self._read_json()
        if err == "payload too large":
            self._json(413, {"ok": False, "error": err})
            return
        if data is None:
            self._json(400, {"ok": False, "error": err or "bad json"})
            return
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            name = "guest"
        name = re.sub(r"[^a-z0-9._-]", "", name.strip().lower())[:24] or "guest"
        score = data.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            self._json(400, {"ok": False, "error": "bad score"})
            return
        score = int(score)
        if score < 0:
            score = 0
        if score > 9999999:
            score = 9999999
        stage = data.get("stage")
        stage_n = None
        if not isinstance(stage, bool) and isinstance(stage, (int, float)):
            stage_n = int(stage)
            if stage_n < 0:
                stage_n = 0
            if stage_n > 9999:
                stage_n = 9999
        champ = data.get("champion")
        now = _now()
        entry = {"name": name, "score": score, "at": now}
        if stage_n is not None:
            entry["stage"] = stage_n
        if isinstance(champ, bool):
            entry["champion"] = champ
        with LOCK:
            scores = load_list(SCORES_PATH)
            scores.append(entry)
            save_list(SCORES_PATH, scores)
        self._json(200, {"ok": True})

    def _extract_email(self, raw: bytes) -> str | None:
        ctype = self.headers.get("Content-Type", "")
        text = raw.decode("utf-8", errors="replace")
        if "application/json" in ctype:
            try:
                data = json.loads(text or "{}")
            except json.JSONDecodeError:
                return None
            if isinstance(data, dict):
                value = data.get("email")
                return value if isinstance(value, str) else None
            return None
        parsed = parse_qs(text, keep_blank_values=True)
        values = parsed.get("email") or []
        return values[0] if values else None

    def _read_form(self) -> dict[str, str]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        raw = self.rfile.read(length) if length else b""
        text = raw.decode("utf-8", errors="replace")
        parsed = parse_qs(text, keep_blank_values=True)
        out: dict[str, str] = {}
        for key, vals in parsed.items():
            out[key] = vals[0] if vals else ""
        return out

    def _public_url(self) -> str:
        host = self.headers.get("Host") or (HOST + ":" + str(PORT))
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        return proto + "://" + host + self.path

    def _twilio_gate(self, form: dict[str, str]) -> bool:
        """Return True if the request may proceed. Sends 503 or 403 otherwise."""
        if not twilio_ready():
            self._json(503, {"ok": False, "error": "twilio parked", "sms": False})
            return False
        if skip_twilio_sig():
            return True
        sig = self.headers.get("X-Twilio-Signature") or ""
        token = os.environ.get("TWILIO_AUTH_TOKEN") or ""
        if not twilio_sig_ok(self._public_url(), form, token, sig):
            self._json(403, {"ok": False, "error": "bad signature"})
            return False
        return True

    def _twiml(self, xml: str) -> None:
        data = xml.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _twilio_sms(self) -> None:
        form = self._read_form()
        if not self._twilio_gate(form):
            return
        body = form.get("Body") or ""
        result = fulfill_order(body)
        q = result["q"] or body.strip()[:280]
        log_order(q, "sms", result.get("out") or result.get("short") or "", order_id=result.get("id") or "")
        msg = (result.get("short") or "queued in the hole.")[:1500]
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Message>" + _esc(msg) + "</Message></Response>"
        )
        self._twiml(xml)

    def _twilio_voice(self) -> None:
        form = self._read_form()
        if not self._twilio_gate(form):
            return
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            '<Gather input="speech dtmf" action="/api/twilio/voice/order" method="POST">'
            "<Say>Gopher A I. Speak an order.</Say>"
            "</Gather>"
            "<Say>No order heard.</Say>"
            "</Response>"
        )
        self._twiml(xml)

    def _twilio_voice_order(self) -> None:
        form = self._read_form()
        if not self._twilio_gate(form):
            return
        spoken = (form.get("SpeechResult") or form.get("Digits") or "").strip()
        result = fulfill_order(spoken)
        q = result["q"] or spoken[:280]
        log_order(q, "voice", result.get("out") or result.get("short") or "", order_id=result.get("id") or "")
        msg = (result.get("short") or "queued in the hole.")[:1500]
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>" + _esc(msg) + "</Say></Response>"
        )
        self._twiml(xml)

    def _brain_reply(self) -> None:
        data, err = self._read_json()
        if not llm_key():
            self._json(503, {"ok": False, "error": "brain parked"})
            return
        body = data if isinstance(data, dict) else {}
        if not brain_key_ok(self.headers, body):
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        if data is None:
            self._json(400, {"ok": False, "error": err or "bad json"})
            return
        order_id = data.get("id") if isinstance(data.get("id"), str) else ""
        if not order_id and isinstance(data.get("order_id"), str):
            order_id = data.get("order_id") or ""
        q = data.get("q") if isinstance(data.get("q"), str) else ""
        text = data.get("text") if isinstance(data.get("text"), str) else ""
        apply_brain_reply(order_id.strip(), q.strip(), text)
        self._json(200, {"ok": True})

    def _fail(self, code: int, message: str) -> None:
        payload = {"ok": False, "status": "invalid", "error": message}
        if wants_json(self):
            self._json(code, payload)
        else:
            self._html_result(payload, code)

    def _json(self, code: int, payload: dict | list) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html_result(self, payload: dict, code: int = 200) -> None:
        if payload.get("status") == "joined":
            line = "ok. you're on the list."
        elif payload.get("status") == "duplicate":
            line = "already listed. we'll still ping you."
        else:
            line = payload.get("error") or "could not file that selector."
        html = (
            "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>GOPHER waitlist</title>"
            "<link rel='stylesheet' href='/style.css'></head><body>"
            "<div class='shell'><p class='breath'>" + _esc(line) + "</p>"
            "<p><a href='/'>back to GOPHER</a></p></div></body></html>"
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> None:
    if not os.path.exists(WAITLIST_PATH):
        save_waitlist([])
    if not os.path.exists(ORDERS_PATH):
        save_list(ORDERS_PATH, [])
    if not os.path.exists(SCORES_PATH):
        save_list(SCORES_PATH, [])
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"GOPHER listening on http://127.0.0.1:{PORT}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nGOPHER closed the hole.", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    main()
