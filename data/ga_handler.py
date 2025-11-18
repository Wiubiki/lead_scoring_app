# data/ga_handler.py
from __future__ import annotations

import os
import pandas as pd
from typing import List, Dict

try:
    import streamlit as st
    SECRETS = dict(st.secrets)
except Exception:
    SECRETS = {}

from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest

from data.schema_contracts import validate_ga_columns


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _get_property_id() -> str:
    """
    Read the GA4 Property ID exactly like main branch does.
    Accept both nested and flat formats because Streamlit Cloud
    sometimes flattens keys.
    """
    s = SECRETS

    pid = (
        s.get("ga", {}).get("property_id")
        or s.get("ga", {}).get("GA_PROPERTY_ID")
        or s.get("GA_PROPERTY_ID")
        or os.getenv("GA_PROPERTY_ID")
    )

    if not pid:
        raise RuntimeError("[GA_norm] Missing GA property id. Add GA_PROPERTY_ID or [ga].property_id to secrets.toml.")

    return str(pid).strip()


def _get_credentials():
    """
    Service account info from main app.
    """
    s = SECRETS

    sa_info = (
        s.get("google_credentials")  # main app structure
        or s.get("service_account_json")  # flattened fallback
    )

    if not sa_info:
        raise RuntimeError("[GA_norm] Missing Google service account in secrets under [google_credentials].")

    return service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )


# -------------------------------------------------------------------------
# Main Fetch Function
# -------------------------------------------------------------------------

def fetch_and_clean(start_date: str, end_date: str) -> pd.DataFrame:
    """
    This is a faithful, minimal version of the main branch GA fetcher,
    adapted only to return normalized columns + pass schema validation.
    """

    property_id = _get_property_id()
    creds = _get_credentials()

    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            {"name": "country"},
            {"name": "firstUserCampaignName"},
            {"name": "firstUserGoogleAdsAdGroupName"},
            {"name": "firstUserSourceMedium"},
            {"name": "region"},
            {"name": "customUser:icpGroup"},
            {"name": "customUser:schoolType"},
            {"name": "customUser:userId"},
        ],
        metrics=[{"name": "keyEvents:sign_up"}],
        date_ranges=[{"start_date": start_date, "end_date": end_date}],
    )

    try:
        response = client.run_report(request)
    except Exception as e:
        raise RuntimeError(f"[GA_norm] GA request failed: {e}")

    rows = []
    for row in response.rows:
        record = {}
        for header, dim in zip(response.dimension_headers, row.dimension_values):
            record[header.name] = dim.value
        for header, met in zip(response.metric_headers, row.metric_values):
            record[header.name] = met.value
        rows.append(record)

    df = pd.DataFrame(rows)

    # Normalize names
    renames = {
    "firstUserCampaignName": "First user campaign",
    "firstUserSourceMedium": "First user source / medium",
    "firstUserGoogleAdsAdGroupName": "Google Ads Ad Group",
    "customUser:icpGroup": "icp_group",
    "customUser:schoolType": "school_type",
    "customUser:userId": "userId",
    "keyEvents:sign_up": "sign_up",
    }

    df = df.rename(columns=renames)

    # ensure correct dtypes
    if "userId" in df.columns:
        df["userId"] = df["userId"].astype(str).str.strip()

    if "sign_up" in df.columns:
        df["sign_up"] = pd.to_numeric(df["sign_up"], errors="coerce").fillna(0).astype(int)

    # pass through schema validator
    return validate_ga_columns(df)