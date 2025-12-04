# app.py
import streamlit as st
import pathlib
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render_reports_page as render_reports
from auth_library import authenticate
from auth_library import require_auth



# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------
st.set_page_config(page_title="Lead Scoring App", layout="wide")
if st.session_state.get("authenticated"):
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
if not st.session_state.get("authenticated"):
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





# -------------------------------------------------------------------
# MAIN ROUTER 
# -------------------------------------------------------------------
def main():
    require_auth()

    is_admin = st.session_state.get("is_admin", False)

    # ------------------------------
    # ADMIN: full app
    # ------------------------------
    if is_admin:

        # Wizard/session setup
        if "wizard_current_step" not in st.session_state:
            st.session_state["wizard_current_step"] = 0
        if "wizard_completed" not in st.session_state:
            st.session_state["wizard_completed"] = set()

        # Render admin sidebar
        render_sidebar()

        # Normal navigation
        current = st.session_state.get("nav", "Scoring")

        if current == "Scoring":
            render_scoring()
        elif current == "Results":
            render_results()
        elif current == "Reports":
            render_reports()
        else:
            render_scoring()

    # ------------------------------
    # NON-ADMIN: Reports only
    # ------------------------------
    else:
        st.session_state["nav"] = "Reports"

        # Minimal sidebar (optional)
        with st.sidebar:
            st.markdown("## DreamClass Lead Scoring App")
            st.caption("Read-only access")

        render_tools_block()
        render_reports()


# -------------------------------------------------------------------
# SIDEBAR NAVIGATION 
# -------------------------------------------------------------------

# Tools section helper function
def render_tools_block():
    st.sidebar.markdown("---")
    st.sidebar.write(
        "<h4 style='color: #ffffff;'>Tools & Resources</h4>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        """
        <div style="margin-top: 0.5rem;">
            <a href="https://xmrtool-standalone.streamlit.app/" target="_blank"
            style="
                color: #ddc507;
                text-decoration: none;
                font-weight: 600;
                font-size: 0.95rem;
            ">
                XmR Control Chart Tool
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        """
        <div style="margin-top: 0.5rem;">
            <a href="https://github.com/Wiubiki/lead_scoring_app" target="_blank"
            style="
                color: #ddc507;
                text-decoration: none;
                font-weight: 600;
                font-size: 0.95rem;
            ">
                Github Repository
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        st.session_state["reports_jump"] = None
        st.rerun()

    render_tools_block()

# -------------------------------------------------------------------
if __name__ == "__main__":
    main()
