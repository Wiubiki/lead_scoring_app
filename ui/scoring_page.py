# ui/scoring_page.py
# PR-1: Wizard UX (Retrieve → Score → Results)
# - Secrets-driven (no endpoint inputs)
# - Step 1: pick dates, Fetch → preview DC & GA
# - Step 2: Run Scoring (DC filtered by createdAt, GA already date-scoped)
# - Step 3: Show scored preview + CTA to Results

import datetime as dt
import streamlit as st
import pandas as pd

from data.dreamclass_handler import fetch_and_clean as fetch_dc, filter_by_date
from data.ga_handler import fetch_and_clean as fetch_ga
from scoring.lead_scores_calculator import apply_lead_scoring as apply_scoring

# ---------- cached fetchers ----------

def _get_dc_cached() -> pd.DataFrame:
    base_url = st.secrets.get("dreamclass", {}).get("BASE_URL", "")
    return fetch_dc(base_url=base_url)  # statuses hardcoded in handler

def _get_ga_cached(start_date: str, end_date: str) -> pd.DataFrame:
    return fetch_ga(start_date=start_date, end_date=end_date)

# ---------- tiny helpers ----------

def _clear_scored():
    st.session_state.pop("scored_df", None)
    st.session_state["wizard_scored"] = False

def _set_date_range(start: dt.date, end: dt.date):
    st.session_state["_date_range"] = (start, end)

def render() -> None:
    st.title("Scoring")

    # Stable step flags (don’t auto-derive each rerun)
    st.session_state.setdefault("wizard_fetched", False)
    st.session_state.setdefault("wizard_scored", False)

    # --- Step state (based on session) ---
    # fetched = ("DC_norm" in st.session_state) and ("GA_norm" in st.session_state)
    # scored = (
    #    ("scored_df" in st.session_state)
    #    and isinstance(st.session_state["scored_df"], pd.DataFrame)
    #    and not st.session_state["scored_df"].empty
    #)
    #st.session_state.setdefault("wizard_fetched", fetched)
    #st.session_state.setdefault("wizard_scored", scored)

    # --- Step 1: Retrieve Data -------------------------------------------------
    with st.expander("1) Retrieve Data", expanded=not st.session_state["wizard_fetched"]):
        default_end = dt.date.today()
        default_start = default_end - dt.timedelta(days=30)

        date_range = st.date_input(
            "Date range",
            value=st.session_state.get("_date_range", (default_start, default_end)),
            help="Inclusive start & end for GA fetch.",
            key="scoring_date_range",
        )

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_dt, end_dt = date_range
        else:
            start_dt, end_dt = default_start, default_end

        # Clear scored results if the range changed
        if st.session_state.get("_date_range") != (start_dt, end_dt):
            _set_date_range(start_dt, end_dt)
            _clear_scored()

        colA, colB = st.columns(2)
        fetch_clicked = colA.button("Fetch Data", type="primary")
        show_samples = colB.checkbox("Show samples after fetch", value=True)

        if fetch_clicked:
            try:
                progress = st.progress(0, text="Starting…")

                # --- Fetch DreamClass (raw) ---
                with st.spinner("Fetching DreamClass…"):
                    DC_raw = fetch_dc()   # handler returns DC_raw
                    st.session_state["DC_raw"] = DC_raw
                progress.progress(50, text="DreamClass ✓")

                # --- Fetch GA (raw; already date-scoped) ---
                with st.spinner("Fetching GA…"):
                    start_s = start_dt.strftime("%Y-%m-%d")
                    end_s = end_dt.strftime("%Y-%m-%d")
                    GA_raw = fetch_ga(start_s, end_s)
                    st.session_state["GA_raw"] = GA_raw
                progress.progress(80, text="GA ✓")

                # --- Apply date-range filtering only to DC ---
                from data.dreamclass_handler import filter_by_date
                DC_range = filter_by_date(DC_raw, start_dt, end_dt)
                GA_range = GA_raw  # GA is already date-filtered by API

                st.session_state["DC_range"] = DC_range
                st.session_state["GA_range"] = GA_range

                progress.progress(100, text="DreamClass ✓ • GA ✓ • Range applied")

                st.success("Fetched & prepared data.")

                st.session_state["wizard_fetched"] = True

                if show_samples:
                    st.subheader("DreamClass (sample, date-range)")
                    st.dataframe(DC_range.head(20), use_container_width=True)

                    st.subheader("GA (sample)")
                    st.dataframe(GA_range.head(20), use_container_width=True)

            except Exception as e:
                st.session_state["wizard_fetched"] = False
                st.error(str(e))



    # --- Step 2: Run Scoring ---------------------------------------------------
    with st.expander(
        "2) Run Scoring Algorithm",
        expanded=st.session_state["wizard_fetched"] and not st.session_state["wizard_scored"],
    ):
        disabled = not st.session_state["wizard_fetched"]
        score_clicked = st.button("Run Scoring", type="primary", disabled=disabled)


        if score_clicked:
            DC_range = st.session_state.get("DC_range")
            GA_range = st.session_state.get("GA_range")

            if DC_range is None or GA_range is None:
                st.error("Fetch data first in Step 1 (no DC_range / GA_range in session).")
            else:
                with st.spinner("Running scoring…"):
                    scored_df = apply_scoring(DC_range, GA_range)

                st.session_state["scored_df"] = scored_df
                st.session_state["wizard_scored"] = True
                st.success(f"Scored {len(scored_df)} records.")



    # --- Step 3: Results (preview) --------------------------------------------
    with st.expander("3) Results (preview)", expanded=st.session_state["wizard_scored"]):
        df = st.session_state.get("scored_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df.head(30), use_container_width=True)

            go = st.button("Open full Results page →", type="secondary")
            if go:
                st.session_state["nav"] = "Results"
                st.rerun()

        else:
            st.caption("No scored data yet. Complete Steps 1 and 2.")
