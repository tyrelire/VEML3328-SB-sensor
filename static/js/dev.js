// Élément d'affichage du résultat du test
const resultEl = document.getElementById("testResult");

// Initialisation du graphique (Chart.js) pour afficher les mesures en temps réel
let chart = new Chart(document.getElementById("chart").getContext("2d"), {
  type: "line",
  data: {
    labels: [], // Axe X (temps ou points)
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
    plugins: { legend: { position: "bottom" } },
    scales: { x: { display: false }, y: { beginAtZero: true } },
  },
});

// Met à jour le graphique avec les nouvelles valeurs reçues
function updateChart(values) {
  if (!values) return;
  // Limite à 50 points pour garder le graphique lisible
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

// Lance un test (DC ou AC) et gère le flux SSE pour afficher les mesures
function launchTest(mode) {
  // Réinitialise le graphique et l'affichage
  chart.data.labels = [];
  chart.data.datasets.forEach((ds) => (ds.data = []));
  chart.update();
  resultEl.textContent = "Test " + mode + " en cours...";
  resultEl.className = "result";

  // Ouvre un flux SSE vers l'API Flask
  const evtSource = new EventSource("/api/measure-stream");

  // À chaque message reçu, met à jour le graphique et affiche le résultat final
  evtSource.onmessage = (event) => {
    const parsed = JSON.parse(event.data);
    if (parsed.values) updateChart(parsed.values);
    if (parsed.final_result) {
      resultEl.textContent = parsed.final_result;
      resultEl.className =
        parsed.final_result === "NO GO" ? "result nogo" : "result go";
      evtSource.close();
    }
  };

  // Gestion des erreurs du flux SSE
  evtSource.onerror = () => {
    evtSource.close();
    resultEl.textContent = "Erreur pendant le test.";
  };
}

// Ajoute les listeners sur les boutons pour lancer les tests DC ou AC
// Bouton DC
document
  .getElementById("startDCBtn")
  .addEventListener("click", () => launchTest("DC"));

// Bouton AC
document
  .getElementById("startACBtn")
  .addEventListener("click", () => launchTest("AC"));
