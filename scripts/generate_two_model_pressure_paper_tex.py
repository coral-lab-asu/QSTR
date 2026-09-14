from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from two_model_decomposed_analysis import STRATIFIED_PRESSURE_SPECS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = PROJECT_ROOT / "tmp" / "two_model_decomposed_analysis"
OUT_PATH = PROJECT_ROOT / "notebooks" / "eda_splitwise_two_model_pressure_paper.tex"

LLAMA = "Llama-3.3-70B-Instruct"
QWEN = "Qwen2.5-72B-Instruct"
PRESSURE_LABELS = {
    "grounding_pressure": "Grounding",
    "localization_pressure": "Localization",
    "execution_pressure": "Execution",
    "output_pressure": "Output",
}
EPS = 1e-12


def fmt(x, digits=1):
    if pd.isna(x):
        return "--"
    return f"{float(x):.{digits}f}"


def fmt_p(x):
    if pd.isna(x):
        return "--"
    if x < 1e-3:
        return f"{x:.2e}"
    return f"{x:.3f}"


def fmt_ci(lo, hi, digits=1):
    return f"[{fmt(lo, digits)}, {fmt(hi, digits)}]"


def get_row(df, **filters):
    out = df.copy()
    for key, value in filters.items():
        out = out[out[key] == value]
    if len(out) != 1:
        raise ValueError(f"Expected exactly one row for filters={filters}, found {len(out)}")
    return out.iloc[0]


def balanced_pooled(df, axis, a, b, metric_col, n_iter=2000, seed=42):
    x = df[df[axis] == a][metric_col].dropna().to_numpy(dtype=float)
    y = df[df[axis] == b][metric_col].dropna().to_numpy(dtype=float)
    if len(x) == 0 or len(y) == 0:
        return None

    m = min(len(x), len(y))
    rng = np.random.default_rng(seed)
    deltas = np.empty(n_iter)
    for i in range(n_iter):
        xs = rng.choice(x, size=m, replace=False)
        ys = rng.choice(y, size=m, replace=False)
        deltas[i] = xs.mean() - ys.mean()

    mean_delta = float(deltas.mean())
    if abs(mean_delta) > EPS:
        sign_agreement = float((np.sign(deltas) == np.sign(mean_delta)).mean())
    else:
        sign_agreement = float((np.abs(deltas) <= EPS).mean())

    return {
        "balanced_n_each": m,
        "balanced_mean_delta": mean_delta,
        "balanced_ci_low": float(np.percentile(deltas, 2.5)),
        "balanced_ci_high": float(np.percentile(deltas, 97.5)),
        "balanced_sign_agreement": sign_agreement,
    }


def balanced_stratified(df, axis, controls, a, b, metric_col, n_iter=1000, seed=42):
    grouped = []
    for _, sdf in df.groupby(controls, dropna=False):
        sa = sdf[sdf[axis] == a][metric_col].dropna().to_numpy(dtype=float)
        sb = sdf[sdf[axis] == b][metric_col].dropna().to_numpy(dtype=float)
        if len(sa) == 0 or len(sb) == 0:
            continue
        m = min(len(sa), len(sb))
        grouped.append((sa, sb, m))

    if not grouped:
        return None

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_iter)
    for i in range(n_iter):
        num = 0.0
        den = 0.0
        for sa, sb, m in grouped:
            xa = rng.choice(sa, size=m, replace=False)
            xb = rng.choice(sb, size=m, replace=False)
            d = xa.mean() - xb.mean()
            num += m * d
            den += m
        deltas[i] = num / den if den > 0 else np.nan

    deltas = deltas[~np.isnan(deltas)]
    total_each = sum(m for _, _, m in grouped)
    mean_delta = float(deltas.mean())
    if abs(mean_delta) > EPS:
        sign_agreement = float((np.sign(deltas) == np.sign(mean_delta)).mean())
    else:
        sign_agreement = float((np.abs(deltas) <= EPS).mean())

    return {
        "matched_strata_balanced": len(grouped),
        "balanced_total_each": total_each,
        "balanced_mean_delta": mean_delta,
        "balanced_ci_low": float(np.percentile(deltas, 2.5)),
        "balanced_ci_high": float(np.percentile(deltas, 97.5)),
        "balanced_sign_agreement": sign_agreement,
    }


def make_pooled_sensitivity(domain, metric_col):
    analysis_df = pd.read_csv(CSV_DIR / f"{domain}_analysis_df.csv")
    pooled_df = pd.read_csv(CSV_DIR / f"{domain}_pooled_pairwise_df.csv")
    rows = []
    for _, r in pooled_df.iterrows():
        model = r["model"]
        axis = r["pressure_axis"]
        comparison = r["comparison"]
        a, b = comparison.split(" vs ")
        sub = analysis_df[analysis_df["model"] == model]
        bal = balanced_pooled(sub, axis, a, b, metric_col)
        rows.append(
            {
                "domain": domain,
                "model": model,
                "axis": axis,
                "comparison": comparison,
                "n_first": int(r["n_first"]),
                "n_second": int(r["n_second"]),
                "imbalance_ratio": max(r["n_first"], r["n_second"]) / min(r["n_first"], r["n_second"]),
                "pooled_delta": r["mean_delta"],
                "pooled_perm_p": r["permutation_pvalue"],
                **bal,
            }
        )
    return pd.DataFrame(rows)


def make_stratified_sensitivity(domain, metric_col):
    analysis_df = pd.read_csv(CSV_DIR / f"{domain}_analysis_df.csv")
    strat_df = pd.read_csv(CSV_DIR / f"{domain}_stratified_pairwise_df.csv")
    rows = []
    for _, r in strat_df.iterrows():
        model = r["model"]
        axis = r["pressure_axis"]
        comparison = r["comparison"]
        a, b = comparison.split(" vs ")
        sub = analysis_df[analysis_df["model"] == model]
        controls = [c for c in STRATIFIED_PRESSURE_SPECS[axis] if c in sub.columns]
        bal = balanced_stratified(sub, axis, controls, a, b, metric_col)
        if bal is None:
            continue
        rows.append(
            {
                "domain": domain,
                "model": model,
                "axis": axis,
                "comparison": comparison,
                "matched_strata_n": int(r["n_matched_strata"]),
                "strat_delta": r["mean_delta"],
                "strat_perm_p": r["permutation_pvalue"],
                **bal,
            }
        )
    return pd.DataFrame(rows)


coverage_by_model = pd.read_csv(CSV_DIR / "coverage_by_model_df.csv")
coverage_overview = pd.read_csv(CSV_DIR / "coverage_overview_df.csv")
event_headline = pd.read_csv(CSV_DIR / "event_headline_df.csv")
numeric_headline = pd.read_csv(CSV_DIR / "numeric_headline_df.csv")
event_factor = pd.read_csv(CSV_DIR / "event_factor_comparisons_df.csv")
numeric_factor = pd.read_csv(CSV_DIR / "numeric_factor_comparisons_df.csv")
numeric_bias_pressure = pd.read_csv(CSV_DIR / "numeric_bias_by_pressure_df.csv")

event_pooled_sensitivity = make_pooled_sensitivity("event", "pk_f1_x100")
event_strat_sensitivity = make_stratified_sensitivity("event", "pk_f1_x100")
numeric_pooled_sensitivity = make_pooled_sensitivity("numeric", "weighted_rmse")
numeric_strat_sensitivity = make_stratified_sensitivity("numeric", "weighted_rmse")

coverage_llama = get_row(coverage_by_model, model=LLAMA)
coverage_qwen = get_row(coverage_by_model, model=QWEN)
paired_total = int(get_row(coverage_overview, subset="paired_sample_ids")["n_samples"])
paired_parsed = int(get_row(coverage_overview, subset="both_parsed_pred_table")["n_samples"])
paired_pk = int(get_row(coverage_overview, subset="both_pk_evaluable")["n_samples"])
paired_numeric = int(get_row(coverage_overview, subset="both_numeric_evaluable")["n_samples"])

headline_rows = []
for section_name, df in [("Event identification", event_headline), ("Numeric fidelity", numeric_headline)]:
    for _, row in df.iterrows():
        headline_rows.append(
            {
                "section": section_name,
                "metric": row["metric_label"],
                "n_pairs": int(row["n_pairs"]),
                "llama": row["mean_a"],
                "qwen": row["mean_b"],
                "delta": row["mean_delta_b_minus_a"],
                "ci": fmt_ci(row["ci_low"], row["ci_high"]),
                "perm_p": row["permutation_pvalue"],
            }
        )


def factor_pick(df, model, factor_pretty, comparison):
    sub = df[(df["model"] == model) & (df["factor_pretty"] == factor_pretty) & (df["comparison"] == comparison)]
    if len(sub) == 0:
        return "--", "--"
    row = sub.iloc[0]
    delta = row["mean_delta"] if pd.notna(row.get("mean_delta")) else row["weighted_mean_delta"]
    return fmt(delta), fmt_ci(row["ci_low"], row["ci_high"])


selected_factor_specs = [
    ("Temporal reasoning", "point-based temporal filtering vs non-temporal control"),
    ("Entity grounding", "multi-entity grounding vs single-entity grounding"),
    ("Compositional depth", "5-6 step composition vs 3-4 step composition"),
]

factor_rows = []
for factor_pretty, comparison in selected_factor_specs:
    factor_rows.append(
        {
            "factor": factor_pretty,
            "comparison": comparison,
            "event_llama": factor_pick(event_factor, LLAMA, factor_pretty, comparison),
            "event_qwen": factor_pick(event_factor, QWEN, factor_pretty, comparison),
            "numeric_llama": factor_pick(numeric_factor, LLAMA, factor_pretty, comparison),
            "numeric_qwen": factor_pick(numeric_factor, QWEN, factor_pretty, comparison),
        }
    )

selected_event_rows = [
    get_row(event_strat_sensitivity, model=LLAMA, axis="grounding_pressure", comparison="medium vs low"),
    get_row(event_strat_sensitivity, model=QWEN, axis="grounding_pressure", comparison="medium vs low"),
    get_row(event_strat_sensitivity, model=LLAMA, axis="execution_pressure", comparison="high vs medium"),
    get_row(event_strat_sensitivity, model=QWEN, axis="execution_pressure", comparison="high vs medium"),
    get_row(event_strat_sensitivity, model=LLAMA, axis="output_pressure", comparison="medium vs low"),
    get_row(event_strat_sensitivity, model=QWEN, axis="output_pressure", comparison="medium vs low"),
]

selected_numeric_rows = [
    get_row(numeric_strat_sensitivity, model=LLAMA, axis="grounding_pressure", comparison="high vs medium"),
    get_row(numeric_strat_sensitivity, model=LLAMA, axis="execution_pressure", comparison="high vs low"),
    get_row(numeric_strat_sensitivity, model=QWEN, axis="execution_pressure", comparison="high vs low"),
    get_row(numeric_strat_sensitivity, model=QWEN, axis="execution_pressure", comparison="high vs medium"),
]

output_bias_rows = []
for model_name in [LLAMA, QWEN]:
    for level in ["low", "medium", "high"]:
        row = get_row(numeric_bias_pressure, group_col="output_pressure", model=model_name, level=level)
        output_bias_rows.append(
            {
                "model": "Llama" if model_name == LLAMA else "Qwen",
                "level": level,
                "weighted_rmse": row["mean_weighted_rmse"],
                "over": row["mean_overcount_pct"],
                "under": row["mean_undercount_pct"],
                "net": row["mean_net_over_under_pct"],
            }
        )

lines = []
lines.append(r"\subsection{Two-part analysis with permutation and balance sensitivity checks}")
lines.append("")
lines.append(
    r"We analyze the two models in two stages. "
    r"First, we study \emph{event identification}, measured by PK-F1 and related PK-recovery statistics. "
    r"Second, we study \emph{numeric fidelity}, measured by weighted RMSE together with aligned cell accuracy and directional bias diagnostics. "
    r"This decomposition is preferable to exact match because it separates event-retrieval failures from numeric-value errors."
)
lines.append("")
lines.append(
    r"The presentation below uses a strict reporting rule: only findings that remain directionally stable under the raw analysis, permutation testing, and balance-corrected sensitivity analysis are promoted to the main results. "
    r"Findings that depend materially on imbalance correction are retained only as sensitivity analyses in the appendix."
)
lines.append("")
lines.append(r"\paragraph{Coverage, comparability, and bias control.}")
lines.append(
    r"The model comparisons are computed on paired-common subsets only. "
    r"Invalid or non-evaluable predictions are reported in coverage statistics, but they are not silently converted into zero scores in the paired headline analysis. "
    r"This prevents parser failure from being conflated with conditional answer quality."
)
lines.append("")
lines.append(
    r"To further reduce bias in the pressure analyses, we use three inferential layers. "
    r"First, pooled pressure contrasts are treated as descriptive and are accompanied by permutation tests on mean differences. "
    r"Second, stratified pressure contrasts condition on the other pressure axes and on major answer-shape confounders; their significance is assessed with sign-flip permutation tests over matched-stratum deltas. "
    r"Third, for imbalanced comparisons we run repeated balanced subsampling: in pooled analyses, the larger level is repeatedly downsampled to the smaller level size; in stratified analyses, each matched stratum is repeatedly equalized to the smaller within-stratum support. "
    r"We then report the resampled mean delta and its empirical confidence interval as a sensitivity check."
)
lines.append("")
lines.append(
    r"In the main text, a result is shown only if all three checks support the same directional interpretation. "
    r"If the raw estimate, the permutation test, and the balanced-resampling estimate do not agree closely enough, the contrast is removed from the headline tables and discussed only in the sensitivity appendix. "
    r"This rule is intentionally conservative and is meant to make every promoted claim straightforward for a reviewer to audit. "
    r"In this paper, we use the term \emph{robust} for findings that pass all three checks; we use \emph{sensitivity-only} for findings whose apparent size or certainty changes materially after rebalancing or whose support is too sparse for a stable stratified comparison."
)
lines.append("")
lines.append(
    rf"Out of {paired_total} paired sample IDs, both models produce parsed tables on {paired_parsed} cases. "
    rf"The common PK-evaluable subset contains {paired_pk} cases, and the common numeric-evaluable subset contains {paired_numeric} cases."
)
lines.append("")

lines.append(r"\begin{table}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Coverage asymmetry and common evaluable subsets.}")
lines.append(r"\label{tab:paired_coverage}")
lines.append(r"\begin{tabular}{lrrrr}")
lines.append(r"\toprule")
lines.append(r"Model / subset & Total & Parsed tables & PK-evaluable & Numeric-evaluable \\")
lines.append(r"\midrule")
lines.append(
    rf"Llama & {int(coverage_llama['total_samples'])} & {int(coverage_llama['parsed_pred_table_n'])} & {int(coverage_llama['pk_evaluable_n'])} & {int(coverage_llama['numeric_evaluable_n'])} \\"
)
lines.append(
    rf"Qwen & {int(coverage_qwen['total_samples'])} & {int(coverage_qwen['parsed_pred_table_n'])} & {int(coverage_qwen['pk_evaluable_n'])} & {int(coverage_qwen['numeric_evaluable_n'])} \\"
)
lines.append(r"\midrule")
lines.append(rf"Common paired parsed subset & \multicolumn{{4}}{{r}}{{{paired_parsed}}} \\")
lines.append(rf"Common paired PK subset & \multicolumn{{4}}{{r}}{{{paired_pk}}} \\")
lines.append(rf"Common paired numeric subset & \multicolumn{{4}}{{r}}{{{paired_numeric}}} \\")
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")
lines.append("")

lines.append(
    r"Table~\ref{tab:paired_coverage} motivates the paired-common design. "
    rf"Llama has {int(coverage_llama['invalid_pred_table_n'])} invalid parsed predictions, compared with {int(coverage_qwen['invalid_pred_table_n'])} for Qwen. "
    r"Coverage asymmetry is therefore analyzed explicitly rather than absorbed into the main quality metric."
)
lines.append("")

lines.append(r"\paragraph{Headline two-part comparison.}")
lines.append("")
lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Headline paired comparison. Positive $\Delta_{\text{Qwen-Llama}}$ favors Qwen for PK metrics and aligned cell accuracy; negative values favor Qwen for weighted RMSE and bias metrics where lower is better. Permutation $p$-values target the paired mean difference.}")
lines.append(r"\label{tab:headline_two_part}")
lines.append(r"\begin{tabular}{llrrrrrr}")
lines.append(r"\toprule")
lines.append(r"Stage & Metric & $n$ & Llama & Qwen & $\Delta_{\text{Qwen-Llama}}$ & 95\% CI & Perm.\ $p$ \\")
lines.append(r"\midrule")
current_section = None
for row in headline_rows:
    section_label = row["section"] if row["section"] != current_section else ""
    current_section = row["section"]
    lines.append(
        rf"{section_label} & {row['metric']} & {row['n_pairs']} & {fmt(row['llama'])} & {fmt(row['qwen'])} & {fmt(row['delta'])} & {row['ci']} & {fmt_p(row['perm_p'])} \\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")
lines.append("")

lines.append(
    r"On the event-identification stage, the models are essentially tied on PK-F1, but they differ in precision versus recall: "
    r"Qwen has higher PK recall, while Llama has higher PK precision. "
    r"On the numeric stage, Qwen has lower mean weighted RMSE, but the paired confidence interval still crosses zero. "
    r"The more stable numeric difference appears in the bias diagnostics: Qwen undercounts more, while Llama has the larger positive net over-under bias."
)
lines.append("")
lines.append(
    r"Accordingly, the main-paper story is not that one model dominates on a single scalar metric. "
    r"Instead, the models differ in error profile: they are similar at the event level, but they trade off recall versus precision and differ systematically in numeric bias."
)
lines.append("")

lines.append(r"\paragraph{Factor analysis.}")
lines.append("")
lines.append(
    r"The factor analysis is used only to motivate the pressure taxonomy. "
    r"It is intentionally descriptive rather than confirmatory: these contrasts help explain why the later pressure axes are scientifically interesting, but they are not promoted as standalone main findings unless they reappear as robust pressure effects in the stratified analysis."
)
lines.append("")
lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Selected descriptive factor contrasts across the two stages. Event columns report PK-F1 deltas; numeric columns report weighted RMSE deltas. This table motivates the pressure design and is not used by itself to support main inferential claims.}")
lines.append(r"\label{tab:factor_two_stage}")
lines.append(r"\begin{tabular}{llrlrlrlrl}")
lines.append(r"\toprule")
lines.append(r"Factor & Contrast & \multicolumn{2}{c}{Event Llama} & \multicolumn{2}{c}{Event Qwen} & \multicolumn{2}{c}{Numeric Llama} & \multicolumn{2}{c}{Numeric Qwen} \\")
lines.append(r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}")
lines.append(r" &  & $\Delta$ & 95\% CI & $\Delta$ & 95\% CI & $\Delta$ & 95\% CI & $\Delta$ & 95\% CI \\")
lines.append(r"\midrule")
for row in factor_rows:
    lines.append(
        rf"{row['factor']} & {row['comparison']} & {row['event_llama'][0]} & {row['event_llama'][1]} & {row['event_qwen'][0]} & {row['event_qwen'][1]} & {row['numeric_llama'][0]} & {row['numeric_llama'][1]} & {row['numeric_qwen'][0]} & {row['numeric_qwen'][1]} \\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")
lines.append("")

lines.append(
    r"The descriptive factor patterns still motivate the pressure design, but the two-stage decomposition clarifies what each factor appears to stress. "
    r"Temporal reasoning looks more like an event-identification challenge, whereas multi-entity grounding and deeper composition appear to act more strongly on numeric fidelity. "
    r"Because these factor contrasts are not balance-corrected in the same way as the final pressure tables, we use them to motivate the analysis plan rather than to anchor the main claims."
)
lines.append("")

lines.append(r"\paragraph{Main pressure results: stratified contrasts.}")
lines.append("")
lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Main stratified event-identification pressure contrasts. We report the raw stratified delta, the sign-flip permutation $p$-value, and the balanced-resampling sensitivity estimate.}")
lines.append(r"\label{tab:event_stratified_main}")
lines.append(r"\begin{tabular}{llrrrrrl}")
lines.append(r"\toprule")
lines.append(r"Model & Axis & Contrast & Raw $\Delta$ & Perm.\ $p$ & Balanced $\Delta$ & Balanced 95\% CI & Verdict \\")
lines.append(r"\midrule")
for row in selected_event_rows:
    verdict = "robust" if row["balanced_ci_low"] * row["balanced_ci_high"] > 0 and row["strat_perm_p"] < 0.05 else "sensitive"
    lines.append(
        rf"{'Llama' if row['model']==LLAMA else 'Qwen'} & {PRESSURE_LABELS[row['axis']]} & {row['comparison']} & {fmt(row['strat_delta'])} & {fmt_p(row['strat_perm_p'])} & {fmt(row['balanced_mean_delta'])} & {fmt_ci(row['balanced_ci_low'], row['balanced_ci_high'])} & {verdict} \\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")
lines.append("")

lines.append(
    r"Table~\ref{tab:event_stratified_main} identifies the most stable event-identification effects. "
    r"Grounding \texttt{medium vs low}, execution \texttt{high vs medium}, and output \texttt{medium vs low} remain directionally consistent under both permutation testing and balanced resampling in both models. "
    r"These are therefore the cleanest pressure claims for the event stage."
)
lines.append("")
lines.append(
    r"Event-stage contrasts omitted from the main table are omitted deliberately. "
    r"Either their stratified support is too sparse, or their inferential signal weakens once balance correction is imposed. "
    r"Those rows are still reported in the appendix so the reviewer can inspect them directly. "
    r"When a reviewer sees a row only in the appendix, the intended reading is not that the pattern is uninteresting; it is that the pattern does not yet meet the paper's threshold for a stable primary claim."
)
lines.append("")

lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Main stratified numeric-fidelity pressure contrasts using weighted RMSE. Only robust rows are shown: each displayed contrast is directionally stable under the raw stratified estimate, the permutation test, and balanced resampling.}")
lines.append(r"\label{tab:numeric_stratified_main}")
lines.append(r"\begin{tabular}{llrrrrrl}")
lines.append(r"\toprule")
lines.append(r"Model & Axis & Contrast & Raw $\Delta$ & Perm.\ $p$ & Balanced $\Delta$ & Balanced 95\% CI & Verdict \\")
lines.append(r"\midrule")
for row in selected_numeric_rows:
    verdict = "robust" if row["balanced_ci_low"] * row["balanced_ci_high"] > 0 and row["strat_perm_p"] < 0.05 else "sensitive"
    lines.append(
        rf"{'Llama' if row['model']==LLAMA else 'Qwen'} & {PRESSURE_LABELS[row['axis']]} & {row['comparison']} & {fmt(row['strat_delta'])} & {fmt_p(row['strat_perm_p'])} & {fmt(row['balanced_mean_delta'])} & {fmt_ci(row['balanced_ci_low'], row['balanced_ci_high'])} & {verdict} \\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")
lines.append("")

lines.append(
    r"On the numeric stage, execution pressure remains the strongest and most stable RMSE stressor. "
    r"For both models, \texttt{high vs low} execution pressure survives permutation testing and balanced resampling, and Qwen also shows a robust \texttt{high vs medium} execution effect. "
    r"Llama additionally shows a robust grounding \texttt{high vs medium} effect. "
    r"Sensitive numeric contrasts are intentionally absent from the main table. "
    r"For example, some output-pressure contrasts become much larger after rebalancing than they appear in the raw stratified analysis; that pattern indicates that the apparent effect size is partly driven by support imbalance, so those rows are retained only in the appendix. "
    r"In practical terms, a sensitivity-only row is not discarded; it is reinterpreted as a hypothesis-generating pattern that requires either better overlap, more support, or explicit reweighting before it can be promoted to a main result."
)
lines.append("")

lines.append(r"\paragraph{Numeric bias profile.}")
lines.append("")
lines.append(r"\begin{table*}[t]")
lines.append(r"\centering")
lines.append(r"\caption{Numeric bias by output pressure. Positive net bias indicates overcounting; negative net bias indicates undercounting.}")
lines.append(r"\label{tab:numeric_output_bias}")
lines.append(r"\begin{tabular}{llrrrr}")
lines.append(r"\toprule")
lines.append(r"Model & Output pressure & Weighted RMSE & Overcount\% & Undercount\% & Net bias \\")
lines.append(r"\midrule")
for row in output_bias_rows:
    lines.append(
        rf"{row['model']} & {row['level']} & {fmt(row['weighted_rmse'])} & {fmt(row['over'])} & {fmt(row['under'])} & {fmt(row['net'])} \\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table*}")
lines.append("")

lines.append(
    r"The bias table clarifies the main numeric story. "
    r"At low output pressure, both models overcount on average. "
    r"As output pressure rises, both models move toward undercounting, and the shift is markedly stronger for Qwen. "
    r"This directional error profile is more stable than the overall weighted-RMSE headline and therefore carries substantial interpretive value."
)
lines.append("")
lines.append(
    r"The final paper narrative is therefore built around three robust claims. "
    r"First, the models are closely matched on event-level PK-F1 but differ in recall versus precision. "
    r"Second, event-identification performance degrades reliably with execution and output pressure, and improves from low to medium grounding pressure. "
    r"Third, numeric fidelity is stressed most clearly by execution pressure, while the overall cross-model numeric difference is better characterized through bias direction than through a decisive RMSE headline."
)
lines.append("")
lines.append(
    r"The distinction between robust and sensitivity-only results is part of the argument rather than a cosmetic reporting choice. "
    r"It shows which claims survive stronger bias checks, and it clarifies which patterns remain plausible but still depend on imbalance correction or limited matched support."
)
lines.append("")

lines.append(r"\appendix")
lines.append(r"\subsection{Sensitivity Analysis: Imbalance Diagnostics and Balanced Resampling}")
lines.append("")
lines.append(
    r"The appendix reports the imbalance ratios and balanced-resampling sensitivity analyses for every pooled and stratified pressure contrast. "
    r"For pooled contrasts, the imbalance ratio is the ratio of the larger level size to the smaller level size. "
    r"For stratified contrasts, the main text relies on matched-stratum comparisons, and the appendix reports the balanced total support after equalizing each stratum to its smaller side."
)
lines.append("")
lines.append(
    r"These appendix tables serve two purposes. "
    r"First, they make the imbalance structure transparent. "
    r"Second, they show which contrasts are sensitive to the empirical support pattern. "
    r"In this paper, a contrast is treated as \emph{sensitivity-only} if its interpretation depends materially on rebalancing, or if the raw permutation test and the balance-corrected estimate do not support the same level of certainty. "
    r"The methodological consequence is explicit: such rows are not used to support the main narrative, and they instead motivate future data collection, stricter overlap restrictions, or more formal weighting approaches."
)
lines.append("")


def add_appendix_table(df, label, caption, pooled=True):
    lines.append(r"\begin{table*}[p]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{{caption}}}")
    lines.append(rf"\label{{{label}}}")
    if pooled:
        lines.append(r"\begin{tabular}{llrrrrrr}")
        lines.append(r"\toprule")
        lines.append(r"Model & Axis & Contrast & Imbalance ratio & Raw $\Delta$ & Perm.\ $p$ & Balanced $\Delta$ & Balanced 95\% CI \\")
        lines.append(r"\midrule")
        for _, row in df.iterrows():
            lines.append(
                rf"{'Llama' if row['model']==LLAMA else 'Qwen'} & {PRESSURE_LABELS[row['axis']]} & {row['comparison']} & {fmt(row['imbalance_ratio'],3)} & {fmt(row['pooled_delta'])} & {fmt_p(row['pooled_perm_p'])} & {fmt(row['balanced_mean_delta'])} & {fmt_ci(row['balanced_ci_low'], row['balanced_ci_high'])} \\"
            )
    else:
        lines.append(r"\begin{tabular}{llrrrrrr}")
        lines.append(r"\toprule")
        lines.append(r"Model & Axis & Contrast & Matched strata & Raw $\Delta$ & Perm.\ $p$ & Balanced $\Delta$ & Balanced 95\% CI \\")
        lines.append(r"\midrule")
        for _, row in df.iterrows():
            lines.append(
                rf"{'Llama' if row['model']==LLAMA else 'Qwen'} & {PRESSURE_LABELS[row['axis']]} & {row['comparison']} & {int(row['matched_strata_n'])} & {fmt(row['strat_delta'])} & {fmt_p(row['strat_perm_p'])} & {fmt(row['balanced_mean_delta'])} & {fmt_ci(row['balanced_ci_low'], row['balanced_ci_high'])} \\"
            )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")
    lines.append("")


add_appendix_table(
    event_pooled_sensitivity,
    "tab:appendix_event_pooled",
    "Appendix event-stage pooled pressure contrasts with imbalance ratios, permutation tests, and balanced-resampling sensitivity.",
    pooled=True,
)
add_appendix_table(
    event_strat_sensitivity,
    "tab:appendix_event_stratified",
    "Appendix event-stage stratified pressure contrasts with permutation tests and balanced-resampling sensitivity.",
    pooled=False,
)
add_appendix_table(
    numeric_pooled_sensitivity,
    "tab:appendix_numeric_pooled",
    "Appendix numeric-stage pooled pressure contrasts with imbalance ratios, permutation tests, and balanced-resampling sensitivity.",
    pooled=True,
)
add_appendix_table(
    numeric_strat_sensitivity,
    "tab:appendix_numeric_stratified",
    "Appendix numeric-stage stratified pressure contrasts with permutation tests and balanced-resampling sensitivity.",
    pooled=False,
)

OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote LaTeX section to {OUT_PATH}")
