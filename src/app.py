import streamlit as st
import pandas as pd
from lead_scoring_tool import apply_lead_scoring

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
    uploaded_ga = st.file_uploader("Upload Google Analytics Data", type=["csv"])

    # Store data in session state if both files are uploaded
    if uploaded_dreamclass and uploaded_ga:
        st.session_state["dreamclass_data"] = pd.read_csv(uploaded_dreamclass)
        st.session_state["ga_data"] = pd.read_csv(uploaded_ga)
        st.success("Data files uploaded and stored successfully!")

        # Display sample data
        st.write("DreamClass Data Sample", st.session_state["dreamclass_data"].head())
        st.write("GA Data Sample", st.session_state["ga_data"].head())

# Run Scoring Section
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
        
        import matplotlib.pyplot as plt

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


# Generate Summary Reports section

elif section == "Generate Summary Reports":
    st.header("Generate Summary Reports")

    # Controls Section
    st.subheader("Controls")

    # Date Range Selection
    start_date = st.date_input("Start Date", pd.to_datetime("2024-01-01"))
    end_date = st.date_input("End Date", pd.to_datetime("2024-12-31"))

    if start_date > end_date:
        st.error("Start date cannot be after end date.")

    # Dimension Mapping
    dimension_mapping = {
        "Source/Medium": "First user source / medium",
        "Campaign": "First user campaign"
    }

    # Dimension Selection
    st.write("**Choose dimensions for grouping:**")
    selected_dimensions = st.multiselect(
        "Group by",
        options=list(dimension_mapping.keys()),  # Display names
        default=["Source/Medium"]
    )

    if not selected_dimensions:
        st.warning("Please select at least one dimension for grouping.")

    # Translate display names to actual column names
    grouping_columns = [dimension_mapping[dim] for dim in selected_dimensions]

