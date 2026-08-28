# GOPHER AI

Paid phone assistant. Menus, selectors, fetch.

## Live

Production: https://oxcryptobot.github.io/gopher/

Staging: https://oxcryptobot.github.io/gopher-test/

Method: ship to staging first, then promote to production. Type `ship` on the hole for the 100-item list (`SHIP.md`).

## On the hole

- Numbered Gopher directory (edit `hole.json`; the page loads it)
- Nested selectors: **Docs/**, **Games/**, **User/**
- Prompt: type a selector, alias (`play`, `login`), or an order
- Live fetch: type `fetch btc` (or ETH, SOL, XRP, `price`) to pull a ticker as a type-0 document
- **FETCH/** — 100-stage maze (selector `5`). One tap, one tile. Energy pellets, orange foxes, clock.
- **User/** — device login (selector `9`). Passphrases are PBKDF2-hashed in localStorage. Not a cloud account yet.

## Keys

`/` prompt · `1` Docs/ · `5` Games/FETCH · `9` user · `0` / `esc` home · arrows in FETCH

## Local

```bash
python3 server.py
```

http://127.0.0.1:7070/

## Promote

See [PROMOTE.md](PROMOTE.md). Short version: test on staging, run `python3 tests/test_*.py`, push `gopher-test`, then the same commit to production `gopher`.

## Tests

```bash
python3 tests/test_hole.py && python3 tests/test_static.py && python3 tests/test_server.py
```
