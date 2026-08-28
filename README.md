# GOPHER AI

Paid phone assistant. Search, then do the task.

## Live

Production: https://oxcryptobot.github.io/gopher/

Staging: https://oxcryptobot.github.io/gopher-test/

Method: ship to staging first, then promote to production. Type `ship` on the hole for the 100-item list (`SHIP.md`).

## On the hole

- Numbered Gopher directory (edit `hole.json`; the page loads it)
- Nested selectors: **Docs/**, **Play/**, **Tasks/**, **User/**
- Prompt: type a selector, alias (`tasks`, `maze`, `login`), or an order
- **FETCH** = search. Type `fetch btc` (or ETH, SOL, XRP, `fear greed`) as a type-0 document
- **DIG** = do a task from the 100 (`tasks`, watch / remind / draft)
- **Play/** — side quest: **MAZE/** (`#/fetch`) and **BURROW/** (`#/dig`). Kill time between searches.
- **User/** — device login (selector `9`). Passphrases are PBKDF2-hashed in localStorage. Not a cloud account yet.

## Keys

`/` prompt · `1` Docs/ · `5` Play/ · `7` Tasks/ · `9` user · `0` / `esc` home · WASD in MAZE when the prompt is not focused

## Local

```bash
python3 server.py
```

http://127.0.0.1:7070/

Copy `.env.example` to `.env` for webhook env (gitignored). GitHub Pages reads optional public `brain` from `hole.json` (empty = matcher only; never put secrets in the client).

## Promote

See [PROMOTE.md](PROMOTE.md). Short version: test on staging, run `python3 tests/test_*.py`, push `gopher-test`, then the same commit to production `gopher`.

## Tests

```bash
python3 tests/test_hole.py && python3 tests/test_static.py && python3 tests/test_server.py
```
