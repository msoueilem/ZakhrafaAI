/* ZakhrafaAI — comportements partagés des composants (module ES).
 *
 *   import { initRadioGroup, initReveal, prefersReducedMotion } from "/assets/js/ui.js";
 *
 * initRadioGroup(el, { onChange })
 *   el = [role=radiogroup] contenant des [role=radio][data-value].
 *   Gère : aria-checked, tabindex itinérant, flèches (sens inversé en RTL),
 *   Home/End, clic. Émet sur `el` l'événement "change" { detail: { value } }.
 *   Si el.classList.contains("segmented") : positionne l'indicateur glissant
 *   (variables --seg-index / --seg-count).
 *   Renvoie { get value(), set(value, {silent}) }.
 *
 * initReveal(root = document) : ajoute .is-in aux .reveal visibles (IntersectionObserver).
 *   Contenu visible par défaut : sans JS (ou en mouvement réduit), rien n'est masqué.
 */

export const prefersReducedMotion = () =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

const isRTL = (el) => getComputedStyle(el).direction === "rtl";

export function initRadioGroup(el, { onChange } = {}) {
  const items = () => [...el.querySelectorAll('[role="radio"]')].filter((r) => !r.hasAttribute("disabled") && r.getAttribute("aria-disabled") !== "true");
  const all = () => [...el.querySelectorAll('[role="radio"]')];

  function sync() {
    const list = all();
    let idx = list.findIndex((r) => r.getAttribute("aria-checked") === "true");
    list.forEach((r, i) => r.setAttribute("tabindex", i === (idx < 0 ? 0 : idx) ? "0" : "-1"));
    if (el.classList.contains("segmented")) {
      el.style.setProperty("--seg-count", String(list.length || 1));
      el.style.setProperty("--seg-index", String(Math.max(0, idx)));
      el.classList.toggle("is-ready", idx >= 0); // active l'indicateur glissant (sinon fond statique)
    }
  }

  function select(radio, { focus = false, silent = false } = {}) {
    if (!radio) return;
    const changed = radio.getAttribute("aria-checked") !== "true";
    all().forEach((r) => r.setAttribute("aria-checked", String(r === radio)));
    sync();
    if (focus) radio.focus();
    if (changed && !silent) {
      const value = radio.dataset.value;
      onChange?.(value, radio);
      el.dispatchEvent(new CustomEvent("change", { detail: { value }, bubbles: true }));
    }
  }

  el.addEventListener("click", (e) => {
    const r = e.target.closest('[role="radio"]');
    if (r && el.contains(r) && items().includes(r)) select(r);
  });

  el.addEventListener("keydown", (e) => {
    const list = items();
    const cur = list.indexOf(document.activeElement);
    if (cur < 0) return;
    const rtl = isRTL(el);
    let next = null;
    switch (e.key) {
      case "ArrowRight": next = cur + (rtl ? -1 : 1); break;
      case "ArrowLeft": next = cur + (rtl ? 1 : -1); break;
      case "ArrowDown": next = cur + 1; break;
      case "ArrowUp": next = cur - 1; break;
      case "Home": next = 0; break;
      case "End": next = list.length - 1; break;
      case " ": case "Enter": e.preventDefault(); select(list[cur]); return;
      default: return;
    }
    e.preventDefault();
    next = (next + list.length) % list.length;
    select(list[next], { focus: true }); // le focus suit la sélection (motif APG radiogroup)
  });

  sync();
  return {
    get value() { return all().find((r) => r.getAttribute("aria-checked") === "true")?.dataset.value; },
    set(value, { silent = true } = {}) { select(all().find((r) => r.dataset.value === String(value)), { silent }); },
    refresh: sync,
  };
}

export function initReveal(root = document) {
  const els = root.querySelectorAll(".reveal:not(.is-in)");
  if (!els.length) return;
  if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
    els.forEach((el) => el.classList.add("is-in"));
    return;
  }
  // le masquage CSS n'est actif qu'avec cette classe : sans appel à initReveal, tout reste visible
  document.documentElement.classList.add("reveal-on");
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
  els.forEach((el) => io.observe(el));
}

/** Défilement doux sauf en mouvement réduit. */
export function scrollToEl(el, block = "start") {
  el?.scrollIntoView({ block, behavior: prefersReducedMotion() ? "auto" : "smooth" });
}
