# ui/scoring_page.py
# Purpose: Scoring page (formerly "Run Scoring")
# - Fetch DreamClass & GA data via new handlers
# - Filter DreamClass by createdAt (inclusive)
# - Apply scoring and store results in session_state["scored_df"]
# - No renaming/cleaning or UI-side logic beyond flow control

from __future__ import annotations
import datetime as dt
import streamlit as st
import pandas as pd

from data.dreamclass_handler import fetch_and_clean as fetch_dc
from data.ga_handler import fetch_and_clean as fetch_ga
from scoring.lead_scores_calculator import apply as apply_scoring

@st.cache_data(show_spinner=False)
def _get_dc(base_url: str, statuses: tuple[str, ...]) -> pd.DataFrame:
    return fetch_dc(base_url=base_url, statuses=statuses)

@st.cache_data(show_spinner=False)
def _get_ga(start_date: str, end_date: str) -> pd.DataFrame:
    return fetch_ga(start_date=start_date, end_date=end_date)

def render() -> None:
    st.title("Scoring")

    # Sidebar controls (date range + statuses)
    st.sidebar.markdown("### Configuration")

    base_url = st.sidebar.text_input(
        "DreamClass API Base URL", value=st.session_state.get("DC_BASE_URL", "")
    )
    dc_statuses = st.sidebar.multiselect(
        "DreamClass statuses",
        options=["trialing", "active", "inactive", "canceled", "paused"],
        default=["trialing", "active"],
    )

    today = dt.date.today()
    start_date = st.sidebar.date_input("Start date", value=today.replace(day=1))
    end_date = st.sidebar.date_input("End date", value=today)
    if start_date > end_date:
        st.sidebar.error("Start date must be on or before End date.")
        return

    if st.button("Run Scoring"):
        if not base_url:
            st.error("Set DreamClass API Base URL.")
            return

        with st.spinner("Fetching DreamClass…"):
            DC_norm = _get_dc(base_url, tuple(dc_statuses))

        # Local DC filter (createdAt inclusive)
        with st.spinner("Filtering DreamClass by createdAt…"):
            if "createdAt" not in DC_norm.columns:
                st.error("DC_norm missing 'createdAt' column.")
                return
            mask = (
                (DC_norm["createdAt"].dt.date >= start_date)
                & (DC_norm["createdAt"].dt.date <= end_date)
            )
            DC_filtered = DC_norm.loc[mask].reset_index(drop=True)

        with st.spinner("Fetching GA data (API date range)…"):
            GA_norm = _get_ga(start_date.isoformat(), end_date.isoformat())

        with st.spinner("Applying scoring…"):
            scored_df = apply_scoring(DC_filtered, GA_norm)

        st.success(f"Scored {len(scored_df)} records.")
        st.session_state["scored_df"] = scored_df
        st.dataframe(scored_df.head(50), use_container_width=True)