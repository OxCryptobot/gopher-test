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
  var FAV_KEY = "gopher_fav_v1";
  var USE_KEY = "gopher_use_v1";

  /* Scalable Gopher directory. Add an item in hole.json; this is the fallback. */
  var HOLES = {
    "/": {
      title: "Directory of GOPHER AI",
      items: [
        { n: "1", type: "1", name: "Docs/", path: "/docs", hint: "or type below" },
        { n: "5", type: "1", name: "Play/", path: "/games", hint: "side quest · MAZE + BURROW" },
        { n: "7", type: "7", name: "Tasks/", path: "/tasks", hint: "DIG · 100 tasks" },
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
        "<li><span class='itype'>0</span> FETCH is search. DIG is a task from the 100. MAZE and BURROW kill time between searches.</li>" +
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
    privacy: "/privacy", fetch: "/fetch", maze: "/fetch", game: "/fetch",
    play: "/games", burrow: "/dig", dig: "/dig", search: "/",
    user: "/user", login: "/user", waitlist: "/waitlist", home: "/", menu: "/",
    tasks: "/tasks", es: "/es", usage: "/usage", stats: "/usage",
    favorites: "/tasks"
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
  var TASKS = [];
  var sugOpen = false;
  var sugHi = -1;
  var sugItems = [];
  var idleTimer = 0;
  var phTimer = 0;
  var holeLive = false;
  var holeProbed = false;
  var replyOpen = false;
  var brainUrl = "";
  var DEFAULT_PH = "ask gopher   or   tasks   or   waitlist";
  var SUG_MAX = 3;
  var SUG_IDLE = 3;


  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pathNow() {
    var h = (location.hash || "#/").replace(/^#/, "");
    var cut;
    if (!h.startsWith("/")) h = "/" + h;
    cut = h.search(/[?#]/);
    if (cut >= 0) h = h.slice(0, cut);
    if (h.length > 1 && h.endsWith("/")) h = h.slice(0, -1);
    if (h === "/maze") h = "/fetch";
    if (h === "/burrow") h = "/dig";
    return h || "/";
  }
  function hashParam(name) {
    var h = (location.hash || "").replace(/^#/, "");
    var i = h.indexOf("?");
    var q, parts, j, pair, key;
    if (i < 0) return "";
    q = h.slice(i + 1);
    parts = q.split("&");
    for (j = 0; j < parts.length; j++) {
      pair = parts[j].split("=");
      key = decodeURIComponent(pair[0] || "").replace(/\+/g, " ");
      if (key === name) return decodeURIComponent((pair[1] || "").replace(/\+/g, " "));
    }
    return "";
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
    var msg = "MAZE score " + n + " on GOPHER AI";
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

  function setBrain(state, text) {
    var el = $("brain");
    var st = $("ask-status");
    var labels = {
      ready: "ready",
      think: "fetching…",
      ok: "ok",
      parked: "parked",
      err: "err",
      match: "GOPHER · match"
    };
    var label = labels[state] || (state || "ready");
    var bad = (state === "parked" || state === "err");
    if (el) {
      el.textContent = label;
      el.className = "brain" + (bad ? " err" : "") + (state === "parked" ? " parked" : "");
    }
    if (!st) return;
    if (state === "ready" || text == null || text === "") {
      setStatus(st, "", "");
      return;
    }
    setStatus(st, state === "err" || state === "parked" ? "err" : (state === "ok" ? "ok" : ""), text);
  }

  function showWaitForm(on) {
    var el = $("wait-form");
    if (el) el.hidden = !on;
  }

  function paintTopbar(path) {
    var keys = {};
    if (path === "/") {
      keys.home = 1;
      keys.search = 1;
    } else if (path === "/tasks") keys.tasks = 1;
    else if (path === "/waitlist") keys.waitlist = 1;
    else if (path === "/games" || path === "/play" || path === "/fetch" || path === "/dig" || path === "/maze" || path === "/burrow") keys.play = 1;
    var nodes = document.querySelectorAll("#chrome [data-nav]");
    var i, a, nav;
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      nav = a.getAttribute("data-nav");
      a.classList.toggle("active", !!keys[nav]);
    }
  }

  function idleCount() {
    return SUG_IDLE;
  }

  function bootLang() {
    var saved = "";
    try { saved = localStorage.getItem(LANG_KEY) || ""; } catch (e) { saved = ""; }
    if (saved === "es" || saved === "en") document.documentElement.lang = saved;
  }
  var I18N = {
    en: {
      footer: "search · tasks · waitlist",
      fetchInfo: "MAZE. Side quest. 100 stages. One tap, one tile. Eat pellets (Huzaaa!). Walls Clunk!!!. Orange foxes Ouchies!. Kill time between searches.",
      digInfo: "Dig dirt. Grab gems. Rocks fall. One tap, one tile. 30 stages.",
      fetchStatus: "press START. one tap, one tile. eat pellets. dodge orange foxes. beat the clock.",
      digStatus: "press START. dig dirt. grab gems. rocks fall.",
      promptInfo: "GOPHER is on. Type an order. FETCH is search. DIG is a task.",
      promptLabel: "ask gopher:",
      emailLabel: "email:",
      navHome: "home",
      navGames: "play",
      navPlay: "play",
      navWaitlist: "waitlist",
      navUser: "user",
      heroLine: "Paid phone assistant. Search, then do the task.",
      heroGames: "side quest: MAZE · BURROW under play",
      sugCap: "GOPHER:",
      sugCapMatch: "GOPHER · match",
      matchCap: "GOPHER matches your order to a skill. Hosted model parked.",
      keysHint: "keys: <kbd>/</kbd> prompt · <kbd>1</kbd>–<kbd>9</kbd> menu · <kbd>?</kbd> help · <kbd>esc</kbd> home",
      helpTitle: "keys",
      help5: "play",
      helpPrompt: "prompt",
      helpLogin: "login",
      helpArrows: "arrows",
      helpPause: "pause",
      helpSounds: "Huzaaa / Clunk / Ouchies",
      helpStar: "wall −0.1 hp · star ZAP/BLOCK",
      helpKey: "MAZE key",
      helpEsc: "home",
      keyTitle: "MAZE key",
      keyTap: "one tap, one tile",
      keyPellet: "pellet · Huzaaa!",
      keyWall: "wall · Clunk!!! · −0.1 hp",
      keyFox: "fox · Ouchies! · −1 hp",
      keyStar: "star · one per stage · ZAP a fox or BLOCK a hit",
      keyClock: "clock · TIME OVER!",
      keyClear: "stage clear · VICTORY!",
      keyChamp: "all 100 · trophy · Eternal GOPHER CHAMPIONS",
      questTitle: "first orders",
      questPlay: "open play",
      questFetch: "fetch a ticker",
      questWait: "join waitlist",
      questDone: "quest done.",
      questNext: "next: ",
      fetchPaused: "paused. P or PAUSE to dig.",
      fetchPlay: "fetch pellets. dodge foxes. KEY for the map.",
      fetchDead: "404 hole. START to dig again.",
      fetchWin: "fetched. next hole…",
      digPlay: "dig dirt. grab gems. rocks fall.",
      digDead: "buried. START to dig again.",
      digWin: "dug through.",
      digMissing: "BURROW engine not on this hole yet."
    },
    es: {
      footer: "search · tasks · waitlist",
      fetchInfo: "MAZE. Side quest. 100 etapas. Un toque, una losa. Pellets Huzaaa!. Paredes Clunk!!!. Foxes naranjas Ouchies!. Mata el tiempo entre búsquedas.",
      digInfo: "Cava tierra. Agarra gemas. Las rocas caen. Un toque, una losa. 30 etapas.",
      fetchStatus: "pulsa START. un toque, una losa. pellets. foxes naranjas. el reloj.",
      digStatus: "pulsa START. cava tierra. agarra gemas. las rocas caen.",
      promptInfo: "GOPHER está on. Escribe una orden. FETCH es search. DIG es una tarea.",
      promptLabel: "ask gopher:",
      emailLabel: "email:",
      navHome: "inicio",
      navGames: "play",
      navPlay: "play",
      navWaitlist: "waitlist",
      navUser: "usuario",
      heroLine: "Asistente de teléfono de pago. Search, then do the task.",
      heroGames: "side quest: MAZE · BURROW en play",
      sugCap: "GOPHER:",
      sugCapMatch: "GOPHER · match",
      matchCap: "GOPHER empareja tu orden con una skill. Modelo hospedado aparcado.",
      keysHint: "teclas: <kbd>/</kbd> prompt · <kbd>1</kbd>–<kbd>9</kbd> menú · <kbd>?</kbd> ayuda · <kbd>esc</kbd> inicio",
      helpTitle: "teclas",
      help5: "play",
      helpPrompt: "prompt",
      helpLogin: "login",
      helpArrows: "flechas",
      helpPause: "pause",
      helpSounds: "Huzaaa / Clunk / Ouchies",
      helpStar: "pared −0.1 hp · estrella ZAP/BLOCK",
      helpKey: "MAZE key",
      helpEsc: "inicio",
      keyTitle: "MAZE key",
      keyTap: "un toque, una losa",
      keyPellet: "pellet · Huzaaa!",
      keyWall: "pared · Clunk!!! · −0.1 hp",
      keyFox: "fox · Ouchies! · −1 hp",
      keyStar: "estrella · una por etapa · ZAP a fox o BLOCK un golpe",
      keyClock: "reloj · TIME OVER!",
      keyClear: "etapa clara · VICTORY!",
      keyChamp: "las 100 · copa · Eternal GOPHER CHAMPIONS",
      questTitle: "primeras órdenes",
      questPlay: "abre play",
      questFetch: "fetch un ticker",
      questWait: "entra a la lista",
      questDone: "misión hecha.",
      questNext: "sigue: ",
      fetchPaused: "pausa. P o PAUSE para cavar.",
      fetchPlay: "pellets. foxes. KEY para el mapa.",
      fetchDead: "404 hueco. START para cavar otra vez.",
      fetchWin: "fetched. siguiente hueco…",
      digPlay: "cava tierra. agarra gemas. las rocas caen.",
      digDead: "enterrado. START para cavar otra vez.",
      digWin: "cavado.",
      digMissing: "BURROW aún no está en este hueco."
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
    var cmdSug = $("command");
    var qSug = cmdSug ? (cmdSug.value || "") : "";
    paintSuggest(filterTasks(qSug), { hi: sugHi, idle: !String(qSug).trim() });
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
    var el = $("who");
    var s;
    if (!el) return;
    s = session();
    if (s && s.name) {
      el.textContent = s.name;
      el.hidden = false;
    } else {
      el.textContent = "";
      el.hidden = true;
    }
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
    loadBrainUrl(data);
  }

  /* brain URL fetch from hole.json; https python hole; empty = Pages matcher-only */
  function loadBrainUrl(data) {
    var raw = data && data.brain;
    setBrainUrl(typeof raw === "string" ? raw : "");
  }

  function setBrainUrl(raw) {
    var u = String(raw || "").trim();
    if (/^https:\/\//i.test(u)) brainUrl = u.replace(/\/+$/, "");
    else brainUrl = "";
  }

  function apiUrl(path) {
    var p = String(path || "");
    if (p.charAt(0) !== "/") p = "/" + p;
    if (brainUrl) return brainUrl + p;
    return p.replace(/^\//, "");
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
    var es = document.documentElement.lang === "es";
    var htmlDoc = (es && doc.html_es) ? doc.html_es : doc.html;
    if (htmlDoc) return htmlDoc;
    var html = "", copy = (es && doc.copy_es) ? doc.copy_es : doc.copy, i;
    var steps = (es && doc.steps_es) ? doc.steps_es : doc.steps;
    var caps = (es && doc.caps_es) ? doc.caps_es : doc.caps;
    var note = (es && doc.note_es) ? doc.note_es : doc.note;
    if (typeof copy === "string") copy = [copy];
    if (Array.isArray(copy)) {
      for (i = 0; i < copy.length; i++) html += "<p class='info'>" + esc(copy[i]) + "</p>";
    }
    if (steps && steps.length) {
      html += "<ol class='steps'>";
      for (i = 0; i < steps.length; i++) html += "<li>" + esc(steps[i]) + "</li>";
      html += "</ol>";
    }
    if (caps && caps.length) {
      html += "<ul class='caps'>";
      for (i = 0; i < caps.length; i++) {
        html += "<li><span class='itype'>0</span> " + esc(caps[i]) + "</li>";
      }
      html += "</ul>";
    }
    if (note) html += "<p class='info dim'>" + esc(note) + "</p>";
    return html;
  }

  function renderDir(path) {
    var nav = navHole(path);
    var hole = nav.hole || { items: [], title: "Directory" };
    var html = "<p class='info dim'>" + esc((document.documentElement.lang === "es" && hole.title_es) ? hole.title_es : (hole.title || "Directory")) + "</p>";
    if (nav.path === "/") {
      html += "<p class='info dim'>the prompt is the menu · or type below</p>";
    }
    html += "<div class='selectors'>";
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

  function readFavs() {
    var list = [];
    try { list = JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); } catch (e) { list = []; }
    if (!Array.isArray(list)) return [];
    return list.filter(function (id) { return typeof id === "string" && id; });
  }
  function isFav(id) {
    return readFavs().indexOf(id) >= 0;
  }
  function toggleFav(id) {
    var list = readFavs(), i;
    if (!id) return list;
    i = list.indexOf(id);
    if (i >= 0) list.splice(i, 1);
    else list.push(id);
    try { localStorage.setItem(FAV_KEY, JSON.stringify(list)); } catch (e) {}
    return list;
  }
  function readUse() {
    var o = {};
    try { o = JSON.parse(localStorage.getItem(USE_KEY) || "{}"); } catch (e) { o = {}; }
    return (o && typeof o === "object" && !Array.isArray(o)) ? o : {};
  }
  function bumpUse(id) {
    var o, row;
    if (!id) return;
    o = readUse();
    row = o[id] || { n: 0, last: 0 };
    row.n = (row.n || 0) + 1;
    row.last = Date.now();
    o[id] = row;
    try { localStorage.setItem(USE_KEY, JSON.stringify(o)); } catch (e) {}
  }
  function useRec(id) {
    var o = readUse();
    return (id && o[id]) ? o[id] : { n: 0, last: 0 };
  }
  function accountIds() {
    return { user: 1, login: 1, install: 1, pwa: 1 };
  }
  function taskGroupOf(row) {
    var id, path;
    if (!row) return "docs";
    if (row.kind === "parked" || row.run === "parked" || row.live === false) return "parked";
    if (row.kind === "fetch" || row.run === "ask") return "fetch";
    if (row.kind === "queue") return "queue";
    if (row.kind === "game") return "game";
    id = row.id || "";
    path = row.path || "";
    if (row.kind === "set" || accountIds()[id] || path === "/user" || path === "/install") return "account";
    return "docs";
  }
  function catalogNormG(g) {
    g = String(g || "all").toLowerCase();
    if (g === "search") return "fetch";
    if (g === "do" || g === "watch") return "queue";
    if (g === "play") return "game";
    if (g === "fav" || g === "favorites") return "fav";
    if (g === "nav" || g === "set") return "account";
    if (g === "skills" || g === "task" || g === "tasks") return "all";
    return g;
  }
  function catalogRows() {
    var live = [], parked = [], seen = {}, out = [], i, row, key;
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row || !row.id) continue;
      if (row.kind === "parked" || row.run === "parked" || row.live === false) parked.push(row);
      else live.push(row);
    }
    function add(list) {
      for (i = 0; i < list.length; i++) {
        row = list[i];
        if (row.id === "tasks") continue;
        key = row.path ? String(row.path) : ("#" + row.id);
        if (row.id === "home" || row.id === "menu" || row.id === "search") key = "/";
        if (row.id === "doc" || row.id === "docs") key = "/docs";
        if (row.id === "ask") key = "#ask";
        if (row.id === "favorites") key = "#favorites";
        if (row.id === "usage") key = "/usage";
        if (seen[key]) continue;
        seen[key] = 1;
        out.push(row);
      }
    }
    add(live);
    add(parked);
    return out;
  }
  function liveParkedCounts() {
    var live = 0, parked = 0, i, row;
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row) continue;
      if (row.kind === "parked" || row.run === "parked" || row.live === false) parked++;
      else live++;
    }
    return { live: live, parked: parked };
  }
  function paintHomeChips(on) {
    var el = $("home-chips");
    var chips, i, html, c;
    if (!el) return;
    if (!on) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    chips = [
      { href: "/tasks?g=fetch", label: "Search" },
      { href: "/tasks?g=queue", label: "Do" },
      { href: "/tasks?g=game", label: "Play" },
      { href: "/tasks?g=fav", label: "Favorites" },
      { href: "/tasks", label: "All" }
    ];
    html = "";
    for (i = 0; i < chips.length; i++) {
      c = chips[i];
      html += "<button type='button' class='chip' data-path='" + esc(c.href) + "'>" + esc(c.label) + "</button>";
    }
    el.innerHTML = html;
    el.hidden = false;
    el.querySelectorAll("button.chip").forEach(function (b) {
      b.addEventListener("click", function () { go(b.getAttribute("data-path")); });
    });
  }
  function catalogRowHtml(row) {
    var parked = (taskGroupOf(row) === "parked") ? " parked" : "";
    var title = taskTitle(row);
    var hint = taskHint(row);
    var star = isFav(row.id) ? "★" : "☆";
    var on = isFav(row.id) ? " on" : "";
    return "<div class='sel-row'>" +
      "<button type='button' class='star-btn" + on + "' data-fav='" + esc(row.id) + "' aria-label='favorite'>" + star + "</button>" +
      "<button type='button' class='sel" + parked + "' data-tid='" + esc(row.id) + "'>" +
      esc(title) + " <span class='path'>" + esc(hint) + "</span></button></div>";
  }
  function bindCatalogRows(root) {
    if (!root) return;
    root.querySelectorAll("button.star-btn[data-fav]").forEach(function (b) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        toggleFav(b.getAttribute("data-fav"));
        paintTasks();
      });
    });
    root.querySelectorAll("button.sel[data-tid]").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-tid");
        var hit = findTaskByIdOrQ(id, id);
        if (hit) runTask(hit);
      });
    });
  }
  function paintTasks() {
    var g = catalogNormG(hashParam("g") || "all");
    var groups = [
      { id: "fetch", label: "Search" },
      { id: "queue", label: "Do" },
      { id: "game", label: "Play" },
      { id: "account", label: "Account" },
      { id: "docs", label: "Docs" },
      { id: "parked", label: "Parked" }
    ];
    var chips = [
      { id: "fetch", label: "Search" },
      { id: "queue", label: "Do" },
      { id: "game", label: "Play" },
      { id: "account", label: "Account" },
      { id: "docs", label: "Docs" },
      { id: "fav", label: "Favorites" },
      { id: "parked", label: "Parked" },
      { id: "all", label: "All" }
    ];
    var counts = liveParkedCounts();
    var rows = catalogRows();
    var buckets = { fetch: [], queue: [], game: [], account: [], docs: [], parked: [] };
    var html = "", i, row, grp, list, j, chip;
    viewEl.hidden = false;
    if (dirEl) dirEl.hidden = true;
    for (i = 0; i < rows.length; i++) {
      row = rows[i];
      grp = taskGroupOf(row);
      if (!buckets[grp]) buckets[grp] = [];
      buckets[grp].push(row);
    }
    html += "<h2>Tasks/</h2>";
    html += "<p class='info'>tap a skill. GOPHER runs it. Parked stay parked. 100 skills.</p>";
    html += "<p class='info dim task-counts'>" + counts.live + " live · " + counts.parked + " parked</p>";
    html += "<div class='chip-row' id='task-chips'>";
    for (i = 0; i < chips.length; i++) {
      chip = chips[i];
      html += "<button type='button' class='chip" + (g === chip.id ? " active" : "") + "' data-g='" + chip.id + "'>" + esc(chip.label) + "</button>";
    }
    html += "</div>";
    if (g === "fav") {
      list = rows.filter(function (r) { return isFav(r.id); });
      html += "<div class='task-group' data-g='fav'><h3>Favorites</h3><div class='selectors'>";
      if (!list.length) html += "<p class='info dim'>none yet. tap a star.</p>";
      for (j = 0; j < list.length; j++) html += catalogRowHtml(list[j]);
      html += "</div></div>";
    } else {
      for (i = 0; i < groups.length; i++) {
        grp = groups[i];
        if (g !== "all" && g !== grp.id) continue;
        list = buckets[grp.id] || [];
        if (!list.length) continue;
        html += "<div class='task-group' data-g='" + grp.id + "'>";
        html += "<h3>" + esc(grp.label) + "</h3>";
        html += "<div class='selectors'>";
        for (j = 0; j < list.length; j++) html += catalogRowHtml(list[j]);
        html += "</div></div>";
      }
    }
    viewEl.innerHTML = html;
    viewEl.querySelectorAll("#task-chips button.chip").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-g") || "all";
        go(id === "all" ? "/tasks" : "/tasks?g=" + id);
      });
    });
    bindCatalogRows(viewEl);
    viewEl.focus();
  }
  function paintUsage() {
    var use = readUse(), favs = readFavs(), ids, i, rec, row, lines, title;
    viewEl.hidden = false;
    if (dirEl) dirEl.hidden = true;
    ids = Object.keys(use);
    ids.sort(function (a, b) {
      var na = (use[a] && use[a].n) || 0, nb = (use[b] && use[b].n) || 0;
      if (nb !== na) return nb - na;
      return ((use[b] && use[b].last) || 0) - ((use[a] && use[a].last) || 0);
    });
    lines = ["this device only. no cloud. TRACK? still sends nowhere.", "", "top skills"];
    if (!ids.length) lines.push("  none yet. run a skill.");
    for (i = 0; i < ids.length && i < 12; i++) {
      rec = use[ids[i]] || {};
      row = findTaskByIdOrQ(ids[i], ids[i]);
      title = row ? taskTitle(row) : ids[i];
      lines.push("  " + title + "  x" + (rec.n || 0));
    }
    lines.push("", "favorites");
    if (!favs.length) lines.push("  none. tap a star in tasks.");
    for (i = 0; i < favs.length; i++) {
      row = findTaskByIdOrQ(favs[i], favs[i]);
      lines.push("  " + (row ? taskTitle(row) : favs[i]));
    }
    viewEl.innerHTML = "<h2>Usage/</h2><p class='info'>on-device counts. GOPHER does not send this anywhere.</p><pre class='gopher-doc'>" + esc(lines.join("\n")) + "</pre>";
    viewEl.focus();
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
    replyOpen = true;
    resetPrompt();
    if (heroEl) heroEl.hidden = false;
    authEl.hidden = true;
    gameEl.hidden = true;
    if (digEl) digEl.hidden = true;
    if (game) game.stop();
    if (dig) dig.stop();
    if (askEl) askEl.hidden = false;
    viewEl.hidden = false;
    viewEl.innerHTML =
      "<h2><span class='itype'>0</span> " + esc(title || "GOPHER") + "</h2>" +
      "<pre class='gopher-doc'>" + esc(text || "") + "</pre>";
    viewEl.focus();
  }

  function render() {
    var path = pathNow();
    var gameOn = (path === "/fetch" || path === "/dig");
    var host = $("host");
    if (host) host.textContent = "gopher://gopher.ai:70" + path;
    document.title = path === "/fetch"
      ? "MAZE — GOPHER AI"
      : (path === "/dig" ? "BURROW — GOPHER AI" : (path === "/" ? "GOPHER AI" : ("GOPHER AI " + path)));
    paintStaging();
    renderDir(path);
    paintWho();
    hideSpecial();
    replyOpen = false;
    if (dirEl) dirEl.hidden = gameOn || path === "/";
    if (askEl) askEl.hidden = false;
    if (heroEl) heroEl.hidden = false;
    document.body.classList.toggle("home-on", path === "/");
    document.body.classList.toggle("game-on", gameOn);
    showWaitForm(path === "/waitlist");
    paintTopbar(path);
    if (gameOn) {
      var cmdGame = $("command");
      if (cmdGame && !(cmdGame.value || "").trim() && TASKS.length) paintSuggest(idleSlice(), { idle: true });
    }

    paintHomeChips(path === "/");
    if (path === "/tasks") {
      paintTasks();
      return;
    }
    if (path === "/usage") {
      paintUsage();
      return;
    }
    if (path === "/" || path === "/waitlist") {
      if (path === "/waitlist") {
        var em = $("email");
        if (em) em.focus();
      }
      return;
    }

    if (path === "/user") {
      authEl.hidden = false;
      var s = session();
      $("auth-out").hidden = !s;
      if (s) setStatus($("auth-status"), "ok", "you’re in as " + s.name + ".");
      return;
    }
    if (path === "/fetch") {
      gameEl.hidden = false;
      var canvas = $("fetch");
      if (canvas) canvas.setAttribute("aria-live", "polite");
      bootGame();
      questMark("play");
      return;
    }
    if (path === "/dig") {
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
    if (path === "/orders") {
      paintOrders();
      return;
    }
    if (path === "/scores") {
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
      return;
    }
    viewEl.hidden = false;
    viewEl.innerHTML = "<h2>" + esc(doc.title || path) + "</h2>" + docHtml(doc);
    viewEl.focus();
    if (path === "/plugins") appendLivePlugins();
  }

  function shoutHud(msg, id) {
    var el = $(id || "g-shout");
    var text = String(msg == null ? "" : msg);
    var ouch = /Ouchies|TIME OVER|CRUSHED|CLUNK/.test(text);
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
    viewEl.innerHTML = "<h2>0 Status/</h2><p class='info'>honest liveness. no fake uptime graph. not a SLA.</p><pre class='gopher-doc' id='status-pre'>checking…</pre>";
    var el = $("status-pre");
    fetch("/api/status", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
      .then(function (d) {
        var p = (d && d.plugins) || {};
        var lines = [
          "hole     python",
          "uptime   " + (d && d.uptime_s != null ? d.uptime_s + "s" : "?"),
          "started  " + ((d && d.started) || ""),
          "requests " + ((d && d.requests) || 0),
          "sla      " + (d && d.sla === true ? "true" : "false"),
          "ticker   " + (p.ticker ? "live" : "parked"),
          "fng      " + (p.fng ? "live" : "parked"),
          "twilio   " + ((d && d.twilio) || "parked"),
          "sms      " + (p.sms ? "ready" : "parked"),
          "voice    " + (p.voice ? "ready" : "parked"),
          "mail     " + ((d && d.mail) || "parked"),
          "llm      " + ((d && d.llm) || "parked"),
          "telegram " + ((d && d.telegram) || "parked"),
          "price    $19/month",
          "checkout parked",
          "billing  parked"
        ];
        if (el) el.textContent = lines.join("\n");
      })
      .catch(function () {
        if (el) el.textContent = "Pages hole: static files.\npython /api/status: no process.\nIf this page loaded, the static hole is up.\nnot a SLA.";
      });
  }
  function appendLivePlugins() {
    fetch("/api/status", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
      .then(function (d) {
        var p = (d && d.plugins) || {};
        var line = "live python: ticker=" + (p.ticker ? "live" : "parked")
          + " fng=" + (p.fng ? "live" : "parked")
          + " sms=" + (p.sms ? "ready" : "parked")
          + " voice=" + (p.voice ? "ready" : "parked")
          + " mail=" + ((d && d.mail) || "parked")
          + " llm=" + ((d && d.llm) || "parked")
          + " telegram=" + ((d && d.telegram) || "parked")
          + " billing=" + (p.billing ? "ready" : "parked")
          + " twilio=" + ((d && d.twilio) || "parked")
          + " sla=" + (d && d.sla === true ? "true" : "false");
        var pre = document.createElement("pre");
        pre.className = "gopher-doc";
        pre.textContent = line;
        if (viewEl) viewEl.appendChild(pre);
      })
      .catch(function () { /* Pages: keep parked hole copy */ });
  }
  function paintOrders() {
    viewEl.hidden = false;
    askEl.hidden = false;
    viewEl.innerHTML = "<h2>0 Orders/</h2><p class='info'>last asks. no emails. not SMS. waitlist is the door. checkout parked.</p><pre class='gopher-doc' id='orders-pre'>loading…</pre>";
    var el = $("orders-pre");
    var local = readKinds().map(function (r, i) {
      return String(i + 1).padStart(2, " ") + "  device  " + String((r && r.kind) || "order") + "  " + String((r && r.q) || "");
    });
    var txt = local.length ? ("device\n" + local.join("\n")) : "device    empty";
    fetch("/api/orders", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : []; })
      .then(function (rows) {
        if (Array.isArray(rows) && rows.length) {
          txt += "\n\npython\n";
          rows.forEach(function (r, i) {
            txt += String(i + 1).padStart(2, " ") + "  " + String((r && r.at) || "").slice(11, 19) + "  " + String((r && r.q) || "") + "\n";
          });
        } else {
          txt += "\n\npython    empty (needs server.py)";
        }
        if (el) el.textContent = txt;
      })
      .catch(function () {
        if (el) el.textContent = txt + "\n\npython    offline";
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
          var a = $("d-score"), b = $("d-lvl"), c = $("d-lives"), d = $("d-gems");
          if (a) a.textContent = "score " + (g.score || 0);
          if (b) b.textContent = "lvl " + (g.lvl || 1);
          if (c) c.textContent = "lives " + (g.lives || 0);
          if (d) d.textContent = "gems " + (g.gemsLeft != null ? g.gemsLeft : 0);
          if (g.dead) setStatus($("d-status"), "err", t("digDead"));
          else if (g.win) setStatus($("d-status"), "ok", t("digWin"));
        },
        onShout: function (text) { shoutHud(text, "d-shout"); }
      });
    }
    if (dig.draw) dig.draw();
  }

  /* autoprompt: ranked Gopher selectors for the 100-task catalog */
  function prefersLessMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (e) {
      return false;
    }
  }
  function taskTitle(row) {
    if (!row) return "";
    return (document.documentElement.lang === "es" && row.title_es) ? row.title_es : (row.title || row.q || "");
  }
  function taskHint(row) {
    if (!row) return "";
    return (document.documentElement.lang === "es" && row.hint_es) ? row.hint_es : (row.hint || "");
  }
  function gopherType(row) {
    if (!row) return "1";
    if (row.kind === "fetch") return "0";
    if (row.kind === "parked") return "3";
    if (row.kind === "queue") return "7";
    return "1";
  }
  function liveTasks() {
    var out = [], i;
    for (i = 0; i < TASKS.length; i++) {
      if (TASKS[i] && TASKS[i].live) out.push(TASKS[i]);
    }
    return out;
  }
  function rankNeedle(text, q) {
    var str, re;
    if (!text) return 0;
    str = String(text).toLowerCase();
    if (str === q) return 100;
    if (str.indexOf(q) === 0) return 80;
    try {
      re = new RegExp("(^|[^a-z0-9])" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      if (re.test(str)) return 60;
    } catch (e) {}
    if (str.indexOf(q) >= 0) return 40;
    return 0;
  }
  function rankTask(row, q) {
    var best = 0, n, i, fields;
    if (!row || !q) return 0;
    fields = [row.q, row.title, row.title_es, row.hint, row.hint_es, row.id];
    if (row.aliases && row.aliases.length) {
      for (i = 0; i < row.aliases.length; i++) fields.push(row.aliases[i]);
    }
    for (i = 0; i < fields.length; i++) {
      n = rankNeedle(fields[i], q);
      if (n > best) best = n;
    }
    return best;
  }
  function findTaskByIdOrQ(id, q) {
    var i, row, lowId = (id || "").toLowerCase(), lowQ = (q || "").toLowerCase();
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row) continue;
      if (lowId && (row.id || "").toLowerCase() === lowId) return row;
    }
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row) continue;
      if (lowQ && (row.q || "").toLowerCase() === lowQ) return row;
    }
    return null;
  }
  function searchExample() {
    return { id: "fetch-btc", q: "fetch btc", title: "fetch btc", title_es: "fetch btc", hint: "live BTC price", hint_es: "precio BTC en vivo", kind: "fetch", run: "ask", live: true };
  }
  function idleHard() {
    return [
      { id: "ask", q: "ask gopher", title: "ask gopher", title_es: "ask gopher", hint: "freeform brain", hint_es: "cerebro libre", kind: "fetch", run: "ask", live: true },
      { id: "tasks", q: "tasks", title: "tasks", title_es: "tareas", hint: "100 skills · tap one", hint_es: "100 skills · toca una", kind: "nav", run: "nav", live: true, path: "/tasks" },
      { id: "waitlist", q: "waitlist", title: "waitlist", title_es: "waitlist", hint: "get in line", hint_es: "entra a la lista", kind: "nav", run: "nav", live: true, path: "/waitlist" }
    ];
  }
  function hasId(list, id) {
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === id) return true;
    }
    return false;
  }
  function sortLearned(scored) {
    scored.sort(function (a, b) {
      if (b.fav !== a.fav) return b.fav - a.fav;
      if (b.n !== a.n) return b.n - a.n;
      if (b.last !== a.last) return b.last - a.last;
      if (b.live !== a.live) return b.live - a.live;
      return (b.score || 0) - (a.score || 0);
    });
    return scored;
  }
  function idleSlice() {
    var hard = idleHard(), out = [], scored = [], i, row, rec, hit, use, favs;
    favs = readFavs();
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row || !row.id) continue;
      rec = useRec(row.id);
      scored.push({
        row: row,
        fav: favs.indexOf(row.id) >= 0 ? 1 : 0,
        n: rec.n || 0,
        last: rec.last || 0,
        live: row.live ? 1 : 0,
        score: 0
      });
    }
    sortLearned(scored);
    for (i = 0; i < scored.length && out.length < SUG_IDLE; i++) {
      if (scored[i].fav || scored[i].n > 0) out.push(scored[i].row);
    }
    for (i = 0; i < hard.length && out.length < SUG_IDLE; i++) {
      row = hard[i];
      hit = findTaskByIdOrQ(row.id, row.q);
      use = hit || row;
      if (hasId(out, use.id)) continue;
      out.push(use);
    }
    return out.slice(0, SUG_IDLE);
  }
  function noMatchRows() {
    var parked = [], out = [], i, row;
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (row && (row.kind === "parked" || row.run === "parked")) parked.push(row);
    }
    out = parked.slice(0, 2);
    out.push({
      id: "no-match",
      q: "tasks",
      title: "no match · try ask gopher or tasks",
      title_es: "sin match · prueba ask gopher o tasks",
      hint: "type an order",
      hint_es: "escribe una orden",
      kind: "nav",
      run: "nav",
      live: true,
      path: "/tasks"
    });
    return out.slice(0, SUG_MAX);
  }
  function rankTop(q) {
    var i, row, score, best = null;
    q = (q || "").toLowerCase().trim();
    if (!q) return null;
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      score = rankTask(row, q);
      if (score <= 0) continue;
      if (!best || score > best.score || (score === best.score && row.live && !best.row.live)) {
        best = { row: row, score: score };
      }
    }
    return best;
  }
  function filterTasks(q) {
    var i, row, score, scored = [], favs, rec;
    q = (q || "").toLowerCase().trim();
    if (!q) return idleSlice();
    favs = readFavs();
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      score = rankTask(row, q);
      if (score <= 0) continue;
      rec = useRec(row.id);
      scored.push({
        row: row,
        score: score,
        fav: favs.indexOf(row.id) >= 0 ? 1 : 0,
        n: rec.n || 0,
        last: rec.last || 0,
        live: row.live ? 1 : 0
      });
    }
    if (!scored.length) return noMatchRows();
    sortLearned(scored);
    return scored.slice(0, SUG_MAX).map(function (item) { return item.row; });
  }
  function suggestEl() {
    return $("suggest");
  }
  function setSugExpanded(on) {
    var cmd = $("command");
    sugOpen = !!on;
    if (cmd) cmd.setAttribute("aria-expanded", on ? "true" : "false");
    if (!on && cmd) cmd.removeAttribute("aria-activedescendant");
  }
  function hideSuggest() {
    sugHi = -1;
    paintSuggest(idleSlice(), { idle: true, hi: -1 });
  }
  function syncSugAria() {
    var cmd = $("command");
    if (!cmd) return;
    if (sugOpen && sugHi >= 0) cmd.setAttribute("aria-activedescendant", "sug-" + sugHi);
    else cmd.removeAttribute("aria-activedescendant");
  }
  function paintSuggest(items, opts) {
    var el = suggestEl(), html = "", i, row, hi, title, hint;
    opts = opts || {};
    if (!el) return;
    if (items && items.length > SUG_MAX) items = items.slice(0, SUG_MAX);
    if (!items || !items.length) {
      if (!opts._idleRetry) {
        paintSuggest(idleSlice(), { idle: true, _idleRetry: true });
        return;
      }
      el.hidden = false;
      el.classList.add("idle");
      sugItems = [searchExample()];
      el.innerHTML = "<li role='option' id='sug-0' aria-selected='true'><button type='button' class='sel active'>" + esc(sugItems[0].title) + " <span class='path'>" + esc(sugItems[0].hint) + "</span></button></li>";
      sugHi = 0;
      setSugExpanded(true);
      return;
    }
    sugItems = items;
    if (opts.hi == null) sugHi = 0;
    else sugHi = opts.hi;
    if (sugHi >= items.length) sugHi = items.length - 1;
    html = "";
    for (i = 0; i < items.length; i++) {
      row = items[i];
      title = taskTitle(row);
      hint = taskHint(row);
      hi = (i === sugHi) ? " active" : "";
      html += "<li role='option' id='sug-" + i + "' aria-selected='" + (i === sugHi ? "true" : "false") + "'>" +
        "<button type='button' class='sel" + hi + "' data-sug='" + i + "'>" +
        esc(title) +
        " <span class='path'>" + esc(hint) + "</span></button></li>";
    }
    el.innerHTML = html;
    el.hidden = false;
    el.classList.toggle("idle", !!opts.idle);
    (function () {
      var cap = $("sug-cap");
      if (cap) cap.textContent = opts.idle ? t("sugCap") : t("sugCapMatch");
    })();
    setSugExpanded(true);
    el.querySelectorAll("button.sel").forEach(function (b) {
      b.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
      b.addEventListener("click", function () {
        var n = +b.getAttribute("data-sug");
        if (sugItems[n]) runTask(sugItems[n]);
      });
    });
    syncSugAria();
  }
  function moveSug(dir) {
    if (!sugItems.length) return;
    if (sugHi < 0) sugHi = dir > 0 ? 0 : sugItems.length - 1;
    else sugHi = (sugHi + dir + sugItems.length) % sugItems.length;
    paintSuggest(sugItems, { hi: sugHi });
  }
  function acceptSug() {
    var row, cmd;
    if (sugHi < 0 || !sugItems[sugHi]) return;
    row = sugItems[sugHi];
    cmd = $("command");
    if (cmd) cmd.value = row.q || "";
    paintSuggest(filterTasks(cmd && cmd.value), { hi: 0 });
  }
  function parkedLine(row) {
    var id = (row && row.id) || "";
    if (id === "sms") return "parked. no SMS number. see plugins";
    if (id === "voice") return "parked. no voice number. see plugins";
    if (id === "mail") return "parked until RESEND_API_KEY or GOPHER_MAIL_HOOK. see plugins";
    if (id === "billing") return "parked. no Stripe checkout. $19/month is public. see pricing";
    if (id === "telegram") return "parked until TELEGRAM_BOT_TOKEN. no bot username. see plugins";
    if (id === "prices") return "$19/month. waitlist is the door. see pricing";
    if (id === "domain") return "parked. no custom domain. see blueprint";
    if (id === "cloud-accounts") return "parked. device login only. see plugins";
    if (id === "sla") return "parked. no SLA. see blueprint";
    if (id === "hiring") return "parked. not hiring. see jobs";
    return "parked. see plugins";
  }
  function afterHole(path, fn) {
    if (pathNow() === path) {
      fn();
      return;
    }
    go(path);
    setTimeout(fn, 40);
  }
  function runSet(row) {
    var id = row.id, on, helpEl, gp, gm;
    if (id === "spanish") {
      applyLang("es");
      setStatus($("ask-status"), "ok", "ok. spanish");
      return;
    }
    if (id === "english") {
      applyLang("en");
      setStatus($("ask-status"), "ok", "ok. english");
      return;
    }
    if (id === "high-contrast") {
      applyHc(!document.documentElement.classList.contains("high-contrast"));
      setStatus($("ask-status"), "ok", "ok. high contrast");
      return;
    }
    if (id === "track") {
      on = !readTrack();
      writeTrack(on);
      paintTrackBtn();
      setStatus($("ask-status"), "ok", on ? "ok. track (this device, no beacon)" : "ok. track off");
      return;
    }
    if (id === "help") {
      helpEl = $("help");
      if (helpEl) helpEl.hidden = false;
      setStatus($("ask-status"), "ok", "ok. help");
      return;
    }
    if (id === "fetch-pause") {
      afterHole("/fetch", function () {
        if (!game) bootGame();
        if (game && game.pauseToggle) game.pauseToggle();
        gp = $("g-pause");
        if (gp && game) gp.textContent = game.paused ? "RESUME" : "PAUSE";
        setStatus($("ask-status"), "ok", "ok. fetch pause");
        if (game) setStatus($("g-status"), "", game.paused ? t("fetchPaused") : t("fetchPlay"));
      });
      return;
    }
    if (id === "fetch-key") {
      afterHole("/fetch", function () {
        if (!game) bootGame();
        toggleKeyCard();
        setStatus($("ask-status"), "ok", "ok. fetch key");
      });
      return;
    }
    if (id === "fetch-mute") {
      afterHole("/fetch", function () {
        if (!game) bootGame();
        if (game) {
          game.mute = true;
          gm = $("g-mute");
          if (gm) gm.textContent = "MUTE";
        }
        setStatus($("ask-status"), "ok", "ok. fetch mute");
      });
      return;
    }
    if (id === "fetch-sound") {
      afterHole("/fetch", function () {
        if (!game) bootGame();
        if (game) {
          game.mute = false;
          gm = $("g-mute");
          if (gm) gm.textContent = "SOUND";
        }
        setStatus($("ask-status"), "ok", "ok. fetch sound");
      });
      return;
    }
    if (id === "share-score") {
      shareScore();
      setStatus($("ask-status"), "ok", "ok. share score");
      return;
    }
    setStatus($("ask-status"), "ok", "ok. " + (row.q || id));
  }
  function runTask(row) {
    var q, line;
    if (!row) return;
    q = row.q || row.id || "";
    bumpUse(row.id);
    threadAppend("you", q);
    if (row.run === "parked" || row.kind === "parked") {
      resetPrompt();
      line = parkedLine(row);
      threadAppend("gopher", line);
      if (row.path) go(row.path);
      setBrain("parked", line);
      return;
    }
    if (row.run === "nav") {
      resetPrompt();
      threadAppend("gopher", "ok. " + q);
      if (row.path) go(row.path);
      setBrain("ok", "ok. " + q);
      return;
    }
    if (row.run === "queue") {
      resetPrompt();
      threadAppend("gopher", "queued on this device. not SMS.");
      queueKindOrder(q);
      return;
    }
    if (row.run === "set") {
      resetPrompt();
      threadAppend("gopher", "ok. " + q);
      runSet(row);
      setBrain("ok", "ok. " + q);
      return;
    }
    if (row.run === "ask") {
      askGopher(q, { skipYou: true });
      return;
    }
    if (row.path) {
      resetPrompt();
      threadAppend("gopher", "ok. " + q);
      go(row.path);
    } else askGopher(q, { skipYou: true });
  }
  function findTaskExact(q) {
    var i, row, low, j;
    low = (q || "").toLowerCase().trim();
    if (!low) return null;
    for (i = 0; i < TASKS.length; i++) {
      row = TASKS[i];
      if (!row) continue;
      if ((row.id || "").toLowerCase() === low) return row;
      if ((row.q || "").toLowerCase() === low) return row;
      if (row.aliases && row.aliases.length) {
        for (j = 0; j < row.aliases.length; j++) {
          if (String(row.aliases[j] || "").toLowerCase() === low) return row;
        }
      }
    }
    return null;
  }

  function handleOrder(q) {
    var hit, task, top, alias, cmd, form, n;
    q = (q || "").trim();
    if (!q) return;
    cmd = $("command");
    if (/^[0-9]$/.test(q)) {
      n = +q;
      if (cmd && document.activeElement === cmd && sugItems[n - 1]) {
        runTask(sugItems[n - 1]);
        return;
      }
      hit = itemsByN()[q];
      if (hit && hit.path) {
        resetPrompt();
        threadAppend("you", q);
        threadAppend("gopher", "ok. " + q);
        go(hit.path);
        setBrain("ok", "ok. " + q);
        return;
      }
      return;
    }
    task = findTaskExact(q);
    if (task) {
      runTask(task);
      return;
    }
    top = rankTop(q);
    if (top && top.score >= 80) {
      runTask(top.row);
      return;
    }
    if (kindOrder(q)) {
      resetPrompt();
      threadAppend("you", q);
      threadAppend("gopher", "queued on this device. not SMS.");
      queueKindOrder(q);
      return;
    }
    alias = ALIAS[q.toLowerCase()];
    if (alias) {
      resetPrompt();
      threadAppend("you", q);
      threadAppend("gopher", "ok. " + q);
      go(alias);
      setBrain("ok", "ok. " + q);
      return;
    }
    if (EMAIL_RE.test(q)) {
      resetPrompt();
      threadAppend("you", q);
      threadAppend("gopher", "ok. waitlist");
      if ($("email")) $("email").value = q;
      go("/waitlist");
      showWaitForm(true);
      form = $("form");
      if (form && form.requestSubmit) form.requestSubmit();
      return;
    }
    askGopher(q);
  }
  function stopIdleSpin() {
    if (idleTimer) {
      clearInterval(idleTimer);
      idleTimer = 0;
    }
    if (phTimer) {
      clearInterval(phTimer);
      phTimer = 0;
    }
  }
  function showIdleSuggest() {
    stopIdleSpin();
    paintSuggest(idleSlice(), { idle: true });
  }
  function paintMatchBrain(items) {
    var row = items && items[0];
    var cap = $("sug-cap");
    if (cap) cap.textContent = t("sugCapMatch");
    if (!row || row.id === "no-match") {
      setBrain("match", "no match · tap a skill");
      return;
    }
    setBrain("match", "matched · " + taskTitle(row));
  }
  function onPromptInput() {
    var cmd = $("command");
    var q = cmd ? (cmd.value || "") : "";
    var items;
    if (!q.trim()) {
      showIdleSuggest();
      setBrain("ready");
      return;
    }
    stopIdleSpin();
    items = filterTasks(q);
    paintSuggest(items, { idle: false });
    paintMatchBrain(items);
  }
  function onPromptFocus() {
    var cmd = $("command");
    if (cmd && !(cmd.value || "").trim()) showIdleSuggest();
    else onPromptInput();
  }
  function onPromptBlur() {
    setTimeout(function () {
      var cmd = $("command");
      if (cmd && document.activeElement === cmd) return;
      if (cmd && !(cmd.value || "").trim()) showIdleSuggest();
    }, 160);
  }
  function onPromptKey(e) {
    var cmd = $("command");
    var empty = cmd && !(cmd.value || "").trim();
    if (empty && /^[1-3]$/.test(e.key) && sugItems[+e.key - 1]) {
      e.preventDefault();
      runTask(sugItems[+e.key - 1]);
      return;
    }
    if (e.key === "ArrowDown") {
      if (!sugItems.length) {
        if (empty) showIdleSuggest();
        else onPromptInput();
      }
      if (sugItems.length) {
        e.preventDefault();
        moveSug(1);
      }
      return;
    }
    if (e.key === "ArrowUp") {
      if (sugItems.length) {
        e.preventDefault();
        moveSug(-1);
      }
      return;
    }
    if (e.key === "Tab") {
      if (sugHi >= 0 && sugItems[sugHi]) {
        e.preventDefault();
        acceptSug();
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      if (e.target && e.target.blur) e.target.blur();
      if (replyOpen) go("/");
      return;
    }
    if (e.key === "Enter") {
      var typed = cmd ? (cmd.value || "").trim() : "";
      if (typed) return;
      if (sugHi >= 0 && sugItems[sugHi] && sugItems[sugHi].id !== "no-match") {
        e.preventDefault();
        runTask(sugItems[sugHi]);
      }
    }
  }
  function startPlaceholders() {
    var cmd = $("command");
    if (!cmd) return;
    stopIdleSpin();
    cmd.placeholder = DEFAULT_PH;
  }
  function fallbackTasks() {
    var out = [], seen = {}, path, hole, alias, coins, i, q, id;
    function add(row) {
      if (!row || !row.id || seen[row.id]) return;
      seen[row.id] = 1;
      out.push(row);
    }
    for (path in HOLES) {
      if (!Object.prototype.hasOwnProperty.call(HOLES, path)) continue;
      hole = HOLES[path] || {};
      id = "nav-" + (path === "/" ? "home" : path.replace(/^\//, "").replace(/\W+/g, "-"));
      q = path === "/" ? "home" : path.replace(/^\//, "").replace(/\//g, " ");
      add({
        id: id,
        q: q,
        title: hole.title || q,
        title_es: hole.title_es || hole.title || q,
        hint: "directory",
        hint_es: "directorio",
        kind: "nav",
        run: "nav",
        live: true,
        path: path
      });
    }
    for (alias in ALIAS) {
      if (!Object.prototype.hasOwnProperty.call(ALIAS, alias)) continue;
      add({
        id: "alias-" + alias,
        q: alias,
        title: alias,
        title_es: alias,
        hint: ALIAS[alias],
        hint_es: ALIAS[alias],
        kind: "nav",
        run: "nav",
        live: true,
        path: ALIAS[alias]
      });
    }
    coins = ["btc", "eth", "sol", "xrp", "doge", "ada", "fg"];
    for (i = 0; i < coins.length; i++) {
      add({
        id: "fetch-" + coins[i],
        q: "fetch " + coins[i],
        title: "fetch " + coins[i],
        title_es: "fetch " + coins[i],
        hint: "live ticker",
        hint_es: "ticker en vivo",
        kind: "fetch",
        run: "ask",
        live: true
      });
    }
    return out;
  }
  function loadTasks() {
    fetch("tasks.json", { headers: { Accept: "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("no tasks");
        return res.json();
      })
      .then(function (data) {
        var list = data && data.tasks;
        TASKS = Array.isArray(list) ? list.filter(function (row) { return row && row.id && row.q; }) : [];
        if (!TASKS.length) TASKS = fallbackTasks();
        startPlaceholders();
        paintSuggest(idleSlice(), { idle: true });
        showIdleSuggest();
        setBrain("ready");
      })
      .catch(function () {
        TASKS = fallbackTasks();
        startPlaceholders();
        paintSuggest(idleSlice(), { idle: true });
        showIdleSuggest();
        setBrain("ready");
      });
  }
  function bindChromeHome() {
    var nav = $("chrome");
    if (!nav || nav.getAttribute("data-home-bound") === "1") return;
    nav.setAttribute("data-home-bound", "1");
    nav.addEventListener("click", function (e) {
      var a = e.target;
      while (a && a !== nav && !(a.getAttribute && a.getAttribute("data-nav"))) a = a.parentNode;
      if (!a || a.getAttribute("data-nav") !== "home") return;
      if (pathNow() === "/") {
        e.preventDefault();
        render();
      }
    });
  }
  function bindPrompt() {
    var cmd = $("command");
    if (!cmd) return;
    cmd.setAttribute("role", "combobox");
    cmd.setAttribute("aria-autocomplete", "list");
    cmd.setAttribute("aria-controls", "suggest");
    cmd.setAttribute("aria-expanded", "true");
    cmd.addEventListener("input", onPromptInput);
    cmd.addEventListener("focus", onPromptFocus);
    cmd.addEventListener("blur", onPromptBlur);
    cmd.addEventListener("keydown", onPromptKey);
  }

  function queueLocal(q) {
    try { localStorage.setItem("gopher_first_order", q); } catch (err) {}
    setBrain("ok", "ok. " + q);
    if ($("email")) $("email").focus();
  }

  function resetPrompt() {
    var cmd = $("command");
    if (cmd) {
      cmd.value = "";
      cmd.placeholder = DEFAULT_PH;
    }
    paintSuggest(idleSlice(), { idle: true });
  }

  function onPages() {
    try {
      return (location.hostname || "").indexOf("github.io") !== -1;
    } catch (e) {
      return false;
    }
  }

  function probeHole() {
    if (onPages()) {
      holeLive = false;
      holeProbed = true;
      return;
    }
    fetch("api/status", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
      .then(function () {
        holeLive = true;
        holeProbed = true;
      })
      .catch(function () {
        holeLive = false;
        holeProbed = true;
      });
  }

  var threadN = 0;
  function threadEl() { return $("thread"); }
  function threadAppend(who, text, opts) {
    var el = threadEl(), line, lab, body, id;
    opts = opts || {};
    if (!el) return "";
    threadN += 1;
    id = opts.id || ("t" + threadN);
    line = document.createElement("div");
    line.className = "thread-line " + (who === "you" ? "you" : "gopher");
    line.setAttribute("data-tid", id);
    lab = document.createElement("span");
    lab.className = "thread-who";
    lab.textContent = who === "you" ? "you" : "GOPHER";
    body = document.createElement("span");
    body.className = "thread-text";
    body.textContent = text || "";
    line.appendChild(lab);
    line.appendChild(document.createTextNode(" "));
    line.appendChild(body);
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
    return id;
  }
  function threadSet(id, text) {
    var el = threadEl(), node;
    if (!el || !id) return;
    node = el.querySelector('[data-tid="' + id + '"] .thread-text');
    if (node) node.textContent = text || "";
    el.scrollTop = el.scrollHeight;
  }
  function placeholderOut(out) {
    var t = String(out || "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!t) return true;
    if (t.indexOf("queued in the hole") === 0) return true;
    if (t.indexOf("sent to gopher") === 0) return true;
    if (t.indexOf("gopher is fetching") === 0) return true;
    return false;
  }
  function orderOutFromRows(rows, oid, q) {
    var i, row, out;
    if (!Array.isArray(rows)) return "";
    for (i = rows.length - 1; i >= 0; i--) {
      row = rows[i];
      if (!row) continue;
      if (oid && String(row.id || "") === String(oid)) {
        out = row.out || "";
        if (!placeholderOut(out)) return out;
      }
    }
    if (!oid && q) {
      for (i = rows.length - 1; i >= 0; i--) {
        row = rows[i];
        if (row && String(row.q || "") === String(q)) {
          out = row.out || "";
          if (!placeholderOut(out)) return out;
        }
      }
    }
    return "";
  }
  function pollAsk(oid, q, lineId, started) {
    var left = 20000 - (Date.now() - started);
    if (left <= 0) {
      threadSet(lineId, "GOPHER is still fetching. see orders.");
      setBrain("ok", "queued");
      return;
    }
    function again() {
      setTimeout(function () { pollAsk(oid, q, lineId, started); }, 800);
    }
    function check(rows) {
      var out = orderOutFromRows(rows, oid, q);
      if (out) {
        threadSet(lineId, out);
        setBrain("ok", "ok.");
        return;
      }
      again();
    }
    fetch(apiUrl("/api/order") + "?id=" + encodeURIComponent(oid || ""), { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (one) {
        var out;
        if (one && typeof one === "object" && !Array.isArray(one)) {
          out = one.out || "";
          if (!placeholderOut(out)) {
            threadSet(lineId, out);
            setBrain("ok", "ok.");
            return;
          }
        }
        return fetch(apiUrl("/api/orders"), { headers: { Accept: "application/json" } })
          .then(function (res) { return res.ok ? res.json() : []; })
          .then(check);
      })
      .catch(again);
  }

  function askGopher(q, opts) {
    var lineId, pages;
    opts = opts || {};
    q = (q || "").trim();
    if (!q) return;
    if (!opts.skipYou) threadAppend("you", q);
    if (kindOrder(q)) {
      resetPrompt();
      threadAppend("gopher", "queued on this device. not SMS.");
      queueKindOrder(q);
      return;
    }
    if (looksTicker(q)) {
      clientFetch(q);
      return;
    }
    pages = !brainUrl && (onPages() || (holeProbed && !holeLive));
    if (pages) {
      clientBrain(q);
      return;
    }
    resetPrompt();
    lineId = threadAppend("gopher", "GOPHER is fetching\u2026");
    setBrain("think", "fetching\u2026");
    fetch(apiUrl("/api/ask"), {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ q: q })
    })
      .then(function (res) {
        return res.json().then(function (body) { return body; }).catch(function () { return null; });
      })
      .then(function (body) {
        var oid, text;
        if (!body || (body.ok !== true && body.kind !== "doc" && body.kind !== "queued")) {
          threadSet(lineId, "brain parked on this static hole. matcher still runs skills.");
          setBrain("parked", "brain parked");
          return;
        }
        if (body.kind === "doc") {
          threadSet(lineId, body.text || "");
          if (body.ok === false) setBrain("err", body.text || "fetch failed.");
          else {
            setBrain("ok", "ok. " + q);
            questMark("fetch");
          }
          return;
        }
        if (body.kind === "queued") {
          try { localStorage.setItem("gopher_first_order", q); } catch (err) {}
          oid = body.id || "";
          text = body.text || "queued in the hole.";
          threadSet(lineId, "GOPHER is fetching\u2026");
          setBrain("think", "fetching\u2026");
          if (oid) pollAsk(oid, q, lineId, Date.now());
          else {
            threadSet(lineId, text);
            setBrain("ok", "ok. " + q);
          }
          return;
        }
        threadSet(lineId, "brain parked on this static hole. matcher still runs skills.");
        setBrain("parked", "brain parked");
      })
      .catch(function () {
        threadSet(lineId, "brain parked on this static hole. matcher still runs skills.");
        setBrain("parked", "brain parked");
      });
  }

  function looksTicker(q) {
    if (/\bfng\b|fear\s*greed|\bfg\b/i.test(q || "")) return false;
    return /fetch|price|ticker|btc|eth|sol|xrp|doge|ada|bitcoin|ethereum|solana|cardano|dogecoin|ripple|link|uni|avax|matic|dot|atom|near|apt|sui|ton/i.test(q || "");
  }
  function tickerId(q) {
    var low = (q || "").toLowerCase();
    var map = {
      bitcoin: "BTC", btc: "BTC",
      ethereum: "ETH", eth: "ETH",
      solana: "SOL", sol: "SOL",
      ripple: "XRP", xrp: "XRP",
      dogecoin: "DOGE", doge: "DOGE",
      cardano: "ADA", ada: "ADA",
      link: "LINK", uni: "UNI", avax: "AVAX", matic: "MATIC",
      dot: "DOT", atom: "ATOM", near: "NEAR", apt: "APT",
      sui: "SUI", ton: "TON"
    };
    var k, best = "", hit = "BTC";
    for (k in map) {
      if (!Object.prototype.hasOwnProperty.call(map, k)) continue;
      if (low.indexOf(k) >= 0 && k.length >= best.length) {
        best = k;
        hit = map[k];
      }
    }
    return hit;
  }
  function helpDoc() {
    var line = "ask gopher   freeform brain\ntasks        100 skills · tap one\nwaitlist     get in line\nfetch btc    live BTC price\n\ntype an order or tap a row.";
    threadAppend("gopher", line);
    setBrain("ok", "try ask gopher \u00b7 tasks \u00b7 waitlist");
  }
  function parkedBrainLine() {
    return "brain parked on this static hole. matcher still runs skills.";
  }
  function clientBrain(q) {
    if (kindOrder(q)) {
      resetPrompt();
      threadAppend("gopher", "queued on this device. not SMS.");
      queueKindOrder(q);
      return;
    }
    if (looksTicker(q)) {
      clientFetch(q);
      return;
    }
    resetPrompt();
    threadAppend("gopher", parkedBrainLine());
    setBrain("parked", "brain parked");
  }
  function stashSpot(id, amt) {
    try {
      sessionStorage.setItem(SPOT_KEY, JSON.stringify({ id: id, amt: amt, at: Date.now() }));
    } catch (err) {}
  }
  function showSpot(id, amt, src, q, lineId) {
    var text = id + "-USD\n\nlast      " + amt + "\n\nsource    " + src;
    if (lineId) threadSet(lineId, text);
    else threadAppend("gopher", text);
    setBrain("ok", "ok. " + (q || id));
    questMark("fetch");
  }
  function spotFromCache(id) {
    var stash = null;
    try { stash = JSON.parse(sessionStorage.getItem(SPOT_KEY) || "null"); } catch (err) { stash = null; }
    if (stash && stash.id === id && stash.amt != null && stash.amt !== "") return stash;
    return null;
  }
  function clientFetch(q) {
    var id, lineId;
    if (!looksTicker(q)) {
      threadAppend("gopher", parkedBrainLine());
      setBrain("parked", "brain parked");
      return;
    }
    id = tickerId(q);
    resetPrompt();
    lineId = threadAppend("gopher", "GOPHER is fetching\u2026");
    setBrain("think", "fetching\u2026");
    fetch("https://api.coinbase.com/v2/prices/" + id + "-USD/spot")
      .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
      .then(function (j) {
        var amt = j && j.data && j.data.amount;
        if (!amt) throw new Error("empty");
        stashSpot(id, amt);
        showSpot(id, amt, "public spot", q, lineId);
      })
      .catch(function () {
        return fetch("https://www.okx.com/api/v5/market/ticker?instId=" + id + "-USDT")
          .then(function (res) { return res.ok ? res.json() : Promise.reject(); })
          .then(function (j) {
            var row = j && j.data && j.data[0];
            var amt = row && row.last;
            if (!amt) throw new Error("empty");
            stashSpot(id, amt);
            showSpot(id, amt, "public spot", q, lineId);
          });
      })
      .catch(function () {
        var stash = spotFromCache(id);
        if (stash) {
          showSpot(id, stash.amt, "cached", q, lineId);
          return;
        }
        threadSet(lineId, "fetch failed.");
        setBrain("err", "fetch failed.");
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
      cmd = $("command");
      if (cmd) {
        cmd.placeholder = "fetch btc";
        cmd.focus();
      }
      return;
    }
    go("/waitlist");
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
      if (e.target && e.target.id === "command") return;
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (e.key === "/") {
      e.preventDefault();
      if (tutOpen) tutDismiss();
      if ($("command")) $("command").focus();
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
      setStatus($("ask-status"), "", "1 Docs/ · 5 Play/ · 7 Tasks/ · 9 user");
      return;
    }
    if (e.key === "Escape") {
      if (helpEl && !helpEl.hidden) {
        helpEl.hidden = true;
        return;
      }
      if (replyOpen) {
        e.preventDefault();
        if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
        go("/");
        return;
      }
      if (document.activeElement && document.activeElement.id === "command") {
        document.activeElement.blur();
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
    if (!q) {
      if (sugHi >= 0 && sugItems[sugHi] && sugItems[sugHi].id !== "no-match") runTask(sugItems[sugHi]);
      return;
    }
    handleOrder(q);
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
  bindPrompt();
  bindChromeHome();
  setBrain("ready");
  probeHole();
  loadTasks();
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
