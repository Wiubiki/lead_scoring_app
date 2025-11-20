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

def render_stepper(current_step):
    steps = ["Fetch Data", "Run Scoring", "Results"]
    icons = []

    for i, step in enumerate(steps):
        if i < current_step:
            icons.append(f"🟩 {step} ✓")
        elif i == current_step:
            icons.append(f"🟦 {step}")
        else:
            icons.append(f"⬜ {step}")

    st.markdown(
        f"""
        <div style="display:flex; gap:40px; font-size:18px; margin-bottom:20px;">
            <div>{icons[0]}</div>
            <div>{icons[1]}</div>
            <div>{icons[2]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render() -> None:
    st.title("Data Retrieval & Scoring")

    # ----- Persistent summaries -----
    st.session_state.setdefault("fetch_summary", "")
    st.session_state.setdefault("scoring_summary", "")

    # ----- Stable wizard flags -----
    st.session_state.setdefault("wizard_fetched", False)
    st.session_state.setdefault("wizard_scored", False)

    # ----- Stepper -----
    if not st.session_state["wizard_fetched"]:
        render_stepper(0)
    elif not st.session_state["wizard_scored"]:
        render_stepper(1)
    else:
        render_stepper(2)

    # ----- Display persistent summaries (always visible) -----
    if st.session_state["fetch_summary"]:
        st.markdown(
            f"<div style='margin: -5px 0 15px 5px; color:#0a7f1c;'>"
            f"{st.session_state['fetch_summary']}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if st.session_state["scoring_summary"]:
        st.markdown(
            f"<div style='margin: -10px 0 20px 5px; color:#0a7f1c;'>"
            f"{st.session_state['scoring_summary']}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ======================================================================
    # --- Step 1: Retrieve Data -------------------------------------------------
    # ======================================================================
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

        # If the range changes → reset scoring
        if st.session_state.get("_date_range") != (start_dt, end_dt):
            _set_date_range(start_dt, end_dt)
            _clear_scored()

        colA, colB = st.columns(2)
        fetch_clicked = colA.button("Fetch Data", type="primary")
        show_samples = colB.checkbox("Show samples after fetch", value=True)

        if fetch_clicked:
            try:
                # Reset scoring summary since new fetch requires new scoring
                st.session_state["scoring_summary"] = ""
                st.session_state["wizard_scored"] = False

                progress = st.progress(0, text="Starting…")

                # --- Fetch DreamClass raw ---
                with st.spinner("Fetching DreamClass…"):
                    DC_raw = fetch_dc()
                    st.session_state["DC_raw"] = DC_raw
                progress.progress(40, text="DreamClass ✓")

                # --- Fetch GA raw ---
                with st.spinner("Fetching GA…"):
                    start_s = start_dt.strftime("%Y-%m-%d")
                    end_s = end_dt.strftime("%Y-%m-%d")
                    GA_raw = fetch_ga(start_s, end_s)
                    st.session_state["GA_raw"] = GA_raw
                progress.progress(70, text="GA ✓")

                # --- Filter DreamClass by date only ---
                from data.dreamclass_handler import filter_by_date
                DC_range = filter_by_date(DC_raw, start_dt, end_dt)
                GA_range = GA_raw  # Already scoped by API

                st.session_state["DC_range"] = DC_range
                st.session_state["GA_range"] = GA_range

                dc_count = len(DC_range)
                ga_count = len(GA_range)

                # Persist summary outside the expander
                st.session_state["fetch_summary"] = (
                    f"DreamClass ✓ — {dc_count} records • "
                    f"GA ✓ — {ga_count} records • "
                    "Range applied"
                )

                progress.progress(100, text="Completed ✓")

                st.session_state["wizard_fetched"] = True
                st.success("Fetched & prepared data. • "f"DreamClass ✓ — {dc_count} records • "
                    f"GA ✓ — {ga_count} records • ")

                # --- After successful fetch ---
                if show_samples:
                    st.subheader("Sample Previews")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**DreamClass (filtered sample)**")
                        if "DC_range" in st.session_state:
                            st.dataframe(
                                st.session_state["DC_range"].head(20),
                                use_container_width=True,
                                height=300
                            )
                        else:
                            st.caption("No DreamClass data loaded.")

                    with col2:
                        st.markdown("**GA (sample)**")
                        if "GA_range" in st.session_state:
                            st.dataframe(
                                st.session_state["GA_range"].head(20),
                                use_container_width=True,
                                height=300
                            )
                        else:
                            st.caption("No GA data loaded.")



            except Exception as e:
                st.session_state["wizard_fetched"] = False
                st.error(str(e))

    # Show fetch summary under the panel
    if st.session_state["fetch_summary"] and st.session_state["wizard_fetched"]:
        st.markdown(
            f"<div style='margin: -5px 0 20px 5px; color:#0a7f1c; font-weight:500;'>"
            f"{st.session_state['fetch_summary']}"
            f"</div>",
            unsafe_allow_html=True,
        )


    # ======================================================================
    # --- Step 2: Run Scoring ---------------------------------------------------
    # ======================================================================
    with st.expander(
        "2) Run Scoring Algorithm",
        expanded=st.session_state["wizard_fetched"] and not st.session_state["wizard_scored"],
    ):
        disabled = not st.session_state["wizard_fetched"]
        score_clicked = st.button("Run Scoring", type="primary", disabled=disabled)

        if score_clicked:
            if "DC_range" not in st.session_state or "GA_range" not in st.session_state:
                st.error("Fetch data first.")
            else:
                with st.spinner("Applying scoring…"):
                    scored_df = apply_scoring(
                        st.session_state["DC_range"],
                        st.session_state["GA_range"]
                    )

                st.session_state["scored_df"] = scored_df
                st.session_state["wizard_scored"] = True

                summary = f"Scored {len(scored_df)} records."
                st.session_state["scoring_summary"] = summary

                st.success(summary)
                st.rerun()


   # --- Step 3: Results (preview) --------------------------------------------


    # Show scored preview + CTA only if scoring done
    scored_df = st.session_state.get("scored_df")
    if isinstance(scored_df, pd.DataFrame) and not scored_df.empty:
        st.subheader("Scored Results (sample)")
        st.dataframe(scored_df.head(30), use_container_width=True)

        go = st.button("Open full Results page →")
        if go:
            st.session_state["nav"] = "Results"
            st.rerun()
    else:
        st.caption("No scored data yet. Complete Steps 1 and 2.")
