# scoring_functions.py

from rapidfuzz import fuzz


# Shared lists for common domains and expanded educational keywords
common_domains = ['gmail', 'yahoo', 'outlook', 'icloud', 'aol', 'mail', 'protonmail', 
                  'zoho', 'yandex', 'gmx', 'live', 'googlemail', 'test', 'example', 'bing', 'hotmail']

educational_keywords = ['academy', 'school', 'institute', 'college', 'university',
                        'christian', 'education', 'learning', 'montessori', 'church',
                        'training', 'conservatory', 'islamic', 'quran', 'saint', 
                        'académie', 'schola', 'career', 'scuola', 'charter', 
                        'foundation', 'prep', 'STEM', 'tech']

secondary_keywords = ['middle', 'high', 'primary', 'tutor']
                        
generic_keywords = ['info', 'admin', 'test', 'principal', 'registrar', 'accounting', 'support']

suffixes = ['jr', 'sr', 'ii', 'iii', 'iv']

titles = ['admin', 'principal', 'hr', 'registrar', 'teacher', 'director', 'support']

# Scoring functions

# Email domain score function
def email_domain_score(email, organization):
    domain = email.split('@')[-1].split('.')[0]
    
    if domain.endswith('.edu') or domain.endswith('.ac'):
        return 1
    elif domain in common_domains:
        return 0
    elif any(keyword in domain for keyword in educational_keywords) or organization.lower() in domain:
        return 1
    return 0.5


# Organization name score function
def organization_name_score(organization):
    org_lower = organization.lower()
    
    # Check for primary educational keywords
    for keyword in educational_keywords:
        if fuzz.partial_ratio(org_lower, keyword) >= 85:  # Adjust threshold as needed
            return 1

    # Check for secondary keywords
    for keyword in secondary_keywords:
        if fuzz.partial_ratio(org_lower, keyword) >= 85:
            return 0.5

    # Check for test-related keywords
    if any(keyword in org_lower for keyword in ['test', 'example', 'demo']):
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
        return 1.5 if email_domain_score == 1 else 0.5  # Adjusted match score for leniency

    # 4. Default Case
    return 0  # Default neutral score if none of the above

# Name score function for validation
def name_score(name):
    name_parts = [part.lower().strip('.') for part in name.split() if part.lower().strip('.') not in suffixes]
    
    if any(title in name_parts for title in titles):
        return 0
    
    if len(name_parts) >= 2 and all(part.isalpha() for part in name_parts):
        return 1
    elif len(name_parts) == 1 and name_parts[0] not in generic_keywords:
        return 0.5
    elif len(name_parts) >= 2 and any(part.islower() or part.isupper() for part in name_parts):
        return 0
    return -1

    

# Engagement score function (admin logins) with updated logic
def engagement_score(adminLogins):
    if adminLogins <= 1:
        return 0
    return adminLogins - 1  # New scaling formula

# Country score function
def country_score(country):
    if country == 'United States':
        return 2
    elif country in ['United Kingdom', 'Canada', 'Australia']:
        return 1.5
    elif country == 'Europe' and country != 'Greece':
        return 1
    return 0

# ICP group score function
def icp_score(icp_group):
    return 1 if icp_group == 1 else (0.5 if icp_group == 2 else 0)
    
    
# Assign Lead Class based in the following criteria
def assign_lead_class(total_score):
    if total_score > 7:
        return 1
    elif 7 >= total_score >= 5:
        return 2
    elif 5 > total_score >= 3:
        return 3
    return 4
    

