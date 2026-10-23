/* ZakhrafaAI — petit client HTTP (module ES). Ne lève JAMAIS d'exception :
 * renvoie toujours un objet résultat.
 *
 *   import { getJSON, postJSON, errorMessage } from "/assets/js/http.js";
 *   const r = await postJSON("/api/generate", payload, { timeout: 90000 });
 *   if (r.ok) render(r.data); else showError(errorMessage(r));
 *
 * Résultat :
 *   succès : { ok: true,  data, status, code: null }
 *   échec  : { ok: false, data, status, code, params }
 *     code = "network"    coupure réseau, délai dépassé ou corps illisible (status 0 si pas de réponse)
 *            "aborted"    annulé par le `signal` de l'appelant (ne rien afficher)
 *            "validation" HTTP 422 (data.detail = détail pydantic/FastAPI)
 *            "<code>"     code métier renvoyé par l'API : body.code ou body.detail.code
 *                         (ex. size_range, seed, prompt_length… -> clé error.validation.<code>)
 *            "http"       toute autre réponse non 2xx
 *     params = body.params ou body.detail.params (pour l'interpolation), sinon {}
 */
import { t, has } from "./i18n.js";

const DEFAULT_TIMEOUT = 60000;

export async function request(url, { method = "GET", body, headers, timeout = DEFAULT_TIMEOUT, signal } = {}) {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = timeout > 0 ? setTimeout(() => { timedOut = true; ctrl.abort(); }, timeout) : null;
  const onAbort = () => ctrl.abort();
  if (signal) {
    if (signal.aborted) ctrl.abort();
    else signal.addEventListener("abort", onAbort, { once: true });
  }

  const init = { method, headers: { Accept: "application/json", ...headers }, signal: ctrl.signal };
  if (body !== undefined) {
    if (body instanceof FormData || typeof body === "string") init.body = body;
    else {
      init.body = JSON.stringify(body);
      init.headers["Content-Type"] = "application/json";
    }
  }

  const fail = (code, status = 0, data = null) => {
    const d = data && typeof data === "object" ? data : {};
    const detail = d.detail && typeof d.detail === "object" && !Array.isArray(d.detail) ? d.detail : {};
    return { ok: false, code, status, data, params: d.params || detail.params || {} };
  };

  try {
    let res;
    try {
      res = await fetch(url, init);
    } catch {
      return fail(signal?.aborted && !timedOut ? "aborted" : "network");
    }
    let data = null;
    const text = await res.text().catch(() => null);
    if (text == null) return fail("network", res.status); // corps tronqué / connexion coupée
    if (text) {
      try { data = JSON.parse(text); } catch { data = text; }
    }
    if (res.ok) return { ok: true, data, status: res.status, code: null };

    const apiCode = data && typeof data === "object" ? data.code || data.detail?.code : null;
    return fail(apiCode || (res.status === 422 ? "validation" : "http"), res.status, data);
  } finally {
    if (timer) clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export const getJSON = (url, opts) => request(url, { ...opts, method: "GET" });
export const postJSON = (url, body, opts) => request(url, { ...opts, method: "POST", body });

/** Message traduit pour un résultat en échec (chaîne vide si "aborted"). */
export function errorMessage(r) {
  if (!r || r.ok) return "";
  if (r.code === "aborted") return "";
  if (r.code === "network") return t("error.network");
  if (has(`error.validation.${r.code}`)) return t(`error.validation.${r.code}`, r.params);
  if (r.code === "http") return t("error.http", { status: r.status });
  return t("error.generic"); // "validation" sans code connu, ou code métier non traduit
}
