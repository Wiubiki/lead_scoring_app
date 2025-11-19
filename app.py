# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports
from auth_library import authenticate

st.set_page_config(page_title="Lead Scoring App", layout="wide")

# --- AUTH WRAPPER -------------------------------------------------------------


def require_auth():
    """Render login UI and block app until authentication succeeds."""
    if st.session_state.get("auth_ok"):
        return True

    # Inject proper centering + width constraints
    st.markdown(
        """
        <style>
            .login-wrapper {
                max-width: 420px !important;
                margin: 10vh auto !important;
                padding: 2rem;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            }
            .block-container {
                padding-top: 0 !important;
            }
            input, button, .stTextInput, .stPassword {
                max-width: 100% !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # The wrapper prevents Streamlit from expanding horizontally
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)

    st.markdown("## Login")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

    if submitted:
        try:
            authed = authenticate(username, password)
        except Exception as e:
            st.error(f"Authentication error: {e}")
            st.stop()

        if authed:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Invalid credentials.")
            st.stop()

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# --- MAIN ROUTER --------------------------------------------------------------

def main():
    require_auth()

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Scoring"

    nav = st.sidebar.radio("Go to", ["Scoring", "Results", "Reports"])
    st.session_state["nav"] = nav

    if nav == "Scoring":
        render_scoring()
    elif nav == "Results":
        render_results()
    else:
        render_reports()


if __name__ == "__main__":
    main()

