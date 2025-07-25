let currentLimits = {};
const resultEl = document.getElementById("testResult");

let chart = new Chart(document.getElementById("chart").getContext("2d"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "Red", data: [], borderColor: "red", fill: false },
      { label: "Green", data: [], borderColor: "green", fill: false },
      { label: "Blue", data: [], borderColor: "blue", fill: false },
      {
        label: "Lumière Totale",
        data: [],
        borderColor: "gray",
        fill: false,
      },
      { label: "IR", data: [], borderColor: "purple", fill: false },
    ],
  },
  options: {
    animation: false,
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: "bottom" } },
    scales: {
      x: { display: false },
      y: { beginAtZero: true },
    },
  },
});

function updateChart(values) {
  if (!values) return;
  if (chart.data.labels.length > 50) {
    chart.data.labels.shift();
    chart.data.datasets.forEach((ds) => ds.data.shift());
  }
  chart.data.labels.push("");
  chart.data.datasets[0].data.push(values.red || 0);
  chart.data.datasets[1].data.push(values.green || 0);
  chart.data.datasets[2].data.push(values.blue || 0);
  chart.data.datasets[3].data.push(values.total_light || 0);
  chart.data.datasets[4].data.push(values.ir || 0);
  chart.update("none");
}

async function startMeasurement() {
  chart.data.labels = [];
  chart.data.datasets.forEach((ds) => (ds.data = []));
  chart.update();
  resultEl.className = "result";
  resultEl.textContent = "Test en cours...";
  document.getElementById("startTestBtn").disabled = true;

  const evtSource = new EventSource(
    "/api/measure-stream?limits=" +
      encodeURIComponent(JSON.stringify(currentLimits))
  );

  evtSource.onmessage = (event) => {
    const parsed = JSON.parse(event.data);
    if (parsed.values) {
      updateChart(parsed.values);
    }
    if (parsed.final_result) {
      let resultText = parsed.final_result;
      if (parsed.final_result === "NO GO" && parsed.failed_checks) {
        resultText += "\n\nÉcarts détectés :\n";
        parsed.failed_checks.forEach((fail) => {
          resultText += `• ${fail.channel} : ${fail.value_raw} (~${fail.value_8bit}/255)\n`;
          resultText += `  Limites : ${fail.min_raw}–${fail.max_raw} (≈ ${fail.min_8bit}–${fail.max_8bit})\n\n`;
        });
      }
      resultEl.textContent = resultText;
      resultEl.className =
        parsed.final_result === "NO GO" ? "result nogo" : "result go";
      evtSource.close();
      document.getElementById("startTestBtn").disabled = false;
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    document.getElementById("startTestBtn").disabled = false;
  };
}

document
  .getElementById("startTestBtn")
  .addEventListener("click", startMeasurement);

document
  .getElementById("barcodeInput")
  .addEventListener("keypress", async function (e) {
    if (e.key !== "Enter") return;
    const barcode = this.value.trim();
    if (!barcode) return;
    this.value = "";

    document.getElementById("productInfo").textContent =
      "Recherche du produit...";
    resultEl.textContent = "";
    document.getElementById("startTestBtn").style.display = "none";

    try {
      const prodRes = await fetch(
        `/api/product?barcode=${encodeURIComponent(barcode)}`
      );
      const prodData = await prodRes.json();
      if (!prodData.donnees || !prodData.donnees.length)
        throw new Error("Produit non trouvé.");
      const produit = prodData.donnees[0];
      const code_article = produit.code_article.trim();

      let html = `<h3>Détails produit :</h3><ul>`;
      for (const [k, v] of Object.entries(produit)) {
        if (v && String(v).trim()) html += `<li><b>${k}:</b> ${v}</li>`;
      }
      html += `</ul>`;
      document.getElementById("productInfo").innerHTML = html;

      resultEl.textContent = "Récupération des limites...";
      const confRes = await fetch(
        `/api/config?code_article=${encodeURIComponent(code_article)}`
      );
      const limits = await confRes.json();

      currentLimits = limits || {};
      if (!limits || Object.keys(limits).length === 0) {
        resultEl.textContent =
          "⚠️ Aucune limite trouvée. Vous pouvez quand même lancer le test.";
      } else {
        resultEl.textContent = "✅ Limites chargées. Prêt pour test.";
      }
      document.getElementById("startTestBtn").style.display = "inline-block";
    } catch (err) {
      console.error(err);
      document.getElementById("productInfo").textContent =
        "Erreur : " + err.message;
      resultEl.textContent = "";
    }
  });

fetch("/api/logname")
  .then((res) => res.json())
  .then((data) => {
    const logDiv = document.getElementById("logPath");
    const logUrl = `/logs/${data.log_filename}`;
    logDiv.innerHTML = `
      🗒️ Log serveur : <code>${logUrl}</code>
      <a href="${logUrl}" download>
        <button class="download-btn">Télécharger</button>
      </a>
    `;
  })
  .catch(() => {
    document.getElementById("logPath").textContent =
      "⚠️ Erreur lors du chargement du log.";
  });

fetch("/api/last-test-log")
  .then((res) => res.json())
  .then((data) => {
    if (data.test_log_filename) {
      const name = data.test_log_filename;
      document.getElementById("lastTestLog").innerHTML = `
        🗂️ Dernier log de test : <code>${data.test_log_filename}</code>
        <a href="/download-log/${data.test_log_filename}">
          <button class="download-btn">Télécharger</button>
        </a>
      `;
    } else {
      document.getElementById("lastTestLog").textContent =
        "ℹ️ Aucun log de test encore enregistré.";
    }
  })
  .catch(() => {
    document.getElementById("lastTestLog").textContent =
      "⚠️ Erreur lors du chargement du dernier log de test.";
  });
