import json
from datasets import load_dataset
from tqdm import tqdm

def save_oolong_samples(num_samples=50):
    # Mapping for easy iteration
    configs = [
        {"name": "synth", "path": "oolongbench/oolong-synth", "config": None},
        {"name": "real", "path": "oolongbench/oolong-real", "config": "dnd"}
    ]
    
    for item in configs:
        print(f"Fetching {item['name']}...")
        
        # Load and Shuffle
        ds = load_dataset(
            item['path'],
            item['config'],
            split="test",
        )
        
        # Select random samples
        sampled_data = ds.shuffle(seed=42).select(range(num_samples))
        
        # Convert to list of dicts
        output_list = [row for row in tqdm(sampled_data, desc=f"Processing {item['name']}")]
        
        # Save to JSON
        file_name = f"oolong_{item['name']}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(output_list, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully saved {num_samples} samples to {file_name}")

def save_oolong_top5():
    """Get 50 smallest by context length, save top 5 to oolong_*_5.json, then show them."""
    configs = [
        {"name": "synth", "path": "oolongbench/oolong-synth", "config": None},
        {"name": "real", "path": "oolongbench/oolong-real", "config": "dnd"},
    ]
    for item in configs:
        print(f"Fetching {item['name']}...")
        ds = load_dataset(
            item["path"],
            item["config"],
            split="test",
        )

        # Compute lengths in Python (avoids Arrow string overflow in ds.map)
        rows = []
        for i in tqdm(range(len(ds)), desc=f"Sorting {item['name']}"):
            row = dict(ds[i])
            row["_text_len"] = len(row.get("context_window_text", ""))
            rows.append(row)
        rows.sort(key=lambda x: x["_text_len"])

        smallest_50 = rows[:50]
        min_len, max_len = smallest_50[0]["_text_len"], smallest_50[-1]["_text_len"]
        top5 = [dict(r) for r in smallest_50[:5]]
        for r in top5:
            r.pop("_text_len", None)

        file_name = f"oolong_{item['name']}_5.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(top5, f, indent=2, ensure_ascii=False)

        print(f"Smallest: {min_len} chars, 50th: {max_len} chars")
        print(f"Saved top 5 smallest to {file_name}")
    print()
    for name in ["real", "synth"]:
        path = f"oolong_{name}_5.json"
        show_top_samples(path, path)


def show_top_samples(json_path, label=None):
    """Show samples from a saved oolong JSON file."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    lbl = label or json_path
    print(f"\n{'='*60}")
    print(f"  {lbl}  ({len(data)} samples)")
    print(f"{'='*60}")
    for i, sample in enumerate(data, 1):
        ctx = (sample.get("context_window_text", "") or "")[:200]
        print(f"\n--- Sample {i} ---")
        print(f"ID: {sample.get('id', 'N/A')}")
        print(f"Question: {sample.get('question', 'N/A')}")
        print(f"Answer: {sample.get('answer', 'N/A')}")
        print(f"Context (first 200 chars): {ctx}...")
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "top5":
        save_oolong_top5()
    elif len(sys.argv) > 1 and sys.argv[1] == "show":
        path = sys.argv[2] if len(sys.argv) > 2 else "oolong_real_5.json"
        show_top_samples(path)
    else:
        save_oolong_samples(50)