import json
from collections import defaultdict
from pathlib import Path

def merge_json_files(json_files):
    merged = defaultdict(list)

    for file_path in json_files:
        with open(file_path, "r") as f:
            data = json.load(f)

        for key, value in data.items():
            if isinstance(value, list):
                merged[key].extend(value)
            else:
                merged[key].append(value)

    return dict(merged)

# Usage
#json_dir = Path("path/to/jsons")
files = ["test_generated_sql_nl_progress.json",
"test_generated_sql_nl_progress_2.json",
"test_generated_sql_nl_progress_3.json",
"test_generated_sql_nl_progress_4.json",
"test_generated_sql_nl_progress_5.json",
"test_generated_sql_nl_progress_6.json",
"test_generated_sql_nl_progress_7.json",
"test_generated_sql_nl_progress_8.json",
]

merged_data = merge_json_files(files)

with open("merged.json", "w") as f:
    json.dump(merged_data, f, indent=2)