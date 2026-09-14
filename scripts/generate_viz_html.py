#!/usr/bin/env python3
"""Generate standalone HTML dashboard for test_generated_sql_nl.json."""

import json
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_PATH = SCRIPT_DIR.parent / "data" / "data_final" / "test_generated_sql_nl.json"
OUT_PATH = SCRIPT_DIR.parent / "data" / "data_final" / "test_data_dashboard.html"


def main():
    data = json.loads(DATA_PATH.read_text())
    data_js = json.dumps(data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QSG Test Data Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0f1117;
      --surface: #181c24;
      --surface-hover: #1e232e;
      --border: #2a3142;
      --text: #e6edf3;
      --text-muted: #8b9cb3;
      --accent: #58a6ff;
      --accent-dim: #388bfd33;
      --green: #3fb950;
      --orange: #d29922;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'DM Sans', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }}
    .header {{
      padding: 1.5rem 2rem;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, var(--surface) 0%, var(--bg) 100%);
    }}
    .header h1 {{
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 1rem;
      padding: 1.5rem 2rem;
    }}
    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      transition: border-color 0.2s, transform 0.15s;
    }}
    .stat-card:hover {{
      border-color: var(--accent);
      transform: translateY(-1px);
    }}
    .stat-value {{
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--accent);
    }}
    .stat-label {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
    }}
    .filters {{
      padding: 0 2rem 1.25rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
    }}
    .filter-group {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .filter-group label {{
      font-size: 0.8rem;
      color: var(--text-muted);
      white-space: nowrap;
    }}
    .filter-group input, .filter-group select {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      padding: 0.5rem 0.75rem;
      font-size: 0.875rem;
      min-width: 120px;
    }}
    .filter-group input::placeholder {{
      color: var(--text-muted);
      opacity: 0.7;
    }}
    .filter-group input:focus, .filter-group select:focus {{
      outline: none;
      border-color: var(--accent);
    }}
    .results-info {{
      padding: 0 2rem 0.75rem;
      font-size: 0.875rem;
      color: var(--text-muted);
    }}
    .results-info strong {{
      color: var(--accent);
    }}
    .table-wrap {{
      margin: 0 2rem 2rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      background: var(--surface);
    }}
    .table-scroll {{
      overflow-x: auto;
      overflow-y: auto;
      max-height: calc(100vh - 380px);
    }}
    table {{
      border-collapse: collapse;
      font-size: 0.875rem;
      table-layout: fixed;
      width: max-content;
    }}
    th {{
      position: sticky;
      top: 0;
      background: var(--surface-hover);
      padding: 0.75rem 1rem;
      text-align: left;
      font-weight: 600;
      border-bottom: 1px solid var(--border);
      z-index: 1;
    }}
    td {{
      padding: 0.65rem 1rem;
      border-bottom: 1px solid var(--border);
      white-space: normal;
      word-wrap: break-word;
      word-break: break-word;
    }}
    tr:hover td {{
      background: var(--surface-hover);
    }}
    .col-desc {{ width: 220px; min-width: 220px; }}
    .col-question {{ width: 300px; min-width: 300px; }}
    .col-item-id {{ width: 90px; min-width: 90px; }}
    .col-round {{ width: 70px; min-width: 70px; }}
    .col-template {{ width: 80px; min-width: 80px; }}
    .col-intent {{ width: 280px; min-width: 280px; }}
    .col-structure {{ width: 300px; min-width: 300px; }}
    .col-sql {{ width: 350px; min-width: 350px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
    .col-primary-key {{ width: 120px; min-width: 120px; }}
    .col-variables {{ width: 120px; min-width: 120px; }}
    .col-paraphrases {{ width: 300px; min-width: 300px; }}
    .col-original-sql {{ width: 320px; min-width: 320px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
    .col-params {{ width: 180px; min-width: 180px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
    .col-actions {{ width: 80px; min-width: 80px; }}
    td.col-desc, td.col-question, td.col-intent, td.col-structure, td.col-paraphrases {{
      font-size: 0.875rem;
      line-height: 1.4;
    }}
    .badge {{
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 500;
    }}
    .badge-round {{ background: var(--accent-dim); color: var(--accent); }}
    .expand-btn {{
      background: none;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 0.25rem 0.5rem;
      font-size: 0.75rem;
      border-radius: 4px;
      cursor: pointer;
    }}
    .expand-btn:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .modal {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.7);
      z-index: 100;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }}
    .modal.active {{
      display: flex;
    }}
    .modal-content {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      max-width: 700px;
      max-height: 85vh;
      overflow: auto;
      padding: 1.5rem;
    }}
    .modal-close {{
      float: right;
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.5rem;
      cursor: pointer;
      line-height: 1;
    }}
    .modal-close:hover {{ color: var(--text); }}
    .modal h3 {{
      margin-bottom: 0.75rem;
      font-size: 0.9rem;
      color: var(--text-muted);
    }}
    .modal pre {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      background: var(--bg);
      padding: 1rem;
      border-radius: 6px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .modal-section {{ margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <header class="header">
    <h1>QSG Test Data Dashboard</h1>
  </header>

  <div class="stats">
    <div class="stat-card">
      <div class="stat-value" id="stat-total">-</div>
      <div class="stat-label">Total Questions</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="stat-filtered">-</div>
      <div class="stat-label">Filtered</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="stat-items">-</div>
      <div class="stat-label">Unique Item IDs</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="stat-templates">-</div>
      <div class="stat-label">Templates</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" id="stat-rounds">-</div>
      <div class="stat-label">Rounds</div>
    </div>
  </div>

  <div class="filters">
    <div class="filter-group">
      <label>Description</label>
      <input type="text" id="filter-desc" placeholder="Search description...">
    </div>
    <div class="filter-group">
      <label>Item ID</label>
      <input type="text" id="filter-item" placeholder="e.g. 1_3_2">
    </div>
    <div class="filter-group">
      <label>Round</label>
      <select id="filter-round">
        <option value="">All</option>
        <option value="0">0</option><option value="1">1</option><option value="2">2</option>
        <option value="3">3</option><option value="4">4</option><option value="5">5</option>
        <option value="6">6</option><option value="7">7</option><option value="8">8</option>
        <option value="9">9</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Template ID</label>
      <select id="filter-template">
        <option value="">All</option>
      </select>
    </div>
  </div>

  <div class="results-info">
    Showing <strong id="show-count">0</strong> of <strong id="total-count">0</strong> rows
  </div>

  <div class="table-wrap">
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th class="col-desc">Description</th>
            <th class="col-item-id">Item ID</th>
            <th class="col-round">Round</th>
            <th class="col-template">Template</th>
            <th class="col-question">Question</th>
            <th class="col-intent">Intent</th>
            <th class="col-structure">Structure</th>
            <th class="col-sql">SQL</th>
            <th class="col-primary-key">Primary Key</th>
            <th class="col-variables">Variables</th>
            <th class="col-paraphrases">Paraphrases</th>
            <th class="col-original-sql">Original SQL</th>
            <th class="col-params">Params</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <div id="modal" class="modal">
    <div class="modal-content">
      <button class="modal-close" onclick="closeModal()">&times;</button>
      <div id="modal-body"></div>
    </div>
  </div>

  <script>
    const DATA = {data_js};

    const statTotal = document.getElementById('stat-total');
    const statFiltered = document.getElementById('stat-filtered');
    const statItems = document.getElementById('stat-items');
    const statTemplates = document.getElementById('stat-templates');
    const statRounds = document.getElementById('stat-rounds');
    const tbody = document.getElementById('tbody');
    const filterDesc = document.getElementById('filter-desc');
    const filterItem = document.getElementById('filter-item');
    const filterRound = document.getElementById('filter-round');
    const filterTemplate = document.getElementById('filter-template');
    const showCount = document.getElementById('show-count');
    const totalCount = document.getElementById('total-count');

    const templates = [...new Set(DATA.map(d => d.template_id))].sort((a,b) => a-b);
    const templateSelect = filterTemplate;
    templates.forEach(t => {{
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      templateSelect.appendChild(opt);
    }});

    function updateStats(filtered) {{
      statTotal.textContent = DATA.length.toLocaleString();
      statFiltered.textContent = filtered.length.toLocaleString();
      const items = new Set(filtered.map(d => d.item_id)).size;
      statItems.textContent = items.toLocaleString();
      statTemplates.textContent = new Set(filtered.map(d => d.template_id)).size;
      statRounds.textContent = new Set(filtered.map(d => d.round_idx)).size;
      totalCount.textContent = DATA.length.toLocaleString();
      showCount.textContent = filtered.length.toLocaleString();
    }}

    function filterData() {{
      const desc = filterDesc.value.toLowerCase().trim();
      const item = filterItem.value.trim();
      const round = filterRound.value;
      const template = filterTemplate.value;

      return DATA.filter(d => {{
        if (desc && !(d.description || '').toLowerCase().includes(desc)) return false;
        if (item && !(d.item_id || '').includes(item)) return false;
        if (round !== '' && String(d.round_idx) !== round) return false;
        if (template !== '' && String(d.template_id) !== template) return false;
        return true;
      }});
    }}

    function escapeHtml(s) {{
      if (s == null) return '';
      const div = document.createElement('div');
      div.textContent = s;
      return div.innerHTML;
    }}
    function formatVal(val) {{
      if (val == null) return '';
      if (Array.isArray(val)) return val.join(', ');
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val);
    }}

    function showDetails(d) {{
      const body = document.getElementById('modal-body');
      let html = `
        <div class="modal-section"><h3>Description</h3><p>${{escapeHtml(d.description)}}</p></div>
        <div class="modal-section"><h3>Question</h3><p>${{escapeHtml(d.question)}}</p></div>
        <div class="modal-section"><h3>Intent</h3><p>${{escapeHtml(d.intent)}}</p></div>
        <div class="modal-section"><h3>Structure</h3><p>${{escapeHtml(d.structure)}}</p></div>
        <div class="modal-section"><h3>SQL</h3><pre>${{escapeHtml(d.sql)}}</pre></div>
        <div class="modal-section"><h3>Primary Key</h3><p>${{escapeHtml(formatVal(d.primary_key))}}</p></div>
        <div class="modal-section"><h3>Variables</h3><p>${{escapeHtml(formatVal(d.variables))}}</p></div>
        <div class="modal-section"><h3>Paraphrases</h3><pre>${{escapeHtml(formatVal(d.paraphrases))}}</pre></div>
      `;
      if (d.original_sql) html += `<div class="modal-section"><h3>Original SQL</h3><pre>${{escapeHtml(d.original_sql)}}</pre></div>`;
      if (d.params) html += `<div class="modal-section"><h3>Params</h3><pre>${{escapeHtml(formatVal(d.params))}}</pre></div>`;
      body.innerHTML = html;
      document.getElementById('modal').classList.add('active');
    }}

    function closeModal() {{
      document.getElementById('modal').classList.remove('active');
    }}

    let filteredData = [];
    function render(filtered) {{
      filteredData = filtered;
      tbody.innerHTML = filtered.map((d, i) => `
        <tr>
          <td class="col-desc">${{escapeHtml(d.description || '')}}</td>
          <td class="col-item-id">${{escapeHtml(d.item_id)}}</td>
          <td class="col-round"><span class="badge badge-round">${{d.round_idx}}</span></td>
          <td class="col-template">${{d.template_id}}</td>
          <td class="col-question">${{escapeHtml(d.question || '')}}</td>
          <td class="col-intent">${{escapeHtml(d.intent || '')}}</td>
          <td class="col-structure">${{escapeHtml(d.structure || '')}}</td>
          <td class="col-sql">${{escapeHtml(d.sql || '')}}</td>
          <td class="col-primary-key">${{escapeHtml(formatVal(d.primary_key))}}</td>
          <td class="col-variables">${{escapeHtml(formatVal(d.variables))}}</td>
          <td class="col-paraphrases">${{escapeHtml(formatVal(d.paraphrases))}}</td>
          <td class="col-original-sql">${{escapeHtml(d.original_sql || '')}}</td>
          <td class="col-params">${{escapeHtml(formatVal(d.params))}}</td>
          <td class="col-actions"><button class="expand-btn" data-idx="${{i}}">Details</button></td>
        </tr>
      `).join('');
      tbody.querySelectorAll('.expand-btn').forEach(btn => {{
        btn.onclick = () => showDetails(filteredData[+btn.dataset.idx]);
      }});
    }}

    function run() {{
      const filtered = filterData();
      updateStats(filtered);
      render(filtered);
    }}

    filterDesc.addEventListener('input', run);
    filterItem.addEventListener('input', run);
    filterRound.addEventListener('change', run);
    filterTemplate.addEventListener('change', run);

    document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});
    document.getElementById('modal').addEventListener('click', e => {{
      if (e.target.id === 'modal') closeModal();
    }});

    run();
  </script>
</body>
</html>
"""
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Generated: {OUT_PATH}")


if __name__ == "__main__":
    main()
