# data/ga_handler.py
# Purpose: Fetch + clean GA4 data (Analytics Data API) and return a normalized GA_norm dataframe.
# Notes:
# - Single responsibility: ask GA for the date range, normalize column names, validate, return.
# - No downstream filtering by date; API already applies it.
# - Optional columns (region, schoolType, sign_up) are included when present but not required.

from __future__ import annotations

import os
from typing import Dict, List
import pandas as pd

from data.schema_contracts import validate_ga_columns

# --- Import GA Data API (v1 preferred; fall back to v1beta if needed) ----------
try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient as GAClient
    from google.analytics.data_v1beta.types import RunReportRequest
    _GA_VERSION = "v1beta"
except Exception:  # pragma: no cover
    try:
        from google.analytics.data_v1alpha import AlphaAnalyticsDataClient as GAClient  # unlikely
        from google.analytics.data_v1alpha.types import RunReportRequest
        _GA_VERSION = "v1alpha"
    except Exception:
        # v1 (stable) import path — some environments ship this one
        from google.analytics.data_v1 import AnalyticsDataClient as GAClient  # type: ignore
        from google.analytics.data_v1.types import RunReportRequest  # type: ignore
        _GA_VERSION = "v1"

# --- Stable output column names (contract lives in schema_contracts) -----------
_DIMENSION_RENAMES: Dict[str, str] = {
    "country": "country",
    "firstUserCampaignName": "first_campaign",
    "firstUserGoogleAdsAdGroupName": "first_ads_adgroup",
    "firstUserSourceMedium": "first_source_medium",
    "region": "region",  # optional
    "customUser:icpGroup": "icp_group",
    "customUser:schoolType": "schoolType",  # optional
    "customUser:userId": "userId",
}

_METRIC_RENAMES: Dict[str, str] = {
    "keyEvents:sign_up": "sign_up",  # optional
}

# Dimensions/metrics to request from GA (kept explicit to avoid drift)
_REQUEST_DIMENSIONS = [
    "country",
    "firstUserCampaignName",
    "firstUserGoogleAdsAdGroupName",
    "firstUserSourceMedium",
    "region",
    "customUser:icpGroup",
    "customUser:schoolType",
    "customUser:userId",
]

_REQUEST_METRICS = [
    "keyEvents:sign_up",
]

# --- Public API ---------------------------------------------------------------

def fetch_and_clean(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch GA rows in [start_date, end_date] and return GA_norm (validated).

    Parameters
    ----------
    start_date : str  (YYYY-MM-DD)
    end_date   : str  (YYYY-MM-DD)

    Environment
    -----------
    - GA4 property id via env var: GA_PROPERTY_ID
    - Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS

    Returns
    -------
    pd.DataFrame
        Columns (required): userId, country, icp_group, first_source_medium, first_campaign, first_ads_adgroup
        Columns (optional, when GA returns them): region, schoolType, sign_up
    """
    property_id = os.getenv("GA_PROPERTY_ID")
    if not property_id:
        raise RuntimeError(
            "[GA_norm] GA_PROPERTY_ID not set. Please export GA_PROPERTY_ID in the Streamlit env."
        )

    # 1) Build request
    req = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[{"name": d} for d in _REQUEST_DIMENSIONS],
        metrics=[{"name": m} for m in _REQUEST_METRICS],
        date_ranges=[{"start_date": start_date, "end_date": end_date}],
        order_bys=[{"dimension": {"order_type": "ALPHANUMERIC", "dimension_name": "customUser:userId"}}],
    )

    # 2) Execute
    try:
        client = GAClient()
        resp = client.run_report(req)
    except Exception as e:
        raise RuntimeError(f"[GA_norm] GA run_report failed: {e}") from e

    # 3) Parse rows -> list[dict]
    if not getattr(resp, "rows", None):
        # Return empty, correctly-shaped frame (validators won't fail on optional cols)
        df = pd.DataFrame(columns=list(_DIMENSION_RENAMES.values()) + list(_METRIC_RENAMES.values()))
        # Keep only distinct columns (metrics may overlap names)
        df = df.loc[:, ~df.columns.duplicated()].copy()
        return validate_ga_columns(df)

    # Build header order to map indices
    dim_headers = [d.name for d in resp.dimension_headers]
    met_headers = [m.name for m in resp.metric_headers]

    records: List[Dict[str, str]] = []
    for row in resp.rows:
        rec: Dict[str, str] = {}

        # Dimensions
        for i, dim_val in enumerate(row.dimension_values):
            ga_name = dim_headers[i]
            norm_name = _DIMENSION_RENAMES.get(ga_name, ga_name)  # preserve unknowns for debug
            rec[norm_name] = (dim_val.value or "").strip()

        # Metrics
        for j, met_val in enumerate(row.metric_values):
            ga_name = met_headers[j]
            norm_name = _METRIC_RENAMES.get(ga_name, ga_name)
            rec[norm_name] = _safe_to_int(met_val.value)

        records.append(rec)

    df = pd.DataFrame.from_records(records)

    # 4) Final normalization touches
    # Ensure userId is string (join key) and non-empty rows are kept
    if "userId" in df.columns:
        df["userId"] = df["userId"].astype(str).str.strip()

    # Optional: drop rows with empty userId (cannot join to DC)
    df = df[df["userId"].ne("")].reset_index(drop=True)

    # 5) Validate contract (names only) and return
    # This will fail fast if any required columns are missing.
    return validate_ga_columns(df)

# --- small utils --------------------------------------------------------------

def _safe_to_int(val: str) -> int:
    try:
        return int(val)
    except Exception:
        return 0
