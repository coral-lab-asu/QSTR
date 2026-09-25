"use strict";

// All numbers come from results.json; changing the view never mixes strategies.
const models = ["Gemini-2.5-Flash", "GPT-4.1", "Llama-3.3-70B-Instruct", "Qwen2.5-72B-Instruct"];
const descriptions = {
  exact: "Exact table match requires the entire normalized table to match. Higher is better. Scale: 0–100%.",
  pk: "Primary-key F1 measures recovery of answer-row identities, not their computed values. Higher is better. Scale: 0–100.",
  cell: "Cell accuracy measures non-key value agreement on aligned rows. Higher is better. Scale: 0–100%.",
  rmse: "Weighted RMSE measures numeric error on evaluable aligned values. Lower is better. Scale: 0–25; not a percentage."
};
let selectedMethod = "Zero Shot";
let results = [];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderChart() {
  const metric = document.getElementById("metric").value;
  const chart = document.getElementById("result-chart");
  chart.replaceChildren();
  document.getElementById("metric-description").textContent = descriptions[metric];
  for (const model of models) {
    const entry = results.find(row => row.model === model && row.method === selectedMethod);
    if (!entry) continue;
    const row = element("div", "result-row");
    const name = element("span", "result-name", model.replace("-Instruct", ""));
    name.title = model;
    const track = element("div", "result-track");
    track.setAttribute("aria-hidden", "true");
    const bar = element("div", "result-bar");
    bar.style.width = `${entry[metric] / (metric === "rmse" ? 25 : 100) * 100}%`;
    track.append(bar);
    row.append(name, track, element("span", "result-value", entry[metric].toFixed(2)));
    chart.append(row);
  }
}

document.querySelectorAll("[data-method]").forEach(button => {
  button.addEventListener("click", () => {
    selectedMethod = button.dataset.method;
    document.querySelectorAll("[data-method]").forEach(item => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    renderChart();
  });
});
document.getElementById("metric").addEventListener("change", renderChart);

async function loadResults() {
  try {
    const response = await fetch("results.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    results = (await response.json()).results;
    const body = document.getElementById("all-results");
    for (const row of results) {
      const tr = element("tr");
      for (const value of [row.model, row.method, row.exact, row.pk, row.cell, row.rmse]) {
        tr.append(element("td", "", typeof value === "number" ? value.toFixed(2) : value));
      }
      body.append(tr);
    }
    renderChart();
  } catch (error) {
    document.getElementById("result-chart").textContent = "The interactive results could not load. Read Table 3 in the linked paper or download the results JSON below. For a local preview, serve this folder over HTTP (see website/README.md).";
    document.querySelectorAll("[data-method], #metric").forEach(control => { control.disabled = true; });
    document.getElementById("all-results").textContent = "Results unavailable here; see the paper or results JSON.";
  }
}
loadResults();

document.querySelectorAll("[data-example]").forEach(button => {
  button.addEventListener("click", () => {
    const boundaries = button.dataset.example === "boundaries";
    document.getElementById("example-question").textContent = boundaries
      ? "What percentage of each batter's runs came from boundaries?"
      : "How many runs did each batter score?";
    document.getElementById("example-column").textContent = boundaries ? "Boundary share" : "Runs";
    const cells = document.querySelectorAll("#example-rows td:last-child");
    cells[0].textContent = boundaries ? "80%" : "5";
    cells[1].textContent = boundaries ? "100%" : "6";
    document.querySelectorAll("[data-example]").forEach(item => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    });
  });
});

document.getElementById("copy-citation").addEventListener("click", async () => {
  const citation = document.getElementById("citation-text");
  const status = document.getElementById("copy-status");
  try {
    await navigator.clipboard.writeText(citation.textContent);
    status.textContent = "BibTeX copied.";
  } catch (error) {
    const range = document.createRange();
    range.selectNodeContents(citation);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = "Citation selected. Press Ctrl+C or ⌘C to copy.";
  }
});
