# scoring/simple_scorer.py
# Tiny, safe default: uses an existing DC field so we get variation.
# Replace with your real logic later.

import pandas as pd

def compute_score(row: pd.Series) -> int:
    # Example heuristic: 10 points per admin login, capped at 100.
    # Guarantees an int in [0, 100] for classing bins [0,40,70,101).
    try:
        v = int(row.get("adminLogins", 0) or 0)
    except Exception:
        v = 0
    return max(0, min(100, v * 10))
