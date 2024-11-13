# Lead Scoring Tool for DreamClass leads
# v2.10 by Aristeidis Kypriotis

import pandas as pd

# Import scoring functions from scoring_functions.py
from scoring_functions import (
    email_domain_score,
    organization_name_score,
    email_username_score,
    name_score,
    engagement_score,
    country_score,
    icp_score,
    assign_lead_class
)

# Define scoring weights and shared lists
weights = {
    'email_domain': 1,
    'organization_name': 2,
    'email_username': 1,
    'name': 2,
    'adminLogins': 1,
    'country': 1,
    'icp_group': 1
}

# Main function to apply scoring to dataframes
def apply_lead_scoring(dreamclass_data: pd.DataFrame, ga_data: pd.DataFrame) -> pd.DataFrame:
    # Rename and merge dataframes
    dreamclass_data = dreamclass_data.rename(columns={'id': 'userId'})
    ga_data = ga_data.rename(columns={'Country': 'country', 'icpGroup': 'icp_group'})
    merged_df = pd.merge(dreamclass_data, ga_data, on='userId', how='left', suffixes=('', '_ga')).fillna('missing')
    merged_df['First user source / medium'] = merged_df['First user source / medium'].str.lower()

    # Separate leads and customers
    lead_statuses = ['trial', 'trial_expired', 'incomplete_expired']
    merged_data_leads = merged_df[merged_df['status'].isin(lead_statuses)]
    
    # Apply scoring
    merged_data_leads['email_domain_score'] = merged_data_leads.apply(lambda row: email_domain_score(row['email'], row['organization']), axis=1)
    merged_data_leads['organization_name_score'] = merged_data_leads['organization'].apply(organization_name_score)
    merged_data_leads['email_username_score'] = merged_data_leads.apply(lambda row: email_username_score(row['email'], row['name'], row['organization'], 1), axis=1)
    merged_data_leads['name_score'] = merged_data_leads['name'].apply(name_score)
    merged_data_leads['engagement_score'] = merged_data_leads['adminLogins'].apply(engagement_score)
    merged_data_leads['country_score'] = merged_data_leads['country'].apply(country_score)
    merged_data_leads['icp_score'] = merged_data_leads['icp_group'].apply(icp_score)
    
    # Calculate total score and assign lead class
    merged_data_leads['total_score'] = (
        weights['email_domain'] * merged_data_leads['email_domain_score'] +
        weights['organization_name'] * merged_data_leads['organization_name_score'] +
        weights['email_username'] * merged_data_leads['email_username_score'] +
        weights['name'] * merged_data_leads['name_score'] +
        weights['adminLogins'] * merged_data_leads['engagement_score'] +
        weights['country'] * merged_data_leads['country_score'] +
        weights['icp_group'] * merged_data_leads['icp_score']
    )
    merged_data_leads['lead_class'] = merged_data_leads['total_score'].apply(assign_lead_class)
    
    # Return scored leads data
    return merged_data_leads

