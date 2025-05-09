# Lead Scoring App

The Lead Scoring App is a fully functional MVP designed to streamline the lead scoring process by integrating data from Google Analytics (GA4) and DreamClass. The app provides features for automated data retrieval, scoring, and summary report generation.

---

## Table of Contents
1. [Features](#features)
2. [Technologies Used](#technologies-used)
3. [Setup Instructions](#setup-instructions)
   - [Clone the Repository](#clone-the-repository)
   - [Install Dependencies](#install-dependencies)
   - [Handle Sensitive Files](#handle-sensitive-files)
   - [Run the App Locally](#run-the-app-locally)
   - [Collaborator Workflow](#collaborator-workflow)
4. [Deployment](#deployment)
   - [Streamlit Community Cloud](#streamlit-community-cloud)
5. [Troubleshooting](#troubleshooting)

---

## Features
- **Data Retrieval**: 
  - Fetches data from Google Analytics and DreamClass APIs.
  - Supports both manual uploads and API-based synchronization.
- **Lead Scoring**:
  - Processes data to assign lead scores based on custom criteria.
  - Provides detailed filtering and sorting options for scored leads.
- **Report Generation**:
  - Generates summary reports with customizable date ranges and grouping dimensions.
  - Includes download options for CSV files.
- **Authentication**:
  - Secures app access with user authentication.

---

## Technologies Used
- **Backend**: Python
- **Frontend**: Streamlit
- **APIs**: Google Analytics Data API, DreamClass API
- **Libraries**: 
  - `pandas`, `numpy`, `matplotlib` for data processing and visualization.
  - `bcrypt` for authentication.
  - `streamlit` for app development.

---

## Setup Instructions

### Clone the Repository
1. Clone the main repository:
   ```bash 
   git clone https://github.com/wiubiki/lead_scoring_app.git
   cd lead_scoring_app
   ```

2. Initialize and update the submodule for sensitive files:
   ```bash
   git submodule update --init --recursive
   ```

### Install Dependencies
1. Create a virtual environment:
   ```bash
   python3 -m venv lead_scoring_env
   source lead_scoring_env/bin/activate  # Linux/MacOS
   lead_scoring_env\Scripts\activate    # Windows
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

### Handle Sensitive Files
The app requires a `secrets.toml` file to function properly. This file is stored securely in the `app_sensitive_files` submodule.


1. Make sure you have access to the private submodule. If not, contact the project maintainer.

2. Create a symlink to the `secrets.toml` file:
   ```bash
   ln -s ../app_sensitive_files/.streamlit/secrets.toml .streamlit/secrets.toml
   ```

3. Verify the symlink:
   ```bash
   realpath .streamlit/secrets.toml
   ```
 

### Running the App Locally
1. Activate your virtual environment:
   ```bash
   source lead_scoring_env/bin/activate  # Linux/MacOS
   ```

2. Run the Streamlit app:
   ```bash 
   streamlit run src/app.py
   ```

---

## Collaborator Workflow
All contributions should be made through **feature branches** and submitted as Pull Requests (PRs) to the `dev` branch.

1. **Create a Feature Branch**
	```bash
	git checkout dev
	git pull origin dev
	git checkout -b feature/your-feature-name

	```
2. **Push Your Branch**
	```bash
	git add .
	git commit -m "Describe your changes"
	git push origin feature/your-feature-name
	
	```

3. **Submit a Pull Request (PR)**
- Go to GitHub and open a PR from your feature branch into `dev`.
- Assign the PR to the maintainer for review,
- Use clear commit messages and ensure code runs before submitting.


## Deployment

### Streamlit Community Cloud
1. **Set up Secrets**:  
   Configure the Google Analytics credentials and other sensitive data in the **Secrets Management** section of the Streamlit Community Cloud platform.

2. **Push to Main Branch**:  
   The deployment is linked to the main branch. Ensure all updates are pushed to `main`:
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

3. The app will automatically update on Streamlit Community Cloud.

---

## Troubleshooting

### Common Errors and Fixes
1. **"No secrets found"**:
   - Ensure the `secrets.toml` symlink is correctly configured.
   - Confirm the `app_sensitive_files` submodule is initialized and updated.

2. **Google Analytics Data Retrieval Fails**:
   - Verify that the Google Analytics API is enabled.
   - Check the credentials in `secrets.toml`.

3. **Symbolic Link Issues**:
   - Use absolute paths if relative paths are not resolving correctly.

4. **Data Parsing Errors**:
   - Check the raw data format for inconsistencies.
   - Update parsing logic in `dreamclass_data_handler.py` if needed.

---
