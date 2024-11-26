# **Lead Scoring MVP**

A streamlined and interactive tool for evaluating and visualizing lead scoring metrics based on DreamClass data. This MVP allows for manual file uploads, real-time filtering, scoring calculations, and intuitive visualizations to assist sales and marketing teams in prioritizing leads.

---

## **Features**

- **Lead Scoring**: Calculates scores for leads based on predefined criteria such as email domain, organization name, engagement, and more.
- **Customer Comparison**: Provides insights into customer behavior by comparing lead scores with customer profiles.
- **Visualization**: Displays filtered results in a pie chart, showcasing the distribution of leads by class.
- **Date Filtering**: Allows users to filter results by `createdAt` date range.
- **Interactive GUI**: A user-friendly Streamlit-based interface for ease of navigation.

---

## **Technologies Used**

- **Streamlit**: For building the web-based interface.
- **Pandas**: For data manipulation and scoring calculations.
- **Matplotlib**: For generating visualizations.
- **Python**: The core programming language.

---

## **Installation**

### Prerequisites
- Python 3.10 or later
- Git

### Steps
 1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd lead_scoring_mvp
   ```
 2. Set up a virtual environemnt:
   ```bash
   python3 -m venv lead_scoring_env
   source lead_scoring_env/bin/activate
   ```
 3. Install dependancies:
   ```bash
   pip install -r requirements.txt
   ```
    
---

## **Usage**

 1. Start the App:
   ```bash
   streamlit run app.py
   ```
   
 2. Upload Data:
    - Upload the `dreamclassAccounts.csv` and `googleanalytics_data.csv` files.
  
 3. Run Scoring:
    - Use the "Run Scoring" button to process the uploaded data.
  
 4. View Results:
    - Navigate through the sidebar to filter by date and view results, including visualizations of lead distributions.


---

## **Folder Structure**

 - src/:
   - `app.py`: Main Streamlit application.
   - `lead_scoring_tool.py`: Lead scoring logic.
   - `scoring_functions.py`: Contains scoring functions.
   - `validation.py`: Validates and compares customer and lead profiles.
 - `input_files/`: Directory for uploading data files.
 - `output_files/`: Stores output files like `master_file.csv` and visualization data.
 
 --- 
 
 ## **Future Enhancements**
 
 - Automate data retrieval from APIs.
 - Advanced visualizations for better insights.
 - Store processed data in cloud storage for accessibility and collaboration.
 - Deploy the app on a server for team-wide usage.

---

## **License**
This project is licensed under the MIT License.


 

