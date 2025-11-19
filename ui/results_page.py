# ui/results_page.py
# v3 Results page
# - Consumes scored_df from session_state (produced in Scoring step)
# - Shows full table
# - Computes Class counts/percentages on the fly from `lead_class`
# - Renders a pie chart of lead-class distribution

import streamlit as st
import pandas as pd

try:
    import altair as alt
except Exception:  # very defensive; page will still work without chart
    alt = None


def _get_scored_df() -> pd.DataFrame | None:
    df = st.session_state.get("scored_df")
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return None


def _build_class_summary(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Take the scored dataframe and aggregate by lead class.

    We expect either:
      - a 'lead_class' column (preferred), or
      - a 'Class' column (fallback – older runs)
    """
    key_col = None
    if "lead_class" in df.columns:
        key_col = "lead_class"
    elif "Class" in df.columns:
        key_col = "Class"

    if not key_col:
        return None

    counts = df[key_col].value_counts().sort_index()
    total = int(counts.sum())

    summary = pd.DataFrame(
        {
            "Class": counts.index.astype(str),
            "count": counts.values,
        }
    )
    summary["Class%"] = (summary["count"] / total * 100).round(2)
    summary["Total"] = total  # handy for labeling

    return summary


def render() -> None:
    st.title("Results")

    scored_df = _get_scored_df()
    if scored_df is None:
        st.warning("No scored data available. Go to **Scoring** and run the scoring step first.")
        return

    # --- Filters (simple, non-destructive) ------------------------------------
    with st.expander("Filters", expanded=False):
        # Filter by lead_class if present
        class_col = "lead_class" if "lead_class" in scored_df.columns else None
        if class_col:
            classes = sorted(scored_df[class_col].dropna().unique().tolist())
            selected = st.multiselect("Lead Class", options=classes, default=classes)
            if selected:
                scored_view = scored_df[scored_df[class_col].isin(selected)].copy()
            else:
                scored_view = scored_df.copy()
        else:
            st.caption("No `lead_class` column found – showing all rows.")
            scored_view = scored_df.copy()

    # --- Main scored table ----------------------------------------------------
    st.dataframe(scored_view, use_container_width=True)

    # --- Class distribution summary + chart -----------------------------------
    summary = _build_class_summary(scored_view)

    if summary is None:
        st.info("Scored data has no 'lead_class'/'Class' column, so lead-class distribution "
                "cannot be computed.")
        return

    total = int(summary["Total"].iloc[0])

    st.subheader("Lead Class Distribution")

    col_table, col_chart = st.columns([1, 2])

    with col_table:
        # show compact summary table
        display_cols = ["Class", "count", "Class%"]
        st.dataframe(summary[display_cols], use_container_width=True)

    with col_chart:
        if alt is None:
            st.caption("Altair not available – skipping pie chart.")
        else:
            chart = (
                alt.Chart(summary)
                .mark_arc()
                .encode(
                    theta="count:Q",
                    color="Class:N",
                    tooltip=["Class", "count", "Class%"],
                )
                .properties(
                    title=f"Lead Class Distribution (Total Leads: {total})"
                )
            )
            st.altair_chart(chart, use_container_width=True)

    # --- Download scored data -------------------------------------------------
    st.markdown("### Export")
    csv = scored_view.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download scored data as CSV",
        data=csv,
        file_name="scored_leads.csv",
        mime="text/csv",
    )
