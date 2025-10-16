# data/dreamclass_handler.py
# Purpose: Fetch + clean DreamClass data and return a normalized DC_norm dataframe.
# Notes:
# - Trusts this module for ALL DC renaming/normalization (no renames elsewhere).
# - Fails fast (clear message) if any required columns are missing (via schema_contracts).
# - Only filters by DreamClass.status; GA date filtering remains GA-side.
# - Keep changes incremental and heavily commented for PR review.

from __future__ import annotations

import os
from typing import Iterable, List, Dict, Any, Optional
import pandas as pd
import requests
from urllib.parse import urljoin

from data.schema_contracts import validate_dc_columns

# ---- Helpers -----------------------------------------------------------------

def _infer_org_from_email(email: Optional[str]) -> Optional[str]:
    """Extract organization from email domain (e.g., 'alice@acme.com' -> 'acme')."""
    if not email or "@" not in email:
        return None
    try:
        domain = email.split("@", 1)[1]
        # take first label (acme from acme.com); keep alnum and hyphen/underscore
        org = domain.split(".")[0]
        return org.strip()
    except Exception:
        return None

def _ensure_tz_naive(series: pd.Series) -> pd.Series:
    """Ensure datetimes are tz-naive (required by downstream logic)."""
    s = pd.to_datetime(series, errors="coerce", utc=True)
    # drop tz info to make naive
    return s.dt.tz_convert(None) if hasattr(s.dt, "tz_convert") else s.dt.tz_localize(None)

# ---- Public API ---------------------------------------------------------------

def fetch_and_clean(base_url: str, statuses: Iterable[str]) -> pd.DataFrame:
    """
    Fetch DreamClass users and return a normalized dataframe with stable columns.

    Expected output columns (names-only validation in schema_contracts):
      - userId (from 'id')
      - email
      - name
      - organization (derived from email domain)
      - adminLogins
      - status
      - createdAt (tz-naive)

    Parameters
    ----------
    base_url : str
        Base API URL for DreamClass (e.g., https://api.example.com/).
        The code uses GET {base_url}/users (adjust path if your current dev repo differs).
    statuses : Iterable[str]
        Status filters applied on the API side (inclusive). Example: ["trialing", "active"].

    Returns
    -------
    pd.DataFrame
        DC_norm dataframe, validated and ready for scoring joins.
    """
    # --- Build request ---------------------------------------------------------
    # Adjust endpoint if your current repo uses a different path, e.g. "/admin/users"
    endpoint = urljoin(base_url.rstrip("/") + "/", "users")

    # Auth: prefer DC_API_KEY if present, else allow unauthenticated (nightly will fail fast if needed).
    api_key = os.getenv("DC_API_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # fallback if your backend proxies
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    # Query params: keep simple & explicit; adapt to your backend (e.g., `status=in.(a,b)` for PostgREST).
    # For now, pass repeated 'status' params so the backend can OR them.
    params: List[tuple[str, str]] = [("limit", "10000")]  # crude cap; tune/ paginate if needed
    for st in statuses:
        params.append(("status", str(st)))

    # --- Fetch (single-shot; add pagination if your API pages results) ---------
    resp = requests.get(endpoint, headers=headers, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(
            f"[DC_norm] HTTP error while fetching DreamClass users: {e}\n"
            f"URL: {resp.request.url}\nStatus: {resp.status_code}\nBody: {resp.text[:500]}"
        ) from e

    payload: Any = resp.json()
    if not isinstance(payload, list):
        raise ValueError(f"[DC_norm] Unexpected response shape (expected list): {type(payload)}")

    raw_df = pd.DataFrame(payload)

    # --- Minimal defensive checks before transform -----------------------------
    if raw_df.empty:
        # Return an empty, correctly-shaped frame so downstream UI doesn’t explode
        empty = pd.DataFrame(
            columns=["userId", "email", "name", "organization", "adminLogins", "status", "createdAt"]
        )
        return validate_dc_columns(empty)

    # --- Normalize column names/values -----------------------------------------
    df = raw_df.copy()

    # 1) id -> userId (join key with GA.userId)
    if "id" in df.columns and "userId" not in df.columns:
        df = df.rename(columns={"id": "userId"})

    # 2) Ensure we have expected raw fields; fail fast later if still missing.
    #    Compute organization from email domain.
    if "organization" not in df.columns:
        df["organization"] = df.get("email").apply(_infer_org_from_email) if "email" in df.columns else None

    # 3) createdAt -> tz-naive
    if "createdAt" in df.columns:
        df["createdAt"] = _ensure_tz_naive(df["createdAt"])

    # 4) Coerce adminLogins to integer where possible (keep names-only validator strict)
    if "adminLogins" in df.columns:
        df["adminLogins"] = pd.to_numeric(df["adminLogins"], errors="coerce").fillna(0).astype("Int64")

    # 5) Keep only stable columns if you prefer (optional). We keep all columns to aid debugging,
    #    but downstream code should only rely on the validated, stable ones.
    #    Uncomment the next line to hard-select:
    # df = df[["userId", "email", "name", "organization", "adminLogins", "status", "createdAt"]]

    # --- Validate names-only contract and return -------------------------------
    return validate_dc_columns(df)
