# ui/results_page.py
# Purpose: Results page (formerly "View Results")
# - Show scored table (with a simple Class filter)
# - Pie chart of Class distribution
# - CSV / Parquet downloads
# - Save Snapshot (delegates to existing implementation)
#
# Notes:
# - Expects a scored dataframe (with 'Class' and 'Class%') either passed as `df`
#   or present in st.session_state["scored_df"].
# - No data renaming/cleaning here.

from __future__ import annotations

import io
import streamlit as st
import pandas as pd

def _save_snapshot(df: pd.DataFrame) -> None:
    """
    Delegate to your existing snapshot saver.
    Adjust the import to match your repo if needed.
    """
    tried = []
    for modpath, fn in [
        ("features.snapshots", "save_snapshot"),
        ("snapshots", "save_snapshot"),
        ("ui.snapshots", "save_snapshot"),
    ]:
        try:
            mod = __import__(modpath, fromlist=[fn])
            getattr(mod, fn)(df)
            return
        except Exception as e:
            tried.append(f"{modpath}.{fn}: {e}")
    raise RuntimeError("Save Snapshot implementation not found.\n" + "\n".join(tried))

def render(df: pd.DataFrame | None = None) -> None:
    st.title("Results")

    # Source the dataframe
    if df is None:
        df = st.session_state.get("scored_df")

    if df is None or df.empty:
        st.info("No scored results available. Run scoring first.")
        return

    # Basic sanity: ensure expected columns exist (names-only check)
    missing = [c for c in ["Class", "Class%"] if c not in df.columns]
    if missing:
        st.warning(f"Scored data missing expected column(s): {missing}. "
                   "Page will render without charts relying on them.")

    # Filters (kept minimal to mirror old behavior)
    with st.expander("Filters", expanded=False):
        class_opts = sorted([c for c in df.get("Class", pd.Series(dtype=str)).dropna().unique().tolist()])
        chosen = st.multiselect("Class", class_opts, default=None)

    tmp = df.copy()
    if chosen:
        tmp = tmp[tmp["Class"].isin(chosen)]

    # Table
    st.dataframe(tmp, use_container_width=True)

    # Pie chart: Class distribution (optional)
    try:
        shares = tmp["Class"].value_counts(normalize=True).sort_index()
        if not shares.empty:
            fig = shares.plot.pie(autopct="%1.1f%%", ylabel="").figure
            st.pyplot(fig, clear_figure=True)
    except Exception:
        st.caption("Pie chart unavailable (requires a 'Class' column and plotting backend).")

    # Downloads
    csv_bytes = tmp.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv_bytes, file_name="scored_results.csv", mime="text/csv")

    try:
        buf = io.BytesIO()
        tmp.to_parquet(buf, index=False)  # requires pyarrow or fastparquet
        st.download_button("Download Parquet", data=buf.getvalue(),
                           file_name="scored_results.parquet", mime="application/octet-stream")
    except Exception:
        st.caption("Parquet export requires `pyarrow` or `fastparquet`.")

    # Save Snapshot (unchanged behavior)
    if st.button("Save Snapshot"):
        try:
            _save_snapshot(tmp)
            st.success("Snapshot saved.")
        except Exception as e:
            st.error(str(e))