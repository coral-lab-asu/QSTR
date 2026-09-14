# Script: generate_shopkeeper_sequences.py
# Purpose: generate canonical event sequences (tuples) + deterministic transcripts + aggregated tables
# - time_idx is integer from 1..N
# - ops: place_order, add_item, remove_item, modify_quantity, confirm_payment, return_item, inventory_adjustment
# - no 'note' field
# - configurable parameters: num_customers, total_turns, group_customers, allow_fractional_kg
# - outputs a JSONL file with one session per line containing: session_id, events, transcript, product_aggregation, customer_aggregation
# - Also writes a plain text transcript file for each session.
#
# Usage: run as a script or import functions. This demo writes generated sessions
# to the current working directory unless an output path is supplied.
#

# Set working directory to the directory of this script
# import os
# os.chdir(os.path.dirname(os.path.abspath(__file__)))

import json, random, os
from collections import defaultdict
import pandas as pd
from datetime import datetime

# === Full product catalog (50 items) ===
PRODUCT_CATALOG = [
  {"product_id":"P001","name":"Whole Milk 1L","category":"Dairy","unit":"unit","price":2.49},
  {"product_id":"P002","name":"Skim Milk 1L","category":"Dairy","unit":"unit","price":2.49},
  {"product_id":"P003","name":"Large Eggs (12 pack)","category":"Dairy","unit":"unit","price":3.99},
  {"product_id":"P004","name":"Salted Butter 200g","category":"Dairy","unit":"unit","price":2.79},
  {"product_id":"P005","name":"Cheddar Cheese 250g","category":"Dairy","unit":"unit","price":4.49},
  {"product_id":"P006","name":"Plain Yogurt 500g","category":"Dairy","unit":"unit","price":3.29},
  {"product_id":"P007","name":"Greek Yogurt 500g","category":"Dairy","unit":"unit","price":4.99},
  {"product_id":"P008","name":"White Bread Loaf","category":"Bakery","unit":"unit","price":2.19},
  {"product_id":"P009","name":"Whole Wheat Bread","category":"Bakery","unit":"unit","price":2.49},
  {"product_id":"P010","name":"Croissants (4 pack)","category":"Bakery","unit":"unit","price":3.99},
  {"product_id":"P011","name":"Bagels (6 pack)","category":"Bakery","unit":"unit","price":3.49},
  {"product_id":"P012","name":"Hamburger Buns (8 pack)","category":"Bakery","unit":"unit","price":2.99},
  {"product_id":"P013","name":"Bananas","category":"Produce","unit":"kg","price":1.29},
  {"product_id":"P014","name":"Apples (Gala)","category":"Produce","unit":"kg","price":2.49},
  {"product_id":"P015","name":"Oranges","category":"Produce","unit":"kg","price":2.29},
  {"product_id":"P016","name":"Tomatoes","category":"Produce","unit":"kg","price":2.99},
  {"product_id":"P017","name":"Potatoes","category":"Produce","unit":"kg","price":1.79},
  {"product_id":"P018","name":"Onions","category":"Produce","unit":"kg","price":1.59},
  {"product_id":"P019","name":"Carrots","category":"Produce","unit":"kg","price":1.39},
  {"product_id":"P020","name":"Broccoli","category":"Produce","unit":"kg","price":2.79},
  {"product_id":"P021","name":"Basmati Rice 1kg","category":"Pantry","unit":"unit","price":4.99},
  {"product_id":"P022","name":"White Rice 1kg","category":"Pantry","unit":"unit","price":3.99},
  {"product_id":"P023","name":"Pasta 500g","category":"Pantry","unit":"unit","price":1.79},
  {"product_id":"P024","name":"Spaghetti 500g","category":"Pantry","unit":"unit","price":1.79},
  {"product_id":"P025","name":"All-Purpose Flour 1kg","category":"Pantry","unit":"unit","price":2.49},
  {"product_id":"P026","name":"Granulated Sugar 1kg","category":"Pantry","unit":"unit","price":2.29},
  {"product_id":"P027","name":"Canned Tuna 150g","category":"Pantry","unit":"unit","price":1.29},
  {"product_id":"P028","name":"Canned Beans 400g","category":"Pantry","unit":"unit","price":0.99},
  {"product_id":"P029","name":"Tomato Ketchup 500ml","category":"Pantry","unit":"unit","price":2.49},
  {"product_id":"P030","name":"Olive Oil 1L","category":"Pantry","unit":"unit","price":7.99},
  {"product_id":"P031","name":"Orange Juice 1L","category":"Beverages","unit":"unit","price":2.99},
  {"product_id":"P032","name":"Apple Juice 1L","category":"Beverages","unit":"unit","price":2.79},
  {"product_id":"P033","name":"Cola 2L","category":"Beverages","unit":"unit","price":2.49},
  {"product_id":"P034","name":"Lemon Soda 2L","category":"Beverages","unit":"unit","price":2.39},
  {"product_id":"P035","name":"Bottled Water 1.5L","category":"Beverages","unit":"unit","price":0.89},
  {"product_id":"P036","name":"Sparkling Water 1L","category":"Beverages","unit":"unit","price":1.19},
  {"product_id":"P037","name":"Ground Coffee 250g","category":"Beverages","unit":"unit","price":5.99},
  {"product_id":"P038","name":"Black Tea (100 bags)","category":"Beverages","unit":"unit","price":4.49},
  {"product_id":"P039","name":"Potato Chips 150g","category":"Snacks","unit":"unit","price":1.99},
  {"product_id":"P040","name":"Tortilla Chips 200g","category":"Snacks","unit":"unit","price":2.29},
  {"product_id":"P041","name":"Chocolate Bar 100g","category":"Snacks","unit":"unit","price":1.49},
  {"product_id":"P042","name":"Biscuits 300g","category":"Snacks","unit":"unit","price":2.49},
  {"product_id":"P043","name":"Salted Peanuts 200g","category":"Snacks","unit":"unit","price":2.29},
  {"product_id":"P044","name":"Popcorn 100g","category":"Snacks","unit":"unit","price":1.79},
  {"product_id":"P045","name":"Chicken Breast (boneless)","category":"Meat & Frozen","unit":"kg","price":8.99},
  {"product_id":"P046","name":"Ground Beef","category":"Meat & Frozen","unit":"kg","price":9.49},
  {"product_id":"P047","name":"Frozen Pizza","category":"Meat & Frozen","unit":"unit","price":5.99},
  {"product_id":"P048","name":"Fish Fillets","category":"Meat & Frozen","unit":"kg","price":10.99},
  {"product_id":"P049","name":"Dishwashing Liquid 500ml","category":"Household","unit":"unit","price":2.49},
  {"product_id":"P050","name":"Toilet Paper (12 rolls)","category":"Household","unit":"unit","price":6.99}
]

# === Utilities ===
def pick_product(catalog):
    return random.choice(catalog)

def format_price(x):
    return f"{x:.2f}"

# === Event generator ===
def generate_events_session(session_id,
                            num_customers=10,
                            total_turns=40,
                            group_customers=False,
                            prob_modify=0.12,
                            prob_return=0.04,
                            prob_inventory_adjust=0.02,
                            max_items_per_turn=3,
                            allow_fractional_kg=True,
                            seed=None):
    """
    Generate one session (list of event tuples) with integer time_idx starting from 1.
    Returns: {"session_id":..., "events": [...], "params": {...}}
    """
    if seed is not None:
        random.seed(seed)
    events = []
    order_counter = 1000
    time_idx = 1
    customers = [f"CUST_{i+1}" for i in range(num_customers)]
    # determine turn order
    if group_customers:
        turns_per_customer = [total_turns // num_customers] * num_customers
        for i in range(total_turns % num_customers):
            turns_per_customer[i] += 1
        turn_sequence = []
        for ci, nturns in enumerate(turns_per_customer):
            turn_sequence.extend([customers[ci]] * nturns)
    else:
        turn_sequence = [random.choice(customers) for _ in range(total_turns)]
    last_order_for_customer = {c: None for c in customers}

    for cust in turn_sequence:
        r = random.random()
        # inventory adjustments are backend ops (no transcript lines)
        if r < prob_inventory_adjust:
            prod = pick_product(PRODUCT_CATALOG)
            new_qty = random.randint(0, 100)
            events.append({
                "time_idx": time_idx,
                "op": "inventory_adjustment",
                "order_id": None,
                "customer_id": None,
                "product_id": prod["product_id"],
                "qty": new_qty,
                "unit_price": prod["price"]
            })
            time_idx += 1
            continue
        has_order = last_order_for_customer[cust] is not None and random.random() < 0.6
        if not has_order:
            # create a new order (multiple place_order tuples possible per order)
            order_counter += 1
            order_id = f"#{order_counter}"
            last_order_for_customer[cust] = order_id
            num_items = random.randint(1, max_items_per_turn)
            for i in range(num_items):
                prod = pick_product(PRODUCT_CATALOG)
                if allow_fractional_kg and prod["unit"] == "kg":
                    qty = round(random.choice([0.5, 0.75, 1.0, 1.25, 1.5, 2.0]), 2)
                else:
                    qty = random.randint(1, 4)
                events.append({
                    "time_idx": time_idx,
                    "op": "place_order",
                    "order_id": order_id,
                    "customer_id": cust,
                    "product_id": prod["product_id"],
                    "qty": qty,
                    "unit_price": prod["price"]
                })
                time_idx += 1
        else:
            order_id = last_order_for_customer[cust]
            action_roll = random.random()
            if action_roll < prob_return:
                prod = pick_product(PRODUCT_CATALOG)
                qty = 1 if prod["unit"] == "unit" else (0.5 if allow_fractional_kg else 1)
                events.append({
                    "time_idx": time_idx,
                    "op": "return_item",
                    "order_id": order_id,
                    "customer_id": cust,
                    "product_id": prod["product_id"],
                    "qty": qty,
                    "unit_price": prod["price"]
                })
                time_idx += 1
            elif action_roll < prob_return + prob_modify:
                prod = pick_product(PRODUCT_CATALOG)
                old_q = random.randint(1,3)
                new_q = random.randint(1,4)
                events.append({
                    "time_idx": time_idx,
                    "op": "modify_quantity",
                    "order_id": order_id,
                    "customer_id": cust,
                    "product_id": prod["product_id"],
                    "old_qty": old_q,
                    "new_qty": new_q,
                    "unit_price": prod["price"]
                })
                time_idx += 1
            elif action_roll < prob_return + prob_modify + 0.12:
                amt = round(random.uniform(2.0, 80.0), 2)
                events.append({
                    "time_idx": time_idx,
                    "op": "confirm_payment",
                    "order_id": order_id,
                    "customer_id": cust,
                    "product_id": None,
                    "qty": None,
                    "unit_price": amt
                })
                time_idx += 1
                if random.random() < 0.5:
                    last_order_for_customer[cust] = None
            else:
                if random.random() < 0.85:
                    prod = pick_product(PRODUCT_CATALOG)
                    qty = round(random.choice([1,1,2,2,3]) if prod["unit"]=="unit" else random.choice([0.5,1.0,1.5]),2)
                    events.append({
                        "time_idx": time_idx,
                        "op": "add_item",
                        "order_id": order_id,
                        "customer_id": cust,
                        "product_id": prod["product_id"],
                        "qty": qty,
                        "unit_price": prod["price"]
                    })
                    time_idx += 1
                else:
                    prod = pick_product(PRODUCT_CATALOG)
                    qty = 1 if prod["unit"]=="unit" else (0.5 if allow_fractional_kg else 1)
                    events.append({
                        "time_idx": time_idx,
                        "op": "remove_item",
                        "order_id": order_id,
                        "customer_id": cust,
                        "product_id": prod["product_id"],
                        "qty": qty,
                        "unit_price": prod["price"]
                    })
                    time_idx += 1

    return {"session_id": session_id, "events": events, "params": {
        "num_customers": num_customers,
        "total_turns": total_turns,
        "group_customers": group_customers,
        "prob_modify": prob_modify,
        "prob_return": prob_return,
        "prob_inventory_adjust": prob_inventory_adjust,
        "max_items_per_turn": max_items_per_turn,
        "allow_fractional_kg": allow_fractional_kg
    }}

# === Transcript realizer ===
def events_to_transcript_lines(events):
    lines = []
    lines.append("Clerk: Next customer please.")
    for ev in events:
        op = ev["op"]
        cid = ev.get("customer_id")
        oid = ev.get("order_id")
        pid = ev.get("product_id")
        p = next((x for x in PRODUCT_CATALOG if x["product_id"]==pid), None) if pid else None
        prod_name = p["name"] if p else pid
        if op == "place_order":
            qty = ev["qty"]
            unit = p["unit"]
            price = ev["unit_price"]
            if unit == "kg":
                lines.append(f"Customer {cid}: I'd like {qty} kg {prod_name}.")
            else:
                lines.append(f"Customer {cid}: I'd like {qty} {prod_name}.")
            lines.append(f"Clerk: That's {qty} × ${format_price(price)} = ${format_price(qty*price)}. (Order {oid})")
        elif op == "add_item":
            qty = ev["qty"]
            unit = p["unit"]
            price = ev["unit_price"]
            if unit == "kg":
                lines.append(f"Customer {cid}: Add {qty} kg {prod_name} to {oid}.")
            else:
                lines.append(f"Customer {cid}: Add {qty} {prod_name} to {oid}.")
            lines.append(f"Clerk: Added {qty} × ${format_price(price)} = ${format_price(qty*price)} to {oid}.")
        elif op == "remove_item":
            qty = ev["qty"]
            unit = p["unit"]
            if unit == "kg":
                lines.append(f"Customer {cid}: Remove {qty} kg {prod_name} from {oid}.")
            else:
                lines.append(f"Customer {cid}: Remove {qty} {prod_name} from {oid}.")
            lines.append(f"Clerk: Removed {qty} {prod_name} from {oid}.")
        elif op == "modify_quantity":
            old_q = ev["old_qty"]
            new_q = ev["new_qty"]
            unit = p["unit"]
            if unit == "kg":
                lines.append(f"Customer {cid}: Actually make {prod_name} {new_q} kg instead of {old_q} kg in {oid}.")
            else:
                lines.append(f"Customer {cid}: Actually make {prod_name} {new_q} instead of {old_q} in {oid}.")
            lines.append(f"Clerk: Updated — {prod_name} changed from {old_q} to {new_q} in {oid}.")
        elif op == "confirm_payment":
            amt = ev["unit_price"]
            lines.append(f"Clerk: Order {oid} charged ${format_price(amt)}.")
        elif op == "return_item":
            qty = ev["qty"]
            unit = p["unit"]
            if unit == "kg":
                lines.append(f"Customer {cid}: I'd like to return {qty} kg of {prod_name} from {oid}.")
            else:
                lines.append(f"Customer {cid}: I'd like to return {qty} {prod_name} from {oid}.")
            lines.append(f"Clerk: Processed return of {qty} {prod_name} for {oid}.")
        elif op == "inventory_adjustment":
            # no transcript evidence for inventory adjustments
            continue
    return lines

# === Aggregation ===
def aggregate_events(events):
    qty_by_product = defaultdict(float)
    revenue_by_product = defaultdict(float)
    qty_by_customer = defaultdict(float)
    revenue_by_customer = defaultdict(float)
    for ev in events:
        op = ev["op"]
        if op == "inventory_adjustment":
            continue
        if op in ("place_order","add_item"):
            signed_qty = float(ev["qty"])
            amt = signed_qty * float(ev["unit_price"])
        elif op in ("remove_item","return_item"):
            signed_qty = -1.0 * float(ev["qty"])
            amt = signed_qty * float(ev["unit_price"])
        elif op == "modify_quantity":
            signed_qty = float(ev["new_qty"]) - float(ev["old_qty"])
            amt = signed_qty * float(ev["unit_price"])
        elif op == "confirm_payment":
            signed_qty = 0.0
            amt = float(ev["unit_price"])
        else:
            signed_qty = 0.0
            amt = 0.0
        pid = ev.get("product_id")
        cid = ev.get("customer_id")
        if pid:
            qty_by_product[pid] += signed_qty
            revenue_by_product[pid] += amt
        if cid:
            qty_by_customer[cid] += signed_qty
            revenue_by_customer[cid] += amt
    prod_rows = []
    for p in PRODUCT_CATALOG:
        pid = p["product_id"]
        prod_rows.append({
            "product_id": pid,
            "name": p["name"],
            "unit": p["unit"],
            "qty_sold": round(qty_by_product.get(pid, 0.0), 2),
            "revenue": round(revenue_by_product.get(pid, 0.0), 2)
        })
    cust_rows = []
    for cid, q in qty_by_customer.items():
        cust_rows.append({
            "customer_id": cid,
            "qty": round(q, 2),
            "revenue": round(revenue_by_customer.get(cid, 0.0), 2)
        })
    prod_df = pd.DataFrame(prod_rows).sort_values(by="product_id").reset_index(drop=True)
    cust_df = pd.DataFrame(cust_rows).sort_values(by="customer_id").reset_index(drop=True)
    return prod_df, cust_df

# === Session file writer ===
def write_sessions_jsonl(sessions, out_dir="synData/shopkeeper_sessions"):
    os.makedirs(out_dir, exist_ok=True)
    jsonl_path = os.path.join(out_dir, "sessions.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as fw:
        for s in sessions:
            fw.write(json.dumps(s) + "\n")
    # Also write individual transcripts
    for s in sessions:
        tid = s["session_id"]
        txt_path = os.path.join(out_dir, f"{tid}_transcript.txt")
        with open(txt_path, "w", encoding="utf-8") as ft:
            ft.write("\n".join(s["transcript"]))
    return jsonl_path, out_dir

# === Demo: generate 3 sessions and save ===
def demo_generate_and_save():
    random.seed(12345)
    sessions = []
    for i in range(3):
        sid = f"session_{i+1:03d}"
        sess = generate_events_session(session_id=sid,
                                       num_customers=4 + i,
                                       total_turns=30 + i*10,
                                       group_customers=False,
                                       prob_modify=0.12,
                                       prob_return=0.05,
                                       prob_inventory_adjust=0.02,
                                       max_items_per_turn=3,
                                       allow_fractional_kg=True,
                                       seed=12345 + i)
        events = sess["events"]
        transcript_lines = events_to_transcript_lines(events)
        prod_df, cust_df = aggregate_events(events)
        session_record = {
            "session_id": sid,
            "generated_at": datetime.utcnow().isoformat()+"Z",
            "params": sess["params"],
            "events": events,
            "transcript": transcript_lines,
            "product_aggregation": prod_df.to_dict(orient="records"),
            "customer_aggregation": cust_df.to_dict(orient="records")
        }
        sessions.append(session_record)
    jsonl_path, out_dir = write_sessions_jsonl(sessions)
    return jsonl_path, out_dir, sessions

# Run demo and show a preview
jsonl_path, out_dir, sessions = demo_generate_and_save()
print("Saved sessions JSONL to:", jsonl_path)
print("Sample transcript (session_001, first 30 lines):\n")
for i, line in enumerate(sessions[0]["transcript"][:30],1):
    print(f"{i:02d}. {line}")
print("\nSample product aggregation (session_001, non-zero qty rows):")
import pandas as pd
df = pd.DataFrame(sessions[0]["product_aggregation"])
nz = df[df["qty_sold"] != 0].reset_index(drop=True)
print(nz.to_string(index=False))

# Inform user where files are
print(f"\nAll session files and transcripts are in: {out_dir}")
print(f"You can download the JSONL: file://{jsonl_path}")
