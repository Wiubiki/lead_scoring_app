import google.analytics.data_v1beta as beta
from google.analytics.data_v1beta import BetaAnalyticsDataClient, RunReportRequest
import pandas as pd
import os

# Replace the property ID directly here
property_id = "353721724"

# Set the environment variable for the Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "dreamclass-leadscoring-10a3ac3a769b.json"

# Function to fetch data from Google Analytics
def fetch_ga_data(start_date, end_date):
    """
    Fetch data from Google Analytics using the API. and he harcoded property ID

    Args:
        property_id (str): GA4 property ID.
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.

    Returns:
        pd.DataFrame: A DataFrame containing the fetched data.
    """
    # Initialize the Analytics Data API client
    client = BetaAnalyticsDataClient()
    # Initialize the request with the following dimensions and metrics
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
        rows.append([dimension.value for dimension in row.dimension_values] +
                    [metric.value for metric in row.metric_values])

    # Extract headers
    headers = [header.name for header in response.dimension_headers] + \
              [header.name for header in response.metric_headers]

    # Return as a DataFrame
    return pd.DataFrame(rows, columns=headers)

'''
# MAIN EXECUTION (Example)
if __name__ == "__main__":
    # Example property ID
    property_id = "353721724"  # Replace with your GA4 property ID

    # Example date range
    start_date = "2024-11-01"
    end_date = "2024-11-30"

    # Fetch data
    ga_data = fetch_ga_data(property_id, start_date, end_date)

    # Save to CSV (optional)
    ga_data.to_csv("output_files/ga_data.csv", index=False)
    print("Google Analytics data retrieved and saved to 'output_files/ga_data.csv'.")'''
