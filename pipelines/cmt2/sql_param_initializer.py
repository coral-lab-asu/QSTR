"""
Helper functions to initialize variables in SQL queries before validation.
Inspired by question_answer_tables_cricket.ipynb parameter sampling logic.
"""

import re
import random
import math
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from pathlib import Path

from sql_agent_tools import run_sql_on_df


# =========================
# Temporal Predicate Builder (from notebook)
# =========================

TEMPORAL_RELATIONS = [
    "between", "overlaps", "within", "before", "after",
    "before_or_at", "after_or_at", "during"
]

TOP_FRAC = 0.6  # 60% top / 40% bottom


def _pick_relation() -> str:
    return random.choice(TEMPORAL_RELATIONS)


def snap_over_ball(x: float, one_to_six: bool = True) -> float:
    """
    Snap arbitrary float x to a valid 'over.ball' value.
    one_to_six=True  -> balls 1..6 (common commentary convention)
    one_to_six=False -> balls 0..5 (some scorecard DBs)
    """
    import math
    O = math.floor(x)
    ball = int(math.floor((x - O) * 10 + 1e-9))  # interpret .1 as 1 ball

    if one_to_six:
        if ball < 1:
            ball = 1
        if ball > 6:
            O += 1
            ball = 1
    else:
        if ball < 0:
            ball = 0
        if ball > 5:
            O += 1
            ball = 0

    return float(f"{O}.{ball}")


def pick_two_valid_points(x1: float, x2: float, one_to_six: bool = True, distinct: bool = True) -> Tuple[float, float]:
    if x1 > x2:
        x1, x2 = x2, x1
    p1 = snap_over_ball(random.uniform(x1, x2), one_to_six=one_to_six)
    p2 = snap_over_ball(random.uniform(x1, x2), one_to_six=one_to_six)
    if distinct and p1 == p2:
        # try once more
        p2 = snap_over_ball(random.uniform(x1, x2), one_to_six=one_to_six)
    return tuple(sorted((p1, p2)))


def build_temporal_with_phrase(
    relation: str | None,
    x1=None, x2=None,
    field: str = "overs",
    *,
    pick_points: bool = True,
    inclusive: bool = True,
    distinct: bool = True,
) -> Tuple[Optional[str], str]:
    """
    Returns (sql_predicate: Optional[str], nl_phrase: str)
    relation=None => (None, "the entire match")
    """
    # no relation => whole match
    if not relation or str(relation).lower() == "none":
        return None, "the entire match"

    r = str(relation).lower()
    a = field

    # choose points if we can
    if x1 is not None and x2 is not None and pick_points:
        b1, b2 = pick_two_valid_points(x1, x2)
    else:
        # order given bounds if any
        if x1 is not None and x2 is not None and x1 > x2:
            x1, x2 = x2, x1
        b1, b2 = x1, x2

    # --- SQL (point semantics) ---
    sql_map = {
        "before":        f"({a} < {b1})",
        "after":         f"({a} > {b2})",
        "before_or_at":  f"({a} <= {b1})",
        "after_or_at":   f"({a} >= {b2})",
        "between":       f"({a} BETWEEN {b1} AND {b2})",
        "overlaps":      f"({a} <= {b2} AND {b1} <= {a})",
        "within":        f"({a} > {b1} AND {a} < {b2})",
        "starts":        f"({a} = {b1})",
        "finishes":      f"({a} = {b2})",
        "equals":        f"({a} = {b1})",
        "meets":         f"({a} = {b1})",
        "met-by":        f"({a} = {b2})",
        "during":        f"({b1} < {a} AND {a} < {b2})",
    }

    # --- Natural language ---
    L = "over"
    nl_map = {
        "before":        f"when {L} is before {b1}",
        "after":         f"when {L} is after {b2}",
        "before_or_at":  f"when {L} is at or before {b1}",
        "after_or_at":   f"when {L} is at or after {b2}",
        "between":       f"when {L} is between {b1} and {b2}",
        "overlaps":      f"when {L} falls between {b1} and {b2}",
        "within":        f"when {L} is strictly between {b1} and {b2}",
        "starts":        f"when {L} equals {b1}",
        "finishes":      f"when {L} equals {b2}",
        "equals":        f"when {L} equals {b1}",
        "meets":         f"when {L} equals {b1}",
        "met-by":        f"when {L} equals {b2}",
        "during":        f"when {L} is between {b1} and {b2}",
    }

    if r not in sql_map:
        raise ValueError(f"Unknown temporal relation: {relation}")

    return sql_map[r], nl_map[r]


# =========================
# Spectrum Sampling (from notebook)
# =========================

def _tiered_lists_from_counts(counts: pd.Series, exclude: set | None = None):
    """
    Split items by frequency into 'top' (desc) and 'bottom' (asc).
    """
    if exclude is None:
        exclude = set()
    counts = counts.copy()
    if not counts.size:
        return [], [], []
    # Remove excluded
    counts = counts[~counts.index.isin(exclude)]
    if not counts.size:
        return [], [], []
    # Rank
    desc = counts.sort_values(ascending=False)
    asc = counts.sort_values(ascending=True)
    # Define "top half" and "bottom half" by rank
    half = max(1, len(desc)//2)
    top = list(desc.index[:half])
    bottom = list(asc.index[:half])
    # Middle = anything not in top or bottom
    mid = [x for x in counts.index if x not in set(top) | set(bottom)]
    return top, bottom, mid


def _spectrum_pick_list(counts: pd.Series, k: int, top_frac: float = TOP_FRAC, distinct: bool = True) -> List:
    """
    Produce a length-k list mixing ~ceil(k*top_frac) from 'top' and the rest from 'bottom'.
    """
    if k <= 0 or counts is None or counts.empty:
        return []
    need_top = math.ceil(k * top_frac)
    need_bot = k - need_top

    chosen = []
    used = set()

    top, bottom, middle = _tiered_lists_from_counts(counts)

    # cycle helpers
    def cycle_take(pool: List, need: int):
        out = []
        if not pool:
            return out
        i = 0
        while len(out) < need:
            cand = pool[i % len(pool)]
            if (not distinct) or (cand not in used):
                out.append(cand)
                used.add(cand)
            i += 1
            if distinct and len(used.intersection(pool)) == len(pool) and len(out) < need:
                distinct_local = False
                while len(out) < need:
                    out.append(pool[len(out) % len(pool)])
                return out
        return out

    # Take from top/bottom
    chosen += cycle_take(top, need_top)
    chosen += cycle_take(bottom, need_bot)

    # If still short, fill from middle, then from whole universe
    if len(chosen) < k:
        fill_need = k - len(chosen)
        mid_fill = cycle_take(middle, fill_need)
        chosen += mid_fill

    if len(chosen) < k:
        fill_need = k - len(chosen)
        universe = list(counts.sort_values(ascending=False).index)
        chosen += universe[:fill_need]

    return chosen[:k]


def _spectrum_pick_pairs(counts: pd.Series, k: int, top_frac: float = TOP_FRAC) -> List[tuple]:
    """
    For templates needing two distinct batsmen/bowlers per sample.
    """
    singles = _spectrum_pick_list(counts, k*2, top_frac=top_frac, distinct=True)
    pairs = []
    i = 0
    while len(pairs) < k and i+1 < len(singles):
        a, b = singles[i], singles[i+1]
        if a == b:
            for j in range(i+2, len(singles)):
                if singles[j] != a:
                    singles[i+1], singles[j] = singles[j], singles[i+1]
                    b = singles[i+1]
                    break
        pairs.append((a, b if a != b else a))
        i += 2
    return pairs


def _bounds_from_series(vals: pd.Series | list):
    vals = pd.Series(vals).dropna().tolist()
    if len(vals) < 2:
        return None
    return (min(vals), max(vals))


# =========================
# Parameter Sampling (adapted from notebook)
# =========================

def sample_params(
    df: pd.DataFrame,
    variables: List[str],
    num_samples: int = 1
) -> List[Dict[str, Any]]:
    """
    Spectrum sampling for cricket variables.
    Returns list of parameter dictionaries.
    """
    if not variables or num_samples <= 0:
        return [{"table_name": "df"}]

    sampled_questions: List[Dict[str, Any]] = []
    bats_counts = df['batsman'].value_counts() if 'batsman' in df.columns else pd.Series(dtype=int)
    bowl_counts = df['bowler'].value_counts() if 'bowler' in df.columns else pd.Series(dtype=int)
    
    bats_all = list(bats_counts.index) if not bats_counts.empty else []
    bowl_all = list(bowl_counts.index) if not bowl_counts.empty else []
    overs_all = df['overs'].dropna().tolist() if 'overs' in df.columns else []

    # Precompute spectrum lists for single-field cases
    bats_spectrum = _spectrum_pick_list(bats_counts, num_samples, top_frac=TOP_FRAC, distinct=True) if 'batsman' in variables and bats_counts.size > 0 else []
    bowl_spectrum = _spectrum_pick_list(bowl_counts, num_samples, top_frac=TOP_FRAC, distinct=True) if 'bowler' in variables and 'batsman' not in variables and bowl_counts.size > 0 else []

    # For pair cases
    bats_pairs = _spectrum_pick_pairs(bats_counts, num_samples, top_frac=TOP_FRAC) if ('batsman1' in variables and 'batsman2' in variables and bats_counts.size >= 2) else []
    bowl_pairs = _spectrum_pick_pairs(bowl_counts, num_samples, top_frac=TOP_FRAC) if ('bowler1' in variables and 'bowler2' in variables and bowl_counts.size >= 2) else []

    top_k = math.ceil(num_samples * TOP_FRAC)

    for i in range(num_samples):
        params: Dict[str, Any] = {"table_name": "df"}

        # ---- batsman single or pair ----
        if 'batsman1' in variables and 'batsman2' in variables:
            if i < len(bats_pairs):
                params['batsman1'], params['batsman2'] = bats_pairs[i]
            elif len(bats_all) >= 2:
                params['batsman1'], params['batsman2'] = random.sample(bats_all, 2)
            elif len(bats_all) == 1:
                params['batsman1'], params['batsman2'] = bats_all[0], bats_all[0]
        elif 'batsman' in variables:
            if i < len(bats_spectrum):
                params['batsman'] = bats_spectrum[i]
            elif bats_all:
                params['batsman'] = random.choice(bats_all)

        # ---- bowler single or pair ----
        if 'bowler1' in variables and 'bowler2' in variables:
            if i < len(bowl_pairs):
                params['bowler1'], params['bowler2'] = bowl_pairs[i]
            elif len(bowl_all) >= 2:
                params['bowler1'], params['bowler2'] = random.sample(bowl_all, 2)
            elif len(bowl_all) == 1:
                params['bowler1'], params['bowler2'] = bowl_all[0], bowl_all[0]
        elif 'bowler' in variables:
            if 'batsman' in params:
                # conditional spectrum within bowlers faced by this batsman
                sub = df[df['batsman'] == params['batsman']]
                cond_counts = sub['bowler'].value_counts() if 'bowler' in sub.columns else pd.Series(dtype=int)
                if cond_counts.empty:
                    if bowl_spectrum:
                        params['bowler'] = bowl_spectrum[i % len(bowl_spectrum)] if bowl_spectrum else None
                    elif bowl_all:
                        params['bowler'] = random.choice(bowl_all)
                else:
                    top_list, bottom_list, middle = _tiered_lists_from_counts(cond_counts)
                    if i < top_k and top_list:
                        params['bowler'] = top_list[i % len(top_list)]
                    elif bottom_list:
                        params['bowler'] = bottom_list[(i - top_k) % len(bottom_list)]
                    else:
                        params['bowler'] = (middle or list(cond_counts.index))[0] if middle or len(cond_counts) > 0 else None
            else:
                if bowl_spectrum:
                    params['bowler'] = bowl_spectrum[i] if i < len(bowl_spectrum) else None
                elif bowl_all:
                    params['bowler'] = random.choice(bowl_all)

        # ---- temporal predicate ----
        if (('x1' in variables and 'x2' in variables) or 'temporal_predicate' in variables):
            def _make_sql_and_phrase(x1, x2):
                rel = _pick_relation()
                if 't' in variables:
                    field = 't.overs'
                elif 'ceil' in variables:
                    field = 'CEIL(overs)'
                else:
                    field = 'overs'
                sql, phrase = build_temporal_with_phrase(rel, x1, x2, field=field)
                return sql, phrase, rel

            # bounds selection
            bounds = None
            if 'batsman' in params and 'bowler' in params:
                rel = df[(df['batsman'] == params['batsman']) & (df['bowler'] == params['bowler'])]['overs'] if 'overs' in df.columns else pd.Series(dtype=float)
                bounds = _bounds_from_series(rel)
            elif 'batsman' in params:
                rel = df[df['batsman'] == params['batsman']]['overs'] if 'overs' in df.columns else pd.Series(dtype=float)
                bounds = _bounds_from_series(rel)
            elif 'bowler' in params:
                rel = df[df['bowler'] == params['bowler']]['overs'] if 'overs' in df.columns else pd.Series(dtype=float)
                bounds = _bounds_from_series(rel)
            else:
                if len(overs_all) >= 2:
                    a, b = sorted(random.sample(overs_all, 2))
                    bounds = (a, b)

            if bounds:
                x1, x2 = bounds
                sql, phrase, rel = _make_sql_and_phrase(x1, x2)
                params['temporal_predicate'] = sql if sql is not None else '(1=1)'
                params['temporal_phrase'] = phrase if sql is not None else 'the entire match'
                params['temporal_relation'] = rel if sql is not None else 'none'
            else:
                # fallback: no temporal predicate
                params['temporal_predicate'] = '(1=1)'
                params['temporal_phrase'] = 'the entire match'
                params['temporal_relation'] = 'none'

        sampled_questions.append(params)

    return sampled_questions


# =========================
# Variable Extraction and Instantiation
# =========================

def extract_variables_from_sql(sql: str) -> List[str]:
    """
    Extract variable names from SQL query (e.g., {variable_name}).
    Returns list of variable names without braces.
    """
    pattern = r'\{([^}]+)\}'
    matches = re.findall(pattern, sql)
    return list(set(matches))  # return unique variables


def instantiate_sql(sql: str, params: Dict[str, Any]) -> str:
    """
    Replace {variable_name} placeholders in SQL with actual values from params.
    Handles string quoting correctly - detects if placeholder is already inside quotes.
    """
    import re
    
    result = sql
    for var_name, var_value in params.items():
        placeholder = f"{{{var_name}}}"
        
        # Find all occurrences of the placeholder
        pattern = re.escape(placeholder)
        matches = list(re.finditer(pattern, result))
        
        # Process matches in reverse order to maintain positions
        for match in reversed(matches):
            start_pos = match.start()
            end_pos = match.end()
            
            # Check if placeholder is inside quotes by looking at context
            text_before = result[:start_pos]
            text_after = result[end_pos:]
            
            # Check if immediately preceded by a single quote
            immediately_after_single_quote = start_pos > 0 and result[start_pos - 1] == "'"
            # Check if immediately followed by a single quote
            immediately_before_single_quote = end_pos < len(result) and result[end_pos] == "'"
            
            # Check if immediately preceded by a double quote
            immediately_after_double_quote = start_pos > 0 and result[start_pos - 1] == '"'
            # Check if immediately followed by a double quote
            immediately_before_double_quote = end_pos < len(result) and result[end_pos] == '"'
            
            # Determine if inside quotes (simple heuristic: quote before and after, or quote before and we're in a string context)
            inside_single_quotes = immediately_after_single_quote and immediately_before_single_quote
            inside_double_quotes = immediately_after_double_quote and immediately_before_double_quote
            
            # Also check for cases like: WHERE col = '{var}' (quote before, quote after)
            # Or: WHERE col = '{var} AND ...' (quote before, but we need to check if there's a quote after)
            if immediately_after_single_quote:
                # Look for the closing quote after the placeholder
                # Find next unescaped single quote
                remaining = text_after
                closing_quote_pos = None
                i = 0
                while i < len(remaining):
                    if remaining[i] == "'":
                        # Check if it's escaped
                        if i == 0 or remaining[i-1] != '\\':
                            closing_quote_pos = i
                            break
                    i += 1
                if closing_quote_pos is not None:
                    inside_single_quotes = True
            
            if immediately_after_double_quote:
                # Look for the closing double quote after the placeholder
                remaining = text_after
                closing_quote_pos = None
                i = 0
                while i < len(remaining):
                    if remaining[i] == '"':
                        # Check if it's escaped
                        if i == 0 or remaining[i-1] != '\\':
                            closing_quote_pos = i
                            break
                    i += 1
                if closing_quote_pos is not None:
                    inside_double_quotes = True
            
            # Determine replacement value
            if var_name == 'temporal_predicate':
                # SQL predicate - always insert as-is (no quotes)
                replacement = str(var_value)
            elif isinstance(var_value, (int, float)) or (isinstance(var_value, str) and var_value.startswith('(')):
                # Number or SQL expression - insert as-is
                replacement = str(var_value)
            else:
                # String value
                if inside_single_quotes:
                    # Already inside single quotes - just replace with escaped value (no additional quotes)
                    escaped_value = str(var_value).replace("'", "''")
                    replacement = escaped_value
                elif inside_double_quotes:
                    # Inside double quotes - replace with escaped value (no additional quotes)
                    escaped_value = str(var_value).replace('"', '""')
                    replacement = escaped_value
                else:
                    # Not inside quotes - add single quotes
                    escaped_value = str(var_value).replace("'", "''")
                    replacement = f"'{escaped_value}'"
            
            # Replace this occurrence
            result = result[:start_pos] + replacement + result[end_pos:]
    
    return result


def initialize_sql_items(
    sql_items: List[Dict[str, Any]],
    csv_path: str,
    num_instantiations: int = 1
) -> List[Dict[str, Any]]:
    """
    For each SQL item with variables, instantiate it with sampled parameters.
    Returns list of instantiated SQL items (one per instantiation).
    
    Args:
        sql_items: List of dicts with 'sql', 'description', 'csv_path', 'variables'
        csv_path: Path to CSV file
        num_instantiations: Number of parameter instantiations per SQL template
    
    Returns:
        List of instantiated SQL items (with 'sql' field replaced with instantiated SQL)
    """
    import pandas as pd
    
    # Load the CSV once
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load CSV {csv_path}: {e}")
    
    instantiated_items = []
    
    for item in sql_items:
        sql = item.get("sql", "")
        variables = item.get("variables", [])
        
        # Extract variables from SQL if not provided in item
        if not variables:
            variables = extract_variables_from_sql(sql)
        
        # If no variables found, use SQL as-is
        if not variables:
            instantiated_items.append(item.copy())
            continue
        
        # Sample parameters
        try:
            param_sets = sample_params(df, variables, num_samples=num_instantiations)
        except Exception as e:
            # If sampling fails, create a fallback with table_name only
            param_sets = [{"table_name": "df"}]
        
        # Create one instantiated item per parameter set
        for params in param_sets:
            instantiated_sql = instantiate_sql(sql, params)
            instantiated_item = {
                **item,
                "sql": instantiated_sql,
                "original_sql": sql,  # keep original for reference
                "params": params,  # store the parameters used
                "variables": variables,  # preserve variables list
            }
            instantiated_items.append(instantiated_item)
    
    return instantiated_items
