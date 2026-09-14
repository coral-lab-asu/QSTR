# sql_crew_agents_v2.py
"""
Fresh base implementation (keep your original sql_crew_agents.py unchanged).

This file contains:
- CrewAI agents for SQL + NL generation + optional fixing
- Schema + template grounding helpers
- Optional diversity-template injection from a CSV bank (e.g. your 1000-bank)
- Optional prompt-level dedupe memory injection (seen canonical list)
- Pure-Python SQL validation against duckdb table `df` (CSV registered as df)

NOTES:
- Table name in SQL must be `df` (DuckDB).
- This file does NOT implement hard dedupe + resume loops; that belongs in sql_crew_agents_dedup.py.
- This file does include prompt hooks so the dedup runner can pass:
    - diversity_templates_json
    - seen_query_canonicals_json

Security:
- Do NOT hardcode API keys in source control. Use env var: GEMINI_API_KEY.
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .config import load_project_env
except ImportError:
    from config import load_project_env


load_project_env()

from crewai import Agent, Crew, Task, LLM
from crewai.tools import BaseTool

try:
    from .sql_agent_tools import (
        CRICKET_TABLE_DIR,
        list_csvs,
        load_templates,
        pretty_json,
        run_sql_on_df,
        sample_table_schema,
    )
    from .sql_param_initializer import initialize_sql_items
except ImportError:  # Supports direct execution from the CMT2 directory.
    from sql_agent_tools import (
        CRICKET_TABLE_DIR,
        list_csvs,
        load_templates,
        pretty_json,
        run_sql_on_df,
        sample_table_schema,
    )
    from sql_param_initializer import initialize_sql_items


# ---------------------------------------------------------------------------
# Retry wrapper for API calls with 429 handling
# ---------------------------------------------------------------------------

def retry_on_429(
    func: Callable,
    max_retries: int = 5,
    base_delay: int = 2,
    *args,
    **kwargs
):
    import sys

    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            if hasattr(result, "raw"):
                _ = result.raw
            sys.stdout.flush()
            sys.stderr.flush()
            time.sleep(1)
            return result
        except Exception as e:
            error_str = str(e).lower()
            print(f"  Error: {error_str}")

            is_429 = (
                "429" in error_str
                or "rate limit" in error_str
                or "quota exceeded" in error_str
                or "too many requests" in error_str
                or "resource exhausted" in error_str
                or "503" in error_str
                or "Service Unavailable" in error_str
            )

            retry_after = None
            if hasattr(e, "response") and getattr(e.response, "headers", None):
                retry_after = e.response.headers.get("Retry-After") or e.response.headers.get("retry-after")
                try:
                    retry_after = int(retry_after) if retry_after is not None else None
                except Exception:
                    retry_after = None

            if attempt < max_retries - 1:
                if retry_after:
                    wait = retry_after
                else:
                    wait = base_delay * (2 ** attempt)
                    wait = wait + random.uniform(0, min(wait, 10))
                print(f"  Rate limit (429) — attempt {attempt+1}/{max_retries}, sleeping {wait:.1f}s")
                time.sleep(wait)
                continue
            raise

    raise RuntimeError(f"Failed after {max_retries} attempts")


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """Atomically write JSON to disk (write temp file then os.replace)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=p.name + ".tmp.", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(p))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helper: Extract JSON from markdown code blocks
# ---------------------------------------------------------------------------


def extract_json_from_text(text: str) -> str:
    """
    Extract JSON from text that might be wrapped in markdown code blocks:
      ```json
      [...]
      ```
    """
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


# ---------------------------------------------------------------------------
# Helper: Escape curly braces in injected context strings for CrewAI .format()
# ---------------------------------------------------------------------------


def escape_curly_braces(s: str) -> str:
    """Escape braces for TWO `.format()` passes."""
    if s is None:
        return ""
    return s.replace("{", "{{{{").replace("}", "}}}}")

# ---------------------------------------------------------------------------
# Template placeholder helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def extract_placeholders_from_text(s: str) -> List[str]:
    """Return sorted unique placeholders found in a string, e.g. ['batsman','bowler']."""
    if not s:
        return []
    return sorted(set(_PLACEHOLDER_RE.findall(s)))


def ensure_template_variables(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure template['variables'] includes all placeholders found in template['query']
    and template['question']. Mutates template in-place and returns it.
    Adds a debugging key '_auto_fixed_vars' when new vars are added.
    """
    if not isinstance(template, dict):
        return template

    declared = template.get("variables") or []
    if not isinstance(declared, list):
        try:
            declared = list(declared)
        except Exception:
            declared = []

    placeholders = set()
    placeholders.update(extract_placeholders_from_text(template.get("query", "")))
    placeholders.update(extract_placeholders_from_text(template.get("question", "")))

    missing = sorted(p for p in placeholders if p not in declared)
    if missing:
        declared.extend(missing)
        template["variables"] = declared
        template.setdefault("_auto_fixed_vars", []).extend(missing)
    return template


# ---------------------------------------------------------------------------
# Local LLM
# ---------------------------------------------------------------------------

def _get_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        # If you REALLY want to allow inline keys, you can set it here,
        # but env var is strongly recommended.
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
    return key


# ---------------------------------------------------------------------------
# Helper: Create LLM with random temperature
# ---------------------------------------------------------------------------

def make_llm_with_random_temp(
    model: str = "gemini/gemini-2.5-flash-lite",
    t_min: float = 0.6,
    t_max: float = 1.1,
) -> LLM:
    """Create a new LLM instance with a randomly sampled temperature."""
    temp = round(random.uniform(t_min, t_max), 2)
    print(f"[LLM] Using temperature={temp}")
    return LLM(
        model=model,
        api_key=_get_gemini_key(),
        temperature=temp,
    )


# ---------------------------------------------------------------------------
# Tool wrappers for CrewAI
# ---------------------------------------------------------------------------

class SimpleTool(BaseTool):
    """Minimal BaseTool wrapper around a Python callable."""

    name: str
    description: str
    fn: Callable[..., str]

    def _run(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        return self.fn(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)


def _load_templates_impl(**_: Any) -> str:
    templates = load_templates()
    # ensure variables align with placeholders found in query/question
    fixed = []
    for t in templates:
        try:
            fixed.append(ensure_template_variables(t))
        except Exception:
            fixed.append(t)
    # truncate paraphrases to avoid huge context
    for t in fixed[:50]:
        if "paraphrases" in t and isinstance(t["paraphrases"], list):
            t["paraphrases"] = t["paraphrases"][:5]
    return pretty_json(fixed, max_chars=8000)


def _list_csvs_impl(base_dir: str | None = None, **_: Any) -> str:
    root = Path(base_dir) if base_dir is not None else CRICKET_TABLE_DIR
    paths = [str(p) for p in list_csvs(root)]
    return "\n".join(paths)


def _sample_table_schema_impl(csv_path: str, n_rows: int = 5, **_: Any) -> str:
    info = sample_table_schema(Path(csv_path), n_rows=n_rows)
    return pretty_json(info)


def _run_sql_on_df_impl(sql: str, csv_path: str, **_: Any) -> str:
    result = run_sql_on_df(sql, Path(csv_path))
    return pretty_json(result, max_chars=4000)


load_templates_tool = SimpleTool(
    name="load_templates_tool",
    description="Load representative SQL+NL templates to use as inspiration.",
    fn=_load_templates_impl,
)

list_csvs_tool = SimpleTool(
    name="list_csvs_tool",
    description="List available cricket CSV files to be queried as table 'df'.",
    fn=_list_csvs_impl,
)

sample_table_schema_tool = SimpleTool(
    name="sample_table_schema_tool",
    description="Given a CSV path, return JSON describing columns and preview rows.",
    fn=_sample_table_schema_impl,
)

run_sql_on_df_tool = SimpleTool(
    name="run_sql_on_df_tool",
    description="Execute SQL against the CSV registered as DuckDB table 'df'.",
    fn=_run_sql_on_df_impl,
)


# ---------------------------------------------------------------------------
# Optional: Diversity templates from CSV (1000-bank)
# ---------------------------------------------------------------------------

def _extract_vars_from_sql(sql: str) -> List[str]:
    if not sql:
        return []
    return sorted(set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", sql)))


@lru_cache(maxsize=8)
def load_diversity_templates_from_csv(diversity_csv_path: str) -> List[Dict[str, Any]]:
    """
    Load a diverse bank from a CSV.

    Expected columns (best-effort):
      - question_template OR question
      - sql_template OR sql
      - category (optional)

    Returns a list of template dicts shaped similarly to your human template objects.
    """
    p = Path(diversity_csv_path)
    if not p.exists():
        return []

    items: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            q = (row.get("question_template") or row.get("question") or "").strip()
            sql = (row.get("sql_template") or row.get("sql") or "").strip()
            cat = (row.get("category") or "").strip() or "diversity"
            if not (q or sql):
                continue
            items.append(
                {
                    "id": f"div_{i+1}",
                    "category": cat,
                    "question": q,
                    "query": sql,
                    "variables": _extract_vars_from_sql(sql),
                    "primary_key": None,
                }
            )
    return items


def sample_diversity_templates(
    bank: List[Dict[str, Any]],
    k: int = 4,
    avoid_categories: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Pick up to k templates preferring distinct categories."""
    if not bank or k <= 0:
        return []

    avoid = set([c for c in (avoid_categories or []) if c])

    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for t in bank:
        cat = str(t.get("category") or "diversity")
        by_cat.setdefault(cat, []).append(t)

    cats = [c for c in by_cat.keys() if c not in avoid] or list(by_cat.keys())
    random.shuffle(cats)

    picked: List[Dict[str, Any]] = []
    for c in cats:
        if len(picked) >= k:
            break
        picked.append(random.choice(by_cat[c]))

    if len(picked) < k:
        pool = bank[:]
        random.shuffle(pool)
        for t in pool:
            if len(picked) >= k:
                break
            if t not in picked:
                picked.append(t)

    return picked[:k]


# ---------------------------------------------------------------------------
# Prefetch context helper (schema/templates injected)
# ---------------------------------------------------------------------------

def build_sql_gen_context(
    csv_path: str,
    template: Dict[str, Any] | None = None,
    diversity_csv_path: str | None = None,
    diversity_k: int = 4,
    seen_query_canonicals_json: str | None = None,
) -> Dict[str, str]:
    """
    Build the injection context for SQL generation prompt.

    - templates_json: either all templates (truncated) or just [template]
    - schema_json: schema + preview rows
    - diversity_templates_json: sampled from a CSV bank (optional)
    - seen_query_canonicals_json: prompt-level dedupe memory (optional, best-effort)
    """
    if template:
        # ensure template variables are consistent with placeholders in text/sql
        try:
            template = ensure_template_variables(template)
        except Exception:
            pass
        templates_json = pretty_json([template], max_chars=8000)
    else:
        templates_json = _load_templates_impl()

    schema_json = _sample_table_schema_impl(csv_path=csv_path, n_rows=1)

    diversity_templates_json = "[]"
    if diversity_csv_path:
        bank = load_diversity_templates_from_csv(diversity_csv_path)
        avoid = []
        if template and isinstance(template, dict) and template.get("category"):
            avoid = [str(template.get("category"))]
        picked = sample_diversity_templates(bank, k=diversity_k, avoid_categories=avoid)
        diversity_templates_json = pretty_json(picked, max_chars=8000)

    if seen_query_canonicals_json is None:
        seen_query_canonicals_json = "[]"

    # IMPORTANT: CrewAI formats Task descriptions with .format(**inputs).
    # Any `{var}` inside these injected JSON strings would be treated as a missing template variable.
    templates_json = escape_curly_braces(templates_json)
    schema_json = escape_curly_braces(schema_json)
    diversity_templates_json = escape_curly_braces(diversity_templates_json)
    seen_query_canonicals_json = escape_curly_braces(seen_query_canonicals_json)

    return {
        "templates_json": templates_json,
        "schema_json": schema_json,
        "diversity_templates_json": diversity_templates_json,
        "seen_query_canonicals_json": seen_query_canonicals_json,
    }


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

# sql_generator = Agent(
#     name="TemplateInspiredSQLGenerator",
#     role="SQL Template Generator",
#     goal=(
#         "Generate new, correct DuckDB SQL queries against a single table 'df', "
#         "inspired by existing templates, while respecting the provided schema context."
#     ),
#     backstory=(
#         "You study cricket SQL templates and create novel but structurally related queries. "
#         "You avoid copies and introduce diversity while staying consistent with available columns. "
#         "You ONLY query table 'df'."
#     ),
#     tools=[load_templates_tool, list_csvs_tool, sample_table_schema_tool],
#     llm=llm,
#     allow_delegation=False,
#     verbose=True,
# )

# nl_generator = Agent(
#     name="NaturalLanguageQuestionGenerator",
#     role="NL Generator",
#     goal=(
#         "Given a SQL query and schema context, generate a clear natural language question "
#         "plus exactly 3 paraphrases in the style of the existing cricket templates."
#     ),
#     backstory=(
#         "You write cricket-focused questions matching the SQL semantics, never mentioning SQL or tables."
#     ),
#     tools=[sample_table_schema_tool],
#     llm=local_llm,
#     allow_delegation=False,
#     verbose=True,
# )

# validator = Agent(
#     name="SQLValidator",
#     role="SQL Runner & Validator",
#     goal="Execute SQL queries against df and report whether they run and return reasonable results.",
#     backstory="You are strict and detail-oriented. You run SQL, capture errors, and sanity-check outputs.",
#     tools=[run_sql_on_df_tool],
#     llm=local_llm,
#     allow_delegation=False,
#     verbose=True,
# )

# fixer = Agent(
#     name="SQLAndNLFixer",
#     role="SQL Repair & Question Refiner",
#     goal=(
#         "Fix failing SQL to run correctly on DuckDB df, using schema inspection tools. "
#         "Update NL question/paraphrases if semantics changed."
#     ),
#     backstory="You debug SQL professionally and ensure NL matches the final SQL semantics.",
#     tools=[run_sql_on_df_tool, sample_table_schema_tool],
#     llm=local_llm,
#     allow_delegation=False,
#     verbose=True,
# )


# ---------------------------------------------------------------------------
# Output schemas (lightly strict)
# ---------------------------------------------------------------------------

SQL_GEN_SCHEMA = {
    "type": "array",
    "minItems": 3,
    "maxItems": 10,
    "items": {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "structure": {"type": "string"},
            "sql": {"type": "string"},
            "description": {"type": "string"},
            "variables": {"type": "array"},
            "primary_key": {"type": ["string", "array", "null"]},
        },
        "required": ["intent", "structure", "sql", "description", "variables", "primary_key"],
        "additionalProperties": True,
    },
}

NL_GEN_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "question": {"type": "string"},
            "paraphrases": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": ["item_id", "question", "paraphrases"],
        "additionalProperties": True,
    },
}


# ---------------------------------------------------------------------------
# Crews
# ---------------------------------------------------------------------------

def make_sql_gen_crew() -> Crew:
    """
    SQL generator crew. Inputs required:
      - schema_json
      - templates_json
      - diversity_templates_json
      - seen_query_canonicals_json
    """
    llm = make_llm_with_random_temp(t_min=0.7, t_max=1.8)
    sql_generator = Agent(
        name="TemplateInspiredSQLGenerator",
        role="SQL Template Generator",
        goal=(
            "Generate new, correct DuckDB SQL queries against a single table 'df', "
            "inspired by existing templates, while respecting the provided schema context."
        ),
        backstory=(
            "You study cricket SQL templates and create novel but structurally related queries. "
            "You avoid copies and introduce diversity while staying consistent with available columns. "
            "You ONLY query table 'df'."
        ),
        tools=[load_templates_tool, list_csvs_tool, sample_table_schema_tool],
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    task_generate_sql = Task(
        description=dedent(
            """
            You are generating NEW, DISTINCT SQL queries for cricket BALL-BY-BALL data.

            The CSV is registered as a DuckDB table named `df`.
            Each row represents ONE DELIVERY.

            You must follow ALL rules below. Any violation makes the output INVALID.

            ════════════════════════════════════════════════════════
            CRITICAL SEMANTIC RULE ABOUT THE `overs` COLUMN
            ════════════════════════════════════════════════════════

            The column `overs` represents BALL-BY-BALL delivery order,
            NOT an integer over identifier.

            It is encoded as:
            <over_number>.<ball_number>

            Examples:
            - 0.1, 0.2, ..., 0.6   → first over (6 balls)
            - 1.1, 1.2, ..., 1.6   → second over
            - 12.3                → 3rd ball of the 13th over

            MANDATORY RULES (STRICT):
            - `overs` ALONE refers to a DELIVERY INDEX.
            - NEVER treat `overs` as an over number.
            - To compute OVER NUMBER, ALWAYS use:
                CEIL(overs)
            - NEVER group by `overs` when you mean over-level analysis.
            - Grouping by `overs` is ONLY valid for ball-level analysis.
            - To analyze ball sequence or momentum, ORDER BY `overs`.
            - To compute runs/wickets per over, GROUP BY CEIL(overs).
            - For phase analysis (early/middle/late), phases MUST be defined
            using CEIL(overs), NOT overs directly.

            INVALID SQL EXAMPLES:
            - SELECT overs, SUM(team_runs) FROM df GROUP BY overs
            - SELECT overs, COUNT(*) FROM df GROUP BY overs

            ════════════════════════════════════════════════════════
            NO SELF-MADE ROW IDENTITIES / DERIVED CONCEPTS MUST BE COLUMNS
            ════════════════════════════════════════════════════════

            STRICT RULES:
            - Do NOT invent row IDs or synthetic identifiers.
              Avoid creating keys like delivery_id, row_id, over_id from ROW_NUMBER(), UUIDs, or arbitrary hashing.
            - If you need ordering, ORDER BY `overs` (delivery index) instead of creating a row identity.
            - Any derived concept MUST be expressed as a derived COLUMN with an alias.
              Examples of allowed derived columns:
                - `CEIL(overs) AS over_no`
                - `CASE WHEN bowler_wickets > 0 THEN 1 ELSE 0 END AS is_wicket_ball`
                - `CASE WHEN CEIL(overs) <= 6 THEN 'Early' ... END AS phase`

            WIDE OUTPUT PREFERENCE FOR BINARY COMPARISONS:
            - If your analysis compares exactly TWO categories (binary split), prefer a SINGLE ROW with TWO or MORECOLUMNS
              using conditional aggregation instead of returning category rows.

            INVALID (row categories) — AVOID WHEN BINARY:
            - Returning rows like ('Wicket Over', value) and ('Non-Wicket Over', value) is discouraged when a wide
              2-column output is feasible.
            - Let there be as many numeric columns as possible in the output other than primary key columns.

            ════════════════════════════════════════════════════════
            GROUND TRUTH CONTEXT
            ════════════════════════════════════════════════════════

            === TABLE SCHEMA (AUTHORITATIVE) ===
            {schema_json}

            === BASE INTENT TEMPLATE (SEMANTIC INSPIRATION ONLY) ===
            This template is provided ONLY to understand the TYPE of analysis.
            You MUST NOT copy its SQL structure or aggregation pattern.

            {templates_json}

            === DIVERSITY IDEAS (MANDATORY INSPIRATION) ===
            These are additional random idea prompts sampled from a CSV bank to encourage diversity.
            Use them for SEMANTIC inspiration only; do NOT copy any SQL structure from them.

            {diversity_templates_json}

            === AVOIDED QUERY PATTERNS (DO NOT REPEAT) ===
            These represent SQL SHAPES already used.
            Any query that is structurally similar is INVALID.

            {seen_query_canonicals_json}

            ════════════════════════════════════════════════════════
            CORE GENERATION PHILOSOPHY
            ════════════════════════════════════════════════════════

            IMPORTANT:
            - You MUST generate SQL that is LOGICALLY . INTENTIONALLY and STRUCTURALLYNEW.
            - Minor edits (column swaps, ORDER BY changes, LIMIT changes)
            DO NOT count as new queries.
            - If a query could be described as a “small variation”
            of an avoided pattern, it is INVALID.

            You MUST follow the 3-STEP PROCESS below FOR EACH QUERY.

            ════════════════════════════════════════════════════════
            MANDATORY 3-STEP PROCESS (FOR EACH QUERY)
            ════════════════════════════════════════════════════════

            STEP 1 — INTENT (NO SQL):
            Describe a NEW analytical question in plain English.
            - It must not be equivalent to previous questions.
            - Focus on insight, not simple totals.
            - Examples of good focus:
            pressure, momentum, efficiency, change over time, imbalance, variation.

            STEP 2 — STRUCTURE (NO SQL):
            Describe the abstract query shape using ONLY concepts:
            - grouping dimensions (e.g., by batsman, by bowler, by CEIL(overs), by phase)
            - aggregation types (sum, avg, count, ratio, cumulative, rank)
            - whether it uses:
                - window functions
                - CTEs
                - CASE expressions
                - subqueries
            DO NOT write SQL here.

            STEP 3 — SQL:
            Write the DuckDB SQL that EXACTLY implements the above structure.
            - Use ONLY table `df`.
            - Use ONLY columns present in the schema.
            - Apply CEIL(overs) correctly when required.
            - Include placeholders ONLY if variables exist.
            - Ensure SQL semantics exactly match the stated intent and structure.

            ════════════════════════════════════════════════════════
            HARD STRUCTURAL CONSTRAINTS (STRICT)
            ════════════════════════════════════════════════════════

            Across the 10 queries you generate:

            - At least 3 queries MUST have DIFFERENT:
                (grouping + aggregation) combinations.

            - At least 1 queries MUST use ONE OR MORE of:
                - window functions
                - CTEs
                - CASE-based bucketing (using CEIL(overs))

            - At least 1 query MUST analyze:
                - ball sequence, streaks, or momentum using ORDER BY overs.
                
            - VARIABLE PLACEHOLDER REQUIREMENT (STRICT):
              * Exactly ONE of the 10 queries MUST include at least one placeholder variable in the SQL using SINGLE curly braces,
                choosing from: batsman and/or bowler.
              * The placeholder(s) MUST appear in a filter condition (WHERE / JOIN / CASE) such as comparing to `batsman` or `bowler` columns.
              * Use the placeholders exactly as batsman and/or bowler (single curly braces). Do NOT invent other placeholder names.
              * The output item's `variables` array MUST list exactly the placeholders used in that SQL (e.g., ["batsman"] or ["bowler"] or ["batsman","bowler"]).
              * The other 4 queries MUST have `variables: []` and MUST NOT contain any `{...}` placeholders.

            - Queries that differ ONLY by:
                column names, ordering, or limits
            are INVALID.

            ════════════════════════════════════════════════════════
            SELF-CHECK (MANDATORY BEFORE FINAL OUTPUT)
            ════════════════════════════════════════════════════════

            Before returning results, verify:
            - No query matches or resembles an avoided pattern.
            - `overs` is used according to the semantic rules.
            - Each query has a distinct analytical purpose.
            - SQL structure matches the stated intent and structure.

            ════════════════════════════════════════════════════════
            PRIMARY_KEY INSTRUCTION:
            - For each output item, analyze the SQL you produced and set `primary_key` to the list of column names or selected aliases that uniquely identify each result row (the query's output grain).
            - If the query returns a single aggregated row or wide-format metrics with no identifying dimensions, set primary_key to null.
            - Do NOT invent keys; only use selected columns or aliases present in the SQL.

            ════════════════════════════════════════════════════════
            OUTPUT FORMAT (JSON ONLY)
            ════════════════════════════════════════════════════════

            Return a JSON array of EXACTLY 10 objects.

            Each object MUST contain:
            - intent        (string)
            - structure     (string)
            - sql           (string)
            - description   (string)
            - variables     (array)
            - primary_key   (string | array | null)

            DO NOT include markdown.
            DO NOT include explanations outside JSON.
            Each SQL MUST include: FROM df
            """
        ).strip(),
        agent=sql_generator,
        expected_output_type="json",
        expected_output_schema=SQL_GEN_SCHEMA,
        expected_output="JSON array of 10 objects with sql, description, variables, primary_key",
    )
    return Crew(agents=[sql_generator], tasks=[task_generate_sql], verbose=True)


def make_nl_crew() -> Crew:
    llm = make_llm_with_random_temp(t_min=0.3, t_max=0.6)
    nl_generator = Agent(
        name="NaturalLanguageQuestionGenerator",
        role="NL Generator",
        goal=(
            "Given a SQL query and schema context, generate a clear natural language question "
            "plus exactly 3 paraphrases in the style of the existing cricket templates."
        ),
        backstory=(
            "You write cricket-focused questions matching the SQL semantics, never mentioning SQL or tables."
        ),
        tools=[sample_table_schema_tool],
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    task_generate_nl = Task(
        description=dedent(
            """
            You are generating natural language questions for validated SQL queries.

            The table is `df`.
            Each row represents ONE DELIVERY.

            IMPORTANT SEMANTIC NOTE ABOUT `overs`:
            - `overs` is a ball-by-ball delivery index encoded as over.ball (e.g., 12.3).
            - `FLOOR(overs)` represents over number.
            - If the SQL uses `overs` directly (not FLOOR(overs)), do NOT describe it as over number.

            === VALIDATED SQL ITEMS (GROUND TRUTH) ===
            {items_json}

            Input format:
            - Each item includes: item_id, sql, description, variables, primary_key

            For each input item:
              - Generate ONE primary question and EXACTLY 3 paraphrases.
              - The question MUST precisely describe what the SQL returns.
              - The question MUST include ALL assumptions/definitions required to recreate the SQL in natural language.
                This includes (when present in SQL):
                  * any CASE bucket definitions and their exact thresholds,
                  * how an over key is derived from `overs` (e.g., over_no = CEIL(overs)),
                  * any window partitioning grain (e.g., "within each over_no"),
                  * any filters (WHERE conditions) and their exact ranges,
                  * any joins/CTEs logic expressed as natural-language assumptions.
              - Each of the EXACTLY 3 paraphrases MUST also include the SAME assumptions/definitions (do not omit them).
              - Do not add cricket concepts not implied by SQL; only restate what the SQL assumes.
              - If variables exist, keep placeholders wrapped in single curly braces in the questions/paraphrases.
              - Do NOT mention SQL, tables, DuckDB, or the word "query".

            OUTPUT FORMAT (STRICT):
            Return a JSON array of the same length as the input.
            Each output element MUST contain ONLY:
              - item_id
              - question
              - paraphrases

            Do NOT echo back sql/description/variables/primary_key/original_sql/params.
            Return JSON only.
            """
        ).strip(),
        agent=nl_generator,
        expected_output_type="json",
        expected_output_schema=NL_GEN_SCHEMA,
        expected_output="JSON array of items with item_id + question + 3 paraphrases",
    )
    return Crew(agents=[nl_generator], tasks=[task_generate_nl], verbose=True)


def make_fix_crew() -> Crew:
    llm = make_llm_with_random_temp(t_min=0.1, t_max=0.3)
    fixer = Agent(
        name="SQLAndNLFixer",
        role="SQL Repair & Question Refiner",
        goal=(
            "Fix failing SQL to run correctly on DuckDB df, using schema inspection tools. "
            "Update NL question/paraphrases if semantics changed."
        ),
        backstory="You debug SQL professionally and ensure NL matches the final SQL semantics.",
        tools=[run_sql_on_df_tool, sample_table_schema_tool],
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    task_fix = Task(
        description=dedent(
            """
            You receive a JSON array in `items_json`. Each item has:
              sql, description, csv_path, question, paraphrases, validation

            For each item:
              - If validation.ok == true and validation.row_count >= 1, keep ENTIRE item as-is.
              - Otherwise:
                  * Fix SQL to run on DuckDB table `df`.
                  * Use sample_table_schema_tool(csv_path, n_rows=2) if needed.
                  * Re-run run_sql_on_df_tool to confirm and copy tool output to validation.
                  * Only update question/paraphrases if semantics changed.

            Return JSON array only (same length).
            """
        ).strip(),
        agent=fixer,
        expected_output_type="json",
        expected_output="JSON array of fixed items",
    )
    return Crew(agents=[fixer], tasks=[task_fix], verbose=True)


# ---------------------------------------------------------------------------
# Pure-Python validator
# ---------------------------------------------------------------------------

def validate_sql_items(items: List[Dict[str, Any]], csv_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Run SQL on df and attach validation results.
    Returns (ok_items, bad_items) where ok has ok==True and row_count>=1.
    """
    ok_items: List[Dict[str, Any]] = []
    bad_items: List[Dict[str, Any]] = []

    for item in items:
        sql = item.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            val = {"ok": False, "error": "missing sql", "row_count": None, "columns": None}
            bad_items.append({**item, "validation": val})
            continue

        validation = run_sql_on_df(sql, Path(csv_path))
        item_with_val = {**item, "validation": validation}

        if validation.get("ok") and (validation.get("row_count") or 0) >= 1:
            ok_items.append(item_with_val)
        else:
            bad_items.append(item_with_val)

    return ok_items, bad_items


# ---------------------------------------------------------------------------
# Optional: classic 1-template processing (kept for compatibility)
# ---------------------------------------------------------------------------

def kickoff_for_csv(
    csv_path: str,
    progress_json_path: str | None = None,
    diversity_csv_path: str | None = None,
    diversity_k: int = 4,
    sleep_between_sql_and_nl_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Classic run: iterate templates once. (Not enough for 5k; use your dedup runner for that.)
    """
    all_templates = load_templates()

    all_final_items: List[Dict[str, Any]] = []
    all_bad_items: List[Dict[str, Any]] = []

    def _checkpoint(stage: str, template_id: str | None = None) -> None:
        if not progress_json_path:
            return
        payload: Dict[str, Any] = {
            "csv_path": csv_path,
            "updated_at": int(time.time()),
            "stage": stage,
            "template_id": template_id,
            "total_templates": len(all_templates),
            "total_generated": len(all_final_items),
            "total_failed": len(all_bad_items),
            "final": all_final_items,
            "failed": all_bad_items,
        }
        _atomic_write_json(progress_json_path, payload)

    for template_idx, template in enumerate(all_templates):
        print(f"Processing template {template_idx} of {len(all_templates)}")
        print(f"Sleeping for 60 seconds to reduce 429s...")
        time.sleep(60)

        sql_gen_crew = make_sql_gen_crew()
        nl_crew = make_nl_crew()

        inputs = build_sql_gen_context(
            csv_path,
            template=template,
            diversity_csv_path=diversity_csv_path,
            diversity_k=diversity_k,
            seen_query_canonicals_json="[]",
        )

        try:
            gen_out = retry_on_429(sql_gen_crew.kickoff, max_retries=5, base_delay=60, inputs=inputs)
            gen_text = str(gen_out.raw) if hasattr(gen_out, "raw") else str(gen_out)
            cleaned = extract_json_from_text(gen_text)
            sql_items: List[Dict[str, Any]] = json.loads(cleaned)
        except Exception as e:
            print(f"Error generating SQL for template {template.get('id')}: {e}")
            _checkpoint(stage="sql_generation_failed", template_id=str(template.get("id")))
            continue

        template_primary_key = template.get("primary_key", None)
        for it in sql_items:
            it["primary_key"] = template_primary_key

        sql_items = [it for it in sql_items if "df" in str(it.get("sql", "")).lower()]
        if not sql_items:
            _checkpoint(stage="no_valid_sql", template_id=str(template.get("id")))
            continue

        # initialize + validate
        try:
            instantiated_items = initialize_sql_items(sql_items, csv_path, num_instantiations=1)
        except Exception as e:
            print(f"Error initializing variables: {e}")
            _checkpoint(stage="param_init_failed", template_id=str(template.get("id")))
            continue

        ok_items, bad_items = validate_sql_items(instantiated_items, csv_path)
        all_bad_items.extend(bad_items)

        if not ok_items:
            _checkpoint(stage="no_passing_sql", template_id=str(template.get("id")))
            continue

        # Assign a stable item_id for joining NL outputs back to validated SQL items
        ok_items_for_nl: List[Dict[str, Any]] = []
        for i, item in enumerate(ok_items):
            item_id = item.get("item_id")
            if not isinstance(item_id, str) or not item_id.strip():
                item_id = f"{template.get('id')}_{i}"
            item["item_id"] = item_id

            # NL generator gets only what it needs for grounding
            ok_items_for_nl.append(
                {
                    "item_id": item_id,
                    "sql": item.get("sql", ""),
                    "description": item.get("description", ""),
                    "variables": item.get("variables", []),
                    "primary_key": item.get("primary_key", None),
                }
            )

        nl_in = pretty_json(ok_items_for_nl, max_chars=None)
        # Escape braces so placeholders like {batsman} inside SQL don't break CrewAI formatting
        nl_in = escape_curly_braces(nl_in)

        # Throttle between SQL generation/validation and NL generation to reduce 429s
        if sleep_between_sql_and_nl_seconds and sleep_between_sql_and_nl_seconds > 0:
            print(f"Sleeping {sleep_between_sql_and_nl_seconds}s before NL generation to reduce 429s...")
            time.sleep(sleep_between_sql_and_nl_seconds)

        try:
            nl_out = retry_on_429(nl_crew.kickoff, max_retries=5, base_delay=60, inputs={"items_json": nl_in})
            nl_text = str(nl_out.raw) if hasattr(nl_out, "raw") else str(nl_out)
            cleaned = extract_json_from_text(nl_text)
            nl_items: List[Dict[str, Any]] = json.loads(cleaned)

            # Build lookup from item_id -> NL fields
            nl_by_id: Dict[str, Dict[str, Any]] = {}
            for x in nl_items:
                iid = x.get("item_id")
                if isinstance(iid, str) and iid.strip():
                    nl_by_id[iid] = x

            final: List[Dict[str, Any]] = []
            for item in ok_items:
                print(item)
                iid = item.get("item_id")
                if not isinstance(iid, str) or iid not in nl_by_id:
                    continue

                # Start from validated SQL item (excluding validation payload)
                merged = {k: v for k, v in item.items() if k != "validation"}

                # Merge NL outputs (question/paraphrases)
                merged["question"] = nl_by_id[iid].get("question", "")
                merged["paraphrases"] = nl_by_id[iid].get("paraphrases", [])

                # Add metadata
                merged["template_id"] = template.get("id")
                if "primary_key" not in merged:
                    merged["primary_key"] = template_primary_key

                final.append(merged)

            all_final_items.extend(final)
            _checkpoint(stage="template_ok", template_id=str(template.get("id")))
        except Exception as e:
            print(f"Error generating NL for template {template.get('id')}: {e}")
            _checkpoint(stage="nl_generation_failed", template_id=str(template.get("id")))

    _checkpoint(stage="all_done", template_id=None)
    return {
        "final": all_final_items,
        "failed": all_bad_items,
        "total_templates": len(all_templates),
        "total_generated": len(all_final_items),
    }


__all__ = [
    "retry_on_429",
    "_atomic_write_json",
    "extract_json_from_text",
    "build_sql_gen_context",
    "make_sql_gen_crew",
    "make_nl_crew",
    "make_fix_crew",
    "validate_sql_items",
    "kickoff_for_csv",
    "sql_generator",
    "nl_generator",
    "validator",
    "fixer",
]
