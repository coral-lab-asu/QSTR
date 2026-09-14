from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, mannwhitneyu, ttest_rel, wilcoxon


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "output_dataset_split" / "dataset.split_analysis.json"
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "tmp" / "two_model_decomposed_analysis"

MODEL_PATHS = {
    "Llama-3.3-70B-Instruct": PROJECT_ROOT
    / "baseline-results-split-analysis-eval"
    / "meta-llama"
    / "Llama-3.3-70B-Instruct"
    / "COT"
    / "eval.samplewise.jsonl",
    "Qwen2.5-72B-Instruct": PROJECT_ROOT
    / "baseline-results-split-analysis-eval"
    / "Qwen"
    / "Qwen2.5-72B-Instruct"
    / "COT"
    / "eval.samplewise.jsonl",
}

MODEL_ORDER = list(MODEL_PATHS.keys())
LEVEL_ORDER = ["low", "medium", "high"]

EVENT_METRICS = [
    ("pk_f1_x100", "PK-F1", True),
    ("pk_recall_x100", "PK recall", True),
    ("pk_precision_x100", "PK precision", True),
    ("pk_exact_set_match_num", "PK exact-set match", True),
]

NUMERIC_METRICS = [
    ("weighted_rmse", "Weighted RMSE", False),
    ("cell_acc_num", "Aligned cell accuracy", True),
    ("overcount_pct", "Overcount%", False),
    ("undercount_pct", "Undercount%", False),
    ("net_over_under_pct", "Net over-under bias", False),
]

FACTOR_LABELS = {
    "span_bucket": "Context scoping",
    "skill_entity_schema_grounding": "Entity grounding",
    "skill_temporal_reasoning": "Temporal reasoning",
    "skill_sql_reasoning": "SQL reasoning",
    "skill_compositional_sql": "Compositional depth",
}

PRESSURE_COLS = [
    "grounding_pressure",
    "localization_pressure",
    "execution_pressure",
    "output_pressure",
]

PRESSURE_LABELS = {
    "grounding_pressure": "Grounding",
    "localization_pressure": "Localization",
    "execution_pressure": "Execution",
    "output_pressure": "Output",
}


def as_list(x):
    if isinstance(x, list):
        return x
    if x is None:
        return []
    if isinstance(x, str):
        return [item.strip() for item in x.split(",") if item.strip()]
    try:
        if pd.isna(x):
            return []
    except Exception:
        pass
    try:
        return list(x)
    except TypeError:
        return [x]


def normalize_temporal_relation(is_temporal, temporal_relation):
    if not bool(is_temporal):
        return "non_temporal"
    if pd.notna(temporal_relation):
        return str(temporal_relation)
    return "missing_temporal_relation"


def difficulty_band(num_steps):
    if pd.isna(num_steps):
        return "missing_num_steps"

    num_steps = int(num_steps)

    if num_steps == 2:
        return "easy"
    if num_steps in [3, 4]:
        return "medium"
    if num_steps in [5, 6]:
        return "hard"
    return "expert"


def bucket_num_rows_contributing(x):
    if pd.isna(x):
        return "missing"
    x = int(x)

    if x == 0:
        return "0"
    if x == 1:
        return "1"
    if 2 <= x <= 5:
        return "2-5"
    if 6 <= x <= 10:
        return "6-10"
    if 11 <= x <= 20:
        return "11-20"
    if 21 <= x <= 50:
        return "21-50"
    if 51 <= x <= 100:
        return "51-100"
    if 101 <= x <= 200:
        return "101-200"
    return "201+"


def bucket_targeted_source_column_count(x):
    if pd.isna(x):
        return "missing"
    x = int(x)

    if x <= 1:
        return "1"
    if x == 2:
        return "2"
    if x == 3:
        return "3"
    if x == 4:
        return "4"
    if 5 <= x <= 6:
        return "5-6"
    return "7+"


def bucket_answer_cols(x):
    if pd.isna(x):
        return "missing"
    x = int(x)

    if x == 1:
        return "1"
    if x == 2:
        return "2"
    if x == 3:
        return "3"
    if x == 4:
        return "4"
    if 5 <= x <= 6:
        return "5-6"
    return "7+"


def bucket_answer_rows(x):
    if pd.isna(x):
        return "missing"
    x = int(x)

    if x == 0:
        return "0"
    if x == 1:
        return "1"
    if x == 2:
        return "2"
    if 3 <= x <= 5:
        return "3-5"
    if 6 <= x <= 10:
        return "6-10"
    if 11 <= x <= 20:
        return "11-20"
    return "21+"


def classify_entity_schema_grounding(variables):
    vars_ = as_list(variables)

    entity_set = {"batsman", "bowler"}
    entities = [v for v in vars_ if v in entity_set]
    has_table = "table_name" in vars_

    if len(entities) == 1:
        return "single-entity grounding"
    if len(entities) >= 2:
        return "multi-entity grounding"
    if has_table:
        return "schema-only grounding"
    return "no entity grounding"


def classify_context_scoping(span_bucket):
    if pd.isna(span_bucket):
        return "missing_span"
    if span_bucket == "entire":
        return "full-span reasoning"
    if span_bucket in {"first_half", "second_half"}:
        return "partial-span reasoning"
    return f"other-span:{span_bucket}"


def classify_temporal_reasoning(is_temporal, temporal_relation):
    relation = normalize_temporal_relation(is_temporal, temporal_relation)

    if relation == "non_temporal":
        return "non-temporal control"
    if relation in {"after", "after_or_at", "before", "before_or_at"}:
        return "point-based temporal filtering"
    if relation == "between":
        return "range-based temporal filtering"
    if relation == "overlaps":
        return "interval overlap reasoning"
    return f"other-temporal:{relation}"


def classify_sql_reasoning_fine(clauses):
    clauses = set(as_list(clauses))

    has_aggregate = "aggregate" in clauses
    has_group_by = "group_by" in clauses
    has_having = "having" in clauses
    has_order_by = "order_by" in clauses
    has_limit = "limit" in clauses
    has_case = "case" in clauses
    has_subquery = "subquery" in clauses
    has_distinct = "distinct" in clauses

    if clauses == {"select", "where"}:
        return "simple retrieval"

    if has_order_by and has_limit and not has_group_by and not has_having and not has_aggregate:
        return "top-k retrieval"

    if has_order_by and not has_group_by and not has_having and not has_aggregate:
        return "ordered retrieval"

    if has_aggregate and not has_group_by and not has_having:
        if has_case:
            return "conditional aggregation"
        if has_subquery:
            return "aggregation with subquery"
        return "filtered aggregation"

    if has_group_by and has_aggregate and not has_having:
        if has_case and has_subquery:
            return "conditional grouped aggregation with subquery"
        if has_case:
            return "conditional grouped aggregation"
        if has_distinct:
            return "distinct grouped aggregation"
        if has_order_by and has_limit:
            return "top-k grouped aggregation"
        if has_order_by:
            return "ordered grouped aggregation"
        return "grouped aggregation"

    if has_group_by and has_having:
        if has_order_by and has_limit and has_case:
            return "ranked conditional grouped comparison"
        if has_order_by and has_limit:
            return "ranked grouped comparison"
        if has_order_by and has_case:
            return "ordered conditional grouped comparison"
        if has_order_by:
            return "ordered grouped comparison"
        if has_case and has_subquery:
            return "conditional grouped comparison with subquery"
        if has_case:
            return "conditional grouped comparison"
        if has_subquery:
            return "grouped comparison with subquery"
        return "post-aggregation comparison"

    return "other retrieval"


def collapse_sql_reasoning(sql_reasoning_fine):
    mapping = {
        "simple retrieval": "Simple retrieval",
        "top-k retrieval": "Simple retrieval",
        "ordered retrieval": "Simple retrieval",
        "other retrieval": "Simple retrieval",
        "filtered aggregation": "Filtered aggregation",
        "conditional aggregation": "Filtered aggregation",
        "aggregation with subquery": "Filtered aggregation",
        "grouped aggregation": "Grouped aggregation",
        "conditional grouped aggregation": "Grouped aggregation",
        "conditional grouped aggregation with subquery": "Grouped aggregation",
        "distinct grouped aggregation": "Grouped aggregation",
        "ordered grouped aggregation": "Grouped aggregation",
        "top-k grouped aggregation": "Grouped aggregation",
        "post-aggregation comparison": "Group comparison",
        "ordered grouped comparison": "Group comparison",
        "ordered conditional grouped comparison": "Group comparison",
        "conditional grouped comparison": "Group comparison",
        "conditional grouped comparison with subquery": "Group comparison",
        "grouped comparison with subquery": "Group comparison",
        "ranked grouped comparison": "Group comparison",
        "ranked conditional grouped comparison": "Group comparison",
    }
    return mapping.get(sql_reasoning_fine, "Simple retrieval")


def classify_compositional_sql(num_steps):
    band = difficulty_band(num_steps)

    if band == "easy":
        return "2-step composition"
    if band == "medium":
        return "3-4 step composition"
    if band == "hard":
        return "5-6 step composition"
    if band == "expert":
        return "7+ step composition"
    return "missing_num_steps"


def bucket_contrib_fraction(x):
    if pd.isna(x):
        return "missing"
    x = float(x)

    if x <= 0.01:
        return "<=1%"
    if x <= 0.05:
        return "1-5%"
    if x <= 0.10:
        return "5-10%"
    if x <= 0.25:
        return "10-25%"
    if x <= 0.50:
        return "25-50%"
    if x <= 0.75:
        return "50-75%"
    return "75-100%"


def map_grounding_pressure(row):
    grounding = row["skill_entity_schema_grounding"]

    if grounding == "schema-only grounding":
        return "low"
    if grounding == "single-entity grounding":
        return "medium"
    if grounding == "multi-entity grounding":
        return "high"
    return "other"


def map_localization_pressure(row):
    temporal = row["skill_temporal_reasoning"]
    span = row["span_bucket"]

    frac = row.get("contrib_fraction", np.nan)
    if pd.notna(frac):
        sparse = frac <= 0.10
        moderate = (frac > 0.10) and (frac <= 0.25)
    else:
        bucket = row.get("num_rows_contributing_bucket", "missing")
        sparse = bucket in {"0", "1", "2-5", "6-10"}
        moderate = bucket in {"11-20", "21-50"}

    temporal_flag = temporal != "non-temporal control"
    partial_flag = span in {"first_half", "second_half"}

    score = 0
    if temporal_flag:
        score += 1
    if partial_flag:
        score += 1
    if moderate:
        score += 1
    if sparse:
        score += 2

    if score <= 1:
        return "low"
    if score <= 3:
        return "medium"
    return "high"


def map_execution_pressure(row):
    comp_map = {
        "2-step composition": 0,
        "3-4 step composition": 1,
        "5-6 step composition": 2,
        "7+ step composition": 3,
    }
    sql_map = {
        "Simple retrieval": 0,
        "Filtered aggregation": 1,
        "Grouped aggregation": 2,
        "Group comparison": 3,
    }

    total = sql_map.get(row["skill_sql_reasoning"], 1) + comp_map.get(row["skill_compositional_sql"], 1)
    if total <= 1:
        return "low"
    if total <= 3:
        return "medium"
    return "high"


def map_output_pressure(row):
    cols_bucket = row.get("answer_cols_bucket", "missing")
    rows_bucket = row.get("answer_rows_bucket", "missing")

    col_score_map = {
        "1": 0,
        "2": 1,
        "3": 1,
        "4": 2,
        "5-6": 2,
        "7+": 3,
        "missing": 1,
    }
    row_score_map = {
        "0": 0,
        "1": 0,
        "2": 1,
        "3-5": 1,
        "6-10": 2,
        "11-20": 3,
        "21+": 4,
        "missing": 1,
    }

    total = col_score_map.get(cols_bucket, 1) + row_score_map.get(rows_bucket, 1)
    if total <= 1:
        return "low"
    if total <= 3:
        return "medium"
    return "high"


def load_base_skill_df(dataset_path: Path = DATASET_PATH) -> pd.DataFrame:
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset_obj = json.load(f)

    raw_df = pd.json_normalize(dataset_obj["records"])
    skills_df = raw_df.copy()

    skills_df["sample_idx"] = pd.to_numeric(skills_df["sample_idx"], errors="coerce")
    skills_df["skill_entity_schema_grounding"] = skills_df["variables"].apply(classify_entity_schema_grounding)
    skills_df["skill_context_scoping"] = skills_df["span_bucket"].apply(classify_context_scoping)
    skills_df["skill_temporal_reasoning"] = skills_df.apply(
        lambda row: classify_temporal_reasoning(row["is_temporal"], row["temporal_relation"]),
        axis=1,
    )
    skills_df["skill_sql_reasoning_fine"] = skills_df["sql_difficulty.clauses"].apply(classify_sql_reasoning_fine)
    skills_df["skill_sql_reasoning"] = skills_df["skill_sql_reasoning_fine"].apply(collapse_sql_reasoning)
    skills_df["skill_compositional_sql"] = skills_df["step_row_progression.num_steps"].apply(classify_compositional_sql)
    skills_df["num_rows_contributing_bucket"] = skills_df["num_rows_contributing"].apply(bucket_num_rows_contributing)
    skills_df["targeted_source_column_count"] = skills_df["sql_projection_stats.targeted_source_column_count"]
    skills_df["targeted_source_column_count_bucket"] = skills_df["targeted_source_column_count"].apply(
        bucket_targeted_source_column_count
    )
    skills_df["answer_cols_bucket"] = skills_df["answer_cols"].apply(bucket_answer_cols)
    skills_df["answer_rows_bucket"] = skills_df["answer_rows"].apply(bucket_answer_rows)

    paper_cols = [
        "sample_idx",
        "idx",
        "match_idx",
        "primary_key",
        "question",
        "span_bucket",
        "num_rows_contributing",
        "num_rows_scanned",
        "num_rows_contributing_bucket",
        "targeted_source_column_count",
        "targeted_source_column_count_bucket",
        "answer_cols",
        "answer_rows",
        "answer_cols_bucket",
        "answer_rows_bucket",
        "skill_entity_schema_grounding",
        "skill_context_scoping",
        "skill_temporal_reasoning",
        "skill_sql_reasoning",
        "skill_compositional_sql",
    ]

    return skills_df[paper_cols].copy()


def load_results_jsonl(path: Path, model_name: str) -> pd.DataFrame:
    rows = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)

            attempts = obj.get("attempts", [])
            chosen_attempt = obj.get("chosen_attempt")

            input_tokens = None
            output_tokens = None
            total_tokens = None

            if isinstance(chosen_attempt, int) and 0 <= chosen_attempt < len(attempts):
                usage = attempts[chosen_attempt].get("usage", {})
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")

            pk = obj.get("pk_metrics") or {}
            cell = obj.get("pk_cell_metrics") or {}
            numeric = obj.get("numeric_metrics") or {}
            numeric_macro = numeric.get("macro") or {}
            table_match = obj.get("table_match") or {}

            rows.append(
                {
                    "model": model_name,
                    "sample_id": pd.to_numeric(obj.get("sample_id"), errors="coerce"),
                    "record_id": obj.get("record_id"),
                    "question_from_results": obj.get("question"),
                    "has_pred_table": isinstance(obj.get("pred_table"), dict)
                    and isinstance(obj.get("gold_table"), dict),
                    "missing_pred": bool(obj.get("missing_pred", False)),
                    "exact_match": bool(table_match.get("exact_match")) if table_match else False,
                    "row_match": bool(table_match.get("row_match")) if table_match else False,
                    "col_match": bool(table_match.get("col_match")) if table_match else False,
                    "content_match": bool(table_match.get("content_match")) if table_match else False,
                    "pk_present": pk.get("pk_present"),
                    "pk_eval_skipped": pk.get("pk_eval_skipped"),
                    "pk_precision": pk.get("pk_precision"),
                    "pk_recall": pk.get("pk_recall"),
                    "pk_f1": pk.get("pk_f1"),
                    "pk_exact_set_match": pk.get("pk_exact_set_match"),
                    "matched_pk_n": pk.get("matched_pk_n"),
                    "gold_pk_count": pk.get("gold_pk_count"),
                    "pred_pk_count": pk.get("pred_pk_count"),
                    "cell_acc": cell.get("cell_acc"),
                    "correct_cells": cell.get("correct_cells"),
                    "total_cells": cell.get("total_cells"),
                    "pk_cell_eval_skipped": cell.get("pk_cell_eval_skipped"),
                    "weighted_mae": numeric_macro.get("weighted_mae"),
                    "weighted_rmse": numeric_macro.get("weighted_rmse"),
                    "total_numeric_pairs": numeric_macro.get("total_numeric_pairs"),
                    "numeric_eval_skipped": numeric.get("numeric_eval_skipped"),
                    "overcount_pct": obj.get("Overcount%"),
                    "undercount_pct": obj.get("Undercount%"),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                }
            )

    df = pd.DataFrame(rows)
    df["exact_match_num"] = 100 * df["exact_match"].astype(float)
    df["row_match_num"] = 100 * df["row_match"].astype(float)
    df["col_match_num"] = 100 * df["col_match"].astype(float)
    df["content_match_num"] = 100 * df["content_match"].astype(float)
    df["pk_f1_x100"] = 100 * df["pk_f1"]
    df["pk_recall_x100"] = 100 * df["pk_recall"]
    df["pk_precision_x100"] = 100 * df["pk_precision"]
    df["pk_exact_set_match_num"] = 100 * df["pk_exact_set_match"].astype(float)
    df["cell_acc_num"] = df["cell_acc"]
    df["net_over_under_pct"] = df["overcount_pct"] - df["undercount_pct"]
    df["has_pk_eval"] = df["pk_f1"].notna() & ~df["pk_eval_skipped"].astype("boolean").fillna(True)
    df["has_numeric_eval"] = df["weighted_rmse"].notna() & ~df["numeric_eval_skipped"].astype("boolean").fillna(True)
    return df


def add_pressure_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["contrib_fraction"] = np.where(
        out["num_rows_scanned"].fillna(0) > 0,
        out["num_rows_contributing"] / out["num_rows_scanned"],
        np.nan,
    )
    out["contrib_fraction_bucket"] = out["contrib_fraction"].apply(bucket_contrib_fraction)
    out["grounding_pressure"] = out.apply(map_grounding_pressure, axis=1)
    out["localization_pressure"] = out.apply(map_localization_pressure, axis=1)
    out["execution_pressure"] = out.apply(map_execution_pressure, axis=1)
    out["output_pressure"] = out.apply(map_output_pressure, axis=1)

    out["pressure_profile"] = out.apply(
        lambda row: " | ".join(
            [
                f"G={row['grounding_pressure']}",
                f"L={row['localization_pressure']}",
                f"E={row['execution_pressure']}",
                f"O={row['output_pressure']}",
            ]
        ),
        axis=1,
    )
    return out


def build_analysis_df() -> pd.DataFrame:
    skill_df = load_base_skill_df()
    results_df = pd.concat(
        [load_results_jsonl(path, model_name) for model_name, path in MODEL_PATHS.items()],
        ignore_index=True,
    )
    analysis_df = skill_df.merge(
        results_df,
        left_on="sample_idx",
        right_on="sample_id",
        how="inner",
        validate="one_to_many",
    )
    return add_pressure_columns(analysis_df)


def paired_ids_for_metric(df: pd.DataFrame, metric_col: str) -> pd.Index:
    wide = df.pivot_table(index="sample_idx", columns="model", values=metric_col)
    available_models = [m for m in MODEL_ORDER if m in wide.columns]
    if len(available_models) != 2:
        return pd.Index([])
    return wide[available_models].dropna().index


def paired_ids_for_boolean(df: pd.DataFrame, bool_col: str) -> pd.Index:
    wide = (
        df.pivot_table(index="sample_idx", columns="model", values=bool_col, aggfunc="max")
        .fillna(False)
        .astype(bool)
    )
    available_models = [m for m in MODEL_ORDER if m in wide.columns]
    if len(available_models) != 2:
        return pd.Index([])
    return wide.index[wide[available_models[0]] & wide[available_models[1]]]


def bootstrap_ci(values, n_boot=10000, alpha=0.05, seed=42):
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]

    if len(values) == 0:
        return np.nan, np.nan

    rng = np.random.default_rng(seed)
    boot_means = []

    for _ in range(n_boot):
        sample = rng.choice(values, size=len(values), replace=True)
        boot_means.append(sample.mean())

    lo = np.percentile(boot_means, 100 * (alpha / 2))
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return lo, hi


def weighted_bootstrap_ci(deltas, weights, n_boot=10000, alpha=0.05, seed=42):
    deltas = np.asarray(deltas, dtype=float)
    weights = np.asarray(weights, dtype=float)

    mask = (~np.isnan(deltas)) & (~np.isnan(weights)) & (weights > 0)
    deltas = deltas[mask]
    weights = weights[mask]

    if len(deltas) == 0:
        return np.nan, np.nan

    rng = np.random.default_rng(seed)
    boot_means = []

    for _ in range(n_boot):
        idx = rng.choice(np.arange(len(deltas)), size=len(deltas), replace=True)
        boot_means.append(np.average(deltas[idx], weights=weights[idx]))

    lo = np.percentile(boot_means, 100 * (alpha / 2))
    hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return lo, hi


def significance_label(ci_low, ci_high):
    if pd.isna(ci_low) or pd.isna(ci_high):
        return "NA"
    return "significant" if (ci_low > 0 or ci_high < 0) else "not significant"


def paired_sign_flip_permutation_pvalue(deltas, n_perm=5000, seed=42):
    deltas = np.asarray(deltas, dtype=float)
    deltas = deltas[~np.isnan(deltas)]
    if len(deltas) == 0:
        return np.nan

    observed = abs(deltas.mean())
    rng = np.random.default_rng(seed)
    p_more_extreme = 0

    for _ in range(n_perm):
        signs = rng.choice(np.array([-1.0, 1.0]), size=len(deltas), replace=True)
        perm_mean = abs((signs * deltas).mean())
        if perm_mean >= observed:
            p_more_extreme += 1

    return float((p_more_extreme + 1) / (n_perm + 1))


def paired_model_delta_table(df: pd.DataFrame, metric_col: str, metric_label: str, higher_is_better: bool) -> pd.DataFrame:
    wide = df.pivot_table(index="sample_idx", columns="model", values=metric_col).dropna().reset_index()
    available_models = [m for m in MODEL_ORDER if m in wide.columns]
    if len(available_models) != 2:
        raise ValueError(f"Expected exactly two models in wide table, found: {available_models}")

    model_a, model_b = available_models
    delta = wide[model_b] - wide[model_a]
    ci_low, ci_high = bootstrap_ci(delta.values)

    try:
        wilcoxon_p = wilcoxon(delta.values).pvalue
    except ValueError:
        wilcoxon_p = np.nan

    favored = model_b if (delta.mean() > 0 and higher_is_better) or (delta.mean() < 0 and not higher_is_better) else model_a

    return pd.DataFrame(
        [
            {
                "metric": metric_col,
                "metric_label": metric_label,
                "model_a": model_a,
                "model_b": model_b,
                "n_pairs": len(wide),
                "mean_a": wide[model_a].mean(),
                "mean_b": wide[model_b].mean(),
                "mean_delta_b_minus_a": delta.mean(),
                "median_delta_b_minus_a": delta.median(),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "wilcoxon_pvalue": wilcoxon_p,
                "permutation_pvalue": paired_sign_flip_permutation_pvalue(delta.values),
                "higher_is_better": higher_is_better,
                "favored_model": favored,
            }
        ]
    )


def factor_level_summary(df, factor_col, metric_col):
    return (
        df.groupby(factor_col, dropna=False)
        .agg(
            n=("sample_idx", "size"),
            mean_metric=(metric_col, "mean"),
            median_metric=(metric_col, "median"),
            std_metric=(metric_col, "std"),
        )
        .reset_index()
        .sort_values("n", ascending=False)
        .reset_index(drop=True)
    )


def controlled_pivot(df, factor_col, control_cols, metric_col):
    grouped = (
        df.groupby(control_cols + [factor_col], dropna=False)
        .agg(metric=(metric_col, "mean"))
        .reset_index()
    )

    return (
        grouped.pivot_table(
            index=control_cols,
            columns=factor_col,
            values="metric",
        )
        .reset_index()
    )


def paired_comparison_table(pairs, comparisons):
    rows = []

    for a, b in comparisons:
        if a not in pairs.columns or b not in pairs.columns:
            continue

        tmp = pairs[[a, b]].dropna().copy()
        if len(tmp) == 0:
            continue

        tmp["delta"] = tmp[a] - tmp[b]
        ci_low, ci_high = bootstrap_ci(tmp["delta"].values)

        try:
            wilcoxon_p = wilcoxon(tmp["delta"]).pvalue
        except ValueError:
            wilcoxon_p = np.nan

        try:
            paired_t_p = ttest_rel(tmp[a], tmp[b], nan_policy="omit").pvalue
        except Exception:
            paired_t_p = np.nan

        n_pos = int((tmp["delta"] > 0).sum())
        n_nonzero = int((tmp["delta"] != 0).sum())
        sign_p = binomtest(n_pos, n_nonzero, p=0.5).pvalue if n_nonzero > 0 else np.nan

        rows.append(
            {
                "comparison": f"{a} vs {b}",
                "n_pairs": len(tmp),
                "mean_delta": tmp["delta"].mean(),
                "median_delta": tmp["delta"].median(),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "prop_first_higher": (tmp["delta"] > 0).mean(),
                "prop_equal": (tmp["delta"] == 0).mean(),
                "paired_t_pvalue": paired_t_p,
                "wilcoxon_pvalue": wilcoxon_p,
                "sign_test_pvalue": sign_p,
                "significance": significance_label(ci_low, ci_high),
            }
        )

    return pd.DataFrame(rows)


def run_paired_factor_analysis(df, factor_col, control_cols, pairwise_comparisons, metric_col):
    pairs = controlled_pivot(
        df=df,
        factor_col=factor_col,
        control_cols=control_cols,
        metric_col=metric_col,
    )

    comparisons = paired_comparison_table(
        pairs=pairs,
        comparisons=pairwise_comparisons,
    )

    level_summary = factor_level_summary(df, factor_col, metric_col=metric_col)

    return {
        "analysis_type": "paired",
        "pairs": pairs,
        "level_summary": level_summary,
        "comparisons": comparisons,
    }


def stratified_comparison_table(df, factor_col, strata_cols, pairwise_comparisons, metric_col):
    rows = []

    for a, b in pairwise_comparisons:
        sub = df[df[factor_col].isin([a, b])].copy()
        if sub.empty:
            continue

        grouped = (
            sub.groupby(strata_cols + [factor_col], dropna=False)
            .agg(
                mean_metric=(metric_col, "mean"),
                n=("sample_idx", "size"),
            )
            .reset_index()
        )

        wide_mean = grouped.pivot_table(index=strata_cols, columns=factor_col, values="mean_metric").reset_index()
        wide_n = grouped.pivot_table(index=strata_cols, columns=factor_col, values="n").reset_index()

        if a not in wide_mean.columns or b not in wide_mean.columns:
            continue

        merged = wide_mean.merge(wide_n, on=strata_cols, suffixes=("_mean", "_n"))
        a_mean = f"{a}_mean"
        b_mean = f"{b}_mean"
        a_n = f"{a}_n"
        b_n = f"{b}_n"

        if a_mean not in merged.columns or b_mean not in merged.columns:
            continue

        tmp = merged[[a_mean, b_mean, a_n, b_n]].dropna().copy()
        if len(tmp) == 0:
            continue

        tmp["delta"] = tmp[a_mean] - tmp[b_mean]
        tmp["weight"] = np.minimum(tmp[a_n], tmp[b_n])

        ci_low, ci_high = weighted_bootstrap_ci(
            deltas=tmp["delta"].values,
            weights=tmp["weight"].values,
        )

        try:
            wilcoxon_p = wilcoxon(tmp["delta"]).pvalue
        except ValueError:
            wilcoxon_p = np.nan

        rows.append(
            {
                "comparison": f"{a} vs {b}",
                "n_strata": len(tmp),
                "weighted_mean_delta": np.average(tmp["delta"], weights=tmp["weight"]),
                "median_stratum_delta": tmp["delta"].median(),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "wilcoxon_pvalue": wilcoxon_p,
                "significance": significance_label(ci_low, ci_high),
            }
        )

    return pd.DataFrame(rows)


def run_stratified_factor_analysis(df, factor_col, strata_cols, pairwise_comparisons, metric_col):
    comparisons = stratified_comparison_table(
        df=df,
        factor_col=factor_col,
        strata_cols=strata_cols,
        pairwise_comparisons=pairwise_comparisons,
        metric_col=metric_col,
    )

    level_summary = factor_level_summary(df, factor_col, metric_col=metric_col)

    return {
        "analysis_type": "stratified",
        "level_summary": level_summary,
        "comparisons": comparisons,
    }


PAIRED_COMMON_CONTROLS = [
    "idx",
    "match_idx",
    "num_rows_contributing_bucket",
    "targeted_source_column_count_bucket",
    "answer_cols_bucket",
]

STRATIFIED_COMMON_CONTROLS = [
    "span_bucket",
    "skill_temporal_reasoning",
    "num_rows_contributing_bucket",
    "targeted_source_column_count_bucket",
    "answer_cols_bucket",
]

ANALYSIS_SPECS = {
    "span_bucket": {
        "analysis_type": "paired",
        "control_cols": PAIRED_COMMON_CONTROLS
        + [
            "skill_entity_schema_grounding",
            "skill_temporal_reasoning",
            "skill_sql_reasoning",
            "skill_compositional_sql",
        ],
        "pairwise_comparisons": [
            ("first_half", "entire"),
            ("second_half", "entire"),
            ("second_half", "first_half"),
        ],
    },
    "skill_temporal_reasoning": {
        "analysis_type": "paired",
        "control_cols": PAIRED_COMMON_CONTROLS
        + [
            "span_bucket",
            "skill_entity_schema_grounding",
            "skill_sql_reasoning",
            "skill_compositional_sql",
        ],
        "pairwise_comparisons": [
            ("point-based temporal filtering", "non-temporal control"),
            ("range-based temporal filtering", "non-temporal control"),
            ("interval overlap reasoning", "non-temporal control"),
            ("range-based temporal filtering", "point-based temporal filtering"),
            ("interval overlap reasoning", "point-based temporal filtering"),
            ("interval overlap reasoning", "range-based temporal filtering"),
        ],
    },
    "skill_entity_schema_grounding": {
        "analysis_type": "stratified",
        "strata_cols": STRATIFIED_COMMON_CONTROLS + ["skill_sql_reasoning", "skill_compositional_sql"],
        "pairwise_comparisons": [
            ("single-entity grounding", "schema-only grounding"),
            ("multi-entity grounding", "schema-only grounding"),
            ("multi-entity grounding", "single-entity grounding"),
        ],
    },
    "skill_sql_reasoning": {
        "analysis_type": "stratified",
        "strata_cols": STRATIFIED_COMMON_CONTROLS + ["skill_entity_schema_grounding", "skill_compositional_sql"],
        "pairwise_comparisons": [
            ("Filtered aggregation", "Simple retrieval"),
            ("Grouped aggregation", "Simple retrieval"),
            ("Group comparison", "Simple retrieval"),
            ("Grouped aggregation", "Filtered aggregation"),
            ("Group comparison", "Filtered aggregation"),
            ("Group comparison", "Grouped aggregation"),
        ],
    },
    "skill_compositional_sql": {
        "analysis_type": "stratified",
        "strata_cols": STRATIFIED_COMMON_CONTROLS + ["skill_entity_schema_grounding", "skill_sql_reasoning"],
        "pairwise_comparisons": [
            ("3-4 step composition", "2-step composition"),
            ("5-6 step composition", "2-step composition"),
            ("7+ step composition", "2-step composition"),
            ("5-6 step composition", "3-4 step composition"),
            ("7+ step composition", "3-4 step composition"),
            ("7+ step composition", "5-6 step composition"),
        ],
    },
}


def run_factor_suite(df: pd.DataFrame, metric_col: str, domain_name: str):
    all_factor_results = {}

    for model_name, model_df in df.groupby("model"):
        model_results = {}

        for factor_col, spec in ANALYSIS_SPECS.items():
            if spec["analysis_type"] == "paired":
                result = run_paired_factor_analysis(
                    df=model_df,
                    factor_col=factor_col,
                    control_cols=spec["control_cols"],
                    pairwise_comparisons=spec["pairwise_comparisons"],
                    metric_col=metric_col,
                )

                if result["comparisons"].empty:
                    fallback_strata = [c for c in spec["control_cols"] if c not in ["idx", "match_idx"]]
                    result = run_stratified_factor_analysis(
                        df=model_df,
                        factor_col=factor_col,
                        strata_cols=fallback_strata,
                        pairwise_comparisons=spec["pairwise_comparisons"],
                        metric_col=metric_col,
                    )
                    result["analysis_type"] = "stratified_fallback"
            else:
                result = run_stratified_factor_analysis(
                    df=model_df,
                    factor_col=factor_col,
                    strata_cols=spec["strata_cols"],
                    pairwise_comparisons=spec["pairwise_comparisons"],
                    metric_col=metric_col,
                )

            model_results[factor_col] = result

        all_factor_results[model_name] = model_results

    factor_level_tables = []
    factor_comparison_tables = []

    for model_name, model_results in all_factor_results.items():
        for factor_col, result in model_results.items():
            level_df = result["level_summary"].copy()
            level_df.insert(0, "domain", domain_name)
            level_df.insert(1, "model", model_name)
            level_df.insert(2, "factor", factor_col)
            level_df.insert(3, "factor_pretty", FACTOR_LABELS.get(factor_col, factor_col))
            level_df.insert(4, "analysis_type", result["analysis_type"])
            factor_level_tables.append(level_df)

            comp_df = result["comparisons"].copy()
            comp_df.insert(0, "domain", domain_name)
            comp_df.insert(1, "model", model_name)
            comp_df.insert(2, "factor", factor_col)
            comp_df.insert(3, "factor_pretty", FACTOR_LABELS.get(factor_col, factor_col))
            comp_df.insert(4, "analysis_type", result["analysis_type"])
            factor_comparison_tables.append(comp_df)

    return (
        pd.concat(factor_level_tables, ignore_index=True),
        pd.concat(factor_comparison_tables, ignore_index=True),
    )


def pooled_permutation_pvalue(x, y, n_perm=5000, seed=42):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    observed = abs(x.mean() - y.mean())
    combined = np.concatenate([x, y])
    n_x = len(x)
    rng = np.random.default_rng(seed)
    perm_stats = np.empty(n_perm, dtype=float)

    for i in range(n_perm):
        perm = rng.permutation(combined)
        perm_stats[i] = abs(perm[:n_x].mean() - perm[n_x:].mean())

    return float((np.sum(perm_stats >= observed) + 1) / (n_perm + 1))


def pooled_pairwise(df, factor, a, b, metric_col):
    x = df[df[factor] == a][metric_col].dropna().astype(float).to_numpy()
    y = df[df[factor] == b][metric_col].dropna().astype(float).to_numpy()

    if len(x) == 0 or len(y) == 0:
        return None

    rng = np.random.default_rng(42)
    boot = []
    for _ in range(10000):
        xs = rng.choice(x, size=len(x), replace=True)
        ys = rng.choice(y, size=len(y), replace=True)
        boot.append(xs.mean() - ys.mean())

    ci_low = np.percentile(boot, 2.5)
    ci_high = np.percentile(boot, 97.5)

    try:
        mannwhitney_p = mannwhitneyu(x, y, alternative="two-sided").pvalue
    except ValueError:
        mannwhitney_p = np.nan

    return {
        "comparison": f"{a} vs {b}",
        "n_first": len(x),
        "n_second": len(y),
        "mean_first": x.mean(),
        "mean_second": y.mean(),
        "mean_delta": x.mean() - y.mean(),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "mannwhitney_pvalue": mannwhitney_p,
        "permutation_pvalue": pooled_permutation_pvalue(x, y),
        "significance": significance_label(ci_low, ci_high),
    }


def run_pooled_pressure_suite(df: pd.DataFrame, metric_col: str, domain_name: str):
    pooled_summary_rows = []
    pooled_pairwise_rows = []

    for model_name, model_df in df.groupby("model"):
        for factor in PRESSURE_COLS:
            summary = (
                model_df.groupby(factor, dropna=False)[metric_col]
                .agg(["size", "mean", "median", "std"])
                .reset_index()
                .rename(
                    columns={
                        factor: "pressure_level",
                        "size": "n",
                        "mean": "mean_metric",
                        "median": "median_metric",
                        "std": "std_metric",
                    }
                )
            )
            summary.insert(0, "domain", domain_name)
            summary.insert(1, "model", model_name)
            summary.insert(2, "pressure_axis", factor)
            pooled_summary_rows.append(summary)

            for a, b in [("medium", "low"), ("high", "low"), ("high", "medium")]:
                row = pooled_pairwise(model_df, factor, a, b, metric_col)
                if row is not None:
                    row["domain"] = domain_name
                    row["model"] = model_name
                    row["pressure_axis"] = factor
                    pooled_pairwise_rows.append(row)

    paper_pooled_pressure_df = pd.concat(pooled_summary_rows, ignore_index=True)
    paper_pooled_pairwise_df = pd.DataFrame(pooled_pairwise_rows)

    model_delta_by_pressure_rows = []
    for factor in PRESSURE_COLS:
        for level in LEVEL_ORDER:
            sub = df[df[factor] == level]
            wide = sub.pivot_table(index="sample_idx", columns="model", values=metric_col).dropna().reset_index()
            if len(wide) == 0:
                continue

            model_names = [m for m in MODEL_ORDER if m in wide.columns]
            if len(model_names) != 2:
                continue

            model_a, model_b = model_names
            delta = wide[model_b] - wide[model_a]
            ci_low, ci_high = bootstrap_ci(delta.values)

            try:
                wilcoxon_p = wilcoxon(delta.values).pvalue
            except ValueError:
                wilcoxon_p = np.nan

            model_delta_by_pressure_rows.append(
                {
                    "domain": domain_name,
                    "pressure_axis": factor,
                    "pressure_level": level,
                    "model_a": model_a,
                    "model_b": model_b,
                    "n_pairs": len(wide),
                    "mean_delta_b_minus_a": delta.mean(),
                    "median_delta_b_minus_a": delta.median(),
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "wilcoxon_pvalue": wilcoxon_p,
                }
            )

    return (
        paper_pooled_pressure_df,
        paper_pooled_pairwise_df,
        pd.DataFrame(model_delta_by_pressure_rows),
    )


def stratified_bootstrap_ci(values, n_boot=10000, alpha=0.05, seed=42):
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan, np.nan

    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        sample = rng.choice(values, size=len(values), replace=True)
        boots.append(sample.mean())

    return (
        np.percentile(boots, 100 * (alpha / 2)),
        np.percentile(boots, 100 * (1 - alpha / 2)),
    )


def sign_flip_permutation_pvalue(deltas, n_perm=5000, seed=42):
    deltas = np.asarray(deltas, dtype=float)
    deltas = deltas[~np.isnan(deltas)]
    if len(deltas) == 0:
        return np.nan

    observed = abs(deltas.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_perm, len(deltas)), replace=True)
    perm_means = np.abs((signs * deltas).mean(axis=1))
    return float((np.sum(perm_means >= observed) + 1) / (n_perm + 1))


def matched_pairwise_table(df, factor, control_cols, metric_col):
    grouped = (
        df.groupby(control_cols + [factor], dropna=False)
        .agg(n=("sample_idx", "size"), mean_metric=(metric_col, "mean"))
        .reset_index()
    )

    strata_support = (
        grouped.groupby(control_cols, dropna=False)
        .agg(
            n_levels=(factor, lambda s: s.nunique(dropna=False)),
            total_samples=("n", "sum"),
        )
        .reset_index()
    )

    matched_only = strata_support[strata_support["n_levels"] >= 2].copy()
    if len(matched_only) == 0:
        return pd.DataFrame(), matched_only

    matched_keyed = grouped.merge(matched_only[control_cols], on=control_cols, how="inner")
    wide = matched_keyed.pivot_table(index=control_cols, columns=factor, values="mean_metric").reset_index()

    rows = []
    for a, b in [("medium", "low"), ("high", "low"), ("high", "medium")]:
        if a not in wide.columns or b not in wide.columns:
            continue

        tmp = wide[[a, b]].dropna().copy()
        if len(tmp) == 0:
            continue

        tmp["delta"] = tmp[a] - tmp[b]
        ci_low, ci_high = stratified_bootstrap_ci(tmp["delta"].values)
        perm_p = sign_flip_permutation_pvalue(tmp["delta"].values)

        try:
            t_p = ttest_rel(tmp[a], tmp[b], nan_policy="omit").pvalue
        except Exception:
            t_p = np.nan

        try:
            w_p = wilcoxon(tmp["delta"]).pvalue
        except ValueError:
            w_p = np.nan

        n_pos = int((tmp["delta"] > 0).sum())
        n_nonzero = int((tmp["delta"] != 0).sum())
        sign_p = binomtest(n_pos, n_nonzero, p=0.5).pvalue if n_nonzero > 0 else np.nan

        rows.append(
            {
                "comparison": f"{a} vs {b}",
                "n_matched_strata": len(tmp),
                "mean_delta": tmp["delta"].mean(),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "paired_t_pvalue": t_p,
                "wilcoxon_pvalue": w_p,
                "sign_test_pvalue": sign_p,
                "permutation_pvalue": perm_p,
                "significance": significance_label(ci_low, ci_high),
            }
        )

    return pd.DataFrame(rows), matched_only


STRATIFIED_PRESSURE_SPECS = {
    "grounding_pressure": [
        "localization_pressure",
        "execution_pressure",
        "output_pressure",
        "span_bucket",
        "num_rows_contributing_bucket",
        "targeted_source_column_count_bucket",
        "answer_cols_bucket",
    ],
    "localization_pressure": [
        "grounding_pressure",
        "execution_pressure",
        "output_pressure",
        "span_bucket",
        "num_rows_contributing_bucket",
        "targeted_source_column_count_bucket",
        "answer_cols_bucket",
    ],
    "execution_pressure": [
        "grounding_pressure",
        "localization_pressure",
        "output_pressure",
        "span_bucket",
        "num_rows_contributing_bucket",
        "targeted_source_column_count_bucket",
        "answer_cols_bucket",
    ],
    "output_pressure": [
        "grounding_pressure",
        "localization_pressure",
        "execution_pressure",
        "span_bucket",
        "num_rows_contributing_bucket",
        "targeted_source_column_count_bucket",
        "answer_cols_bucket",
    ],
}


def run_stratified_pressure_suite(df: pd.DataFrame, metric_col: str, domain_name: str):
    stratified_outer_rows = []
    stratified_pair_rows = []

    for model_name, model_df in df.groupby("model"):
        for factor, controls in STRATIFIED_PRESSURE_SPECS.items():
            control_cols = [c for c in controls if c in model_df.columns]
            pair_df, matched_only = matched_pairwise_table(
                model_df,
                factor=factor,
                control_cols=control_cols,
                metric_col=metric_col,
            )

            counts = model_df[factor].value_counts().to_dict()
            stratified_outer_rows.append(
                {
                    "domain": domain_name,
                    "model": model_name,
                    "pressure_axis": factor,
                    "n_low": counts.get("low", 0),
                    "n_medium": counts.get("medium", 0),
                    "n_high": counts.get("high", 0),
                    "matched_strata_n": len(matched_only),
                    "mean_matched_stratum_size": matched_only["total_samples"].mean() if len(matched_only) else np.nan,
                    "median_matched_stratum_size": matched_only["total_samples"].median() if len(matched_only) else np.nan,
                }
            )

            if len(pair_df):
                pair_df = pair_df.copy()
                pair_df.insert(0, "domain", domain_name)
                pair_df.insert(1, "model", model_name)
                pair_df.insert(2, "pressure_axis", factor)
                stratified_pair_rows.append(pair_df)

    return (
        pd.DataFrame(stratified_outer_rows),
        pd.concat(stratified_pair_rows, ignore_index=True) if stratified_pair_rows else pd.DataFrame(),
    )


def numeric_bias_tables(df: pd.DataFrame):
    bias_metrics = {
        "weighted_rmse": "mean_weighted_rmse",
        "overcount_pct": "mean_overcount_pct",
        "undercount_pct": "mean_undercount_pct",
        "net_over_under_pct": "mean_net_over_under_pct",
    }

    factor_rows = []
    for factor_col, factor_label in FACTOR_LABELS.items():
        grouped = (
            df.groupby(["model", factor_col], dropna=False)
            .agg(
                n=("sample_idx", "size"),
                **{new_name: (old_name, "mean") for old_name, new_name in bias_metrics.items()},
            )
            .reset_index()
            .rename(columns={factor_col: "level"})
        )
        grouped.insert(0, "group_family", "factor")
        grouped.insert(1, "group_col", factor_col)
        grouped.insert(2, "group_label", factor_label)
        factor_rows.append(grouped)

    pressure_rows = []
    for pressure_col in PRESSURE_COLS:
        grouped = (
            df.groupby(["model", pressure_col], dropna=False)
            .agg(
                n=("sample_idx", "size"),
                **{new_name: (old_name, "mean") for old_name, new_name in bias_metrics.items()},
            )
            .reset_index()
            .rename(columns={pressure_col: "level"})
        )
        grouped.insert(0, "group_family", "pressure")
        grouped.insert(1, "group_col", pressure_col)
        grouped.insert(2, "group_label", PRESSURE_LABELS[pressure_col])
        pressure_rows.append(grouped)

    return (
        pd.concat(factor_rows, ignore_index=True),
        pd.concat(pressure_rows, ignore_index=True),
    )


def build_coverage_tables(df: pd.DataFrame):
    coverage_by_model_df = (
        df.groupby("model")
        .agg(
            total_samples=("sample_idx", "size"),
            parsed_pred_table_n=("has_pred_table", "sum"),
            invalid_pred_table_n=("has_pred_table", lambda s: (~s.astype(bool)).sum()),
            missing_pred_n=("missing_pred", "sum"),
            pk_evaluable_n=("has_pk_eval", "sum"),
            numeric_evaluable_n=("has_numeric_eval", "sum"),
        )
        .reset_index()
    )

    coverage_overview_df = pd.DataFrame(
        [
            {"subset": "paired_sample_ids", "n_samples": int(df["sample_idx"].nunique())},
            {"subset": "both_parsed_pred_table", "n_samples": int(len(paired_ids_for_boolean(df, "has_pred_table")))},
            {"subset": "both_pk_evaluable", "n_samples": int(len(paired_ids_for_metric(df, "pk_f1_x100")))},
            {"subset": "both_numeric_evaluable", "n_samples": int(len(paired_ids_for_metric(df, "weighted_rmse")))},
        ]
    )
    return coverage_by_model_df, coverage_overview_df


def run_domain(df: pd.DataFrame, domain_name: str, metric_col: str, metric_specs):
    headline_df = pd.concat(
        [
            paired_model_delta_table(df, metric_col=name, metric_label=label, higher_is_better=higher_is_better)
            for name, label, higher_is_better in metric_specs
        ],
        ignore_index=True,
    )
    factor_levels_df, factor_comparisons_df = run_factor_suite(df, metric_col=metric_col, domain_name=domain_name)
    pooled_pressure_df, pooled_pairwise_df, model_delta_by_pressure_df = run_pooled_pressure_suite(
        df,
        metric_col=metric_col,
        domain_name=domain_name,
    )
    stratified_outer_df, stratified_pairwise_df = run_stratified_pressure_suite(
        df,
        metric_col=metric_col,
        domain_name=domain_name,
    )

    return {
        f"{domain_name}_headline_df": headline_df,
        f"{domain_name}_factor_levels_df": factor_levels_df,
        f"{domain_name}_factor_comparisons_df": factor_comparisons_df,
        f"{domain_name}_pooled_pressure_df": pooled_pressure_df,
        f"{domain_name}_pooled_pairwise_df": pooled_pairwise_df,
        f"{domain_name}_model_delta_by_pressure_df": model_delta_by_pressure_df,
        f"{domain_name}_stratified_outer_df": stratified_outer_df,
        f"{domain_name}_stratified_pairwise_df": stratified_pairwise_df,
    }


def run_full_analysis(export_dir: Path | None = DEFAULT_EXPORT_DIR):
    analysis_df = build_analysis_df()

    coverage_by_model_df, coverage_overview_df = build_coverage_tables(analysis_df)
    event_ids = paired_ids_for_metric(analysis_df, "pk_f1_x100")
    numeric_ids = paired_ids_for_metric(analysis_df, "weighted_rmse")

    event_df = analysis_df[analysis_df["sample_idx"].isin(event_ids)].copy()
    numeric_df = analysis_df[analysis_df["sample_idx"].isin(numeric_ids)].copy()

    outputs = {
        "coverage_by_model_df": coverage_by_model_df,
        "coverage_overview_df": coverage_overview_df,
        "event_analysis_df": event_df,
        "numeric_analysis_df": numeric_df,
    }
    outputs.update(run_domain(event_df, "event", "pk_f1_x100", EVENT_METRICS))
    outputs.update(run_domain(numeric_df, "numeric", "weighted_rmse", NUMERIC_METRICS))

    numeric_bias_by_factor_df, numeric_bias_by_pressure_df = numeric_bias_tables(numeric_df)
    outputs["numeric_bias_by_factor_df"] = numeric_bias_by_factor_df
    outputs["numeric_bias_by_pressure_df"] = numeric_bias_by_pressure_df

    if export_dir is not None:
        export_dir.mkdir(parents=True, exist_ok=True)
        for name, df in outputs.items():
            if isinstance(df, pd.DataFrame):
                df.to_csv(export_dir / f"{name}.csv", index=False)

    return outputs


def main():
    outputs = run_full_analysis()
    print("Wrote analysis tables to", DEFAULT_EXPORT_DIR)
    print("Coverage overview:")
    print(outputs["coverage_overview_df"].to_string(index=False))


if __name__ == "__main__":
    main()
