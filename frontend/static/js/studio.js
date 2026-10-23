(() => {
  // palettes (id, libellé, couleurs réelles) chargées depuis /api/meta :
  // les couleurs ne sont définies que côté serveur (generators/utils.py)
  let palettes = [];

  const state = {
    category: "zellige",
    engine: "gan",
    palette: "zellige_classique",
    seed: null,
    size: null,
  };

  // état du rendu IA d'après /api/meta (null tant qu'inconnu)
  let ai = null;
  const PROMPT_MAX = 300;
  const SIZE_MIN = 128;
  const SIZE_MAX = 1024;

  const els = {
    categorySeg: document.getElementById("categorySeg"),
    engineSeg: document.getElementById("engineSeg"),
    paletteSwatches: document.getElementById("paletteSwatches"),
    seedInput: document.getElementById("seedInput"),
    sizeInput: document.getElementById("sizeInput"),
    generateBtn: document.getElementById("generateBtn"),
    regenBtn: document.getElementById("regenBtn"),
    downloadBtn: document.getElementById("downloadBtn"),
    canvasWrap: document.getElementById("canvasWrap"),
    metaRow: document.getElementById("metaRow"),
    metaEngine: document.getElementById("metaEngine"),
    metaSize: document.getElementById("metaSize"),
    metaTime: document.getElementById("metaTime"),
    metaSeed: document.getElementById("metaSeed"),
    metaSourceWrap: document.getElementById("metaSourceWrap"),
    galleryGrid: document.getElementById("galleryGrid"),
    engineHint: document.getElementById("engineHint"),
    promptField: document.getElementById("promptField"),
    promptInput: document.getElementById("promptInput"),
    promptCount: document.getElementById("promptCount"),
    noticeBox: document.getElementById("noticeBox"),
    seedError: document.getElementById("seedError"),
  };

  // Résultat affiché { result, request, notices } (le nom du fichier
  // téléchargé et « Régénérer » s'appuient dessus, pas sur l'état courant) ;
  // `history` garde les 12 derniers, restaurables depuis les miniatures.
  let last = null;
  const history = [];

  function renderPalettes() {
    els.paletteSwatches.replaceChildren();
    if (!palettes.length) {
      const msg = document.createElement("small");
      msg.className = "field-hint";
      msg.textContent = "Palettes indisponibles : la palette par défaut sera utilisée.";
      els.paletteSwatches.appendChild(msg);
      return;
    }
    palettes.forEach((p) => {
      const active = p.id === state.palette;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "swatch" + (active ? " active" : "");
      btn.setAttribute("aria-pressed", String(active));
      // bande multicolore : les vraies couleurs de la palette, dans l'ordre
      const strip = document.createElement("span");
      strip.className = "swatch-strip";
      strip.setAttribute("aria-hidden", "true");
      (p.colors || []).forEach((c) => {
        const stop = document.createElement("span");
        stop.style.background = c;
        strip.appendChild(stop);
      });
      const label = document.createElement("span");
      label.className = "swatch-label";
      label.textContent = p.label;
      btn.append(strip, label);
      btn.addEventListener("click", () => {
        state.palette = p.id;
        renderPalettes();
      });
      els.paletteSwatches.appendChild(btn);
    });
  }

  function wireSegmented(container, key, onChange) {
    container.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        container.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state[key] = btn.dataset.value;
        if (onChange) onChange();
      });
    });
  }

  // Texte d'aide du mode choisi + champ « style souhaité » (rendu IA seulement)
  function renderEngineHint() {
    const isAI = state.engine === "diffusion";
    els.promptField.style.display = isAI ? "" : "none";
    if (!isAI) {
      els.engineHint.textContent = "Instantané et gratuit : motif géométrique procédural (256 px).";
      return;
    }
    if (!ai) {
      els.engineHint.textContent = "Géométrie procédurale + rendu Gemini (768 px) ; repli sur le procédural si le service IA est indisponible.";
    } else if (!ai.enabled) {
      els.engineHint.textContent = "Rendu IA indisponible sur ce serveur (clé Gemini absente) : ce mode renvoie le motif procédural 768 px.";
    } else {
      els.engineHint.textContent = `Géométrie procédurale + rendu Gemini (${ai.model}), 768 px. Rendus IA restants aujourd'hui : ${ai.remaining_today}.`;
    }
  }

  // /api/meta : état du rendu IA (quota) et, au premier chargement, palettes
  async function refreshAI() {
    let meta = null;
    try {
      meta = await ZakhrafaAPI.meta();
    } catch (_) {
      meta = null;
    }
    ai = (meta && meta.ai) || null;
    renderEngineHint();
    if (!palettes.length && meta && Array.isArray(meta.palettes)) {
      palettes = meta.palettes;
      renderPalettes();
    } else if (!meta && !palettes.length) {
      renderPalettes();
    }
  }

  function updatePromptCount() {
    els.promptCount.textContent = `${els.promptInput.value.length} / ${PROMPT_MAX}`;
  }

  // Sur téléphone, les réglages sont sous la galerie : au lancement, on ramène
  // la zone de résultat à l'écran si elle n'est pas visible (sans animation
  // si l'utilisateur a demandé à réduire les mouvements).
  function revealResultArea() {
    const rect = els.canvasWrap.getBoundingClientRect();
    const navH = document.querySelector(".nav")?.offsetHeight || 0;
    const visible = rect.top >= navH && rect.bottom <= window.innerHeight;
    if (visible) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    els.canvasWrap.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
  }

  // Masque les détails (méta, badge, notice) et désactive Télécharger /
  // Régénérer : ils ne doivent jamais décrire autre chose que l'image affichée.
  function clearResultDetails() {
    els.metaRow.style.display = "none";
    els.metaSourceWrap.replaceChildren();
    els.noticeBox.textContent = "";
    els.noticeBox.style.display = "none";
    els.downloadBtn.disabled = true;
    els.regenBtn.disabled = true;
  }

  function setLoading(request) {
    const text = request.engine === "diffusion" && ai && ai.enabled
      ? "Rendu IA en cours… (10–30 s)"
      : "Génération en cours…";
    els.canvasWrap.innerHTML = `
      <div class="loading-shimmer" role="status">
        <div class="spinner"></div>
        <span>${text}</span>
      </div>`;
    clearResultDetails();
    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Génération…";
    revealResultArea();
  }

  const CAT_LABELS = { zellige: "Zellige", tapis: "Tapis", broderie: "Broderie" };
  const engineLabel = (engine) => (engine === "gan" ? "Rapide" : "Rendu IA");

  // Affiche un résultat (nouveau ou restauré depuis l'historique) : image,
  // méta, badge, notice ; Télécharger / Régénérer s'appuient sur `entry`.
  function showEntry(entry) {
    const { result, request } = entry;
    last = entry;
    els.canvasWrap.innerHTML = "";
    const img = document.createElement("img");
    img.src = result.image;
    img.alt = `Motif ${request.category} généré`;
    els.canvasWrap.appendChild(img);
    els.metaRow.style.display = "flex";
    els.metaEngine.textContent = engineLabel(result.engine);
    els.metaSize.textContent = `${result.width}×${result.height}`;
    els.metaTime.textContent = `${result.elapsed_ms} ms`;
    els.metaSeed.textContent = result.seed;
    const label = result.source === "gemini"
      ? `Rendu IA · ${result.model}`
      : result.source === "trained_weights" ? "Poids entraînés" : "Générateur procédural";
    // textContent : nom du modèle et notice viennent du serveur
    const badge = document.createElement("span");
    badge.className = `badge-source ${result.source}`;
    badge.innerHTML = `<span class="dot"></span>`;
    badge.appendChild(document.createTextNode(label));
    els.metaSourceWrap.replaceChildren(badge);
    els.noticeBox.textContent = entry.notices.join("\n");
    els.noticeBox.style.display = entry.notices.length ? "" : "none";
    els.downloadBtn.disabled = false;
    els.regenBtn.disabled = false;
    renderHistory();
  }

  // Miniatures = boutons qui restaurent le résultat correspondant
  function renderHistory() {
    els.galleryGrid.replaceChildren();
    history.forEach((entry) => {
      const { result, request } = entry;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gallery-item";
      const current = entry === last;
      if (current) btn.setAttribute("aria-current", "true");
      btn.setAttribute("aria-label",
        `Afficher : ${CAT_LABELS[request.category] || request.category}, ${engineLabel(result.engine)}, seed ${result.seed}`
        + (current ? " (affiché)" : ""));
      const img = document.createElement("img");
      img.src = result.image;
      img.alt = "";
      btn.appendChild(img);
      btn.addEventListener("click", () => {
        showEntry(entry);
        els.galleryGrid.querySelector('[aria-current="true"]')?.focus();
      });
      els.galleryGrid.appendChild(btn);
    });
  }

  function renderResult(result, request) {
    // le serveur borne la résolution à 128–1024 px : on le signale
    const notices = [];
    if (request.size && result.width !== request.size) {
      notices.push(`Résolution ajustée à ${result.width} px (autorisé : ${SIZE_MIN}–${SIZE_MAX} px).`);
    }
    if (result.notice) notices.push(result.notice);
    // seed renvoyée par le serveur : permet de reproduire exactement l'image
    const entry = { result, request: { ...request, seed: result.seed }, notices };
    history.unshift(entry);
    history.length = Math.min(history.length, 12);
    showEntry(entry);
  }

  function renderError(message) {
    // plus de résultat valide : Télécharger / Régénérer restent désactivés
    // jusqu'au prochain succès
    last = null;
    clearResultDetails();
    renderHistory(); // plus aucune miniature « affichée »
    // textContent : le message vient du serveur, on ne l'interprète pas en HTML
    const box = document.createElement("div");
    box.className = "canvas-placeholder";
    box.setAttribute("role", "alert");
    box.style.color = "var(--danger)";
    box.textContent = `Échec de la génération : ${message}`;
    els.canvasWrap.innerHTML = "";
    els.canvasWrap.appendChild(box);
  }

  function showSeedError(message) {
    els.seedError.textContent = message || "";
    els.seedError.hidden = !message;
    if (message) els.seedInput.setAttribute("aria-invalid", "true");
    else els.seedInput.removeAttribute("aria-invalid");
  }

  // Seed : entier ≥ 0 représentable exactement en JavaScript (sinon la seed
  // renvoyée par le serveur ne serait pas relue à l'identique).
  // Renvoie { seed } ou { error }.
  function parseSeed(raw) {
    const text = raw.trim();
    if (!text) return { seed: null };
    if (!/^\d+$/.test(text)) return { error: "La seed doit être un entier positif ou nul (ex. 42)." };
    const value = Number(text);
    if (!Number.isSafeInteger(value)) {
      return { error: `Seed trop grande : maximum ${Number.MAX_SAFE_INTEGER}.` };
    }
    return { seed: value };
  }

  // Renvoie la requête, ou null si un champ est invalide (message affiché)
  function currentRequest() {
    // un champ number contenant du texte non numérique renvoie "" + badInput
    if (els.seedInput.validity.badInput) {
      showSeedError("La seed doit être un entier positif ou nul (ex. 42).");
      return null;
    }
    const parsed = parseSeed(els.seedInput.value);
    if (parsed.error) {
      showSeedError(parsed.error);
      return null;
    }
    showSeedError(null);
    const sizeVal = els.sizeInput.value ? Math.round(Number(els.sizeInput.value)) : null;
    return {
      category: state.category,
      engine: state.engine,
      palette: state.palette,
      seed: parsed.seed,
      size: Number.isFinite(sizeVal) && sizeVal > 0 ? sizeVal : null,
      prompt: state.engine === "diffusion" ? els.promptInput.value.trim() || null : null,
    };
  }

  // « Générer » : réglages courants (nouvelle seed si le champ est vide).
  // « Régénérer » : rejoue exactement la dernière requête, seed comprise.
  async function doGenerate(request) {
    setLoading(request);
    try {
      const result = await ZakhrafaAPI.generate(request);
      renderResult(result, request);
    } catch (err) {
      renderError(err.message || "erreur inconnue");
    } finally {
      els.generateBtn.disabled = false;
      els.generateBtn.textContent = "Générer le motif";
      // succès ou échec : le serveur a pu terminer (et décompter) le rendu IA
      // même si la réponse n'est pas arrivée, on relit donc le quota restant
      if (request.engine === "diffusion") refreshAI();
    }
  }

  els.generateBtn.addEventListener("click", () => {
    const request = currentRequest();
    if (request) doGenerate(request);
    else els.seedInput.focus();
  });
  els.seedInput.addEventListener("input", () => showSeedError(null));
  els.regenBtn.addEventListener("click", () => {
    if (last) doGenerate({ ...last.request });
  });
  els.downloadBtn.addEventListener("click", () => {
    if (!last) return;
    const { category, engine, seed } = last.request;
    const a = document.createElement("a");
    a.href = last.result.image;
    a.download = `zakhrafaai_${category}_${engine}_${seed}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  wireSegmented(els.categorySeg, "category");
  wireSegmented(els.engineSeg, "engine", renderEngineHint);
  els.promptInput.addEventListener("input", updatePromptCount);
  updatePromptCount();
  refreshAI();
})();
