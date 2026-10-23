/* ZakhrafaAI — icônes linéaires inline (24×24, trait currentColor).
 *   import { icon } from "/assets/js/icons.js";
 *   btn.innerHTML = icon("download") + `<span>${t("studio.download")}</span>`;
 * Les icônes directionnelles (DIR) reçoivent la classe .icon-dir et sont
 * miroitées en RTL par base.css. Toujours décoratives (aria-hidden) :
 * le libellé accessible vient du texte voisin ou d'un aria-label.
 */
const P = {
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  "chevron-down": '<path d="M6 9l6 6 6-6"/>',
  "chevron-end": '<path d="M9 6l6 6-6 6"/>',
  "arrow-end": '<path d="M5 12h14M13 6l6 6-6 6"/>',
  "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  star: '<path d="M12 3l2.6 4.2 4.8-1.6-1.6 4.8L22 12l-4.2 2.6 1.6 4.8-4.8-1.6L12 22l-2.6-4.2-4.8 1.6 1.6-4.8L2 12l4.2-2.6-1.6-4.8 4.8 1.6z"/>',
  diamond: '<path d="M12 3l9 9-9 9-9-9z"/><path d="M12 8l4 4-4 4-4-4z"/>',
  flower: '<circle cx="12" cy="12" r="2.5"/><path d="M12 9.5C10 6 10.5 3.5 12 3c1.5.5 2 3 0 6.5zM12 14.5c2 3.5 1.5 6 0 6.5-1.5-.5-2-3 0-6.5zM9.5 12C6 14 3.5 13.5 3 12c.5-1.5 3-2 6.5 0zM14.5 12c3.5-2 6-1.5 6.5 0-.5 1.5-3 2-6.5 0z"/>',
  bolt: '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.01"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
};
const DIR = new Set(["chevron-end", "arrow-end"]);

export function icon(name, { size = 20, className = "" } = {}) {
  const body = P[name];
  if (!body) return "";
  const cls = ["icon", DIR.has(name) ? "icon-dir" : "", className].filter(Boolean).join(" ");
  return `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
}

export const ICONS = Object.keys(P);

/* Logo : étoile à 8 branches (khatam), jamais miroitée. */
let logoCount = 0;
export function logoMark(size = 28) {
  const id = `zk-logo-g${++logoCount}`;
  return `<svg class="logo-mark" width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
<defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFD27A"/><stop offset=".55" stop-color="#E8743A"/><stop offset="1" stop-color="#9D8FFF"/></linearGradient></defs>
<path d="M16 2.5L18.83 9.16 25.55 6.45 22.84 13.17 29.5 16 22.84 18.83 25.55 25.55 18.83 22.84 16 29.5 13.17 22.84 6.45 25.55 9.16 18.83 2.5 16 9.16 13.17 6.45 6.45 13.17 9.16Z" fill="none" stroke="url(#${id})" stroke-width="1.8" stroke-linejoin="round"/>
<path d="M17.61 12.12L19.88 14.39 19.88 17.61 17.61 19.88 14.39 19.88 12.12 17.61 12.12 14.39 14.39 12.12Z" fill="url(#${id})"/></svg>`;
}
