# ui/reports_page.py
# Purpose: Reports page (formerly "Summary Reports")
# - Historical KPIs + XmR with WE/Nelson rules
# - Zero logic here; purely delegates to existing implementation

from __future__ import annotations
import streamlit as st

def render() -> None:
    st.title("Reports")

    tried = []
    # Try common locations; adjust once you know the exact module
    candidates = [
        ("reports.summary", "render"),
        ("reports.summary_reports", "render"),
        ("reports.xmr", "render"),
        ("ui.summary_reports", "render"),
        ("features.reports", "render"),
    ]
    for modpath, fn in candidates:
        try:
            mod = __import__(modpath, fromlist=[fn])
            getattr(mod, fn)()
            return
        except Exception as e:
            tried.append(f"{modpath}.{fn}: {e}")

    st.error("Reports renderer not found. Verify the module path for your existing Summary Reports.")
    with st.expander("Details"):
        st.code("\n".join(tried))