# How to play FETCH

FETCH is a 100-stage maze on this site. Alternate pathways. One tap, one tile — you never auto-run. Free demo. Not the paid phone assistant.

DIG is a separate 8-stage burrow (type `dig` or Games/). FETCH stays the 100-stage maze.

Open it: press 5, type `play`, or go to `#/fetch`. Hit START.

## Move

Arrows, WASD, or the pad. One tap equals one tile. The player never auto-runs.

## Eat, bump, get hit

- Energy pellets shout **Huzaaa!**
- Wall bump: **Clunk!!!** costs **0.1 HP**. Health bar starts at 3.0.
- Orange foxes hit: **Ouchies!** costs **1 HP**.
- One star per stage, random tile. Pick it up, then **ZAP** a fox or **BLOCK** a hit.
- **KEY** or `K` shows the in-game key.

## Clock and stages

- Stage clear: **VICTORY!**
- Clock hits 0: **TIME OVER!**
- Clear all 100: **GOPHER CHAMPION!**, a trophy, and your name on **Eternal GOPHER CHAMPIONS**.
- Time limit per stage is reasonable. Foxes speed up 0.01 each stage. Stage 100 is nearly impossible.

## Sound

Friendly chiptune + FX. MUTE still defaults on (browser autoplay).

## Scores

Device best lives in localStorage on this device. That works on GitHub Pages and on a local python hole.

The hole board is `GET /api/scores` when `python3 server.py` is serving. Eternal GOPHER CHAMPIONS is `GET /api/champions` on that same server (append-only names who cleared 100). GitHub Pages has no python process, so the live Pages hole cannot host a true global board or global champions list — device best and a local eternal list still work.
