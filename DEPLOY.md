# GOPHER AI — free deploy path

Public price: **$19/month**. Waitlist is the door. Checkout stays parked.

Twilio is **never required**. Prefer Telegram + Resend + in-app Ask first. Do not invent a phone number or a bot username.

No secrets in this file, in `hole.json`, or in any client asset.

## Free path (order)

1. **GitHub Pages now** — static hole (staging → promote). Matcher-only while `hole.json` `"brain"` is empty.
2. **Python hole on a free host** — Render, Railway, or Fly (one process running `server.py`).
3. **Point `brain`** — set `hole.json` top-level `"brain"` to the public `https://…` URL of that python process (no trailing slash required; client talks to `/api/ask`).
4. **Telegram / Resend env** — optional. Empty = parked. Twilio stays parked.
5. **Vercel static later** — optional; `vercel.json` is ready. Does not replace Pages today.

## 5 steps — free python host

Pick **one** host. Same process: `python3 server.py`, health at `/health`.

### A. Render (Blueprint or Web Service)

1. Push this repo (or connect the GitHub remote) to [Render](https://render.com).
2. New → Blueprint (`render.yaml`) **or** Web Service: runtime Python, start `python3 server.py`, health path `/health`, free plan.
3. Set env (dashboard): at least `GOPHER_PUBLIC_URL=https://YOUR-SERVICE.onrender.com`. Add `TELEGRAM_BOT_TOKEN`, `RESEND_API_KEY`, `GOPHER_MAIL_FROM`, `GOPHER_LLM_HOOK`, `GOPHER_LLM_KEY` only when you have real values.
4. Deploy. Check `https://YOUR-SERVICE.onrender.com/health` → `ok`.
5. Set Pages `hole.json` `"brain"` to that https URL. Commit/push Pages. Ask GOPHER leaves the matcher.

### B. Railway

1. New project from this repo. Railway reads `railway.json` + `Dockerfile`.
2. Generate a public HTTPS domain for the service.
3. Set `GOPHER_PUBLIC_URL` to that https origin. Add optional Telegram/Resend/LLM env the same way.
4. Deploy. Hit `/health`.
5. Point `hole.json` `"brain"` at the origin. Push Pages.

### C. Fly.io

1. Install `flyctl`, run `fly launch` (uses `fly.toml` / `Dockerfile`). Pick a unique app name if `gopher-hole` is taken.
2. `fly secrets set GOPHER_PUBLIC_URL=https://YOUR-APP.fly.dev` (plus optional Telegram/Resend/LLM secrets).
3. `fly deploy`.
4. Check `https://YOUR-APP.fly.dev/health`.
5. Point `hole.json` `"brain"` at that URL. Push Pages.

Local Docker smoke:

```bash
docker build -t gopher-hole .
docker run --rm -p 8080:8080 -e GOPHER_PUBLIC_URL=http://127.0.0.1:8080 gopher-hole
curl -s http://127.0.0.1:8080/health
```

## Env (server only)

Copy `.env.example` → `.env` for local. On the host, set the same keys in the dashboard / secrets. Never commit `.env`.

| Key | Role |
| --- | --- |
| `GOPHER_PUBLIC_URL` | Public https origin of this process |
| `GOPHER_LLM_HOOK` / `GOPHER_LLM_KEY` | Live bot webhook (parked if empty) |
| `TELEGRAM_BOT_TOKEN` | Telegram webhook channel (parked if empty) |
| `RESEND_API_KEY` + `GOPHER_MAIL_FROM` | Waitlist join mail (parked if empty) |
| `TWILIO_*` | Optional forever; 503 until set. Not required |

`PORT` is injected by most hosts. Local default remains 7070 via `GOPHER_PORT` / `PORT`.

## Telegram webhook

After the python hole is public and `TELEGRAM_BOT_TOKEN` is set:

```bash
export TELEGRAM_BOT_TOKEN=…   # real token from BotFather — never invent a username
export GOPHER_PUBLIC_URL=https://YOUR-SERVICE…
python3 scripts/telegram_set_webhook.py
```

Webhook target: `{GOPHER_PUBLIC_URL}/api/telegram/webhook`. Optional `TELEGRAM_WEBHOOK_SECRET` must match the host env.

## Smoke plugins (no secret values)

```bash
python3 scripts/smoke_env.py
```

Prints ready vs parked for llm / telegram / mail / sms / voice / billing. Does not print token or key values.

Or hit the live process: `GET /api/status`.

## Pages ↔ brain

- Empty `"brain": ""` → GitHub Pages stays matcher-only (safe default).
- Non-empty https `"brain"` → client POSTs that origin’s `/api/ask` (and polls orders).
- Never put `GOPHER_LLM_KEY`, Telegram tokens, or Resend keys in `hole.json` or the browser.

## Vercel (future static)

`vercel.json` configures a static front only. GitHub Pages ignores it and keeps serving `index.html`, assets, and `.nojekyll` as today. Do not point Vercel at `server.py` for the python brain — use Render / Railway / Fly for that.

## What stays parked

- Twilio SMS / voice (no number invented)
- Billing / Stripe checkout (price is public: $19/month)
- Bot usernames, SLA, hiring

## Checks

```bash
python3 -m py_compile server.py scripts/telegram_set_webhook.py scripts/smoke_env.py
python3 scripts/smoke_env.py
curl -s "$GOPHER_PUBLIC_URL/health"
```
