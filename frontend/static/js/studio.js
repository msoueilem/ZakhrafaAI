/* ZakhrafaAI — Atelier (/studio). Module ES.
 *
 * Règles conservées de l'ancienne version (ne pas régresser) :
 *  - au lancement, la zone de résultat est ramenée à l'écran si besoin (doux sauf mouvement réduit) ;
 *  - échec : message traduit (réseau -> « connexion interrompue »), méta/badge/notice effacés,
 *    Télécharger/Régénérer désactivés jusqu'au prochain succès, quota IA relu après toute tentative IA ;
 *  - palettes = vraies couleurs de /api/meta + nom traduit visible ;
 *  - seed entière 0..2^53-1 (vérifiée côté client), résolution 128–1024, notice si le serveur ajuste ;
 *  - miniatures d'historique = boutons qui restaurent le résultat (aria-current) ;
 *  - fichier zakhrafaai_<categorie>_<rapide|ia|procedural>_<seed>.png ;
 *  - « Régénérer » rejoue exactement la requête avec la seed renvoyée.
 * Tout texte rendu ici est stocké sous forme de descripteur {key, params} | {raw} et re-rendu
 * au changement de langue.
 */
import { initI18n, t, has, getLang, onLangChange, formatNumber, ltr } from "./i18n.js";
import { initShell } from "./shell.js";
import { getJSON, postJSON } from "./http.js";
import { initRadioGroup, prefersReducedMotion } from "./ui.js";
import { icon } from "./icons.js";

const SIZE_MIN = 128;
const SIZE_MAX = 1024;
const PROMPT_MAX = 300;
const IDEA_MAX = 500;
const HISTORY_MAX = 12;
const CATEGORIES = ["zellige", "tapis", "broderie"];
const ENGINES = ["gan", "diffusion"];
const DEFAULT_PALETTE = "zellige_classique";
const MOBILE_MQ = window.matchMedia("(max-width: 959.98px)");

const $ = (id) => document.getElementById(id);

await initI18n("studio");
initShell();

/* ------------------------------------------------------------------ */
/* Éléments                                                            */
/* ------------------------------------------------------------------ */
const el = {
  form: $("controls"),
  scroll: $("controls-scroll"),
  craft: $("craft"),
  mode: $("mode"),
  quota: $("quota"),
  modeHint: $("mode-hint"),
  palettes: $("palettes"),
  paletteCurrent: $("palette-current"),
  promptOff: $("prompt-off"),
  promptField: $("prompt-field"),
  prompt: $("prompt"),
  promptCount: $("prompt-count"),
  promptError: $("prompt-error"),
  switchAi: $("switch-ai"),
  enhance: $("enhance"),
  enhanceUndo: $("enhance-undo"),
  enhanceOut: $("enhance-out"),
  advanced: $("advanced"),
  seed: $("seed"),
  seedError: $("seed-error"),
  size: $("size"),
  sizeError: $("size-error"),
  genBar: $("gen-bar"),
  genCost: $("gen-cost"),
  generate: $("generate"),
  assist: $("assist"),
  idea: $("assist-idea"),
  ideaCount: $("assist-count"),
  plan: $("assist-submit"),
  planOut: $("assist-out"),
  assistDownOut: $("assist-down"),
  result: $("result"),
  stage: $("stage"),
  img: $("stage-img"),
  empty: $("stage-empty"),
  loading: $("stage-loading"),
  loadingLabel: $("loading-label"),
  error: $("stage-error"),
  errorText: $("stage-error-text"),
  retry: $("stage-retry"),
  modeAiMeta: $("mode-ai-meta"),
  status: $("result-status"),
  badge: $("source-badge"),
  meta: $("meta"),
  metaMode: $("meta-mode"),
  metaSize: $("meta-size"),
  metaTime: $("meta-time"),
  metaSeed: $("meta-seed"),
  copySeed: $("copy-seed"),
  copyDone: $("copy-done"),
  notices: $("notices"),
  download: $("download"),
  regenerate: $("regenerate"),
  about: $("about"),
  aboutBody: $("about-body"),
  history: $("history"),
  historyEmpty: $("history-empty"),
};

hydrateIcons(document);

/* ------------------------------------------------------------------ */
/* État                                                                */
/* ------------------------------------------------------------------ */
const state = { category: "zellige", engine: "gan", palette: DEFAULT_PALETTE };
const meta = { loaded: false, failed: false, ai: null, assist: null, palettes: [] };
let assistDown = false;        // l'API a répondu assist_disabled pendant la session
let current = null;            // entrée affichée { id, result, request, notices }
let failure = null;            // descripteur du dernier échec affiché
let failedRequest = null;      // requête à rejouer avec « Réessayer »
let pending = null;            // requête en cours
const history = [];
let entrySeq = 0;
const fieldErrors = { seed: null, size: null, prompt: null };
const msgs = { plan: null, enhance: null };
let enhancePrev = null;        // texte avant « Améliorer » (pour Annuler)
const busy = { plan: false, enhance: false }; // « Proposer » et « Améliorer » s'excluent mutuellement
let planInfo = null;           // dernier plan appliqué (explication, réglages)
const captions = new Map();    // "cat|palette|lang" -> texte
let captionToken = 0;
let paletteGroup = null;

/* ------------------------------------------------------------------ */
/* Utilitaires                                                         */
/* ------------------------------------------------------------------ */
function hydrateIcons(root) {
  root.querySelectorAll("[data-icon]").forEach((n) => {
    if (n.dataset.iconDone) return;
    n.innerHTML = icon(n.dataset.icon, { size: Number(n.dataset.size) || (n.closest(".btn--sm, .badge") ? 16 : 20) });
    n.dataset.iconDone = "1";
    n.classList.add("icon-slot");
  });
}

/** Délai en secondes -> « 3 minutes » / « 3 دقائق » / « 45 s » dans la langue active. */
function formatWait(sec) {
  const s = Math.max(1, Math.round(sec));
  const [n, unit] = s < 60 ? [s, "second"] : [Math.ceil(s / 60), "minute"];
  return formatNumber(n, { style: "unit", unit, unitDisplay: "long" });
}

/** Descripteur -> texte. {key, params, wait?} | {raw} ; `wait` (s) est formaté au rendu (paramètre {wait}). */
const tx = (d) => (!d ? "" : d.raw != null ? String(d.raw)
  : t(d.key, d.wait != null ? { ...d.params, wait: formatWait(d.wait) } : d.params));

const catName = (id) => (has(`category.${id}.name`) ? t(`category.${id}.name`) : id);
const modeName = (engine) => t(engine === "diffusion" ? "mode.ai.name" : "mode.fast.name");
function paletteName(id) {
  if (has(`palette.${id}`)) return t(`palette.${id}`);
  return meta.palettes.find((p) => p.id === id)?.label || id;
}
const aiOn = () => !!(meta.ai && meta.ai.enabled);
const assistOn = () => !!(meta.assist && meta.assist.enabled);
/** Rendu IA actif mais quota du jour épuisé : le serveur renverra le motif Rapide. */
const quotaOut = () => aiOn() && meta.ai.remaining_today != null && Number(meta.ai.remaining_today) <= 0;

function setLabel(btn, key) {
  const lab = btn.querySelector(".js-label");
  if (!lab) return;
  lab.dataset.i18n = key;
  lab.textContent = t(key);
}

function setBusy(btn, busy, key) {
  if (busy) btn.setAttribute("aria-busy", "true");
  else btn.removeAttribute("aria-busy");
  btn.disabled = busy;
  if (key) setLabel(btn, key);
}

/** Notice de la fondation : {tone, title?, lines: [descripteur], action?} */
function noticeEl({ tone = "info", title, lines = [], action }) {
  const box = document.createElement("div");
  box.className = `notice notice--${tone}`;
  box.setAttribute("role", tone === "danger" ? "alert" : "status");
  const ico = { info: "info", success: "check", warning: "alert", danger: "alert", ai: "sparkle" }[tone] || "info";
  box.insertAdjacentHTML("afterbegin", icon(ico, { size: 18 }));
  const body = document.createElement("div");
  body.className = "notice__body";
  if (title) {
    const p = document.createElement("p");
    p.className = "notice__title";
    p.textContent = tx(title);
    body.appendChild(p);
  }
  for (const line of lines) {
    if (!line) continue;
    const p = document.createElement("p");
    if (line.node) p.appendChild(line.node());
    else p.textContent = tx(line);
    if (line.raw != null) p.dir = "auto"; // texte du modèle ou du serveur : direction selon son contenu
    body.appendChild(p);
  }
  if (action) body.appendChild(action());
  box.appendChild(body);
  return box;
}

function renderMsg(slot, container) {
  const m = msgs[slot];
  container.replaceChildren(m ? noticeEl(m) : "");
}

/** Message du plan : dans le panneau, ou sous lui s'il a été masqué (assistant coupé en cours de session). */
function renderPlanMsg() {
  const down = assistDown && msgs.plan;
  renderMsg("plan", down ? el.assistDownOut : el.planOut);
  (down ? el.planOut : el.assistDownOut).replaceChildren();
}

function flash(node) {
  if (!node) return;
  node.classList.remove("is-suggested");
  void node.offsetWidth; // relance l'animation
  node.classList.add("is-suggested");
  clearTimeout(node._flashT);
  node._flashT = setTimeout(() => node.classList.remove("is-suggested"), 2400);
}

/** Nombre isolé LTR en police mono (.num) : l'unité traduite reste dans la police du texte. */
function numEl(value) {
  const b = ltr(value);
  b.classList.add("num");
  return b;
}

/** t(key) dont le paramètre {n} devient un <bdi class="num"> : « 2,3 » en mono, « ث » / « s » en police de texte. */
function withNum(key, n) {
  const frag = document.createDocumentFragment();
  const parts = t(key, { n: "\u0000" }).split("\u0000");
  parts.forEach((part, i) => {
    if (i) frag.appendChild(numEl(n));
    if (part) frag.appendChild(document.createTextNode(part));
  });
  return frag;
}

/** Compteur « n / max » isolé LTR (lisible en arabe). */
function setCounter(node, n, max) {
  node.replaceChildren(ltr(t("studio.prompt.counter", { n, max })));
}

/* ------------------------------------------------------------------ */
/* Contrôles                                                           */
/* ------------------------------------------------------------------ */
const craftGroup = initRadioGroup(el.craft, {
  onChange: (v) => { state.category = v; },
});
const modeGroup = initRadioGroup(el.mode, {
  onChange: (v) => { state.engine = v; renderMode(); },
});

el.switchAi.addEventListener("click", () => {
  modeGroup.set("diffusion");
  state.engine = "diffusion";
  renderMode();
  el.prompt.focus();
});

function renderMode() {
  const isAI = state.engine === "diffusion";
  el.promptField.hidden = !isAI;
  el.promptOff.hidden = isAI;

  // indication sous les cartes
  let hint;
  if (!isAI) hint = t("studio.mode.fast.hint");
  else if (!meta.loaded) hint = meta.failed ? t("studio.mode.ai.fallback_hint") : t("studio.mode.ai.hint_checking");
  else if (!aiOn()) hint = t("studio.mode.ai.hint_disabled");
  else if (quotaOut()) hint = t("studio.mode.ai.hint_none");
  else hint = `${t("studio.mode.ai.hint", { model: meta.ai.model || "Gemini" })} ${t("studio.mode.ai.fallback_hint")}`;
  el.modeHint.textContent = hint;

  // carte Rendu IA : coût réel du jour (quota épuisé -> repli Rapide)
  const metaKey = quotaOut() ? "studio.mode.ai.meta_none" : "studio.mode.ai.meta";
  el.modeAiMeta.dataset.i18n = metaKey;
  el.modeAiMeta.textContent = t(metaKey);

  // pastille de quota (connue seulement si le rendu IA est actif)
  const n = aiOn() ? meta.ai.remaining_today : null;
  if (n == null || !Number.isFinite(Number(n))) {
    el.quota.hidden = true;
  } else {
    el.quota.hidden = false;
    const key = n <= 0 ? "studio.quota.none" : n === 1 ? "studio.quota.one" : "studio.quota.remaining";
    el.quota.innerHTML = icon("sparkle", { size: 14 });
    el.quota.append(document.createTextNode(t(key, { n })));
    el.quota.classList.toggle("badge--danger", n <= 0);
    el.quota.classList.toggle("badge--ai", n > 0);
  }

  // bouton Générer : couleur IA (payant) ou primaire (gratuit) + coût rappelé
  el.generate.classList.toggle("btn--primary", !isAI);
  el.generate.classList.toggle("btn--ai-solid", isAI);
  el.generate.querySelector("[data-icon]").innerHTML = icon(isAI ? "sparkle" : "bolt", { size: 20 });
  el.genBar.classList.toggle("is-ai", isAI);
  el.genCost.replaceChildren();
  const name = document.createElement("strong");
  name.textContent = t(isAI ? "studio.mode.ai.label" : "studio.mode.fast.label");
  const cost = document.createElement("span");
  cost.textContent = t(!isAI ? "studio.mode.fast.meta" : quotaOut() ? "studio.gen.cost_none" : "studio.mode.ai.meta");
  el.genCost.append(name, cost);
}

/* ---------- Palettes ---------- */
function renderPalettes() {
  if (!meta.palettes.length && !meta.failed) return; // squelettes jusqu'à /api/meta
  el.palettes.replaceChildren();
  if (!meta.palettes.length) {
    const p = document.createElement("p");
    p.className = "field__hint palette-grid__msg";
    p.textContent = t(meta.failed ? "studio.palette.unavailable" : "studio.palette.loading");
    el.palettes.appendChild(p);
    renderPaletteCurrent();
    return;
  }
  if (!meta.palettes.some((p) => p.id === state.palette)) {
    state.palette = meta.palettes.some((p) => p.id === DEFAULT_PALETTE) ? DEFAULT_PALETTE : meta.palettes[0].id;
  }
  for (const p of meta.palettes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "swatch";
    btn.setAttribute("role", "radio");
    btn.setAttribute("aria-checked", String(p.id === state.palette));
    btn.dataset.value = p.id;
    const strip = document.createElement("span");
    strip.className = "swatch__strip";
    strip.setAttribute("aria-hidden", "true");
    for (const c of p.colors || []) {
      const stop = document.createElement("span");
      stop.style.background = c;
      strip.appendChild(stop);
    }
    const name = document.createElement("span");
    name.className = "swatch__name";
    name.textContent = paletteName(p.id);
    btn.append(strip, name);
    el.palettes.appendChild(btn);
  }
  if (!paletteGroup) {
    paletteGroup = initRadioGroup(el.palettes, {
      onChange: (v) => { state.palette = v; renderPaletteCurrent(); },
    });
  } else paletteGroup.refresh();
  renderPaletteCurrent();
}

function renderPaletteNames() {
  el.palettes.querySelectorAll(".swatch").forEach((b) => {
    b.querySelector(".swatch__name").textContent = paletteName(b.dataset.value);
  });
  const msg = el.palettes.querySelector(".palette-grid__msg");
  if (msg) msg.textContent = t(meta.failed ? "studio.palette.unavailable" : "studio.palette.loading");
  renderPaletteCurrent();
}

function renderPaletteCurrent() {
  el.paletteCurrent.textContent = meta.palettes.length ? t("studio.palette.selected", { name: paletteName(state.palette) }) : "";
}

function selectPalette(id) {
  state.palette = id;
  if (paletteGroup) paletteGroup.set(id);
  renderPaletteCurrent();
}

/* ---------- Description de style ---------- */
function updatePromptCount() { setCounter(el.promptCount, el.prompt.value.length, PROMPT_MAX); }
function updateIdeaCount() { setCounter(el.ideaCount, el.idea.value.length, IDEA_MAX); }

el.prompt.addEventListener("input", () => {
  updatePromptCount();
  setFieldError("prompt", null);
  if (enhancePrev != null) { enhancePrev = null; el.enhanceUndo.hidden = true; }
  if (msgs.enhance) { msgs.enhance = null; renderMsg("enhance", el.enhanceOut); }
});
el.idea.addEventListener("input", updateIdeaCount);
el.idea.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runPlan(); }
});

/* ---------- Erreurs de champ ---------- */
const FIELD_NODES = {
  seed: () => [el.seed, el.seedError],
  size: () => [el.size, el.sizeError],
  prompt: () => [el.prompt, el.promptError],
};

function setFieldError(field, desc) {
  fieldErrors[field] = desc;
  const [input, out] = FIELD_NODES[field]();
  if (desc) {
    out.replaceChildren();
    out.insertAdjacentHTML("afterbegin", icon("alert", { size: 14 }));
    out.append(document.createTextNode(tx(desc)));
    out.hidden = false;
    input.setAttribute("aria-invalid", "true");
  } else {
    out.hidden = true;
    out.replaceChildren();
    input.removeAttribute("aria-invalid");
  }
}

function focusField(field) {
  const [input] = FIELD_NODES[field]();
  if (field !== "prompt") el.advanced.open = true;
  else if (state.engine !== "diffusion") { modeGroup.set("diffusion"); state.engine = "diffusion"; renderMode(); }
  input.focus({ preventScroll: true });
  input.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

el.seed.addEventListener("input", () => setFieldError("seed", null));
el.size.addEventListener("input", () => setFieldError("size", null));

/** Seed : entier ≥ 0 représentable exactement en JS. Renvoie {seed} | {error}. */
function parseSeed() {
  if (el.seed.validity.badInput) return { error: { key: "studio.seed.error_format" } };
  const text = el.seed.value.trim();
  if (!text) return { seed: null };
  if (!/^\d+$/.test(text)) return { error: { key: "studio.seed.error_format" } };
  const value = Number(text);
  if (!Number.isSafeInteger(value)) return { error: { key: "studio.seed.error_max", params: { max: Number.MAX_SAFE_INTEGER } } };
  return { seed: value };
}

function parseSize() {
  if (el.size.validity.badInput) return { error: { key: "studio.size.error_format" } };
  const text = el.size.value.trim();
  if (!text) return { size: null };
  const v = Math.round(Number(text));
  if (!Number.isFinite(v)) return { error: { key: "studio.size.error_format" } };
  return { size: v > 0 ? v : null };
}

/** Requête courante, ou null si un champ est invalide (erreur affichée + focus). */
function currentRequest() {
  const s = parseSeed();
  const z = parseSize();
  setFieldError("seed", s.error || null);
  setFieldError("size", z.error || null);
  if (s.error) { focusField("seed"); return null; }
  if (z.error) { focusField("size"); return null; }
  const isAI = state.engine === "diffusion";
  return {
    category: state.category,
    engine: state.engine,
    palette: state.palette,
    seed: s.seed,
    size: z.size,
    prompt: isAI ? el.prompt.value.trim() || null : null,
  };
}

/* ------------------------------------------------------------------ */
/* /api/meta : rendu IA, assistant, palettes                           */
/* ------------------------------------------------------------------ */
async function refreshMeta() {
  const r = await getJSON("/api/meta", { timeout: 15000 });
  if (r.ok && r.data && typeof r.data === "object") {
    meta.loaded = true;
    meta.failed = false;
    meta.ai = r.data.ai || null;
    meta.assist = r.data.assist || null;
    if (!meta.palettes.length && Array.isArray(r.data.palettes) && r.data.palettes.length) {
      meta.palettes = r.data.palettes.filter((p) => p && p.id);
      renderPalettes();
    }
  } else if (!meta.loaded) {
    meta.failed = true;
    if (!meta.palettes.length) renderPalettes();
  }
  renderMode();
  renderAssistAvailability();
}

/* ------------------------------------------------------------------ */
/* Génération                                                          */
/* ------------------------------------------------------------------ */
el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  if (pending) return;
  const req = currentRequest();
  if (req) generate(req);
});

el.retry.addEventListener("click", () => {
  if (failedRequest && !pending) generate({ ...failedRequest });
});

el.regenerate.addEventListener("click", () => {
  if (current && !pending) generate({ ...current.request });
});

async function generate(request) {
  pending = request;
  setLoading(request);
  const r = await postJSON("/api/generate", request, { timeout: 120000 });
  pending = null;
  endLoading();
  if (r.ok && r.data && typeof r.data === "object" && r.data.image) onSuccess(r.data, request);
  else if (r.code !== "aborted") onFailure(r, request);
  // succès ou échec : le serveur a pu décompter un rendu IA, on relit le quota
  if (request.engine === "diffusion") refreshMeta();
}

/** Ramène la scène à l'écran si elle n'est pas entièrement visible. */
function revealResultArea() {
  const rect = el.stage.getBoundingClientRect();
  const navH = document.getElementById("site-header")?.offsetHeight || 64;
  const barH = MOBILE_MQ.matches ? el.genBar.offsetHeight : 0;
  const visible = rect.top >= navH - 1 && rect.bottom <= window.innerHeight - barH + 1;
  if (visible) return;
  el.stage.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

/** Méta, badge, notices, actions et note : jamais autre chose que l'image affichée. */
function clearResultDetails() {
  el.meta.hidden = true;
  el.badge.replaceChildren();
  el.notices.replaceChildren();
  el.download.disabled = true;
  el.regenerate.disabled = true;
  el.about.hidden = true;
  el.about.open = false;
  el.aboutBody.replaceChildren();
}

function loadingKey(request) {
  return request.engine === "diffusion" && aiOn() ? "studio.loading.ai" : "studio.loading.fast";
}

function setLoading(request) {
  failure = null;
  clearResultDetails();
  el.error.hidden = true;
  el.empty.hidden = true;
  el.loading.hidden = false;
  el.loadingLabel.textContent = t(loadingKey(request));
  el.stage.classList.add("is-loading");
  el.stage.classList.toggle("is-ai", request.engine === "diffusion");
  el.stage.setAttribute("aria-busy", "true");
  el.result.classList.remove("is-empty"); // première génération : la scène reprend son format carré
  el.status.textContent = t(loadingKey(request));
  setBusy(el.generate, true, "studio.generating");
  revealResultArea();
}

function endLoading() {
  el.loading.hidden = true;
  el.stage.classList.remove("is-loading");
  el.stage.removeAttribute("aria-busy");
  setBusy(el.generate, false, "studio.generate");
}

function noticeFromResult(data) {
  const code = typeof data.notice_code === "string" && data.notice_code ? data.notice_code : null;
  if (code) {
    const key = has(`notice.${code}`) ? `notice.${code}` : "notice.service_error";
    return { tone: "warning", lines: [{ key, params: data.notice_params || {} }] };
  }
  if (data.notice) return { tone: "warning", lines: [{ raw: data.notice }] };
  return null;
}

function onSuccess(data, request) {
  const notices = [];
  if (request.size && Number(data.width) !== request.size) {
    notices.push({ tone: "info", lines: [{ key: "error.validation.size_adjusted", params: { n: data.width } }] });
  }
  const n = noticeFromResult(data);
  if (n) notices.push(n);
  // seed renvoyée par le serveur : « Régénérer » reproduit exactement l'image
  const entry = { id: ++entrySeq, result: data, request: { ...request, seed: data.seed }, notices };
  history.unshift(entry);
  history.length = Math.min(history.length, HISTORY_MAX);
  showEntry(entry, { fresh: true });
  el.status.textContent = t("studio.result.status_done");
}

function showEntry(entry, { fresh = false } = {}) {
  current = entry;
  failure = null;
  el.error.hidden = true;
  el.empty.hidden = true;
  el.img.hidden = false;
  if (el.img.getAttribute("src") !== entry.result.image) el.img.src = entry.result.image;
  el.stage.classList.toggle("is-ai", entry.result.source === "gemini");
  if (fresh && !prefersReducedMotion()) {
    el.img.classList.remove("is-fresh");
    void el.img.offsetWidth;
    el.img.classList.add("is-fresh");
  }
  renderEntryText();
  el.download.disabled = false;
  el.regenerate.disabled = false;
  el.about.hidden = !(assistOn() && !assistDown);
  el.about.open = false;
  el.aboutBody.replaceChildren();
  renderHistory();
}

/** Textes dépendant de la langue pour l'entrée affichée. */
function renderEntryText() {
  if (!current) return;
  const { result, request } = current;
  el.img.alt = t("studio.result.image_alt", { category: catName(request.category), palette: paletteName(request.palette) });

  el.metaMode.textContent = modeName(result.engine);
  el.metaSize.replaceChildren(numEl(`${result.width}×${result.height}`));
  const ms = Number(result.elapsed_ms) || 0;
  el.metaTime.replaceChildren(ms < 1000
    ? withNum("studio.meta.time_value", String(Math.round(ms)))
    : withNum("studio.meta.time_seconds", formatNumber(ms / 1000, { maximumFractionDigits: 1 })));
  el.metaSeed.replaceChildren(numEl(result.seed));
  el.meta.hidden = false;

  const badge = document.createElement("span");
  if (result.source === "gemini") {
    badge.className = "badge badge--ai";
    badge.innerHTML = icon("sparkle", { size: 14 });
    badge.append(document.createTextNode(t("badge.ai", { model: result.model || "Gemini" })));
  } else {
    badge.className = "badge";
    badge.innerHTML = icon(result.source === "trained_weights" ? "chart" : "bolt", { size: 14 });
    badge.append(document.createTextNode(t(result.source === "trained_weights" ? "badge.trained" : "badge.procedural")));
  }
  el.badge.replaceChildren(badge);
  el.notices.replaceChildren(...current.notices.map(noticeEl));
}

function errorDesc(r) {
  if (r.code === "network") return { key: "error.network" };
  if (r.code && has(`error.validation.${r.code}`)) return { key: `error.validation.${r.code}`, params: r.params };
  if (r.code === "http" && r.status) return { key: "error.http", params: { status: r.status } };
  return { key: "error.generic" };
}

const FIELD_ERROR_KEYS = {
  seed: { key: "error.validation.seed" },
  size: { key: "error.validation.size_range", params: { min: SIZE_MIN, max: SIZE_MAX } },
  prompt: { key: "error.validation.prompt_length", params: { max: PROMPT_MAX } },
  category: { key: "error.validation.category" },
  engine: { key: "error.validation.engine" },
  palette: { key: "error.validation.palette" },
};

function onFailure(r, request) {
  current = null;
  clearResultDetails();
  let desc = errorDesc(r);
  if (r.code === "validation" || r.status === 422) {
    const fields = Array.isArray(r.data?.fields) ? r.data.fields : [];
    const known = fields.filter((f) => FIELD_ERROR_KEYS[f]);
    if (known.length) desc = FIELD_ERROR_KEYS[known[0]];
    for (const f of known) if (FIELD_NODES[f]) setFieldError(f, FIELD_ERROR_KEYS[f]);
    const focusable = known.find((f) => FIELD_NODES[f]);
    if (focusable) focusField(focusable);
    for (const f of known) if (f === "palette") flash(document.getElementById("group-palette"));
    for (const f of known) if (f === "category") flash(document.getElementById("group-craft"));
  }
  failure = desc;
  // « Réessayer » rejoue la même requête, sauf erreur de saisie (elle échouerait à l'identique)
  failedRequest = r.code === "validation" || r.status === 422 ? null : request;
  el.retry.hidden = !failedRequest;
  el.img.hidden = true;
  el.empty.hidden = true;
  el.error.hidden = false;
  el.errorText.textContent = tx(desc);
  el.status.textContent = `${t("studio.result.error_title")}. ${tx(desc)}`;
  renderHistory(); // plus aucune miniature « affichée »
}

/* ---------- Actions ---------- */
function fileModeLabel(result) {
  if (result.engine === "gan") return "rapide";
  return result.source === "gemini" ? "ia" : "procedural";
}

el.download.addEventListener("click", () => {
  if (!current) return;
  const { category, seed } = current.request;
  const a = document.createElement("a");
  a.href = current.result.image;
  a.download = `zakhrafaai_${category}_${fileModeLabel(current.result)}_${seed}.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
});

el.copySeed.addEventListener("click", async () => {
  if (!current) return;
  try {
    await navigator.clipboard.writeText(String(current.result.seed));
  } catch {
    const range = document.createRange();
    range.selectNodeContents(el.metaSeed);
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    return;
  }
  el.copyDone.hidden = false;
  el.copySeed.classList.add("is-done");
  clearTimeout(el.copySeed._t);
  el.copySeed._t = setTimeout(() => { el.copyDone.hidden = true; el.copySeed.classList.remove("is-done"); }, 1600);
});

/* ---------- Historique ---------- */
function renderHistory() {
  el.history.replaceChildren();
  el.historyEmpty.hidden = history.length > 0;
  for (const entry of history) {
    const { result, request } = entry;
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "history__item";
    const isCurrent = entry === current;
    if (isCurrent) btn.setAttribute("aria-current", "true");
    btn.setAttribute("aria-label", t("studio.history.item_label", {
      category: catName(request.category), mode: modeName(result.engine), seed: result.seed,
    }) + (result.source === "gemini" ? ` · ${t("badge.ai", { model: result.model || "Gemini" })}` : "")
      + (isCurrent ? ` ${t("studio.history.current")}` : ""));
    const img = document.createElement("img");
    img.src = result.image;
    img.alt = "";
    img.decoding = "async";
    btn.appendChild(img);
    if (result.source === "gemini") {
      const b = document.createElement("span");
      b.className = "history__ai";
      b.innerHTML = icon("sparkle", { size: 12 });
      btn.appendChild(b);
    }
    btn.addEventListener("click", () => {
      if (pending) return;
      showEntry(entry);
      el.history.querySelector('[aria-current="true"]')?.focus();
    });
    li.appendChild(btn);
    el.history.appendChild(li);
  }
}

/* ------------------------------------------------------------------ */
/* Assistant (DeepSeek)                                                */
/* ------------------------------------------------------------------ */
/** Assistant visible seulement s'il est actif ET n'a pas répondu assist_disabled pendant la session. */
function renderAssistAvailability() {
  const on = assistOn() && !assistDown;
  el.assist.hidden = !on;
  el.enhance.hidden = !on;
  if (!on) el.enhanceUndo.hidden = true;
  if (!on) { el.about.hidden = true; el.about.open = false; }
  else if (current) el.about.hidden = false;
  syncAssistButtons();
}

/** Un seul appel d'assistant modifiant les réglages à la fois. */
function syncAssistButtons() {
  el.plan.disabled = assistDown || busy.plan || busy.enhance;
  el.enhance.disabled = assistDown || busy.plan || busy.enhance;
}

function assistErrorDesc(r) {
  if (r.code === "network") return { key: "error.network" };
  const limited = r.code === "assist_ip_limit" || (r.code === "http" && r.status === 429);
  if (limited && Number.isFinite(r.retryAfter) && r.retryAfter > 0) {
    return { key: "studio.assist.error.assist_ip_limit_wait", wait: r.retryAfter };
  }
  const k = `studio.assist.error.${r.code}`;
  if (r.code && has(k)) return { key: k };
  if (r.code && has(`error.validation.${r.code}`)) return { key: `error.validation.${r.code}`, params: r.params }; // ex. payload_too_large (413)
  if (r.code === "http" && r.status === 429) return { key: "studio.assist.error.assist_ip_limit" };
  return { key: "studio.assist.error.assist_error" };
}

function noteAssistFailure(r) {
  if (r.code === "assist_disabled") {
    assistDown = true;
    renderAssistAvailability(); // masque tout de suite le panneau, « Améliorer » et « À propos »
  }
}

/** Réponse arrivée après un changement de langue : on l'écarte (texte dans l'ancienne langue). */
const langChangedMsg = () => ({ tone: "info", lines: [{ key: "studio.assist.lang_changed" }] });

/* (a) idée -> réglages */
el.plan.addEventListener("click", runPlan);

async function runPlan() {
  if (el.plan.disabled) return;
  const idea = el.idea.value.trim();
  if (!idea) {
    msgs.plan = { tone: "warning", lines: [{ key: "studio.assist.empty" }] };
    renderMsg("plan", el.planOut);
    el.idea.focus();
    return;
  }
  msgs.plan = null;
  renderPlanMsg();
  const lang = getLang();
  busy.plan = true;
  setBusy(el.plan, true, "studio.assist.submitting");
  syncAssistButtons();
  el.idea.setAttribute("aria-busy", "true");
  const r = await postJSON("/api/assist/plan", { idea: idea.slice(0, IDEA_MAX), lang }, { timeout: 45000 });
  busy.plan = false;
  setBusy(el.plan, false, "studio.assist.submit");
  syncAssistButtons();
  el.idea.removeAttribute("aria-busy");
  if (r.code === "aborted") return;
  if (!r.ok || !r.data || typeof r.data !== "object") {
    noteAssistFailure(r);
    msgs.plan = { tone: "danger", lines: [assistErrorDesc(r)] };
    renderPlanMsg();
    return;
  }
  if (getLang() !== lang) { msgs.plan = langChangedMsg(); renderPlanMsg(); return; }
  applyPlan(r.data);
}

function applyPlan(d) {
  const changed = [];
  if (CATEGORIES.includes(d.category)) {
    if (d.category !== state.category) changed.push("group-craft");
    state.category = d.category;
    craftGroup.set(d.category);
  }
  if (ENGINES.includes(d.engine)) {
    if (d.engine !== state.engine) changed.push("group-mode");
    state.engine = d.engine;
    modeGroup.set(d.engine);
  }
  const knownPalette = meta.palettes.length ? meta.palettes.some((p) => p.id === d.palette) : typeof d.palette === "string";
  if (d.palette && knownPalette) {
    if (d.palette !== state.palette) changed.push("group-palette");
    selectPalette(d.palette);
  }
  if (state.engine === "diffusion" && typeof d.prompt === "string" && d.prompt.trim()) {
    if (el.prompt.value !== d.prompt) changed.push("group-prompt");
    el.prompt.value = d.prompt.trim().slice(0, PROMPT_MAX);
    enhancePrev = null;
    el.enhanceUndo.hidden = true;
    setFieldError("prompt", null);
    updatePromptCount();
  }
  renderMode();
  planInfo = {
    category: state.category, palette: state.palette, engine: state.engine,
    explanation: typeof d.explanation === "string" ? d.explanation.slice(0, 240) : "",
  };
  msgs.plan = planNotice();
  renderPlanMsg();
  // mise en valeur visible de ce qui a changé (tout, si rien n'a changé)
  (changed.length ? changed : ["group-craft", "group-mode", "group-palette"]).forEach((id) => flash($(id)));
}

function planNotice() {
  const p = planInfo;
  return {
    tone: "ai",
    title: { key: "studio.assist.applied_title" },
    lines: [
      { key: "studio.assist.summary", params: { category: catName(p.category), palette: paletteName(p.palette), mode: modeName(p.engine) } },
      p.explanation ? { raw: p.explanation } : null,
      { key: "studio.assist.applied_cta" },
    ],
  };
}

/* (b) Améliorer la description */
el.enhance.addEventListener("click", async () => {
  if (el.enhance.disabled) return;
  const text = el.prompt.value.trim();
  if (!text) {
    msgs.enhance = { tone: "warning", lines: [{ key: "studio.assist.enhance_empty" }] };
    renderMsg("enhance", el.enhanceOut);
    el.prompt.focus();
    return;
  }
  msgs.enhance = null;
  renderMsg("enhance", el.enhanceOut);
  const before = el.prompt.value;
  const lang = getLang();
  busy.enhance = true;
  setBusy(el.enhance, true, "studio.assist.enhancing");
  syncAssistButtons();
  el.prompt.readOnly = true;
  const r = await postJSON("/api/assist/enhance", { prompt: text, category: state.category, lang }, { timeout: 45000 });
  busy.enhance = false;
  setBusy(el.enhance, false, "studio.assist.enhance");
  syncAssistButtons();
  el.prompt.readOnly = false;
  if (r.code === "aborted") return;
  if (!r.ok || typeof r.data?.prompt !== "string" || !r.data.prompt.trim()) {
    noteAssistFailure(r);
    msgs.enhance = { tone: "danger", lines: [assistErrorDesc(r)] };
    renderMsg("enhance", el.enhanceOut);
    return;
  }
  // le texte a changé entre-temps (plan appliqué, saisie…) : ne pas l'écraser
  if (el.prompt.value !== before) return;
  if (getLang() !== lang) { msgs.enhance = langChangedMsg(); renderMsg("enhance", el.enhanceOut); return; }
  enhancePrev = el.prompt.value;
  el.prompt.value = r.data.prompt.trim().slice(0, PROMPT_MAX);
  updatePromptCount();
  el.enhanceUndo.hidden = false;
  msgs.enhance = { tone: "ai", lines: [{ key: "studio.assist.enhanced" }] };
  renderMsg("enhance", el.enhanceOut);
  flash(el.prompt.closest(".field"));
});

el.enhanceUndo.addEventListener("click", () => {
  if (enhancePrev == null) return;
  el.prompt.value = enhancePrev;
  enhancePrev = null;
  el.enhanceUndo.hidden = true;
  updatePromptCount();
  msgs.enhance = { tone: "info", lines: [{ key: "studio.assist.restored" }] };
  renderMsg("enhance", el.enhanceOut);
  el.prompt.focus();
});

/* (c) À propos de ce motif (chargé à l'ouverture) */
el.about.addEventListener("toggle", () => {
  if (el.about.open && current) loadCaption();
});

async function loadCaption() {
  const entry = current;
  if (!entry) return;
  const { category, palette } = entry.request;
  const lang = getLang();
  const key = `${category}|${palette}|${lang}`;
  const token = ++captionToken;
  if (captions.has(key)) return renderCaption(captions.get(key));
  el.aboutBody.replaceChildren();
  const wrap = document.createElement("div");
  wrap.className = "about__loading";
  wrap.innerHTML = '<span class="skeleton skeleton--text"></span><span class="skeleton skeleton--text"></span><span class="skeleton skeleton--text" style="inline-size:60%"></span>';
  const lab = document.createElement("p");
  lab.className = "sr-only";
  lab.textContent = t("studio.about.loading");
  wrap.appendChild(lab);
  el.aboutBody.appendChild(wrap);
  const r = await postJSON("/api/assist/caption", { category, palette, lang }, { timeout: 45000 });
  if (token !== captionToken || current !== entry || !el.about.open) return;
  if (r.ok && typeof r.data?.caption === "string" && r.data.caption.trim()) {
    captions.set(key, r.data.caption.trim());
    renderCaption(r.data.caption.trim());
  } else if (r.code !== "aborted") {
    noteAssistFailure(r);
    const retry = () => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn--quiet btn--sm about__retry";
      b.textContent = t("studio.about.retry");
      b.addEventListener("click", loadCaption);
      if (assistDown) b.hidden = true;
      return b;
    };
    el.aboutBody.replaceChildren(noticeEl({ tone: "danger", lines: [assistErrorDesc(r)], action: retry }));
  }
}

function renderCaption(text) {
  const p = document.createElement("p");
  p.className = "about__text";
  p.dir = "auto";
  p.textContent = text;
  const note = document.createElement("p");
  note.className = "field__hint about__note";
  note.textContent = t("studio.about.note");
  el.aboutBody.replaceChildren(p, note);
}

/* ------------------------------------------------------------------ */
/* Langue : re-rendu de tout texte produit en JS                       */
/* ------------------------------------------------------------------ */
onLangChange(() => {
  renderMode();
  renderPaletteNames();
  updatePromptCount();
  updateIdeaCount();
  for (const f of Object.keys(fieldErrors)) if (fieldErrors[f]) setFieldError(f, fieldErrors[f]);
  if (pending) {
    el.loadingLabel.textContent = t(loadingKey(pending));
  }
  if (current) renderEntryText();
  if (failure) el.errorText.textContent = tx(failure);
  renderHistory();
  if (planInfo && msgs.plan && msgs.plan.tone === "ai") msgs.plan = planNotice();
  renderPlanMsg();
  renderMsg("enhance", el.enhanceOut);
  if (el.about.open && current) loadCaption();
  else el.aboutBody.replaceChildren();
});

/* ------------------------------------------------------------------ */
/* Démarrage                                                           */
/* ------------------------------------------------------------------ */
(function applyQuery() {
  let q;
  try { q = new URLSearchParams(location.search); } catch { return; }
  const cat = q.get("category");
  if (CATEGORIES.includes(cat)) { state.category = cat; craftGroup.set(cat); }
  const mode = q.get("mode");
  const engine = mode === "ai" || mode === "diffusion" ? "diffusion" : mode === "fast" || mode === "gan" ? "gan" : null;
  if (engine) { state.engine = engine; modeGroup.set(engine); }
  const pal = q.get("palette");
  if (pal && /^[a-z_]{1,40}$/.test(pal)) state.palette = pal;
})();

renderMode();
renderPalettes();
updatePromptCount();
updateIdeaCount();
renderHistory();
refreshMeta();
