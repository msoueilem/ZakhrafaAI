/* ZakhrafaAI — tableau de bord (/dashboard), module ES.
 *
 * Données : GET /api/dashboard (totaux cumulés depuis le démarrage + derniers motifs avec vignette)
 *           GET /api/meta      (ai.remaining_today pour la carte « rendus IA restants »)
 * Le code reste défensif : tout champ peut manquer (ancien backend, réponse partielle).
 * Tout texte rendu en JS est recalculé à chaque changement de langue (render()).
 * Actualisation légère toutes les 30 s tant que l'onglet est visible.
 */
import {
  initI18n, t, has, onLangChange,
  formatNumber, formatDate, formatTime, formatRelative, ltr, withLang,
} from "./i18n.js";
import { initShell } from "./shell.js";
import { getJSON, errorMessage } from "./http.js";
import { icon } from "./icons.js";
import { initReveal } from "./ui.js";

const REFRESH_MS = 30000;
const CATEGORIES = ["zellige", "tapis", "broderie"];

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/* ---------- État ---------- */
const state = {
  dash: null,        // dernière réponse /api/dashboard valide
  ai: null,          // /api/meta .ai (ou null si indisponible)
  updatedAt: null,   // Date de la dernière actualisation réussie
  error: null,       // résultat http en échec (dernière tentative)
  loading: false,
};
let ctrl = null;
let timer = null;

/* ---------- Utilitaires ---------- */
const num = (v) => (Number.isFinite(Number(v)) ? Math.max(0, Number(v)) : 0);
const fmtN = (v) => formatNumber(num(v));
const fmtPct = (part, total) => formatNumber(total ? part / total : 0, { style: "percent", maximumFractionDigits: 0 });

const clock = (d) => formatTime(d, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function categoryName(id) {
  return has(`category.${id}.name`) ? t(`category.${id}.name`) : String(id ?? "—");
}
function paletteName(id) {
  if (!id) return "";
  return has(`palette.${id}`) ? t(`palette.${id}`) : String(id);
}
function parseDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Normalise la réponse de /api/dashboard. */
function normalize(raw) {
  const d = raw && typeof raw === "object" ? raw : {};
  const cats = d.repartition_par_categorie || {};
  const eng = d.repartition_par_moteur || {};
  const src = d.repartition_par_source || {};
  const byCat = Object.fromEntries(CATEGORIES.map((c) => [c, num(cats[c])]));
  const catSum = CATEGORIES.reduce((s, c) => s + byCat[c], 0);
  const total = d.total_motifs != null ? num(d.total_motifs) : catSum;
  const hasModes = d.repartition_par_moteur != null;
  const fast = num(eng.gan);
  const ai = num(eng.diffusion);
  // rendus IA réussis : source « gemini » ; le reste des demandes IA est un repli procédural
  const aiOk = Math.min(ai, num(src.gemini));
  return {
    total, byCat, hasModes, fast, ai, aiOk, aiFallback: ai - aiOk,
    recent: Array.isArray(d.derniers_motifs) ? d.derniers_motifs.filter((x) => x && typeof x === "object") : [],
  };
}

/* ---------- Rendu : cartes ---------- */
function setValue(key, text, { word = false } = {}) {
  const v = $(`[data-stat="${key}"]`);
  v.textContent = text;
  v.classList.toggle("stat__value--word", word);
}

function shareBar(part, total) {
  const bar = el("div", "share");
  bar.setAttribute("aria-hidden", "true");
  const fill = el("i");
  fill.style.setProperty("--p", total ? String(part / total) : "0");
  bar.append(fill);
  return bar;
}

function renderStats() {
  const list = $("#dash-stats");
  const foot = (k) => $(`[data-foot="${k}"]`);
  const d = state.dash;
  if (!d) {
    // aucune donnée (erreur au premier chargement) : tirets plutôt que squelettes infinis
    if (!state.loading) {
      ["total", "fast", "ai"].forEach((k) => { setValue(k, "—"); foot(k).replaceChildren(); });
      list.setAttribute("aria-busy", "false");
    }
  } else {
    list.setAttribute("aria-busy", "false");
    setValue("total", fmtN(d.total));
    // pied du total : répartition par artisanat en texte (pastilles + nombres)
    const f = foot("total");
    f.replaceChildren();
    const row = el("p", "stat__cats");
    CATEGORIES.forEach((c) => {
      const item = el("span", "stat__cat");
      item.append(el("span", `dot dot--${c}`), el("span", null, `${categoryName(c)} ${fmtN(d.byCat[c])}`));
      row.append(item);
    });
    f.append(row);

    if (d.hasModes) {
      setValue("fast", fmtN(d.fast));
      foot("fast").replaceChildren(shareBar(d.fast, d.total), el("span", null, t("dashboard.stat.share", { pct: fmtPct(d.fast, d.total) })));
      setValue("ai", fmtN(d.ai));
      const aiFoot = [shareBar(d.ai, d.total), el("span", null, t("dashboard.stat.share", { pct: fmtPct(d.ai, d.total) }))];
      if (d.ai) aiFoot.push(el("span", null, t("dashboard.stat.ai_split", { ok: fmtN(d.aiOk), fallback: fmtN(d.aiFallback) })));
      foot("ai").replaceChildren(...aiFoot);
    } else {
      ["fast", "ai"].forEach((k) => { setValue(k, "—"); foot(k).replaceChildren(); });
    }
  }

  // carte « rendus IA restants » (indépendante de /api/dashboard)
  const ai = state.ai;
  const lf = foot("ai_left");
  if (ai && ai.enabled === false) {
    setValue("ai_left", t("dashboard.stat.ai_off"), { word: true });
    lf.replaceChildren(el("span", null, t("dashboard.stat.ai_off_hint")));
  } else if (ai && ai.remaining_today != null && Number.isFinite(Number(ai.remaining_today))) {
    setValue("ai_left", fmtN(ai.remaining_today));
    lf.replaceChildren(el("span", null, t("dashboard.stat.ai_left_hint")));
  } else if (!state.loading || state.dash) {
    setValue("ai_left", "—");
    lf.replaceChildren(el("span", null, t("dashboard.stat.ai_unknown")));
  }
}

/* ---------- Rendu : barres empilées + légende (valeurs en texte) ---------- */
function stackedChart(container, rows, total) {
  container.replaceChildren();
  // animation d'entrée au premier dessin seulement (pas à chaque actualisation)
  container.classList.toggle("is-first", !container.dataset.drawn);
  container.dataset.drawn = "1";
  const bar = el("div", "stackbar");
  bar.setAttribute("aria-hidden", "true"); // la légende porte les valeurs
  if (!total) bar.classList.add("stackbar--empty");
  rows.filter((r) => r.n > 0).forEach((r) => {
    const seg = el("span", `stackbar__seg stackbar__seg--${r.key}`);
    seg.style.setProperty("--n", String(r.n));
    seg.title = t("dashboard.bar_aria", { label: r.label, n: fmtN(r.n) });
    bar.append(seg);
  });
  const legend = el("ul", "legend");
  legend.setAttribute("role", "list");
  rows.forEach((r) => {
    const li = el("li", "legend__row");
    const label = el("span", "legend__label", r.label);
    if (r.sub) label.append(el("span", "legend__sub", r.sub));
    li.append(el("span", `dot ${r.dot}`), label, el("span", "legend__count", fmtN(r.n)), el("span", "legend__pct", total ? fmtPct(r.n, total) : "—"));
    legend.append(li);
  });
  container.append(bar, legend);
  if (!total) container.append(el("p", "dash-chart__empty", t("dashboard.chart_empty")));
}

function skeletonChart(container) {
  container.replaceChildren();
  const s = el("div", "skeleton");
  s.style.blockSize = "14px";
  s.style.borderRadius = "999px";
  container.append(s);
  for (let i = 0; i < 3; i++) container.append(el("div", "skeleton skeleton--text"));
}

function renderCharts() {
  const catBox = $("#dash-by-category");
  const modeBox = $("#dash-by-mode");
  const d = state.dash;
  if (!d) {
    if (state.loading) { skeletonChart(catBox); skeletonChart(modeBox); }
    else {
      catBox.replaceChildren(el("p", "dash-chart__empty", "—"));
      modeBox.replaceChildren(el("p", "dash-chart__empty", "—"));
    }
    return;
  }
  stackedChart(catBox, CATEGORIES.map((c) => ({ key: c, dot: `dot--${c}`, label: categoryName(c), n: d.byCat[c] })), d.total);

  modeBox.closest("section").hidden = !d.hasModes;
  if (!d.hasModes) return;
  const modeTotal = d.fast + d.ai;
  stackedChart(modeBox, [
    { key: "fast", dot: "dot--fast", label: t("mode.fast.name"), n: d.fast },
    { key: "ai", dot: "dot--ai", label: t("mode.ai.name"), sub: t("dashboard.mode.ai_ok_sub"), n: d.aiOk },
    { key: "fallback", dot: "dot--ai dot--fallback", label: t("dashboard.mode.ai_fallback"), sub: t("dashboard.mode.ai_fallback_sub"), n: d.aiFallback },
  ], modeTotal);
}

/* ---------- Rendu : derniers motifs ---------- */
function modeBadge(item) {
  if (item.engine === "diffusion") {
    const fallback = item.source && item.source !== "gemini";
    const b = el("span", fallback ? "badge badge--fallback" : "badge badge--ai");
    b.innerHTML = icon("sparkle", { size: 14 });
    b.append(el("span", null, fallback ? t("dashboard.mode.ai_fallback") : t("mode.ai.name")));
    return b;
  }
  if (item.engine === "gan") {
    const b = el("span", "badge badge--fast");
    b.innerHTML = icon("bolt", { size: 14 });
    b.append(el("span", null, t("mode.fast.name")));
    return b;
  }
  return el("span", "badge", String(item.engine ?? "—"));
}

function thumbFor(item) {
  const box = el("div", "recent__thumb");
  const src = typeof item.thumb === "string" && /^data:image\/(webp|jpeg|png);base64,/.test(item.thumb) ? item.thumb : null;
  if (src) {
    const img = el("img");
    img.src = src;
    img.width = 56; img.height = 56;
    img.decoding = "async";
    const pal = paletteName(item.palette);
    img.alt = pal
      ? t("dashboard.thumb_alt", { category: categoryName(item.category), palette: pal })
      : t("dashboard.thumb_alt_nopal", { category: categoryName(item.category) });
    box.append(img);
  } else {
    box.classList.add(`recent__thumb--ph-${CATEGORIES.includes(item.category) ? item.category : "x"}`);
    box.innerHTML = icon("star", { size: 22 });
  }
  return box;
}

function recentItem(item) {
  const li = el("li", "recent__item");
  const main = el("div", "recent__main");

  const title = el("p", "recent__title");
  const name = el("span", "recent__cat");
  name.append(el("span", `dot dot--${item.category}`), el("span", null, categoryName(item.category)));
  title.append(name, modeBadge(item));

  const meta = el("p", "recent__meta");
  const pal = paletteName(item.palette);
  if (pal) meta.append(el("span", null, t("dashboard.palette", { palette: pal })));
  if (item.seed != null && item.seed !== "") {
    const s = el("span", "recent__seed");
    const v = ltr(item.seed);
    v.classList.add("mono");
    s.append(el("span", null, `${t("dashboard.seed")} `), v);
    meta.append(s);
  }
  main.append(title);
  if (meta.childNodes.length) main.append(meta);

  const time = el("time", "recent__time");
  const d = parseDate(item.date);
  if (d) {
    time.dateTime = d.toISOString();
    time.textContent = formatRelative(d);
    time.title = formatDate(d, { dateStyle: "full", timeStyle: "medium" });
  } else {
    time.textContent = item.date ? String(item.date) : "";
  }
  li.append(thumbFor(item), main, time);
  return li;
}

function renderLatest() {
  const box = $("#dash-latest");
  const hint = $("#dash-latest-hint");
  const d = state.dash;
  if (!d) {
    hint.textContent = "";
    if (state.loading) {
      box.setAttribute("aria-busy", "true");
      const sk = [el("p", "sr-only", t("dashboard.loading"))];
      for (let i = 0; i < 3; i++) {
        const r = el("div", "dash-skel-row");
        r.setAttribute("aria-hidden", "true");
        const txt = el("div");
        txt.append(el("div", "skeleton skeleton--text"), el("div", "skeleton skeleton--text"));
        txt.lastChild.style.inlineSize = "50%";
        r.append(el("div", "skeleton skeleton--circle"), txt);
        sk.push(r);
      }
      box.replaceChildren(...sk);
    } else {
      box.setAttribute("aria-busy", "false");
      box.replaceChildren(el("p", "dash-chart__empty", "—"));
    }
    return;
  }
  box.setAttribute("aria-busy", "false");
  if (!d.recent.length) {
    hint.textContent = "";
    const empty = el("div", "dash-empty");
    const ic = el("span");
    ic.innerHTML = icon("star", { size: 40 });
    const cta = el("a", "btn btn--primary");
    cta.href = withLang("/studio");
    cta.append(el("span", null, t("dashboard.empty_cta")));
    cta.insertAdjacentHTML("beforeend", icon("arrow-end"));
    empty.append(ic.firstElementChild || ic, el("p", "h4", t("dashboard.empty")), el("p", "dash-empty__hint", t("dashboard.empty_hint")), cta);
    box.replaceChildren(empty);
    return;
  }
  hint.textContent = t("dashboard.latest_hint", { n: fmtN(d.recent.length) });
  const ul = el("ul", "recent");
  ul.setAttribute("role", "list");
  d.recent.forEach((item) => ul.append(recentItem(item)));
  box.replaceChildren(ul);
}

/* ---------- Rendu : erreur + horodatage ---------- */
function renderError() {
  const box = $("#dash-error");
  const r = state.error;
  if (!r) { box.hidden = true; box.replaceChildren(); return; }
  const notice = el("div", "notice notice--danger dash-error");
  notice.setAttribute("role", "alert");
  notice.innerHTML = icon("alert");
  const body = el("div", "notice__body");
  body.append(el("p", "notice__title", t("error.dashboard_load")));
  const detail = r.code === "network" ? errorMessage(r) : t("dashboard.error", { message: r.status ? `HTTP ${r.status}` : r.code });
  body.append(el("p", null, detail));
  if (state.dash && state.updatedAt) body.append(el("p", null, t("dashboard.stale", { time: clock(state.updatedAt) })));
  const actions = el("div", "dash-error__actions");
  const retry = el("button", "btn btn--secondary btn--sm");
  retry.type = "button";
  retry.innerHTML = icon("refresh");
  retry.append(el("span", null, t("error.retry")));
  retry.addEventListener("click", () => load({ focus: true }));
  if (state.loading) retry.setAttribute("aria-busy", "true");
  actions.append(retry);
  body.append(actions);
  notice.append(body);
  box.replaceChildren(notice);
  box.hidden = false;
}

function renderUpdated() {
  const u = $("#dash-updated");
  u.classList.toggle("is-stale", !!state.error && !!state.updatedAt);
  u.textContent = state.updatedAt ? t("dashboard.updated", { time: clock(state.updatedAt) }) : "";
  const btn = $("#dash-refresh");
  if (state.loading) btn.setAttribute("aria-busy", "true");
  else btn.removeAttribute("aria-busy");
}

function render() {
  renderStats();
  renderCharts();
  renderLatest();
  renderError();
  renderUpdated();
}

/* ---------- Chargement ---------- */
async function load({ focus = false } = {}) {
  ctrl?.abort();
  const mine = (ctrl = new AbortController());
  state.loading = true;
  renderUpdated();
  if (!state.dash) render();

  const [dash, meta] = await Promise.all([
    getJSON("/api/dashboard", { timeout: 15000, signal: mine.signal }),
    getJSON("/api/meta", { timeout: 15000, signal: mine.signal }),
  ]);
  if (mine !== ctrl) return; // une requête plus récente a pris le relais
  ctrl = null;
  state.loading = false;

  if (dash.ok && dash.data && typeof dash.data === "object") {
    state.dash = normalize(dash.data);
    state.updatedAt = new Date();
    state.error = null;
  } else if (dash.code !== "aborted") {
    state.error = dash.ok ? { ok: false, code: "http", status: dash.status } : dash;
  }
  if (meta.ok && meta.data && typeof meta.data === "object") state.ai = meta.data.ai || null;
  render();
  if (focus && state.error) $("#dash-error button")?.focus();
  schedule();
}

function schedule() {
  clearTimeout(timer);
  if (document.visibilityState === "visible") timer = setTimeout(() => load(), REFRESH_MS);
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") { clearTimeout(timer); return; }
  // retour sur l'onglet : actualiser tout de suite si les données ont plus de 30 s
  const age = state.updatedAt ? Date.now() - state.updatedAt.getTime() : Infinity;
  if (age >= REFRESH_MS && !state.loading) load();
  else schedule();
});

/* ---------- Démarrage ---------- */
await initI18n("dashboard");
initShell();
document.querySelectorAll(".js-icon").forEach((n) => {
  n.outerHTML = icon(n.dataset.icon, { size: Number(n.dataset.size) || 18 });
});
$("#dash-refresh").addEventListener("click", () => load());
onLangChange(render);
initReveal();
load();
