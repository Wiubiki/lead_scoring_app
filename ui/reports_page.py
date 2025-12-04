import io
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from utils.supabase_client import supabase

from utils.advanced_analytics import (
    load_lead_quality_timeseries,
    prepare_lqi_xmr_series,
    compute_xmr,
    xmr_interpretation,
    mr_interpretation,
)

from ui.widgets.xmr_charts import render_xmr_chart

# -------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------

BUCKET_NAME = "scoring-runs-nightly"  # Supabase Storage bucket


# -------------------------------------------------------------------
# DATA ACCESS
# -------------------------------------------------------------------

def load_scoring_runs() -> List[dict]:
    """
    Load all scoring runs from Supabase.

    We assume:
      - Table: scoring_runs
      - Columns: id, env, period_start, period_end, file_key,
                 lead_count, data_type
    """
    resp = (
        supabase.table("scoring_runs")
        .select(
            "id, env, period_start, period_end, file_key, "
            "lead_count, data_type"
        )
        .order("period_end")
        .execute()
    )

    rows = resp.data or []

    runs: List[dict] = []
    for row in rows:
        runs.append(
            {
                "id": row["id"],
                "env": row.get("env"),
                "start": row.get("period_start"),
                "end": row.get("period_end"),
                "file_key": row.get("file_key"),
                "lead_count": row.get("lead_count"),
                "data_type": row.get("data_type"),
                "label": f"{row.get('period_start')} → {row.get('period_end')}",
            }
        )

    return runs


def _load_full_run_parquet(file_key: str, run_id: str) -> pd.DataFrame:
    """
    Load a FULL run parquet (row-level data).

    We normalise any 'class' column to 'lead_class'
    and tag rows with __run_id so we can trace later.
    """
    file_bytes = supabase.storage.from_(BUCKET_NAME).download(file_key)
    df = pd.read_parquet(io.BytesIO(file_bytes))

    # Normalise lead class column if needed
    if "lead_class" not in df.columns:
        if "class" in df.columns:
            df = df.rename(columns={"class": "lead_class"})
        elif "score_class" in df.columns:
            df = df.rename(columns={"score_class": "lead_class"})

    df["__run_id"] = run_id
    return df


def _load_summary_run_parquet(file_key: str) -> Dict[str, int]:
    """
    Load a SUMMARY run parquet (aggregated data only).

    Confirmed schema:
      period_start    VARCHAR
      period_end      VARCHAR
      class_1_count   BIGINT
      class_2_count   BIGINT
      class_3_count   BIGINT
      class_4_count   BIGINT
      total_leads     BIGINT
      data_type       VARCHAR
    """
    file_bytes = supabase.storage.from_(BUCKET_NAME).download(file_key)
    df = pd.read_parquet(io.BytesIO(file_bytes))

    if df.empty:
        return {"total": 0, 1: 0, 2: 0, 3: 0, 4: 0}

    row = df.iloc[0]

    def safe_get(col: str) -> int:
        return int(row[col]) if col in df.columns and pd.notna(row[col]) else 0

    return {
        "total": safe_get("total_leads"),
        1: safe_get("class_1_count"),
        2: safe_get("class_2_count"),
        3: safe_get("class_3_count"),
        4: safe_get("class_4_count"),
    }


def load_data_for_runs(
    selected_runs: List[dict],
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    For a list of runs:
      - Load FULL runs as a concatenated dataframe (row-level)
      - Aggregate SUMMARY runs into a dict of per-class + total counts.

    Returns:
      (df_full, summary_totals)

      df_full: may be empty if no full runs were selected.
      summary_totals: dict with keys 'total', 1,2,3,4.
    """
    full_frames: List[pd.DataFrame] = []
    summary_totals: Dict[str, int] = {"total": 0, 1: 0, 2: 0, 3: 0, 4: 0}

    for run in selected_runs:
        file_key = run.get("file_key")
        data_type = (run.get("data_type") or "").lower()

        if not file_key:
            continue

        try:
            if data_type == "full":
                df_run = _load_full_run_parquet(file_key, run["id"])
                full_frames.append(df_run)

            elif data_type == "summary":
                counts = _load_summary_run_parquet(file_key)
                summary_totals["total"] += counts.get("total", 0)
                for cls in (1, 2, 3, 4):
                    summary_totals[cls] += counts.get(cls, 0)

            else:
                # Unknown type: ignore rather than crash
                st.warning(
                    f"Run {run.get('label') or run['id']} has unknown "
                    f"data_type='{data_type}', skipping."
                )

        except Exception as e:
            st.warning(
                f"Could not load data for run "
                f"{run.get('label') or run['id']}: {e}"
            )

    df_full = (
        pd.concat(full_frames, ignore_index=True) if full_frames else pd.DataFrame()
    )
    return df_full, summary_totals


# -------------------------------------------------------------------
# Advanced Analytics: XmR tab content
# -------------------------------------------------------------------

def render_xmr_tab():
    st.subheader("Lead Quality Index - XmR charts")
    # Short contextual explanation for the LQI metric
    st.caption(
        "The Lead Quality Index (LQI) is a weighted 0–10 score summarizing overall lead quality. "
        "It reflects the mix of lead classes in each period. "
        "[Learn more in the FAQ below 👇](#lqi-faq)"
    )   


    df_ts = load_lead_quality_timeseries()
    if df_ts.empty or len(df_ts) < 2:
        st.info("Not enough periods in lead_quality_timeseries to compute XmR.")
        return

    # Prepare LQI series for XmR
    lqi_series = prepare_lqi_xmr_series(df_ts)
    if lqi_series.empty or len(lqi_series) < 2:
        st.info("Not enough valid LQI points to compute XmR.")
        return

    # For now we can use the index (period_start) as "dates" for the chart
    dates = pd.Series(lqi_series.index)

    stats_q = compute_xmr(lqi_series)

    render_xmr_chart("Lead Quality Index (LQI) over time", dates, lqi_series, stats_q)

    # ------------------------------------------------------
    # INTERPRETATION (2 columns: X vs mR)
    # ------------------------------------------------------
    st.markdown("### Interpretation")

    col_x, col_mr = st.columns(2)

    with col_x:
        st.markdown("#### What the X chart tells us")
        st.markdown(xmr_interpretation(dates, lqi_series, stats_q))

    with col_mr:
        st.markdown("#### What the mR chart tells us")
        st.markdown(mr_interpretation(dates, lqi_series, stats_q))



# -------------------------------------------------------------------
# MAIN PAGE
# -------------------------------------------------------------------

def render_reports_page():
    jump = st.session_state.get("reports_jump", None)

    st.markdown(
        "<h1 style='color: #006550; text-align: center;'>Reports</h1>",
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------------
    # 1. Load runs
    # ---------------------------------------------------------------
    runs = load_scoring_runs()
    if not runs:
        st.info("No scoring runs found in Supabase yet.")
        return

    # Already ordered by period_end from Supabase, but be safe
    runs_sorted = sorted(
        runs,
        key=lambda r: str(r.get("end") or ""),
        reverse=True,
    )

    # ---------------------------------------------------------------
    # 2. Initialise session defaults
    # ---------------------------------------------------------------
    if "reports_selected_run_ids" not in st.session_state:
        st.session_state["reports_selected_run_ids"] = [runs_sorted[0]["id"]]

    if "reports_lead_classes" not in st.session_state:
        # None = "all classes"
        st.session_state["reports_lead_classes"] = None

    # ---------------------------------------------------------------
    # 3. Run selection UI
    # ---------------------------------------------------------------
    st.markdown(
        "<h3 style='color: #006550; text-align: center;'>Scoring Runs (2-week batches)</h3>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.5])

    with col1:
        if st.button("Latest", key="reports-latest"):
            st.session_state["reports_selected_run_ids"] = [runs_sorted[0]["id"]]
            st.session_state["reports_lead_classes"] = None
            st.rerun()

    with col2:
        if st.button("Last 3", key="reports-last-3"):
            st.session_state["reports_selected_run_ids"] = [
                r["id"] for r in runs_sorted[:3]
            ]
            st.session_state["reports_lead_classes"] = None
            st.rerun()

    with col3:
        if st.button("Last 5", key="reports-last-5"):
            st.session_state["reports_selected_run_ids"] = [
                r["id"] for r in runs_sorted[:5]
            ]
            st.session_state["reports_lead_classes"] = None
            st.rerun()

    with col4:
        if st.button("Reset to default", key="reports-reset"):
            st.session_state["reports_selected_run_ids"] = [runs_sorted[0]["id"]]
            st.session_state["reports_lead_classes"] = None
            st.rerun()

    label_to_id = {r["label"]: r["id"] for r in runs_sorted}
    id_to_run = {r["id"]: r for r in runs_sorted}

    current_ids = st.session_state.get("reports_selected_run_ids", [])
    default_labels = [
        id_to_run[rid]["label"] for rid in current_ids if rid in id_to_run
    ]

    selected_labels = st.multiselect(
        "Select scoring batch(es)",
        options=list(label_to_id.keys()),
        default=default_labels,
        key="reports-run-multiselect",
    )

    selected_run_ids = [label_to_id[lbl] for lbl in selected_labels]
    st.session_state["reports_selected_run_ids"] = selected_run_ids

    if not selected_run_ids:
        st.info("No scoring batch selected.")
        return

    selected_runs = [id_to_run[rid] for rid in selected_run_ids if rid in id_to_run]

    st.markdown("---")

    # ---------------------------------------------------------------
    # 4. Load data for selected runs
    # ---------------------------------------------------------------
    df_full, summary_totals = load_data_for_runs(selected_runs)

    has_full_rows = not df_full.empty
    has_summary_data = summary_totals["total"] > 0

    if not has_full_rows and not has_summary_data:
        st.info("No data available for the current run selection.")
        return

    # ---------------------------------------------------------------
    # 5. Lead Class filter (only meaningful for classes 1–4)
    # ---------------------------------------------------------------
    st.markdown(
        "<h3 style='color: #006550; text-align: center;'>Filter by Lead Class</h3>",
        unsafe_allow_html=True,
    )

    # Determine available classes:
    full_classes = set()
    if has_full_rows and "lead_class" in df_full.columns:
        full_classes = set(
            int(c) for c in df_full["lead_class"].dropna().unique().tolist()
        )

    summary_classes = {cls for cls in (1, 2, 3, 4) if summary_totals.get(cls, 0) > 0}

    available_classes = sorted(full_classes.union(summary_classes) or {1, 2, 3, 4})

    stored = st.session_state.get("reports_lead_classes")
    if stored is None:
        default_classes = available_classes
    else:
        default_classes = [
            c for c in stored if c in available_classes
        ] or available_classes

    selected_classes = st.multiselect(
        "Select Lead Class",
        options=available_classes,
        default=default_classes,
        key="reports-lead-class-multiselect",
    )

    if selected_classes:
        st.session_state["reports_lead_classes"] = selected_classes
    else:
        selected_classes = available_classes
        st.session_state["reports_lead_classes"] = selected_classes

    # Filter full rows by class if we have them
    if has_full_rows and "lead_class" in df_full.columns:
        df_filtered = df_full[df_full["lead_class"].isin(selected_classes)]
    else:
        df_filtered = pd.DataFrame()  # no row-level data for current filter

    st.markdown("---")

    # ---------------------------------------------------------------
    # 6. Summary row (Total + per-class)
    # ---------------------------------------------------------------
    full_class_counts = (
        df_filtered["lead_class"].value_counts().to_dict()
        if not df_filtered.empty and "lead_class" in df_filtered.columns
        else {}
    )

    total_all = 0
    per_class_display: List[str] = []

    for cls in sorted(selected_classes):
        full_c = int(full_class_counts.get(cls, 0))
        summary_c = int(summary_totals.get(cls, 0))
        cls_total = full_c + summary_c
        total_all += cls_total
        per_class_display.append((cls, cls_total))

    summary_text_segments = [f"<strong>Total scored leads:</strong> {total_all}"]

    for cls, cls_total in per_class_display:
        pct = (cls_total / total_all * 100) if total_all > 0 else 0.0
        summary_text_segments.append(
            f"Class {cls}: {cls_total} ({pct:.1f}%)"
        )

    summary_html = " &nbsp;|&nbsp; ".join(summary_text_segments)

    st.markdown(
        f"""
        <div id="reports-summary-row">
            {summary_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ---------------------------------------------------------------
    # 7. Lead table + CSV download (FULL runs only)
    # ---------------------------------------------------------------
    st.markdown(
        "<h3 style='color: #006550; text-align: center;'>Scored Leads (row-level data from FULL runs)</h3>",
        unsafe_allow_html=True,
    )

    if df_filtered.empty:
        if has_full_rows:
            st.info(
                "No row-level leads match the current filters "
                "(but summary data exists for these runs)."
            )
        else:
            st.info(
                "Only SUMMARY runs are selected for this period; "
                "no row-level lead data is available."
            )
    else:
        st.dataframe(df_filtered)

        csv_data = df_filtered.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="scored_leads.csv",
            mime="text/csv",
            key="reports-download-csv",
        )

    # ---------------------------------------------------------------
    # 8. Advanced Analytics (tabs) - BELOW everything else
    # ---------------------------------------------------------------
    st.markdown("---")
    st.markdown('<a name="advanced-analytics"></a>', unsafe_allow_html=True)

    st.markdown(
        "<h2 style='color: #006550; text-align: center;'>Advanced Analytics</h2>",
        unsafe_allow_html=True,
    )
    if jump == "advanced-analytics":
        st.markdown(
            """
            <script>
                const el = document.querySelector("a[name='advanced-analytics']");
                if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
            </script>
            """,
            unsafe_allow_html=True,
        )


    tab_xmr, tab_future = st.tabs(
        ["Lead Quality (XmR)", "More analytics (coming soon)"]
    )

    with tab_xmr:
        render_xmr_tab()

    with tab_future:
        st.info("Additional analytics will appear here in future versions.")

    # ------------------------------------------------------
    # FAQ SECTION
    # ------------------------------------------------------
    st.markdown('<a name="lqi-faq"></a>', unsafe_allow_html=True)
    st.markdown("### FAQ")

    # 1. what are XmR charts
    with st.expander("What are XmR charts, and why do we use them?"):
        st.write(
            """
    **XmR charts** (Individuals and Moving Range charts) are simple, powerful tools  
    used to understand whether a metric is behaving predictably over time.

    - The **X chart** tracks the metric itself (here: LQI).
    - The **mR chart** tracks how much the metric changes from one period to the next.

    Together, they allow you to distinguish **routine variation** from **meaningful changes**.
    """
            )

    # 2. How to read the X chart
    with st.expander("How do I read the Individuals (X) chart?"):
        st.write(
            """
    The X chart tells you about **changes in the level** of the process.

    Key signals include:

    1. **Points beyond the limits** → strong sign of a special-cause change.
    2. **Runs of 8+ points on one side of the mean** → sustained level shift.
    3. **Clusters near limits** → variation is increasing and stability may be weakening.
    4. **No signals** → the process is stable and predictable.
    """
            )

    # 3. How to read the mR chart
    with st.expander("How do I read the Moving Range (mR) chart?"):
        st.write(
            """
    The mR chart tells you about the **stability of variation**.

    Look for:

    1. **MR points above the MR limit** → sudden spikes in variation.
    2. **Several MR values near the MR limit** → variation trending upward.
    3. **Zero MR values** → identical consecutive values; may indicate data issues.
    4. **Stable MR** → variation is routine, and X-chart limits are trustworthy.
    """
            )

    # 4. What is the LQI
    with st.expander("What is the Lead Quality Index (LQI), and how is it calculated?"):
        st.write(
            """
    The LQI is a single score that summarizes the **quality mix** of leads  
    in a given period on a scale from **0 to 10**.

    We assign points as follows:

    - Class 1 → **10 points**
    - Class 2 → **6 points**
    - Class 3 → **3 points**
    - Class 4 → **0 points**

    The formula:

    **LQI = (10·C1 + 6·C2 + 3·C3 + 0·C4) / total_leads**

    Higher LQI indicates stronger lead quality; lower LQI indicates lower-quality mix.
    """
            )

    # 5. How many data points are needed
    with st.expander("How many data points do I need for a reliable XmR chart?"):
        st.write(
            """
    Guidelines:

    - **8+ points** → minimum for meaningful limits.
    - **12+ points** → reasonably stable and interpretable.
    - **20+ points** → limits stabilize; signals become reliable.
    - **30–50 points** → ideal for detecting subtle shifts.

    More data improves limit stability and reduces false signals.
    """
            )









# -------------------------------------------------------------------
# Standalone run
# -------------------------------------------------------------------
if __name__ == "__main__":
    render_reports_page()
