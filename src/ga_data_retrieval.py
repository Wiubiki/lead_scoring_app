import google.analytics.data_v1beta as beta
from google.analytics.data_v1beta import BetaAnalyticsDataClient, RunReportRequest
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# Load credentials from Streamlit secrets
credentials_dict = st.secrets["google_credentials"]

# Create credentials object
credentials = Credentials.from_service_account_info(credentials_dict)

# Initialize the Analytics Data API client with credentials
client = BetaAnalyticsDataClient(credentials=credentials)

# Define the property ID
PROPERTY_ID = "353721724"  # Replace with your GA4 property ID


def fetch_ga_data(start_date, end_date):
    """
    Fetch data from Google Analytics using the API.

    Args:
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.

    Returns:
        pd.DataFrame: A DataFrame containing the fetched data.
    """
    # Initialize the request with the desired dimensions, metrics, and date range
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[
            {"name": "country"},
            {"name": "firstUserCampaignName"},
            {"name": "firstUserGoogleAdsAdGroupName"},
            {"name": "firstUserSourceMedium"},
            {"name": "region"},
            {"name": "customUser:icpGroup"},
            {"name": "customUser:schoolType"},
            {"name": "customUser:userId"}
        ],
        metrics=[
            {"name": "keyEvents:sign_up"}
        ],
        date_ranges=[
            {"start_date": start_date, "end_date": end_date}
        ],
        order_bys=[
            {"dimension": {"order_type": "ALPHANUMERIC", "dimension_name": "customUser:userId"}}
        ]
    )

    # Execute the request
    response = client.run_report(request)

    # Parse the response into a DataFrame
    rows = []
    for row in response.rows:
        rows.append(
            [dimension.value for dimension in row.dimension_values] +
            [metric.value for metric in row.metric_values]
        )

    # Extract headers
    headers = [
        header.name for header in response.dimension_headers
    ] + [
        header.name for header in response.metric_headers
    ]

    # Return the data as a DataFrame
    return pd.DataFrame(rows, columns=headers)
