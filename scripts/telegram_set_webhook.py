#!/usr/bin/env python3
"""Register Telegram webhook for the GOPHER python hole.

Uses TELEGRAM_BOT_TOKEN + GOPHER_PUBLIC_URL.
Never invents a bot username. Never prints the token.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path: str) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    load_dotenv(os.path.join(ROOT, ".env"))
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    public = (os.environ.get("GOPHER_PUBLIC_URL") or "").strip().rstrip("/")
    secret = (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    api_base = (os.environ.get("GOPHER_TELEGRAM_API") or "https://api.telegram.org").rstrip("/")

    if not token:
        print("error: TELEGRAM_BOT_TOKEN is empty — set it in the environment or .env", file=sys.stderr)
        print("hint: create a bot with BotFather; do not invent a username here", file=sys.stderr)
        return 1
    if not public:
        print("error: GOPHER_PUBLIC_URL is empty — need the public https origin of server.py", file=sys.stderr)
        return 1
    if not (public.startswith("https://") or public.startswith("http://127.") or public.startswith("http://localhost")):
        print("error: GOPHER_PUBLIC_URL must be an http(s) origin (https for Telegram cloud)", file=sys.stderr)
        return 1

    webhook_url = public + "/api/telegram/webhook"
    payload: dict = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret

    endpoint = api_base + "/bot" + token + "/setWebhook"
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"error: Telegram HTTP {e.code} for setWebhook", file=sys.stderr)
        if err_body:
            print(err_body[:800], file=sys.stderr)
        print("hint: check the token; never invent a bot username", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"error: could not reach Telegram API: {e.reason}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"error: non-JSON response (HTTP {status}): {raw[:400]}", file=sys.stderr)
        return 1

    if not data.get("ok"):
        desc = data.get("description") or data.get("error") or raw[:400]
        print(f"error: setWebhook rejected: {desc}", file=sys.stderr)
        return 1

    print("ok: webhook set")
    print("url:", webhook_url)
    if secret:
        print("secret_token: (set; value not printed)")
    else:
        print("secret_token: (none — optional TELEGRAM_WEBHOOK_SECRET)")
    # Do not call getMe / print username — never invent or publish a bot username.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
