# data/dreamclass_handler.py (patch)
import os, json
import pandas as pd
import requests
from urllib.parse import urljoin
from data.schema_contracts import validate_dc_columns


# data/dreamclass_handler.py (top-level constants)
ALL_STATUSES = [
    "trial", "trial_expired", "dc_incomplete", "incomplete",
    "incomplete_expired", "active", "past_due", "canceled",
    "locked_out", "unpaid",
]

DEFAULT_STATUSES = ["trial", "trial_expired", "active", "canceled"]


def _get_dc_secrets():
    try:
        import streamlit as st
        s = st.secrets["dreamclass_api"]
        return s["base_url"], json.loads(s["auth_headers"])
    except Exception as e:
        raise RuntimeError("[DC_norm] Missing or invalid [dreamclass_api] in secrets.toml") from e

def fetch_and_clean(base_url: str | None = None, statuses=None) -> pd.DataFrame:
    """
    Exact revival of old DreamClass flow:
      - GET {base_url}?statuses=trial,trial_expired,active,canceled
      - headers from [dreamclass_api].auth_headers (JSON string) in secrets
      - parse/clean dcSubscription -> status, plan_name
      - normalize required columns and validate (names only)
    """
    import json, ast

    # 1) Secrets & request setup (use your existing keys verbatim)
    def _secrets():
        try:
            import streamlit as st
            return dict(st.secrets).get("dreamclass_api", {})
        except Exception:
            return {}
    cfg = _secrets()
    endpoint = (base_url or cfg.get("base_url", "")).strip()
    if not endpoint:
        raise RuntimeError("[DC_norm] Missing dreamclass_api.base_url in secrets.toml")

    raw_headers = cfg.get("auth_headers", "{}")
    try:
        headers = json.loads(raw_headers)
    except Exception:
        headers = {}
    headers.setdefault("Accept", "application/json")

    # 2) Statuses (hardcoded defaults unless explicitly passed)
    use_statuses = DEFAULT_STATUSES if statuses is None else list(statuses)
    request_url = f"{endpoint}?statuses={','.join(use_statuses)}"

    # 3) Fetch (GET)
    resp = requests.get(request_url, headers=headers, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(
            f"[DC_norm] HTTP error while fetching DreamClass accounts: {e}\n"
            f"URL: {resp.request.url}\nStatus: {resp.status_code}\nBody: {resp.text[:500]}"
        ) from e

    raw = resp.json()
    if isinstance(raw, dict) and "data" in raw:
        raw = raw["data"]

    df = pd.DataFrame(raw)
    if df.empty:
        # return empty but correctly-shaped frame (keeps UI from exploding)
        empty = pd.DataFrame(columns=["userId","email","name","organization","adminLogins","status","createdAt"])
        return validate_dc_columns(empty)

    # 4) Clean exactly like the old cleaner
    # DreamClass also returns timestamps like "27/10/2025
    df["createdAt"] = pd.to_datetime(df["createdAt"], format="%d/%m/%Y", errors="coerce")


    # adminLogins -> int
    if "adminLogins" in df.columns:
        df["adminLogins"] = pd.to_numeric(df["adminLogins"], errors="coerce").fillna(0).astype(int)
    else:
        df["adminLogins"] = 0

    # dcSubscription -> status, plan_name (handles dict or string)
    def _parse_dc_sub(value):
        if pd.isna(value):
            return {"status": "unknown", "dcPlan": {"name": "unknown"}}
        if isinstance(value, dict):
            return value
        try:
            # old logic: be lenient with quotes
            cleaned = str(value).replace('""','"').replace('"','').replace("'", '"')
            return json.loads(cleaned)
        except Exception:
            try:
                return ast.literal_eval(str(value))
            except Exception:
                return {"status": "unknown", "dcPlan": {"name": "unknown"}}

    sub = df.get("dcSubscription")
    parsed = sub.apply(_parse_dc_sub) if sub is not None else pd.Series([{"status":"unknown","dcPlan":{"name":"unknown"}}]*len(df))
    df["status"] = parsed.apply(lambda x: x.get("status", "unknown"))
    df["plan_name"] = parsed.apply(lambda x: x.get("dcPlan", {}).get("name", "unknown"))

    # drop old cruft (same as old cleaner)
    df = df.drop(columns=["dcSubscription","zohoLeadId","zohoContactId","zohoAccountId","schemaName"], errors="ignore")

    # 5) Normalize to the v3 stable columns (names only; no enrichment)
    def _pick_col(d: pd.DataFrame, *names: str) -> pd.Series:
        for n in names:
            if n in d.columns:
                return d[n]
        # length-preserving NA series
        return pd.Series([pd.NA] * len(d), index=d.index)

    out = pd.DataFrame(index=df.index)

    out["userId"] = _pick_col(df, "userId", "id", "user_id").astype("string")
    out["email"] = _pick_col(df, "email").astype("string")
    out["name"] = _pick_col(df, "name", "fullName", "full_name").astype("string")
    out["organization"] = _pick_col(df, "organization", "domain", "company", "org").astype("string")
    out["adminLogins"] = pd.to_numeric(_pick_col(df, "adminLogins", "admin_logins"), errors="coerce").astype("Int64")
    out["status"] = _pick_col(df, "status", "plan_status", "account_status").astype("string")

    # createdAt is strictly DD/MM/YYYY in DreamClass
    out["createdAt"] = pd.to_datetime(_pick_col(df, "createdAt"), format="%d/%m/%Y", errors="coerce")


    # 6) Validate and return
    return validate_dc_columns(out)
