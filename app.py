# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports
from auth_library import authenticate

# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------
st.set_page_config(
    page_title="DreamClass Lead Scoring App",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------------
# GLOBAL CSS (Login + Sidebar Styling)
# -------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* LOGIN BACKGROUND */
    body {
        background: linear-gradient(180deg, #006550 0%, #004237 100%) !important;
    }

    /* SIDEBAR HEADER */
    .sidebar-header {
        background: #006550;
        padding: 18px;
        color: white;
        font-size: 1.3rem;
        font-weight: 600;
        text-align: center;
        border-radius: 6px;
        margin-bottom: 12px;
    }

    /* SIDEBAR NAV BUTTONS */
    .nav-btn {
        display: block;
        padding: 12px 16px;
        margin: 6px 0;
        border-radius: 6px;
        font-weight: 600;
        text-align: left;
        width: 100%;
        border: 2px solid #00655022;
        cursor: pointer;
        font-size: 0.95rem;
    }
    .nav-btn-active {
        background: #006550;
        color: white !important;
        border-color: #006550;
    }
    .nav-btn-done {
        background: #e6f4ef;
        color: #006550 !important;
    }
    .nav-btn-locked {
        background: #f4f4f4;
        color: #777 !important;
        cursor: default;
    }

    /* LOGIN CARD */
    .login-container {
        max-width: 360px;
        margin: 0 auto;
        padding-top: 12vh;
        text-align: center;
    }
    .login-box {
        background: white;
        padding: 30px 25px;
        border-radius: 10px;
        box-shadow: 0 0px 10px rgba(0,0,0,0.15);
        margin-top: 20px;
    }
    .login-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: white;
    }
    .login-subheader {
        font-size: 1.2rem;
        font-weight: 400;
        color: white;
        margin-bottom: 30px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------------------------------------------------------
# AUTH LAYER
# -------------------------------------------------------------------
def require_auth():
    if st.session_state.get("auth_ok"):
        return True

    # LOGIN PAGE
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<div class='login-header'>DreamClass Lead Scoring App</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-subheader'>Please login to continue</div>", unsafe_allow_html=True)

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    st.markdown("</div></div>", unsafe_allow_html=True)

    if submitted:
        try:
            authed = authenticate(username, password)
        except Exception as e:
            st.error(f"Authentication error: {e}")
            st.stop()

        if authed:
            st.session_state["auth_ok"] = True
            st.session_state["nav"] = 1   # Step 1
            st.session_state["completed"] = set()
            st.rerun()
        else:
            st.error("Invalid credentials.")

    st.stop()


# -------------------------------------------------------------------
# SIDEBAR NAVIGATION (Option C)
# -------------------------------------------------------------------
def render_sidebar():
    current = st.session_state.get("nav", 1)
    completed = st.session_state.get("completed", set())

    # Header
    st.sidebar.markdown("<div class='sidebar-header'>Lead Scoring</div>", unsafe_allow_html=True)

    # Helper to build a button
    def step_button(label, step):
        if step == current:
            css = "nav-btn nav-btn-active"
        elif step in completed:
            css = "nav-btn nav-btn-done"
        else:
            css = "nav-btn nav-btn-locked"

        clicked = st.sidebar.button(
            label,
            key=f"nav_{step}",
            disabled=("locked" in css),
            help=None
        )
        if clicked:
            st.session_state["nav"] = step
            st.rerun()

    # Steps
    step_button("Fetch Data", 1)
    step_button("Run Scoring", 2)
    step_button("View Results", 3)


# -------------------------------------------------------------------
# MAIN ROUTER
# -------------------------------------------------------------------
def main():
    require_auth()
    render_sidebar()

    nav = st.session_state.get("nav", 1)

    if nav == 1:
        render_scoring()
    elif nav == 2:
        render_scoring()   # scoring page handles the second step
    elif nav == 3:
        render_results()


# -------------------------------------------------------------------
if __name__ == "__main__":
    main()
