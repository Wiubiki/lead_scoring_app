# Generate Summary Reports for DreamClass leads based on the data generated by lead_scoring_tool.py

import pandas as pd

def generate_summary(data, start_date, end_date, dimensions):
    """
    Generate a summary report grouped by specified dimensions for a given date range.

    Args:
        data (pd.DataFrame): Input dataset containing lead scoring results.
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        dimensions (list): List of dimensions to group by.

    Returns:
        pd.DataFrame: Summary DataFrame with calculated metrics.
    """
    # Filter data based on date range
    filtered_data = data[
        (data['createdAt'] >= pd.to_datetime(start_date)) &
        (data['createdAt'] <= pd.to_datetime(end_date))
    ]

    # Group by specified dimensions
    grouped = filtered_data.groupby(dimensions).agg(
        total_leads=('lead_class', 'size'),
        avg_total_score=('total_score', 'mean')
    )

    # Calculate lead class distribution
    lead_class_data = filtered_data.groupby(dimensions)['lead_class'].value_counts().unstack(fill_value=0)
    lead_class_percentages = lead_class_data.div(lead_class_data.sum(axis=1), axis=0)

    # Combine into a single summary
    summary = grouped.copy()
    for lead_class in [1, 2, 3, 4]:
        summary[f'class_{lead_class}_count'] = lead_class_data.get(lead_class, 0)
        summary[f'class_{lead_class}_percent'] = lead_class_percentages.get(lead_class, 0)

    return summary.reset_index()


# MAIN EXECUTION
if __name__ == "__main__":
    # Load the master file
    master_file_path = "output_files/output_master_file.csv"
    master_data = pd.read_csv(master_file_path, parse_dates=['createdAt'], dayfirst=True)


    print("Columns in master_data:", master_data.columns)

    # Prompt the user for start and end dates in the same format as the data
    start_date = pd.to_datetime(input("Enter the start date (DD/MM/YYYY): "), format='%d/%m/%Y')
    end_date = pd.to_datetime(input("Enter the end date (DD/MM/YYYY): "), format='%d/%m/%Y')


    # Prompt the user for dimensions to group by
    dimensions_input = input("Enter dimensions to group by, separated by commas (e.g., 'First user source / medium,First user campaign'): ")
    dimensions = [dim.strip() for dim in dimensions_input.split(',')]

    # Generate the summary
    summary = generate_summary(master_data, start_date, end_date, dimensions)

    # Convert start and end dates to strings for filenames
    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    # Save the summary report
    output_file_path = f"output_files/summary_{'_'.join(dimensions)}_{start_date_str}_to_{end_date_str}.csv"
    summary.to_csv(output_file_path, index=False)

    print(f"Summary report generated and saved to {output_file_path}")
