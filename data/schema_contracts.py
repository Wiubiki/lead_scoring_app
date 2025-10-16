# data/schema_contracts.py
# Purpose: central, names-only schema contracts. Keep lightweight and explicit.
# Usage: called by data handlers after cleaning, before returning.

from typing import Iterable, Set
import pandas as pd

# --- Expected, stable columns after cleaning/normalization ---
# --- GA schema (core + optional) ---
GA_REQUIRED: Set[str] = {
    "userId",
    "country",
    "icp_group",
    "first_source_medium",
    "first_campaign",
    "first_ads_adgroup",
}

GA_OPTIONAL: Set[str] = {
    "region",
    "schoolType",
    "sign_up",
}

DC_REQUIRED: Set[str] = {
    "userId", "email", "name", "organization",
    "adminLogins", "status", "createdAt",
}

def _require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(
            f"[{label}] Missing required column(s): {sorted(missing)}. "
            f"Present columns: {sorted(df.columns)}"
        )
    # Warn but don’t fail if optional fields are absent
    if label == "GA_norm":
        optional_missing = GA_OPTIONAL - set(df.columns)
        if optional_missing:
            print(f"[{label}] Optional columns not found (ok): {sorted(optional_missing)}")


def validate_ga_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Validate GA normalized dataframe columns."""
    _require_columns(df, GA_REQUIRED, "GA_norm")
    return df

def validate_dc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Validate DreamClass normalized dataframe columns."""
    _require_columns(df, DC_REQUIRED, "DC_norm")
    return df
