# app.py
import streamlit as st
from ui.scoring_page import render as render_scoring
from ui.results_page import render as render_results
from ui.reports_page import render as render_reports

st.set_page_config(page_title="Lead Scoring App", layout="wide")

# --- AUTH WRAPPER -------------------------------------------------------------

def require_auth():
    """Stops rendering until user is authenticated."""
    try:
        from auth_library import authenticate
    except Exception:
        return True  # fail-open for local dev

    auth = authenticate()
    if not auth:
        st.stop()
    return True


# --- MAIN ROUTER --------------------------------------------------------------

def main():
    # AUTH FIRST — stops here until login is complete
    require_auth()

    if "nav" not in st.session_state:
        st.session_state["nav"] = "Scoring"

    with st.sidebar:
        st.title("Navigation")
        page = st.radio("Go to", ["Scoring", "Results", "Reports"], index=["Scoring", "Results", "Reports"].index(st.session_state["nav"]))
        st.session_state["nav"] = page

    if page == "Scoring":
        render_scoring()
    elif page == "Results":
        render_results()
    else:
        render_reports()


if __name__ == "__main__":
    main()
