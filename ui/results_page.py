import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import io
from utils.supabase_client import supabase

def render():
    st.markdown("<h1 style='color: #006550; text-align: center;'>Results</h1>", unsafe_allow_html=True)


    # --------------------------
    # Helper: save scoring run to Supabase
    # --------------------------
    def save_scoring_run_to_supabase(df: pd.DataFrame) -> None:
        """
        Uploads the scored DataFrame as a Parquet file to the
        'scoring-runs-nightly' bucket and upserts a row into the
        public.scoring_runs table.
        """
        # 1) Get scoring period from session
        period_start = st.session_state.get("scoring_period_start")
        period_end = st.session_state.get("scoring_period_end")

        if period_start is None or period_end is None:
            st.error("Scoring period is not available in session. Please re-run scoring.")
            return

        # Normalise to date objects
        if isinstance(period_start, dt.datetime):
            period_start = period_start.date()
        if isinstance(period_end, dt.datetime):
            period_end = period_end.date()

        if not isinstance(period_start, dt.date) or not isinstance(period_end, dt.date):
            st.error("Scoring period has invalid format. Please re-run scoring.")
            return

        start_str = period_start.isoformat()
        end_str = period_end.isoformat()
        year_str = str(period_start.year)

        # 2) Build file_key
        file_key = f"full/{year_str}/{start_str}__{end_str}.parquet"

        # 3) Clean up DataFrame for Parquet

        # Work on a copy so we don't mutate session state by accident
        df_to_save = df.copy()

        # Ensure sign_up is numeric with proper missing values
        if "sign_up" in df_to_save.columns:
            # Convert "missing" (and any non-numeric junk) to NaN, keep 0/1 as numbers
            df_to_save["sign_up"] = pd.to_numeric(df_to_save["sign_up"], errors="coerce")

        # Serialise DataFrame to Parquet in memory
        buffer = io.BytesIO()
        df_to_save.to_parquet(buffer, index=False)
        buffer.seek(0)
        data_bytes = buffer.getvalue()

        # 4) Upload to Supabase Storage (with upsert)
        bucket_name = "scoring-runs-nightly"

        try:
            storage_resp = supabase.storage.from_(bucket_name).upload(
                path=file_key,
                file=data_bytes,
                file_options={"upsert": "true"},
            )
        except Exception as e:
            st.error(f"Failed to upload Parquet to Supabase Storage: {e}")
            return

        # 5) Upsert metadata row into scoring_runs
        lead_count = int(len(df))

        payload = {
            "env": "nightly",
            "data_type": "full",
            "period_start": start_str,
            "period_end": end_str,
            "file_key": file_key,
            "lead_count": lead_count,
            "created_by": "admin_results_page",
            "notes": None,
        }

        try:
            supabase.table("scoring_runs").upsert(payload).execute()
        except Exception as e:
            st.error(f"Failed to upsert scoring_runs metadata: {e}")
            return

        st.success(
            f"Saved scoring run to Supabase: {start_str} → {end_str} "
            f"({lead_count} leads)."
        )


    # --------------------------
    # Retrieve the scored results
    # --------------------------
    scored_df = st.session_state.get("scored_df")

    if scored_df is None or scored_df.empty:
        st.warning("No scored data available. Please run scoring first.")
        return

    # --------------------------
    # Filters Panel (Basic)
    # --------------------------
    with st.expander("Filters", expanded=False):
        st.dataframe(scored_df, use_container_width=True)

    st.markdown("---")

    # --------------------------
    # Admin save action
    # --------------------------
    if st.button("💾 Save scoring run to Supabase", type="primary"):
        save_scoring_run_to_supabase(scored_df)


    # ============================================
    # Lead Class Distribution Section
    # ============================================

    dist = (
        scored_df["lead_class"]
        .value_counts()
        .sort_index()
        .rename_axis("Class")
        .reset_index(name="count")
    )

    total_leads = dist["count"].sum()
    dist["Class%"] = (dist["count"] / total_leads * 100).round(2)

    # Unified centered header
    st.markdown(
        f"""
        <h3 style="text-align:center; margin-bottom:0px;">
            Lead Class Distribution (Total Leads: {total_leads})
        </h3>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Side-by-side layout (table 25%, pie 75%)
    colA, colSpacer, colB = st.columns([1, 0.35, 2.65])

    # TABLE
    with colA:
        st.markdown(
            f"""
            <h4 style="text-align:center; margin-bottom:0px;">
                Distribution Table
            </h4>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(
            dist,
            use_container_width=True,
            hide_index=True,
            height=178
        )

    with colSpacer:
        st.markdown("&nbsp;", unsafe_allow_html=True)  # ensures column renders consistently

            
    # PIE CHART
    with colB:
        st.markdown(
            f"""
            <h4 style="text-align:center; margin-bottom:0px;">
                Distribution Chart
            </h4>
            """,
            unsafe_allow_html=True,
        )

        fig, ax = plt.subplots(figsize=(4, 4), dpi=100)  # smaller, prevents overflow

        # Prepare labels
        class_labels = [f"Class {c}" for c in dist["Class"]]
        pct_labels = [f"{p}%" for p in dist["Class%"]]
        count_labels = [f"({c})" for c in dist["count"]]

        wedges, _ = ax.pie(
            dist["count"],
            startangle=90,
            counterclock=False,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )

        # External + internal labels
        for w, class_label, pct, count in zip(wedges, class_labels, pct_labels, count_labels):
            ang = (w.theta2 - w.theta1) / 2 + w.theta1

            # External label (Class X)
            label_radius = 1.35
            x = label_radius * np.cos(np.deg2rad(ang))
            y = label_radius * np.sin(np.deg2rad(ang))
            ax.text(x, y, class_label, ha="center", va="center", fontsize=9)

            # Internal label (% + count)
            inner_radius = 0.7
            x2 = inner_radius * np.cos(np.deg2rad(ang))
            y2 = inner_radius * np.sin(np.deg2rad(ang))
            ax.text(x2, y2, f"{pct}\n{count}", ha="center", va="center", fontsize=8)

        ax.axis("equal")

        # Center the chart within its column (Streamlit-proof)
        st.markdown(
            """
            <style>
            .pie-wrapper {
                max-width: 450px; /* match your figsize */
                margin-left: auto;
                margin-right: auto;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div class='pie-wrapper'>", unsafe_allow_html=True)
        st.pyplot(fig, use_container_width=False)
        st.markdown("</div>", unsafe_allow_html=True)


    st.markdown("---")

    # ============================================
    # Export Section
    # ============================================

    st.markdown("## Export")

    col1, col2, col3 = st.columns([1, 1, 1])

    # CSV Export
    csv_data = scored_df.to_csv(index=False).encode("utf-8")
    with col1:
        st.download_button(
            "Download CSV",
            csv_data,
            file_name="scored_results.csv",
            mime="text/csv",
            type="primary",
        )
        st.caption("For Excel, Sheets, or manual inspection")

    # Parquet Export (FIXED: replace 'missing' with NaN)
    clean_df = scored_df.replace("missing", pd.NA)
    parquet_bytes = clean_df.to_parquet(index=False)

    with col2:
        st.download_button(
            "Download Parquet",
            parquet_bytes,
            file_name="scored_results.parquet",
            mime="application/octet-stream",
            type="secondary",
        )
        st.caption("For analytics pipelines and large datasets")

    # Supabase placeholder
    with col3:
        st.button(
            "Save to Supabase (coming soon)",
            type="secondary",
            disabled=True,
        )
        st.caption("Upload to secure storage (not yet implemented)")
