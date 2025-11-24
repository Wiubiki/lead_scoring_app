# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports
from auth_library import authenticate

# -------------------------------------------------------------------
# PAGE SETUP
# -------------------------------------------------------------------
st.set_page_config(page_title="Lead Scoring App", layout="wide")

# -------------------------------------------------------------------
# GLOBAL CSS (Login + Sidebar Styling)
# -------------------------------------------------------------------
def inject_global_css():
    """Set background depending on auth state + login styles."""
    auth_ok = st.session_state.get("auth_ok", False)

    # Background: gradient on login, white after login
    if not auth_ok:
        bg = "linear-gradient(180deg, #006550 0%, #004237 100%)"
        padding_top = "18vh"
    else:
        bg = "#FFFFFF"
        padding_top = "2rem"

    st.markdown(
        f"""
        <style>
        /* Main app background */
        [data-testid="stAppViewContainer"] {{
            background: {bg} !important;
        }}

        [data-testid="stAppViewContainer"] .block-container {{
            padding-top: {padding_top} !important;
        }}

        /* Login layout classes (only used on login screen) */
        .login-container {{
            max-width: 420px;
            margin: 0 auto;
            text-align: center;
        }}
        .login-box {{
            background: white;
            padding: 30px 25px;
            border-radius: 10px;
            box-shadow: 0 0px 10px rgba(0,0,0,0.15);
            margin-top: 20px;
        }}
        .login-header {{
            font-size: 2.2rem;
            font-weight: 700;
            color: white;
        }}
        .login-subheader {{
            font-size: 1.2rem;
            font-weight: 400;
            color: white;
            margin-bottom: 30px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------------
# AUTH LAYER
# -------------------------------------------------------------------
def require_auth():
    """Render login UI and block app until authentication succeeds."""
    if st.session_state.get("auth_ok"):
        return True

    # LOGIN PAGE
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='login-header'>DreamClass Lead Scoring App</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='login-subheader'>Please login to continue</div>",
        unsafe_allow_html=True,
    )

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
            st.session_state["nav"] = "Scoring"
            st.rerun()
        else:
            st.error("Invalid credentials.")

    # If we're here, still not authenticated
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
    inject_global_css()
    require_auth()
    render_sidebar()

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Scoring"

    nav_options = ["Scoring", "Results", "Reports"]
    current = st.session_state.get("nav", "Scoring")

    nav = st.sidebar.radio(
        "Navigation",
        nav_options,
        index=nav_options.index(current),
    )
    st.session_state["nav"] = nav

    if nav == "Scoring":
        render_scoring()
    elif nav == "Results":
        render_results()
    else:
        render_reports()

# -------------------------------------------------------------------
if __name__ == "__main__":
    main()
