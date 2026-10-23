/* ZakhrafaAI — internationalisation (module ES, sans dépendance).
 *
 *   import { initI18n, t, setLang } from "/assets/js/i18n.js";
 *   await initI18n("studio");          // charge i18n/<lang>/common.json + studio.json
 *   t("studio.quota.remaining", { n: 3 });
 *
 * Attributs reconnus par apply(root) :
 *   data-i18n="key"                     -> textContent
 *   data-i18n-html="key"                -> innerHTML (UNIQUEMENT nos JSON, jamais de donnée utilisateur/API)
 *   data-i18n-attr="placeholder:key;aria-label:key;title:key;content:key"
 *   data-i18n-params='{"n":3}'          -> paramètres d'interpolation pour les 3 précédents
 * <title data-i18n="meta.studio.title"> et <meta name="description" data-i18n-attr="content:…">
 * fonctionnent tels quels (apply() parcourt tout le document, <head> compris).
 */

export const SUPPORTED = ["fr", "ar", "en"];
export const DEFAULT_LANG = "fr";
const STORAGE_KEY = "zk.lang"; // partagé avec boot.js
const BASE = "/assets/i18n";

/* Locales Intl. Arabe : « ar-MA » (Maroc, public visé) + extension -u-nu-latn
   pour forcer les chiffres occidentaux 0-9 sur tous les moteurs : cohérence avec
   le contenu (chiffres latins dans les textes arabes), les seeds et les tailles px. */
const LOCALES = { fr: "fr-FR", ar: "ar-MA-u-nu-latn", en: "en-GB" };

const dicts = {};          // { fr: {...}, ar: {...} } — fusion common + page
const loaded = new Set();  // "fr/common", "ar/studio"…
let page = null;
let current = DEFAULT_LANG;
let storageOk = true;
const warned = new Set();

/* ---------- Résolution de langue ---------- */

function pick(v) {
  if (!v) return null;
  const s = String(v).toLowerCase().slice(0, 2);
  return SUPPORTED.includes(s) ? s : null;
}

function readStorage() {
  try { return localStorage.getItem(STORAGE_KEY); } catch { storageOk = false; return null; }
}

function writeStorage(lang) {
  try { localStorage.setItem(STORAGE_KEY, lang); storageOk = true; } catch { storageOk = false; }
}

/** ?lang= -> localStorage -> navigator.languages (ar*, en*, fr*) -> fr */
export function resolveLang() {
  let lang = null;
  try { lang = pick(new URLSearchParams(location.search).get("lang")); } catch { /* ignore */ }
  if (!lang) lang = pick(readStorage());
  if (!lang) {
    for (const l of navigator.languages || [navigator.language]) {
      lang = pick(l);
      if (lang) break;
    }
  }
  return lang || DEFAULT_LANG;
}

/* ---------- Chargement ---------- */

async function loadFile(lang, name) {
  const id = `${lang}/${name}`;
  if (loaded.has(id)) return;
  try {
    const res = await fetch(`${BASE}/${lang}/${name}.json`, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    Object.assign((dicts[lang] ||= {}), await res.json());
    loaded.add(id);
  } catch (err) {
    console.warn(`[i18n] ${id}.json introuvable`, err);
  }
}

async function loadLang(lang) {
  const files = ["common", page].filter(Boolean);
  const jobs = files.map((f) => loadFile(lang, f));
  // le français sert de repli pour toute clé manquante
  if (lang !== DEFAULT_LANG) jobs.push(...files.map((f) => loadFile(DEFAULT_LANG, f)));
  await Promise.all(jobs);
}

/* ---------- Traduction ---------- */

/** Traduit `key` ; `{nom}` est remplacé par params.nom. Repli : fr, puis la clé. */
export function t(key, params) {
  let s = dicts[current]?.[key];
  if (s == null) s = dicts[DEFAULT_LANG]?.[key];
  if (s == null) {
    if (!warned.has(key)) { warned.add(key); console.warn(`[i18n] clé manquante : ${key}`); }
    s = key;
  }
  if (params) s = s.replace(/\{(\w+)\}/g, (m, p) => (params[p] != null ? String(params[p]) : m));
  return s;
}

/** Vrai si la clé existe (langue active ou fr). */
export function has(key) {
  return dicts[current]?.[key] != null || dicts[DEFAULT_LANG]?.[key] != null;
}

function paramsOf(el) {
  const raw = el.getAttribute("data-i18n-params");
  if (!raw) return undefined;
  try { return JSON.parse(raw); } catch { return undefined; }
}

/** Applique les traductions sur `root` (document par défaut) et ses descendants. */
export function apply(root = document) {
  const scope = root.querySelectorAll ? root : document;
  const all = (sel) => {
    const list = [...scope.querySelectorAll(sel)];
    if (root !== document && root.matches?.(sel)) list.unshift(root);
    return list;
  };
  for (const el of all("[data-i18n]")) el.textContent = t(el.dataset.i18n, paramsOf(el));
  for (const el of all("[data-i18n-html]")) el.innerHTML = t(el.dataset.i18nHtml, paramsOf(el));
  for (const el of all("[data-i18n-attr]")) {
    const params = paramsOf(el);
    for (const pair of el.dataset.i18nAttr.split(";")) {
      const i = pair.indexOf(":");
      if (i < 1) continue;
      el.setAttribute(pair.slice(0, i).trim(), t(pair.slice(i + 1).trim(), params));
    }
  }
}

function setDocumentLang(lang) {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = dirOf(lang);
}

/* ---------- API publique ---------- */

/**
 * À appeler une fois par page, AVANT tout rendu dépendant du texte.
 * @param {"landing"|"studio"|"dashboard"|string} pageName fichier i18n/<lang>/<pageName>.json
 * @returns {Promise<string>} la langue active
 */
export async function initI18n(pageName) {
  page = pageName || null;
  current = resolveLang();
  setDocumentLang(current);
  await loadLang(current);
  apply(document);
  document.documentElement.classList.remove("i18n-pending");
  document.dispatchEvent(new CustomEvent("i18n:ready", { detail: info() }));
  return current;
}

/** Change de langue sans recharger : DOM, <html lang dir>, ?lang=, stockage, événement i18n:change. */
export async function setLang(lang) {
  lang = pick(lang) || DEFAULT_LANG;
  writeStorage(lang);
  try {
    const url = new URL(location.href);
    url.searchParams.set("lang", lang);
    history.replaceState(history.state, "", url);
  } catch { /* ignore */ }
  if (lang === current && loaded.has(`${lang}/common`)) return lang;
  await loadLang(lang);
  current = lang;
  setDocumentLang(lang);
  apply(document);
  document.dispatchEvent(new CustomEvent("i18n:change", { detail: info() }));
  return lang;
}

/** Abonnement pratique à i18n:change ; renvoie la fonction de désabonnement. */
export function onLangChange(cb) {
  const h = (e) => cb(e.detail);
  document.addEventListener("i18n:change", h);
  return () => document.removeEventListener("i18n:change", h);
}

export const getLang = () => current;
export const getLocale = () => LOCALES[current];
export const dirOf = (lang) => (lang === "ar" ? "rtl" : "ltr");
export const isRTL = () => current === "ar";
const info = () => ({ lang: current, dir: dirOf(current), locale: LOCALES[current] });

/** Ajoute ?lang= à un lien interne seulement si le stockage local est indisponible
    (sinon la langue suit via localStorage et les URL restent propres). */
export function withLang(href) {
  if (storageOk && readStorage() === current) return href;
  try {
    const url = new URL(href, location.href);
    if (url.origin !== location.origin) return href;
    url.searchParams.set("lang", current);
    return url.pathname + url.search + url.hash;
  } catch { return href; }
}

/* ---------- Formatage (Intl, locale active) ---------- */

export function formatNumber(n, opts) {
  return new Intl.NumberFormat(LOCALES[current], opts).format(n);
}

/** Date courte par défaut ; passer des options Intl.DateTimeFormat pour autre chose. */
export function formatDate(d, opts = { dateStyle: "medium" }) {
  return new Intl.DateTimeFormat(LOCALES[current], opts).format(d instanceof Date ? d : new Date(d));
}

export function formatTime(d, opts = { hour: "2-digit", minute: "2-digit" }) {
  return new Intl.DateTimeFormat(LOCALES[current], opts).format(d instanceof Date ? d : new Date(d));
}

/** « il y a 3 min » / « منذ 3 دقائق » / « 3 min ago ». */
export function formatRelative(d, now = Date.now()) {
  const diff = ((d instanceof Date ? d : new Date(d)).getTime() - now) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALES[current], { numeric: "auto", style: "short" });
  const steps = [[60, "second"], [60, "minute"], [24, "hour"], [7, "day"], [4.345, "week"], [12, "month"], [Infinity, "year"]];
  let v = diff;
  for (const [size, unit] of steps) {
    if (Math.abs(v) < size) return rtf.format(Math.round(v), unit);
    v /= size;
  }
  return "";
}

/** Valeur toujours LTR (seed, ID, hex, « 256×256 ») isolée du texte environnant. */
export function ltr(value) {
  const b = document.createElement("bdi");
  b.dir = "ltr";
  b.className = "ltr";
  b.textContent = String(value);
  return b;
}
