#!/usr/bin/env python3
"""Print ready vs parked plugins from env. Never print secret values."""
from __future__ import annotations

import os
import sys

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


def present(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def flag(ready: bool) -> str:
    return "ready" if ready else "parked"


def main() -> int:
    load_dotenv(os.path.join(ROOT, ".env"))

    llm = present("GOPHER_LLM_HOOK")
    telegram = present("TELEGRAM_BOT_TOKEN")
    mail = (
        present("GOPHER_MAIL_HOOK")
        or present("RESEND_API_KEY")
        or present("SENDGRID_API_KEY")
    )
    # Resend also needs a from address to actually send; still mark mail ready if key/hook set
    # to match server mail_ready(). From-only does not unlock mail.
    sms = present("TWILIO_NUMBER") and present("TWILIO_AUTH_TOKEN")
    voice = sms
    billing = False

    public = present("GOPHER_PUBLIC_URL")
    reply = present("GOPHER_REPLY_URL")
    port = (os.environ.get("GOPHER_PORT") or os.environ.get("PORT") or "7070").strip()

    print("GOPHER env smoke (values not printed)")
    print("bind_port_hint:", port)
    print("GOPHER_PUBLIC_URL:", "set" if public else "empty")
    print("GOPHER_REPLY_URL:", "set" if reply else "empty")
    print("--- plugins ---")
    print("ticker:   ready  (built-in)")
    print("fng:      ready  (built-in)")
    print("tasks:    ready  (built-in)")
    print("llm:     ", flag(llm))
    print("telegram:", flag(telegram))
    print("mail:    ", flag(mail))
    print("sms:     ", flag(sms), "  (Twilio never required)")
    print("voice:   ", flag(voice), "  (Twilio never required)")
    print("billing: ", flag(billing), "  (price public $19/month; checkout parked)")
    print("--- notes ---")
    if not public:
        print("hint: set GOPHER_PUBLIC_URL to the public https origin before Telegram webhook")
    if present("RESEND_API_KEY") and not (
        present("GOPHER_MAIL_FROM") or present("RESEND_FROM")
    ):
        print("hint: RESEND_API_KEY is set but GOPHER_MAIL_FROM / RESEND_FROM is empty")
    if telegram and not public:
        print("hint: TELEGRAM_BOT_TOKEN is set; still need GOPHER_PUBLIC_URL for setWebhook")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
