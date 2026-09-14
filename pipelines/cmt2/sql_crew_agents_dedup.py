# sql_crew_agents_dedup.py
"""
Dedup + resume + multi-round generation wrapper for your existing sql_crew_agents.py.

Goal:
- Option 1 scaling: multiple rounds per base template (5 SQLs per call) until target_unique reached.
- Safe resume: stop anytime, restart later, and NEVER accept duplicate SQL again.
- Diversity support: optionally inject extra inspiration templates from a 1000-bank CSV if your
  base.build_sql_gen_context supports it.

How it works:
- Hard dedupe is enforced via a persistent SQL fingerprint registry stored in progress_json.
- Prompt-level dedupe is optional (and can be added later), but hard dedupe is the guarantee.

Requirements:
- Your project must have sql_crew_agents.py (imported as base) with:
    - load_templates()
    - make_sql_gen_crew()
    - make_nl_crew()
    - retry_on_429()
    - extract_json_from_text()
    - initialize_sql_items()
    - validate_sql_items()
    - pretty_json()
    - _atomic_write_json()
    - build_sql_gen_context(...)  (we try to call it with diversity args, but fallback if not supported)
"""

from __future__ import annotations

import json
import re
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

try:
    from . import sql_crew_agents_v2 as base
except ImportError:  # Supports direct execution from the CMT2 directory.
    import sql_crew_agents_v2 as base


# -----------------------------------------------------------------------------
# Canonicalization + fingerprint (hard dedupe)
# -----------------------------------------------------------------------------

_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_SQ_STR_RE = re.compile(r"'([^'\\]|\\.)*'")
_WS_RE = re.compile(r"\s+")

# Description string regex for quoted strings (double quotes)
_DESC_STR_RE = re.compile(r"\"([^\"\\]|\\.)*\"")


def canonicalize_description(desc: str) -> str:
    """Canonical form for description dedupe: normalize case/whitespace, strip numbers/strings."""
    if not desc:
        return ""
    s = desc
    s = s.lower().strip()
    # normalize quoted strings and numbers
    s = _DESC_STR_RE.sub("<str>", s)
    s = _SQ_STR_RE.sub("<str>", s)
    s = _NUM_RE.sub("<num>", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def description_fingerprint(desc: str) -> str:
    c = canonicalize_description(desc)
    return hashlib.sha256(c.encode("utf-8")).hexdigest() if c else ""


def canonicalize_sql(sql: str) -> str:
    """Canonical form for dedupe: removes comments, normalizes numbers/strings/whitespace."""
    if not sql:
        return ""
    s = sql
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)   # /* ... */
    s = re.sub(r"--[^\n]*", " ", s)                # -- ...
    s = s.lower()
    s = _SQ_STR_RE.sub("<str>", s)
    s = _NUM_RE.sub("<num>", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def sql_fingerprint(sql: str) -> str:
    c = canonicalize_sql(sql)
    return hashlib.sha256(c.encode("utf-8")).hexdigest() if c else ""


class DedupeRegistry:
    """
    Stores fingerprints (sha256(canonical_sql)) to guarantee no duplicates.
    Uses a rolling window to cap memory/payload size.
    """

    def __init__(self, max_items: int = 50000):
        self.max_items = max_items
        self._queue: deque[str] = deque(maxlen=max_items)
        self._set: set[str] = set()

    def add_sql(self, sql: str) -> bool:
        """Returns True if added (new), False if already seen/invalid."""
        fp = sql_fingerprint(sql)
        if not fp or fp in self._set:
            return False

        if len(self._queue) == self._queue.maxlen:
            oldest = self._queue[0]
            self._set.discard(oldest)

        self._queue.append(fp)
        self._set.add(fp)
        return True

    def add_fp(self, fp: str) -> None:
        if not fp or fp in self._set:
            return

        if len(self._queue) == self._queue.maxlen:
            oldest = self._queue[0]
            self._set.discard(oldest)

        self._queue.append(fp)
        self._set.add(fp)

    def add_text(self, text: str, fp_fn) -> bool:
        """Add text using provided fingerprint function; returns True if new."""
        fp = fp_fn(text)
        if not fp or fp in self._set:
            return False

        if len(self._queue) == self._queue.maxlen:
            oldest = self._queue[0]
            self._set.discard(oldest)

        self._queue.append(fp)
        self._set.add(fp)
        return True

    def to_list(self) -> List[str]:
        return list(self._queue)

    def __len__(self) -> int:
        return len(self._queue)


# -----------------------------------------------------------------------------
# Resume helpers
# -----------------------------------------------------------------------------

def _load_progress(progress_json_path: str) -> Dict[str, Any]:
    p = Path(progress_json_path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_registry_and_state_from_progress(
    progress_json_path: str,
    registry_max_items: int = 50000,
) -> Tuple[DedupeRegistry, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Restore:
      - registry from seen_sql_fingerprints
      - final and failed arrays
    """
    reg = DedupeRegistry(max_items=registry_max_items)
    final: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    payload = _load_progress(progress_json_path)
    if not payload:
        return reg, final, failed

    if isinstance(payload.get("final"), list):
        final = payload["final"]
    if isinstance(payload.get("failed"), list):
        failed = payload["failed"]

    fps = payload.get("seen_sql_fingerprints", [])
    if isinstance(fps, list):
        for fp in fps[-registry_max_items:]:
            if isinstance(fp, str) and fp:
                reg.add_fp(fp)

    return reg, final, failed


def seed_registry_from_sql_json(
    reg: DedupeRegistry,
    sql_json_path: str,
) -> None:
    """
    Seed dedupe from an existing outputs JSON so a new session doesn't re-generate old SQL.
    Supports common shapes:
      - [ {sql: ...}, ... ]
      - { final: [ ... ] }
      - { items: [ ... ] }
      - { results: [ ... ] }
    """
    p = Path(sql_json_path)
    if not p.exists():
        return

    try:
        data: Any = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return

    if isinstance(data, dict):
        for key in ("final", "items", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break

    if not isinstance(data, list):
        return

    for it in data:
        if not isinstance(it, dict):
            continue
        sql = it.get("sql") or it.get("original_sql")
        if isinstance(sql, str) and sql.strip():
            reg.add_sql(sql)


# -----------------------------------------------------------------------------
# Prompt-level seen canonicals helper
# -----------------------------------------------------------------------------

def compute_seen_sql_canonicals_for_prompt(final_items: List[Dict[str, Any]], max_items: int = 300) -> List[str]:
    """Return a recent, unique list of canonical SQL strings to discourage repeats (prompt-level)."""
    out: List[str] = []
    seen: set[str] = set()
    for it in reversed(final_items):
        sql = it.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            continue
        c = canonicalize_sql(sql)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= max_items:
            break
    return list(reversed(out))

# -----------------------------------------------------------------------------
# Context builder wrapper (diversity + optional prompt-level seen list)
# -----------------------------------------------------------------------------

def build_inputs(
    csv_path: str,
    template: Dict[str, Any],
    diversity_csv_path: Optional[str],
    diversity_k: int,
    seen_query_canonicals_json: str,
) -> Dict[str, Any]:
    """
    Calls base.build_sql_gen_context with best-effort support for diversity args.
    This keeps compatibility even if your base file doesn't yet accept those params.
    """
    # Try the richest signature first
    try:
        return base.build_sql_gen_context(
            csv_path,
            template=template,
            diversity_csv_path=diversity_csv_path,
            diversity_k=diversity_k,
            seen_query_canonicals_json=seen_query_canonicals_json,
        )
    except TypeError:
        # Older signature: build_sql_gen_context(csv_path, template=template)
        return base.build_sql_gen_context(csv_path, template=template)


# -----------------------------------------------------------------------------
# Main: generate until target with safe resume + hard dedupe
# -----------------------------------------------------------------------------

def kickoff_until_target(
    csv_path: str,
    target_unique: int = 5000,
    progress_json_path: str = "progress_sql_dedup.json",
    rounds_per_template: int = 10,
    diversity_csv_path: Optional[str] = None,
    diversity_k: int = 4,
    resume_from_sql_json_path: Optional[str] = None,
    registry_max_items: int = 50000,
    temporal_only: bool = True,
    temporal_min_template_id: int = 91,
) -> Dict[str, Any]:
    """
    Option 1 scaling:
      - Iterate over the human templates
      - For each template, run multiple rounds (each round asks model for 5 SQLs)
      - Stop when we reach target_unique validated NL items

    Resume safety:
      - If progress_json_path exists, we restore:
          final, failed, seen_sql_fingerprints
      - If resume_from_sql_json_path is provided, we also seed dedupe from that output file
      - Hard dedupe guarantees no duplicates are accepted even across sessions

    Notes:
      - You can stop the process anytime; on restart, call this same function with the same
        progress_json_path. It will continue toward 5k without duplicates.
    """

    # Load templates (human-written)
    all_templates = base.load_templates()

    # Restore prior progress if available
    reg, final_items, failed_items = load_registry_and_state_from_progress(
        progress_json_path,
        registry_max_items=registry_max_items,
    )

    # Description dedupe registry
    desc_reg = DedupeRegistry(max_items=registry_max_items)
    # restore description fingerprints if present
    payload = _load_progress(progress_json_path)
    fps_desc = payload.get("seen_desc_fingerprints", []) if isinstance(payload, dict) else []
    if isinstance(fps_desc, list):
        for fp in fps_desc[-registry_max_items:]:
            if isinstance(fp, str) and fp:
                desc_reg.add_fp(fp)

    # Optional seed from an existing outputs JSON (for safety if you migrated runs)
    if resume_from_sql_json_path:
        seed_registry_from_sql_json(reg, resume_from_sql_json_path)

    def checkpoint(stage: str, template_id: Optional[str] = None, round_idx: Optional[int] = None) -> None:
        payload: Dict[str, Any] = {
            "csv_path": csv_path,
            "updated_at": int(time.time()),
            "stage": stage,
            "template_id": template_id,
            "round_idx": round_idx,
            "target_unique": target_unique,
            "rounds_per_template": rounds_per_template,
            "diversity_csv_path": diversity_csv_path,
            "diversity_k": diversity_k,
            "total_templates": len(all_templates),
            "total_generated": len(final_items),
            "total_failed": len(failed_items),
            "seen_sql_fingerprints": reg.to_list(),
            "seen_desc_fingerprints": desc_reg.to_list(),
            "final": final_items,
            "failed": failed_items,
        }
        base._atomic_write_json(progress_json_path, payload)

    # Already done?
    if len(final_items) >= target_unique:
        checkpoint("already_done", None, None)
        return {
            "final": final_items,
            "failed": failed_items,
            "total_generated": len(final_items),
            "registry_size": len(reg),
        }

    # Outer loops
    for t_idx, template in enumerate(all_templates):
        tid = template.get("id", "unknown")

        if temporal_only and isinstance(tid, int) and tid <= temporal_min_template_id:
            continue

        time.sleep(60)
        print(f"Sleeping for 60 seconds to reduce 429s...")

        for r in range(rounds_per_template):
            if len(final_items) >= target_unique:
                checkpoint("target_reached", str(tid), r)
                return {
                    "final": final_items,
                    "failed": failed_items,
                    "total_generated": len(final_items),
                    "registry_size": len(reg),
                }

            print("\n" + "=" * 70)
            print(f"Template {t_idx+1}/{len(all_templates)} id={tid}  round={r+1}/{rounds_per_template}")
            print(f"Progress: {len(final_items)}/{target_unique} unique")
            print("=" * 70)

            # Fresh crews per round (helps avoid shared state)
            sql_gen_crew = base.make_sql_gen_crew()
            nl_crew = base.make_nl_crew()

            # Reduce base template's influence for the prompt
            prompt_template = dict(template)
            # LLM overfits the base SQL; remove it so it follows intent + schema instead.
            if "query" in prompt_template:
                prompt_template["query"] = ""

            seen_list = compute_seen_sql_canonicals_for_prompt(final_items, max_items=40)
            seen_json = base.pretty_json(seen_list, max_chars=8000)
            if hasattr(base, "escape_curly_braces"):
                seen_json = base.escape_curly_braces(seen_json)

            # Build inputs (schema + base template + optional diversity bank + seen canonicals)
            inputs = build_inputs(
                csv_path=csv_path,
                template=prompt_template,
                diversity_csv_path=diversity_csv_path,
                diversity_k=diversity_k,
                seen_query_canonicals_json=seen_json,
            )

            print(f"Seen canonicals sent to prompt: {len(seen_list)}; desc_reg={len(desc_reg)}; sql_reg={len(reg)}")

            # 1) Generate (LLM)
            try:
                gen_out = base.retry_on_429(sql_gen_crew.kickoff, max_retries=5, base_delay=60, inputs=inputs)
                gen_text = str(gen_out.raw) if hasattr(gen_out, "raw") else str(gen_out)
                cleaned = base.extract_json_from_text(gen_text)
                sql_items: List[Dict[str, Any]] = json.loads(cleaned)
            except Exception as e:
                print(f"  SQL generation failed: {e}")
                checkpoint("sql_generation_failed", str(tid), r)
                time.sleep(5)
                continue

            # Add primary_key from template (as your pipeline expects)
            # template_primary_key = template.get("primary_key", None)
            # for it in sql_items:
            #     it["primary_key"] = template_primary_key

            # Keep only items with FROM df
            valid_items = []
            for it in sql_items:
                sql = it.get("sql")
                if not isinstance(sql, str):
                    continue
                if "df" not in sql.lower():
                    continue
                valid_items.append(it)

            if not valid_items:
                print("  No valid SQL items (missing FROM df).")
                checkpoint("no_valid_sql", str(tid), r)
                continue

            # 2) HARD DEDUPE before param init/validation (require BOTH SQL and description to be new)
            unique_items: List[Dict[str, Any]] = []
            for it in valid_items:
                sql = it.get("sql", "")
                desc = it.get("description", "")

                if not (isinstance(sql, str) and sql.strip()):
                    continue

                # Require both: SQL fingerprint new AND description fingerprint new
                if reg.add_sql(sql) and desc_reg.add_text(str(desc or ""), description_fingerprint):
                    unique_items.append(it)

            print(f"  Hard dedupe: kept {len(unique_items)}/{len(valid_items)} unique SQL this round. (registry={len(reg)})")

            if not unique_items:
                checkpoint("all_duplicates", str(tid), r)
                continue

            # 3) Initialize variables (your existing initializer)
            try:
                instantiated_items = base.initialize_sql_items(unique_items, csv_path, num_instantiations=1)
            except Exception as e:
                print(f"  Param initialization failed: {e}")
                failed_items.extend(unique_items)
                checkpoint("param_init_failed", str(tid), r)
                continue

            # 4) Validate (pure python)
            ok_items, bad_items = base.validate_sql_items(instantiated_items, csv_path)
            failed_items.extend(bad_items)

            if not ok_items:
                print("  No passing SQL after validation.")
                checkpoint("no_passing_sql", str(tid), r)
                continue

            # 5) NL generation for passing SQLs (NL returns only: item_id, question, paraphrases)
            items_for_nl: List[Dict[str, Any]] = []
            for i, item in enumerate(ok_items):
                # stable join key for merging NL back onto SQL items
                item_id = item.get("item_id")
                if not isinstance(item_id, str) or not item_id.strip():
                    item_id = f"{tid}_{r}_{i}"
                item["item_id"] = item_id

                items_for_nl.append(
                    {
                        "item_id": item_id,
                        "sql": item.get("sql", ""),
                        "description": item.get("description", ""),
                        "variables": item.get("variables", []),
                        "primary_key": item.get("primary_key", None),
                    }
                )

            nl_in = base.pretty_json(items_for_nl, max_chars=None)
            # Escape braces so placeholders like {batsman} inside SQL won't break CrewAI formatting
            if hasattr(base, "escape_curly_braces"):
                nl_in = base.escape_curly_braces(nl_in)

            try:
                nl_out = base.retry_on_429(
                    nl_crew.kickoff,
                    max_retries=5,
                    base_delay=60,
                    inputs={"items_json": nl_in},
                )
                nl_text = str(nl_out.raw) if hasattr(nl_out, "raw") else str(nl_out)
                cleaned = base.extract_json_from_text(nl_text)
                nl_items: List[Dict[str, Any]] = json.loads(cleaned)

                # index NL outputs by item_id
                nl_by_id: Dict[str, Dict[str, Any]] = {}
                for x in nl_items:
                    iid = x.get("item_id")
                    if isinstance(iid, str) and iid.strip():
                        nl_by_id[iid] = x

                merged_batch: List[Dict[str, Any]] = []
                for item in ok_items:
                    iid = item.get("item_id")
                    if not isinstance(iid, str) or iid not in nl_by_id:
                        continue

                    merged = {k: v for k, v in item.items() if k != "validation"}
                    merged["question"] = nl_by_id[iid].get("question", "")
                    merged["paraphrases"] = nl_by_id[iid].get("paraphrases", [])

                    merged["template_id"] = tid
                    merged["round_idx"] = r
                    if "primary_key" not in merged:
                        merged["primary_key"] = ["N/A"]

                    merged_batch.append(merged)

                final_items.extend(merged_batch)
                print(f"  ✓ Round OK: +{len(merged_batch)} (total={len(final_items)})")
                checkpoint("round_ok", str(tid), r)

            except Exception as e:
                # Even if NL fails, SQL dedupe already happened, so we won't regenerate those SQLs.
                print(f"  NL generation failed: {e}")
                checkpoint("nl_generation_failed", str(tid), r)

    checkpoint("all_done", None, None)
    return {
        "final": final_items,
        "failed": failed_items,
        "total_generated": len(final_items),
        "registry_size": len(reg),
    }


__all__ = [
    "canonicalize_sql",
    "sql_fingerprint",
    "DedupeRegistry",
    "load_registry_and_state_from_progress",
    "seed_registry_from_sql_json",
    "kickoff_until_target",
]
