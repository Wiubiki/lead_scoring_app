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

    st.markdown(
        f"""
        <h3 style="text-align:center; margin-bottom:0px;">
            Lead Class Distribution (Total Leads: {total_leads})
        </h3>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ---------- FLEXBOX LAYOUT ----------
    st.markdown(
        """
        <div style="
            display: flex;
            justify-content: center;
            gap: 40px;
            align-items: flex-start;
            width: 100%;
            margin-top: 20px;
            margin-bottom: 20px;
        ">
            <div style="flex: 1; max-width: 260px;">
                <h4 style="text-align:center;">Distribution Table</h4>
                <!-- TABLE_PLACEHOLDER -->
            </div>

            <div style="flex: 2; display:flex; justify-content:center;">
                <!-- PIE_PLACEHOLDER -->
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- Insert table into the placeholder ---
    table_html = dist.to_html(index=False)
    st.markdown(
        table_html.replace(
            "<table",
            "<table style='width:100%; border-collapse: collapse; text-align:center; font-size:14px;'"
        ),
        unsafe_allow_html=True
    )


    # Build fixed-size chart for consistency
    fig, ax = plt.subplots(figsize=(3.5, 3.5))

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

    # Labels
    for w, class_label, pct, count in zip(wedges, class_labels, pct_labels, count_labels):
        ang = (w.theta2 - w.theta1) / 2 + w.theta1

        label_radius = 1.25
        x = label_radius * np.cos(np.deg2rad(ang))
        y = label_radius * np.sin(np.deg2rad(ang))
        ax.text(x, y, class_label, ha="center", va="center", fontsize=11)

        inner_radius = 0.7
        x2 = inner_radius * np.cos(np.deg2rad(ang))
        y2 = inner_radius * np.sin(np.deg2rad(ang))
        ax.text(x2, y2, f"{pct}\n{count}", ha="center", va="center", fontsize=10)

    ax.axis("equal")

    # Render pie chart into the right flexbox div
    chart_html = st.pyplot(fig)



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
