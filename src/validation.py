# validation.py

"""
Validation Script for Lead Scoring Tool

This script performs validation on the lead scoring system by comparing average scores for key metrics 
between leads and customers. The process involves:

1. Loading the `output_master_file.csv` and `merged_data_customers.csv` files.
2. Applying individual scoring functions to the customer data for organization, name, email_username, 
   and email_domain metrics.
3. Generating a comparison table showing average scores for these metrics between leads and customers, 
   segmented by lead class.

The output provides insight into how closely lead scores align with customer scores, helping to validate 
and refine the lead scoring criteria.
"""

import pandas as pd

# Load leads and customers data
leads_data = pd.read_csv('output_files/output_master_file.csv') # Already scored leads
customers_data = pd.read_csv('output_files/merged_data_customers.csv') # Customers need scoring

print("Data files loaded successfully.")

# Import the scoring functions from scoring_functions.py
from scoring_functions import organization_name_score, name_score, email_username_score, email_domain_score

# Apply individual scores to customers data
customers_data['organization_name_score'] = customers_data['organization'].apply(organization_name_score)
customers_data['name_score'] = customers_data['name'].apply(name_score)
customers_data['email_username_score'] = customers_data.apply(
    lambda row: email_username_score(row['email'], row['name'], row['organization'], email_domain_score(row['email'], row['organization'])),
    axis=1
)
customers_data['email_domain_score'] = customers_data.apply(
    lambda row: email_domain_score(row['email'], row['organization']),
    axis=1
)

print("Individual scores applied to customer data.")

# Calculate average scores for customers
customer_averages = customers_data[['organization_name_score', 'name_score', 'email_username_score', 'email_domain_score']].mean()
customer_averages.name = 'Customers'

# Calculate average scores for leads, grouped by lead class
lead_averages = leads_data.groupby('lead_class')[['organization_name_score', 'name_score', 'email_username_score', 'email_domain_score']].mean()
lead_averages.index.name = 'Lead Class'

# Combine customer and lead averages into a single comparison table
comparison_table = lead_averages.copy()  # Start with lead averages
comparison_table.loc['Customers'] = customer_averages  # Add customer averages as a new row

# Save the comparison table to a CSV for review
comparison_table.to_csv('output_files/validation_comparison_table.csv')

print("Validation comparison table generated and saved as validation_comparison_table.csv in output_files/")
