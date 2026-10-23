/* ZakhrafaAI — client API minimal, sans dépendance externe. */
const ZakhrafaAPI = (() => {
  const BASE = ""; // même origine (servi par FastAPI)

  // FastAPI renvoie `detail` sous forme de chaîne (HTTPException) ou de
  // tableau d'erreurs pydantic (422 de validation) : on aplatit en texte.
  function formatDetail(detail) {
    if (!detail) return null;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (typeof d === "string") return d;
          const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(".") : "";
          return field ? `${field} : ${d.msg}` : d.msg || JSON.stringify(d);
        })
        .join(" ; ");
    }
    return detail.msg || JSON.stringify(detail);
  }

  async function meta() {
    const res = await fetch(`${BASE}/api/meta`);
    if (!res.ok) throw new Error("Impossible de charger la configuration.");
    return res.json();
  }

  const NETWORK_ERROR = "Connexion interrompue — réessayez.";

  // `prompt` (souhait de style) n'est pris en compte qu'en rendu IA.
  // Les erreurs sont traduites en message lisible : coupure réseau
  // (TypeError « Failed to fetch »), erreur serveur/proxy (5xx), ou détail
  // renvoyé par l'API pour les requêtes refusées (4xx).
  async function generate({ category, engine, palette, seed, size, prompt }) {
    let res;
    try {
      res = await fetch(`${BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, engine, palette, seed, size, prompt: prompt || null }),
      });
    } catch (_) {
      throw new Error(NETWORK_ERROR);
    }
    if (!res.ok) {
      if (res.status >= 500) {
        throw new Error(`Service momentanément indisponible (HTTP ${res.status}) — réessayez.`);
      }
      const body = await res.json().catch(() => ({}));
      throw new Error(formatDetail(body.detail) || `Requête refusée (HTTP ${res.status}).`);
    }
    try {
      return await res.json();
    } catch (_) {
      // corps tronqué : la connexion a été coupée pendant la réponse
      throw new Error(NETWORK_ERROR);
    }
  }

  async function dashboard() {
    const res = await fetch(`${BASE}/api/dashboard`);
    if (!res.ok) throw new Error("Impossible de charger le tableau de bord.");
    return res.json();
  }

  return { meta, generate, dashboard };
})();
