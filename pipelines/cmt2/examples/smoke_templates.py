"""Small deterministic templates used by the credential-free KT smoke test."""

question_templates = [
    {
        "id": "smoke-total-runs",
        "question": "How many runs were scored in total?",
        "query": "SELECT SUM(batsman_runs) AS total_runs FROM {table_name};",
        "variables": ["table_name"],
        "primary_key": ["N/A"],
    },
    {
        "id": "smoke-total-runs-equivalent",
        "question": "What is the match run total?",
        "query": "SELECT SUM(batsman_runs + 0) AS total_runs FROM {table_name};",
        "variables": ["table_name"],
        "primary_key": ["N/A"],
    },
    {
        "id": "smoke-runs-by-batsman",
        "question": "How many runs did each batter score?",
        "query": (
            "SELECT batsman, SUM(batsman_runs) AS total_runs "
            "FROM {table_name} GROUP BY batsman ORDER BY batsman;"
        ),
        "variables": ["table_name"],
        "primary_key": ["batsman"],
    },
]
