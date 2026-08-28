# GOPHER AI — missing product blueprint

Honest bar: **82/100**. Phases 0–2 are the playable hole (74/75). Phase 3 is the paid phone assistant (8/25). This file is the todo guide for the 18 open items. Type `blueprint` on the hole.

Do not mark an item done until the real product exists. No fake prices, numbers, SLA, or hiring.

## What already works

- Playable hole on staging and (older) production Pages
- FETCH 100-stage maze, DIG 8-stage burrow
- Waitlist JSON on `server.py`, device fallback on Pages
- Device login (PBKDF2 localStorage)
- Ticker `fetch btc` (Coinbase/OKX)
- Scores + Eternal GOPHER CHAMPIONS on python `/api/scores` and `/api/champions`
- Watch / remind / draft as **device queues**, not SMS
- EN/ES directory, shell, and 29 doc bodies

## Open items (18)

| # | Item | Status | What “done” is | Blocked on |
| --- | --- | --- | --- | --- |
| 28 | CI | YAML local | Actions green on GitHub | PAT `workflow` scope |
| 76 | Custom domain | parked | DNS + TLS on the hole, not only github.io | domain registrar |
| 77 | Mail waitlist | parked | real outbound mail on join | mail provider (Resend/Mailgun/SendGrid) |
| 78 | SMS number | parked | a number people can text | Twilio/Sinch + number |
| 79 | Voice in | parked | talk to the number, same thread | Twilio/Sinch voice |
| 80 | Cloud accounts | parked | not device-only PBKDF2 | identity (Clerk or similar) |
| 81 | Billing | parked | a paid SKU that charges | Stripe + a real price |
| 82 | Published prices | parked | public numbers only when real | you naming the SKU |
| 83 | SLA | parked | a written SLA | legal + ops |
| 84 | Plugins | ticker live | more connected tools that fetch | each provider |
| 85 | Cloud order log | python file | off-device log of ask → answer | python hole or a host |
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

## What this wave wires (honest)

- `#/blueprint` — this guide on the hole
- `#/plugins` — registry: ticker is live; mail/SMS/billing named and parked
- `#/orders` — last orders from python `GET /api/orders` (no emails). Pages: device queue only
- `#/status` — `GET /api/status` when python is up (process uptime + request count). Not a 99.9% SLA

## Connectors when you say go

Not installed. Install only after you pick one.

- Mail: Resend, Mailgun, or SendGrid
- SMS/voice: Twilio or Sinch
- Billing: Stripe
- Identity: Clerk

Pages cannot run `server.py`. Anything `/api/*` besides a static 404 needs the python hole or another host.
