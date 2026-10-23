(() => {
  const CAT_LABELS = { zellige: "Zellige", tapis: "Tapis", broderie: "Broderie" };
  // ids d'API conservés (gan / diffusion), libellés honnêtes côté interface
  const ENGINE_LABELS = { gan: "Rapide", diffusion: "Rendu IA" };

  // dates ISO 8601 UTC (« …Z ») affichées à l'heure locale du navigateur
  const dateFmt = new Intl.DateTimeFormat(document.documentElement.lang || undefined, {
    dateStyle: "short",
    timeStyle: "short",
  });

  function formatDate(iso) {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
  }

  function renderBars(container, entries) {
    const max = Math.max(1, ...entries.map(([, count]) => count));
    container.replaceChildren();
    entries.forEach(([label, count]) => {
      const pct = Math.round((count / max) * 100);
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <div class="label"></div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div style="width:24px; text-align:right; font-family:var(--font-mono); font-size:0.8rem;">${count}</div>`;
      row.querySelector(".label").textContent = label;
      container.appendChild(row);
    });
  }

  // libellé d'une ligne d'historique : le rendu IA peut être un repli procédural
  function engineLabel(h) {
    const label = ENGINE_LABELS[h.engine] || h.engine;
    if (h.engine === "diffusion" && h.source && h.source !== "gemini") return `${label} (repli procédural)`;
    return label;
  }

  async function load() {
    try {
      const data = await ZakhrafaAPI.dashboard();
      const cats = data.repartition_par_categorie;

      document.getElementById("statTotal").textContent = data.total_motifs;
      document.getElementById("statZellige").textContent = cats.zellige || 0;
      document.getElementById("statTapis").textContent = cats.tapis || 0;
      document.getElementById("statBroderie").textContent = cats.broderie || 0;

      renderBars(document.getElementById("barChart"),
        Object.entries(cats).map(([cat, count]) => [CAT_LABELS[cat] || cat, count]));

      const engines = data.repartition_par_moteur || {};
      renderBars(document.getElementById("engineChart"),
        Object.entries(engines).map(([eng, count]) => [ENGINE_LABELS[eng] || eng, count]));
      const sources = data.repartition_par_source || {};
      const aiTotal = engines.diffusion || 0;
      document.getElementById("sourceNote").textContent = aiTotal
        ? `Rendus IA : ${sources.gemini || 0} réussi(s) via Gemini, ${aiTotal - (sources.gemini || 0)} repli(s) sur le procédural.`
        : "";

      const historyList = document.getElementById("historyList");
      if (!data.derniers_motifs.length) {
        historyList.innerHTML = `<div class="empty-state">Aucun motif généré pour l'instant. <a href="/studio">Ouvrir l'atelier →</a></div>`;
      } else {
        historyList.replaceChildren();
        data.derniers_motifs.forEach((h) => {
          const row = document.createElement("div");
          row.className = "history-row";
          const cat = document.createElement("span");
          cat.className = "cat";
          cat.textContent = `${CAT_LABELS[h.category] || h.category} · ${engineLabel(h)}`;
          const when = document.createElement("time");
          when.className = "when";
          when.dateTime = h.date;
          when.title = `${h.date} (UTC)`;
          when.textContent = formatDate(h.date);
          row.append(cat, when);
          historyList.appendChild(row);
        });
      }
    } catch (err) {
      const box = document.createElement("div");
      box.className = "empty-state";
      box.style.color = "var(--danger)";
      box.textContent = `Erreur : ${err.message}`;
      document.getElementById("historyList").replaceChildren(box);
    }
  }

  load();
})();
