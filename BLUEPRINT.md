# GOPHER AI — missing product blueprint

Honest bar: **82/100**. About 18% of the 100-list is still open, but remaining work is the HARD product, not 18% of effort.

Two bars:

- Playable hole **74/75** (phases 0–2; item 28 CI is the miss)
- Paid phone **8/25** (phase 3)

Type `blueprint` on the hole. Do not mark an item done until the real product exists. No fake prices, numbers, SLA, or hiring.

## What already works

- Playable hole on staging and (older) production Pages
- FETCH is search; DIG is a task from the 100; MAZE/BURROW side quest
- Waitlist JSON on `server.py`, device fallback on Pages
- Device login (PBKDF2 localStorage)
- Ticker `fetch btc` (ETH SOL XRP DOGE ADA LINK UNI AVAX MATIC DOT ATOM NEAR APT SUI TON)
- Python fear/greed fetch (`fetch fg` / `fear greed` / `fng`)
- Scores + Eternal GOPHER CHAMPIONS on python `/api/scores` and `/api/champions`
- Watch / remind / draft as **device queues**, not SMS
- EN/ES directory, shell, and 29 doc bodies
- Python `/api/status` product flags and `/api/orders` last 20 (no emails)
- Twilio webhook endpoints on python: HTTP 503 until env is set


## Prompt / 100 tasks

Live autoprompt on the hole: type in Prompt <search>, ranked selectors appear. Catalog is `tasks.json` (100). Parked products (SMS, voice, mail, billing, prices, domain, cloud accounts, SLA, hiring) still parked — they do not fake a number. Python `GET /api/tasks`. Pages uses static `tasks.json`.

## Prompt UX

The GOPHER prompt is always on (the star). One quiet nav row: GOPHER · search · tasks · waitlist · play. Directory is the page. Three answers under the prompt. MAZE and BURROW live under play. GOPHER is an on-device order router over 100 tasks + python `/api/ask` when `server.py` is up. A hosted model is parked until `GOPHER_LLM_HOOK` is set. No fake model name. No chat transcript.

## Open items (18)

| # | Item | Status | What “done” is | Blocked on |
| --- | --- | --- | --- | --- |
| 28 | CI | YAML local | Actions green on GitHub | PAT `workflow` scope |
| 76 | Custom domain | parked | DNS + TLS on the hole, not only github.io | domain registrar |
| 77 | Mail waitlist | parked | real outbound mail on join | mail provider (Resend/Mailgun/SendGrid) |
| 78 | SMS number | parked | a number people can text | Twilio SID/token/number |
| 79 | Voice in | parked | talk to the number, same thread | Twilio voice |
| 80 | Cloud accounts | parked | not device-only PBKDF2 | identity (Clerk or similar) |
| 81 | Billing | parked | a paid SKU that charges | Stripe + a real price |
| 82 | Published prices | parked | public numbers only when real | you naming the SKU |
| 83 | SLA | parked | a written SLA | legal + ops |
| 84 | Plugins | ticker + fng live on python | more connected tools that fetch | each provider |
| 85 | Cloud order log | python file | off-device log of ask → answer on a public host | Pages has no python |
| 86 | App store listing | parked | a store page | an app |
| 88 | Status uptime | process only | a real uptime product | monitor host |
| 91 | Legal counsel | parked | paid-service terms | a lawyer |
| 92 | Refund policy | parked | with billing, not before | billing |
| 93 | DPA | parked | when there is a processor | billing + host |
| 95 | Hiring | not hiring | real openings only | you |
| 97 | Demo video | stills only | FETCH + directory, no stock | a capture |

## Wire order (do not skip)

1. **CI (28)** — add `workflow` to the GitHub PAT, push `.github/workflows/ci.yml`.
2. **Domain (76)** — pick the hostname, point it at Pages or the python hole.
3. **Mail (77)** — connect a mail plugin, send one join mail, then the waitlist is a product.
4. **Billing (81–82, then 92–93)** — you name a price, Stripe/Link takes it, then refunds and a DPA.
5. **SMS + voice (78–79)** — number, then watch/remind/draft leave the device queue.
6. **Cloud accounts (80)** — replace local PBKDF2 when people pay.
7. **Uptime (88)** — a monitor that is not this process’s `/health`.
8. **Legal (91) + hiring (95) + store (86) + demo video (97)** — humans.

## Twilio

Connector/skills are installed on the account. Still parked: no Account SID, Auth Token, or phone number in this process. Colombia numbers need a Twilio regulatory bundle. US A2P needs 10DLC. Do not invent a number.

Python endpoints `POST /api/twilio/sms`, `POST /api/twilio/voice`, and `POST /api/twilio/voice/order` exist. They return HTTP 503 `{"ok":false,"error":"twilio parked","sms":false}` until `TWILIO_NUMBER` and `TWILIO_AUTH_TOKEN` are set. Local signature skip: `GOPHER_TWILIO_SKIP_SIG=1` (dev only; not a public hole feature).

## What this wave wires (honest)

- Python hole live plugin flags on `GET /api/status` (ticker live, fng live, sms/voice/mail/billing parked unless env is set)
- Fear/greed fetch on python (`fetch fg` / `fear greed` / `fng`)
- Twilio webhook endpoints that 503 until env is set
- Waitlist mail hook if `GOPHER_MAIL_HOOK` is set (file-only if unset). Mail is still parked.
- `#/blueprint` — this guide on the hole
- `#/plugins` — ticker live, fng live on python, SMS/voice parked (skills installed, no number), mail parked, billing parked
- `#/orders` — last orders from python `GET /api/orders` (no emails). Pages: device queue only
- `#/status` — `GET /api/status` when python is up. Not a 99.9% SLA

Pages still cannot run `server.py`. Anything `/api/*` besides a static 404 needs the python hole or another host.
