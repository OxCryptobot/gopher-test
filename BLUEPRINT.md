# GOPHER AI — missing product blueprint

**Ship A→Z** (product + marketing + distribution from 83/100): see `SHIP_AZ.md`. Type `ship-az` on the hole.

Honest bar: **83/100**. About 17% of the 100-list is still open, but remaining work is the HARD product, not 17% of effort.

Two bars:

- Playable hole **74/75** (phases 0–2; item 28 CI is the miss)
- Paid phone **9/25** (phase 3)

Type `blueprint` on the hole. Do not mark an item done until the real product exists. Public price is $19/month. Do not invent other prices, SMS numbers, bot usernames, SLA, or hiring.

## What already works

- Playable hole on staging and (older) production Pages
- FETCH is search; DIG is a task from the 100; MAZE/BURROW side quest
- Waitlist JSON on `server.py`, device fallback on Pages
- Device login (PBKDF2 localStorage)
- Ticker `fetch btc` (ETH SOL XRP DOGE ADA LINK UNI AVAX MATIC DOT ATOM NEAR APT SUI TON)
- Python fear/greed fetch (`fetch fg` / `fear greed` / `fng`)
- Python market summary (`market`) and trending (`trending`) soft-fail fetches
- Scores + Eternal GOPHER CHAMPIONS on python `/api/scores` and `/api/champions`
- Watch / remind / draft as **device queues**, not SMS
- EN/ES directory, shell, and 29 doc bodies
- Python `/api/status` product flags and durable `/api/orders` JSONL export (no emails)
- Twilio webhook endpoints on python: HTTP 503 until env is set. Twilio is not required.
- Telegram webhook `POST /api/telegram/webhook`: HTTP 503 until `TELEGRAM_BOT_TOKEN`. No bot username invented.
- Waitlist join mail via Resend if `RESEND_API_KEY` + from, or `GOPHER_MAIL_HOOK`. Parked otherwise.
- Public price $19/month on `/pricing`. Waitlist is the door. Checkout/billing parked.


## Prompt / 100 tasks

Live autoprompt on the hole: type in Prompt <search>, ranked selectors appear. Catalog is `tasks.json` (100). Parked products (SMS, voice, mail, billing, telegram, domain, cloud accounts, SLA, hiring) still parked — they do not fake a number or a bot username. Prices are public: $19/month. Python `GET /api/tasks`. Pages uses static `tasks.json`.

## Prompt UX

The GOPHER prompt is always on (the star). One quiet nav row: GOPHER · search · tasks · waitlist · play. Directory is the page. Three answers under the prompt. MAZE and BURROW live under play. GOPHER is an on-device order router over 100 tasks. GitHub Pages uses a client ticker brain (never POST `/api/ask` on github.io to itself). Optional public `brain` URL in `hole.json`: if it is a non-empty https URL, Ask GOPHER POSTs that python hole (`/api/ask`, poll `/api/order` and `/api/orders`). Empty `brain` keeps Pages matcher-only. python `/api/ask` runs when `server.py` is up. When `GOPHER_LLM_HOOK` is set, python fires the live bot webhook (`GOPHER_LLM_KEY` is sent when present). The key stays on the python hole, never in the client. SMS and voice stay parked (no number). Telegram stays parked until `TELEGRAM_BOT_TOKEN`. No fake model name. No chat transcript.

## Live bot webhook

Python `GOPHER_LLM_HOOK` + `GOPHER_LLM_KEY` fire the live bot webhook from this process. Optional `GOPHER_REPLY_URL` (or `GOPHER_PUBLIC_URL` + `/api/brain/reply`) is where answers POST back. Copy `.env.example` to `.env` (gitignored; never served). GitHub Pages cannot hold the key; point `hole.json` `brain` at a public python hole if Ask GOPHER should leave the matcher. SMS/voice still parked (no number). `GET /api/status` llm is ready only when the hook env is set — wiring, not a live public brain until then.

## Open items (17)

| # | Item | Status | What “done” is | Blocked on |
| --- | --- | --- | --- | --- |
| 28 | CI | YAML local | Actions green on GitHub | PAT `workflow` scope |
| 76 | Custom domain | parked | DNS + TLS on the hole, not only github.io | domain registrar; Vercel later |
| 77 | Mail waitlist | code ready, needs env | real outbound mail on join | `RESEND_API_KEY` + from (or `GOPHER_MAIL_HOOK`) |
| 78 | SMS number | parked | a number people can text | not required; Telegram first |
| 79 | Voice in | parked | talk to the number, same thread | not required; Telegram first |
| 80 | Cloud accounts | parked | not device-only PBKDF2 | identity (Clerk or similar) |
| 81 | Billing | parked | a paid SKU that charges | Stripe checkout. Price is named ($19/month) |
| 83 | SLA | parked | a written SLA | legal + ops |
| 84 | Plugins | ticker + fng + market + trending on python | connected tools that fetch on a public host | Telegram/Resend parked until env |
| 85 | Cloud order log | code ready (`orders.jsonl`) | off-device log of ask → answer on a public host | Pages has no python |
| 86 | App store listing | parked | a store page | an app |
| 88 | Status uptime | process only | a real uptime product | monitor host |
| 91 | Legal counsel | parked | paid-service terms | a lawyer |
| 92 | Refund policy | parked | with billing, not before | `#/refund` honest parked hole; billing |
| 93 | DPA | parked | when there is a processor | `#/dpa` honest parked hole; billing + host |
| 95 | Hiring | not hiring | real openings only | you |
| 97 | Demo video | stills only | FETCH + directory, no stock | a capture |

Shipped this wave: **82 published prices** — $19/month on `/pricing`. Waitlist is the door. Checkout parked.

## Wire order (do not skip)

Free path = Pages/Vercel static + python brain on a free host + Telegram/email before Twilio.

Deploy runbook: `DEPLOY.md` and `#/deploy` (Pages → Render/Railway/Fly → point `brain` → optional Telegram/Resend).

1. **CI (28)** — add `workflow` to the GitHub PAT, push `.github/workflows/ci.yml`.
2. **Free host** — GitHub Pages now. Vercel static (free tier) later; not this batch. Python brain on a free host.
3. **Mail (77)** — Resend free tier join mail (`RESEND_API_KEY` + `GOPHER_MAIL_FROM`), then the waitlist is a product.
4. **Telegram** — test channel via `POST /api/telegram/webhook` when `TELEGRAM_BOT_TOKEN` is set. In-app Ask stays. No bot username invented.
5. **Billing (81, then 92–93)** — Stripe checkout for the named $19/month SKU. Price is public (82). Checkout still parked.
6. **SMS + voice (78–79)** — not required. Stay parked. Prefer Telegram/email/Ask first. Do not invent a number.
7. **Cloud accounts (80)** — replace local PBKDF2 when people pay.
8. **Uptime (88)** — a monitor that is not this process’s `/health`.
9. **Legal (91) + hiring (95) + store (86) + demo video (97)** — humans.

## Twilio

Not required. Prefer Telegram, Resend email, and in-app Ask first. Connector/skills are installed on the account. Still parked: no Account SID, Auth Token, or phone number in this process. Do not invent a number. Items 78 and 79 stay open.

Python endpoints `POST /api/twilio/sms`, `POST /api/twilio/voice`, and `POST /api/twilio/voice/order` exist. They return HTTP 503 `{"ok":false,"error":"twilio parked","sms":false}` until `TWILIO_NUMBER` and `TWILIO_AUTH_TOKEN` are set. Local signature skip: `GOPHER_TWILIO_SKIP_SIG=1` (dev only; not a public hole feature).

## Telegram

Free test channel. `POST /api/telegram/webhook` returns HTTP 503 `{"ok":false,"error":"telegram parked","telegram":false}` until `TELEGRAM_BOT_TOKEN` is set. When set, message text maps to `fulfill_order` and the reply goes through Telegram `sendMessage`. No bot username is published. Optional `TELEGRAM_WEBHOOK_SECRET` checks `X-Telegram-Bot-Api-Secret-Token`.

## Resend

Waitlist join mail. Prefer Resend HTML+text when `RESEND_API_KEY` and `GOPHER_MAIL_FROM` (or `RESEND_FROM`) are set; else `GOPHER_MAIL_HOOK`; else file-only. `GET /api/mail` returns 503 `mail parked` until ready. Item 77 stays open until a real join mail is sent.

## What this wave wires (honest)

- Public price $19/month on `/pricing`. Waitlist is the door. Checkout/billing parked (81).
- Python hole live plugin flags on `GET /api/status` (ticker, fng, market, trending live; telegram/sms/voice/mail/billing parked unless env is set)
- Fear/greed fetch on python (`fetch fg` / `fear greed` / `fng`)
- Market summary (`market`) and CoinGecko trending (`trending`) soft-fail on python
- Telegram webhook: `/start` help (no fake username), fulfill → sendMessage, optional `TELEGRAM_WEBHOOK_SECRET`; 503 until `TELEGRAM_BOT_TOKEN`
- Twilio webhook endpoints that 503 until env is set (not required)
- Waitlist mail: prefer Resend HTML+text (`RESEND_API_KEY` + from), then `GOPHER_MAIL_HOOK`, else file-only. `GET /api/mail` is 503 until ready. Item 77 stays open until a real join mail is sent.
- Durable order log `orders.jsonl` (last N) + `GET /api/orders?limit=` export. Item 85 needs a public python host (Pages is not enough).
- `#/blueprint` — this guide on the hole. Free path: Pages now, Vercel later, Telegram + Resend before Twilio.
- `#/plugins` — ticker/fng/market/trending live on python, Telegram/mail parked until env, SMS/voice parked (no number), billing parked
- `#/orders` — last orders from python `GET /api/orders` (no emails). Pages: device queue only
- `#/status` — `GET /api/status` when python is up. Not a 99.9% SLA

Pages still cannot run `server.py`. Anything `/api/*` besides a static 404 needs the python hole or another host.
