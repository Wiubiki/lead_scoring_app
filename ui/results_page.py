import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

def render():
    st.title("Results")

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

    # ============================================
    #  Lead Class Distribution Section
    # ============================================

    # Compute distribution
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

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------
    # Distribution Table + Pie Chart (side-by-side)
    # -----------------------------------------

    colA, colB = st.columns([1, 1])

    # ---- Table (no index column) ----
    with colA:
        st.markdown("### Distribution Table")
        st.dataframe(dist, use_container_width=True, hide_index=True)

    # ---- Pie Chart with labels ----
    with colB:
        st.markdown("### Distribution Pie Chart")

        fig, ax = plt.subplots(figsize=(5, 5))

        labels = [
            f"Class {row.Class}\n{row.count} ({row['Class%']}%)"
            for _, row in dist.iterrows()
        ]

        ax.pie(
            dist["count"],
            labels=labels,
            autopct=None,            # handled manually
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        ax.axis("equal")  # Perfect circle

        st.pyplot(fig)

    st.markdown("---")

    # ============================================
    # Export Section
    # ============================================

    st.markdown("## Export")

    col1, col2, col3 = st.columns([1, 1, 1])

    # ---- CSV Export ----
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

    # ---- Parquet Export ----
    parquet_bytes = scored_df.to_parquet(index=False)
    with col2:
        st.download_button(
            "Download Parquet",
            parquet_bytes,
            file_name="scored_results.parquet",
            mime="application/octet-stream",
            type="secondary",
        )
        st.caption("For analytics pipelines and large datasets")

    # ---- Supabase Placeholder ----
    with col3:
        st.button(
            "Save to Supabase (coming soon)",
            type="secondary",
            disabled=True,
        )
        st.caption("Upload to secure storage (not yet implemented)")
