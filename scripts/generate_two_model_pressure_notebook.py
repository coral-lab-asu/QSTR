from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "eda_splitwise_two_model_pressure.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip() + "\n")


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip() + "\n")


cells = [
    md(
        """
        # Two-Model Splitwise Analysis: Event Identification and Numeric Fidelity

        ## Outcomes First

        This notebook keeps the same broad flow as `eda_splitwise`, but the paper story is now explicitly **two-stage**:

        1. **Event identification / primary-key recovery**
           We ask whether the model identifies the correct events or rows.
           The main metric here is `pk_f1_x100`, with recall, precision, and exact-set match as supporting views.

        2. **Numeric fidelity inside the identified structure**
           We then ask how well the numeric content is recovered.
           The main metric here is `weighted_rmse`, with aligned cell accuracy, `Overcount%`, `Undercount%`, and net over-under bias as supporting diagnostics.

        ## Why this decomposition

        We do **not** use exact match as the main story because it collapses near-miss tables and detailed numeric mistakes into the same 0/1 label.

        We also avoid using a single holistic score as the main paper endpoint because it blends together two scientifically distinct failure modes:
        - failing to identify the right events / rows;
        - failing to estimate the numeric values correctly once the events are identified.

        ## Comparable subsets

        The key fairness decision in this notebook is:
        - **direct model comparisons use only paired-common evaluable samples**;
        - invalid or unparsed predictions are reported in the coverage table, but they are not silently scored as zero in the paired headline comparisons.

        That means we first report coverage, then we analyze:
        - the PK-evaluable common subset for event identification;
        - the numeric-evaluable common subset for numeric fidelity.

        ## Flow

        The notebook follows the same research flow you asked for:
        - inspect factor analysis to motivate pressure design;
        - test pooled pressures;
        - test stratified pressures;
        - and keep the event-identification story separate from the numeric-fidelity story.
        """
    ),
    code(
        """
        import sys
        from pathlib import Path

        import pandas as pd

        try:
            from IPython.display import display
        except ImportError:
            display = print

        PROJECT_ROOT = Path.cwd()
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

        from two_model_decomposed_analysis import FACTOR_LABELS, PRESSURE_LABELS, run_full_analysis

        outputs = run_full_analysis()

        coverage_by_model_df = outputs["coverage_by_model_df"]
        coverage_overview_df = outputs["coverage_overview_df"]

        event_headline_df = outputs["event_headline_df"]
        event_factor_comparisons_df = outputs["event_factor_comparisons_df"]
        event_pooled_pressure_df = outputs["event_pooled_pressure_df"]
        event_model_delta_by_pressure_df = outputs["event_model_delta_by_pressure_df"]
        event_stratified_pairwise_df = outputs["event_stratified_pairwise_df"]

        numeric_headline_df = outputs["numeric_headline_df"]
        numeric_factor_comparisons_df = outputs["numeric_factor_comparisons_df"]
        numeric_pooled_pressure_df = outputs["numeric_pooled_pressure_df"]
        numeric_model_delta_by_pressure_df = outputs["numeric_model_delta_by_pressure_df"]
        numeric_stratified_pairwise_df = outputs["numeric_stratified_pairwise_df"]
        numeric_bias_by_factor_df = outputs["numeric_bias_by_factor_df"]
        numeric_bias_by_pressure_df = outputs["numeric_bias_by_pressure_df"]
        """
    ),
    md(
        """
        ## Coverage and Comparable Subsets

        Read this block first.

        The most important methodological point is that the samplewise files are not symmetric in parse coverage:
        - `Llama-3.3-70B-Instruct` has substantially more invalid / unparsed predictions;
        - `Qwen2.5-72B-Instruct` has fewer such failures.

        For a paper, the honest way to handle that is:
        - report the asymmetry clearly;
        - then compare the models on the common subset where the relevant metric is actually defined for both.

        That gives us a clean separation between:
        - **coverage / robustness to parser failure**, and
        - **quality conditional on both systems being evaluable**.
        """
    ),
    code(
        """
        print("Coverage by model")
        display(coverage_by_model_df)

        print("Paired-common subsets used for the main two-part analysis")
        display(coverage_overview_df)
        """
    ),
    md(
        """
        ## Part I: Event Identification

        ### Metrics

        `pk_f1_x100` is the main event-identification metric.

        Intuition:
        - it measures whether the predicted table recovers the right PK-aligned events or rows;
        - it does **not** score the numeric values inside those rows;
        - higher recall means the model misses fewer true events;
        - higher precision means the model introduces fewer spurious events.

        Supporting metrics:
        - `pk_recall_x100`
        - `pk_precision_x100`
        - `pk_exact_set_match_num`

        So this block answers: **who finds the right events, and how do those errors change across factors and pressures?**
        """
    ),
    code(
        """
        display(
            event_headline_df[
                [
                    "metric_label",
                    "n_pairs",
                    "mean_a",
                    "mean_b",
                    "mean_delta_b_minus_a",
                    "ci_low",
                    "ci_high",
                    "permutation_pvalue",
                    "wilcoxon_pvalue",
                ]
            ]
        )
        """
    ),
    md(
        """
        The headline result to look for here is usually a **precision-recall trade-off** rather than a single winner:
        - if PK-F1 is tied but recall and precision move in opposite directions, the models are finding rows differently;
        - that is a stronger and more informative story than exact match.
        """
    ),
    code(
        """
        def get_selected_factor_rows(df, specs):
            rows = []
            for factor_pretty, comparison in specs:
                sub = df[(df["factor_pretty"] == factor_pretty) & (df["comparison"] == comparison)].copy()
                rows.append(sub)
            return pd.concat(rows, ignore_index=True)


        event_factor_selected = get_selected_factor_rows(
            event_factor_comparisons_df,
            [
                ("Temporal reasoning", "point-based temporal filtering vs non-temporal control"),
                ("Temporal reasoning", "range-based temporal filtering vs non-temporal control"),
                ("SQL reasoning", "Group comparison vs Grouped aggregation"),
                ("Compositional depth", "5-6 step composition vs 3-4 step composition"),
            ],
        )

        display(event_factor_selected)
        """
    ),
    md(
        """
        These factor contrasts motivate the pressure design:
        - temporal comparisons tell us whether event identification degrades when time filtering is involved;
        - SQL and compositional contrasts tell us whether execution depth affects row recovery;
        - if those effects are stable enough, they justify later pressure axes such as localization and execution pressure.
        """
    ),
    code(
        """
        event_pooled_tidy = event_pooled_pressure_df.copy()
        event_pooled_tidy["pressure_axis_label"] = event_pooled_tidy["pressure_axis"].map(PRESSURE_LABELS)
        event_pooled_tidy = event_pooled_tidy[
            ["model", "pressure_axis_label", "pressure_level", "n", "mean_metric", "median_metric"]
        ].sort_values(["pressure_axis_label", "pressure_level", "model"])

        print("Event-identification pooled pressure means")
        display(event_pooled_tidy)

        event_stratified_selected = event_stratified_pairwise_df[
            event_stratified_pairwise_df["comparison"].isin(["medium vs low", "high vs medium"])
        ].copy()
        event_stratified_selected["pressure_axis_label"] = event_stratified_selected["pressure_axis"].map(PRESSURE_LABELS)
        event_stratified_selected = event_stratified_selected[
            [
                "model",
                "pressure_axis_label",
                "comparison",
                "n_matched_strata",
                "mean_delta",
                "ci_low",
                "ci_high",
                "permutation_pvalue",
                "significance",
            ]
        ].sort_values(["pressure_axis_label", "comparison", "model"])

        print("Event-identification stratified pressure contrasts")
        display(event_stratified_selected)
        """
    ),
    md(
        """
        ## Part II: Numeric Fidelity

        ### Metrics

        This stage is deliberately separate from PK-F1.

        `weighted_rmse` is the main numeric-fidelity metric:
        - lower is better;
        - it measures the magnitude of numeric error on the numeric-evaluable subset.

        Supporting diagnostics:
        - `cell_acc_num`: aligned cell accuracy after evaluator alignment;
        - `Overcount%`: tendency to overshoot numeric values;
        - `Undercount%`: tendency to undershoot numeric values;
        - `net_over_under_pct`: signed bias diagnostic (`Overcount% - Undercount%`).

        So this block answers: **once the event structure is evaluable, which model is numerically more faithful, and what kind of numeric bias does each one show?**
        """
    ),
    code(
        """
        display(
            numeric_headline_df[
                [
                    "metric_label",
                    "n_pairs",
                    "mean_a",
                    "mean_b",
                    "mean_delta_b_minus_a",
                    "ci_low",
                    "ci_high",
                    "permutation_pvalue",
                    "wilcoxon_pvalue",
                ]
            ]
        )
        """
    ),
    md(
        """
        The main numeric interpretation should separate **error magnitude** from **bias direction**:
        - `weighted_rmse` tells us how far off the numbers are on average, while penalizing larger misses more strongly;
        - `Overcount%` and `Undercount%` tell us *how* the model is wrong.

        That lets the paper say things like:
        - one model is not just better or worse numerically;
        - it may systematically overcount, while the other systematically undercounts.
        """
    ),
    code(
        """
        numeric_factor_selected = get_selected_factor_rows(
            numeric_factor_comparisons_df,
            [
                ("Temporal reasoning", "point-based temporal filtering vs non-temporal control"),
                ("Entity grounding", "single-entity grounding vs schema-only grounding"),
                ("Entity grounding", "multi-entity grounding vs single-entity grounding"),
                ("Compositional depth", "5-6 step composition vs 3-4 step composition"),
            ],
        )

        print("Selected numeric factor contrasts using weighted RMSE")
        display(numeric_factor_selected)
        """
    ),
    code(
        """
        numeric_pooled_tidy = numeric_pooled_pressure_df.copy()
        numeric_pooled_tidy["pressure_axis_label"] = numeric_pooled_tidy["pressure_axis"].map(PRESSURE_LABELS)
        numeric_pooled_tidy = numeric_pooled_tidy[
            ["model", "pressure_axis_label", "pressure_level", "n", "mean_metric", "median_metric"]
        ].sort_values(["pressure_axis_label", "pressure_level", "model"])

        print("Numeric-fidelity pooled pressure means (weighted RMSE; lower is better)")
        display(numeric_pooled_tidy)

        numeric_stratified_selected = numeric_stratified_pairwise_df[
            numeric_stratified_pairwise_df["comparison"].isin(["high vs low", "high vs medium"])
        ].copy()
        numeric_stratified_selected["pressure_axis_label"] = numeric_stratified_selected["pressure_axis"].map(PRESSURE_LABELS)
        numeric_stratified_selected = numeric_stratified_selected[
            [
                "model",
                "pressure_axis_label",
                "comparison",
                "n_matched_strata",
                "mean_delta",
                "ci_low",
                "ci_high",
                "permutation_pvalue",
                "significance",
            ]
        ].sort_values(["pressure_axis_label", "comparison", "model"])

        print("Numeric-fidelity stratified pressure contrasts")
        display(numeric_stratified_selected)
        """
    ),
    code(
        """
        output_bias_df = numeric_bias_by_pressure_df[
            numeric_bias_by_pressure_df["group_col"] == "output_pressure"
        ].copy()
        output_bias_df = output_bias_df[
            [
                "model",
                "level",
                "n",
                "mean_weighted_rmse",
                "mean_overcount_pct",
                "mean_undercount_pct",
                "mean_net_over_under_pct",
            ]
        ].sort_values(["level", "model"])

        print("Numeric bias by output pressure")
        display(output_bias_df)
        """
    ),
    md(
        """
        The output-pressure bias table is especially useful for a research-paper discussion because it reveals a model's **numeric error profile**:
        - positive net bias means systematic overcounting;
        - negative net bias means systematic undercounting;
        - if that bias flips as output pressure rises, the model is not just getting noisier, it is changing error direction.
        """
    ),
    code(
        """
        paper_plan_df = pd.DataFrame(
            [
                {
                    "figure_or_table": "Table 1",
                    "purpose": "Coverage asymmetry and paired-common evaluable subsets.",
                    "source_object": "coverage_by_model_df + coverage_overview_df",
                },
                {
                    "figure_or_table": "Table 2",
                    "purpose": "Event-identification headline comparison on the common PK-evaluable subset.",
                    "source_object": "event_headline_df",
                },
                {
                    "figure_or_table": "Table 3",
                    "purpose": "Selected factor contrasts that motivate pressure design across event and numeric stages.",
                    "source_object": "event_factor_selected + numeric_factor_selected",
                },
                {
                    "figure_or_table": "Table 4",
                    "purpose": "Event-identification pressure results, with emphasis on stratified contrasts.",
                    "source_object": "event_stratified_selected",
                },
                {
                    "figure_or_table": "Table 5",
                    "purpose": "Numeric-fidelity headline comparison on the common numeric-evaluable subset.",
                    "source_object": "numeric_headline_df",
                },
                {
                    "figure_or_table": "Table 6",
                    "purpose": "Numeric-bias diagnostics by pressure level.",
                    "source_object": "output_bias_df",
                },
            ]
        )

        display(paper_plan_df)
        """
    ),
    md(
        """
        ## Reading Guide

        A paper-quality read of this notebook should follow this order:

        1. Start from coverage and the paired-common subset counts.
        2. Read the event-identification headline table as a PK precision-recall trade-off story.
        3. Use the factor tables to justify why pressure design is still useful after decomposing the task.
        4. Read the event pressure block as the stronger structural story.
        5. Read the numeric block as a separate value-fidelity and bias story.

        If you still want a single holistic table metric later, `full_cell_f1` can be added back as an appendix sensitivity analysis. It should not replace the main two-part decomposition.
        """
    ),
]


nb = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    },
)

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
with NOTEBOOK_PATH.open("w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Wrote notebook to {NOTEBOOK_PATH}")
