import requests
import pandas as pd
import json
import streamlit as st

def fetch_dreamclass_data():
    """
    Fetch raw DreamClass data securely using credentials from secrets.
    """
    try:
        # Fetch credentials from Streamlit secrets
        api_url = st.secrets["dreamclass_api"]["url"]
        auth_headers = {
            "Authorization": st.secrets["dreamclass_api"]["authorization"],
            "x-dc-additional-data": st.secrets["dreamclass_api"]["additional_data"]
        }

        # Make API request
        response = requests.get(api_url, headers=auth_headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return pd.DataFrame(response.json())  # Convert response JSON to DataFrame
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



def clean_dreamclass_data(raw_data):
    """
    Clean and process the raw DreamClass data.
    """
    try:
        # Parse `dcSubscription` and extract `status` and `plan_name`
        parsed_subscription = raw_data["dcSubscription"].apply(parse_dc_subscription)
        raw_data["status"] = parsed_subscription.apply(lambda x: x.get("status", "unknown"))
        raw_data["plan_name"] = parsed_subscription.apply(lambda x: x.get("dcPlan", {}).get("name", "unknown"))

        # Convert dates
        raw_data["createdAt"] = pd.to_datetime(raw_data["createdAt"], errors="coerce").dt.strftime("%d/%m/%Y")

        # Convert 'id' to string
        raw_data["id"] = raw_data["id"].astype(str)

        # Handle adminLogins as integers
        raw_data["adminLogins"] = raw_data["adminLogins"].fillna(0).astype(int)

        # Drop unnecessary columns
        raw_data = raw_data.drop(columns=["dcSubscription", "lastAdminLogin", "schoolType", "zohoLeadId", "zohoContactId", "zohoAccountId", "schemaName"], errors="ignore")

        return raw_data
    except Exception as e:
        print(f"Error cleaning DreamClass data: {e}")
        raise
