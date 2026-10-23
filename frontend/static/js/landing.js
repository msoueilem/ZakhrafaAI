/* ZakhrafaAI — page d'accueil (module ES).
 * Tout le contenu est écrit en HTML (visible sans JS) ; ce module ajoute :
 * traductions, en-tête/pied partagés, icônes, textes composés (complexité,
 * chiffres), filtre de la galerie, révélation au défilement.
 */
import { initI18n, t, onLangChange, formatNumber, withLang } from "./i18n.js";
import { initShell } from "./shell.js";
import { initReveal } from "./ui.js";
import { icon } from "./icons.js";

await initI18n("landing");
initShell({
  sectionLinks: [
    { href: "#how", key: "nav.how" },
    { href: "#crafts", key: "nav.crafts" },
    { href: "#gallery", key: "nav.gallery" },
    { href: "#faq", key: "nav.faq" },
  ],
});

// Icônes : <span class="js-icon" data-icon="…" data-size="…">
document.querySelectorAll("main .js-icon").forEach((el) => {
  el.outerHTML = icon(el.dataset.icon, { size: Number(el.dataset.size) || 18 });
});

/* ---------- Galerie : filtre par artisanat ---------- */
const filters = document.querySelector(".gallery-filters");
const items = [...document.querySelectorAll(".g-item")];
const status = document.getElementById("gallery-status");
const empty = document.querySelector(".gallery-empty");
let current = "all";

function applyFilter(value, { announce = true } = {}) {
  current = value;
  let n = 0;
  for (const it of items) {
    const show = value === "all" || it.dataset.cat === value;
    it.hidden = !show;
    if (show) { n++; it.classList.add("is-in"); }
  }
  filters.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.filter === value)));
  document.querySelector(".gallery").classList.toggle("is-filtered", value !== "all");
  empty.hidden = n > 0;
  if (announce) status.textContent = t("gallery.count", { n: formatNumber(n) });
}

if (filters && items.length) {
  filters.hidden = false;
  filters.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip[data-filter]");
    if (chip && chip.dataset.filter !== current) applyFilter(chip.dataset.filter);
  });
}

/* ---------- Textes dépendant de la langue ---------- */
function renderDynamic() {
  document.querySelectorAll(".js-level").forEach((el) => {
    el.textContent = t("crafts.complexity", { level: t(el.dataset.levelKey) });
  });
  document.querySelectorAll(".js-num").forEach((el) => { el.textContent = formatNumber(Number(el.dataset.n)); });
  // liens internes du contenu : ?lang= seulement si le stockage local est indisponible
  document.querySelectorAll("main a[data-href]").forEach((a) => { a.href = withLang(a.dataset.href); });
  if (status.textContent) applyFilter(current);
}
renderDynamic();
onLangChange(renderDynamic);

initReveal();
