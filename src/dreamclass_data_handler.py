import requests
import pandas as pd
import json
import streamlit as st
import ast
from typing import Any


def fetch_dreamclass_data(api_url, statuses):
    """
    Fetch raw DreamClass data from the API.

    Args:
        api_url (str): Base URL for the DreamClass API.
        statuses (list): List of statuses to retrieve.

    Returns:
        pd.DataFrame: A DataFrame containing the raw DreamClass data.
    """
    try:
        # Load credentials and headers from Streamlit secrets
        credentials_dict = st.secrets["dreamclass_api"]
        base_url = credentials_dict["base_url"]
        auth_headers = json.loads(credentials_dict["auth_headers"])

        # Development-only warning
        if "Authorization" not in auth_headers:
            print("⚠️ Warning: Missing Authorization header in auth_headers. Did you update your secrets.toml?")

        # Construct the API URL with selected statuses
        statuses_param = ",".join(statuses)
        request_url = f"{base_url}?statuses={statuses_param}"

        #  Debug output before the API call
        print("Final request URL:", request_url)
        print("Final auth headers:", auth_headers)

        # Make the API request
        response = requests.get(request_url, headers=auth_headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Convert response JSON to DataFrame
        return pd.DataFrame(response.json())
    except Exception as e:
        print(f"Error fetching DreamClass data: {e}")
        raise



def parse_dc_subscription(value):
    """
    Parse the `dcSubscription` field to extract status and plan_name.
    Handles both dictionary and string formats.
    """
    if pd.isna(value):
        return {"status": "unknown", "dcPlan": {"name": "unknown"}}

    # If already a dictionary, return it directly
    if isinstance(value, dict):
        return value

    try:
        # Handle string values and ensure proper JSON format
        cleaned_value = value.replace('""', '"').replace('"', '')  # Remove excessive quotes
        cleaned_value = cleaned_value.replace("'", '"')  # Replace single quotes with double quotes
        parsed = json.loads(cleaned_value)  # Parse as JSON
        return parsed
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error decoding JSON for value: {value} -> {e}")
        return {"status": "unknown", "dcPlan": {"name": "unknown"}}





def _parse_created_at(series: pd.Series, prefer_dayfirst: bool | None = None) -> pd.Series:
    s = series.astype("string").str.strip()

    def _try(src: pd.Series, **kw) -> pd.Series:
        return pd.to_datetime(src, errors="coerce", utc=False, **kw)

    # ISO/common first, then day-first
    base = _try(s)
    dfirst = _try(s, dayfirst=True)
    dt = (dfirst.fillna(base) if prefer_dayfirst is True
          else base.fillna(dfirst))

    # 10-digit epoch seconds
    mask10 = dt.isna() & s.str.match(r"^\d{10}(\.\d+)?$").fillna(False)
    if mask10.any():
        dt.loc[mask10] = pd.to_datetime(s[mask10].astype(float), unit="s", errors="coerce")

    # 13-digit epoch milliseconds
    mask13 = dt.isna() & s.str.match(r"^\d{13}$").fillna(False)
    if mask13.any():
        dt.loc[mask13] = pd.to_datetime(s[mask13].astype(float), unit="ms", errors="coerce")

    # return naive datetimes (good for Streamlit widgets/comparisons)
    return pd.to_datetime(dt).dt.tz_localize(None)

def _parse_dc_subscription(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    # Try literal_eval safely; fall back to empty dict on malformed values
    try:
        parsed = ast.literal_eval(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, SyntaxError):
        return {}

def clean_dreamclass_data(raw_data: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and process raw DreamClass data.
    - Keep createdAt as datetime (and add a date-only helper column)
    - Ensure numeric adminLogins
    - Parse dcSubscription safely; extract status & plan_name
    - Drop unused heavy fields
    """
    df = raw_data.copy()

    # createdAt: robust parsing (do NOT stringify here)
    df["createdAt"] = _parse_created_at(df.get("createdAt", pd.Series([])))
    df["createdAt_date"] = df["createdAt"].dt.date  # convenient for grouping

    # adminLogins: ensure integer
    if "adminLogins" in df.columns:
        df["adminLogins"] = pd.to_numeric(df["adminLogins"], errors="coerce").fillna(0).astype(int)

    # dcSubscription: safe parse + field extraction
    if "dcSubscription" in df.columns:
        parsed = df["dcSubscription"].apply(_parse_dc_subscription)
        df["status"] = parsed.apply(lambda x: x.get("status", "unknown"))
        df["plan_name"] = parsed.apply(lambda x: x.get("dcPlan", {}).get("name", "unknown"))

    # Light hygiene (optional)
    if "email" in df.columns:
        df["email"] = df["email"].astype("string").str.strip().str.lower()
    if "phoneNumber" in df.columns:
        df["phoneNumber"] = df["phoneNumber"].astype("string").str.strip()

    # Drop heavy/unused columns
    df = df.drop(
        columns=["dcSubscription", "zohoLeadId", "zohoContactId", "zohoAccountId", "schemaName"],
        errors="ignore",
    )

    return df
