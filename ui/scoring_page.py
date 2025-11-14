# ui/scoring_page.py
# PR-1: Wizard UX (Retrieve → Score → Results)
# - Secrets-driven (no endpoint inputs)
# - Step 1: pick dates, Fetch → preview DC & GA
# - Step 2: Run Scoring (DC filtered by createdAt, GA already date-scoped)
# - Step 3: Show scored preview + CTA to Results

import datetime as dt
import streamlit as st
import pandas as pd

from data.dreamclass_handler import fetch_and_clean as fetch_dc
from data.ga_handler import fetch_and_clean as fetch_ga
from scoring.lead_scores_calculator import apply as apply_scoring

# ---------- cached fetchers ----------

@st.cache_data(show_spinner=False)
def _get_dc_cached() -> pd.DataFrame:
    base_url = st.secrets.get("dreamclass", {}).get("BASE_URL", "")
    return fetch_dc(base_url=base_url)  # statuses hardcoded in handler

@st.cache_data(show_spinner=False)
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

                with st.spinner("Fetching DreamClass…"):
                    DC_norm = _get_dc_cached()
                    st.session_state["DC_norm"] = DC_norm
                progress.progress(50, text="DreamClass ✓")

                with st.spinner("Fetching GA…"):
                    start_s = start_dt.strftime("%Y-%m-%d")
                    end_s = end_dt.strftime("%Y-%m-%d")
                    GA_norm = _get_ga_cached(start_s, end_s)
                    st.session_state["GA_norm"] = GA_norm
                progress.progress(100, text="DreamClass ✓  •  GA ✓")

                st.success("Fetched data from DreamClass & GA.")
                st.session_state["wizard_fetched"] = True

                if show_samples:
                    st.subheader("DreamClass (sample)")
                    st.dataframe(DC_norm.head(20), use_container_width=True)
                    st.subheader("GA (sample)")
                    st.dataframe(GA_norm.head(20), use_container_width=True)

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
            DC_norm = st.session_state.get("DC_norm")
            GA_norm = st.session_state.get("GA_norm")

            if DC_norm is None or GA_norm is None:
                st.error("Fetch data first (Step 1).")
            elif "createdAt" not in DC_norm.columns:
                st.error("DC_norm missing 'createdAt'.")
            else:
                start_dt, end_dt = st.session_state.get("_date_range", (None, None))
                if not start_dt or not end_dt:
                    st.error("Please select a valid date range in Step 1.")
                else:
                    with st.spinner("Filtering DreamClass by createdAt and applying scoring…"):
                        mask = (
                            (DC_norm["createdAt"].dt.date >= start_dt)
                            & (DC_norm["createdAt"].dt.date <= end_dt)
                        )
                        DC_filtered = DC_norm.loc[mask].reset_index(drop=True)
                        scored_df = apply_scoring(DC_filtered, GA_norm)

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
                try:
                    import streamlit as _st
                    _st.experimental_rerun()
                except Exception:
                    st.info("Use the sidebar to open **Results**.")
        else:
            st.caption("No scored data yet. Complete Steps 1 and 2.")
