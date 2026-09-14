import json
from pathlib import Path
import argparse

# This script is intended to be run *after* src.eval.check_duplicates.
# It assumes:
#   - The original JSON with "final" items lives in data/data_progress_run/
#   - check_duplicates was run with an --out-dir that ends with "_duplicate_removed"
#
# Concretely, for the 5k run:
#   Original JSON:
#     data/data_progress_run/test_generated_sql_nl_progress_5k.json
#   check_duplicates out-dir:
#     data/data_progress_run/test_generated_sql_nl_progress_5k_duplicate_removed
#   This script will then write the deduped JSON as:
#     data/data_progress_run/test_generated_sql_nl_progress_5k_duplicate_removed.json
#
BASE_DIR = Path("data/data_progress_run")
ORIGINAL_JSON = BASE_DIR / "test_generated_sql_nl_progress_5k.json"

CHECK_OUT_DIR = BASE_DIR / "test_generated_sql_nl_progress_5k_duplicate_removed"
DUPLICATES_JSON = CHECK_OUT_DIR / "duplicates.json"
ZERO_NAN_JSON = CHECK_OUT_DIR / "all_zero_or_nan_columns.json"

# Main deduped dataset (same directory as original, name with _duplicate_removed)
OUT_DEDUPED = BASE_DIR / "test_generated_sql_nl_progress_5k_duplicate_removed.json"
# Optional: list of removed entries for inspection
OUT_REMOVED = BASE_DIR / "test_generated_sql_nl_progress_5k_removed.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate / low-signal entries from a generated SQL JSON using outputs from check_duplicates."
    )
    parser.add_argument(
        "--original-json",
        type=str,
        default=str(ORIGINAL_JSON),
        help="Path to the original JSON file containing a 'final' list (default: data/data_progress_run/test_generated_sql_nl_progress_5k.json).",
    )
    parser.add_argument(
        "--check-dir",
        type=str,
        default=str(CHECK_OUT_DIR),
        help="Directory where check_duplicates wrote duplicates.json and all_zero_or_nan_columns.json "
             "(default: data/data_progress_run/test_generated_sql_nl_progress_5k_duplicate_removed).",
    )
    parser.add_argument(
        "--out-deduped",
        type=str,
        default=str(OUT_DEDUPED),
        help="Path to write the deduped JSON (default: data/data_progress_run/test_generated_sql_nl_progress_5k_duplicate_removed.json).",
    )
    parser.add_argument(
        "--out-removed",
        type=str,
        default=str(OUT_REMOVED),
        help="Path to write the removed entries JSON (default: data/data_progress_run/test_generated_sql_nl_progress_5k_removed.json).",
    )

    args = parser.parse_args()

    original_json_path = Path(args.original_json)
    check_dir = Path(args.check_dir)
    duplicates_json_path = check_dir / "duplicates.json"
    zero_nan_json_path = check_dir / "all_zero_or_nan_columns.json"
    out_deduped_path = Path(args.out_deduped)
    out_removed_path = Path(args.out_removed)

    original = load_json(original_json_path)
    duplicates = load_json(duplicates_json_path)

    # Load zero/NaN column findings (if exists)
    if zero_nan_json_path.exists():
        zero_nan_findings = load_json(zero_nan_json_path)
    else:
        zero_nan_findings = []

    if "final" not in original or not isinstance(original["final"], list):
        raise ValueError("No 'final' list found in original JSON")

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

    save_json(deduped_obj, out_deduped_path)
    save_json(removed_entries, out_removed_path)

    print("\n✅ Done")
    print(f"Saved deduped file: {out_deduped_path}")
    print(f"Saved removed entries: {out_removed_path}")


if __name__ == "__main__":
    main()

# python -m src.eval.remove_duplicates \
#   --original-json "data/data_progress_run/test_generated_sql_nl_progress_5k_4.json" \
#   --check-dir "data/data_progress_run/test_generated_sql_nl_progress_5k_4_duplicate_removed" \
#   --out-deduped "data/data_progress_run/test_generated_sql_nl_progress_5k_4_duplicate_removed.json" \
#   --out-removed "data/data_progress_run/test_generated_sql_nl_progress_5k_4_removed.json"