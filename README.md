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
- **FETCH/** — original 8-bit burrow game (selector `5`)
- **User/** — device login (selector `9`). Passphrases are PBKDF2-hashed in localStorage. Not a cloud account yet.

## Keys

`/` prompt · `1` Docs/ · `5` Games/FETCH · `9` user · `0` / `esc` home · arrows in FETCH

## Local

```bash
python3 server.py
```

http://127.0.0.1:7070/
