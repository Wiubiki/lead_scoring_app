# scoring/scoring_logic.py
# Purpose: Pure helpers for the scoring pipeline. No column renames here.
# Notes:
# - Keep this file free of UI/IO. Only dataframe ops used by lead_scores_calculator.
# - Trust data handlers for column naming. Join key is userId.
# - Collisions are prevented by pandas merge behavior; we just detect & raise if needed.

from __future__ import annotations
import pandas as pd

# ---- Joins & safety ----------------------------------------------------------

def join_dc_ga(DC_norm: pd.DataFrame, GA_norm: pd.DataFrame) -> pd.DataFrame:
    """
    Left-join GA features onto DreamClass leads by userId.
    Does not rename columns; if collisions (other than 'userId') occur, fail fast.
    """
    _assert_required_join_cols(DC_norm, GA_norm)

    # Detect potential collisions (besides userId)
    dc_cols = set(DC_norm.columns) - {"userId"}
    ga_cols = set(GA_norm.columns) - {"userId"}
    collisions = sorted(dc_cols & ga_cols)
    if collisions:
        # We *could* suffix here, but per design we fail fast to surface drift early.
        raise ValueError(
            f"[scoring] Column collisions detected on join: {collisions}. "
            "Handlers must ensure distinct names (except 'userId')."
        )

    merged = DC_norm.merge(GA_norm, on="userId", how="left")
    return merged


def _assert_required_join_cols(DC_norm: pd.DataFrame, GA_norm: pd.DataFrame) -> None:
    if "userId" not in DC_norm.columns:
        raise ValueError("[scoring] DC_norm missing 'userId' for join.")
    if "userId" not in GA_norm.columns:
        raise ValueError("[scoring] GA_norm missing 'userId' for join.")


# ---- Class helpers (generic) -------------------------------------------------

def add_class_column(df: pd.DataFrame, score_col: str, bins: list[int], labels: list[str]) -> pd.DataFrame:
    """
    Bin a numeric score into discrete classes.
    Example: bins=[0,40,70,101], labels=['C','B','A']  (right-closed intervals)
    """
    if score_col not in df.columns:
        raise ValueError(f"[scoring] Missing score column: '{score_col}'")

    if len(bins) - 1 != len(labels):
        raise ValueError("[scoring] bins and labels length mismatch.")

    df = df.copy()
    df["Class"] = pd.cut(df[score_col], bins=bins, labels=labels, right=False, include_lowest=True)
    return df


def add_class_percent(df: pd.DataFrame, class_col: str = "Class") -> pd.DataFrame:
    """
    Add a 'Class%' column representing the global share of each class across the dataframe.
    The value is constant per class, repeated per row to avoid groupby gymnastics in the UI.
    """
    if class_col not in df.columns:
        raise ValueError(f"[scoring] Missing '{class_col}' column to compute Class%.")

    df = df.copy()
    counts = df[class_col].value_counts(dropna=False)
    total = len(df) if len(df) else 1
    share = (counts / total).rename("Class%")  # Series indexed by class label
    df["Class%"] = df[class_col].map(share).astype(float)
    return df
