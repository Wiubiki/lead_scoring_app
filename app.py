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
    # Already logged in -> let the app continue
    if st.session_state.get("auth_ok"):
        return True

    # Small vertical spacer so it's not glued to the top
    st.markdown("<div style='height: 12vh'></div>", unsafe_allow_html=True)

    # Centered layout: empty | login | empty
    left, center, right = st.columns([1, 1, 1])

    with center:
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

    # If we’re here, user is not authenticated yet -> stop app after showing login
    st.stop()



# --- MAIN ROUTER --------------------------------------------------------------

def main():
    require_auth()

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Scoring"

    nav_options = ["Scoring", "Results", "Reports"]

    nav_options = ["Scoring", "Results", "Reports"]
    current = st.session_state.get("nav", "Scoring")
    nav = st.sidebar.radio(
        "Navigation",
        nav_options,
        index=nav_options.index(current),
    )
    st.session_state["nav"] = nav



    if nav == "Data Retrieval & Scoring":
        render_scoring()
    elif nav == "Results":
        render_results()
    else:
        render_reports()


if __name__ == "__main__":
    main()

