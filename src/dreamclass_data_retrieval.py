import requests
import pandas as pd
import json

# Base URL and endpoint for DreamClass API
BASE_URL = "https://panel-backend.dreamclass.io"
ENDPOINT = "/account/getAccountsWithStatuses"

# Headers for authorization and additional data
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "authorization": "Basic ZGlhZ25yYW1tYTpkcmVhbQ==",  # updated base64: diagnramma:dream
    "x-dc-additional-data": "GxwShGVaegQiF4HJ1XezXTvfLjVacFnr",  # Replace if needed
}

def fetch_dreamclass_data(status="trial_expired"):
    """
    Fetch data from DreamClass API based on account status.

    Args:
        status (str): Account status to filter by (e.g., trial_expired, active).

    Returns:
        pd.DataFrame: A DataFrame containing the fetched DreamClass data.
    """
    # Build the request URL
    url = f"{BASE_URL}{ENDPOINT}?statuses={status}"

    # Make the API request
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        # Parse JSON response
        data = response.json()
        # Convert to DataFrame
        df = pd.DataFrame(data)
        return df
    else:
        # Handle errors
        raise Exception(f"Failed to fetch data: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # Example usage: Fetch trial_expired accounts
    try:
        dreamclass_data = fetch_dreamclass_data(status="trial_expired")
        print("Fetched DreamClass data:")
        print(dreamclass_data.head())
        # Save to CSV
        dreamclass_data.to_csv("output_files/dreamclass_data.csv", index=False)
        print("Data saved to output_files/dreamclass_data.csv")
    except Exception as e:
        print(f"Error: {e}")
