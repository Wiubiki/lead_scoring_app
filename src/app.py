import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from lead_scoring_tool import apply_lead_scoring
from generate_summary_reports import generate_summary
from ga_data_retrieval import fetch_ga_data
from auth_library import authenticate

# Authenticate logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

st.sidebar.header("Login")

if not st.session_state["authenticated"]:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    login_button = st.sidebar.button("Login")

    if login_button:
        if authenticate(username, password):
            st.success("Login successful!")
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid username or password.")

if st.session_state["authenticated"]:


    st.title("Lead Scoring Tool")

    # Sidebar Navigation
    st.sidebar.header("Navigation")
    section = st.sidebar.selectbox(
        "Choose a section:",
        ["Upload Data", "Run Scoring", "View Results", "Generate Summary Reports"]
    )

    # Placeholder data variables
    dreamclass_data = None
    ga_data = None
    scored_data = None

    # Upload Data Section with Session State Storage
    if section == "Upload Data":
        st.header("Upload Data Files")

        # File uploaders for DreamClass and Google Analytics data
        uploaded_dreamclass = st.file_uploader("Upload DreamClass Data", type=["csv"])
        if uploaded_dreamclass:
            st.session_state["dreamclass_data"] = pd.read_csv(uploaded_dreamclass)
            st.success("DreamClass data uploaded successfully!")

            # Display sample DreamClass data
            st.write("DreamClass Data Sample", st.session_state["dreamclass_data"].head())

            # Google Analytics Data Retrieval Options
            st.subheader("Google Analytics Data Retrieval")

            # Default initialization for date_min and date_max
            date_min = None
            date_max = None

            # Set retrieval option
            retrieval_option = st.radio(
                "How do you want to retrieve Google Analytics data?",
                ("Provide Date Range", "Sync with DreamClass")
            )

            if retrieval_option == "Sync with DreamClass":
                # Auto-sync with DreamClass
                if "dreamclass_data" in st.session_state:
                    dreamclass_data = st.session_state["dreamclass_data"]
                    dreamclass_data["createdAt"] = pd.to_datetime(
                        dreamclass_data["createdAt"], format="%d/%m/%Y", errors="coerce"
                    )
                    date_min = dreamclass_data["createdAt"].min().strftime("%d/%m/%Y")
                    date_max = dreamclass_data["createdAt"].max().strftime("%d/%m/%Y")
                else:
                    st.error("DreamClass data is missing. Please upload it in the 'Upload Data' section.")
                    st.stop()

            elif retrieval_option == "Provide Date Range":
                # Default values if no DreamClass data is available
                if date_min is None or date_max is None:
                    date_min = "01/01/2024"  # Example default
                    date_max = "31/12/2024"  # Example default

                # Allow user to pick a date range
                st.write("Select Date Range")
                user_start_date, user_end_date = st.date_input(
                    "Pick a date range",
                    [
                        pd.to_datetime(date_min, format="%d/%m/%Y"),
                        pd.to_datetime(date_max, format="%d/%m/%Y")
                    ],
                    min_value=pd.to_datetime("01/01/2023", format="%d/%m/%Y"),
                    max_value=pd.to_datetime("31/12/2025", format="%d/%m/%Y"),
                )

                # Update date_min and date_max based on user input
                if user_start_date and user_end_date:
                    date_min = user_start_date.strftime("%d/%m/%Y")
                    date_max = user_end_date.strftime("%d/%m/%Y")

            # Convert dates to GA4 format right before the fetch
            start_date = pd.to_datetime(date_min, format="%d/%m/%Y").strftime("%Y-%m-%d")
            end_date = pd.to_datetime(date_max, format="%d/%m/%Y").strftime("%Y-%m-%d")

            # Fetch GA Data
            if st.button("Fetch Google Analytics Data"):
                try:
                    ga_data = fetch_ga_data(start_date, end_date)
                    # Rename columns for consistency with application conventions
                    ga_data = ga_data.rename(columns={
                        'firstUserCampaignName': 'First user campaign',
                        'firstUserSourceMedium': 'First user source / medium',
                        'customUser:icpGroup': 'icp_group',
                        'customUser:schoolType': 'school_type',
                        'customUser:userId': 'userId',
                        'firstUserGoogleAdsAdGroupName': 'Google Ads Ad Group'
                    })

                    # Store the fetched GA data in session state
                    st.session_state["ga_data"] = ga_data

                    st.success("Google Analytics data retrieved and processed successfully!")
                    st.dataframe(ga_data)  # Display the renamed GA data
                except Exception as e:
                    st.error(f"Failed to fetch GA data: {e}")



    elif section == "Run Scoring":
        st.header("Run Lead Scoring")

        # Check if data is in session state
        if "dreamclass_data" in st.session_state and "ga_data" in st.session_state:
            # Use data directly from session state
            scored_data = apply_lead_scoring(st.session_state["dreamclass_data"], st.session_state["ga_data"])
            st.session_state["scored_data"] = scored_data  # Store scored data in session state
            st.success("Lead scoring completed!")
            st.write("Scored Leads Sample", scored_data.head())
        else:
            st.info("Please upload data files first in the 'Upload Data' section.")

    # View Results section

    elif section == "View Results":
        st.header("View Scoring Results")

        # Check if scored data is available in session state
        if "scored_data" in st.session_state:
            scored_data = st.session_state["scored_data"]

            # Convert `createdAt` to datetime if it isn't already
            scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], format="%d/%m/%Y", errors="coerce")


            # Filtering options
            st.subheader("Filter Results")

            # Date Range Filter
            date_min = scored_data["createdAt"].min()
            date_max = scored_data["createdAt"].max()
            start_date, end_date = st.date_input(
                "Select Date Range",
                [date_min, date_max],
                min_value=date_min,
                max_value=date_max
            )

            # Convert selected dates to datetime format to match `createdAt`
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            # Filter by Date Range
            filtered_data = scored_data[(scored_data["createdAt"] >= start_date) & (scored_data["createdAt"] <= end_date)]

            # Lead Class and Score Filters
            lead_class_filter = st.multiselect("Select Lead Class", options=sorted(filtered_data["lead_class"].unique()), default=sorted(filtered_data["lead_class"].unique()))
            min_score, max_score = st.slider("Total Score Range", min_value=float(filtered_data["total_score"].min()), max_value=float(filtered_data["total_score"].max()), value=(float(filtered_data["total_score"].min()), float(filtered_data["total_score"].max())))

            # Apply Lead Class and Score Filters
            filtered_data = filtered_data[
                (filtered_data["lead_class"].isin(lead_class_filter)) &
                (filtered_data["total_score"] >= min_score) &
                (filtered_data["total_score"] <= max_score)
            ]

            # Sorting options
            st.subheader("Sort Results")
            sort_by = st.selectbox("Sort by", ["Total Score", "Lead Class"])
            ascending = st.radio("Order", ["Ascending", "Descending"]) == "Ascending"

            # Sort the data
            if sort_by == "Total Score":
                filtered_data = filtered_data.sort_values(by="total_score", ascending=ascending)
            elif sort_by == "Lead Class":
                filtered_data = filtered_data.sort_values(by="lead_class", ascending=ascending)

            # Display filtered and sorted data
            st.write("Filtered and Sorted Results", filtered_data)

            # Calculate lead class distribution
            lead_class_counts = filtered_data["lead_class"].value_counts()
            lead_class_percentages = lead_class_counts / lead_class_counts.sum() * 100

            # Pie Chart Visualization
            st.subheader("Lead Class Distribution")

            # Function to format the autopct text
            def autopct_format(pct, all_values):
                absolute = int(round(pct / 100. * sum(all_values)))
                return f"{pct:.1f}%\n({absolute})"  # Show percentage and count

            # Generate Pie Chart
            fig, ax = plt.subplots()
            ax.pie(
                lead_class_percentages,
                labels=[f"Class {int(cls)}" for cls in lead_class_counts.index],
                autopct=lambda pct: autopct_format(pct, lead_class_counts),  # Custom formatting
                startangle=90,
                colors=plt.cm.Paired.colors[:len(lead_class_counts)]
            )
            ax.set_title(f"Lead Class Distribution (Total Leads: {len(filtered_data)})")
            ax.axis("equal")  # Equal aspect ratio ensures that the pie chart is a circle

            # Display pie chart in Streamlit
            st.pyplot(fig)


            # Download Button for Filtered Results
            st.download_button(
                label="Download Results as CSV",
                data=filtered_data.to_csv(index=False).encode("utf-8"),
                file_name="filtered_scoring_results.csv",
                mime="text/csv"
            )
        else:
            st.info("Run lead scoring to view results.")

    # Generate Summary Reports Section

    elif section == "Generate Summary Reports":
        st.header("Generate Summary Reports")

        # Check if scored data is available in session state
        if "scored_data" in st.session_state:
            scored_data = st.session_state["scored_data"]

            # Convert `createdAt` to datetime if not already
            if scored_data["createdAt"].dtype != "datetime64[ns]":
                scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], format="%d/%m/%Y", errors="coerce")

            # Controls Section
            st.subheader("Controls")

            # Date Range Selection
            date_min = scored_data["createdAt"].min()
            date_max = scored_data["createdAt"].max()
            start_date, end_date = st.date_input(
                "Select Date Range",
                [date_min, date_max],
                min_value=date_min,
                max_value=date_max
            )

            # Ensure selected dates are in datetime format
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            if start_date > end_date:
                st.error("Start date cannot be after end date.")

            # Dimension Mapping for human-readable dimensions
            dimension_mapping = {
                "Source/Medium": "First user source / medium",
                "Campaign": "First user campaign"
            }

            # Dimension Selection
            st.write("**Choose dimensions for grouping:**")
            selected_dimensions = st.multiselect(
                "Select dimensions to group by",
                options=list(dimension_mapping.keys()),  # Dropdown labels
                default=['Source/Medium']  # Default selection
            )

            # Map selected options to dataset column names
            selected_columns = [dimension_mapping[dim] for dim in selected_dimensions if dim in dimension_mapping]

            if not selected_columns:
                st.warning("Please select at least one dimension for grouping.")

            # Button to generate the report
            if st.button("Generate Report"):
                if not start_date or not end_date:
                    st.error("Please specify both start and end dates.")
                elif not selected_columns:
                    st.error("Please select at least one grouping dimension.")
                else:
                    # Generate the report
                    try:
                        summary = generate_summary(scored_data, start_date, end_date, selected_columns)

                        # Display the report
                        st.subheader("Summary Report")
                        st.dataframe(summary)

                        # Download option
                        st.download_button(
                            label="Download Report",
                            data=summary.to_csv(index=False).encode("utf-8"),
                            file_name=f"summary_report_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
        else:
            st.info("Run lead scoring to generate summary reports.")
else:
    st.warning("Please log in to access the app.")
