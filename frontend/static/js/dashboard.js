(() => {
  const CAT_LABELS = { zellige: "Zellige", tapis: "Tapis", broderie: "Broderie" };
  // ids d'API conservés (gan / diffusion), libellés honnêtes côté interface
  const ENGINE_LABELS = { gan: "Rapide", diffusion: "Rendu IA" };

  async function load() {
    try {
      const data = await ZakhrafaAPI.dashboard();

      document.getElementById("statTotal").textContent = data.total_motifs;
      document.getElementById("statZellige").textContent = data.repartition_par_categorie.zellige || 0;
      document.getElementById("statTapis").textContent = data.repartition_par_categorie.tapis || 0;
      document.getElementById("statBroderie").textContent = data.repartition_par_categorie.broderie || 0;

      const max = Math.max(1, ...Object.values(data.repartition_par_categorie));
      const barChart = document.getElementById("barChart");
      barChart.innerHTML = "";
      Object.entries(data.repartition_par_categorie).forEach(([cat, count]) => {
        const pct = Math.round((count / max) * 100);
        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `
          <div class="label">${CAT_LABELS[cat] || cat}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
          <div style="width:24px; text-align:right; font-family:var(--font-mono); font-size:0.8rem;">${count}</div>`;
        barChart.appendChild(row);
      });

      const historyList = document.getElementById("historyList");
      if (!data.derniers_motifs.length) {
        historyList.innerHTML = `<div class="empty-state">Aucun motif généré pour l'instant. <a href="/studio.html">Ouvrir l'atelier →</a></div>`;
      } else {
        historyList.innerHTML = "";
        data.derniers_motifs.forEach((h) => {
          const row = document.createElement("div");
          row.className = "history-row";
          row.innerHTML = `<span class="cat">${CAT_LABELS[h.category] || h.category} · ${ENGINE_LABELS[h.engine] || h.engine}</span><span class="when">${h.date}</span>`;
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
