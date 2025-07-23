let currentLimits = {};
let allProducts = [];
const resultEl = document.getElementById("testResult");
const startBtn = document.getElementById("startTestBtn");
const modelInput = document.getElementById("modelSelect");

let chart = new Chart(document.getElementById("chart").getContext("2d"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "Red", data: [], borderColor: "red", fill: false },
      { label: "Green", data: [], borderColor: "green", fill: false },
      { label: "Blue", data: [], borderColor: "blue", fill: false },
      { label: "Lumière Totale", data: [], borderColor: "gray", fill: false },
      { label: "IR", data: [], borderColor: "purple", fill: false },
    ],
  },
  options: {
    animation: false,
    responsive: true,
    plugins: { legend: { position: "bottom" } },
    scales: { x: { display: false }, y: { beginAtZero: true } },
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
  startBtn.disabled = true;

  const evtSource = new EventSource(
    "/api/measure-stream?limits=" +
      encodeURIComponent(JSON.stringify(currentLimits))
  );

  evtSource.onmessage = (event) => {
    const parsed = JSON.parse(event.data);
    if (parsed.values) updateChart(parsed.values);

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
      startBtn.disabled = false;
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    resultEl.textContent = "❌ Erreur de communication.";
    startBtn.disabled = false;
  };
}

modelInput.addEventListener("input", async () => {
  const selectedRef = modelInput.value.trim();

  if (selectedRef === "") {
    currentLimits = {};
    resultEl.textContent = "";
    startBtn.style.display = "none";
    return;
  }

  const match = allProducts.find((p) => p.reference === selectedRef);

  if (!match) {
    currentLimits = {};
    resultEl.textContent = "";
    startBtn.style.display = "none";
    return;
  }

  resultEl.textContent = "⏳ Chargement des limites...";

  try {
    const confRes = await fetch(
      `/api/config?code_article=${encodeURIComponent(match.reference)}`
    );
    const limits = await confRes.json();

    currentLimits = limits || {};
    if (!limits || Object.keys(limits).length === 0) {
      resultEl.textContent =
        "⚠️ Aucune limite trouvée. Vous pouvez quand même lancer le test.";
    } else {
      resultEl.textContent = "✅ Limites chargées. Prêt pour test.";
    }

    startBtn.style.display = "inline-block";
  } catch (err) {
    console.error(err);
    resultEl.textContent = "❌ Erreur lors du chargement des limites.";
    startBtn.style.display = "none";
  }
});

startBtn.addEventListener("click", startMeasurement);

fetch("/api/products")
  .then((res) => res.json())
  .then((data) => {
    allProducts = data;
    const datalist = document.getElementById("modelOptions");
    data.forEach((prod) => {
      if (prod.reference) {
        const opt = document.createElement("option");
        opt.value = prod.reference;
        datalist.appendChild(opt);
      }
    });
  })
  .catch((err) => console.error("Erreur chargement modèles :", err));

fetch("/api/logname")
  .then((res) => res.json())
  .then((data) => {
    document.getElementById(
      "logPath"
    ).textContent = `🗒️ Log serveur : /logs/${data.log_filename}`;
  });

fetch("/api/last-test-log")
  .then((res) => res.json())
  .then((data) => {
    if (data.test_log_filename) {
      document.getElementById(
        "lastTestLog"
      ).textContent = `🗂️ Dernier log de test : /logs/${data.test_log_filename}`;
    } else {
      document.getElementById("lastTestLog").textContent =
        "ℹ️ Aucun log de test encore enregistré.";
    }
  });
