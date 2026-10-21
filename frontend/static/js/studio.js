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
  };

  let lastImageUrl = null;
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

  function wireSegmented(container, key) {
    container.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        container.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state[key] = btn.dataset.value;
      });
    });
  }

  function setLoading() {
    els.canvasWrap.innerHTML = `
      <div class="loading-shimmer">
        <div class="spinner"></div>
        <span>Génération en cours…</span>
      </div>`;
    els.generateBtn.disabled = true;
    els.generateBtn.textContent = "Génération…";
  }

  function renderResult(result) {
    lastImageUrl = result.image;
    els.canvasWrap.innerHTML = `<img src="${result.image}" alt="Motif ${state.category} généré" />`;
    els.metaRow.style.display = "flex";
    els.metaEngine.textContent = result.engine === "gan" ? "GAN" : "Diffusion";
    els.metaSize.textContent = `${result.width}×${result.height}`;
    els.metaTime.textContent = `${result.elapsed_ms} ms`;
    els.metaSeed.textContent = result.seed;
    const label = result.source === "trained_weights" ? "Poids entraînés" : "Générateur procédural";
    els.metaSourceWrap.innerHTML = `<span class="badge-source ${result.source}"><span class="dot"></span>${label}</span>`;
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
    els.canvasWrap.innerHTML = `
      <div class="canvas-placeholder" style="color:var(--danger);">
        Échec de la génération : ${message}
      </div>`;
  }

  async function doGenerate() {
    setLoading();
    const seedVal = els.seedInput.value ? parseInt(els.seedInput.value, 10) : null;
    const sizeVal = els.sizeInput.value ? parseInt(els.sizeInput.value, 10) : null;
    try {
      const result = await ZakhrafaAPI.generate({
        category: state.category,
        engine: state.engine,
        palette: state.palette,
        seed: seedVal,
        size: sizeVal,
      });
      renderResult(result);
    } catch (err) {
      renderError(err.message || "erreur inconnue");
    } finally {
      els.generateBtn.disabled = false;
      els.generateBtn.textContent = "Générer le motif";
    }
  }

  els.generateBtn.addEventListener("click", doGenerate);
  els.regenBtn.addEventListener("click", doGenerate);
  els.downloadBtn.addEventListener("click", () => {
    if (!lastImageUrl) return;
    const a = document.createElement("a");
    a.href = lastImageUrl;
    a.download = `zakhrafaai_${state.category}_${state.engine}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  wireSegmented(els.categorySeg, "category");
  wireSegmented(els.engineSeg, "engine");
  renderPalettes();
})();
