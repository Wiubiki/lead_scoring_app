import requests
import pandas as pd
import json
import streamlit as st
import ast


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
        auth_headers = ast.literal_eval(credentials_dict["auth_headers"])

        # Construct the API URL with selected statuses
        statuses_param = ",".join(statuses)
        request_url = f"{base_url}?statuses={statuses_param}"

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



def clean_dreamclass_data(raw_data):
    """
    Clean and process the raw DreamClass data.
    """
    import json

    try:
        # Ensure createdAt is in a consistent format
        raw_data["createdAt"] = pd.to_datetime(raw_data["createdAt"], errors="coerce").dt.strftime("%Y-%m-%d")

        # Ensure adminLogins is an integer
        raw_data["adminLogins"] = raw_data["adminLogins"].fillna(0).astype(int)

        # Parse dcSubscription safely
        def parse_dc_subscription(value):
            # Check if the value is already a dictionary
            if isinstance(value, dict):
                return value
            # If it's a string, try to parse it
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                raise ValueError(f"Malformed dcSubscription value: {value}")

        raw_data["dcSubscription_parsed"] = raw_data["dcSubscription"].apply(parse_dc_subscription)

        # Extract fields from the parsed dcSubscription
        raw_data["status"] = raw_data["dcSubscription_parsed"].apply(lambda x: x.get("status", "unknown"))
        raw_data["plan_name"] = raw_data["dcSubscription_parsed"].apply(lambda x: x.get("dcPlan", {}).get("name", "unknown"))

        # Drop unnecessary columns
        raw_data = raw_data.drop(columns=["dcSubscription", "dcSubscription_parsed", "zohoLeadId", "zohoContactId", "zohoAccountId", "schemaName"], errors="ignore")

        return raw_data
    except Exception as e:
        print(f"Error cleaning DreamClass data: {e}")
        raise


