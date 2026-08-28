/* BURROW — 30-stage dig. Gems, rocks, one tap one tile. */
(function (global) {
  "use strict";

  var COLS = 20, ROWS = 16, TILE = 8;
  var DIRS = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
  var EMPTY = 0, WALL = 1, DIRT = 2, ROCK = 3, GEM = 4, EXIT = 5;
  var MAX_LVL = 30;
  var THEMES = [
    { wall: "#1c140c", dirt: "#6b3a18", dirt2: "#8a5224", pellet: "#c4a054", player: "#39ff14" },
    { wall: "#241808", dirt: "#7a4018", dirt2: "#9a5a28", pellet: "#d4b060", player: "#5cff38" },
    { wall: "#18120c", dirt: "#5a3014", dirt2: "#7a4420", pellet: "#b89048", player: "#6a8a32" }
  ];
  var GEM_C = "#f0c840";
  var ROCK_C = "#8c8c8c";
  var ROCK_HI = "#c8c8c8";
  var ROCK_LO = "#5a5a5a";
  var ERR = "#ff6a3d";

  function rnd(n) { return Math.floor(Math.random() * n); }

  function lcg(seed) {
    var s = (seed >>> 0) || 1;
    return function () {
      s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  function caveFor(lvl) {
    var rng = lcg(lvl * 7919 + 42);
    var g = [], x, y, i, n, px, py;
    for (y = 0; y < ROWS; y++) {
      g[y] = [];
      for (x = 0; x < COLS; x++) {
        g[y][x] = (x === 0 || y === 0 || x === COLS - 1 || y === ROWS - 1) ? WALL : DIRT;
      }
    }
    g[1][1] = EMPTY;
    g[1][2] = EMPTY;
    g[2][1] = EMPTY;
    g[2][2] = EMPTY;
    n = Math.max(4, 14 - lvl);
    for (i = 0; i < n; i++) {
      x = 2 + Math.floor(rng() * (COLS - 4));
      y = 2 + Math.floor(rng() * (ROWS - 4));
      if (x <= 2 && y <= 3) continue;
      g[y][x] = EMPTY;
      if (rng() > 0.45 && x + 1 < COLS - 1) g[y][x + 1] = EMPTY;
      if (rng() > 0.55 && y + 1 < ROWS - 1) g[y + 1][x] = EMPTY;
    }
    n = 1 + Math.floor(lvl / 2);
    i = 0;
    while (n > 0 && i < 80) {
      i++;
      x = 2 + Math.floor(rng() * (COLS - 4));
      y = 2 + Math.floor(rng() * (ROWS - 4));
      if (x <= 2 && y <= 3) continue;
      if (g[y][x] !== DIRT) continue;
      g[y][x] = WALL;
      n--;
    }
    n = 2 + Math.min(14, lvl);
    i = 0;
    while (n > 0 && i < 200) {
      i++;
      x = 1 + Math.floor(rng() * (COLS - 2));
      y = 1 + Math.floor(rng() * (ROWS - 2));
      if (x <= 2 && y <= 3) continue;
      if (g[y][x] !== DIRT) continue;
      px = x;
      py = y - 1;
      if (py >= 1 && py <= 3 && px <= 2) continue;
      g[y][x] = ROCK;
      n--;
    }
    n = Math.min(12, 3 + Math.floor((lvl - 1) / 3));
    i = 0;
    while (n > 0 && i < 240) {
      i++;
      x = 2 + Math.floor(rng() * (COLS - 4));
      y = 2 + Math.floor(rng() * (ROWS - 4));
      if (x <= 2 && y <= 3) continue;
      if (g[y][x] !== DIRT) continue;
      g[y][x] = GEM;
      n--;
    }
    n = 0;
    for (y = 1; y < ROWS - 1; y++) {
      for (x = 1; x < COLS - 1; x++) {
        if (g[y][x] === GEM) n++;
      }
    }
    if (n === 0) g[ROWS - 2][COLS - 2] = GEM;
    return g;
  }

  function DigGame(canvas, hooks) {
    this.canvas = canvas;
    this.c = canvas.getContext("2d");
    this.c.imageSmoothingEnabled = false;
    this.hooks = hooks || {};
    this.mute = true;
    this.hapticOn = true;
    this.volume = 0.03;
    this.needConfirm = false;
    this.theme = 0;
    this.running = false;
    this.paused = false;
    this.looping = false;
    this.raf = 0;
    this.parts = [];
    this.flash = 0;
    this.tx = 0;
    this.ty = 0;
    this.tOn = false;
    this.maxLvl = MAX_LVL;
    this.cleared = false;
    this.lives = 3;
    this.hp = 3;
    this.rockMs = 380;
    this.rockAcc = 0;
    this.lastTs = 0;
    this.shoutText = "";
    this.shoutLife = 0;
    this.reset(1);
    this.bind();
    this.ensureLoop();
  }

  DigGame.prototype.reset = function (lvl) {
    this.lvl = lvl || 1;
    if (this.lvl > MAX_LVL) this.lvl = MAX_LVL;
    this.theme = (this.lvl - 1) % 3;
    this.needConfirm = false;
    if (lvl === 1) {
      this.score = 0;
      this.lives = 3;
      this.cleared = false;
    }
    this.hp = this.lives;
    this.grid = caveFor(this.lvl);
    this.falling = [];
    var y, x, gems = 0;
    for (y = 0; y < ROWS; y++) {
      this.falling[y] = [];
      for (x = 0; x < COLS; x++) {
        this.falling[y][x] = 0;
        if (this.grid[y][x] === GEM) gems++;
      }
    }
    this.sx = 1;
    this.sy = 1;
    this.px = this.sx;
    this.py = this.sy;
    this.gemsNeed = Math.max(1, gems);
    this.gemsLeft = this.gemsNeed;
    this.need = this.gemsNeed;
    this.got = 0;
    this.needLeft = this.gemsLeft;
    this.exitOn = false;
    this.needLeft = this.need;
    this.dead = false;
    this.win = false;
    this.rockMs = Math.max(180, 400 - (this.lvl - 1) * 24);
    this.rockAcc = 0;
    this.parts = [];
    this.flash = 0;
  };

  DigGame.prototype.at = function (x, y) {
    if (x < 0 || y < 0 || x >= COLS || y >= ROWS) return WALL;
    return this.grid[y][x];
  };

  DigGame.prototype.bind = function () {
    var self = this, el = this.canvas;
    this._onTs = function (e) {
      var t = e.changedTouches && e.changedTouches[0];
      if (!t) return;
      self.tx = t.clientX;
      self.ty = t.clientY;
      self.tOn = true;
    };
    this._onTm = function (e) {
      if (!self.tOn) return;
      var t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]);
      if (!t) return;
      if (self.swipeDir(t.clientX - self.tx, t.clientY - self.ty)) {
        if (e.cancelable) e.preventDefault();
      }
    };
    this._onTe = function (e) {
      if (!self.tOn) return;
      self.tOn = false;
      var t = e.changedTouches && e.changedTouches[0];
      if (!t) return;
      var dir = self.swipeDir(t.clientX - self.tx, t.clientY - self.ty);
      if (dir) self.input(dir);
    };
    this._onTc = function () { self.tOn = false; };
    el.addEventListener("touchstart", this._onTs, { passive: true });
    el.addEventListener("touchmove", this._onTm, { passive: false });
    el.addEventListener("touchend", this._onTe, { passive: true });
    el.addEventListener("touchcancel", this._onTc, { passive: true });
  };

  DigGame.prototype.swipeDir = function (dx, dy) {
    var ax = Math.abs(dx), ay = Math.abs(dy);
    if (ax < 18 && ay < 18) return null;
    if (ax >= ay * 1.2) return dx > 0 ? "right" : "left";
    if (ay >= ax * 1.2) return dy > 0 ? "down" : "up";
    return null;
  };

  DigGame.prototype.shout = function (text) {
    this.shoutText = text;
    this.shoutLife = 48;
    var h = this.hooks;
    if (h.onShout) h.onShout(text);
    if (h.shout) h.shout(text);
  };

  DigGame.prototype.input = function (name) {
    var d = DIRS[name];
    if (!d) return;
    if (this.needConfirm) {
      this.needConfirm = false;
      this.emit();
      this.paint();
    }
    if (!this.running || this.dead || this.win || this.paused || this.cleared) return;
    this.step(d[0], d[1]);
  };

  DigGame.prototype.pauseToggle = function () {
    if (this.needConfirm) this.needConfirm = false;
    if (!this.running || this.dead || this.cleared) return;
    this.paused = !this.paused;
    this.emit();
    this.paint();
  };

  DigGame.prototype.pause = function () {
    this.pauseToggle();
  };

  DigGame.prototype.beep = function (f, ms) {
    if (this.mute || !global.AudioContext) return;
    try {
      var ctx = this.ac || new AudioContext();
      this.ac = ctx;
      var o = ctx.createOscillator();
      var g = ctx.createGain();
      o.type = "square";
      o.frequency.value = f;
      g.gain.value = this.volume;
      o.connect(g); g.connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + (ms || 0.05));
    } catch (e) {}
  };

  DigGame.prototype.tune = function (notes) {
    var i, self = this;
    for (i = 0; i < notes.length; i++) {
      (function (f, t) {
        setTimeout(function () { self.beep(f, 0.09); }, t);
      })(notes[i][0], notes[i][1]);
    }
  };

  DigGame.prototype.buzz = function (ms) {
    try {
      if (!this.hapticOn) return;
      if (global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      if (global.navigator && global.navigator.vibrate) global.navigator.vibrate(ms);
    } catch (e) {}
  };

  DigGame.prototype.hapticToggle = function () {
    this.hapticOn = !this.hapticOn;
    this.emit();
  };

  DigGame.prototype.setVolume = function (n) {
    n = +n;
    if (!(n >= 0)) n = 0;
    if (n > 0.08) n = 0.08;
    this.volume = n;
  };

  DigGame.prototype.speck = function (tx, ty, col) {
    var i, cx = tx * TILE + 4, cy = ty * TILE + 4;
    for (i = 0; i < 8; i++) {
      this.parts.push({
        x: cx + rnd(5) - 2,
        y: cy + rnd(5) - 2,
        vx: (rnd(7) - 3) * 0.4,
        vy: (rnd(7) - 3) * 0.4 - 0.25,
        life: 8 + rnd(10),
        c: col || (rnd(2) ? "#c4a054" : "#8a5224")
      });
    }
  };

  DigGame.prototype.tickFx = function () {
    var i, p;
    for (i = this.parts.length - 1; i >= 0; i--) {
      p = this.parts[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life -= 1;
      if (p.life <= 0) this.parts.splice(i, 1);
    }
    if (this.flash > 0) this.flash -= 1;
    if (this.shoutLife > 0) this.shoutLife -= 1;
  };

  DigGame.prototype.placeExit = function () {
    var best = null, bestD = -1, x, y, t, d;
    for (y = 1; y < ROWS - 1; y++) {
      for (x = 1; x < COLS - 1; x++) {
        t = this.grid[y][x];
        if (t !== EMPTY && t !== DIRT) continue;
        if (x === this.px && y === this.py) continue;
        d = Math.abs(x - this.px) + Math.abs(y - this.py);
        if (d > bestD) {
          bestD = d;
          best = [x, y];
        }
      }
    }
    if (!best) best = [COLS - 2, ROWS - 2];
    if (best[0] === this.px && best[1] === this.py) {
      best = [COLS - 2, ROWS - 2];
    }
    this.grid[best[1]][best[0]] = EXIT;
    this.exitOn = true;
    this.shout("EXIT!");
  };
  DigGame.prototype.step = function (dx, dy) {
    var nx = this.px + dx;
    var ny = this.py + dy;
    var t = this.at(nx, ny);
    if (t === WALL || t === ROCK) {
      this.beep(90, 0.07);
      this.buzz(8);
      this.shout("CLUNK!");
      this.emit();
      this.paint();
      return;
    }
    this.px = nx;
    this.py = ny;
    if (t === DIRT) {
      this.grid[ny][nx] = EMPTY;
      this.score += 5 * this.lvl;
      this.speck(nx, ny);
      this.shout("DIG!");
      this.beep(660);
      this.buzz(12);
    } else if (t === GEM) {
      this.grid[ny][nx] = EMPTY;
      this.got++;
      this.gemsLeft = Math.max(0, this.gemsLeft - 1);
      this.needLeft = this.gemsLeft;
      this.score += 40 * this.lvl;
      this.speck(nx, ny, GEM_C);
      this.shout("GEM!");
      this.beep(880);
      this.buzz(16);
      if (this.gemsLeft <= 0 && !this.exitOn) this.placeExit();
    } else if (t === EXIT) {
      this.stageWin();
      return;
    }
    this.emit();
    this.paint();
  };

  DigGame.prototype.dropRock = function (x, y, nx, ny) {
    if (this.px === nx && this.py === ny) {
      this.crush();
      return false;
    }
    this.grid[y][x] = EMPTY;
    this.falling[y][x] = 0;
    this.grid[ny][nx] = ROCK;
    this.falling[ny][nx] = 1;
    return true;
  };

  DigGame.prototype.canSlip = function (x, y, dx) {
    var nx = x + dx, by = y + 1;
    if (this.at(nx, y) !== EMPTY) return false;
    if (this.at(nx, by) !== EMPTY) return false;
    if (this.px === nx && this.py === y) return false;
    return true;
  };

  DigGame.prototype.gravity = function () {
    var x, y, below, slipped;
    for (y = ROWS - 2; y >= 1; y--) {
      for (x = 1; x < COLS - 1; x++) {
        if (this.grid[y][x] !== ROCK) continue;
        if (this.px === x && this.py === y + 1) {
          this.crush();
          return;
        }
        below = this.at(x, y + 1);
        if (below === EMPTY) {
          if (!this.dropRock(x, y, x, y + 1)) return;
          continue;
        }
        slipped = false;
        if (this.lvl >= 3 && (below === ROCK || below === WALL)) {
          if (this.canSlip(x, y, -1)) {
            if (this.px === x - 1 && this.py === y + 1) {
              this.crush();
              return;
            }
            if (!this.dropRock(x, y, x - 1, y)) return;
            slipped = true;
          } else if (this.canSlip(x, y, 1)) {
            if (this.px === x + 1 && this.py === y + 1) {
              this.crush();
              return;
            }
            if (!this.dropRock(x, y, x + 1, y)) return;
            slipped = true;
          }
        }
        if (!slipped) this.falling[y][x] = 0;
      }
    }
  };

  DigGame.prototype.crush = function () {
    this.shout("CRUSHED!");
    this.lives -= 1;
    if (this.lives < 0) this.lives = 0;
    this.hp = this.lives;
    this.beep(110, 0.12);
    this.buzz(40);
    this.speck(this.px, this.py, ROCK_C);
    this.flash = 2;
    if (this.lives <= 0) {
      this.die();
      return;
    }
    this.px = this.sx;
    this.py = this.sy;
    this.emit();
    this.paint();
  };

  DigGame.prototype.stageWin = function () {
    this.win = true;
    this.flash = 3;
    this.score += 50 * this.lvl;
    this.shout("CLEAR!");
    this.tune([[523, 0], [659, 90], [784, 180]]);
    var self = this;
    if (this.lvl >= MAX_LVL) {
      this.tune([[523, 0], [659, 90], [784, 180], [1046, 280]]);
      setTimeout(function () {
        self.cleared = true;
        self.running = false;
        self.paused = false;
        self.win = true;
        self.shout("DUG!");
        self.emit();
        self.paint();
      }, 700);
      this.emit();
      this.paint();
      return;
    }
    this.emit();
    this.paint();
    setTimeout(function () {
      if (!self.running) return;
      self.reset(self.lvl + 1);
      self.win = false;
      self.flash = 3;
      self.emit();
      self.paint();
    }, 700);
  };

  DigGame.prototype.die = function () {
    this.lives = 0;
    this.hp = 0;
    this.dead = true;
    this.running = false;
    this.paused = false;
    this.emit();
    this.paint();
  };

  DigGame.prototype.emit = function () {
    this.hp = this.lives;
    this.needLeft = this.gemsLeft;
    if (this.hooks.onHud) this.hooks.onHud(this);
  };

  DigGame.prototype.centerText = function (str, y) {
    var c = this.c, w;
    w = c.measureText(str).width;
    c.fillText(str, (160 - w) / 2, y);
  };

  DigGame.prototype.drawRock = function (x, y) {
    var c = this.c;
    var gx = x * TILE, gy = y * TILE;
    c.fillStyle = ROCK_C;
    c.fillRect(gx + 1, gy + 1, 6, 6);
    c.fillStyle = ROCK_HI;
    c.fillRect(gx + 1, gy + 1, 6, 1);
    c.fillRect(gx + 1, gy + 1, 1, 6);
    c.fillStyle = ROCK_LO;
    c.fillRect(gx + 6, gy + 2, 1, 5);
    c.fillRect(gx + 2, gy + 6, 5, 1);
  };

  DigGame.prototype.drawGopher = function () {
    var c = this.c;
    var pal = THEMES[this.theme] || THEMES[0];
    var gx = this.px * TILE, gy = this.py * TILE;
    c.fillStyle = pal.player;
    c.fillRect(gx + 1, gy + 2, 6, 5);
    c.fillRect(gx + 2, gy + 1, 4, 2);
    c.fillStyle = "#070908";
    c.fillRect(gx + 2, gy + 3, 1, 1);
    c.fillRect(gx + 5, gy + 3, 1, 1);
    c.fillStyle = pal.pellet;
    c.fillRect(gx + 3, gy + 5, 2, 1);
  };

  DigGame.prototype.paint = function () {
    var c = this.c, x, y, i, blink, p, t;
    var pal = THEMES[this.theme] || THEMES[0];
    c.fillStyle = "#020302";
    c.fillRect(0, 0, 160, 144);
    blink = (Date.now() % 600) < 400;
    for (y = 0; y < ROWS; y++) {
      for (x = 0; x < COLS; x++) {
        t = this.grid[y][x];
        if (t === WALL) {
          c.fillStyle = pal.wall;
          c.fillRect(x * TILE, y * TILE, TILE, TILE);
          c.fillStyle = "#2a2014";
          c.fillRect(x * TILE, y * TILE + 3, TILE, 1);
        } else if (t === DIRT) {
          c.fillStyle = pal.dirt;
          c.fillRect(x * TILE, y * TILE, TILE, TILE);
          c.fillStyle = pal.dirt2;
          c.fillRect(x * TILE + 1, y * TILE + 1, 6, 6);
        } else if (t === GEM) {
          c.fillStyle = pal.dirt;
          c.fillRect(x * TILE, y * TILE, TILE, TILE);
          c.fillStyle = blink ? GEM_C : pal.pellet;
          c.fillRect(x * TILE + 3, y * TILE + 3, 2, 2);
          c.fillRect(x * TILE + 2, y * TILE + 4, 4, 1);
        } else if (t === EXIT) {
          c.fillStyle = pal.player;
          c.fillRect(x * TILE + 1, y * TILE + 1, 6, 6);
          c.fillStyle = "#070908";
          c.fillRect(x * TILE + 3, y * TILE + 3, 2, 3);
        } else if (t === ROCK) {
          this.drawRock(x, y);
        }
      }
    }
    this.drawGopher();
    for (i = 0; i < this.parts.length; i++) {
      p = this.parts[i];
      c.fillStyle = p.c;
      c.fillRect(p.x | 0, p.y | 0, 1, 1);
    }
    c.font = "8px monospace";
    if (this.shoutLife > 0 && this.shoutText) {
      c.fillStyle = /CRUSHED|CLUNK|BURIED|ROCK|Clunk/.test(this.shoutText) ? ERR : pal.pellet;
      this.centerText(this.shoutText, 20);
    }
    if (this.cleared) {
      c.fillStyle = pal.pellet;
      this.centerText("DUG!", 72);
      this.centerText(String(this.score), 86);
    } else if (this.dead) {
      c.fillStyle = ERR;
      this.centerText("BURIED", 68);
      this.centerText(String(this.score), 82);
    } else if (this.needConfirm) {
      c.fillStyle = "rgba(2,3,2,0.45)";
      c.fillRect(0, 0, 160, 144);
      c.fillStyle = pal.pellet;
      this.centerText("START?", 80);
    } else if (this.win) {
      c.fillStyle = pal.pellet;
      this.centerText("CLEAR!", 80);
    } else if (this.paused) {
      c.fillStyle = "rgba(2,3,2,0.45)";
      c.fillRect(0, 0, 160, 144);
      c.fillStyle = pal.pellet;
      this.centerText("PAUSE", 80);
    }
    if (this.flash > 0) {
      c.fillStyle = "#ffffff";
      c.fillRect(0, 0, 160, 144);
    }
  };

  DigGame.prototype.draw = function () {
    this.paint();
    this.ensureLoop();
  };

  DigGame.prototype.ensureLoop = function () {
    if (this.looping) return;
    this.looping = true;
    this.lastTs = 0;
    var self = this;
    this.raf = requestAnimationFrame(function (t) { self.loop(t); });
  };

  DigGame.prototype.loop = function (ts) {
    if (!this.looping) return;
    var dt = this.lastTs ? Math.min(48, ts - this.lastTs) : 16;
    this.lastTs = ts;
    if (this.running && !this.paused && !this.dead && !this.win && !this.cleared) {
      this.rockAcc += dt;
      while (this.rockAcc >= this.rockMs) {
        this.rockAcc -= this.rockMs;
        this.gravity();
        if (this.dead) break;
      }
    }
    this.tickFx();
    this.paint();
    if (!this.looping) return;
    var self = this;
    this.raf = requestAnimationFrame(function (t) { self.loop(t); });
  };

  DigGame.prototype.start = function () {
    if (this.running && !this.dead && !this.needConfirm && !this.cleared) {
      this.needConfirm = true;
      this.emit();
      this.paint();
      return;
    }
    this.needConfirm = false;
    this.score = 0;
    this.lives = 3;
    this.hp = 3;
    this.cleared = false;
    this.reset(1);
    this.dead = false;
    this.paused = false;
    this.running = true;
    this.ensureLoop();
    this.emit();
    this.paint();
  };

  DigGame.prototype.stop = function () {
    this.running = false;
    this.paused = false;
    this.looping = false;
    cancelAnimationFrame(this.raf);
  };

  global.DigGame = DigGame;
})(window);
