# Promote GOPHER AI (staging → production)

Staging: https://oxcryptobot.github.io/gopher-test/
Production: https://oxcryptobot.github.io/gopher/

Never push a half-built hole to production first.

## Runbook

1. Work in `/workspace/gopher` (or a clone of `OxCryptobot/gopher`).
2. Type `ship` on the hole, or read `SHIP.md`. Only check an item when it is actually live.
3. Run tests:

```bash
python3 tests/test_hole.py
python3 tests/test_static.py
python3 tests/test_server.py
python3 -m py_compile server.py
```

4. Commit. Push **test** remote (`OxCryptobot/gopher-test`) `main`.
5. Hard-refresh https://oxcryptobot.github.io/gopher-test/ and play FETCH (`#/fetch`). Confirm the orange TEST HOLE bar.
6. If the hole is good, promote the **same commit** to `OxCryptobot/gopher` `main`. GitHub Pages on production rebuilds from that branch.
7. Production must not show the TEST ribbon (it keys off `/gopher-test` in the path).

## Do not promote

- Fake prices, fake SLA, fake SMS numbers
- CI workflow files until the GitHub token has `workflow` scope
- Secrets: `waitlist.json`, `orders.json`, `scores.json`

## Blocked on a human

Custom domain, outbound mail (Resend key), billing checkout (Stripe), phone number (not required; prefer Telegram/email), cloud accounts.
