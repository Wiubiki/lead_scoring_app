# app.py
import streamlit as st
import pathlib
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render_reports_page as render_reports
from auth_library import authenticate


# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------
st.set_page_config(page_title="Lead Scoring App", layout="wide")
if st.session_state.get("auth_ok"):
    st.markdown("<body class='logged-in'>", unsafe_allow_html=True)
else:
    st.markdown("<body class='logged-out'>", unsafe_allow_html=True)


# -------------------------------------------------------------------
# Function to load CSS from the 'assets' folder
# -------------------------------------------------------------------
def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Load the external CSS
css_path = pathlib.Path("assets/styles.css")
load_css(css_path)



# Dynamic background logic BEFORE rendering the page
if not st.session_state.get("auth_ok"):
    st.markdown("""
        <style>
            :root {
                --app-bg: linear-gradient(180deg, #05a988 0%, #00241e 100%);
            }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            :root {
                --app-bg: #ffffff;
            }
        </style>
    """, unsafe_allow_html=True)


# -------------------------------------------------------------------
# AUTH LAYER
# -------------------------------------------------------------------
def require_auth():
    if st.session_state.get("auth_ok"):
        return True
    

    # Page headings
    st.title("DreamClass Lead Scoring App")
    st.subheader("Please login to continue")

    # Login box container (you still want this — styling hook + layout)
    login_container = st.container(key="login-box")

    with login_container:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login-username")
            password = st.text_input("Password", type="password", key="login-password")
            submitted = st.form_submit_button("Login")

    if submitted:
        try:
            authed = authenticate(username, password)
        except Exception as e:
            st.error(f"Authentication error: {e}")
            st.stop()

        if authed:
            st.session_state["auth_ok"] = True
            st.session_state["nav"] = "Scoring"
            st.rerun()
        else:
            st.error("Invalid credentials.")

    st.stop()



# -------------------------------------------------------------------
# MAIN ROUTER 
# -------------------------------------------------------------------
def main():
    if "wizard_current_step" not in st.session_state:
        st.session_state["wizard_current_step"] = 0
    if "wizard_completed" not in st.session_state:
        st.session_state["wizard_completed"] = set()

    require_auth()
    render_sidebar()

    current = st.session_state.get("nav", "Scoring")

    if current == "Scoring":
        render_scoring()
    elif current == "Results":
        render_results()
    elif current == "Reports":
        render_reports()
    else:
        render_scoring()



# -------------------------------------------------------------------
# SIDEBAR NAVIGATION 
# -------------------------------------------------------------------
def render_sidebar():
    # Read unified wizard state
    current_step = st.session_state.get("wizard_current_step", 0)
    completed_steps = st.session_state.get("wizard_completed", set())

    # Sidebar header
    sidebar_header = st.sidebar.container(key="sidebar-header")
    sidebar_header.markdown("## DreamClass Lead Scoring App")
    sidebar_header.markdown(
        "<span class='version-badge'>v3.01</span>",
        unsafe_allow_html=True,
    )

    # Map step numbers to page names
    step_pages = {
        0: "Scoring",   # Fetch Data step
        1: "Scoring",   # Run Scoring step
        2: "Results",   # Results step
    }

    def step_button(base_label: str, step_number: int):
        # Determine step state
        if step_number in completed_steps:
            status = "done"
            prefix = "🟩 "
        elif step_number == current_step:
            status = "active"
            prefix = "🟦 "
        else:
            status = "locked"
            prefix = "⬜ "

        label = f"{prefix}{base_label}"

        clicked = st.sidebar.button(
            label,
            key=f"sidebar-step-{step_number}",
            disabled=(status == "locked"),
        )

        if clicked:
            st.session_state["nav"] = step_pages[step_number]
            st.session_state["wizard_current_step"] = step_number
            st.rerun()

    # Buttons = the stepper
    step_button("Fetch Data", 0)
    step_button("Run Scoring", 1)
    step_button("View Results", 2)
    st.sidebar.markdown("---")
    
    # Reports Button
    if st.sidebar.button("📄 Reports", key="nav-reports"):
        st.session_state["nav"] = "Reports"
        st.rerun()



# -------------------------------------------------------------------
if __name__ == "__main__":
    main()
