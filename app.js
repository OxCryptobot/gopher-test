(function () {
  "use strict";

  var EMAIL_RE = /^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$/i;
  var USERS_KEY = "gopher_users_v1";
  var SESS_KEY = "gopher_session_v1";
  var BEST_KEY = "gopher_fetch_best_v1";
  var CHAMP_KEY = "gopher_eternal_v1";
  var TUT_KEY = "gopher_tut_v1";
  var LANG_KEY = "gopher_lang_v1";
  var HC_KEY = "gopher_hc_v1";
  var SPOT_KEY = "gopher_last_spot_v1";
  var VOL_KEY = "gopher_vol_v1";
  var QUEST_KEY = "gopher_quest_v1";
  var LOG_KEY = "gopher_log_v1";
  var TRACK_KEY = "gopher_track_v1";
  var KIND_KEY = "gopher_kind_v1";

  /* Scalable Gopher directory. Add an item in hole.json; this is the fallback. */
  var HOLES = {
    "/": {
      title: "Directory of GOPHER AI",
      items: [
        { n: "1", type: "1", name: "Docs/", path: "/docs", hint: "about, how, caps, privacy" },
        { n: "5", type: "1", name: "FETCH/", path: "/fetch", hint: "PLAY NOW — 8-bit burrow" },
        { n: "6", type: "7", name: "Waitlist", path: "/waitlist", hint: "get in" },
        { n: "8", type: "1", name: "Games/", path: "/games", hint: "more holes" },
        { n: "9", type: "1", name: "User/", path: "/user", hint: "enter your hole" }
      ]
    },
    "/about": {
      title: "1 About/",
      html:
        "<p class='info'>GOPHER AI is a standalone phone assistant you pay for. You talk to a number. It turns the talk into an order, fetches, and brings the answer back to the same thread.</p>" +
        "<p class='info'>The name is the point. Old Gopher was a menu, a selector, a fetch. No infinite scroll. No chat sludge. A modern prompt sits on that contract.</p>"
    },
    "/how": {
      title: "2 How it works/",
      html:
        "<ol class='steps'>" +
        "<li>You send an order — voice, SMS, or the prompt.</li>" +
        "<li>GOPHER AI files it as a selector: fetch, watch, draft, remind.</li>" +
        "<li>Plugins you connect do the work.</li>" +
        "<li>The result comes back to the same conversation.</li>" +
        "</ol>"
    },
    "/caps": {
      title: "3 Capabilities/",
      html:
        "<ul class='caps'>" +
        "<li><span class='itype'>0</span> Voice and SMS in. A reply out.</li>" +
        "<li><span class='itype'>0</span> Orders, not chat.</li>" +
        "<li><span class='itype'>0</span> Numbered menus + a modern ask box.</li>" +
        "<li><span class='itype'>0</span> FETCH, an original 8-bit hole.</li>" +
        "<li><span class='itype'>0</span> A log of what was asked and what came back.</li>" +
        "</ul>" +
        "<p class='info dim'>Not a general chatbot. Not a free public menu.</p>"
    },
    "/privacy": {
      title: "4 Privacy",
      html: "<p class='info'>We keep your waitlist email now; later, your number and order logs to do the job. Login on this page stays on this device. We don’t sell any of it.</p>"
    }
  };

  var ALIAS = {
    about: "/about", how: "/how", caps: "/caps", capabilities: "/caps",
    privacy: "/privacy", fetch: "/fetch", game: "/fetch", play: "/fetch",
    user: "/user", login: "/user", waitlist: "/waitlist", home: "/", menu: "/",
    es: "/es"
  };

  var $ = function (id) { return document.getElementById(id); };
  var dirEl = $("dir"), viewEl = $("view"), authEl = $("auth"), gameEl = $("game"), digEl = $("dig");
  var heroEl = $("hero"), askEl = $("ask");
  var game = null;
  var dig = null;
  var scoreSent = false;
  var shoutTimer = 0;
  var deferredInstall = null;
  var questBound = false;

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pathNow() {
    var h = (location.hash || "#/").replace(/^#/, "");
    if (!h.startsWith("/")) h = "/" + h;
    if (h.length > 1 && h.endsWith("/")) h = h.slice(0, -1);
    return h || "/";
  }

  function go(path) {
    if (!path.startsWith("/")) path = "/" + path;
    if (location.hash !== "#" + path) location.hash = path;
    else render();
  }

  function isStaging() {
    var path = location.pathname || "";
    var q = location.search || "";
    return path.indexOf("/gopher-test") === 0 || q.indexOf("env=test") !== -1;
  }

  function paintStaging() {
    var el = $("stage-ribbon");
    var on = isStaging();
    var robots;
    document.body.classList.toggle("staging", on);
    robots = document.querySelector('meta[name="robots"]');
    if (on) {
      if (!robots) {
        robots = document.createElement("meta");
        robots.setAttribute("name", "robots");
        document.head.appendChild(robots);
      }
      robots.setAttribute("content", "noindex,nofollow");
    } else if (robots && (robots.getAttribute("content") || "") === "noindex,nofollow") {
      robots.parentNode.removeChild(robots);
    }
    if (!on) {
      if (el) el.hidden = true;
      return;
    }
    if (!el) {
      el = document.createElement("div");
      el.id = "stage-ribbon";
      el.textContent = "TEST HOLE · not production";
      el.style.position = "fixed";
      el.style.top = "0";
      el.style.left = "0";
      el.style.right = "0";
      el.style.zIndex = "200";
      document.body.insertBefore(el, document.body.firstChild);
    } else {
      el.hidden = false;
      el.textContent = "TEST HOLE · not production";
    }
  }

  function shareScore() {
    var n = (game && typeof game.score === "number") ? game.score : bestScore(whoName());
    var msg = "FETCH score " + n + " on GOPHER AI";
    if (navigator.share) {
      navigator.share({ text: msg }).catch(function () {});
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(msg).catch(function () {});
      return;
    }
    try {
      var ta = document.createElement("textarea");
      ta.value = msg;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (err) {}
  }

  function setStatus(el, kind, text) {
    if (!el) return;
    el.className = "status-line" + (kind ? " " + kind : "");
    el.textContent = text;
  }

  function bootLang() {
    var saved = "";
    try { saved = localStorage.getItem(LANG_KEY) || ""; } catch (e) { saved = ""; }
    if (saved === "es" || saved === "en") document.documentElement.lang = saved;
  }
  var I18N = {
    en: {
      footer: "menus · selectors · fetch",
      fetchInfo: "Maze of 100 stages. One tap, one tile. Eat pellets (Huzaaa!). Walls Clunk!!!. Orange foxes Ouchies!. Clock runs. Stage 100 is nearly impossible.",
      digInfo: "Second burrow. One tap, one tile. Dig dirt. Rocks fall. 8 stages. FETCH stays the 100-stage maze.",
      fetchStatus: "press START. one tap, one tile. eat pellets. dodge orange foxes. beat the clock.",
      digStatus: "press START. dig dirt. rocks fall.",
      promptInfo: "Type a selector, a path, or an order. Same hole, either way.",
      promptLabel: "select or ask:",
      emailLabel: "email:",
      keysHint: "keys: <kbd>/</kbd> prompt · <kbd>1</kbd>–<kbd>9</kbd> menu · <kbd>?</kbd> help · <kbd>esc</kbd> home",
      helpTitle: "keys",
      help5: "FETCH",
      helpPrompt: "prompt",
      helpLogin: "login",
      helpArrows: "arrows",
      helpPause: "pause",
      helpSounds: "Huzaaa / Clunk / Ouchies",
      helpStar: "wall −0.1 hp · star ZAP/BLOCK",
      helpKey: "FETCH key",
      helpEsc: "home",
      keyTitle: "FETCH key",
      keyTap: "one tap, one tile",
      keyPellet: "pellet · Huzaaa!",
      keyWall: "wall · Clunk!!! · −0.1 hp",
      keyFox: "fox · Ouchies! · −1 hp",
      keyStar: "star · one per stage · ZAP a fox or BLOCK a hit",
      keyClock: "clock · TIME OVER!",
      keyClear: "stage clear · VICTORY!",
      keyChamp: "all 100 · trophy · Eternal GOPHER CHAMPIONS",
      questTitle: "first orders",
      questPlay: "play FETCH",
      questFetch: "fetch a ticker",
      questWait: "join waitlist",
      questDone: "quest done.",
      questNext: "next: ",
      fetchPaused: "paused. P or PAUSE to dig.",
      fetchPlay: "fetch pellets. dodge foxes. KEY for the map.",
      fetchDead: "404 hole. START to dig again.",
      fetchWin: "fetched. next hole…",
      digPlay: "dig dirt. rocks fall.",
      digDead: "buried. START to dig again.",
      digWin: "dug through.",
      digMissing: "DIG engine not on this hole yet."
    },
    es: {
      footer: "menús · selectores · fetch",
      fetchInfo: "Laberinto de 100 etapas. Un toque, una losa. Pellets Huzaaa!. Paredes Clunk!!!. Foxes naranjas Ouchies!. El reloj corre. La 100 es casi imposible.",
      digInfo: "Segunda madriguera. Un toque, una losa. Cava. Las rocas caen. 8 etapas. FETCH sigue el laberinto de 100.",
      fetchStatus: "pulsa START. un toque, una losa. pellets. foxes naranjas. el reloj.",
      digStatus: "pulsa START. cava tierra. las rocas caen.",
      promptInfo: "Selector, ruta u orden. El mismo hueco.",
      promptLabel: "elige o pregunta:",
      emailLabel: "email:",
      keysHint: "teclas: <kbd>/</kbd> prompt · <kbd>1</kbd>–<kbd>9</kbd> menú · <kbd>?</kbd> ayuda · <kbd>esc</kbd> inicio",
      helpTitle: "teclas",
      help5: "FETCH",
      helpPrompt: "prompt",
      helpLogin: "login",
      helpArrows: "flechas",
      helpPause: "pause",
      helpSounds: "Huzaaa / Clunk / Ouchies",
      helpStar: "pared −0.1 hp · estrella ZAP/BLOCK",
      helpKey: "FETCH key",
      helpEsc: "inicio",
      keyTitle: "FETCH key",
      keyTap: "un toque, una losa",
      keyPellet: "pellet · Huzaaa!",
      keyWall: "pared · Clunk!!! · −0.1 hp",
      keyFox: "fox · Ouchies! · −1 hp",
      keyStar: "estrella · una por etapa · ZAP a fox o BLOCK un golpe",
      keyClock: "reloj · TIME OVER!",
      keyClear: "etapa clara · VICTORY!",
      keyChamp: "las 100 · copa · Eternal GOPHER CHAMPIONS",
      questTitle: "primeras órdenes",
      questPlay: "juega FETCH",
      questFetch: "fetch un ticker",
      questWait: "entra a la lista",
      questDone: "misión hecha.",
      questNext: "sigue: ",
      fetchPaused: "pausa. P o PAUSE para cavar.",
      fetchPlay: "pellets. foxes. KEY para el mapa.",
      fetchDead: "404 hueco. START para cavar otra vez.",
      fetchWin: "fetched. siguiente hueco…",
      digPlay: "cava tierra. las rocas caen.",
      digDead: "enterrado. START para cavar otra vez.",
      digWin: "cavado.",
      digMissing: "DIG aún no está en este hueco."
    }
  };
  function t(key) {
    var lang = document.documentElement.lang === "es" ? "es" : "en";
    var pack = I18N[lang] || I18N.en;
    if (pack[key] != null) return pack[key];
    if (I18N.en[key] != null) return I18N.en[key];
    return key;
  }
  function applyLang(code) {
    var lang = code === "es" ? "es" : "en";
    var pack = I18N[lang] || I18N.en;
    var nodes, i, el, key, gs, ds;
    document.documentElement.lang = lang;
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) {}
    nodes = document.querySelectorAll("[data-i18n]");
    for (i = 0; i < nodes.length; i++) {
      el = nodes[i];
      key = el.getAttribute("data-i18n");
      if (key && pack[key] != null) el.textContent = pack[key];
    }
    nodes = document.querySelectorAll("[data-i18n-html]");
    for (i = 0; i < nodes.length; i++) {
      el = nodes[i];
      key = el.getAttribute("data-i18n-html");
      if (key && pack[key] != null) el.innerHTML = pack[key];
    }
    gs = $("g-status");
    if (gs) {
      if (game && game.dead) gs.textContent = pack.fetchDead;
      else if (game && game.win) gs.textContent = pack.fetchWin;
      else if (game && game.running && game.paused) gs.textContent = pack.fetchPaused;
      else if (game && game.running) gs.textContent = pack.fetchPlay;
      else gs.textContent = pack.fetchStatus;
    }
    ds = $("d-status");
    if (ds) {
      if (dig && dig.dead) ds.textContent = pack.digDead;
      else if (dig && dig.win) ds.textContent = pack.digWin;
      else if (dig && dig.running) ds.textContent = pack.digPlay;
      else ds.textContent = pack.digStatus;
    }
    questPaint();
  }

  function bootHc() {
    var v = "";
    try { v = localStorage.getItem(HC_KEY) || ""; } catch (e) { v = ""; }
    document.documentElement.classList.toggle("high-contrast", v === "1");
  }
  function applyHc(on) {
    document.documentElement.classList.toggle("high-contrast", !!on);
    try { localStorage.setItem(HC_KEY, on ? "1" : "0"); } catch (e) {}
  }

  function readVol() {
    try {
      var raw = localStorage.getItem(VOL_KEY);
      if (raw == null || raw === "") return null;
      var n = +raw;
      return (n >= 0) ? n : null;
    } catch (e) { return null; }
  }
  function writeVol(n) {
    try { localStorage.setItem(VOL_KEY, String(n)); } catch (e) {}
  }
  function syncVolSlider() {
    var el = $("g-vol");
    var n = readVol();
    var s;
    if (!el || n == null) return;
    s = Math.round(n / 0.01);
    if (s < 0) s = 0;
    if (s > 8) s = 8;
    el.value = String(s);
  }
  function applySavedVol() {
    var n = readVol();
    if (n == null) return;
    if (game && typeof game.setVolume === "function") game.setVolume(n);
  }
  function applyVolFromSlider(el) {
    var n;
    if (!el) return;
    if (!game) bootGame();
    n = (+el.value) * 0.01;
    if (game && typeof game.setVolume === "function") game.setVolume(n);
    writeVol(n);
  }

  function tutorialFocusables() {
    var tut = $("tutorial");
    if (!tut || tut.hidden) return [];
    var card = tut.querySelector(".tutorial-card");
    if (!card) return [];
    var nodes = card.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    );
    var out = [], i, el;
    for (i = 0; i < nodes.length; i++) {
      el = nodes[i];
      if (el.hidden) continue;
      out.push(el);
    }
    return out;
  }
  function trapTutorialTab(e) {
    var list = tutorialFocusables();
    var i;
    e.preventDefault();
    if (!list.length) return;
    i = list.indexOf(document.activeElement);
    if (e.shiftKey) i = i <= 0 ? list.length - 1 : i - 1;
    else i = (i < 0 || i >= list.length - 1) ? 0 : i + 1;
    list[i].focus();
  }

  function session() {
    try { return JSON.parse(sessionStorage.getItem(SESS_KEY) || "null"); }
    catch (e) { return null; }
  }
  function setSession(name) {
    if (!name) sessionStorage.removeItem(SESS_KEY);
    else sessionStorage.setItem(SESS_KEY, JSON.stringify({ name: name, at: Date.now() }));
    paintWho();
  }
  function paintWho() {
    var s = session();
    $("who").textContent = s && s.name ? s.name : "guest";
  }

  function users() {
    try { return JSON.parse(localStorage.getItem(USERS_KEY) || "{}"); }
    catch (e) { return {}; }
  }
  function saveUsers(u) { localStorage.setItem(USERS_KEY, JSON.stringify(u)); }

  function bufToB64(buf) {
    var b = new Uint8Array(buf), s = "", i;
    for (i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
    return btoa(s);
  }
  function b64ToBuf(s) {
    var raw = atob(s), u = new Uint8Array(raw.length), i;
    for (i = 0; i < raw.length; i++) u[i] = raw.charCodeAt(i);
    return u;
  }

  async function hashPass(pass, saltB64) {
    var enc = new TextEncoder();
    var salt = saltB64 ? b64ToBuf(saltB64) : crypto.getRandomValues(new Uint8Array(16));
    var key = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveBits"]);
    var bits = await crypto.subtle.deriveBits(
      { name: "PBKDF2", salt: salt, iterations: 120000, hash: "SHA-256" },
      key,
      256
    );
    return { hash: bufToB64(bits), salt: saltB64 || bufToB64(salt) };
  }

  function bestScore(name) {
    try {
      var all = JSON.parse(localStorage.getItem(BEST_KEY) || "{}");
      return all[name || "guest"] || 0;
    } catch (e) { return 0; }
  }
  function saveBest(name, n) {
    var all = {};
    try { all = JSON.parse(localStorage.getItem(BEST_KEY) || "{}"); } catch (e) {}
    var k = name || "guest";
    all[k] = Math.max(n, all[k] || 0);
    localStorage.setItem(BEST_KEY, JSON.stringify(all));
    return all[k];
  }

  function whoName() {
    var s = session();
    return (s && s.name) ? s.name : "guest";
  }

  function rememberChampion(name) {
    var list = [], n = (name || "guest").toLowerCase();
    try { list = JSON.parse(localStorage.getItem(CHAMP_KEY) || "[]"); } catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    if (list.indexOf(n) < 0) {
      list.push(n);
      try { localStorage.setItem(CHAMP_KEY, JSON.stringify(list)); } catch (e2) {}
    }
    return list;
  }

  function postChampion(name, score) {
    rememberChampion(name);
    fetch("/api/champions", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || "guest", score: score || 0 })
    }).catch(function () {});
  }

  function showTrophy(name) {
    var el = $("g-trophy");
    var who = $("trophy-name");
    if (who) who.textContent = name || "guest";
    if (el) el.hidden = false;
  }

  function hideTrophy() {
    var el = $("g-trophy");
    if (el) el.hidden = true;
  }

  function toggleKeyCard(force) {
    var el = $("g-keycard");
    if (!el) return;
    if (force === true) el.hidden = false;
    else if (force === false) el.hidden = true;
    else el.hidden = !el.hidden;
  }

  function postScore(name, score) {
    var body = {
      name: name || "guest",
      score: score || 0,
      stage: (game && game.lvl) || 0
    };
    if (game && game.champion) body.champion = true;
    fetch("/api/score", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).catch(function () {});
  }

  function materializeChildren(holes) {
    Object.keys(holes).forEach(function (p) {
      var items = (holes[p] && holes[p].items) || [];
      items.forEach(function (it) {
        if (it.children && it.children.length && !holes[it.path]) {
          holes[it.path] = { title: it.name, items: it.children };
        }
      });
    });
  }

  function applyCatalog(data) {
    if (!data) return;
    if (data.holes) HOLES = data.holes;
    else if (data["/"] || data.items) HOLES = data.holes || data;
    if (data.alias) ALIAS = data.alias;
    if (!ALIAS.es) ALIAS.es = "/es";
    materializeChildren(HOLES);
  }

  function parentPath(path) {
    var p, items, i;
    for (p in HOLES) {
      if (!Object.prototype.hasOwnProperty.call(HOLES, p)) continue;
      items = (HOLES[p] && HOLES[p].items) || [];
      for (i = 0; i < items.length; i++) {
        if (items[i].path === path) return p;
      }
    }
    if (path === "/") return "/";
    i = path.lastIndexOf("/");
    return i <= 0 ? "/" : path.slice(0, i);
  }

  function navHole(path) {
    var hole = HOLES[path];
    if (hole && hole.items && hole.items.length) return { path: path, hole: hole };
    var par = parentPath(path);
    var ph = HOLES[par];
    if (ph && ph.items && ph.items.length) return { path: par, hole: ph };
    return { path: "/", hole: HOLES["/"] || { items: [], title: "Directory" } };
  }

  function itemsByN() {
    var path = pathNow();
    var cur = (HOLES[path] && HOLES[path].items) || [];
    var root = (HOLES["/"] && HOLES["/"].items) || [];
    var byN = {}, i;
    for (i = 0; i < root.length; i++) byN[root[i].n] = root[i];
    for (i = 0; i < cur.length; i++) byN[cur[i].n] = cur[i];
    return byN;
  }

  function docHtml(doc) {
    if (!doc) return "";
    if (doc.html) return doc.html;
    var html = "", copy = doc.copy, i;
    if (typeof copy === "string") copy = [copy];
    if (Array.isArray(copy)) {
      for (i = 0; i < copy.length; i++) html += "<p class='info'>" + esc(copy[i]) + "</p>";
    }
    if (doc.steps && doc.steps.length) {
      html += "<ol class='steps'>";
      for (i = 0; i < doc.steps.length; i++) html += "<li>" + esc(doc.steps[i]) + "</li>";
      html += "</ol>";
    }
    if (doc.caps && doc.caps.length) {
      html += "<ul class='caps'>";
      for (i = 0; i < doc.caps.length; i++) {
        html += "<li><span class='itype'>0</span> " + esc(doc.caps[i]) + "</li>";
      }
      html += "</ul>";
    }
    if (doc.note) html += "<p class='info dim'>" + esc(doc.note) + "</p>";
    return html;
  }

  function renderDir(path) {
    var nav = navHole(path);
    var hole = nav.hole || { items: [], title: "Directory" };
    var html = "<p class='info dim'>" + esc((document.documentElement.lang === "es" && hole.title_es) ? hole.title_es : (hole.title || "Directory")) + "</p><div class='selectors'>";
    if (nav.path !== "/") {
      html += "<button type='button' class='sel' data-path='" + parentPath(nav.path) + "' data-n='0'>" +
        "<span class='itype'>0</span> ../ <span class='path'>parent</span></button>";
    }
    (hole.items || []).forEach(function (it) {
      var active = path === it.path ? " active" : "";
      var es = document.documentElement.lang === "es";
      var nm = (es && it.name_es) ? it.name_es : it.name;
      var hn = (es && it.hint_es) ? it.hint_es : (it.hint || "");
      html += "<button type='button' class='sel" + active + "' data-path='" + it.path + "' data-n='" + it.n + "'>" +
        "<span class='itype'>" + esc(it.n) + "</span> " + esc(nm) +
        " <span class='path'>" + esc(hn) + "</span></button>";
    });
    html += "</div>";
    dirEl.innerHTML = html;
    dirEl.querySelectorAll("button.sel").forEach(function (b) {
      b.addEventListener("click", function () { go(b.getAttribute("data-path")); });
    });
  }

  function hideSpecial() {
    authEl.hidden = true;
    gameEl.hidden = true;
    if (digEl) digEl.hidden = true;
    viewEl.hidden = true;
    if (game) game.stop();
    if (dig) dig.stop();
  }

  function showType0(title, text) {
    heroEl.hidden = true;
    authEl.hidden = true;
    gameEl.hidden = true;
    if (digEl) digEl.hidden = true;
    if (game) game.stop();
    if (dig) dig.stop();
    askEl.hidden = false;
    viewEl.hidden = false;
    viewEl.innerHTML =
      "<h2><span class='itype'>0</span> " + esc(title || "Document") + "</h2>" +
      "<pre class='gopher-doc'>" + esc(text || "") + "</pre>";
    viewEl.focus();
  }

  function render() {
    var path = pathNow();
    $("host").textContent = "gopher://gopher.ai:70" + path;
    document.title = path === "/fetch"
      ? "FETCH — GOPHER AI"
      : (path === "/dig" ? "DIG — GOPHER AI" : (path === "/" ? "GOPHER AI" : ("GOPHER AI " + path)));
    paintStaging();
    renderDir(path);
    paintWho();
    hideSpecial();
    if (dirEl) dirEl.hidden = (path === "/fetch" || path === "/dig");

    if (path === "/" || path === "/waitlist") {
      heroEl.hidden = false;
      askEl.hidden = false;
      if (path === "/waitlist") $("email").focus();
      return;
    }
    heroEl.hidden = true;
    askEl.hidden = true;

    if (path === "/user") {
      askEl.hidden = false;
      authEl.hidden = false;
      var s = session();
      $("auth-out").hidden = !s;
      if (s) setStatus($("auth-status"), "ok", "you’re in as " + s.name + ".");
      return;
    }
    if (path === "/fetch") {
      askEl.hidden = true;
      gameEl.hidden = false;
      var canvas = $("fetch");
      if (canvas) canvas.setAttribute("aria-live", "polite");
      bootGame();
      questMark("play");
      return;
    }
    if (path === "/dig") {
      askEl.hidden = true;
      if (digEl) digEl.hidden = false;
      bootDig();
      return;
    }
    if (path === "/watch" || path === "/remind" || path === "/draft") {
      paintKindHole(path);
      return;
    }
    if (path === "/status") {
      paintStatus();
      return;
    }
    if (path === "/scores") {
      askEl.hidden = false;
      viewEl.hidden = false;
      viewEl.innerHTML = "<h2>0 Scores/</h2><p class='info'>device best, hole board if the server is up, and Eternal GOPHER CHAMPIONS who cleared all 100.</p><pre class='gopher-doc' id='scoreboard'>loading…</pre>";
      paintScores();
      return;
    }
    var doc = HOLES[path];
    if (!doc) {
      viewEl.hidden = false;
      viewEl.innerHTML = "<h2>3 Error</h2><p class='info'>selector not found. press esc or 0 for the directory.</p>";
      return;
    }
    if (doc.items && doc.items.length && !doc.html && !doc.copy && !doc.steps && !doc.caps) {
      askEl.hidden = false;
      return;
    }
    viewEl.hidden = false;
    viewEl.innerHTML = "<h2>" + esc(doc.title || path) + "</h2>" + docHtml(doc);
    viewEl.focus();
  }

  function shoutHud(msg) {
    var el = $("g-shout");
    var text = String(msg == null ? "" : msg);
    var ouch = /Ouchies|TIME OVER/.test(text);
    if (!el) return;
    el.textContent = text;
    el.className = "g-shout " + (ouch ? "ouch" : "ok");
    if (shoutTimer) clearTimeout(shoutTimer);
    shoutTimer = setTimeout(function () {
      el.textContent = "";
      el.className = "g-shout";
      shoutTimer = 0;
    }, 1400);
  }

  function bootGame() {
    var canvas = $("fetch");
    var name = whoName();
    $("g-best").textContent = "best " + bestScore(name);
    if (!game) {
      game = new FetchGame(canvas, {
        onHud: function (g) {
          var hpEl, bar, tEl, pct;
          $("g-score").textContent = "score " + g.score;
          $("g-lvl").textContent = "lvl " + g.lvl;
          $("g-lives").textContent = "lives " + g.lives;
          if (g.hp != null) {
            hpEl = $("g-hp");
            bar = $("g-hp-bar");
            if (hpEl) hpEl.textContent = "hp " + Number(g.hp).toFixed(1);
            if (bar) {
              pct = Math.max(0, Math.min(100, (g.hp / 3) * 100));
              bar.style.width = pct + "%";
              bar.classList.toggle("low", g.hp < 1);
            }
          }
          var pwr = $("g-pwr");
          if (pwr) pwr.textContent = "pwr " + (g.power ? 1 : 0);
          var needEl = $("g-need");
          if (needEl) needEl.textContent = "pellets " + (g.needLeft != null ? g.needLeft : (g.pellets ? g.pellets.length : 0));
          if (g.leftMs != null) {
            tEl = $("g-time");
            if (tEl) tEl.textContent = String(Math.ceil(g.leftMs / 1000));
          }
          var b = saveBest(name, g.score);
          $("g-best").textContent = "best " + b;
          if (g.champion) {
            if (!scoreSent) {
              scoreSent = true;
              postScore(whoName(), g.score);
              postChampion(whoName(), g.score);
              showTrophy(whoName());
            }
          } else if (g.dead) {
            setStatus($("g-status"), "err", t("fetchDead"));
            if (!scoreSent) {
              scoreSent = true;
              postScore(whoName(), g.score);
            }
          } else if (g.win) setStatus($("g-status"), "ok", t("fetchWin"));
        },
        shout: shoutHud,
        onShout: shoutHud
      });
    }
    applySavedVol();
    game.draw();
  }


  function readKinds() {
    var list = [];
    try { list = JSON.parse(localStorage.getItem(KIND_KEY) || "[]"); } catch (e) { list = []; }
    return Array.isArray(list) ? list : [];
  }
  function pushKind(kind, q) {
    var list = readKinds();
    list.push({ kind: kind, q: String(q || ""), at: Date.now() });
    if (list.length > 40) list = list.slice(-40);
    try { localStorage.setItem(KIND_KEY, JSON.stringify(list)); } catch (e) {}
  }
  function paintKindHole(path) {
    var kind = path.replace("/", "");
    var rows = readKinds().filter(function (r) { return r && r.kind === kind; });
    var lines = rows.map(function (r, i) {
      var t = new Date(r.at || 0);
      var hh = t.toISOString ? t.toISOString().slice(11, 16) : "";
      return String(i + 1).padStart(2, " ") + "  " + hh + "  " + String(r.q || "");
    });
    viewEl.hidden = false;
    askEl.hidden = false;
    viewEl.innerHTML =
      "<h2>0 " + esc(kind) + "/</h2>" +
      "<p class='info'>queued on this device. not SMS. there is no number. waitlist is the phone door.</p>" +
      "<pre class='gopher-doc'>" + esc(lines.length ? lines.join("\n") : "empty. type " + kind + " plus an order in the prompt.") + "</pre>";
    viewEl.focus();
  }
  function paintStatus() {
    viewEl.hidden = false;
    askEl.hidden = false;
    viewEl.innerHTML = "<h2>0 Status/</h2><p class='info'>honest liveness. no fake uptime graph.</p><pre class='gopher-doc' id='status-pre'>checking…</pre>";
    var el = $("status-pre");
    var base = "Pages hole: static files.\npython /health: ";
    fetch("/health", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.text() : Promise.reject(); })
      .then(function (t) {
        if (el) el.textContent = base + "up (" + String(t).slice(0, 80) + ")\nthis is the local process, not a SLA.";
      })
      .catch(function () {
        if (el) el.textContent = base + "no process (GitHub Pages or server down).\nIf this page loaded, the static hole is up.";
      });
  }
  function bootDig() {
    var canvas = $("dig-canvas");
    if (!canvas || typeof DigGame !== "function") {
      setStatus($("d-status"), "err", t("digMissing"));
      return;
    }
    if (!dig) {
      dig = new DigGame(canvas, {
        onHud: function (g) {
          var a = $("d-score"), b = $("d-lvl"), c = $("d-lives");
          if (a) a.textContent = "score " + (g.score || 0);
          if (b) b.textContent = "lvl " + (g.lvl || 1);
          if (c) c.textContent = "lives " + (g.lives || 0);
          if (g.dead) setStatus($("d-status"), "err", t("digDead"));
          else if (g.win) setStatus($("d-status"), "ok", t("digWin"));
        }
      });
    }
    if (dig.draw) dig.draw();
  }

  function queueLocal(q) {
    try { localStorage.setItem("gopher_first_order", q); } catch (err) {}
    setStatus($("ask-status"), "ok", "queued: “" + q + "”. leave an email or enter your hole.");
    if ($("email")) $("email").focus();
  }

  function askServer(q) {
    if (kindOrder(q)) {
      queueKindOrder(q);
      return;
    }
    setStatus($("ask-status"), "", "fetching…");
    fetch("/api/ask", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ q: q })
    })
      .then(function (res) {
        return res.json().then(function (body) { return body; }).catch(function () { return null; });
      })
      .then(function (body) {
        if (!body || (body.ok !== true && body.kind !== "doc" && body.kind !== "queued")) {
          clientFetch(q);
          return;
        }
        if (body.kind === "doc") {
          showType0(body.title || "0 Document", body.text || "");
          setStatus($("ask-status"), body.ok ? "ok" : "err", body.ok ? "fetched." : (body.text || "fetch failed."));
          if (body.ok !== false) questMark("fetch");
          return;
        }
        if (body.kind === "queued") {
          try { localStorage.setItem("gopher_first_order", q); } catch (err) {}
          showType0("0 Order", body.text || "queued in the hole.");
          setStatus($("ask-status"), "ok", body.text || "queued in the hole.");
          return;
        }
        queueLocal(q);
      })
      .catch(function () { clientFetch(q); });
  }

  function looksTicker(q) {
    return /fetch|price|btc|eth|sol|xrp|doge|ada/i.test(q || "");
  }
  function tickerId(q) {
    var low = (q || "").toLowerCase();
    var map = { btc: "BTC", eth: "ETH", sol: "SOL", xrp: "XRP", doge: "DOGE", ada: "ADA" };
    var k;
    for (k in map) if (Object.prototype.hasOwnProperty.call(map, k) && low.indexOf(k) >= 0) return map[k];
    return "BTC";
  }
  function clientFetch(q) {
    if (!looksTicker(q)) { queueLocal(q); return; }
    var id = tickerId(q);
    setStatus($("ask-status"), "", "fetching…");
    fetch("https://api.coinbase.com/v2/prices/" + id + "-USD/spot")
      .then(function (res) { return res.json(); })
      .then(function (j) {
        var amt = j && j.data && j.data.amount;
        if (!amt) throw new Error("empty");
        try {
          sessionStorage.setItem(SPOT_KEY, JSON.stringify({ id: id, amt: amt, at: Date.now() }));
        } catch (err) {}
        showType0("0 " + id + "-USD", id + "-USD\n\nlast      " + amt + "\n\nsource    public spot");
        setStatus($("ask-status"), "ok", "fetched.");
        questMark("fetch");
      })
      .catch(function () {
        var stash = null;
        try { stash = JSON.parse(sessionStorage.getItem(SPOT_KEY) || "null"); } catch (err) { stash = null; }
        if (stash && stash.id === id && stash.amt != null && stash.amt !== "") {
          showType0("0 " + id + "-USD", id + "-USD\n\nlast      " + stash.amt + "\n\nsource    cached");
          setStatus($("ask-status"), "ok", "cached");
          questMark("fetch");
          return;
        }
        queueLocal(q);
      });
  }

  function tutSeen() {
    try { return localStorage.getItem(TUT_KEY) === "1"; } catch (e) { return true; }
  }
  function tutDismiss() {
    try { localStorage.setItem(TUT_KEY, "1"); } catch (e) {}
    var el = $("tutorial");
    if (el) el.hidden = true;
    questPaint();
  }
  function tutShow() {
    if (tutSeen()) return;
    var path = pathNow();
    if (path === "/fetch" || path === "/dig") return;
    var el = $("tutorial");
    if (el) el.hidden = false;
  }

  function questRead() {
    var o;
    try { o = JSON.parse(localStorage.getItem(QUEST_KEY) || "null"); } catch (e) { o = null; }
    if (!o || typeof o !== "object") o = {};
    return {
      play: !!o.play,
      fetch: !!o.fetch,
      wait: !!o.wait,
      done: !!o.done
    };
  }
  function questWrite(st) {
    try { localStorage.setItem(QUEST_KEY, JSON.stringify(st)); } catch (e) {}
  }
  function questMark(key) {
    var st = questRead();
    if (st.done) return;
    if (key === "play" || key === "fetch" || key === "wait") st[key] = true;
    if (st.play && st.fetch && st.wait) st.done = true;
    questWrite(st);
    questPaint();
  }
  function questNextKey(st) {
    if (!st.play) return "play";
    if (!st.fetch) return "fetch";
    if (!st.wait) return "wait";
    return "";
  }
  function ensureQuestDom() {
    var el = $("quest");
    if (el) return el;
    el = document.createElement("div");
    el.id = "quest";
    el.hidden = true;
    el.setAttribute("role", "region");
    el.setAttribute("aria-label", "onboarding quest");
    el.style.cssText = "position:fixed;right:0.75rem;bottom:0.75rem;z-index:30;max-width:28ch;border:1px solid var(--fg-mid,#39ff14);background:var(--bg-2,#070908);padding:0.75rem 0.85rem;box-shadow:var(--glow);";
    el.innerHTML =
      "<p id='quest-status' class='info'>first orders</p>" +
      "<ul id='quest-list'></ul>" +
      "<div class='row'>" +
      "<button type='button' id='quest-next'>NEXT</button>" +
      "<button type='button' id='quest-skip' class='ghost'>SKIP</button>" +
      "</div>";
    document.body.appendChild(el);
    return el;
  }
  function bindQuestBtns() {
    var skip, next;
    if (questBound) return;
    skip = $("quest-skip");
    next = $("quest-next");
    if (skip) {
      skip.addEventListener("click", function () {
        var st = questRead();
        st.done = true;
        questWrite(st);
        questPaint();
      });
    }
    if (next) {
      next.addEventListener("click", function () { questJump(); });
    }
    if (skip || next) questBound = true;
  }
  function questPaint() {
    var el = $("quest");
    var tut = $("tutorial");
    var tutOpen = !!(tut && !tut.hidden);
    var st = questRead();
    var list, status, steps, i, n, html, nextK, labels;
    if (tutOpen || !tutSeen() || st.done) {
      if (el) el.hidden = true;
      return;
    }
    if (!el) el = ensureQuestDom();
    bindQuestBtns();
    el.hidden = false;
    labels = { play: t("questPlay"), fetch: t("questFetch"), wait: t("questWait") };
    steps = ["play", "fetch", "wait"];
    n = 0;
    html = "";
    for (i = 0; i < steps.length; i++) {
      if (st[steps[i]]) n++;
      html += "<li>" + (st[steps[i]] ? "[x]" : "[ ]") + " " + labels[steps[i]] + "</li>";
    }
    list = $("quest-list");
    status = $("quest-status");
    if (list) list.innerHTML = html;
    nextK = questNextKey(st);
    if (status) {
      if (!nextK) status.textContent = t("questDone");
      else status.textContent = n + "/3 · " + t("questNext") + labels[nextK];
    }
  }
  function questJump() {
    var st = questRead();
    var key = questNextKey(st);
    var cmd, em;
    if (!key) return;
    if (key === "play") {
      go("/fetch");
      return;
    }
    if (key === "fetch") {
      if (askEl && askEl.hidden) go("/");
      cmd = $("command");
      if (cmd) {
        cmd.placeholder = "fetch btc";
        cmd.focus();
      }
      return;
    }
    if (askEl && askEl.hidden) go("/");
    em = $("email");
    if (em) em.focus();
  }

  function kindOrder(q) {
    var m = /^(watch|remind|draft)\b/i.exec(q || "");
    return m ? m[1].toLowerCase() : "";
  }
  function queueKindOrder(q) {
    var kind = kindOrder(q) || "order";
    queueLocal(q);
    pushKind(kind, q);
    paintKindHole("/" + kind);
  }

  function logClientErr(msg) {
    var list = [], n;
    try { list = JSON.parse(localStorage.getItem(LOG_KEY) || "[]"); } catch (e) { list = []; }
    if (!Array.isArray(list)) list = [];
    list.push({ at: Date.now(), msg: String(msg == null ? "" : msg) });
    n = list.length - 20;
    if (n > 0) list = list.slice(n);
    try { localStorage.setItem(LOG_KEY, JSON.stringify(list)); } catch (e) {}
  }
  function readTrack() {
    try { return localStorage.getItem(TRACK_KEY) === "true"; } catch (e) { return false; }
  }
  function writeTrack(on) {
    try { localStorage.setItem(TRACK_KEY, on ? "true" : "false"); } catch (e) {}
  }
  function paintTrackBtn() {
    var el = $("opt-in");
    if (!el) return;
    el.textContent = readTrack() ? "TRACK ON" : "TRACK?";
  }
  function bindTrackBtn() {
    var el = $("opt-in");
    if (!el) return;
    paintTrackBtn();
    el.addEventListener("click", function () {
      var on = !readTrack();
      writeTrack(on);
      paintTrackBtn();
      if (on) setStatus($("ask-status"), "ok", "tracking on this device only. no beacon.");
    });
  }
  window.onerror = function (msg) {
    logClientErr(msg);
  };
  window.addEventListener("unhandledrejection", function (e) {
    var r = e && e.reason;
    logClientErr(r && r.message ? r.message : r);
  });

  function tickClock() {
    var clock = $("clock");
    if (!clock) return;
    clock.textContent = new Date().toLocaleString("en-CA", {
      timeZone: "America/Bogota",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false
    }).replace(",", "") + " COT";
  }
  tickClock();
  setInterval(tickClock, 30000);

  window.addEventListener("hashchange", render);
  document.addEventListener("keydown", function (e) {
    var inField = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA");
    var tut = $("tutorial");
    var tutOpen = tut && !tut.hidden;
    var helpEl = $("help");
    if (tutOpen && e.key === "Tab") {
      trapTutorialTab(e);
      return;
    }
    if (tutOpen && !inField && (e.key === "Escape" || e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      tutDismiss();
      if (e.key === "Escape") return;
    }
    if (digEl && !digEl.hidden && dig && !inField) {
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        if (dig.pauseToggle) dig.pauseToggle();
      }
      if (e.key === " " && !dig.running) {
        e.preventDefault();
        dig.start();
      }
      if (dig.running) {
        if (e.key === "ArrowUp" || e.key === "w") { e.preventDefault(); dig.input("up"); }
        if (e.key === "ArrowDown" || e.key === "s") { e.preventDefault(); dig.input("down"); }
        if (e.key === "ArrowLeft" || e.key === "a") { e.preventDefault(); dig.input("left"); }
        if (e.key === "ArrowRight" || e.key === "d") { e.preventDefault(); dig.input("right"); }
      }
    }
    if (!gameEl.hidden && game && !inField) {
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        if (game.pauseToggle) game.pauseToggle();
        var paused = !!game.paused;
        setStatus($("g-status"), "", paused ? t("fetchPaused") : t("fetchPlay"));
        var gp = $("g-pause");
        if (gp) gp.textContent = paused ? "RESUME" : "PAUSE";
      }
      if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        toggleKeyCard();
      }
      if (e.key === " " && !game.running) {
        e.preventDefault();
        scoreSent = false;
        game.start();
        if (game.running) setStatus($("g-status"), "", t("fetchPlay"));
        questMark("play");
      }
      if (game.running) {
        if (e.key === "ArrowUp" || e.key === "w") { e.preventDefault(); game.input("up"); }
        if (e.key === "ArrowDown" || e.key === "s") { e.preventDefault(); game.input("down"); }
        if (e.key === "ArrowLeft" || e.key === "a") { e.preventDefault(); game.input("left"); }
        if (e.key === "ArrowRight" || e.key === "d") { e.preventDefault(); game.input("right"); }
      }
    }
    if (inField) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (e.key === "/") {
      e.preventDefault();
      if (tutOpen) tutDismiss();
      go("/");
      $("command").focus();
      return;
    }
    if (e.key === "?") {
      e.preventDefault();
      if (helpEl) {
        helpEl.hidden = !helpEl.hidden;
        return;
      }
      if (tutOpen) tutDismiss();
      go("/");
      $("command").focus();
      setStatus($("ask-status"), "", "1 Docs/ · 5 FETCH play · 6 waitlist · 9 user");
      return;
    }
    if (e.key === "Escape") {
      if (helpEl && !helpEl.hidden) {
        helpEl.hidden = true;
        return;
      }
      go("/");
      return;
    }
    if (e.key === "0") { go("/"); return; }
    var byN = itemsByN();
    if (byN[e.key]) {
      e.preventDefault();
      if (tutOpen) tutDismiss();
      go(byN[e.key].path);
    }
  });

  $("ask-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var q = ($("command").value || "").trim();
    if (!q) return;
    if (/^[0-9]$/.test(q)) {
      var hit = itemsByN()[q];
      if (hit) { go(hit.path); $("command").value = ""; return; }
    }
    if (kindOrder(q)) {
      $("command").value = "";
      queueKindOrder(q);
      return;
    }
    var alias = ALIAS[q.toLowerCase()];
    if (alias) { go(alias); $("command").value = ""; return; }
    if (EMAIL_RE.test(q)) {
      $("email").value = q;
      $("command").value = "";
      $("form").requestSubmit();
      return;
    }
    $("command").value = "";
    askServer(q);
  });

  $("form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var email = ($("email").value || "").trim();
    var st = $("form-status");
    if (!EMAIL_RE.test(email)) {
      setStatus(st, "err", "! that doesn’t look like an email.");
      return;
    }
    $("submit").disabled = true;
    var order = "";
    try { order = localStorage.getItem("gopher_first_order") || ""; } catch (err) {}
    fetch("/api/waitlist", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, order: order })
    })
      .then(function (res) { return res.json().then(function (body) { return body; }).catch(function () { return {}; }); })
      .then(function (body) {
        if (body.status === "joined" || body.status === "duplicate") {
          setStatus(st, body.status === "joined" ? "ok" : "dup",
            body.status === "joined" ? "ok. you’re on the list." : "already listed.");
        } else {
          stashLocal(email, order);
          setStatus(st, "ok", "ok. listed on this device.");
        }
        $("form").classList.add("done");
        $("email").readOnly = true;
        questMark("wait");
      })
      .catch(function () {
        stashLocal(email, order);
        setStatus(st, "ok", "ok. listed on this device.");
        $("form").classList.add("done");
        $("email").readOnly = true;
        questMark("wait");
      });
  });

  function stashLocal(email, order) {
    var key = "gopher_waitlist", list = [];
    try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { list = []; }
    if (!list.some(function (e) { return (e.email || "").toLowerCase() === email.toLowerCase(); })) {
      list.push({ email: email, order: order || "", at: new Date().toISOString() });
    }
    try { localStorage.setItem(key, JSON.stringify(list)); } catch (e) {}
  }

  async function authSubmit(isNew) {
    var name = ($("uname").value || "").trim().toLowerCase();
    var pass = $("pass").value || "";
    var st = $("auth-status");
    if (!/^[a-z0-9._-]{3,24}$/.test(name)) {
      setStatus(st, "err", "! name: 3–24 letters, numbers, . _ -");
      return;
    }
    if (pass.length < 8) {
      setStatus(st, "err", "! passphrase at least 8.");
      return;
    }
    var db = users();
    if (isNew) {
      if (db[name]) { setStatus(st, "err", "! that hole already exists on this device."); return; }
      var h = await hashPass(pass);
      db[name] = { salt: h.salt, hash: h.hash, at: Date.now() };
      saveUsers(db);
      setSession(name);
      $("pass").value = "";
      setStatus(st, "ok", "hole dug. welcome, " + name + ".");
      $("auth-out").hidden = false;
      return;
    }
    if (!db[name]) { setStatus(st, "err", "! no hole by that name here."); return; }
    var check = await hashPass(pass, db[name].salt);
    if (check.hash !== db[name].hash) { setStatus(st, "err", "! passphrase doesn’t match."); return; }
    setSession(name);
    $("pass").value = "";
    setStatus(st, "ok", "entered. hi " + name + ".");
    $("auth-out").hidden = false;
  }

  $("auth-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    authSubmit(false);
  });
  $("auth-new").addEventListener("click", function () { authSubmit(true); });
  $("auth-out").addEventListener("click", function () {
    setSession(null);
    setStatus($("auth-status"), "", "left the hole. guest mode.");
    $("auth-out").hidden = true;
  });

  $("g-start").addEventListener("click", function () {
    if (!game) bootGame();
    scoreSent = false;
    game.start();
    if (game.running) setStatus($("g-status"), "", t("fetchPlay"));
    questMark("play");
  });
  $("g-mute").addEventListener("click", function () {
    if (!game) bootGame();
    game.mute = !game.mute;
    $("g-mute").textContent = game.mute ? "MUTE" : "SOUND";
  });
  var gVol = $("g-vol");
  if (gVol) {
    syncVolSlider();
    gVol.addEventListener("input", function () { applyVolFromSlider(gVol); });
    gVol.addEventListener("change", function () { applyVolFromSlider(gVol); });
  }
  var gPause = $("g-pause");
  if (gPause) gPause.addEventListener("click", function () {
    if (!game) bootGame();
    if (game.pauseToggle) game.pauseToggle();
    gPause.textContent = game.paused ? "RESUME" : "PAUSE";
    setStatus($("g-status"), "", game.paused ? t("fetchPaused") : t("fetchPlay"));
  });
  var gKey = $("g-key");
  if (gKey) gKey.addEventListener("click", function () { toggleKeyCard(); });
  var gKeyOk = $("g-key-ok");
  if (gKeyOk) gKeyOk.addEventListener("click", function () { toggleKeyCard(false); });
  var gTrophyOk = $("g-trophy-ok");
  if (gTrophyOk) gTrophyOk.addEventListener("click", function () {
    hideTrophy();
    go("/scores");
  });
  var gInstall = $("g-install");
  if (gInstall) {
    gInstall.addEventListener("click", function () {
      if (deferredInstall && typeof deferredInstall.prompt === "function") {
        deferredInstall.prompt();
      }
    });
  }
  var gShare = $("g-share");
  if (gShare) gShare.addEventListener("click", function () { shareScore(); });
  var gHaptic = $("g-haptic");
  if (gHaptic) {
    gHaptic.addEventListener("click", function () {
      if (!game) bootGame();
      if (game && game.hapticToggle) game.hapticToggle();
    });
  }
  var langBtn = $("lang");
  if (langBtn) {
    langBtn.addEventListener("click", function () {
      applyLang(document.documentElement.lang === "es" ? "en" : "es");
    });
  }
  var contrastBtn = $("contrast");
  if (contrastBtn) {
    contrastBtn.addEventListener("click", function () {
      applyHc(!document.documentElement.classList.contains("high-contrast"));
    });
  }
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredInstall = e;
    var btn = $("g-install");
    if (btn) { btn.hidden = false; btn.disabled = false; }
  });
  document.querySelectorAll("#game .dpad button").forEach(function (b) {
    b.addEventListener("click", function () {
      if (game) game.input(b.getAttribute("data-dir"));
    });
  });
  document.querySelectorAll("#dig .dpad button").forEach(function (b) {
    b.addEventListener("click", function () {
      if (dig) dig.input(b.getAttribute("data-dig"));
    });
  });
  var dStart = $("d-start");
  if (dStart) dStart.addEventListener("click", function () {
    if (!dig) bootDig();
    if (dig && dig.start) dig.start();
    if (dig && dig.running) setStatus($("d-status"), "", t("digPlay"));
  });
  var dPause = $("d-pause");
  if (dPause) dPause.addEventListener("click", function () {
    if (!dig) bootDig();
    if (dig && dig.pauseToggle) dig.pauseToggle();
    dPause.textContent = (dig && dig.paused) ? "RESUME" : "PAUSE";
  });
  var dMute = $("d-mute");
  if (dMute) dMute.addEventListener("click", function () {
    if (!dig) bootDig();
    if (!dig) return;
    dig.mute = !dig.mute;
    dMute.textContent = dig.mute ? "MUTE" : "SOUND";
  });

  var tutOk = $("tut-ok");
  if (tutOk) tutOk.addEventListener("click", function () { tutDismiss(); });
  var tutEl = $("tutorial");
  if (tutEl) {
    tutEl.addEventListener("click", function (ev) {
      if (ev.target === tutEl) tutDismiss();
    });
  }
  var helpOk = $("help-ok");
  if (helpOk) {
    helpOk.addEventListener("click", function () {
      var el = $("help");
      if (el) el.hidden = true;
    });
  }
  var helpPane = $("help");
  if (helpPane) {
    helpPane.addEventListener("click", function (ev) {
      if (ev.target === helpPane) helpPane.hidden = true;
    });
  }

  function deviceBoardText() {
    var all = {}, names, me, txt, i;
    try { all = JSON.parse(localStorage.getItem(BEST_KEY) || "{}"); } catch (e) { all = {}; }
    me = whoName();
    if (all[me] == null) all[me] = bestScore(me);
    names = Object.keys(all);
    names.sort(function (a, b) { return (all[b] || 0) - (all[a] || 0); });
    txt = "device\n";
    for (i = 0; i < names.length; i++) {
      txt += String(i + 1).padStart(2, " ") + "  " + String(names[i] || "guest").slice(0, 16).padEnd(16, " ") + "  " + (all[names[i]] || 0) + "\n";
    }
    return txt;
  }

  function paintScores() {
    var el = $("scoreboard");
    if (!el) return;
    var txt = deviceBoardText();
    var localCh = [];
    try { localCh = JSON.parse(localStorage.getItem(CHAMP_KEY) || "[]"); } catch (e) { localCh = []; }
    if (Array.isArray(localCh) && localCh.length) {
      txt += "\neternal (this device)\n";
      localCh.forEach(function (n, i) {
        txt += String(i + 1).padStart(2, " ") + "  " + String(n || "guest").slice(0, 16) + "\n";
      });
    }
    fetch("/api/scores", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : []; })
      .then(function (rows) {
        if (Array.isArray(rows) && rows.length) {
          txt += "\nboard\n";
          rows.slice(0, 10).forEach(function (r, i) {
            var line = String(i + 1).padStart(2, " ") + "  " + String((r && r.name) || "guest").slice(0, 16).padEnd(16, " ") + "  " + ((r && r.score) || 0);
            if (r && r.stage != null && r.stage !== "") line += "  " + r.stage;
            txt += line + "\n";
          });
        } else {
          txt += "\nboard    empty (needs the local server)";
        }
        return fetch("/api/champions", { headers: { Accept: "application/json" } });
      })
      .then(function (res) { return res && res.ok ? res.json() : []; })
      .then(function (rows) {
        txt += "\nEternal GOPHER CHAMPIONS\n";
        if (Array.isArray(rows) && rows.length) {
          rows.forEach(function (r, i) {
            txt += String(i + 1).padStart(2, " ") + "  " + String((r && r.name) || "guest").slice(0, 16).padEnd(16, " ") + "  " + ((r && r.score) || 0) + "\n";
          });
        } else {
          txt += "  none yet. clear all 100.\n";
        }
        el.textContent = txt;
      })
      .catch(function () { el.textContent = txt + "\nboard    offline"; });
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }

  bootLang();
  applyLang(document.documentElement.lang);
  bootHc();
  paintStaging();
  bindTrackBtn();
  render();
  tutShow();
  bindQuestBtns();
  questPaint();
  fetch("hole.json", { headers: { Accept: "application/json" } })
    .then(function (res) {
      if (!res.ok) throw new Error("no hole");
      return res.json();
    })
    .then(function (data) {
      applyCatalog(data);
      render();
    })
    .catch(function () {});
})();
