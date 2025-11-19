# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports
from auth_library import authenticate

st.set_page_config(page_title="Lead Scoring App", layout="wide")

# --- AUTH WRAPPER -------------------------------------------------------------
import streamlit as st
from auth_library import authenticate

def require_auth():
    """Render login UI and block app until authentication succeeds."""
    if st.session_state.get("auth_ok"):
        return True

    # Center layout
    st.markdown(
        """
        <style>
            .centered {
                max-width: 400px;
                margin: auto;
                margin-top: 12vh;
                padding: 2rem;
                border-radius: 12px;
                background-color: #ffffff;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Outer container
    with st.container():
        st.markdown('<div class="centered">', unsafe_allow_html=True)

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

