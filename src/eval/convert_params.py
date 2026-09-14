import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse

ALLOWED_PARAMS = ("batsman", "bowler")


# -----------------------------
# Utilities
# -----------------------------
def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def get_allowed_params(params: Any) -> List[str]:
    """Return only ['batsman','bowler'] if present in params dict (case-insensitive)."""
    if not isinstance(params, dict):
        return []
    out = []
    keys_lower = {k.lower(): k for k in params.keys() if isinstance(k, str)}
    for p in ALLOWED_PARAMS:
        if p in keys_lower:
            out.append(p)  # return normalized lowercase
    return out


def get_allowed_param_values(params: Any) -> Dict[str, str]:
    """Return allowed param values as {'batsman': 'Head', 'bowler': 'Fazalhaq Farooqi'}.

    Only includes keys in ALLOWED_PARAMS. Keys are normalized to lowercase.
    """
    if not isinstance(params, dict):
        return {}

    out: Dict[str, str] = {}
    for k, v in params.items():
        if isinstance(k, str) and k.lower() in ALLOWED_PARAMS:
            out[k.lower()] = "" if v is None else str(v)
    return out


def contains_param_token(text: str, p: str) -> bool:
    """Check if {p} or word p appears (case-insensitive) in text."""
    if not isinstance(text, str):
        return False
    if f"{{{p}}}" in text:
        return True
    return re.search(rf"\b{re.escape(p)}\b", text, flags=re.IGNORECASE) is not None


# -----------------------------
# Task 1: Fix original_sql
# -----------------------------
def replace_quoted_placeholder(sql: str, p: str) -> Tuple[str, bool]:
    """
    Replace quoted occurrences of p with '{p}'.
    Examples matched:
      'batsman', ' batsman ', "batsman ", " batsman"
    """
    if not isinstance(sql, str):
        return sql, False

    changed = False
    # Match '  batsman  ' OR " batsman " (same quote on both sides)
    pat = re.compile(rf"(['\"])\s*{re.escape(p)}\s*\1", flags=re.IGNORECASE)
    new_sql, n = pat.subn(rf"'{{{p}}}'", sql)  # normalize to single quotes for SQL string
    if n > 0:
        sql = new_sql
        changed = True

    return sql, changed


def ensure_braced_placeholder(sql: str, p: str) -> Tuple[str, bool]:
    """
    Ensure {p} exists somewhere in sql. If missing, try to create it by replacing
    sloppy placeholders.
    """
    if not isinstance(sql, str):
        return sql, False

    if f"{{{p}}}" in sql:
        return sql, False

    changed_any = False

    # First: fix quoted 'p' / "p" occurrences -> '{p}'
    sql, changed = replace_quoted_placeholder(sql, p)
    changed_any |= changed

    # If still missing, try to fix unquoted value positions conservatively:
    # e.g., WHERE bowler = {bowler}  -> WHERE bowler = '{bowler}'
    # or WHERE bowler = bowler (rare) -> WHERE bowler = '{bowler}' (only if looks like value position)
    if f"{{{p}}}" not in sql:
        # Pattern: "<col> = {p}" (unquoted)  OR "<col> = p" (bare)
        # We'll only rewrite when the LHS column name matches p (common in your data: bowler = ...)
        pat_value = re.compile(
            rf"(\b{re.escape(p)}\b\s*=\s*)(\{{\s*{re.escape(p)}\s*\}}|\b{re.escape(p)}\b)(?!\s*\.)",
            flags=re.IGNORECASE
        )
        new_sql, n = pat_value.subn(rf"\1'{{{p}}}'", sql)
        if n > 0:
            sql = new_sql
            changed_any = True

    return sql, changed_any


def fix_original_sql(obj: Dict[str, Any], params_to_fix: List[str]) -> bool:
    """Apply Task 1 to obj['original_sql']."""
    if "original_sql" not in obj or not isinstance(obj.get("original_sql"), str):
        return False

    sql = obj["original_sql"]
    changed_any = False
    for p in params_to_fix:
        sql, changed = ensure_braced_placeholder(sql, p)
        changed_any |= changed

    if changed_any:
        obj["original_sql"] = sql
    return changed_any


# -----------------------------
# Task 2: Fix question/paraphrases
# -----------------------------
def normalize_text_placeholders(text: str, p: str) -> Tuple[str, bool]:
    """
    Replace occurrences of 'p', "p", <p> (with optional internal whitespace) with {p}.
    Does NOT replace bare word p because that can make normal English awkward.
    """
    if not isinstance(text, str):
        return text, False

    changed = False
    out = text

    # ' p ' or " p " -> {p}
    pat_quoted = re.compile(rf"(['\"])\s*{re.escape(p)}\s*\1", flags=re.IGNORECASE)
    out2, n = pat_quoted.subn(rf"{{{p}}}", out)
    if n > 0:
        out = out2
        changed = True

    # < p > -> {p}
    pat_angle = re.compile(rf"<\s*{re.escape(p)}\s*>", flags=re.IGNORECASE)
    out2, n = pat_angle.subn(rf"{{{p}}}", out)
    if n > 0:
        out = out2
        changed = True

    return out, changed


def replace_value_with_placeholder(text: str, param: str, value: str) -> Tuple[str, bool]:
    """Replace occurrences of the concrete value (e.g., 'Head') with {param} in NL text.

    Handles:
      - quoted: 'Head' or "Head"
      - unquoted: Head
      - multi-word values like 'Fazalhaq Farooqi'

    Uses conservative boundaries: value must not be embedded in a larger word.
    """
    if not isinstance(text, str) or not value:
        return text, False

    placeholder = f"{{{param}}}"
    changed = False
    out = text

    # Quoted value
    pat_q = re.compile(rf"(['\"])\s*{re.escape(value)}\s*\1", flags=re.IGNORECASE)
    out2, n = pat_q.subn(placeholder, out)
    if n > 0:
        out = out2
        changed = True

    # Unquoted value with conservative boundaries (works for multi-word too)
    pat_b = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])", flags=re.IGNORECASE)
    out2, n = pat_b.subn(placeholder, out)
    if n > 0:
        out = out2
        changed = True

    return out, changed


def replace_values_in_text(text: str, param_values: Dict[str, str]) -> Tuple[str, bool]:
    """Replace allowed param values with their placeholders in a single text field."""
    if not isinstance(text, str):
        return text, False

    changed_any = False
    out = text
    for p, v in param_values.items():
        out2, ch = replace_value_with_placeholder(out, p, v)
        if ch:
            out = out2
            changed_any = True
    return out, changed_any


def inject_placeholders_into_question_from_paraphrases(question: str, paraphrases: Any, params_to_fix: List[str]) -> Tuple[str, bool]:
    """If placeholders appear in any paraphrase, inject them into the main question.

    Rule requested:
      - If any paraphrase contains {bowler}, then in the question add "'{bowler}'" after the word 'bowler'
      - If any paraphrase contains {batsman}, then in the question add "'{batsman}'" after the word 'batsman'

    This only modifies the question if the placeholder is not already present there.
    """
    if not isinstance(question, str):
        return question, False

    paras = paraphrases if isinstance(paraphrases, list) else []

    has_bowler_ph = any(isinstance(p, str) and "{bowler}" in p for p in paras)
    has_batsman_ph = any(isinstance(p, str) and "{batsman}" in p for p in paras)

    out = question
    changed = False

    if "bowler" in params_to_fix and has_bowler_ph and "{bowler}" not in out:
        # Add placeholder right after the word 'bowler' (first occurrence), but don't double-insert.
        # Examples: "a given bowler," -> "a given bowler '{bowler}',"
        pat = re.compile(r"\bbowler\b(?!\s*\{bowler\}|\s*'\{bowler\}')", flags=re.IGNORECASE)
        out2, n = pat.subn("bowler '{bowler}'", out, count=1)
        if n > 0:
            out = out2
            changed = True

    if "batsman" in params_to_fix and has_batsman_ph and "{batsman}" not in out:
        pat = re.compile(r"\bbatsman\b(?!\s*\{batsman\}|\s*'\{batsman\}')", flags=re.IGNORECASE)
        out2, n = pat.subn("batsman '{batsman}'", out, count=1)
        if n > 0:
            out = out2
            changed = True

    return out, changed


def fix_question_and_paraphrases(obj: Dict[str, Any], params_to_fix: List[str], param_values: Dict[str, str]) -> Tuple[bool, List[str]]:
    """
    Normalize placeholders in question + paraphrases.
    If a param is missing from BOTH question and all paraphrases, append to question.
    Returns (changed_any, missing_everywhere_params)
    """
    changed_any = False

    # Normalize question
    q = obj.get("question")
    if isinstance(q, str):
        # First replace concrete values (e.g., Head -> {batsman})
        q2, chv = replace_values_in_text(q, param_values)
        if chv:
            q = q2
            changed_any = True

        # Then normalize quoted/angled placeholders like ' batsman ' -> {batsman}
        for p in params_to_fix:
            q2, ch = normalize_text_placeholders(q, p)
            if ch:
                q = q2
                changed_any = True
        obj["question"] = q

    # Normalize paraphrases
    paras = obj.get("paraphrases")
    if isinstance(paras, list):
        new_paras = []
        para_changed = False
        for para in paras:
            if isinstance(para, str):
                s = para

                # Replace concrete values first
                s2, chv = replace_values_in_text(s, param_values)
                if chv:
                    s = s2
                    para_changed = True

                # Then normalize placeholder formatting
                for p in params_to_fix:
                    s2, ch = normalize_text_placeholders(s, p)
                    if ch:
                        s = s2
                        para_changed = True

                new_paras.append(s)
            else:
                new_paras.append(para)
        if para_changed:
            obj["paraphrases"] = new_paras
            changed_any = True

    # If any paraphrase already uses placeholders, inject them into the main question after words like batsman/bowler
    q_now = obj.get("question")
    if isinstance(q_now, str):
        q2, chi = inject_placeholders_into_question_from_paraphrases(q_now, obj.get("paraphrases"), params_to_fix)
        if chi:
            obj["question"] = q2
            changed_any = True

    # Check if params appear anywhere; if not, append them to question.
    missing_everywhere = []
    for p in params_to_fix:
        mentioned_in_q = contains_param_token(obj.get("question", ""), p)
        mentioned_in_para = False
        if isinstance(obj.get("paraphrases"), list):
            for para in obj["paraphrases"]:
                if isinstance(para, str) and contains_param_token(para, p):
                    mentioned_in_para = True
                    break
        if not mentioned_in_q and not mentioned_in_para:
            missing_everywhere.append(p)

    if missing_everywhere:
        if isinstance(obj.get("question"), str):
            suffix = " Parameters: " + ", ".join([f"{{{p}}}" for p in missing_everywhere]) + "."
            obj["question"] = obj["question"].rstrip() + suffix
            changed_any = True

    return changed_any, missing_everywhere


# -----------------------------
# Traversal
# -----------------------------
def traverse(obj: Any, stats: Dict[str, int]) -> Any:
    if isinstance(obj, dict):
        has_original_sql = "original_sql" in obj and isinstance(obj.get("original_sql"), str)
        has_params = "params" in obj and isinstance(obj.get("params"), dict)

        if has_original_sql and has_params:
            params_to_fix = get_allowed_params(obj["params"])
            param_values = get_allowed_param_values(obj["params"])

            if params_to_fix:
                if fix_original_sql(obj, params_to_fix):
                    stats["original_sql_fixed"] += 1

                changed_text, missing = fix_question_and_paraphrases(obj, params_to_fix, param_values)
                if changed_text:
                    stats["text_fixed"] += 1
                if missing:
                    stats["text_missing_appended"] += 1

        # recurse into children
        for k, v in list(obj.items()):
            obj[k] = traverse(v, stats)
        return obj

    if isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = traverse(obj[i], stats)
        return obj

    return obj


# -----------------------------
# Main / CLI
# -----------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize batsman/bowler placeholders in generated SQL JSON."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input JSON file to fix (e.g. data/data_progress_run/test_generated_sql_nl_progress_5k_4_removed.json).",
    )
    parser.add_argument(
        "--out-dir",
        default="output/converted_params",
        help="Directory to write the fixed JSON into (default: output/converted_params).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="Optional output file name. If omitted, uses <input_stem>_fixed.json.",
    )

    args = parser.parse_args()

    in_file = Path(args.input)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.out_name:
        out_file = output_dir / args.out_name
    else:
        out_file = output_dir / f"{in_file.stem}_fixed.json"

    data = load_json(in_file)

    stats = {
        "original_sql_fixed": 0,
        "text_fixed": 0,
        "text_missing_appended": 0,
    }

    fixed = traverse(data, stats)
    save_json(fixed, out_file)

    print("✅ Done.")
    print(f"Input : {in_file}")
    print(f"Output: {out_file}")
    print("Stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

# Example:
# python -m src.eval.convert_params \
# --input "data/data_progress_run/test_generated_sql_nl_progress_5k_4_removed.json" \
# --out-dir "data/data_final/test_generated_sql_nl_progress_5k_4_removed_fixed.json"