"""
Generate gold vs predicted comparison HTML.
Reads gold_questions_answers.json and experiment/<session_id>/<qid>.txt (OUTPUT section),
builds a superpositioned table (gold/pred per cell) and highlights:
  - rows only in gold (missing from prediction)
  - rows only in prediction (extra predicted).

Usage: python synData/generate_gold_pred_viz.py
Output: synData/experiment/gold_vs_predicted.html
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GOLD_QA_JSON = os.path.join(_SCRIPT_DIR, "gold_questions_answers.json")
EXPERIMENT_DIR = os.path.join(_SCRIPT_DIR, "experiment")
OUT_HTML = os.path.join(EXPERIMENT_DIR, "gold_vs_predicted.html")

JSON_ARRAY_RE = re.compile(r"(\[.*\])", re.DOTALL)

# qid -> key column for row identity (None = scalar Q7/Q8)
QID_KEY_COLUMN = {
    "Q1": "product_id", "Q2": "product_id", "Q3": "customer_id", "Q4": "customer_id",
    "Q5": "product_id", "Q6": "product_id", "Q7": None, "Q8": None,
    "Q9": "category", "Q10": "customer_id",
}


def _load_gold() -> List[Dict[str, Any]]:
    with open(GOLD_QA_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_output_from_log(path: str) -> Optional[Any]:
    """Parse OUTPUT section from experiment log; return list of dicts or scalar or None."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if "---OUTPUT---" not in text:
            return None
        out_text = text.split("---OUTPUT---", 1)[1].strip()
        # Try as JSON array
        try:
            parsed = json.loads(out_text)
            if isinstance(parsed, list):
                return parsed
            return [parsed] if isinstance(parsed, dict) else parsed
        except json.JSONDecodeError:
            pass
        m = JSON_ARRAY_RE.search(out_text)
        if m:
            sub = re.sub(r",\s*]", "]", m.group(1))
            sub = re.sub(r",\s*}", "}", sub)
            try:
                parsed = json.loads(sub)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        # Scalar: try single number
        try:
            return float(out_text.strip())
        except ValueError:
            pass
        return None
    except Exception:
        return None


def _get_key(row: Dict[str, Any], key_col: Optional[str]) -> Optional[str]:
    if key_col is None:
        return None
    return row.get(key_col) if isinstance(row.get(key_col), str) else str(row.get(key_col, ""))


def _row_to_cells(row: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
    return {c: row.get(c) for c in columns}


def _build_comparison(
    gold: Any, pred: Any, qid: str, columns: List[str]
) -> Dict[str, Any]:
    """Build merged rows with row_type and gold/pred cell values. For Q7/Q8 gold and pred are scalars."""
    key_col = QID_KEY_COLUMN.get(qid)
    if key_col is None:  # Q7, Q8 scalar
        g_val = gold if isinstance(gold, (int, float)) else None
        p_val = None
        if isinstance(pred, list) and len(pred) > 0:
            first = pred[0]
            if isinstance(first, dict) and first:
                p_val = first.get(list(first.keys())[0])
            else:
                p_val = first
        elif isinstance(pred, (int, float)):
            p_val = pred
        col_name = columns[0] if columns else "value"
        return {
            "scalar": True,
            "columns": [col_name],
            "rows": [{"row_type": "both", "cells": {col_name: (g_val, p_val)}}],
        }
    # Table: gold and pred are lists of dicts
    gold_list = gold if isinstance(gold, list) else []
    pred_list = pred if isinstance(pred, list) else []
    if isinstance(pred_list, list) and len(pred_list) == 1 and isinstance(pred_list[0], dict) and not any(
        _get_key(pred_list[0], key_col) for _ in [None]
    ):
        pass
    gold_by_key = {_get_key(r, key_col): r for r in gold_list if _get_key(r, key_col) is not None}
    pred_by_key = {_get_key(r, key_col): r for r in pred_list if _get_key(r, key_col) is not None}
    all_keys = sorted(set(gold_by_key) | set(pred_by_key))
    rows = []
    for k in all_keys:
        g_row = gold_by_key.get(k)
        p_row = pred_by_key.get(k)
        if g_row is not None and p_row is not None:
            row_type = "both"
        elif g_row is not None:
            row_type = "gold_only"
        else:
            row_type = "pred_only"
        cells = {}
        for col in columns:
            g_val = g_row.get(col) if g_row else None
            p_val = p_row.get(col) if p_row else None
            cells[col] = (g_val, p_val)
        rows.append({"row_type": row_type, "key": k, "cells": cells})
    return {"scalar": False, "columns": columns, "rows": rows}


def _get_columns_for_qid(qid: str) -> List[str]:
    """Column names for this qid (from question schema)."""
    schema_path = os.path.join(_SCRIPT_DIR, "question_schemas.json")
    if not os.path.isfile(schema_path):
        return []
    with open(schema_path, "r", encoding="utf-8") as f:
        schemas = json.load(f)
    for s in schemas:
        if s.get("qid") == qid:
            return [c["name"] for c in s.get("columns", [])]
    return []


def main() -> None:
    gold_sessions = _load_gold()
    payload: Dict[str, Dict[str, Any]] = {}
    for sess in gold_sessions:
        sid = sess["session_id"]
        gold_answers = sess.get("gold_answers", {})
        payload[sid] = {}
        for qid in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"]:
            gold = gold_answers.get(qid)
            log_path = os.path.join(EXPERIMENT_DIR, sid, f"{qid}.txt")
            pred = _parse_output_from_log(log_path)
            columns = _get_columns_for_qid(qid)
            comp = _build_comparison(gold, pred, qid, columns)
            qa = next((q for q in sess.get("questions_and_answers", []) if q.get("qid") == qid), None)
            comp["question"] = qa.get("question", "") if qa else ""
            payload[sid][qid] = comp

    # Embed in HTML
    html = _make_html(payload, list(payload.keys()))
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT_HTML}")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def _make_html(payload: Dict[str, Dict[str, Any]], session_ids: List[str]) -> str:
    data_js = json.dumps(payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gold vs Predicted</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1rem 2rem; background: #1a1a1a; color: #e0e0e0; }}
    h1 {{ margin-bottom: 0.5rem; }}
    .controls {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    label {{ display: flex; align-items: center; gap: 0.5rem; }}
    select {{ padding: 0.4rem 0.8rem; font-size: 1rem; background: #2a2a2a; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; }}
    table {{ border-collapse: collapse; font-size: 0.9rem; margin-top: 0.5rem; }}
    th, td {{ border: 1px solid #444; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #2a2a2a; }}
    tr.gold_only {{ background: rgba(200, 80, 60, 0.25); }}
    tr.pred_only {{ background: rgba(60, 80, 200, 0.2); }}
    tr.both {{ }}
    .cell-match {{ color: #8f8; }}
    .cell-mismatch {{ color: #f88; }}
    .legend {{ margin-top: 1rem; display: flex; gap: 2rem; flex-wrap: wrap; }}
    .legend span {{ display: inline-block; padding: 0.2rem 0.5rem; border-radius: 3px; }}
    .legend .gold_only {{ background: rgba(200, 80, 60, 0.35); }}
    .legend .pred_only {{ background: rgba(60, 80, 200, 0.3); }}
    #question {{ color: #aaa; margin-bottom: 0.5rem; }}
  </style>
</head>
<body>
  <h1>Gold vs Predicted</h1>
  <p id="question"></p>
  <div class="controls">
    <label>Session <select id="session"></select></label>
    <label>Question <select id="qid"></select></label>
  </div>
  <div class="legend">
    <span class="gold_only">In GT only (missing from prediction)</span>
    <span class="pred_only">Extra in prediction (not in GT)</span>
  </div>
  <div id="table-wrap"></div>

  <script>
    const payload = {data_js};
    const sessionSelect = document.getElementById('session');
    const qidSelect = document.getElementById('qid');
    const questionEl = document.getElementById('question');
    const tableWrap = document.getElementById('table-wrap');

    const sessionIds = {json.dumps(session_ids)};
    sessionIds.forEach(s => {{
      const o = document.createElement('option');
      o.value = s; o.textContent = s;
      sessionSelect.appendChild(o);
    }});
    ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8','Q9','Q10'].forEach(q => {{
      const o = document.createElement('option');
      o.value = q; o.textContent = q;
      qidSelect.appendChild(o);
    }});

    function render() {{
      const sid = sessionSelect.value;
      const qid = qidSelect.value;
      const data = payload[sid] && payload[sid][qid];
      if (!data) {{ tableWrap.innerHTML = ''; questionEl.textContent = ''; return; }}
      questionEl.textContent = data.question || '';
      const cols = data.columns || [];
      const rows = data.rows || [];
      let html = '<table><thead><tr>';
      cols.forEach(c => html += '<th>' + escapeHtml(c) + '</th>');
      html += '<th>Status</th></tr></thead><tbody>';
      rows.forEach(r => {{
        const cls = r.row_type || 'both';
        html += '<tr class="' + cls + '">';
        cols.forEach(col => {{
          const pair = r.cells && r.cells[col];
          let cellText = '— / —';
          if (pair !== undefined && (pair[0] !== undefined || pair[1] !== undefined)) {{
            const g = pair[0] == null ? '—' : pair[0];
            const p = pair[1] == null ? '—' : pair[1];
            cellText = formatVal(g) + ' / ' + formatVal(p);
          }}
          const match = pair && pair[0] != null && pair[1] != null && String(pair[0]) === String(pair[1]);
          html += '<td class="' + (match ? 'cell-match' : 'cell-mismatch') + '">' + escapeHtml(cellText) + '</td>';
        }});
        let status = '';
        if (cls === 'gold_only') status = 'Missing from pred';
        else if (cls === 'pred_only') status = 'Extra in pred';
        html += '<td>' + status + '</td></tr>';
      }});
      html += '</tbody></table>';
      tableWrap.innerHTML = html;
    }}
    function formatVal(v) {{
      if (v == null) return '—';
      if (typeof v === 'number' && Number.isInteger(v)) return String(v);
      return String(v);
    }}
    function escapeHtml(s) {{
      const d = document.createElement('div');
      d.textContent = s;
      return d.innerHTML;
    }}
    sessionSelect.addEventListener('change', render);
    qidSelect.addEventListener('change', render);
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
