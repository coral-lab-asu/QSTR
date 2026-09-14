#!/usr/bin/env python3
"""
Script to evaluate table alignment between LLM output and ground truth tables.
Matches primary keys using name matching and Hungarian algorithm.
Calculates RMSE, accuracy, SMAPE for numeric columns.
Calculates row missing and row extra from primary key analysis.
"""

import json
import sys
from typing import List, Dict, Any, Tuple, Optional, Union
from collections import defaultdict

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # Create minimal numpy-like functions
    class np:
        @staticmethod
        def mean(x):
            return sum(x) / len(x) if x else 0.0
        @staticmethod
        def sqrt(x):
            return x ** 0.5
        @staticmethod
        def isnan(x):
            return x != x
        @staticmethod
        def isinf(x):
            return abs(x) == float('inf')
        @staticmethod
        def ones(shape):
            if isinstance(shape, tuple):
                return [[1.0] * shape[1] for _ in range(shape[0])]
            return [1.0] * shape

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from rapidfuzz import fuzz, process
    FUZZ_LIB = 'rapidfuzz'
except ImportError:
    try:
        from fuzzywuzzy import fuzz, process
        FUZZ_LIB = 'fuzzywuzzy'
    except ImportError:
        print("Warning: rapidfuzz or fuzzywuzzy not available. Name matching will be limited.")
        FUZZ_LIB = None


def normalize_value(val: Any) -> Any:
    """Normalize values for comparison (handle None, NaN, etc.)"""
    if val is None:
        return None
    if isinstance(val, float):
        if HAS_NUMPY:
            if np.isnan(val) or np.isinf(val):
                return None
        else:
            # Manual check for NaN/Inf
            if val != val or abs(val) == float('inf'):
                return None
    if isinstance(val, str):
        return val.strip()
    return val


def extract_table_from_llm_output(llm_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract table data from llm_output structure."""
    if isinstance(llm_output, list):
        return llm_output
    if isinstance(llm_output, dict):
        # Try common keys
        if 'results' in llm_output:
            results = llm_output['results']
            if isinstance(results, list) and len(results) > 0:
                if isinstance(results[0], dict) and 'table' in results[0]:
                    return results[0]['table']
        if 'table' in llm_output:
            return llm_output['table']
        if 'data' in llm_output:
            return llm_output['data']
    return []


def get_primary_key_value(row: Dict[str, Any], pk: Union[str, List[str]]) -> Tuple:
    """Extract primary key value(s) from a row."""
    if pk is None or pk == "N/A":
        return None
    
    if isinstance(pk, str):
        return normalize_value(row.get(pk))
    elif isinstance(pk, list):
        return tuple(normalize_value(row.get(col)) for col in pk)
    else:
        return None


def name_similarity(name1: Any, name2: Any, threshold: float = 0.85) -> float:
    """Calculate name similarity score between two values."""
    if name1 is None or name2 is None:
        return 0.0
    
    str1 = str(name1).strip().lower()
    str2 = str(name2).strip().lower()
    
    if str1 == str2:
        return 1.0
    
    if FUZZ_LIB == 'rapidfuzz':
        # Use token_sort_ratio for better name matching
        score = fuzz.token_sort_ratio(str1, str2) / 100.0
    elif FUZZ_LIB == 'fuzzywuzzy':
        score = fuzz.token_sort_ratio(str1, str2) / 100.0
    else:
        # Fallback: simple string similarity
        if str1 == str2:
            return 1.0
        # Levenshtein-like simple comparison
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 1.0
        # Simple character overlap
        common = sum(1 for c in set(str1) if c in set(str2))
        score = common / max(len(set(str1)), len(set(str2)), 1)
    
    return score if score >= threshold else 0.0


def match_primary_keys(
    gt_rows: List[Dict[str, Any]],
    pred_rows: List[Dict[str, Any]],
    pk: Union[str, List[str]],
    name_threshold: float = 0.85
) -> Dict[int, int]:
    """
    Match primary keys between ground truth and predicted rows.
    Returns a mapping from GT row index to predicted row index.
    Uses Hungarian algorithm for optimal matching when names are involved.
    """
    if pk is None or pk == "N/A":
        return {}
    
    # Extract primary keys
    gt_pks = [get_primary_key_value(row, pk) for row in gt_rows]
    pred_pks = [get_primary_key_value(row, pk) for row in pred_rows]
    
    # Filter out None values
    gt_valid = [(i, pk_val) for i, pk_val in enumerate(gt_pks) if pk_val is not None]
    pred_valid = [(i, pk_val) for i, pk_val in enumerate(pred_pks) if pk_val is not None]
    
    if not gt_valid or not pred_valid:
        return {}
    
    # Check if we need name matching (if any PK values are strings)
    needs_name_matching = False
    for _, pk_val in gt_valid + pred_valid:
        if isinstance(pk_val, str) or (isinstance(pk_val, tuple) and any(isinstance(v, str) for v in pk_val)):
            needs_name_matching = True
            break
    
    matches = {}
    
    if needs_name_matching:
        # Use Hungarian algorithm for optimal matching
        n_gt = len(gt_valid)
        n_pred = len(pred_valid)
        
        # Build cost matrix (1 - similarity, so lower is better)
        if HAS_NUMPY:
            cost_matrix = np.ones((n_gt, n_pred)) * 1000  # Large penalty for no match
        else:
            cost_matrix = [[1000.0] * n_pred for _ in range(n_gt)]
        
        for i, (gt_idx, gt_pk) in enumerate(gt_valid):
            for j, (pred_idx, pred_pk) in enumerate(pred_valid):
                if isinstance(gt_pk, tuple) and isinstance(pred_pk, tuple):
                    # Composite key: average similarity across components
                    similarities = []
                    for gv, pv in zip(gt_pk, pred_pk):
                        if gv == pv:
                            similarities.append(1.0)
                        else:
                            similarities.append(name_similarity(gv, pv, threshold=0.0))
                    sim = (sum(similarities) / len(similarities)) if similarities else 0.0
                else:
                    if gt_pk == pred_pk:
                        sim = 1.0
                    else:
                        sim = name_similarity(gt_pk, pred_pk, threshold=0.0)
                
                if HAS_NUMPY:
                    cost_matrix[i, j] = 1.0 - sim  # Convert similarity to cost
                else:
                    cost_matrix[i][j] = 1.0 - sim  # Convert similarity to cost
        
        # Apply Hungarian algorithm
        if HAS_SCIPY and HAS_NUMPY and n_gt > 0 and n_pred > 0:
            row_indices, col_indices = linear_sum_assignment(cost_matrix)
            
            for i, j in zip(row_indices, col_indices):
                if HAS_NUMPY:
                    cost = cost_matrix[i, j]
                else:
                    cost = cost_matrix[i][j]
                similarity = 1.0 - cost
                if similarity >= name_threshold:
                    gt_idx = gt_valid[i][0]
                    pred_idx = pred_valid[j][0]
                    matches[gt_idx] = pred_idx
        else:
            # Fallback: greedy matching
            used_pred = set()
            for i, (gt_idx, gt_pk) in enumerate(gt_valid):
                best_match = None
                best_sim = 0.0
                for j, (pred_idx, pred_pk) in enumerate(pred_valid):
                    if pred_idx in used_pred:
                        continue
                    if isinstance(gt_pk, tuple) and isinstance(pred_pk, tuple):
                        similarities = []
                        for gv, pv in zip(gt_pk, pred_pk):
                            if gv == pv:
                                similarities.append(1.0)
                            else:
                                similarities.append(name_similarity(gv, pv, threshold=0.0))
                        sim = np.mean(similarities) if similarities else 0.0
                    else:
                        if gt_pk == pred_pk:
                            sim = 1.0
                        else:
                            sim = name_similarity(gt_pk, pred_pk, threshold=0.0)
                    if sim > best_sim and sim >= name_threshold:
                        best_sim = sim
                        best_match = pred_idx
                if best_match is not None:
                    matches[gt_idx] = best_match
                    used_pred.add(best_match)
    else:
        # Exact matching for non-string PKs
        pred_pk_map = {pred_pk: pred_idx for pred_idx, pred_pk in pred_valid}
        for gt_idx, gt_pk in gt_valid:
            if gt_pk in pred_pk_map:
                matches[gt_idx] = pred_pk_map[gt_pk]
    
    return matches


def is_numeric(value: Any) -> bool:
    """Check if a value is numeric."""
    if value is None:
        return False
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if HAS_NUMPY:
                if np.isnan(value) or np.isinf(value):
                    return False
            else:
                if value != value or abs(value) == float('inf'):
                    return False
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    return False


def convert_to_numeric(value: Any) -> Optional[float]:
    """Convert value to numeric, returning None if not possible."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if HAS_NUMPY:
                if np.isnan(value) or np.isinf(value):
                    return None
            else:
                if value != value or abs(value) == float('inf'):
                    return None
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def calculate_rmse(values1: List[float], values2: List[float]) -> float:
    """Calculate Root Mean Squared Error."""
    if not values1 or not values2 or len(values1) != len(values2):
        return float('inf')
    
    squared_errors = [(v1 - v2) ** 2 for v1, v2 in zip(values1, values2) 
                      if v1 is not None and v2 is not None]
    if not squared_errors:
        return float('inf')
    
    if HAS_NUMPY:
        mse = np.mean(squared_errors)
        return np.sqrt(mse)
    else:
        mse = sum(squared_errors) / len(squared_errors)
        return mse ** 0.5


def calculate_accuracy(values1: List[Any], values2: List[Any]) -> float:
    """Calculate accuracy (exact match rate)."""
    if not values1 or not values2 or len(values1) != len(values2):
        return 0.0
    
    matches = sum(1 for v1, v2 in zip(values1, values2) 
                 if normalize_value(v1) == normalize_value(v2))
    return matches / len(values1) if values1 else 0.0


def calculate_smape(values1: List[float], values2: List[float]) -> float:
    """Calculate Symmetric Mean Absolute Percentage Error."""
    if not values1 or not values2 or len(values1) != len(values2):
        return float('inf')
    
    errors = []
    for v1, v2 in zip(values1, values2):
        if v1 is None or v2 is None:
            continue
        denominator = (abs(v1) + abs(v2)) / 2.0
        if denominator == 0:
            if v1 == v2:
                errors.append(0.0)
            else:
                errors.append(1.0)  # 100% error
        else:
            errors.append(abs(v1 - v2) / denominator)
    
    if not errors:
        return float('inf')
    
    if HAS_NUMPY:
        return np.mean(errors) * 100.0  # Return as percentage
    else:
        return (sum(errors) / len(errors)) * 100.0  # Return as percentage


def evaluate_table_alignment(
    gt_table: List[Dict[str, Any]],
    pred_table: List[Dict[str, Any]],
    pk: Union[str, List[str], None],
    name_threshold: float = 0.85
) -> Dict[str, Any]:
    """
    Evaluate alignment between ground truth and predicted tables.
    
    Returns:
        Dictionary with metrics including:
        - row_matches: mapping from GT row index to pred row index
        - row_missing: list of GT row indices not matched
        - row_extra: list of pred row indices not matched
        - numeric_metrics: dict with RMSE, accuracy, SMAPE per numeric column
    """
    if pk is None or pk == "N/A":
        return {
            'row_matches': {},
            'row_missing': list(range(len(gt_table))),
            'row_extra': list(range(len(pred_table))),
            'numeric_metrics': {},
            'skipped': True,
            'reason': 'Primary key is None or N/A'
        }
    
    # Match primary keys
    matches = match_primary_keys(gt_table, pred_table, pk, name_threshold)
    
    matched_gt_indices = set(matches.keys())
    matched_pred_indices = set(matches.values())
    
    row_missing = [i for i in range(len(gt_table)) if i not in matched_gt_indices]
    row_extra = [i for i in range(len(pred_table)) if i not in matched_pred_indices]
    
    # Get all column names
    all_columns = set()
    for row in gt_table:
        all_columns.update(row.keys())
    for row in pred_table:
        all_columns.update(row.keys())
    
    # Identify numeric columns (columns that have numeric values in matched rows)
    numeric_columns = {}
    for col in all_columns:
        has_numeric = False
        for gt_idx, pred_idx in matches.items():
            gt_val = gt_table[gt_idx].get(col)
            pred_val = pred_table[pred_idx].get(col)
            if is_numeric(gt_val) or is_numeric(pred_val):
                has_numeric = True
                break
        if has_numeric:
            numeric_columns[col] = True
    
    # Calculate metrics for numeric columns
    numeric_metrics = {}
    for col in numeric_columns:
        gt_values = []
        pred_values = []
        
        for gt_idx, pred_idx in matches.items():
            gt_val = convert_to_numeric(gt_table[gt_idx].get(col))
            pred_val = convert_to_numeric(pred_table[pred_idx].get(col))
            
            if gt_val is not None and pred_val is not None:
                gt_values.append(gt_val)
                pred_values.append(pred_val)
        
        if gt_values and pred_values:
            numeric_metrics[col] = {
                'rmse': calculate_rmse(gt_values, pred_values),
                'accuracy': calculate_accuracy(
                    [gt_table[gt_idx].get(col) for gt_idx, _ in matches.items()],
                    [pred_table[pred_idx].get(col) for _, pred_idx in matches.items()]
                ),
                'smape': calculate_smape(gt_values, pred_values),
                'num_matched_values': len(gt_values)
            }
    
    return {
        'row_matches': matches,
        'row_missing': row_missing,
        'row_extra': row_extra,
        'row_missing_count': len(row_missing),
        'row_extra_count': len(row_extra),
        'row_matched_count': len(matches),
        'numeric_metrics': numeric_metrics,
        'skipped': False
    }


def process_json_file(json_path: str, name_threshold: float = 0.85) -> List[Dict[str, Any]]:
    """Process the JSON file and evaluate all records."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    
    for i, record in enumerate(data):
        record_id = record.get('record_id', f'record_{i}')
        pk = record.get('pk')
        
        # Extract tables
        gt_table = record.get('answer_gnd_truth', [])
        if not isinstance(gt_table, list):
            gt_table = []
        
        llm_output = record.get('llm_output', {})
        pred_table = extract_table_from_llm_output(llm_output)
        
        if not pred_table:
            pred_table = []
        
        # Evaluate alignment
        evaluation = evaluate_table_alignment(gt_table, pred_table, pk, name_threshold)
        
        result = {
            'record_id': record_id,
            'pk': pk,
            'gt_row_count': len(gt_table),
            'pred_row_count': len(pred_table),
            **evaluation
        }
        
        results.append(result)
    
    return results


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate table alignment between LLM output and ground truth')
    parser.add_argument('--input_json', help='Input JSON file (corpus_everything_llm_output.json)',default='corpus_everything_llm_output.json')
    parser.add_argument('--output', '-o', help='Output JSON file for results', default='evaluation_results.json')
    parser.add_argument('--name-threshold', type=float, default=0.85, 
                       help='Name matching threshold (default: 0.85)')
    
    args = parser.parse_args()
    
    print(f"Processing {args.input_json}...")
    results = process_json_file(args.input_json, args.name_threshold)
    
    print(f"Processed {len(results)} records")
    
    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to {args.output}")
    
    # Print summary statistics
    skipped = sum(1 for r in results if r.get('skipped', False))
    matched = sum(1 for r in results if not r.get('skipped', False))
    total_missing = sum(r.get('row_missing_count', 0) for r in results)
    total_extra = sum(r.get('row_extra_count', 0) for r in results)
    total_matched = sum(r.get('row_matched_count', 0) for r in results)
    
    print(f"\nSummary:")
    print(f"  Records with valid PK: {matched}")
    print(f"  Records skipped (no PK): {skipped}")
    print(f"  Total rows matched: {total_matched}")
    print(f"  Total rows missing: {total_missing}")
    print(f"  Total rows extra: {total_extra}")


if __name__ == '__main__':
    main()
