"""
CrewAI agents and tools for template-inspired SQL & NL generation, validation,
and repair against your cricket tables.

Flow: SQL generation (LLM, with schema+templates injected) ->
      Validate (pure Python) ->
      Fix failing SQL once (LLM) ->
      Re-validate (pure Python) ->
      NL generation for passing items (LLM)
"""

from __future__ import annotations, generator_stop

import json
import time
from textwrap import dedent
from typing import Any, Dict, Callable, List, Tuple, Optional
from pathlib import Path
import os
import tempfile

from crewai import Agent, Crew, Task, LLM
from crewai.tools import BaseTool

from sql_agent_tools import (
    CRICKET_TABLE_DIR,
    TEMPLATE_FILE,
    list_csvs,
    load_templates,
    pretty_json,
    run_sql_on_df,
    sample_table_schema,
)
from sql_param_initializer import initialize_sql_items


# ---------------------------------------------------------------------------
# Helper: Retry wrapper for API calls with 429 handling
# ---------------------------------------------------------------------------
import random
import math

def retry_on_429(func: Callable, max_retries: int = 5, base_delay: int = 2, *args, **kwargs):
    import sys
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            if hasattr(result, 'raw'):
                _ = result.raw
            sys.stdout.flush()
            sys.stderr.flush()
            time.sleep(1)
            return result
        except Exception as e:
            # detect 429
            error_str = str(e).lower()
            print(f"  Error: {error_str}")
            is_429 = ("429" in error_str or "rate limit" in error_str or "quota exceeded" in error_str
                      or "too many requests" in error_str or "resource exhausted" in error_str)
            # check headers if available
            retry_after = None
            if hasattr(e, "response") and getattr(e.response, "headers", None):
                retry_after = e.response.headers.get("Retry-After") or e.response.headers.get("retry-after")
                try:
                    retry_after = int(retry_after) if retry_after is not None else None
                except Exception:
                    retry_after = None
            if is_429 and attempt < max_retries - 1:
                if retry_after:
                    wait = retry_after
                else:
                    # exponential backoff with jitter
                    wait = base_delay * (2 ** attempt)
                    wait = wait + random.uniform(0, min(wait, 10))
                print(f"  Rate limit (429) — attempt {attempt+1}/{max_retries}, sleeping {wait:.1f}s")
                time.sleep(wait)
                continue
            else:
                raise
    raise Exception(f"Failed after {max_retries} attempts")



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
        # If replace failed, cleanup tmp.
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
    Extract JSON from text that might be wrapped in markdown code blocks.
    Handles cases like:
      ```json\n[...]\n```
      ```\n[...]\n```
      Just plain JSON
    """
    text = text.strip()
    
    # Remove markdown code block markers
    if text.startswith("```"):
        # Find the closing ```
        lines = text.split("\n")
        # Remove first line (```json or ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    
    return text.strip()


# ---------------------------------------------------------------------------
# Local LLM configuration
# ---------------------------------------------------------------------------

def _get_gemini_key() -> str:
    """Return the Gemini key from the environment, never from source code."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
    return key


local_llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=_get_gemini_key(),
    temperature=0.6,
)


# ---------------------------------------------------------------------------
# Tool wrappers to expose to CrewAI agents
# ---------------------------------------------------------------------------

class SimpleTool(BaseTool):
    """
    Minimal BaseTool wrapper around a Python callable so CrewAI can validate it.
    """

    name: str
    description: str
    fn: Callable[..., str]

    def _run(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        return self.fn(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)


def _load_templates_impl(**_: Any) -> str:
    templates = load_templates()
    # Lightly truncate paraphrases to avoid blowing up context
    for t in templates[0:30]:
        if "paraphrases" in t and isinstance(t["paraphrases"], list):
            t["paraphrases"] = t["paraphrases"][:5]
    return pretty_json(t, max_chars=8000)


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


# Expose BaseTool instances for Agents (unchanged)
load_templates_tool = SimpleTool(
    name="load_templates_tool",
    description=(
        "Load representative SQL+NL templates from template_q_param_cricket_pk.py "
        "to use as inspiration when generating new queries."
    ),
    fn=_load_templates_impl,
)

list_csvs_tool = SimpleTool(
    name="list_csvs_tool",
    description=(
        "List available cricket CSV files that can be queried as table 'df'. "
        "Optionally accepts a base_dir string."
    ),
    fn=_list_csvs_impl,
)

sample_table_schema_tool = SimpleTool(
    name="sample_table_schema_tool",
    description=(
        "Given a CSV path, return a JSON description of its columns and a few "
        "preview rows. Helps understand which fields can be used in SQL."
    ),
    fn=_sample_table_schema_impl,
)

run_sql_on_df_tool = SimpleTool(
    name="run_sql_on_df_tool",
    description=(
        "Execute a SQL query against a CSV (registered as table 'df' in duckdb) "
        "and return JSON with ok/error, row_count, columns, and sample_rows."
    ),
    fn=_run_sql_on_df_impl,
)


# ---------------------------------------------------------------------------
# Prefetch context helper (ensures generator can't ignore schema/templates)
# ---------------------------------------------------------------------------

def build_sql_gen_context(csv_path: str, template: Dict[str, Any] = None) -> dict:
    """
    Fetch the template & schema JSON strings in Python so they are injected
    into the LLM prompt as ground-truth context.
    If template is provided, only include that one template.
    """
    if template:
        # Include only the specified template
        templates_json = pretty_json([template], max_chars=8000)
    else:
        templates_json = _load_templates_impl()
    schema_json = _sample_table_schema_impl(csv_path=csv_path, n_rows=3)

    return {
        "templates_json": templates_json,
        "schema_json": schema_json,
    }


# ---------------------------------------------------------------------------
# Agent definitions (kept from your original code)
# ---------------------------------------------------------------------------

sql_generator = Agent(
    name="TemplateInspiredSQLGenerator",
    role="SQL Template Generator",
    goal=(
        "Generate new, correct SQL queries against a single pandas table 'df', "
        "inspired by existing templates, but with different reasoning keeping in mind the table schema and the context of the match "
        "aggregations, and primary keys when reasonable."
    ),
    backstory=(
        "You study existing cricket SQL templates and create novel but "
        "structurally similar queries. You must avoid exact copies and "
        "introduce diversity while staying consistent with the available "
        "columns. You ONLY query the table named 'df'."
    ),
    tools=[load_templates_tool, list_csvs_tool, sample_table_schema_tool],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

nl_generator = Agent(
    name="NaturalLanguageQuestionGenerator",
    role="NL Generator",
    goal=(
        "Given a SQL query and knowledge of the table schema, generate a clear "
        "natural language question plus 3–5 paraphrases in the same style as "
        "the existing question templates."
    ),
    backstory=(
        "You write cricket-focused questions that exactly match the semantics "
        "of the SQL. You talk about bowlers, batsmen, overs, runs, wickets, "
        "etc., never about SQL or tables."
    ),
    tools=[sample_table_schema_tool],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

# We keep validator/fixer agent definitions available, but we won't use the validator agent
validator = Agent(
    name="SQLValidator",
    role="SQL Runner & Validator",
    goal=(
        "Execute SQL queries against the appropriate CSV as pandas/duckdb using tools provided, "
        "and report whether they run successfully and produce reasonable "
        "output."
    ),
    backstory=(
        "You are strict and detail-oriented. You run the SQL, capture any "
        "errors, and sanity-check outputs for empty or obviously wrong "
        "results."
    ),
    tools=[run_sql_on_df_tool],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)

fixer = Agent(
    name="SQLAndNLFixer",
    role="SQL Repair & Question Refiner",
    goal=(
        "Given a faulty SQL + validator feedback and the original NL question, "
        "fix the SQL to run correctly and match the intended semantics, then "
        "update the natural language question/paraphrases if semantics changed."
    ),
    backstory=(
        "You debug SQL like a pro: you read error messages and adjust SQL to "
        "work with the actual schema. You then ensure the NL question matches "
        "the final SQL."
    ),
    tools=[run_sql_on_df_tool, sample_table_schema_tool],
    llm=local_llm,
    allow_delegation=False,
    verbose=True,
)


# ---------------------------------------------------------------------------
# Task/crew helpers (small crews used by pure-python flow)
# ---------------------------------------------------------------------------

# Strict JSON schema for SQL generator: exactly 5 items with specified fields.
SQL_GEN_SCHEMA = {
    "type": "array",
    "minItems": 3,
    "maxItems": 5,
    "items": {
        "type": "object",
        "properties": {
            "sql": {"type": "string"},
            "description": {"type": "string"},
            "variables": {"type": "array"},
            "primary_key": {"type": ["string", "array", "null"]},
        },
        "required": ["sql", "description", "csv_path"],
        "additionalProperties": True,  # Allow original_sql, params, etc. after initialization
    },
}

# Strict JSON schema for NL generator: array of items with question + paraphrases.
NL_GEN_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "sql": {"type": "string"},
            "description": {"type": "string"},
            "variables": {"type": "array"},
            "primary_key": {"type": ["string", "array", "null"]},
            "question": {"type": "string"},
            "paraphrases": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
            # "validation": {
            #     "type": "object",
            #     "properties": {
            #         "ok": {"type": "boolean"},
            #         "error": {"type": ["string", "null"]},
            #         "row_count": {"type": ["integer", "null"]},
            #         "columns": {"type": ["array", "null"]},
            #     },
            #     "required": ["ok"],
            # },
        },
        "required": ["sql", "description", "question", "paraphrases", "primary_key"],
        "additionalProperties": True,  # Allow original_sql, params, etc.
    },
}


def make_sql_gen_crew() -> Crew:
    """
    Crew that runs the SQL generator LLM task.
    The task expects inputs: csv_path, templates_json, schema_json (we provide them).
    """
    task_generate_sql = Task(
        description=dedent(
            """
            You are generating SQL for the cricket.
            The CSV will be registered as duckdb table `df`.

            You MUST use the following context (these are GROUND TRUTH and were
            extracted from the dataset and templates; do not invent or ignore them):

            === TABLE SCHEMA + PREVIEW ROWS (GROUND TRUTH) ===
            {schema_json}

            === INSPIRATION TEMPLATE (Use this ONE as base inspiration) ===
            {templates_json}

            GOAL:
            - Pick EXACTLY ONE template from templates_json as the base inspiration.
            - Extract the primary_key field from the chosen template (it may be a string, array, or null).
            - Produce 5 NEW, diverse SQL queries for table `df` ONLY, making sure to keep parameters or variables in the queries for us to initialize them.
            - If variables are present in the template, use them in the SQL queries by keeping the placeholders in curly braces format. Do not invent your own variables.
            - Have variable names same as in the template query.
            - Do not replace the variables with actual values from the schema_json.
            - In case of nested queries use With CTEs.
            - Use ONLY column names present in schema_json.columns.
            - Each row in table represents 1 delivery in the match, needs to be aggregated to get for overall match statistics.
            - Queries must be valid DuckDB SQL.
            - Each query should be clearly inspired by the chosen template, but not a copy.
            - Include the primary_key from the chosen template in each output item.

            Return JSON array of length 5:
            [
              {{"sql": "...", "description": "...", "variables": ["..."], "primary_key": [...]}},
              ...
            ]
            Note: primary_key should be copied from the chosen template's primary_key field.

            IMPORTANT: Return JSON only. Each `sql` must include `FROM df`.
            """
        ).strip(),
        agent=sql_generator,
        expected_output_type="json",
        expected_output_schema=SQL_GEN_SCHEMA,
        expected_output="JSON array of 5 objects with sql, description, csv_path fields (must be valid JSON and include FROM df in each sql)",
    )

    return Crew(agents=[sql_generator], tasks=[task_generate_sql], verbose=True)


def make_fix_crew() -> Crew:
    """
    Crew that runs the fixer LLM. Input is a single string variable `items_json`
    which is a JSON array of items with fields sql, description, csv_path, validation.
    The fixer must return a JSON array of items with corrected `sql` and updated `question`/`paraphrases`
    only when semantics changed; otherwise keep items as-is.
    """
    task_fix = Task(
        description=dedent(
            """
            You receive a JSON array in the input variable `items_json`. Each item has:
              sql, description, csv_path, question, paraphrases, validation

            For each item:
              - If validation.ok == true and validation.row_count >= 1, keep the ENTIRE item as-is (including csv_path).
              - Otherwise:
                  * Read validation.error and fix the SQL so it runs successfully
                    on duckdb table `df` (the csv_path was already provided).
                  * When adjusting columns, call sample_table_schema_tool(csv_path, n_rows=2)
                    (this tool is available) and only use column names that exist.
                  * After fixing, re-run run_sql_on_df_tool to confirm success.
                  * Copy the tool's JSON validation output verbatim into the `validation` field.
                  * If the semantics changed, update the `question` and `paraphrases`
                    to match the final SQL.
                  * CRITICAL: Preserve ALL original fields exactly:
                    - csv_path: Copy EXACTLY from input, do NOT change it
                    - description: Copy EXACTLY from input, do NOT change it
                    - variables: Copy EXACTLY from input if present, do NOT change it
                    - original_sql: Copy EXACTLY from input if present, do NOT change it
                    - params: Copy EXACTLY from input if present, do NOT change it
                    - Only modify: sql (if fixing), validation (with tool output), question/paraphrases (if semantics changed)

            IMPORTANT: 
            - Respond with a JSON array ONLY (same shape and length as input)
            - Preserve csv_path exactly as provided in input
            - Do not emit any other text
            """
        ).strip(),
        agent=fixer,
        expected_output_type="json",
        expected_output="JSON array of items with sql, description, csv_path, question (optional), paraphrases (optional), validation (return JSON only)",
    )
    return Crew(agents=[fixer], tasks=[task_fix], verbose=True)


def make_nl_crew() -> Crew:
    """
    Crew that generates NL questions for validated SQL items.
    Input variable: items_json (JSON array of validated items, passed as fixed context).
    """
    task_generate_nl = Task(
        description=dedent(
            """
            You are generating natural language questions for validated SQL queries.

            You MUST use the following context (these are GROUND TRUTH and were
            validated against the dataset; do not invent or ignore them):

            === VALIDATED SQL ITEMS (GROUND TRUTH) ===
            {items_json}

            Each item in the array has:
              - sql: The SQL query (already validated and working, may be instantiated from a template)
              - description: Brief description of what the query does
              - variables: List of variable names (if this was a templated query)
              - primary_key: Primary key field(s) from the inspiration template (string, array, or null)
              - original_sql: Original SQL template with variable placeholders in curly braces format (if applicable)
              - params: Parameter values used to instantiate the SQL (if applicable)
              - validation: Validation results including sample_rows from actual execution

            For each entry:
              - Generate one primary natural language question and exactly 3 paraphrases
                in the same style as the existing cricket templates.
              - Ensure the question precisely describes the SQL's result.
              - Use the validation.sample_rows to understand what the query actually returns.
              - CRITICAL: If 'variables' field has items like (e.g., ['batsman', 'bowler', 'temporal_phrase']), 
                you MUST keep these variable placeholders in curly braces format in your generated questions and paraphrases.
                For example:
                  * If variables includes 'batsman', use the placeholder format with single braces around the word batsman
                  * If variables includes 'bowler', use the placeholder format with single braces around the word bowler
                  * If variables includes 'temporal_phrase', use the placeholder format with single braces around the phrase temporal_phrase
                This matches the template format where variables are placeholders, not actual values.
                DO NOT replace these with actual values from params - keep them as placeholders.
              - Use params values only to understand the context and semantics, but keep the placeholders in output.
              - Do NOT modify the sql, description, csv_path, variables, primary_key, original_sql, params, or validation fields - copy them exactly.

            Respond with a JSON array of the same length as the input:
              [
                {{
                  "sql": "...",  (copy exactly from input)
                  "description": "...",  (copy exactly from input)
                  "variables": ["..."],  (copy exactly from input, if present)
                  "primary_key": "...",  (copy exactly from input, if present)
                  "original_sql": "...",  (copy exactly from input, if present)
                  "params": {{ ... }},  (copy exactly from input, if present)
                  "question": "...",  (your generated question - keep variable placeholders in single-brace format if they exist in the variables list)
                  "paraphrases": ["...", "...", "..."],  (exactly 3 paraphrases - also keep variable placeholders if in variables list)
                }},
                ...
              ]

            IMPORTANT: Return JSON only. Do not hallucinate or modify the input fields.
            
            Example format: If variables list includes "batsman" and "temporal_phrase", 
            the question should contain placeholders in single-brace format like:
              "How many runs did [batsman placeholder] score [temporal_phrase placeholder]?"
            Where [batsman placeholder] means the literal text with single braces around batsman.
            NOT: "How many runs did MW Short score when over is at or before 3.3?"
            (Keep the placeholders as template variables, don't substitute with actual param values)
            """
        ).strip(),
        agent=nl_generator,
        expected_output_type="json",
        expected_output_schema=NL_GEN_SCHEMA,
        expected_output="JSON array of items with question + 3 paraphrases: [{sql, description, question, paraphrases, validation}, ...] (must match input length and preserve all input fields)",
    )
    return Crew(agents=[nl_generator], tasks=[task_generate_nl], verbose=True)


# ---------------------------------------------------------------------------
# Pure-Python validator (uses your run_sql_on_df)
# ---------------------------------------------------------------------------

def validate_sql_items(items: List[Dict[str, Any]], csv_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Attach a `validation` key to each item by running run_sql_on_df(sql, csv_path).
    Returns (ok_items, bad_items) where ok_items have validation.ok == True and row_count >= 1.
    """
    ok_items: List[Dict[str, Any]] = []
    bad_items: List[Dict[str, Any]] = []

    for item in items:
        sql = item.get("sql")
        #csv_path = item.get("csv_path")
        if not sql:
            # malformed item; mark as bad with synthetic validation
            val = {"ok": False, "error": "missing sql", "row_count": None, "columns": None}
            item_with_val = {**item, "validation": val}
            bad_items.append(item_with_val)
            continue

        validation = run_sql_on_df(sql, Path(csv_path))
        item_with_val = {**item, "validation": validation}

        if validation.get("ok") and (validation.get("row_count") or 0) >= 1:
            ok_items.append(item_with_val)
        else:
            bad_items.append(item_with_val)

    return ok_items, bad_items


# ---------------------------------------------------------------------------
# End-to-end kickoff (pure python flow)
# ---------------------------------------------------------------------------

def kickoff_for_csv(csv_path: str, progress_json_path: str | None = None) -> Dict[str, Any]:
    """
    End-to-end runner that processes each template:
      For each template:
        1) Generate 5 SQLs (LLM) with schema+template injected.
        2) Initialize variables in SQL queries.
        3) Validate (pure Python).
        4) Generate NL questions only for passing SQL items (LLM).
        5) Accumulate results.
      Returns all accumulated results.
    """
    # Load all templates
    all_templates = load_templates()
    
    # Accumulate results across all templates
    all_final_items: List[Dict[str, Any]] = []
    all_bad_items: List[Dict[str, Any]] = []

    def _checkpoint(stage: str, template_id: str | None = None) -> None:
        """Write progress after each loop iteration (or error) if path provided."""
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
    
    # Process each template sequentially
    import sys
    
    for template_idx, template in enumerate(all_templates):
        # Sleep before processing each template (except the first one) to ensure spacing
        if template.get('id')<=112:
            print(f"  Skipping template {template.get('id')} as it is not a temporal template")
            continue
        if template_idx > 0:
            print(f"\n{'='*60}")
            print(f"Waiting 60 seconds before processing next template...")
            print(f"{'='*60}")
            sys.stdout.flush()  # Force flush before sleep
            time.sleep(90)  # Explicit blocking sleep
            sys.stdout.flush()  # Force flush after sleep
        
        print(f"\n{'='*60}")
        print(f"Processing template {template_idx + 1}/{len(all_templates)} (id: {template.get('id', 'unknown')})")
        print(f"{'='*60}")
        
        # Create fresh crew instances for each template to ensure no shared state
        sql_gen_crew = make_sql_gen_crew()
        nl_crew = make_nl_crew()
        
        # Extract primary_key from template
        template_primary_key = template.get("primary_key", None)
        
        # 0) Build context with this specific template
        inputs = build_sql_gen_context(csv_path, template=template)

        # 1) Generate 5 SQLs for this template (LLM) with retry on 429
        # Ensure sequential execution - wait for completion before proceeding
        try:
            print(f"  [Step 1/4] Starting SQL generation for template {template.get('id')}...")
            gen_out = retry_on_429(sql_gen_crew.kickoff, max_retries=5, base_delay=60, inputs=inputs)
            # Explicitly wait for result to ensure it's complete
            gen_text = str(gen_out.raw) if hasattr(gen_out, "raw") else str(gen_out)
            cleaned = extract_json_from_text(gen_text)
            sql_items: List[Dict[str, Any]] = json.loads(cleaned)
            print(f"  [Step 1/4] Completed SQL generation: {len(sql_items)} queries generated")
        except Exception as e:
            print(f"  Error generating SQL for template {template.get('id')}: {e}")
            # Sleep even on error before continuing to next template
            _checkpoint(stage="sql_generation_failed", template_id=str(template.get("id")))
            print(f"  Sleeping 60 seconds before next template...")
            time.sleep(30)
            continue

        # Add primary_key to each SQL item
        for item in sql_items:
            item["primary_key"] = template_primary_key

        # Quick sanity check: ensure each sql mentions FROM df
        valid_items = []
        for idx, it in enumerate(sql_items):
            if "sql" not in it or "df" not in it.get("sql", "").lower():
                print(f"  Skipping item {idx} from template {template.get('id')}: missing 'FROM df'")
                continue
            valid_items.append(it)
        
        if not valid_items:
            print(f"  No valid SQL items for template {template.get('id')}")
            _checkpoint(stage="no_valid_sql", template_id=str(template.get("id")))
            print(f"  Sleeping 60 seconds before next template...")
            #time.sleep(60)
            continue
        
        # 1.5) Initialize variables in SQL queries before validation
        print(f"  [Step 2/4] Initializing variables in SQL queries...")
        try:
            instantiated_items = initialize_sql_items(valid_items, csv_path, num_instantiations=1)
            print(f"  [Step 2/4] Initialized {len(instantiated_items)} SQL queries")
        except Exception as e:
            print(f"  Error initializing variables for template {template.get('id')}: {e}")
            _checkpoint(stage="param_init_failed", template_id=str(template.get("id")))
            print(f"  Sleeping 60 seconds before next template...")
            time.sleep(60)
            continue

        # 2) Validate (PURE PYTHON) - validate instantiated SQLs
        print(f"  [Step 3/4] Validating SQL queries...")
        ok_items, bad_items = validate_sql_items(instantiated_items, csv_path)
        print(f"  [Step 3/4] Validation complete: {len(ok_items)} passed, {len(bad_items)} failed")
        
        if not ok_items:
            print(f"  No valid SQL queries for template {template.get('id')}")
            all_bad_items.extend(bad_items)
            _checkpoint(stage="no_passing_sql", template_id=str(template.get("id")))
            print(f"  Sleeping 60 seconds before next template...")
            #time.sleep(60)
            continue

        # 4) NL generation ONLY for passing (LLM) with retry on 429
        # Wait before NL generation to space out API calls
        print(f"  [Step 4/4] Waiting 60 seconds before NL generation...")
        time.sleep(60)
        # Remove validation field from ok_items for NL generation (validation will be added back from tool output)
        ok_items_for_nl = [{k: v for k, v in item.items() if k != "validation"} for item in ok_items]
        nl_in = pretty_json(ok_items_for_nl, max_chars=None)
        try:
            print(f"  [Step 4/4] Starting NL generation for {len(ok_items_for_nl)} items...")
            nl_out = retry_on_429(nl_crew.kickoff, max_retries=5, base_delay=60, inputs={"items_json": nl_in})
            # Explicitly wait for result to ensure it's complete
            nl_text = str(nl_out.raw) if hasattr(nl_out, "raw") else str(nl_out)
            cleaned = extract_json_from_text(nl_text)
            final: List[Dict[str, Any]] = json.loads(cleaned)
            print(f"  [Step 4/4] Completed NL generation: {len(final)} questions generated")
            
            # Ensure primary_key is preserved in final items
            for item in final:
                if "primary_key" not in item:
                    item["primary_key"] = template_primary_key
                item["template_id"] = template.get("id")
            
            all_final_items.extend(final)
            all_bad_items.extend(bad_items)
            _checkpoint(stage="nl_generation_ok", template_id=str(template.get("id")))
            print(f"  Generated {len(final)} questions for template {template.get('id')}")
        except Exception as e:
            print(f"  Error generating NL for template {template.get('id')}: {e}")
            all_bad_items.extend(ok_items)  # Add to bad_items if NL generation failed
            all_bad_items.extend(bad_items)
            _checkpoint(stage="nl_generation_failed", template_id=str(template.get("id")))
        
        # Template processing complete - sleep will happen at start of next iteration
        print(f"  ✓ Completed template {template.get('id')} ({template_idx + 1}/{len(all_templates)})")
        _checkpoint(stage="template_done", template_id=str(template.get("id")))
        # Force flush output to ensure messages are visible
        import sys
        sys.stdout.flush()

    _checkpoint(stage="all_done", template_id=None)
    return {
        "final": all_final_items,      # All items with question/paraphrases and validation
        "failed": all_bad_items,       # All failed items
        "total_templates": len(all_templates),
        "total_generated": len(all_final_items),
    }


# export names (keep as before)
__all__ = [
    "make_sql_gen_crew",
    "make_fix_crew",
    "make_nl_crew",
    "kickoff_for_csv",
    "sql_generator",
    "nl_generator",
    "validator",
    "fixer",
]
