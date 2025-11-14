# scoring/lead_scores_calculator.py
# Purpose: Orchestrate scoring using existing scorer logic (no renames here),
#          then add Class + Class% safely. Trust data handlers for columns.
# Notes:
# - apply(DC_norm, GA_norm) returns a dataframe ready for UI.
# - We DO NOT alter column names. We only add: 'TotalScore' (or your scorer's name), 'Class', 'Class%'.
# - If no known scorer is importable, we fail fast with a clear message (mid-refactor safety).

from __future__ import annotations

import os
from typing import Callable, Optional, List
import importlib
import pandas as pd

from scoring.scoring_logic import join_dc_ga, add_class_column, add_class_percent


try:
    import streamlit as st
except Exception:
    st = None

# --------- Public API ----------------------------------------------------------

def apply(
    DC_norm: pd.DataFrame,
    GA_norm: pd.DataFrame,
    score_fn: Optional[Callable[[pd.Series], float]] = None,
    bins: Optional[List[int]] = None,
    labels: Optional[List[str]] = None,
    score_col_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Run the end-to-end scoring pipeline.

    Parameters
    ----------
    DC_norm, GA_norm : pd.DataFrame
        Clean, validated frames from data handlers (join key: userId).
    score_fn : callable(row) -> float, optional
        If None, we auto-discover an existing scorer to preserve current behavior.
    bins : list[int], optional
        Class bin edges. Default: [0, 40, 70, 101]
    labels : list[str], optional
        Class labels. Default: ['C','B','A'] (aligned to the bins above)
    score_col_name : str, optional
        Column name to store the total/aggregate score. Default: 'TotalScore' unless
        the discovered scorer already sets a column; we’ll respect that.

    Returns
    -------
    pd.DataFrame
        Merged + scored dataframe with 'Class' and 'Class%' added.
    """
    # 1) Join safely (raises on collisions except 'userId')
    df = join_dc_ga(DC_norm, GA_norm)

    # 2) Find a scorer if not provided (no internal renames — we adapt to what's already there)
    if score_fn is None:
        score_fn = _discover_existing_scorer()

    # 3) Compute score
    #    If the scorer already writes a score column (e.g., mutates row-like dict), we’ll detect it.
    #    Otherwise, we place its numeric return into score_col_name (default 'TotalScore').
    proposed_score_col = score_col_name or "TotalScore"

    # Apply scorer row-wise; keep vector-friendly if your scorer supports it
    scores = df.apply(score_fn, axis=1)

    # If the scorer returned a Series (with its own name), respect that; else use proposed_score_col
    if isinstance(scores, pd.Series) and scores.name:
        score_col = str(scores.name)
        df[score_col] = scores.values
    else:
        score_col = proposed_score_col
        df[score_col] = scores.values if isinstance(scores, pd.Series) else scores

    # 4) Classing
    bins = bins or [0, 40, 70, 101]
    labels = labels or ["C", "B", "A"]
    df = add_class_column(df, score_col=score_col, bins=bins, labels=labels)

    # 5) Class% (global share by class)
    df = add_class_percent(df, class_col="Class")

    return df


# --------- Scorer discovery (preserve existing behavior) -----------------------

_CANDIDATE_SCORERS = [
    # (module_path, function_name)
    ("scoring.scorer", "compute_score"),
    ("scoring.scorer", "score_row"),
    ("scoring.rules", "compute_lead_score"),
    ("scoring.rules", "score_row"),
    ("scoring.existing", "compute_lead_score"),
    ("scoring.existing", "score_row"),
    ("scoring.v2_scorer", "compute_score"),
    ("scoring.simple_scorer", "compute_score"),  # <— fallback
]

def _discover_existing_scorer() -> Callable[[pd.Series], float]:
     # secrets override: [app].score_fn = "module.path:function"
    if st is not None:
        sf = dict(st.secrets).get("app", {}).get("score_fn")
        if sf:
            mod, _, fn = sf.partition(":")
            if not fn:
                raise RuntimeError("[scoring] app.score_fn must be 'module.path:function'")
            module = importlib.import_module(mod)
            cand = getattr(module, fn)
            if callable(cand):
                return cand
    """
    Try known module/function pairs to keep existing scoring intact.
    If nothing is found, raise a clear, actionable error guiding the developer.
    """
    # Allow override via env var, e.g. SCORE_FN="scoring.scorer:compute_score"
    override = os.getenv("SCORE_FN")
    if override:
        mod, _, fn = override.partition(":")
        if not fn:
            raise RuntimeError("[scoring] SCORE_FN must look like 'module.path:function_name'")
        try:
            module = importlib.import_module(mod)
            cand = getattr(module, fn)
            if callable(cand):
                return cand
        except Exception as e:
            raise RuntimeError(f"[scoring] Could not import SCORE_FN={override}: {e}") from e

    for mod, fn in _CANDIDATE_SCORERS:
        try:
            module = importlib.import_module(mod)
            cand = getattr(module, fn)
            if callable(cand):
                return cand
        except Exception:
            continue

    raise RuntimeError(
        "[scoring] No existing scorer found. Provide score_fn=… or set env SCORE_FN='module.path:function'.\n"
        "Tried candidates: "
        + ", ".join([f"{m}:{f}" for m, f in _CANDIDATE_SCORERS])
    )
