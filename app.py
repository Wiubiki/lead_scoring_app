# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports
from auth_library import authenticate

st.set_page_config(page_title="Lead Scoring App", layout="wide")

# --- AUTH WRAPPER -------------------------------------------------------------
def require_auth():
    """Render login UI and block app until auth succeeds."""
    if st.session_state.get("auth_ok"):
        return True

    st.title("Login")

    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

    if submitted:
        try:
            authed = authenticate(u, p)
        except Exception as e:
            st.error(f"Auth error: {e}")
            st.stop()

        if authed:
            st.session_state["auth_ok"] = True
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")
            st.stop()

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

