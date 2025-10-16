# app.py
# v3 modular router-only Streamlit app
# - Navigation: Scoring / Results / Reports
# - Optional login via auth_library.authenticate (kept at project root)
# - All logic lives in data/*, scoring/*, ui/*

import streamlit as st

# Optional auth (kept from old app; safe to remove if not needed)
try:
    from auth_library import authenticate  # root-level per your note
except Exception:
    authenticate = None  # proceed without auth if module missing

from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports

st.set_page_config(page_title="Lead Scoring App", layout="wide")

# ---- Optional login gate -----------------------------------------------------
if authenticate:
    if "authed" not in st.session_state:
        st.session_state.authed = False

    if not st.session_state.authed:
        st.sidebar.subheader("Login")
        user = st.sidebar.text_input("Username")
        pwd = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Sign in"):
            if authenticate(user, pwd):
                st.session_state.authed = True
                st.sidebar.success("Signed in.")
            else:
                st.sidebar.error("Invalid credentials.")
        st.stop()

# ---- Router ------------------------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Scoring", "Results", "Reports"])

if page == "Scoring":
    render_scoring()
elif page == "Results":
    render_results()
else:  # "Reports"
    render_reports()
