/* FETCH — 8-bit burrow. One tap, one tile. */
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

  function rnd(n) { return Math.floor(Math.random() * n); }

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
    this.reset(1);
    this.bind();
    this.ensureLoop();
  }

  FetchGame.prototype.reset = function (lvl) {
    this.lvl = lvl || 1;
    this.theme = (this.lvl - 1) % 3;
    this.needConfirm = false;
    if (lvl === 1) { this.score = 0; this.lives = 3; }
    this.px = 2; this.py = 8;
    this.need = 4 + this.lvl;
    this.got = 0;
    this.dead = false;
    this.win = false;
    this.combo = false;
    this.packets = [];
    this.sludge = [];
    var i, p;
    for (i = 0; i < this.need; i++) {
      p = this.empty();
      if (p) this.packets.push(p);
    }
    for (i = 0; i < this.lvl; i++) {
      p = this.empty();
      if (p) this.sludge.push({ x: p.x, y: p.y, d: rnd(4) });
    }
  };

  FetchGame.prototype.empty = function () {
    var x, y, n = 0;
    do {
      x = 1 + rnd(COLS - 2);
      y = 1 + rnd(ROWS - 2);
      n++;
    } while (n < 120 && this.blocked(x, y, true));
    if (this.blocked(x, y, true)) return null;
    return { x: x, y: y };
  };

  FetchGame.prototype.blocked = function (x, y, includePlayer) {
    if (x <= 0 || y <= 0 || x >= COLS - 1 || y >= ROWS - 1) return true;
    if (includePlayer && x === this.px && y === this.py) return true;
    var i;
    for (i = 0; i < this.packets.length; i++) {
      if (this.packets[i].x === x && this.packets[i].y === y) return true;
    }
    for (i = 0; i < this.sludge.length; i++) {
      if (this.sludge[i].x === x && this.sludge[i].y === y) return true;
    }
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

  FetchGame.prototype.input = function (name) {
    var d = DIRS[name];
    if (!d) return;
    if (this.needConfirm) {
      this.needConfirm = false;
      this.emit();
      this.paint();
    }
    if (!this.running || this.dead || this.win || this.paused) return;
    this.step(d[0], d[1]);
  };

  FetchGame.prototype.pauseToggle = function () {
    if (this.needConfirm) {
      this.needConfirm = false;
    }
    if (!this.running || this.dead) return;
    this.paused = !this.paused;
    this.emit();
    this.paint();
  };

  FetchGame.prototype.pause = function () {
    this.pauseToggle();
  };

  FetchGame.prototype.beep = function (f) {
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
      o.stop(ctx.currentTime + 0.05);
    } catch (e) {}
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

  FetchGame.prototype.speck = function (tx, ty) {
    var i, cx = tx * TILE + 4, cy = ty * TILE + 4;
    for (i = 0; i < 8; i++) {
      this.parts.push({
        x: cx + rnd(5) - 2,
        y: cy + rnd(5) - 2,
        vx: (rnd(7) - 3) * 0.4,
        vy: (rnd(7) - 3) * 0.4 - 0.25,
        life: 8 + rnd(10),
        c: rnd(2) ? "#b8ff9a" : "#39ff14"
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
  };

  FetchGame.prototype.step = function (dx, dy) {
    var nx = this.px + dx;
    var ny = this.py + dy;
    if (nx <= 0 || ny <= 0 || nx >= COLS - 1 || ny >= ROWS - 1) {
      this.beep(90);
      return;
    }
    var i, grabbed = false;
    for (i = 0; i < this.sludge.length; i++) {
      if (this.sludge[i].x === nx && this.sludge[i].y === ny) {
        this.hit();
        return;
      }
    }
    this.px = nx;
    this.py = ny;
    for (i = this.packets.length - 1; i >= 0; i--) {
      if (this.packets[i].x === this.px && this.packets[i].y === this.py) {
        this.packets.splice(i, 1);
        this.got++;
        this.score += 10 * this.lvl;
        grabbed = true;
        this.speck(this.px, this.py);
      }
    }
    if (grabbed) {
      if (this.combo) this.score += 1;
      this.combo = true;
      this.beep(660);
      this.buzz(12);
    } else {
      this.combo = false;
    }
    if (this.got >= this.need) {
      this.win = true;
      this.flash = 3;
      this.beep(880);
      var self = this;
      setTimeout(function () {
        if (!self.running) return;
        self.reset(self.lvl + 1);
        self.win = false;
        self.flash = 3;
        self.emit();
        self.paint();
      }, 650);
      this.emit();
      this.paint();
      return;
    }
    this.moveSludge();
    this.emit();
    this.paint();
  };

  FetchGame.prototype.moveSludge = function () {
    var i, s, dd, sx, sy;
    for (i = 0; i < this.sludge.length; i++) {
      s = this.sludge[i];
      if (rnd(2) === 0) s.d = rnd(4);
      dd = DIRS[DIRN[s.d]];
      sx = s.x + dd[0];
      sy = s.y + dd[1];
      if (sx > 0 && sy > 0 && sx < COLS - 1 && sy < ROWS - 1) {
        s.x = sx;
        s.y = sy;
      } else {
        s.d = rnd(4);
      }
      if (s.x === this.px && s.y === this.py) {
        this.hit();
        return;
      }
    }
  };

  FetchGame.prototype.hit = function () {
    this.lives -= 1;
    this.combo = false;
    this.beep(110);
    this.buzz(40);
    if (this.lives <= 0) {
      this.dead = true;
      this.running = false;
      this.paused = false;
    } else {
      this.px = 2;
      this.py = 8;
    }
    this.emit();
    this.paint();
  };

  FetchGame.prototype.emit = function () {
    if (this.hooks.onHud) this.hooks.onHud(this);
  };

  FetchGame.prototype.centerText = function (str, y) {
    var c = this.c, w;
    w = c.measureText(str).width;
    c.fillText(str, (160 - w) / 2, y);
  };

  FetchGame.prototype.paint = function () {
    var c = this.c, x, y, i, blink, p;
    var pal = THEMES[this.theme] || THEMES[0];
    c.fillStyle = "#020302";
    c.fillRect(0, 0, 160, 144);
    c.fillStyle = pal.wall;
    for (x = 0; x < COLS; x++) {
      c.fillRect(x * TILE, 0, TILE, TILE);
      c.fillRect(x * TILE, (ROWS - 1) * TILE, TILE, TILE);
    }
    for (y = 0; y < ROWS; y++) {
      c.fillRect(0, y * TILE, TILE, TILE);
      c.fillRect((COLS - 1) * TILE, y * TILE, TILE, TILE);
    }
    c.fillStyle = "#143f14";
    for (i = 0; i < 18; i++) {
      c.fillRect((1 + (i * 3) % 18) * TILE + 3, (1 + (i * 5) % 14) * TILE + 3, 2, 2);
    }
    blink = (Date.now() % 600) < 400;
    if (blink) {
      c.fillStyle = pal.packet;
      for (i = 0; i < this.packets.length; i++) {
        c.fillRect(this.packets[i].x * TILE + 2, this.packets[i].y * TILE + 2, 4, 4);
      }
    }
    c.fillStyle = "#ff6a3d";
    for (i = 0; i < this.sludge.length; i++) {
      c.fillRect(this.sludge[i].x * TILE + 1, this.sludge[i].y * TILE + 1, 6, 6);
    }
    var gx = this.px * TILE, gy = this.py * TILE;
    c.fillStyle = pal.player;
    c.fillRect(gx + 1, gy + 2, 6, 5);
    c.fillRect(gx + 2, gy + 1, 4, 2);
    c.fillStyle = "#070908";
    c.fillRect(gx + 2, gy + 3, 1, 1);
    c.fillRect(gx + 5, gy + 3, 1, 1);
    for (i = 0; i < this.parts.length; i++) {
      p = this.parts[i];
      c.fillStyle = p.c;
      c.fillRect(p.x | 0, p.y | 0, 1, 1);
    }
    c.font = "8px monospace";
    if (this.dead) {
      c.fillStyle = "#ff6a3d";
      this.centerText("404", 68);
      this.centerText(String(this.score), 82);
    } else if (this.needConfirm) {
      c.fillStyle = "rgba(2,3,2,0.45)";
      c.fillRect(0, 0, 160, 144);
      c.fillStyle = pal.packet;
      this.centerText("START?", 80);
    } else if (this.win) {
      c.fillStyle = pal.packet;
      this.centerText("FETCHED", 80);
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
    var self = this;
    this.raf = requestAnimationFrame(function () { self.loop(); });
  };

  FetchGame.prototype.loop = function () {
    if (!this.looping) return;
    this.tickFx();
    this.paint();
    if (!this.looping) return;
    var self = this;
    this.raf = requestAnimationFrame(function () { self.loop(); });
  };

  FetchGame.prototype.start = function () {
    if (this.running && !this.dead && !this.needConfirm) {
      this.needConfirm = true;
      this.emit();
      this.paint();
      return;
    }
    this.needConfirm = false;
    this.score = 0;
    this.reset(1);
    this.dead = false;
    this.paused = false;
    this.running = true;
    this.ensureLoop();
    this.emit();
    this.paint();
  };

  FetchGame.prototype.stop = function () {
    this.running = false;
    this.paused = false;
    this.looping = false;
    cancelAnimationFrame(this.raf);
  };

  global.FetchGame = FetchGame;
})(window);
