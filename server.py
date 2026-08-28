#!/usr/bin/env python3
"""GOPHER landing + waitlist + ask/score. Tiny static server. No extra deps."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
WAITLIST_PATH = os.path.join(ROOT, "waitlist.json")
ORDERS_PATH = os.path.join(ROOT, "orders.json")
SCORES_PATH = os.path.join(ROOT, "scores.json")
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
    "server.py",
    "README.md",
    ".gitignore",
}
# SHA-1 ETag for these GET static files (and other .html/.css/.js).
ETAG_FILES = {
    "hole.json",
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

TICKER_NAMES = {
    "BTC": "BTC-USDT",
    "BITCOIN": "BTC-USDT",
    "ETH": "ETH-USDT",
    "ETHEREUM": "ETH-USDT",
    "SOL": "SOL-USDT",
    "SOLANA": "SOL-USDT",
    "XRP": "XRP-USDT",
    "RIPPLE": "XRP-USDT",
}
FETCH_WORDS = {"PRICE", "TICKER", "FETCH", "QUOTE", "SPOT", "PX"}
SKIP_WORDS = FETCH_WORDS | {
    "OF", "THE", "A", "AN", "FOR", "US", "USD", "USDT", "PLEASE", "GET", "SHOW", "ME", "LIVE",
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
        print(f"[gopher] {self.log_date_time_string()} {fmt % args}", file=sys.stderr)

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
        super().end_headers()

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
        if base in ("index.html", "hole.json") or path in ("/", "/index.html", "/hole.json"):
            return "no-cache"
        if base.endswith((".png", ".css", ".js")):
            return "public, max-age=3600"
        return "no-store"

    def translate_path(self, path: str) -> str:
        mapped = super().translate_path(path)
        name = os.path.basename(mapped)
        if name in HIDDEN or name.endswith(".tmp"):
            return os.path.join(ROOT, "__no_such_file__")
        try:
            rel = os.path.relpath(mapped, ROOT)
        except ValueError:
            return os.path.join(ROOT, "__no_such_file__")
        if rel.startswith("..") or ".git" in rel.split(os.sep):
            return os.path.join(ROOT, "__no_such_file__")
        return mapped

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if path == "/health":
            self._health()
            return
        if path == "/api/scores":
            self._scores()
            return
        if path == "/api/waitlist":
            self._json(405, {"ok": False, "error": "POST an email to join."})
            return
        if path in ("/api/ask", "/api/score"):
            self._json(405, {"ok": False, "error": "POST only."})
            return
        return super().do_GET()

    def do_POST(self) -> None:
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
        self.send_error(404, "Not found")

    def _health(self) -> None:
        if wants_json(self):
            self._json(200, {"ok": True})
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
            ranked.append({"name": name, "score": int(score)})
        ranked.sort(key=lambda item: item["score"], reverse=True)
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
        q = q.strip()
        if not q:
            self._json(400, {"ok": False, "error": "empty order"})
            return
        if len(q) > 280:
            q = q[:280]
        inst = parse_crypto(q)
        if inst:
            tick = okx_ticker(inst)
            if tick:
                self._json(
                    200,
                    {
                        "ok": True,
                        "kind": "doc",
                        "title": "0 " + inst,
                        "text": format_ticker(tick),
                    },
                )
            else:
                self._json(
                    200,
                    {
                        "ok": False,
                        "kind": "doc",
                        "title": "3 Error",
                        "text": "could not fetch " + inst + " from the ticker hole.",
                    },
                )
            return
        now = _now()
        with LOCK:
            orders = load_list(ORDERS_PATH)
            orders.append({"q": q, "at": now})
            save_list(ORDERS_PATH, orders)
        self._json(200, {"ok": True, "kind": "queued", "text": "queued in the hole."})

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
        now = _now()
        with LOCK:
            scores = load_list(SCORES_PATH)
            scores.append({"name": name, "score": score, "at": now})
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
