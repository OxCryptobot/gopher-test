# GOPHER AI ship list

Production: https://oxcryptobot.github.io/gopher/  
Staging: https://oxcryptobot.github.io/gopher-test/  
Method: stage on test, then promote to production. Do not ship to production first. Production is frozen until promote.

Status marks are honest as of 2026-08-28.

Progress: 82/100. Phase 0 25/25, phase 1 24/25 (28 CI blocked on workflow PAT), phase 2 25/25, phase 3 7/25.

Open: 28, 76–86, 88, 90, 91–93, 95, 97.

- `[x]` done on production
- `[ ]` this staging wave, or next

Full list: 100 items in four phases. GOPHER AI only.

## Phase 0 — Playable hole (1–25)

The public hole is playable. Directory, FETCH, waitlist, and device login are live.

1. [x] FETCH — 100-stage maze, one tap one tile (never auto-runs), home selector 5
2. [x] hole.json — data-driven catalog (holes + aliases)
3. [x] Hash routes — `#/docs`, `#/fetch`, `#/user`, and the rest of the tree
4. [x] Device login — PBKDF2 (SHA-256, 120000 iterations) in localStorage
5. [x] Waitlist — email form; server list locally, device fallback on Pages
6. [x] Ticker fetch — `fetch btc` (ETH, SOL, XRP, DOGE, ADA) as a type-0 document
7. [x] PLAY CTA — home row `5 PLAY FETCH`
8. [x] First-hole tutorial — GOT IT, stored on device
9. [x] D-pad — on-screen FETCH controls
10. [x] WASD + arrows — one tap, one tile
11. [x] Pause — `P` and PAUSE / RESUME
12. [x] Swipe — FETCH canvas touch gestures
13. [x] Haptics — `navigator.vibrate` on grab and hit (respects reduced motion)
14. [x] Particles — pellet-collect specks on the canvas
15. [x] PWA shell — `manifest.json`, `sw.js`, service worker register
16. [x] 404 — `404.html`, selector-not-found, link home and FETCH
17. [x] robots.txt — Allow `/`, Sitemap pointer
18. [x] sitemap.xml — production origin plus `#/fetch` and `#/dig`
19. [x] security.txt — `.well-known/security.txt`
20. [x] LICENSE — MIT, OxCryptobot 2026
21. [x] CSP on the python server — Content-Security-Policy plus companion headers
22. [x] `/health` — local python liveness (`ok` / JSON). Pages is static; this is the process, not a fake 99.9%
23. [x] `/api/scores` — GET board when `python3 server.py` is up
24. [x] Nested docs — Docs/, Site/, Legal/, Games/, User/
25. [x] FAQ, pricing, and terms holes — no invented prices, no fake SLA

## Phase 1 — Staging and quality (26–50)

Staging exists. Quality docs and a11y basics that already landed on production are checked. 24/25 done. Open: 28 CI workflow — YAML exists locally; PAT lacks `workflow` scope so Actions is not on GitHub yet.

26. [x] Staging site — https://oxcryptobot.github.io/gopher-test/
27. [x] TEST ribbon — show `TEST HOLE · not production` on the staging host
28. [ ] CI workflow — YAML exists locally; PAT lacks `workflow` scope so Actions is not on GitHub yet
29. [x] hole.json tests — selector 5 is FETCH/, `play` → `/fetch`, required holes, no banned vendor copy
30. [x] Static tests — PLAY FETCH, manifest name, sw cache gopher-v4 (includes dig.js), game exports, maze strings (fox, Huzaaa, Clunk, Ouchies, TIME OVER, GOPHER CHAMPION), dig.js exists and exports DigGame, 404, `server.py` compile
31. [x] A11y d-pad labels — `aria-label` on the pad and each direction
32. [x] SHARE score — Web Share / clipboard of the FETCH result
33. [x] INSTALL PWA hook — `beforeinstallprompt` and an INSTALL control
34. [x] Ship list page — this file, linked from `/ship`
35. [x] README methodology — stage on test, promote to production, written in the README
36. [x] `.nojekyll` — GitHub Pages serves the hole as static files
37. [x] apple-touch-icon — PNG on disk; apple-touch link in the document
38. [x] Manifest icons — 192 and 512 PNG, purpose `any`
39. [x] Reduced motion — CRT off, no animation; haptics skipped
40. [x] Skip link — Skip to prompt
41. [x] Live title — `document.title` follows the current hole
42. [x] Scores hole — `#/scores`, device best; python `/api/scores` when the server is up. Pages cannot host a true global board
43. [x] Keys doc — `#/keys`, 1–9 / ? esc, FETCH moves
44. [x] Changelog — `#/changelog`, dated 2026-08-27/28 (2026-08-28: maze FETCH polish, playable DIG, device watch/remind/draft, 82/100)
45. [x] Contact — GitHub + waitlist, no support number
46. [x] Status hole — Pages is static; python `/health` is the process; no fake 99.9%, no fake uptime graph
47. [x] Press hole — one paragraph, no invented metrics
48. [x] Jobs hole — not hiring; no fake roles
49. [x] `/es` stub — one Spanish hole, rest of the tree in English
50. [x] humans.txt — GOPHER AI, OxCryptobot

## Phase 2 — Depth (51–75)

Playable is not deep. Combo and waitlist rate-limit are already in. DIG is playable this wave (type `dig` or Games/). A true global board and Eternal GOPHER CHAMPIONS are python `/api/scores` and `/api/champions` only; GitHub Pages cannot host them.

51. [x] i18n toggle — language switch, not only `/es`
52. [x] FETCH maze — 100 stages with alternate pathways; energy pellets (Huzaaa!); orange foxes (Ouchies! −1 HP); walls Clunk!!! (−0.1 HP); star ZAP/BLOCK; KEY; stage clear VICTORY!; clock 0 TIME OVER!; all 100 GOPHER CHAMPION! + trophy + Eternal GOPHER CHAMPIONS; 3 HP; reasonable time limit; foxes +0.01 speed per stage; stage 100 nearly impossible; mute defaults on (browser autoplay)
53. [x] DIG — playable 8-stage burrow (one tap, one tile, rocks fall). Type `dig` or Games/. FETCH stays the 100-stage maze
54. [x] Offline ticker cache — last good quote when the public spot is down
55. [x] Focus trap on the tutorial — Tab stays in the first-hole dialog
56. [x] Keyboard help overlay — a real overlay, not only the `?` status line
57. [x] High contrast — optional phosphor/contrast mode
58. [x] Print-safe skip — skip link and CRT do not wreck a print stylesheet
59. [x] Rate-limit already — waitlist POST capped on the python server (8 / hour / IP)
60. [x] Leaderboard — device best in localStorage on every hole; server-wide board is GET `/api/scores` and Eternal GOPHER CHAMPIONS is GET `/api/champions` when `python3 server.py` is up. GitHub Pages has no python process, so the live Pages hole cannot host a true global board or global champions list
61. [x] Haptic setting — user toggle, independent of MUTE
62. [x] Volume — gain control, not only MUTE / SOUND. Mute defaults on (browser autoplay). Friendly chiptune + FX
63. [x] Combo already — consecutive pellet grabs add a point
64. [x] Restart confirm — START while a run is live asks before wiping the hole
65. [x] Landscape lock hint — notice when the phone is the wrong way
66. [x] Safe-area insets — `env(safe-area-inset-*)` padding (viewport-fit is already cover)
67. [x] Manifest screenshots — install-store shots in `manifest.json`
68. [x] Maskable icon — purpose `maskable` (192 / 512)
69. [x] Share-card OG for FETCH — Open Graph + Twitter tags; description names FETCH
70. [x] Canonical URL — `link rel=canonical` on the production origin
71. [x] JSON-LD SoftwareApplication — structured data for the hole
72. [x] Sitemap all holes — every public selector, not only `/` and `#/fetch`
73. [x] 304 caching — python static files honor If-Modified-Since
74. [x] ETag — explicit validators on hole.json and the shell
75. [x] Extra python headers already — nosniff, `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy

## Phase 3 — Product (76–100)

Paid phone assistant. None of this is pretend-shipped. Waitlist is the only door.

76. [ ] Custom domain — gopher.ai (or successor) on the hole, not only github.io
77. [ ] Mail waitlist — real outbound mail, not only a JSON file / device stash
78. [ ] SMS number — a number people can text
79. [ ] Voice in — talk to the number, order in the same thread
80. [ ] Cloud accounts — not device-only PBKDF2
81. [ ] Billing — a paid SKU, not a mock table
82. [ ] Published prices — public numbers only when they are real
83. [ ] SLA — none today; do not invent one
84. [ ] Plugins — connected tools that actually fetch
85. [ ] Cloud order log — what was asked and what came back, off-device
86. [ ] Phone app store listing — a store page if/when there is an app
87. [x] Analytics opt-in — TRACK? on the hole; default off; still sends nowhere
88. [ ] Status page uptime — a real uptime hole, not only `/status` copy. Do not fake 99.9%
89. [x] Error reporting — on-device log only (`gopher_log_v1`), no cloud
90. [x] i18n full — EN/ES toggle, directory names, FETCH/DIG shell, and 29 doc bodies (`copy_es`). Buttons stay EN. Not every language, EN/ES is the pair
91. [ ] Legal counsel pass — paid-service terms before money moves
92. [ ] Refund policy — with billing, not before
93. [ ] DPA — when there is a processor relationship
94. [x] Cookie banner — not required; this hole has no tracking cookies
95. [ ] Hiring — not hiring; no fake openings
96. [x] Press kit images — `press/home.png`, `press/fetch.png`, `press/icon.png`
97. [ ] Demo video — FETCH + the directory, no stock sludge
98. [x] Brand book — working `BRAND.md` (not a 40-page PDF)
99. [x] Onboarding quest — play FETCH, fetch btc, waitlist
100. [x] Watch / remind / draft as device queues (type `watch`, `remind`, `draft` — stored on this device, not SMS, no number). [x] Promote runbook in PROMOTE.md. [x] PWA install hole `/install`. [ ] Phone SMS watch / remind / draft.
