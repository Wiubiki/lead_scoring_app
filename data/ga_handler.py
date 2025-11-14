# data/ga_handler.py
from __future__ import annotations
import os
from typing import Dict, List
import pandas as pd

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore

from data.schema_contracts import validate_ga_columns

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient as GAClient
    from google.analytics.data_v1beta.types import RunReportRequest
except Exception:  # pragma: no cover
    from google.analytics.data_v1 import AnalyticsDataClient as GAClient  # type: ignore
    from google.analytics.data_v1.types import RunReportRequest  # type: ignore

from google.oauth2 import service_account

_DIMENSION_RENAMES: Dict[str, str] = {
    "country": "country",
    "firstUserCampaignName": "first_campaign",
    "firstUserGoogleAdsAdGroupName": "first_ads_adgroup",
    "firstUserSourceMedium": "first_source_medium",
    "region": "region",
    "customUser:icpGroup": "icp_group",
    "customUser:schoolType": "schoolType",
    "customUser:userId": "userId",
}
_METRIC_RENAMES: Dict[str, str] = {"keyEvents:sign_up": "sign_up"}

def _secrets() -> Dict:
    return dict(st.secrets) if st is not None else {}

def _get_property_id() -> str:
    s = _secrets()
    pid = (
        s.get("ga", {}).get("property_id")
        or s.get("ga", {}).get("GA_PROPERTY_ID")
        or os.getenv("GA_PROPERTY_ID")
    )
    if not pid:
        raise RuntimeError("[GA_norm] Missing GA property id. Use [ga].property_id in secrets.toml.")
    return str(pid).strip()

def _build_client() -> GAClient:
    s = _secrets()
    sa_info = s.get("google_credentials")  # <-- your existing section
    if sa_info:
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )
        return GAClient(credentials=creds)
    # Fallback: ADC (works locally if GOOGLE_APPLICATION_CREDENTIALS is set)
    return GAClient()

def _safe_to_int(val: str) -> int:
    try:
        return int(val)
    except Exception:
        return 0

def fetch_and_clean(start_date: str, end_date: str) -> pd.DataFrame:
    property_id = _get_property_id()
    req = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[{"name": n} for n in [
            "country","firstUserCampaignName","firstUserGoogleAdsAdGroupName",
            "firstUserSourceMedium","region","customUser:icpGroup",
            "customUser:schoolType","customUser:userId"
        ]],
        metrics=[{"name": "keyEvents:sign_up"}],
        date_ranges=[{"start_date": start_date, "end_date": end_date}],
        order_bys=[{"dimension": {"order_type": "ALPHANUMERIC", "dimension_name": "customUser:userId"}}],
    )

    try:
        client = _build_client()
        resp = client.run_report(req)
    except Exception as e:
        raise RuntimeError(f"[GA_norm] GA run_report failed: {e}") from e

    if not getattr(resp, "rows", None):
        df = pd.DataFrame(columns=list(_DIMENSION_RENAMES.values()) + list(_METRIC_RENAMES.values()))
        df = df.loc[:, ~df.columns.duplicated()].copy()
        return validate_ga_columns(df)

    dim_headers = [d.name for d in resp.dimension_headers]
    met_headers = [m.name for m in resp.metric_headers]

    rows: List[Dict[str, str]] = []
    for r in resp.rows:
        rec: Dict[str, str] = {}
        for i, dv in enumerate(r.dimension_values):
            ga = dim_headers[i]; rec[_DIMENSION_RENAMES.get(ga, ga)] = (dv.value or "").strip()
        for j, mv in enumerate(r.metric_values):
            ga = met_headers[j]; rec[_METRIC_RENAMES.get(ga, ga)] = _safe_to_int(mv.value)
        rows.append(rec)

    df = pd.DataFrame.from_records(rows)
    if "userId" in df.columns:
        df["userId"] = df["userId"].astype(str).str.strip()
        df = df[df["userId"].ne("")].reset_index(drop=True)
    return validate_ga_columns(df)
