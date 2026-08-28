/* FETCH — 100-stage maze. One tap, one tile. Foxes, not sludge. */
(function (global) {
  "use strict";

  var COLS = 20, ROWS = 16, TILE = 8;
  var DIRS = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
  var DIRN = ["up", "down", "left", "right"];
  var THEMES = [
    { wall: "#0b330b", packet: "#b8ff9a", player: "#39ff14" },
    { wall: "#146614", packet: "#d4ffb0", player: "#5cff38" },
    { wall: "#1c2e14", packet: "#9aaa62", player: "#6a8a32" }
  ];
  var FOX = "#ff6a3d";
  var STAR = "#7ee8ff";
  var MAX_LVL = 100;

  function rnd(n) { return Math.floor(Math.random() * n); }

  function lcg(seed) {
    var s = (seed >>> 0) || 1;
    return function () {
      s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  function round1(n) {
    return Math.round(n * 10) / 10;
  }

  function mazeFor(lvl) {
    var rng = lcg(lvl * 9973 + 17);
    var walls = [], x, y, i;
    for (y = 0; y < ROWS; y++) {
      walls[y] = [];
      for (x = 0; x < COLS; x++) walls[y][x] = 1;
    }
    function inb(cx, cy) {
      return cx > 0 && cy > 0 && cx < COLS - 1 && cy < ROWS - 1;
    }
    var stack = [[1, 1]];
    walls[1][1] = 0;
    var carve = [[2, 0], [-2, 0], [0, 2], [0, -2]];
    while (stack.length) {
      var cur = stack[stack.length - 1];
      var opts = [];
      for (i = 0; i < 4; i++) {
        var nx = cur[0] + carve[i][0];
        var ny = cur[1] + carve[i][1];
        if (inb(nx, ny) && (nx % 2) === 1 && (ny % 2) === 1 && walls[ny][nx] === 1) {
          opts.push([nx, ny, carve[i]]);
        }
      }
      if (!opts.length) {
        stack.pop();
        continue;
      }
      var pick = opts[Math.floor(rng() * opts.length)];
      var mx = cur[0] + pick[2][0] / 2;
      var my = cur[1] + pick[2][1] / 2;
      walls[my][mx] = 0;
      walls[pick[1]][pick[0]] = 0;
      stack.push([pick[0], pick[1]]);
    }
    var punches = lvl >= 100 ? 1 : Math.max(2, 16 - Math.floor(lvl / 7));
    var tries = 0;
    while (punches > 0 && tries < 500) {
      tries++;
      x = 1 + Math.floor(rng() * (COLS - 2));
      y = 1 + Math.floor(rng() * (ROWS - 2));
      if (walls[y][x] !== 1) continue;
      var open = 0;
      if (walls[y][x - 1] === 0) open++;
      if (walls[y][x + 1] === 0) open++;
      if (walls[y - 1][x] === 0) open++;
      if (walls[y + 1][x] === 0) open++;
      if (open >= 2) {
        walls[y][x] = 0;
        punches--;
      }
    }
    return walls;
  }

  function FetchGame(canvas, hooks) {
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
    this.combo = false;
    this.tx = 0;
    this.ty = 0;
    this.tOn = false;
    this.maxLvl = MAX_LVL;
    this.champion = false;
    this.hp = 3;
    this.power = 0;
    this.leftMs = 50000;
    this.limitMs = 50000;
    this.foxMs = 520;
    this.foxAcc = 0;
    this.lastTs = 0;
    this.shoutText = "";
    this.shoutLife = 0;
    this.invulnMs = 0;
    this.musicOn = false;
    this.musicT = 0;
    this.musicI = 0;
    this.reset(1);
    this.bind();
    this.ensureLoop();
  }

  FetchGame.prototype.reset = function (lvl) {
    this.lvl = lvl || 1;
    if (this.lvl > MAX_LVL) this.lvl = MAX_LVL;
    this.theme = (this.lvl - 1) % 3;
    this.needConfirm = false;
    if (lvl === 1) {
      this.score = 0;
      this.hp = 3;
      this.champion = false;
    }
    this.lives = Math.ceil(this.hp);
    this.walls = mazeFor(this.lvl);
    this.sx = 1;
    this.sy = 1;
    var y, x, found = false;
    for (y = 1; y < ROWS - 1 && !found; y++) {
      for (x = 1; x < COLS - 1 && !found; x++) {
        if (this.walls[y][x] === 0) {
          this.sx = x;
          this.sy = y;
          found = true;
        }
      }
    }
    this.px = this.sx;
    this.py = this.sy;
    this.need = 4 + Math.min(8, 2 + Math.floor(this.lvl / 10));
    this.got = 0;
    this.dead = false;
    this.win = false;
    this.combo = false;
    this.power = 0;
    this.star = null;
    this.pellets = [];
    this.foxes = [];
    this.packets = this.pellets;
    this.sludge = this.foxes;
    this.limitMs = Math.max(18000, 50000 - (this.lvl - 1) * 250);
    if (this.lvl >= 100) this.limitMs = 18000;
    this.leftMs = this.limitMs;
    this.foxMs = 520 / (1 + 0.01 * (this.lvl - 1));
    this.foxAcc = 0;
    this.invulnMs = 0;
    var nFox = Math.min(8, 1 + Math.floor((this.lvl - 1) / 8));
    if (this.lvl >= 100) nFox = 8;
    var i, p;
    for (i = 0; i < this.need; i++) {
      p = this.empty();
      if (p) this.pellets.push(p);
    }
    this.need = this.pellets.length;
    this.needLeft = this.pellets.length;
    for (i = 0; i < nFox; i++) {
      p = this.empty(true);
      if (p && p.x === this.sx && p.y === this.sy) p = this.empty(true);
      if (p && !(p.x === this.sx && p.y === this.sy)) this.foxes.push({ x: p.x, y: p.y, d: rnd(4) });
    }
    p = this.empty();
    if (p && p.x === this.sx && p.y === this.sy) p = this.empty();
    if (p && !(p.x === this.sx && p.y === this.sy)) this.star = { x: p.x, y: p.y };
  };

  FetchGame.prototype.wallAt = function (x, y) {
    if (x < 0 || y < 0 || x >= COLS || y >= ROWS) return true;
    return this.walls[y][x] === 1;
  };

  FetchGame.prototype.empty = function (preferFar) {
    var x, y, n = 0, best = null, bestD = -1, d, ok;
    do {
      x = 1 + rnd(COLS - 2);
      y = 1 + rnd(ROWS - 2);
      n++;
      ok = !(x === this.sx && y === this.sy) && !this.occupied(x, y, true);
      if (!ok) continue;
      if (!preferFar) return { x: x, y: y };
      d = Math.abs(x - this.px) + Math.abs(y - this.py);
      if (d > bestD) {
        best = { x: x, y: y };
        bestD = d;
      }
    } while (n < 220);
    if (preferFar && best) return best;
    if ((x === this.sx && y === this.sy) || this.occupied(x, y, true)) return null;
    return { x: x, y: y };
  };

  FetchGame.prototype.occupied = function (x, y, includePlayer) {
    if (this.wallAt(x, y)) return true;
    if (includePlayer && x === this.px && y === this.py) return true;
    var i;
    for (i = 0; i < this.pellets.length; i++) {
      if (this.pellets[i].x === x && this.pellets[i].y === y) return true;
    }
    for (i = 0; i < this.foxes.length; i++) {
      if (this.foxes[i].x === x && this.foxes[i].y === y) return true;
    }
    if (this.star && this.star.x === x && this.star.y === y) return true;
    return false;
  };

  FetchGame.prototype.bind = function () {
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

  FetchGame.prototype.swipeDir = function (dx, dy) {
    var ax = Math.abs(dx), ay = Math.abs(dy);
    if (ax < 18 && ay < 18) return null;
    if (ax >= ay * 1.2) return dx > 0 ? "right" : "left";
    if (ay >= ax * 1.2) return dy > 0 ? "down" : "up";
    return null;
  };

  FetchGame.prototype.shout = function (text) {
    this.shoutText = text;
    this.shoutLife = 48;
    var h = this.hooks;
    if (h.onShout) h.onShout(text);
    if (h.shout) h.shout(text);
  };

  FetchGame.prototype.input = function (name) {
    var d = DIRS[name];
    if (!d) return;
    if (this.needConfirm) {
      this.needConfirm = false;
      this.emit();
      this.paint();
    }
    if (!this.running || this.dead || this.win || this.paused || this.champion) return;
    this.step(d[0], d[1]);
  };

  FetchGame.prototype.pauseToggle = function () {
    if (this.needConfirm) this.needConfirm = false;
    if (!this.running || this.dead || this.champion) return;
    this.paused = !this.paused;
    if (this.paused) this.musicStop();
    else this.musicMaybe();
    this.emit();
    this.paint();
  };

  FetchGame.prototype.pause = function () {
    this.pauseToggle();
  };

  FetchGame.prototype.beep = function (f, ms) {
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

  FetchGame.prototype.tune = function (notes) {
    var i, self = this;
    for (i = 0; i < notes.length; i++) {
      (function (f, t) {
        setTimeout(function () { self.beep(f, 0.09); }, t);
      })(notes[i][0], notes[i][1]);
    }
  };

  FetchGame.prototype.musicMaybe = function () {
    if (this.mute || !this.running || this.paused || this.dead) {
      this.musicStop();
      return;
    }
    this.musicOn = true;
  };

  FetchGame.prototype.musicStop = function () {
    this.musicOn = false;
  };

  FetchGame.prototype.musicTick = function (dt) {
    if (this.mute || !this.running || this.paused || this.dead || this.champion) {
      this.musicOn = false;
      return;
    }
    this.musicOn = true;
    this.musicT += dt;
    if (this.musicT < 180) return;
    this.musicT -= 180;
    var seq = [262, 330, 392, 330, 262, 392, 440, 392];
    var n = seq[this.musicI % seq.length];
    this.musicI += 1;
    this.beep(n, 0.08);
  };

  FetchGame.prototype.buzz = function (ms) {
    try {
      if (!this.hapticOn) return;
      if (global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      if (global.navigator && global.navigator.vibrate) global.navigator.vibrate(ms);
    } catch (e) {}
  };

  FetchGame.prototype.hapticToggle = function () {
    this.hapticOn = !this.hapticOn;
    this.emit();
  };

  FetchGame.prototype.setVolume = function (n) {
    n = +n;
    if (!(n >= 0)) n = 0;
    if (n > 0.08) n = 0.08;
    this.volume = n;
  };

  FetchGame.prototype.speck = function (tx, ty, col) {
    var i, cx = tx * TILE + 4, cy = ty * TILE + 4;
    for (i = 0; i < 8; i++) {
      this.parts.push({
        x: cx + rnd(5) - 2,
        y: cy + rnd(5) - 2,
        vx: (rnd(7) - 3) * 0.4,
        vy: (rnd(7) - 3) * 0.4 - 0.25,
        life: 8 + rnd(10),
        c: col || (rnd(2) ? "#b8ff9a" : "#39ff14")
      });
    }
  };

  FetchGame.prototype.tickFx = function () {
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

  FetchGame.prototype.foxAt = function (x, y) {
    var i;
    for (i = 0; i < this.foxes.length; i++) {
      if (this.foxes[i].x === x && this.foxes[i].y === y) return i;
    }
    return -1;
  };

  FetchGame.prototype.zapFox = function (i, defend) {
    if (i < 0) return;
    var f = this.foxes[i];
    this.speck(f.x, f.y, FOX);
    this.foxes.splice(i, 1);
    this.power = 0;
    if (defend) {
      this.shout("BLOCK!");
      this.beep(520);
      this.buzz(16);
    } else {
      this.score += 25 * this.lvl;
      this.shout("ZAP!");
      this.beep(980);
      this.buzz(18);
    }
  };

  FetchGame.prototype.step = function (dx, dy) {
    var nx = this.px + dx;
    var ny = this.py + dy;
    if (this.wallAt(nx, ny)) {
      this.beep(90, 0.07);
      this.buzz(8);
      this.shout("Clunk!!!");
      this.hp = round1(this.hp - 0.1);
      this.lives = Math.ceil(this.hp);
      if (this.hp <= 0) {
        this.die();
        return;
      }
      this.emit();
      this.paint();
      return;
    }
    var fi = this.foxAt(nx, ny);
    if (fi >= 0) {
      if (this.power) {
        this.zapFox(fi, false);
        this.px = nx;
        this.py = ny;
        this.afterMove();
        return;
      }
      if (this.invulnMs > 0) {
        this.px = nx;
        this.py = ny;
        this.afterMove();
        return;
      }
      this.ouch();
      return;
    }
    this.px = nx;
    this.py = ny;
    this.afterMove();
  };

  FetchGame.prototype.afterMove = function () {
    var i, grabbed = false;
    for (i = this.pellets.length - 1; i >= 0; i--) {
      if (this.pellets[i].x === this.px && this.pellets[i].y === this.py) {
        this.pellets.splice(i, 1);
        this.got++;
        this.score += 10 * this.lvl;
        grabbed = true;
        this.speck(this.px, this.py);
      }
    }
    if (grabbed) {
      if (this.combo) this.score += 1;
      this.combo = true;
      this.shout("Huzaaa!");
      this.beep(660);
      this.buzz(12);
    } else {
      this.combo = false;
    }
    if (this.star && this.star.x === this.px && this.star.y === this.py) {
      this.star = null;
      this.power = 1;
      this.shout("STAR!");
      this.beep(740);
      this.speck(this.px, this.py, STAR);
    }
    if (this.got >= this.need && this.need > 0) {
      this.stageWin();
      return;
    }
    this.emit();
    this.paint();
  };

  FetchGame.prototype.stageWin = function () {
    this.win = true;
    this.flash = 3;
    this.shout("VICTORY!");
    this.tune([[523, 0], [659, 90], [784, 180], [1046, 280]]);
    var self = this;
    if (this.lvl >= MAX_LVL) {
      this.tune([[523, 0], [659, 120], [784, 240], [1046, 360], [1318, 500]]);
      setTimeout(function () {
        self.champion = true;
        self.running = false;
        self.paused = false;
        self.musicStop();
        self.shout("GOPHER CHAMPION!");
        self.emit();
        self.paint();
      }, 800);
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

  FetchGame.prototype.moveFoxes = function () {
    var i, f, d, nx, ny, chase, opts, k, best, dist, nd;
    chase = this.lvl >= 40;
    for (i = 0; i < this.foxes.length; i++) {
      f = this.foxes[i];
      opts = [];
      for (k = 0; k < 4; k++) {
        d = DIRS[DIRN[k]];
        nx = f.x + d[0];
        ny = f.y + d[1];
        if (!this.wallAt(nx, ny) && this.foxAt(nx, ny) < 0) opts.push([nx, ny, k]);
      }
      if (opts.length) {
        if (chase || this.lvl >= 100) {
          best = opts[0];
          dist = Math.abs(best[0] - this.px) + Math.abs(best[1] - this.py);
          for (k = 1; k < opts.length; k++) {
            nd = Math.abs(opts[k][0] - this.px) + Math.abs(opts[k][1] - this.py);
            if (nd < dist || (nd === dist && rnd(2) === 0)) {
              dist = nd;
              best = opts[k];
            }
          }
          if (this.lvl < 100 && rnd(3) === 0) best = opts[rnd(opts.length)];
          f.x = best[0];
          f.y = best[1];
          f.d = best[2];
        } else {
          if (rnd(2) === 0) f.d = rnd(4);
          d = DIRS[DIRN[f.d]];
          nx = f.x + d[0];
          ny = f.y + d[1];
          if (!this.wallAt(nx, ny) && this.foxAt(nx, ny) < 0) {
            f.x = nx;
            f.y = ny;
          } else {
            f.d = rnd(4);
          }
        }
      }
      if (f.x === this.px && f.y === this.py) {
        if (this.power) {
          this.zapFox(i, true);
          i--;
          continue;
        }
        if (this.invulnMs > 0) continue;
        this.ouch();
        return;
      }
    }
  };

  FetchGame.prototype.ouch = function () {
    if (this.power) {
      this.zapFox(this.foxAt(this.px, this.py), true);
      this.emit();
      this.paint();
      return;
    }
    if (this.invulnMs > 0) return;
    this.shout("Ouchies!");
    this.hp = round1(this.hp - 1);
    this.lives = Math.ceil(this.hp);
    this.combo = false;
    this.beep(110, 0.12);
    this.buzz(40);
    if (this.hp <= 0) {
      this.die();
      return;
    }
    this.invulnMs = 900;
    this.px = this.sx;
    this.py = this.sy;
    this.emit();
    this.paint();
  };

  FetchGame.prototype.die = function () {
    this.hp = 0;
    this.lives = 0;
    this.dead = true;
    this.running = false;
    this.paused = false;
    this.musicStop();
    this.emit();
    this.paint();
  };

  FetchGame.prototype.timeOver = function () {
    this.shout("TIME OVER!");
    this.tune([[392, 0], [330, 120], [196, 240]]);
    this.die();
  };

  FetchGame.prototype.emit = function () {
    this.lives = Math.ceil(this.hp);
    this.needLeft = this.pellets.length;
    if (this.hooks.onHud) this.hooks.onHud(this);
  };

  FetchGame.prototype.centerText = function (str, y) {
    var c = this.c, w;
    w = c.measureText(str).width;
    c.fillText(str, (160 - w) / 2, y);
  };

  FetchGame.prototype.drawFox = function (f) {
    var c = this.c;
    var gx = f.x * TILE, gy = f.y * TILE;
    c.fillStyle = FOX;
    c.fillRect(gx + 1, gy + 2, 6, 5);
    c.fillRect(gx + 1, gy + 1, 2, 2);
    c.fillRect(gx + 5, gy + 1, 2, 2);
    c.fillStyle = "#070908";
    c.fillRect(gx + 2, gy + 4, 1, 1);
    c.fillRect(gx + 5, gy + 4, 1, 1);
  };

  FetchGame.prototype.paint = function () {
    var c = this.c, x, y, i, blink, p;
    var pal = THEMES[this.theme] || THEMES[0];
    c.fillStyle = "#020302";
    c.fillRect(0, 0, 160, 144);
    for (y = 0; y < ROWS; y++) {
      for (x = 0; x < COLS; x++) {
        if (this.walls[y][x]) {
          c.fillStyle = pal.wall;
          c.fillRect(x * TILE, y * TILE, TILE, TILE);
        }
      }
    }
    blink = (Date.now() % 600) < 400;
    if (blink) {
      c.fillStyle = pal.packet;
      for (i = 0; i < this.pellets.length; i++) {
        c.fillRect(this.pellets[i].x * TILE + 2, this.pellets[i].y * TILE + 2, 4, 4);
      }
      if (this.star) {
        c.fillStyle = STAR;
        x = this.star.x * TILE;
        y = this.star.y * TILE;
        c.fillRect(x + 3, y + 1, 2, 6);
        c.fillRect(x + 1, y + 3, 6, 2);
      }
    }
    for (i = 0; i < this.foxes.length; i++) this.drawFox(this.foxes[i]);
    var gx = this.px * TILE, gy = this.py * TILE;
    var flashP = this.invulnMs > 0 && (((this.invulnMs / 90) | 0) % 2 === 0);
    if (this.invulnMs <= 0 || flashP) {
      c.fillStyle = this.invulnMs > 0 ? "#ffffff" : pal.player;
      c.fillRect(gx + 1, gy + 2, 6, 5);
      c.fillRect(gx + 2, gy + 1, 4, 2);
      c.fillStyle = "#070908";
      c.fillRect(gx + 2, gy + 3, 1, 1);
      c.fillRect(gx + 5, gy + 3, 1, 1);
      if (this.power) {
        c.fillStyle = STAR;
        c.fillRect(gx + 3, gy + 6, 2, 1);
      }
    }
    for (i = 0; i < this.parts.length; i++) {
      p = this.parts[i];
      c.fillStyle = p.c;
      c.fillRect(p.x | 0, p.y | 0, 1, 1);
    }
    c.font = "8px monospace";
    if (this.shoutLife > 0 && this.shoutText) {
      c.fillStyle = /Ouchies|TIME OVER|Clunk/.test(this.shoutText) ? FOX : pal.packet;
      this.centerText(this.shoutText, 20);
    }
    if (this.champion) {
      c.fillStyle = pal.packet;
      this.centerText("GOPHER CHAMPION!", 72);
      this.centerText(String(this.score), 86);
    } else if (this.dead) {
      c.fillStyle = FOX;
      this.centerText(this.shoutText === "TIME OVER!" ? "TIME OVER!" : "404", 68);
      this.centerText(String(this.score), 82);
    } else if (this.needConfirm) {
      c.fillStyle = "rgba(2,3,2,0.45)";
      c.fillRect(0, 0, 160, 144);
      c.fillStyle = pal.packet;
      this.centerText("START?", 80);
    } else if (this.win) {
      c.fillStyle = pal.packet;
      this.centerText("VICTORY!", 80);
    } else if (this.paused) {
      c.fillStyle = "rgba(2,3,2,0.45)";
      c.fillRect(0, 0, 160, 144);
      c.fillStyle = pal.packet;
      this.centerText("PAUSE", 80);
    }
    if (this.flash > 0) {
      c.fillStyle = "#ffffff";
      c.fillRect(0, 0, 160, 144);
    }
  };

  FetchGame.prototype.draw = function () {
    this.paint();
    this.ensureLoop();
  };

  FetchGame.prototype.ensureLoop = function () {
    if (this.looping) return;
    this.looping = true;
    this.lastTs = 0;
    var self = this;
    this.raf = requestAnimationFrame(function (t) { self.loop(t); });
  };

  FetchGame.prototype.loop = function (ts) {
    if (!this.looping) return;
    var dt = this.lastTs ? Math.min(48, ts - this.lastTs) : 16;
    this.lastTs = ts;
    if (this.mute || !this.running || this.paused) this.musicOn = false;
    else if (!this.dead && !this.champion) this.musicOn = true;
    if (this.running && !this.paused && !this.dead && !this.win && !this.champion) {
      if (this.invulnMs > 0) {
        this.invulnMs -= dt;
        if (this.invulnMs < 0) this.invulnMs = 0;
      }
      this.leftMs -= dt;
      if (this.leftMs <= 0) {
        this.leftMs = 0;
        this.timeOver();
      } else {
        this.foxAcc += dt;
        while (this.foxAcc >= this.foxMs) {
          this.foxAcc -= this.foxMs;
          this.moveFoxes();
          if (this.dead) break;
        }
      }
      this.musicTick(dt);
      var sec = Math.ceil(this.leftMs / 1000);
      if (sec !== this._hudSec) {
        this._hudSec = sec;
        this.emit();
      }
    }
    this.tickFx();
    this.paint();
    if (!this.looping) return;
    var self = this;
    this.raf = requestAnimationFrame(function (t) { self.loop(t); });
  };

  FetchGame.prototype.start = function () {
    if (this.running && !this.dead && !this.needConfirm && !this.champion) {
      this.needConfirm = true;
      this.emit();
      this.paint();
      return;
    }
    this.needConfirm = false;
    this.score = 0;
    this.hp = 3;
    this.champion = false;
    this.reset(1);
    this.dead = false;
    this.paused = false;
    this.running = true;
    this.ensureLoop();
    this.musicMaybe();
    this.emit();
    this.paint();
  };

  FetchGame.prototype.stop = function () {
    this.running = false;
    this.paused = false;
    this.looping = false;
    this.musicStop();
    cancelAnimationFrame(this.raf);
  };

  global.FetchGame = FetchGame;
})(window);
