"""
Generate a JSON file with all questions and their gold answers per session/transcript.

Usage (from repo root or from synData):
  python synData/generate_gold_qa.py
  # or
  cd synData && python generate_gold_qa.py

Output: synData/gold_questions_answers.json
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_JSONL = os.path.join(_SCRIPT_DIR, "shopkeeper_sessions", "sessions.jsonl")
PRODUCTS_JSON = os.path.join(_SCRIPT_DIR, "products.json")
OUT_JSON = os.path.join(_SCRIPT_DIR, "gold_questions_answers.json")

# Question text and qid order (must match prompt_and_eval comparison logic)
QUESTION_LIST = [
    ("Q1", "What is the total quantity sold per product?"),
    ("Q2", "What is the total revenue per product?"),
    ("Q3", "What is the total quantity bought by each customer?"),
    ("Q4", "How much did each customer spend?"),
    ("Q5", "Which 5 products had the highest revenue?"),
    ("Q6", "Which 5 products had the highest quantity sold?"),
    ("Q7", "What is the total revenue across all products?"),
    ("Q8", "What is the total number of units (or kg) sold across all products?"),
    ("Q9", "What is the total revenue per category?"),
    ("Q10", "What is the average order value per customer?"),
]


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Only include rows with non-zero activity (entities that exist in the transcript)
_EPS = 1e-9


def compute_gold_answers(session: Dict[str, Any], catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    From session's product_aggregation, customer_aggregation, and events,
    compute gold answers for Q1..Q10. Only includes rows for entities that
    have non-zero activity in the transcript (no zero qty/revenue rows).
    """
    prod_agg = session.get("product_aggregation") or []
    cust_agg = session.get("customer_aggregation") or []
    events = session.get("events") or []

    pid_to_category = {p["product_id"]: p["category"] for p in catalog}

    gold: Dict[str, Any] = {}

    # Q1: total quantity sold per product — only products with qty_sold > 0
    q1 = [
        {
            "product_id": r["product_id"],
            "name": r["name"],
            "total_qty_sold": round(float(r.get("qty_sold", 0)), 2),
        }
        for r in prod_agg
        if float(r.get("qty_sold", 0)) > _EPS
    ]
    gold["Q1"] = q1

    # Q2: total revenue per product — only products with revenue > 0
    q2 = [
        {
            "product_id": r["product_id"],
            "name": r["name"],
            "total_revenue": round(float(r.get("revenue", 0)), 2),
        }
        for r in prod_agg
        if float(r.get("revenue", 0)) > _EPS
    ]
    gold["Q2"] = q2

    # Q3: total quantity per customer — only customers with total_qty > 0
    q3 = [
        {"customer_id": r["customer_id"], "total_qty": round(float(r.get("qty", 0)), 2)}
        for r in cust_agg
        if float(r.get("qty", 0)) > _EPS
    ]
    gold["Q3"] = q3

    # Q4: total spent per customer — only customers with total_spent > 0
    q4 = [
        {"customer_id": r["customer_id"], "total_spent": round(float(r.get("revenue", 0)), 2)}
        for r in cust_agg
        if float(r.get("revenue", 0)) > _EPS
    ]
    gold["Q4"] = q4

    # Q5: top 5 products by revenue — only from products with revenue > 0 (up to 5)
    by_revenue = sorted(
        [r for r in prod_agg if float(r.get("revenue", 0) or 0) > _EPS],
        key=lambda x: float(x.get("revenue", 0)),
        reverse=True,
    )[:5]
    q5 = [
        {
            "rank": i + 1,
            "product_id": r["product_id"],
            "name": r["name"],
            "revenue": round(float(r.get("revenue", 0)), 2),
        }
        for i, r in enumerate(by_revenue)
    ]
    gold["Q5"] = q5

    # Q6: top 5 products by quantity sold — only from products with qty_sold > 0 (up to 5)
    by_qty = sorted(
        [r for r in prod_agg if float(r.get("qty_sold", 0) or 0) > _EPS],
        key=lambda x: float(x.get("qty_sold", 0)),
        reverse=True,
    )[:5]
    q6 = [
        {
            "rank": i + 1,
            "product_id": r["product_id"],
            "name": r["name"],
            "qty_sold": round(float(r.get("qty_sold", 0)), 2),
        }
        for i, r in enumerate(by_qty)
    ]
    gold["Q6"] = q6

    # Q7: scalar total revenue (unchanged)
    total_rev = sum(float(r.get("revenue", 0)) for r in prod_agg)
    gold["Q7"] = round(total_rev, 2)

    # Q8: scalar total qty (unchanged)
    total_qty = sum(float(r.get("qty_sold", 0)) for r in prod_agg)
    gold["Q8"] = round(total_qty, 2)

    # Q9: revenue per category — only categories with revenue > 0
    rev_by_cat: Dict[str, float] = defaultdict(float)
    for r in prod_agg:
        pid = r.get("product_id")
        cat = pid_to_category.get(pid, "Other")
        rev_by_cat[cat] += float(r.get("revenue", 0))
    q9 = [
        {"category": cat, "revenue": round(rev, 2)}
        for cat, rev in sorted(rev_by_cat.items())
        if rev > _EPS
    ]
    gold["Q9"] = q9

    # Q10: average order value per customer — only customers with at least one order and total_spent > 0
    orders_per_customer: Dict[str, set] = defaultdict(set)
    for ev in events:
        cid = ev.get("customer_id")
        oid = ev.get("order_id")
        if cid and oid:
            orders_per_customer[cid].add(oid)
    q10 = []
    for r in cust_agg:
        cid = r["customer_id"]
        total_spent = float(r.get("revenue", 0))
        if total_spent <= _EPS:
            continue
        num_orders = len(orders_per_customer.get(cid, set())) or 1
        avg = round(total_spent / num_orders, 2)
        q10.append({"customer_id": cid, "average_order_value": avg})
    gold["Q10"] = q10

    return gold


def main():
    if not os.path.exists(SESSIONS_JSONL):
        raise FileNotFoundError(f"Sessions not found: {SESSIONS_JSONL}. Run generate_op_sequence.py first.")
    if not os.path.exists(PRODUCTS_JSON):
        raise FileNotFoundError(f"Catalog not found: {PRODUCTS_JSON}")

    catalog = _load_json(PRODUCTS_JSON)
    sessions = []
    with open(SESSIONS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            sessions.append(json.loads(line))

    output = []
    for s in sessions:
        gold = compute_gold_answers(s, catalog)
        # Include transcript so the file is self-contained (optional: can omit or truncate to save space)
        transcript = s.get("transcript") or []
        questions_and_answers = [
            {
                "qid": qid,
                "question": q_text,
                "gold_answer": gold[qid],
            }
            for qid, q_text in QUESTION_LIST
        ]
        output.append({
            "session_id": s["session_id"],
            "transcript": transcript,
            "questions_and_answers": questions_and_answers,
            # Also attach gold_answers in the shape prompt_and_eval expects (for direct use)
            "gold_answers": gold,
        })

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(output)} sessions to {OUT_JSON}")
    print(f"Each session has {len(QUESTION_LIST)} questions with gold answers.")


if __name__ == "__main__":
    main()
