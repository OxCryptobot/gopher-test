# GOPHER AI — soft-tester beta (Phase E1)

Honest select-testers path. Progress stays **83/100**. Public price **$19/month**. No fake emails, bot usernames, Twilio numbers, or live checkout invented here.

## Hole

- Type `beta` / `invite` / `testers` → `#/beta`
- Copy: select testers only. Soft launch on staging (`gopher-test`). Production frozen until promote (`PROMOTE.md`).

## Invite codes (optional python)

- Env: `INVITE_CODES` — comma-separated plaintext codes (gitignored `.env`)
- Python hashes with SHA-256 and compares with `hmac.compare_digest`
- `POST /api/invite/redeem` body `{"code":"..."}`
  - No `INVITE_CODES` → HTTP **503** `{ok:false, error:"invite parked", invite:false}`
  - Bad code → **403**
  - Good code → `{ok:true, invite:true, flag:"gopher_beta_v1"}`
- `GET /api/status` → `plugins.invite` / top-level `invite` ready only when codes are set

## Device-only flag

- `localStorage` key **`gopher_beta_v1`** (`"1"` = on)
- Client redeem sets it when python accepts a code
- You can flip the flag on-device without python (device-only beta). Not a cloud account.

## Checkout (Phase B2 — related)

- Public price on `/pricing`. Checkout hole: `/checkout`
- `GET`/`POST /api/checkout` → **503** `{ok:false, error:"checkout parked", billing:false}` until `STRIPE_SECRET_KEY` + `STRIPE_PRICE_ID` (price id must be the **$19/month** product)
- When env is set: POST creates a Stripe Checkout Session; success/cancel URLs from `GOPHER_PUBLIC_URL`. Secret never goes to the client.
- **Do not mark SHIP item 81 done** until real Stripe keys + money path work. BLUEPRINT: code ready, needs Stripe keys.

## Docs

- Plan: `SHIP_AZ.md` Phase B2 / E1
- Missing product: `BLUEPRINT.md`
- Env template: `.env.example`

Type `beta` on the hole.
