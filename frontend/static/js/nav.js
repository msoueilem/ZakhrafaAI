/* Menu de navigation mobile : sous 920 px, les liens sont repliés derrière
   un bouton (aria-expanded / aria-controls). Échap, un clic sur un lien ou
   en dehors du menu le referment. */
(() => {
  const toggle = document.querySelector(".nav-toggle");
  const menu = toggle && document.getElementById(toggle.getAttribute("aria-controls"));
  if (!menu) return;

  function setOpen(open, { focusToggle = false } = {}) {
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Fermer le menu" : "Ouvrir le menu");
    menu.classList.toggle("open", open);
    if (focusToggle) toggle.focus();
  }

  const isOpen = () => toggle.getAttribute("aria-expanded") === "true";

  toggle.addEventListener("click", () => setOpen(!isOpen()));
  menu.addEventListener("click", (e) => {
    if (e.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen()) setOpen(false, { focusToggle: true });
  });
  document.addEventListener("click", (e) => {
    if (isOpen() && !menu.contains(e.target) && !toggle.contains(e.target)) setOpen(false);
  });
})();
