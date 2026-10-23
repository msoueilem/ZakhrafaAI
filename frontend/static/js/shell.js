/* ZakhrafaAI — en-tête et pied de page partagés (module ES).
 *
 *   import { initI18n } from "/assets/js/i18n.js";
 *   import { initShell } from "/assets/js/shell.js";
 *   await initI18n("studio");
 *   initShell();                       // après initI18n
 *
 * Remplit <header id="site-header"> et <footer id="site-footer">.
 * Page active : <body data-page="landing|studio|dashboard">.
 * Options :
 *   sectionLinks : [{ href: "#how", key: "nav.how" }, …]  liens d'ancre propres à la page
 *                  (landing), affichés après les liens de pages.
 *   cta : false pour masquer le bouton d'appel (masqué d'office sur studio).
 * Tous les textes passent par data-i18n : setLang() les met à jour sans re-rendu.
 */
import { t, apply, setLang, getLang, withLang, SUPPORTED, onLangChange } from "./i18n.js";
import { icon, logoMark } from "./icons.js";

const PAGES = [
  { id: "landing", href: "/", key: "nav.home" },
  { id: "studio", href: "/studio", key: "nav.studio" },
  { id: "dashboard", href: "/dashboard", key: "nav.dashboard" },
];
const MOBILE_MQ = "(max-width: 899.98px)";

export function initShell({ sectionLinks = [], cta = true } = {}) {
  const page = document.body.dataset.page || "";
  const header = document.getElementById("site-header");
  const footer = document.getElementById("site-footer");
  if (header) renderHeader(header, page, sectionLinks, cta && page !== "studio");
  if (footer) renderFooter(footer, page);
  apply(header || document);
  if (footer) apply(footer);
  syncLinks();
  onLangChange(syncLinks);
}

/* ---------- En-tête ---------- */

function renderHeader(header, page, sectionLinks, showCta) {
  header.classList.add("site-header");
  const pageLinks = PAGES.map((p) => `<li><a class="nav-link" href="${p.href}" data-href="${p.href}" data-i18n="${p.key}"${p.id === page ? ' aria-current="page"' : ""}></a></li>`).join("");
  const anchors = sectionLinks.map((l) => `<li><a class="nav-link nav-link--section" href="${l.href}" data-i18n="${l.key}"></a></li>`).join("");
  const langItems = SUPPORTED.map((l) => `<li role="none"><button type="button" role="menuitemradio" class="lang-menu__item" data-lang="${l}" lang="${l}" dir="${l === "ar" ? "rtl" : "ltr"}" data-i18n="lang.${l}" tabindex="-1"></button></li>`).join("");

  header.innerHTML = `
<a class="skip-link" href="#main" data-i18n="a11y.skip"></a>
<div class="site-header__bar container">
  <a class="brand" href="/" data-href="/" data-i18n-attr="aria-label:a11y.brand_home">${logoMark(28)}<span class="brand__name" dir="ltr">Zakhrafa<span class="brand__ai">AI</span></span></a>
  <nav class="site-nav" id="site-nav" data-i18n-attr="aria-label:a11y.nav_main">
    <ul class="site-nav__list">${pageLinks}${anchors ? `<li class="site-nav__sep" aria-hidden="true"></li>${anchors}` : ""}</ul>
    ${showCta ? `<a class="btn btn--primary btn--block site-nav__cta" href="/studio" data-href="/studio"><span data-i18n="nav.cta"></span>${icon("arrow-end", { size: 18 })}</a>` : ""}
  </nav>
  <div class="site-header__actions">
    <div class="lang-switch">
      <button type="button" class="lang-switch__btn" id="lang-btn" aria-haspopup="menu" aria-expanded="false" aria-controls="lang-menu" data-i18n-attr="aria-label:lang.switcher_aria">
        ${icon("globe", { size: 18 })}<span class="lang-switch__code"></span>${icon("chevron-down", { size: 14, className: "lang-switch__chev" })}
      </button>
      <ul class="lang-menu" id="lang-menu" role="menu" aria-labelledby="lang-btn" hidden>${langItems}</ul>
    </div>
    ${showCta ? `<a class="btn btn--primary btn--sm site-header__cta" href="/studio" data-href="/studio" data-i18n="nav.cta"></a>` : ""}
    <button type="button" class="menu-btn" aria-expanded="false" aria-controls="site-nav" data-i18n-attr="aria-label:a11y.menu_open">
      <span class="menu-btn__bars" aria-hidden="true"><span></span><span></span><span></span></span>
    </button>
  </div>
</div>`;

  initScrollState(header);
  initLangSwitch(header);
  initMobileMenu(header);
}

function initScrollState(header) {
  let ticking = false;
  const update = () => {
    header.classList.toggle("is-scrolled", window.scrollY > 8);
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  update();
}

function initLangSwitch(header) {
  const btn = header.querySelector(".lang-switch__btn");
  const menu = header.querySelector(".lang-menu");
  const items = () => [...menu.querySelectorAll('[role="menuitemradio"]')];

  const open = (focusIdx) => {
    menu.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    const list = items();
    const i = focusIdx ?? Math.max(0, list.findIndex((it) => it.dataset.lang === getLang()));
    list[i]?.focus();
  };
  const close = (refocus = true) => {
    if (menu.hidden) return;
    menu.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (refocus) btn.focus();
  };

  btn.addEventListener("click", () => (menu.hidden ? open() : close()));
  btn.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      open(e.key === "ArrowUp" ? items().length - 1 : 0);
    }
  });
  menu.addEventListener("keydown", (e) => {
    const list = items();
    const i = list.indexOf(document.activeElement);
    let n = null;
    if (e.key === "ArrowDown") n = (i + 1) % list.length;
    else if (e.key === "ArrowUp") n = (i - 1 + list.length) % list.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = list.length - 1;
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    else if (e.key === "Tab") { close(false); return; }
    if (n != null) { e.preventDefault(); list[n].focus(); }
  });
  menu.addEventListener("click", async (e) => {
    const it = e.target.closest("[data-lang]");
    if (!it) return;
    close();
    await setLang(it.dataset.lang);
  });
  document.addEventListener("click", (e) => {
    if (!menu.hidden && !e.target.closest(".lang-switch")) close(false);
  });
}

function initMobileMenu(header) {
  const btn = header.querySelector(".menu-btn");
  const nav = header.querySelector(".site-nav");
  const mq = window.matchMedia(MOBILE_MQ);
  const isOpen = () => header.classList.contains("is-open");

  // hors header (main, footer…) : rendus inertes pendant l'ouverture
  const outside = () => [...document.body.children].filter((el) => el !== header && el.tagName !== "SCRIPT");

  function setOpen(open, { refocus = false } = {}) {
    header.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
    btn.setAttribute("data-i18n-attr", `aria-label:${open ? "a11y.menu_close" : "a11y.menu_open"}`);
    btn.setAttribute("aria-label", t(open ? "a11y.menu_close" : "a11y.menu_open"));
    document.documentElement.classList.toggle("scroll-locked", open);
    outside().forEach((el) => { el.inert = open; });
    if (open) nav.querySelector("a, button")?.focus();
    else if (refocus) btn.focus();
  }

  btn.addEventListener("click", () => setOpen(!isOpen()));
  nav.addEventListener("click", (e) => { if (e.target.closest("a") && isOpen()) setOpen(false); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) setOpen(false, { refocus: true });
    // piège de focus : header = bouton menu + feuille de navigation
    if (e.key === "Tab" && isOpen()) {
      const f = [...header.querySelectorAll("a[href], button:not([disabled])")].filter((el) => el.offsetParent !== null && !el.closest("[hidden]") && !el.classList.contains("skip-link"));
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  // clic sur le voile (hors en-tête) : fermeture
  document.addEventListener("click", (e) => { if (isOpen() && !header.contains(e.target)) setOpen(false); });
  mq.addEventListener("change", () => { if (!mq.matches && isOpen()) setOpen(false); });
}

/* ---------- Pied de page ---------- */

function renderFooter(footer, page) {
  footer.classList.add("site-footer");
  const links = PAGES.map((p) => `<li><a href="${p.href}" data-href="${p.href}" data-i18n="${p.key}"${p.id === page ? ' aria-current="page"' : ""}></a></li>`).join("");
  footer.innerHTML = `
<div class="container site-footer__grid">
  <div class="site-footer__brand">
    <a class="brand" href="/" data-href="/" data-i18n-attr="aria-label:a11y.brand_home">${logoMark(24)}<span class="brand__name" dir="ltr">Zakhrafa<span class="brand__ai">AI</span></span></a>
    <p class="site-footer__tagline" data-i18n="footer.tagline"></p>
  </div>
  <nav class="site-footer__nav" data-i18n-attr="aria-label:a11y.nav_main"><ul>${links}</ul></nav>
  <div class="site-footer__credits">
    <p data-i18n="footer.project"></p>
    <p data-i18n="footer.supervisor"></p>
    <p data-i18n="footer.ai_credit"></p>
  </div>
</div>
<div class="container site-footer__bottom">
  <p class="site-footer__disclaimer" data-i18n="footer.disclaimer"></p>
  <a class="site-footer__top" href="#main">${icon("arrow-up", { size: 16 })}<span data-i18n="footer.back_to_top"></span></a>
</div>`;
}

/* ---------- Synchronisation dépendant de la langue ---------- */

function syncLinks() {
  const lang = getLang();
  document.querySelectorAll(".lang-switch__code").forEach((el) => { el.textContent = t(`lang.${lang}_short`); });
  document.querySelectorAll(".lang-menu__item").forEach((it) => it.setAttribute("aria-checked", String(it.dataset.lang === lang)));
  // ?lang= sur les liens internes seulement si localStorage indisponible (cf. withLang)
  document.querySelectorAll("#site-header [data-href], #site-footer [data-href]").forEach((a) => { a.href = withLang(a.dataset.href); });
}
