# GOPHER AI — SHIP A→Z

Honest plan from **83/100** to a real ship. Public face: **GOPHER AI** only. Public price: **$19/month**. Waitlist is the door. Twilio is not required. Prefer Telegram + Resend. Stage on **gopher-test**; production stays frozen until promote.

Companion docs: `BLUEPRINT.md` (missing product), `SHIP.md` (100-item list), `DEPLOY.md` (free host path), `PROMOTE.md` (staging→prod), `MARKETING.md` / `LAUNCH.md` / `NURTURE.md` / `CREATORS.md` (Phase C), `DISTRIBUTION.md` (Phase D), `DEMO.md` (stills; video not yet).

## Status now

| Bar | Score | Meaning |
| --- | --- | --- |
| Overall | **83/100** | Do not mark items done until the real product exists |
| Playable hole | **74/75** | Phases 0–2; miss is **28 CI** (PAT `workflow` scope) |
| Paid phone | **9/25** | Phase 3 — hard product still open |

- Staging: https://oxcryptobot.github.io/gopher-test/
- Production: https://oxcryptobot.github.io/gopher/ — **frozen** until promote
- Free path: Pages (static) → python host (Render/Railway/Fly) → optional Telegram/Resend
- Code ready, env/host parked: mail (77), Telegram, order log (85), more plugins (84)
- Explicitly parked: SMS/voice (78/79), Stripe (81), cloud accounts (80), domain (76), SLA (83), store (86), hiring (95)

## North star

**Shipped** means a paid **$19/month** phone VA people can actually reach: web Ask (matcher + optional live brain), Telegram bot when token is real, and email waitlist with real join mail — honest checkout when Stripe is live, no invented phone numbers, bot usernames, or SLA percentages. Waitlist remains the door until money moves. Stage on test; promote one commit when A+B exit.

## Phases (do not skip)

### Phase A — Foundation unlocks (days 0–2)

| ID | Work | Done when |
| --- | --- | --- |
| **A1** | CI (28) | PAT with `workflow` scope → push `.github/workflows/ci.yml` to **test** remote; Actions green |
| **A2** | Free python host | Render / Railway / Fly per `DEPLOY.md`; `GET /health` → ok; `GOPHER_PUBLIC_URL` set |
| **A3** | Point brain | Non-empty `brain` https URL in `hole.json` on staging; hard-refresh `gopher-vN` |
| **A4** | Resend | `RESEND_API_KEY` + `GOPHER_MAIL_FROM` → real join mail on waitlist (77) |
| **A5** | Telegram | BotFather token → `TELEGRAM_BOT_TOKEN` + `telegram_set_webhook.py` (no invented username) |
| **A6** | Live Ask | Restore `GOPHER_LLM_HOOK` brain webhook if Ask must leave the matcher |

**Exit criteria (A)**

- [ ] CI green on gopher-test (or consciously deferred with PAT plan)
- [ ] Public python `/health` ok
- [ ] Staging `brain` points at that origin; Ask works beyond matcher when intended
- [ ] Waitlist join sends real mail (or documented park with env missing)
- [ ] Telegram webhook 200 with real token (or documented park)
- [ ] Progress still honest — only mark 77/84/85 when env+host prove live

### Phase B — Product complete for beta (days 2–7)

| ID | Work | Notes |
| --- | --- | --- |
| **B1** | Mark 77 / 84 / 85 | Only when env+host prove live — never paper-ship |
| **B2** | Stripe Checkout $19/mo (81) | Parked until ready; then refund (92) + DPA (93) copy **with counsel** |
| **B3** | Cloud accounts (80) | Clerk (or similar) when money moves — device PBKDF2 is not cloud |
| **B4** | Custom domain (76) | DNS + TLS; Vercel static optional |
| **B5** | Uptime monitor (88) | External check; **not** a fake 99.9% |
| **B6** | Demo video (97) | Capture real FETCH + directory; no stock |
| **B7** | Legal (91) | Counsel pass; hiring stays **not hiring** (95); store listing (86) only if app |
| **B8** | SMS / voice (78/79) | Stay parked unless later needed; Twilio never required |

**Exit:** beta invite from waitlist works end-to-end (mail → hole → Telegram or Ask → no broken checkout promise).

### Phase C — Marketing system (parallel from day 0)

| ID | Work |
| --- | --- |
| **C1** | Positioning one-liner + 3 bullets (protocol nostalgia, FETCH/DIG, $19 waitlist) |
| **C2** | Landing funnel: home → pricing → waitlist; press kit; OG/social meta; share cards from `BRAND.md` phosphor |
| **C3** | Content: 4 launch posts (X/Twitter, Reddit, HN Show HN, Product Hunt later) — see `LAUNCH.md` |
| **C4** | Waitlist nurture: Resend welcome + weekly “hole notes” — `NURTURE.md` (no spam) |
| **C5** | Influencer/creator list criteria — `CREATORS.md` (crypto twitter, retro web, indie hackers; no fake metrics) |
| **C6** | SEO: sitemap, humans.txt, press hole, unique titles — finish keywords |
| **C7** | Demo stills → short demo reel (97) — `DEMO.md` / `#/demo`; video not yet |

**Assets checklist:** OG meta · press blurb · 4 posts · nurture email (`NURTURE.md`) · creators criteria (`CREATORS.md`) · share card (`press/share-card.svg`) · demo stills (`DEMO.md`) · `MARKETING.md` · `DISTRIBUTION.md`

### Phase D — Distribution (days 5–21)

| ID | Work |
| --- | --- |
| **D1** | Owned: site + Telegram bot + email list |
| **D2** | Community: public GitHub, Show HN, Indie Hackers, relevant Discords (rules-respecting) |
| **D3** | App: PWA install first (`/install`, manifest); native store (86) only after product sticks |
| **D4** | Partnerships: protocol/retro blogs, crypto newsletter swaps — **after** beta |
| **D5** | Promote runbook: `PROMOTE.md` staging→production only when A+B exit met |
| **D6** | Metrics that matter: waitlist joins, Telegram DAU, paid conversions (after Stripe) — not vanity — see `DISTRIBUTION.md` |

### Phase E — Launch day runbook

| ID | Work |
| --- | --- |
| **E1** | Soft launch staging with TEST ribbon off for select testers (custom domain or passwordless invite) |
| **E2** | Promote production **same commit** |
| **E3** | Announce sequence: waitlist email → Telegram → X → HN → PH |
| **E4** | Support: GitHub issues + waitlist reply; no fake phone support |
| **E5** | Kill / rollback: if checkout or mail fails, pause ads, keep waitlist |

### Phase F — Post-launch (week 2–8)

| ID | Work |
| --- | --- |
| **F1** | Convert waitlist → paid |
| **F2** | SLA only if ops real (83) |
| **F3** | More plugins (84) |
| **F4** | Optional Twilio later |
| **F5** | Hiring only if real roles (95) |

## Owner map

| Item | Owner | Blocked on |
| --- | --- | --- |
| A1 CI workflow push | you (PAT) / code | GitHub PAT `workflow` scope |
| A2 python host | you (host dashboard) | Render/Railway/Fly account |
| A3 brain URL on staging | code + you | A2 public URL |
| A4 Resend keys | you | Resend account + verified from |
| A5 Telegram token + webhook | you | BotFather token |
| A6 LLM hook | you | Live bot webhook URL + key |
| B2 Stripe + refund/DPA | you + lawyer | Ready to take money |
| B3 Clerk (or similar) | you / code | Billing live |
| B4 Domain DNS/TLS | you (registrar) | Domain owned |
| B5 Uptime monitor | you | External monitor account |
| B6 Demo video | you | Screen capture of real hole |
| B7 Legal counsel | lawyer | Retainer / review |
| C1–C7 Marketing copy/assets | code + you | Brand rules in `BRAND.md` |
| D5 Promote | you | A+B exit |
| E support | you | GitHub + waitlist inbox |

## Money path

```
Waitlist → email proof (Resend) → Stripe $19/mo → cloud accounts → refund policy + DPA
```

Do not open Stripe until mail + python host + beta invite work. Price is public; checkout is not live until B2.

## Do not invent

- Phone numbers / SMS / voice lines
- Telegram bot usernames
- SLA percentages (no fake 99.9%)
- Other prices (only **$19/month**)
- Hiring / open roles
- Counsel language / DPA / refund legalese without a lawyer
- Fake uptime graphs or vanity metrics (ARR, download counts, awards)
- Vendor names in public copy (keep public face **GOPHER AI**)

## Immediate next 10 actions (ordered)

1. **Agent / code (no secrets):** keep shipping docs + hole copy on **gopher-test** only (`SHIP_AZ.md`, `/ship-az`, OG, `LAUNCH.md`).
2. **Agent / code:** run tests; push **test** remote; never promote production until A+B exit.
3. **You:** create free python host (Render/Railway/Fly); set `GOPHER_PUBLIC_URL`; confirm `/health`.
4. **You:** add `RESEND_API_KEY` + `GOPHER_MAIL_FROM`; join waitlist once; confirm real mail.
5. **You:** BotFather → `TELEGRAM_BOT_TOKEN`; run `scripts/telegram_set_webhook.py` against public URL.
6. **You + agent:** set staging `hole.json` `brain` to python https origin; bump cache; hard-refresh.
7. **You (optional A6):** set `GOPHER_LLM_HOOK` (+ key) only if live Ask beyond matcher is required.
8. **You:** PAT with `workflow` scope → allow CI YAML push to test (A1 / item 28).
9. **Agent / code (Phase C):** keep funnel + posts + nurture drafts current; no fake metrics.
10. **You:** when A+B exit green, follow `PROMOTE.md` — same commit to production; then announce per E3.

Type `ship-az` on the hole. Progress stays **83/100** until something truly ships.
