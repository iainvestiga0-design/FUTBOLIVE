"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Crea elementos de forma segura (textContent, nunca innerHTML con datos externos)
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid);
  return el;
}

const state = { leagues: [], when: "upcoming", region: "todos", league: "all", tableLeague: null, view: "inicio" };
const MSG = {
  premium: ["FUTBOLIVE Premium", "Estamos preparando esta sección. En esta versión no se realizan cobros ni se activa ninguna suscripción."],
  login: ["Acceso de usuarios", "El registro y el inicio de sesión llegarán en la siguiente etapa. Todavía no se crean cuentas."],
};

async function api(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api/${path}${qs ? "?" + qs : ""}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ---------- Formato ---------- */
const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
function dayLabel(iso) {
  const d = new Date(iso), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(d) - day(now)) / 864e5);
  if (diff === 0) return "Hoy";
  if (diff === 1) return "Mañana";
  if (diff === -1) return "Ayer";
  return d.toLocaleDateString("es", { weekday: "long", day: "numeric", month: "short" });
}
const safeUrl = (u) => (typeof u === "string" && u.startsWith("https://") ? u : null);

/* ---------- Componentes ---------- */
function crest(team) {
  const box = h("div", { class: "crest" });
  const src = safeUrl(team.badge);
  if (src) {
    const img = h("img", { src: src + "/tiny", alt: "", loading: "lazy", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => { box.textContent = (team.name || "?")[0]; });
    box.append(img);
  } else box.textContent = (team.name || "?")[0];
  return box;
}

function matchCard(m) {
  const live = m.status === "LIVE", ft = m.status === "FT";
  const pill = live ? h("span", { class: "pill live", text: "● " + (m.minute || "EN VIVO") })
    : ft ? h("span", { class: "pill ft", text: "FINAL" })
    : m.status === "PST" ? h("span", { class: "pill", text: "APLAZADO" })
    : h("span", { class: "pill", text: "PRÓXIMO" });
  const center = (live || ft)
    ? h("div", { class: "center" }, h("div", { class: "score", text: `${m.home.score ?? 0} - ${m.away.score ?? 0}` }))
    : h("div", { class: "center" }, h("div", { class: "time", text: fmtTime(m.kickoff) }));
  const team = (t) => h("div", { class: "team" }, crest(t), h("span", { text: t.name }));
  return h("article", { class: "match" + (live ? " live" : "") },
    h("div", { class: "m-top" }, h("span", { class: "lg", text: m.league_name + (m.round ? ` · Fecha ${m.round}` : "") }), pill),
    h("div", { class: "m-body" }, team(m.home), center, team(m.away)));
}

function renderMatches(box, matches, emptyMsg, grouped = false) {
  box.replaceChildren();
  if (!matches.length) { box.append(h("div", { class: "empty", text: emptyMsg })); return; }
  let last = null;
  for (const m of matches) {
    if (grouped) {
      const lab = dayLabel(m.kickoff);
      if (lab !== last) { box.append(h("div", { class: "day-label", text: lab })); last = lab; }
    }
    box.append(matchCard(m));
  }
}
const skeleton = (box, n = 2) => box.replaceChildren(...Array.from({ length: n }, () => h("div", { class: "skeleton" })));

function setBanner(data, error) {
  const b = $("#banner");
  if (error) {
    b.className = "banner err"; b.hidden = false;
    b.textContent = "No se pudo conectar con el servidor. Mostrando lo último guardado, si hay.";
  } else if (data && data.source === "demo") {
    b.className = "banner"; b.hidden = false;
    b.textContent = "Modo demostración: estos partidos son de ejemplo, no reales.";
  } else if (data && ((data.loading && data.loading.length) || (data.unavailable && data.unavailable.length))) {
    const nm = (list) => list.map((x) => (state.leagues.find((l) => l.slug === x) || {}).name || x).join(", ");
    b.className = "banner"; b.hidden = false;
    b.textContent = data.loading && data.loading.length
      ? "Cargando datos de: " + nm(data.loading) + ". La primera vez tarda un par de minutos."
      : "Sin datos por ahora de: " + nm(data.unavailable) + ". Reintentamos en unos segundos.";
    clearTimeout(state.retry);
    state.retry = setTimeout(() => { if (!document.hidden) refresh(); }, 20000);
  } else b.hidden = true;
}

/* ---------- Vistas ---------- */
async function loadHome() {
  skeleton($("#liveList"), 1); skeleton($("#todayList"), 2);
  try {
    const d = await api("matches", { when: "today" });
    setBanner(d);
    const live = d.matches.filter((m) => m.status === "LIVE");
    renderMatches($("#liveList"), live, "No hay partidos en vivo en este momento.");
    renderMatches($("#todayList"), d.matches.filter((m) => m.status !== "LIVE"), "Hoy no hay más partidos en estas competiciones.");
  } catch { setBanner(null, true); $("#liveList").replaceChildren(); renderMatches($("#todayList"), [], "Sin conexión."); }
}

async function loadMatches() {
  const box = $("#matchList"); skeleton(box, 3);
  try {
    const d = await api("matches", { when: state.when, region: state.region, league: state.league });
    setBanner(d);
    const msg = { upcoming: "No hay próximos partidos para este filtro.", results: "No hay resultados recientes.", live: "No hay partidos en vivo ahora." }[state.when];
    renderMatches(box, d.matches, msg, state.when !== "live");
  } catch { setBanner(null, true); renderMatches(box, [], "Sin conexión."); }
}

function leagueChips(box, selected, onPick, withAll) {
  box.replaceChildren();
  const list = state.leagues.filter((l) => withAll === false ? l.has_table : (state.region === "todos" || l.region === state.region));
  const mk = (slug, label) => h("button", { class: "chip" + (slug === selected ? " active" : ""), text: label, onclick: () => onPick(slug) });
  if (withAll) box.append(mk("all", "Todas"));
  for (const l of list) box.append(mk(l.slug, `${l.icon} ${l.name}`));
}

function drawMatchFilters() {
  $$("#regionChips .chip").forEach((c) => c.classList.toggle("active", c.dataset.region === state.region));
  leagueChips($("#leagueChips"), state.league, (s) => { state.league = s; drawMatchFilters(); loadMatches(); }, true);
}

async function loadTable() {
  const box = $("#tableBox");
  leagueChips($("#tableChips"), state.tableLeague, (s) => { state.tableLeague = s; loadTable(); }, false);
  skeleton(box, 1); box.firstChild.style.height = "260px";
  try {
    const d = await api("standings", { league: state.tableLeague });
    setBanner(d);
    if (!d.table.length) { box.replaceChildren(h("div", { class: "empty", text: d.note || "Tabla no disponible." })); return; }
    const head = ["#", "Equipo", "PJ", "G", "E", "P", "DG", "Pts"];
    const tbl = h("table", {},
      h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: i === 1 ? "t" : "", text: t })))),
      h("tbody", {}, d.table.map((r) => h("tr", { class: r.rank <= 4 ? "top" : "" },
        h("td", { class: "rk", text: r.rank }), h("td", { class: "t", text: r.team }),
        h("td", { text: r.played ?? "–" }), h("td", { text: r.won ?? "–" }), h("td", { text: r.drawn ?? "–" }),
        h("td", { text: r.lost ?? "–" }), h("td", { text: r.gd ?? "–" }), h("td", { class: "pts", text: r.points ?? "–" })))));
    box.replaceChildren(h("div", { class: "table-wrap" }, tbl));
  } catch { setBanner(null, true); box.replaceChildren(h("div", { class: "empty", text: "No se pudo cargar la tabla." })); }
}

function show(view) {
  state.view = view;
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  $("#banner").hidden = true;
  window.scrollTo({ top: 0 });
  refresh();
}

function refresh() {
  if (state.view === "inicio") return loadHome();
  if (state.view === "partidos") return loadMatches();
  if (state.view === "tablas") return loadTable();
}

function info(key) {
  const [t, m] = MSG[key];
  $("#dialogTitle").textContent = t; $("#dialogText").textContent = m; $("#infoDialog").showModal();
}

/* ---------- Arranque ---------- */
async function init() {
  $$(".tab").forEach((t) => t.addEventListener("click", () => show(t.dataset.view)));
  $$("[data-info]").forEach((b) => b.addEventListener("click", () => info(b.dataset.info)));
  $("#loginBtn").addEventListener("click", () => info("login"));
  $("#closeDialog").addEventListener("click", () => $("#infoDialog").close());
  $("#okDialog").addEventListener("click", () => $("#infoDialog").close());
  $("#refreshBtn").addEventListener("click", async (e) => {
    e.currentTarget.classList.add("spin"); await refresh(); setTimeout(() => e.currentTarget.classList.remove("spin"), 400);
  });
  $$("#whenSeg .seg-btn").forEach((b) => b.addEventListener("click", () => {
    state.when = b.dataset.when; $$("#whenSeg .seg-btn").forEach((x) => x.classList.toggle("active", x === b)); loadMatches();
  }));
  $$("#regionChips .chip").forEach((c) => c.addEventListener("click", () => {
    state.region = c.dataset.region; state.league = "all"; drawMatchFilters(); loadMatches();
  }));

  try {
    const d = await api("leagues");
    state.leagues = d.leagues; state.tableLeague = (d.leagues.find((l) => l.has_table) || d.leagues[0]).slug;
    $("#leagueGrid").replaceChildren(...d.leagues.map((l) => h("button", { class: "league", onclick: () => {
      state.league = l.slug; state.region = "todos"; state.when = "upcoming";
      $$("#whenSeg .seg-btn").forEach((x) => x.classList.toggle("active", x.dataset.when === "upcoming"));
      drawMatchFilters(); show("partidos");
    } }, h("span", { class: "ic", text: l.icon }), h("div", {}, h("b", { text: l.name }), h("small", { text: l.country })))));
    drawMatchFilters();
  } catch { setBanner(null, true); }
  refresh();

  // Actualiza solo, cada minuto, cuando la app está a la vista
  setInterval(() => { if (!document.hidden && state.view !== "premium") refresh(); }, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}
init();
