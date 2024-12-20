import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from lead_scoring_tool import apply_lead_scoring
from generate_summary_reports import generate_summary
from ga_data_retrieval import fetch_ga_data
from dreamclass_data_handler import fetch_dreamclass_data 
from dreamclass_data_handler import clean_dreamclass_data
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
        ["Retrieve Data", "Run Scoring", "View Results", "Generate Summary Reports"]
    )

    # Placeholder data variables
    dreamclass_data = None
    ga_data = None
    scored_data = None
    if "dreamclass_data" not in st.session_state:
        st.session_state["dreamclass_data"] = None

    # Retrieve Data Section with Date Range Picker
    if section == "Retrieve Data":
        st.header("Retrieve Data")
    
        # Date Range Picker
        st.subheader("Pick a Date Range (Mandatory)")
    
        # Initialize the default date range (e.g., for the last year)
        today = pd.Timestamp.now()
        default_start = today - pd.Timedelta(days=14)
        default_end = today
    
        # Let users pick a date range
        user_date_range = st.date_input(
            "Pick a date range",
            [default_start.date(), default_end.date()],
            min_value=pd.Timestamp("2023-01-01").date(),  # Adjust as needed
            max_value=today.date(),
        )
    
        # Validate user input
        if isinstance(user_date_range, (list, tuple)) and len(user_date_range) == 2:
            user_start_date, user_end_date = user_date_range
            if user_start_date and user_end_date:  # Ensure both dates are selected
                start_date = pd.Timestamp(user_start_date).strftime("%Y-%m-%d")
                end_date = pd.Timestamp(user_end_date).strftime("%Y-%m-%d")
                st.session_state["date_min"] = start_date
                st.session_state["date_max"] = end_date
                st.success(f"Date Range Selected: {start_date} to {end_date}")
            else:
                st.error("Please select both start and end dates to proceed.")
                st.stop()
        else:
            st.error("Please select a valid date range to proceed.")
            st.stop()
        
    
        # Display the selected date range
        st.write(f"Selected Date Range: {st.session_state['date_min']} to {st.session_state['date_max']}")
    
        # DreamClass Data Retrieval
        st.subheader("DreamClass Data Retrieval")
        
        # Status selection for DreamClass retrieval
        default_statuses = ["trial", "trial_expired", "active", "canceled"]
        selected_statuses = st.multiselect(
            "Select statuses to retrieve:",
            options=default_statuses,
            default=default_statuses  # Pre-select all statuses
        )
        
        if not selected_statuses:
            st.error("Please select at least one status to retrieve data.")
            st.stop()
        
        # Fetch and Clean DreamClass Data
        if st.button("Fetch DreamClass Data"):
            try:
                raw_dreamclass_data = fetch_dreamclass_data(
                    st.secrets["dreamclass_api"]["base_url"],
                    selected_statuses
                )
                st.write("Raw DreamClass Data", raw_dreamclass_data.head())  # Display raw data for debugging
        
                dreamclass_data = clean_dreamclass_data(raw_dreamclass_data)
                st.session_state["dreamclass_data"] = dreamclass_data
        
                st.success("DreamClass data retrieved and cleaned successfully!")
                st.dataframe(dreamclass_data)  # Display cleaned data
            except Exception as e:
                st.error(f"Failed to retrieve or clean DreamClass data: {e}")
        
    
        # Fetch Google Analytics Data
        st.subheader("Google Analytics Data Retrieval")
        if st.button("Fetch Google Analytics Data"):
            try:
                ga_data = fetch_ga_data(start_date, end_date)
                ga_data = ga_data.rename(columns={
                    'firstUserCampaignName': 'First user campaign',
                    'firstUserSourceMedium': 'First user source / medium',
                    'customUser:icpGroup': 'icp_group',
                    'customUser:schoolType': 'school_type',
                    'customUser:userId': 'userId',
                    'firstUserGoogleAdsAdGroupName': 'Google Ads Ad Group'
                })
                st.session_state["ga_data"] = ga_data
                st.success("Google Analytics data retrieved and processed successfully!")
                st.dataframe(ga_data)
            except Exception as e:
                st.error(f"Failed to fetch GA data: {e}")

    # Run Scoring Section
    if section == "Run Scoring":
        st.header("Run Lead Scoring")
    
        # Check if data is in session state
        if "dreamclass_data" in st.session_state and "ga_data" in st.session_state:
            dreamclass_data = st.session_state["dreamclass_data"]
            ga_data = st.session_state["ga_data"]
    
            # Convert createdAt to datetime for filtering
            dreamclass_data["createdAt"] = pd.to_datetime(dreamclass_data["createdAt"], format="%Y-%m-%d", errors="coerce")
    
            # Filter DreamClass data within the selected date range
            filtered_dreamclass_data = dreamclass_data[
                (pd.to_datetime(dreamclass_data["createdAt"]) >= pd.to_datetime(st.session_state["date_min"])) &
                (pd.to_datetime(dreamclass_data["createdAt"]) <= pd.to_datetime(st.session_state["date_max"]))
            ]
            
            # Perform lead scoring on filtered data
            scored_data = apply_lead_scoring(filtered_dreamclass_data, ga_data)
            st.session_state["scored_data"] = scored_data  # Store scored data in session state
            st.success("Lead scoring completed!")
            st.write("Scored Leads Sample", scored_data.head())
        else:
            st.info("Please upload data files first in the 'Retrieve Data' section.")
            

    
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
