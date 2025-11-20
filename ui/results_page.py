import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

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
    colA, colB = st.columns([1, 3])

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

        fig, ax = plt.subplots(figsize=(4, 4))  # smaller, prevents overflow

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
