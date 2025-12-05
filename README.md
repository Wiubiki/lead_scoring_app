# Lead Scoring App

The Lead Scoring App is a full-featured Streamlit application that automates lead quality assessment by integrating and scoring data from Google Analytics (GA4) and DreamClass. The application provides end-to-end functionality for data retrieval, scoring, reporting, advanced analytics, and longitudinal evaluation of lead quality.

This version (v3.1.0) introduces a redesigned architecture, new Advanced Analytics features (including XmR control charts and the Lead Quality Index), a production-grade Supabase integration, and full environment segregation between nightly and production deployments.

--- 
## Table of Contents
1. Features
2. Architecture Overview
3. Environments (Nightly & Production)
4. Technologies Used
5. Setup Instructions
6. Deployment (Streamlit Cloud)
7. Redirect Handling for Legacy Deployment
8. Troubleshooting

--- 
## 1. Features
### Automated Data Retrieval
- Fetches and prepares data from GA4 and DreamClass APIs.
- Supports periodic scoring runs.

### Lead Scoring Engine
- Vectorized scoring logic.
- Exportable run outputs.

### Reporting
- Historical scoring run summaries.
- Class distribution tracking.

### Advanced Analytics
- XmR control charts for lead quality stability.
- LQI (Lead Quality Index) generated at database level.
- Interpretation & FAQ.

### Authentication Modes
- Admin: full scoring + reports.
- Non-admin: read-only access.

### Environment Separation
- Distinct Supabase projects for nightly and production.

--- 
## 2. Architecture Overview
lead_scoring_app/
│
├── app.py
├── ui/
│   ├── scoring_page.py
│   ├── results_page.py
│   ├── reports_page.py
│   └── widgets/xmr_charts.py
├── utils/
│   ├── supabase_client.py
│   ├── advanced_analytics.py
├── scoring/
├── assets/
└── src/app.py  (legacy redirect app)

--- 
## 3. Environments

### Nightly
[supabase]
url="https://<nightly>.supabase.co"
service_key="<nightly>"
scoring_bucket="scoring-runs-nightly"
env="nightly"

### Production
[supabase]
url="https://<prod>.supabase.co"
service_key="<prod>"
scoring_bucket="scoring-runs-production"
env="production"

--- 
## 4. Technologies
Streamlit, Supabase, Plotly, pandas, numpy, GA4 API.

--- 
## 5. Setup

### Clone repo
git clone <repo>
cd lead_scoring_app

### Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

### Add secrets
Create .streamlit/secrets.toml with environment-specific Supabase credentials.

### Run
streamlit run app.py

--- 
## 6. Deployment
- Nightly deploy uses dev branch + nightly secrets.
- Production deploy uses main branch + production secrets.
- Legacy app uses src/app.py redirect.

--- 
## 7. Redirect Handling
Old Streamlit deployment still active and redirects to new production app.

--- 
## 8. Troubleshooting
500 errors: usually Supabase outage or wrong URL.
Missing secrets: ensure proper [supabase] block.
XmR errors: ensure numeric data and plotly installed.