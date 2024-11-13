# Lead Scoring Tool for DreamClass leads
# v2.10
# by Aristeidis Kypriotis


import pandas as pd
import os

# Define file paths for input and output
dreamclass_file_path = "input_files/dreamclassAccounts.csv"
ga_file_path = "input_files/googleanalytics_data.csv"
output_master_file = "output_files/output_master_file.csv"
output_summary_source_medium = "output_files/summary_source_medium.csv"
output_summary_source_medium_campaign = "output_files/summary_source_medium_campaign.csv"

# Check if input files exist
if not os.path.exists(dreamclass_file_path) or not os.path.exists(ga_file_path):
    raise FileNotFoundError("Input files not found in 'input_files' folder. Please add the files and try again.")

# Load the input files
dreamclass_data = pd.read_csv(dreamclass_file_path)
ga_data = pd.read_csv(ga_file_path)


# Rename 'id' to 'userId' in DreamClass data for merging
dreamclass_data = dreamclass_data.rename(columns={'id': 'userId'})

# Rename 'Country' to 'country' in Google Analytics data for merging
ga_data = ga_data.rename(columns={'Country': 'country'})

# Rename 'icpGroup' to 'icp_group' in Google Analytics data for merging
ga_data = ga_data.rename(columns={'icpGroup': 'icp_group'})

# Rename 'icpGroup' to 'icp_group' in Google Analytics data for merging
ga_data = ga_data.rename(columns={'icpGroup': 'icp_group'})

# Merge the two dataframes on 'userId'
merged_data = pd.merge(dreamclass_data, ga_data, on='userId', how='left', suffixes=('', '_ga'))

# Fill missing values with 'missing' for consistency
merged_data = merged_data.fillna('missing')

# Normalize 'first_user_source_medium' to lowercase for consistency
merged_data['First user source / medium'] = merged_data['First user source / medium'].str.lower()

# Ensure 'status' column is available to classify leads and customers

# Filter accounts by status
lead_statuses = ['trial', 'trial_expired', 'incomplete_expired']
customer_statuses = ['active', 'canceled', 'past_due', 'locked_out']

# Separate into leads and customers based on status
merged_data_leads = merged_data[merged_data['status'].isin(lead_statuses) | ~merged_data['status'].isin(customer_statuses)]
merged_data_customers = merged_data[merged_data['status'].isin(customer_statuses)]

# Save the separated files
merged_data_leads.to_csv('output_files/merged_data_leads.csv', index=False)
merged_data_customers.to_csv('output_files/merged_data_customers.csv', index=False)

print("Files merged_data_leads.csv and merged_data_customers.csv have been generated and saved to output_files/")


# Define scoring functions
# Define the weights for each score component
weights = {
    'email_domain': 1,
    'organization_name': 2,
    'email_username': 1,
    'name': 2,
    'adminLogins': 1,  # 11 Nov edit: reduced from 1.5. It has a built-in linear scaling already
    'country': 1,
    'icp_group': 1
}

# Shared lists for common domains and expanded educational keywords
common_domains = ['gmail', 'yahoo', 'outlook', 'icloud', 'aol', 'mail', 'protonmail', 
                  'zoho', 'yandex', 'gmx', 'live', 'googlemail', 'test', 'example']

educational_keywords = ['academy', 'school', 'institute', 'college', 'university',
                        'christian', 'education', 'learning', 'montessori', 'church',
                        'training', 'conservatory', 'islamic', 'quran', 'saint', 
                        'académie', 'schola', 'career', 'scuola', 'charter', 
                        'foundation', 'prep', 'STEM', 'tech']
                        
generic_keywords = ['info', 'admin', 'test', 'principal', 'registrar', 'accounting', 'support']

suffixes = ['jr', 'sr', 'ii', 'iii', 'iv']

titles = ['admin', 'principal', 'hr', 'registrar', 'teacher', 'director', 'support']



# Email domain score function
def email_domain_score(email, organization):
    domain = email.split('@')[-1].split('.')[0]
    
    if domain in common_domains:
        return 0
    elif any(keyword in domain for keyword in educational_keywords) or organization.lower() in domain:
        return 1
    else:
        return 0.5

# Organization name score function
def organization_name_score(organization):
    if any(keyword in organization.lower() for keyword in educational_keywords):
        return 1
    elif any(keyword in organization.lower() for keyword in ['test', 'example', 'demo']):
        return -1
    return 0

# Email username score function with latest adjustments
def email_username_score(email, name, organization, email_domain_score):
    username = email.split('@')[0]
    email_domain = email.split('@')[-1].split('.')[0]
 
    # Clean and parse name
    name = name.replace(",", " ")  # Handle cases like "Nathan, W, Owens"
    name_parts = [part.lower() for part in name.split() if part.lower() not in suffixes]

    # Check for title-based names
    if any(title in name_parts for title in titles):
        return 0  # Neutral score for title-only names

    # Extract first and last names
    first_name = name_parts[0] if len(name_parts) > 0 else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    # Scoring logic
    # 1. Randomness Check
    if any(char.isdigit() for char in username) and sum(char.isdigit() for char in username) >= 3:
        return 0 if email_domain_score == 1 else -1  # Neutral if professional domain, otherwise -1
    
    # 2. Generic Keywords Check
    elif any(keyword in username for keyword in generic_keywords):
        if email_domain_score == 1:
            return 1  # Professional domain + generic username
        elif email_domain_score == 0.5:
            return 0.5  # Custom unrecognized domain + generic username
        return 0  # Common domain + generic username, default

    # 3. Name and Organization Match Check
    if first_name in username or last_name in username or organization.lower() in username:
        return 1.5 if email_domain_score == 1 else 0  # High score for match with professional domain

    # 4. Default Case
    return 0  # Default neutral score if none of the above

# Name score function for validation
def name_score(name):
    
    name_parts = [part.lower() for part in name.split() if part.lower() not in suffixes]
    
    # Check for title-based names
    if any(title in name_parts for title in titles):
        return 0  # Neutral score for title-only names
    
    # Assign score based on name format
    if len(name_parts) == 2:  # Typical first and last name
        return 1
    elif len(name_parts) == 1 and name_parts[0] not in generic_keywords:
        return 0.5  # Single name, somewhat reliable
    return -1  # Names that appear too generic or as placeholders

# Engagement score function (admin logins) with updated logic
def engagement_score(adminLogins):
    if adminLogins <= 1:
        return 0
    return adminLogins - 1  # New scaling formula

# Country score function
def country_score(country):
    if country == 'United States':
        return 1.5                    # 11 Nov edit: reduced all scores by -0.5. A score of 2 is probably too high
    elif country in ['United Kingdom', 'Canada', 'Australia']:
        return 1
    elif country == 'Europe' and country != 'Greece':
        return 0.5
    return 0

# ICP group score function
def icp_score(icp_group):
    return 1 if icp_group == 1 else (0.5 if icp_group == 2 else 0)

# Lead class assignment based on updated total score ranges
def assign_lead_class(total_score):
    if total_score > 7:
        return 1
    elif 7 >= total_score >= 5:
        return 2
    elif 5 > total_score >= 3:
        return 3
    return 4  # Lead Class 4 for total_score < 3

# Applying the scoring to the dataframe
def apply_lead_scoring(merged_df):
    merged_df['email_domain_score'] = merged_df.apply(lambda row: email_domain_score(row['email'], row['organization']), axis=1)
    merged_df['organization_name_score'] = merged_df['organization'].apply(organization_name_score)
    merged_df['email_username_score'] = merged_df.apply(lambda row: email_username_score(row['email'], row['name'], row['organization'], 1), axis=1)
    merged_df['name_score'] = merged_df['name'].apply(name_score)
    merged_df['engagement_score'] = merged_df['adminLogins'].apply(engagement_score)
    merged_df['country_score'] = merged_df['country'].apply(country_score)
    merged_df['icp_score'] = merged_df['icp_group'].apply(icp_score)
    
    # Calculate total score
    merged_df['total_score'] = (
        weights['email_domain'] * merged_df['email_domain_score'] +
        weights['organization_name'] * merged_df['organization_name_score'] +
        weights['email_username'] * merged_df['email_username_score'] +
        weights['name'] * merged_df['name_score'] +
        weights['adminLogins'] * merged_df['engagement_score'] +
        weights['country'] * merged_df['country_score'] +
        weights['icp_group'] * merged_df['icp_score']
    )
    
    # Assign lead class based on the updated logic
    merged_df['lead_class'] = merged_df['total_score'].apply(assign_lead_class)
    
    # Return the entire dataframe with all columns and new scores
    return merged_df


# Load the leads file for scoring
leads_data = pd.read_csv('output_files/merged_data_leads.csv')

# Apply the scoring process to leads_data
scored_data = apply_lead_scoring(leads_data)

# Save the master file with scored leads
scored_data.to_csv('output_files/output_master_file.csv', index=False)

print("Scoring completed on leads. Master file saved as output_master_file.csv in output_files/")
