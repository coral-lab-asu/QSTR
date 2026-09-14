import json
from pathlib import Path

ORIGINAL_JSON = Path("test_generated_sql_nl_progress_5k_4.json")
DUPLICATES_JSON = Path("output/results/duplicates.json")
ZERO_NAN_JSON = Path("output/results/all_zero_or_nan_columns.json")

OUT_DEDUPED = Path("test_generated_sql_nl_progress_5k_4_deduped.json")
OUT_REMOVED = Path("test_generated_sql_nl_progress_5k_4_removed.json")


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main():
    original = load_json(ORIGINAL_JSON)
    duplicates = load_json(DUPLICATES_JSON)

    # Load zero/NaN column findings (if exists)
    if ZERO_NAN_JSON.exists():
        zero_nan_findings = load_json(ZERO_NAN_JSON)
    else:
        zero_nan_findings = []

    if "final" not in original or not isinstance(original["final"], list):
        raise ValueError("No 'final' list found in 5k_4.json")

    final_list = original["final"]

    # Collect indices to remove (track reasons separately)
    remove_due_to_duplicates = set()
    remove_due_to_zero_nan = set()

    for group in duplicates:
        members = group.get("members", [])
        if len(members) <= 1:
            continue

        # Keep the first entry, remove the rest
        for member in members[1:]:
            idx = member.get("index_in_final")
            if isinstance(idx, int) and 0 <= idx < len(final_list):
                remove_due_to_duplicates.add(idx)

    # Also remove queries where any column was entirely 0 or NaN
    for entry in zero_nan_findings:
        idx = entry.get("index_in_final")
        if isinstance(idx, int) and 0 <= idx < len(final_list):
            remove_due_to_zero_nan.add(idx)

    # Final removal set (union)
    indices_to_remove = remove_due_to_duplicates | remove_due_to_zero_nan

    # Build removed entries once (avoid duplicates in removed.json)
    removed_entries = [final_list[i] for i in sorted(indices_to_remove)]

    print(f"Total entries before dedupe: {len(final_list)}")
    print(f"Removed due to duplicates: {len(remove_due_to_duplicates)}")
    print(f"Removed due to all-0/NaN cols: {len(remove_due_to_zero_nan)}")
    print(f"Removed total (union): {len(indices_to_remove)}")
    print(f"Overlap (both reasons): {len(remove_due_to_duplicates & remove_due_to_zero_nan)}")

    # Create deduped list
    deduped_final = [
        item for i, item in enumerate(final_list)
        if i not in indices_to_remove
    ]

    print(f"Total entries after dedupe: {len(deduped_final)}")

    # Save deduped file
    deduped_obj = dict(original)
    deduped_obj["final"] = deduped_final

    save_json(deduped_obj, OUT_DEDUPED)
    save_json(removed_entries, OUT_REMOVED)

    print("\n✅ Done")
    print(f"Saved deduped file: {OUT_DEDUPED}")
    print(f"Saved removed entries: {OUT_REMOVED}")


if __name__ == "__main__":
    main()