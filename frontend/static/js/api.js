/* ZakhrafaAI — client API minimal, sans dépendance externe. */
const ZakhrafaAPI = (() => {
  const BASE = ""; // même origine (servi par FastAPI)

  async function meta() {
    const res = await fetch(`${BASE}/api/meta`);
    if (!res.ok) throw new Error("Impossible de charger la configuration.");
    return res.json();
  }

  async function generate({ category, engine, palette, seed, size }) {
    const res = await fetch(`${BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, engine, palette, seed, size }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || "Échec de la génération.");
    }
    return res.json();
  }

  async function dashboard() {
    const res = await fetch(`${BASE}/api/dashboard`);
    if (!res.ok) throw new Error("Impossible de charger le tableau de bord.");
    return res.json();
  }

  return { meta, generate, dashboard };
})();
