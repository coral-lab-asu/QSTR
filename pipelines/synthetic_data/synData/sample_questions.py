import json, os, math
from typing import List, Dict, Any, Tuple

# Paste the JSON above as a Python object
QUESTION_SCHEMAS = [
  {
    "qid": "Q1",
    "question": "What is the total quantity sold per product?",
    "type": "table",
    "include_all_products": True,
    "columns": [
      {"name": "product_id", "type": "string", "description": "Product identifier (e.g., P001)"},
      {"name": "name", "type": "string", "description": "Product canonical name"},
      {"name": "total_qty_sold", "type": "number", "description": "Total quantity sold (units or kg). Use floats for kg; round to 2 decimals if fractional."}
    ],
    "sorting": {"primary": "product_id", "order": "asc"},
    "notes": "Return one row per product (all products if include_all_products=true)."
  },
  {
    "qid": "Q2",
    "question": "What is the total revenue per product?",
    "type": "table",
    "include_all_products": True,
    "columns": [
      {"name": "product_id", "type": "string"},
      {"name": "name", "type": "string"},
      {"name": "total_revenue", "type": "number", "description": "Total revenue from this product in same currency as transcript (round to 2 decimals)."}
    ],
    "sorting": {"primary": "product_id", "order": "asc"},
    "notes": "Return one row per product."
  },
  {
    "qid": "Q3",
    "question": "What is the total quantity bought by each customer?",
    "type": "table",
    "columns": [
      {"name":"customer_id","type":"string"},
      {"name":"total_qty","type":"number","description":"Total quantity bought by that customer (sum of units and kg as recorded)."}
    ],
    "sorting": {"primary": "customer_id", "order":"asc"},
    "notes": "Return rows for every customer who appears in the transcript."
  },
  {
    "qid": "Q4",
    "question": "How much did each customer spend?",
    "type": "table",
    "columns": [
      {"name":"customer_id","type":"string"},
      {"name":"total_spent","type":"number","description":"Total money spent by customer; round to 2 decimals."}
    ],
    "sorting": {"primary":"customer_id","order":"asc"},
    "notes":"Return rows for every customer who appears in the transcript."
  },
  {
    "qid": "Q5",
    "question": "Which 5 products had the highest revenue?",
    "type":"table",
    "columns":[
      {"name":"rank","type":"integer","description":"1 = highest revenue"},
      {"name":"product_id","type":"string"},
      {"name":"name","type":"string"},
      {"name":"revenue","type":"number","description":"Revenue, round to 2 decimals"}
    ],
    "constraints":{"top_k":5},
    "sorting":{"primary":"rank","order":"asc"},
    "notes":"Ties may be broken arbitrarily but must preserve rank order starting at 1."
  },
  {
    "qid":"Q6",
    "question":"Which 5 products had the highest quantity sold?",
    "type":"table",
    "columns":[
      {"name":"rank","type":"integer"},
      {"name":"product_id","type":"string"},
      {"name":"name","type":"string"},
      {"name":"qty_sold","type":"number","description":"Total qty sold; round to 2 decimals"}
    ],
    "constraints":{"top_k":5},
    "sorting":{"primary":"rank","order":"asc"}
  },
  {
    "qid":"Q7",
    "question":"What is the total revenue across all products?",
    "type":"table",
    "columns":[
      {"name":"total_revenue","type":"number","description":"Single-row table with total revenue (round to 2 decimals)"}
    ],
    "notes":"Return a single row with the scalar."
  },
  {
    "qid":"Q8",
    "question":"What is the total number of units (or kg) sold across all products?",
    "type":"table",
    "columns":[
      {"name":"total_qty_all","type":"number","description":"Scalar sum of all quantities (units and kg as recorded). Round to 2 decimals."}
    ]
  },
  {
    "qid":"Q9",
    "question":"What is the total revenue per category?",
    "type":"table",
    "columns":[
      {"name":"category","type":"string"},
      {"name":"revenue","type":"number","description":"Total revenue for that category; round to 2 decimals"}
    ],
    "sorting":{"primary":"category","order":"asc"},
    "notes":"Return one row per category present in the catalog."
  },
  {
    "qid":"Q10",
    "question":"What is the average order value per customer?",
    "type":"table",
    "columns":[
      {"name":"customer_id","type":"string"},
      {"name":"average_order_value","type":"number","description":"Average revenue per order for that customer; round to 2 decimals"}
    ],
    "sorting":{"primary":"customer_id","order":"asc"},
    "notes":"Include customers who had at least one order."
  }
]

# -- write JSON file utility
def write_question_schemas(path="synData/question_schemas.json"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fw:
        json.dump(QUESTION_SCHEMAS, fw, indent=2, ensure_ascii=False)
    return path

# -- small validator for model-returned tables
def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def validate_table(schema: Dict[str,Any], table_rows: List[Dict[str,Any]], relax_zero_rows: bool=False) -> Tuple[bool, List[str]]:
    """
    schema: single question schema (one element from QUESTION_SCHEMAS)
    table_rows: list of row-dicts returned by model
    Returns: (ok:bool, errors:list[str])
    """
    errors = []
    cols = schema["columns"]
    required_col_names = [c["name"] for c in cols]

    # check row count constraints for top_k/scalar
    if schema.get("constraints", {}).get("top_k") is not None:
        k = schema["constraints"]["top_k"]
        if len(table_rows) != k:
            errors.append(f"Expected top_k={k} rows but got {len(table_rows)} rows.")
    if schema["type"] == "table" and len(cols)==1 and "total" in cols[0]["name"].lower():
        # scalar table: expect exactly 1 row
        if len(table_rows) != 1:
            errors.append("Expected a single-row table for scalar output.")

    if not table_rows and not relax_zero_rows:
        errors.append("Model returned no rows; expected at least one row.")

    # check columns exist and types
    for i, row in enumerate(table_rows):
        for c in cols:
            cname = c["name"]
            if cname not in row:
                errors.append(f"Row {i}: missing column '{cname}'.")
                continue
            val = row[cname]
            ctype = c["type"]
            if ctype == "string":
                if not isinstance(val, str):
                    errors.append(f"Row {i}, col '{cname}': expected string but got {type(val).__name__}.")
            elif ctype == "integer":
                if not (isinstance(val, int) and not isinstance(val, bool)):
                    errors.append(f"Row {i}, col '{cname}': expected integer but got {val} ({type(val).__name__}).")
            elif ctype == "number":
                if not _is_number(val):
                    errors.append(f"Row {i}, col '{cname}': expected number but got {type(val).__name__}.")
                else:
                    # if numeric, check rounding for monetary columns (heuristic)
                    lname = cname.lower()
                    if any(k in lname for k in ["revenue","spent","total_revenue","average","price"]):
                        # check two-decimal rounding
                        rounded = round(float(val) + 0.0, 2)
                        if abs(rounded - float(val)) > 1e-8:
                            # allow small floating noise; check difference
                            # but if val has more than 2 decimals (beyond rounding), warn
                            errors.append(f"Row {i}, col '{cname}': expected value rounded to 2 decimals but got {val}.")
    # optional ordering checks (rank)
    if schema.get("constraints", {}).get("top_k"):
        # ensure rank column monotonic
        if "rank" in required_col_names:
            ranks = []
            for i,row in enumerate(table_rows):
                if "rank" in row:
                    ranks.append(row["rank"])
            if ranks != sorted(ranks):
                errors.append("Rank column is not sorted ascending.")
            if ranks and ranks[0] != 1:
                errors.append("Rank should start at 1.")
    # primary sorting enforcement (best-effort)
    if "sorting" in schema and table_rows:
        primary = schema["sorting"]["primary"]
        order = schema["sorting"].get("order","asc")
        # skip enforcement if primary column missing
        if primary in table_rows[0]:
            seq = [row.get(primary) for row in table_rows]
            try:
                if order=="asc":
                    if seq != sorted(seq):
                        errors.append(f"Rows not sorted ascending by {primary}.")
                else:
                    if seq != sorted(seq, reverse=True):
                        errors.append(f"Rows not sorted descending by {primary}.")
            except Exception:
                pass

    return (len(errors)==0, errors)


# Example: write schema json to cwd
if __name__ == "__main__":
    path = write_question_schemas("question_schemas.json")
    print("Wrote question schema to", path)
    # Example of validation usage (pseudo)
    # ok, errs = validate_table(QUESTION_SCHEMAS[0], model_rows_for_Q1)