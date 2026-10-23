(() => {
  const PALETTES = [
    { id: "fes_bleu", label: "Bleu de Fès", color: "#0B3D5C" },
    { id: "zellige_classique", label: "Zellige classique", color: "#01BAEF" },
    { id: "terracotta", label: "Terracotta", color: "#B5533C" },
    { id: "emeraude", label: "Émeraude", color: "#2E7D5B" },
    { id: "berbere", label: "Berbère", color: "#7A1E2B" },
    { id: "monochrome_ivoire", label: "Ivoire", color: "#8C8C8C" },
  ];

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
  };

  // Dernier résultat + paramètres de la requête qui l'a produit (le nom du
  // fichier téléchargé et « Régénérer » s'appuient dessus, pas sur l'état courant).
  let last = null;
  const history = [];

  function renderPalettes() {
    els.paletteSwatches.innerHTML = "";
    PALETTES.forEach((p) => {
      const btn = document.createElement("button");
      btn.className = "swatch" + (p.id === state.palette ? " active" : "");
      btn.style.background = p.color;
      btn.style.border = p.id === state.palette ? "2px solid var(--gold-soft)" : "2px solid transparent";
      btn.title = p.label;
      btn.setAttribute("aria-label", p.label);
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

  async function refreshAI() {
    try {
      ai = (await ZakhrafaAPI.meta()).ai || null;
    } catch (_) {
      ai = null;
    }
    renderEngineHint();
  }

  function updatePromptCount() {
    els.promptCount.textContent = `${els.promptInput.value.length} / ${PROMPT_MAX}`;
  }

  function setLoading(request) {
    const text = request.engine === "diffusion" && ai && ai.enabled
      ? "Rendu IA en cours… (10–30 s)"
      : "Génération en cours…";
    els.canvasWrap.innerHTML = `
      <div class="loading-shimmer">
        <div class="spinner"></div>
        <span>${text}</span>
      </div>`;
    els.noticeBox.style.display = "none";
    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Génération…";
  }

  function renderResult(result, request) {
    // seed renvoyée par le serveur : permet de reproduire exactement l'image
    last = { image: result.image, request: { ...request, seed: result.seed } };
    els.canvasWrap.innerHTML = "";
    const img = document.createElement("img");
    img.src = result.image;
    img.alt = `Motif ${request.category} généré`;
    els.canvasWrap.appendChild(img);
    els.metaRow.style.display = "flex";
    els.metaEngine.textContent = result.engine === "gan" ? "Rapide" : "Rendu IA";
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
    els.noticeBox.textContent = result.notice || "";
    els.noticeBox.style.display = result.notice ? "" : "none";
    els.downloadBtn.disabled = false;
    els.regenBtn.disabled = false;

    history.unshift(result.image);
    history.length = Math.min(history.length, 12);
    els.galleryGrid.innerHTML = "";
    history.forEach((src) => {
      const img = document.createElement("img");
      img.src = src;
      els.galleryGrid.appendChild(img);
    });
  }

  function renderError(message) {
    // textContent : le message vient du serveur, on ne l'interprète pas en HTML
    const box = document.createElement("div");
    box.className = "canvas-placeholder";
    box.style.color = "var(--danger)";
    box.textContent = `Échec de la génération : ${message}`;
    els.canvasWrap.innerHTML = "";
    els.canvasWrap.appendChild(box);
  }

  function currentRequest() {
    const seedVal = els.seedInput.value ? parseInt(els.seedInput.value, 10) : null;
    const sizeVal = els.sizeInput.value ? parseInt(els.sizeInput.value, 10) : null;
    return {
      category: state.category,
      engine: state.engine,
      palette: state.palette,
      seed: Number.isNaN(seedVal) ? null : seedVal,
      size: Number.isNaN(sizeVal) ? null : sizeVal,
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
      if (request.engine === "diffusion") refreshAI(); // quota restant à jour
    }
  }

  els.generateBtn.addEventListener("click", () => doGenerate(currentRequest()));
  els.regenBtn.addEventListener("click", () => {
    if (last) doGenerate({ ...last.request });
  });
  els.downloadBtn.addEventListener("click", () => {
    if (!last) return;
    const { category, engine, seed } = last.request;
    const a = document.createElement("a");
    a.href = last.image;
    a.download = `zakhrafaai_${category}_${engine}_${seed}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  wireSegmented(els.categorySeg, "category");
  wireSegmented(els.engineSeg, "engine", renderEngineHint);
  els.promptInput.addEventListener("input", updatePromptCount);
  renderPalettes();
  updatePromptCount();
  refreshAI();
})();
