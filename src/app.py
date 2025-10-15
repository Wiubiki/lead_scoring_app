"""
Lead Scoring App (nightly) — refactored from the user's current app.py
- Source (for reference): see original app.py provided in chat.
- Purpose of this refactor: clearer structure, safer date handling, fewer duplicates.

Key behavior preserved:
- Auth flow
- Retrieve → Run Scoring → View Results → Generate Summary Reports
- Supabase storage + snapshots (draft)
- Download CSV/Parquet
- XmR plot for Class 1 %
- Retro backfill helper (nightly only; guarded)
"""

from __future__ import annotations

# ============== stdlib
import io
import os
import secrets
from datetime import date, datetime, time, timedelta

# ============== 3rd-party
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pyarrow as pa
import pyarrow.parquet as pq

# Altair is used for XmR; import lazily in the function to avoid startup errors
# (kept as hard import originally; refactor makes it lazy)

# ============== app modules (project-local)
from lead_scoring_tool import apply_lead_scoring
from generate_summary_reports import generate_summary
from ga_data_retrieval import fetch_ga_data
from dreamclass_data_handler import fetch_dreamclass_data, clean_dreamclass_data
from auth_library import authenticate

# =============================================================
# 0) ENV + GUARDS
# =============================================================
APP = st.secrets.get("app", {})
ENV = APP.get("env", "prod")
IS_NIGHTLY = (ENV == "nightly")
ALLOW_PUBLISH = APP.get("allow_publish", ENV == "prod")
TIMEZONE = APP.get("timezone", "Europe/Athens")
SCORING_VERSION = APP.get("scoring_version", "3.0.0")

if IS_NIGHTLY:
    st.sidebar.caption("🧪 NIGHTLY — not for official KPIs")
    # belt & suspenders
    assert not ALLOW_PUBLISH, "Nightly must not allow publishing"

# =============================================================
# 1) SUPABASE
# =============================================================
try:
    from supabase import create_client
except Exception:
    st.sidebar.error("Supabase client not installed. Add 'supabase' to requirements.txt.")
    create_client = None

def _get_supabase():
    cfg = st.secrets.get("supabase", {})
    url, key = cfg.get("url"), cfg.get("service_key")
    bucket = cfg.get("bucket", "snapshots-nightly")
    if not create_client or not url or not key:
        return None, bucket
    return create_client(url, key), bucket

SB, BUCKET = _get_supabase()
if SB:
    try:
        buckets = SB.storage.list_buckets()
        names = [b.get("name") if isinstance(b, dict) else getattr(b, "name", None) for b in buckets]
        st.sidebar.success(f"Supabase connected ({len(buckets)} buckets)")
        st.sidebar.success(f"Bucket '{BUCKET}' ready" if BUCKET in names else f"Bucket '{BUCKET}' missing")
    except Exception as e:
        st.sidebar.error("Supabase connection failed")
        st.sidebar.exception(e)
else:
    st.sidebar.warning("Supabase not configured")

# =============================================================
# 2) HELPERS
# =============================================================
# 2.1 Arrow-friendly export
import json

def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    def _to_json_if_nested(v):
        if isinstance(v, (dict, list, tuple, set)):
            try:
                return json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                return str(v)
        return v
    for col in out.columns:
        s = out[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            out[col] = pd.to_datetime(s, utc=True)
            continue
        if s.dtype == "object":
            if s.map(lambda x: isinstance(x, (dict, list, tuple, set))).any():
                out[col] = s.map(_to_json_if_nested).astype("string")
            else:
                types = s.map(lambda x: type(x).__name__ if pd.notna(x) else "NA").unique().tolist()
                non_na = [t for t in types if t != "NA"]
                if len(non_na) > 1:
                    out[col] = s.astype("string")
    for col in ("email", "phone", "schooltype"):
        if col in out.columns:
            out[col] = out[col].astype("string")
    return out

def as_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    clean = _normalize_for_parquet(df)
    table = pa.Table.from_pandas(clean, preserve_index=False)
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()

def as_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# 2.2 Inclusive date-range filtering (by date, not time)

def filter_by_period(df: pd.DataFrame, col: str, start_d: date, end_d: date) -> pd.DataFrame:
    if not pd.api.types.is_datetime64_any_dtype(df[col]):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df[df[col].dt.date.between(start_d, end_d)]

# 2.3 KPIs

def compute_kpis(df: pd.DataFrame, class_col: str = "lead_class") -> dict:
    total = int(len(df))
    out = {"total_leads": total}
    if total == 0 or class_col not in df.columns:
        for c in (1, 2, 3, 4):
            out[f"class{c}_count"], out[f"class{c}_pct"] = 0, 0.0
        return out
    counts = df[class_col].value_counts().sort_index()
    for c in (1, 2, 3, 4):
        n = int(counts.get(c, 0))
        out[f"class{c}_count"] = n
        out[f"class{c}_pct"] = round(100.0 * n / total, 2) if total else 0.0
    return out

# 2.4 XmR (lazy Altair import) + zone lines

def render_xmr_class1(df_rep: pd.DataFrame, *, drafts_only: bool) -> None:
    try:
        import altair as alt
    except Exception as e:
        st.warning("Altair not available.")
        st.exception(e)
        return

    if df_rep.empty or not {"period_end", "class1_pct"}.issubset(df_rep.columns):
        st.info("No snapshots with class1_pct found.")
        return

    df = df_rep.copy()
    if drafts_only and "is_draft" in df.columns:
        df = df[df["is_draft"] == True]
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.date
    df = df.sort_values("period_end").reset_index(drop=True)

    x = pd.to_numeric(df["class1_pct"], errors="coerce").astype(float)
    idx = df["period_end"].astype(str)

    mr = x.diff().abs()
    mr_bar = mr[1:].mean() if len(mr) > 1 else np.nan
    d2 = 1.128
    sigma = (mr_bar / d2) if (isinstance(mr_bar, (int, float)) and not np.isnan(mr_bar) and mr_bar > 0) else np.nan
    x_bar = x.mean() if len(x) else np.nan

    def clamp(v):
        return float(np.clip(v, 0.0, 100.0)) if v == v else np.nan
    ucl_x = clamp(x_bar + 3 * sigma) if sigma == sigma else np.nan
    lcl_x = clamp(x_bar - 3 * sigma) if sigma == sigma else np.nan
    z1_up = clamp(x_bar + 1 * sigma) if sigma == sigma else np.nan
    z1_lo = clamp(x_bar - 1 * sigma) if sigma == sigma else np.nan
    z2_up = clamp(x_bar + 2 * sigma) if sigma == sigma else np.nan
    z2_lo = clamp(x_bar - 2 * sigma) if sigma == sigma else np.nan

    plot_df = pd.DataFrame({"period_end": idx, "class1_pct": x, "mr": mr})

    base_x = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
    line_x = base_x.mark_line().encode(y=alt.Y("class1_pct:Q", title="Class 1 %"))
    pts_x  = base_x.mark_circle(size=60).encode(
        y="class1_pct:Q",
        tooltip=[alt.Tooltip("period_end:N", title="Period end"), alt.Tooltip("class1_pct:Q", title="Class1 %", format=".2f")],
    )

    rules_df = pd.DataFrame({"y": [x_bar, ucl_x, lcl_x], "label": ["CL", "UCL", "LCL"]})
    rules_x = alt.Chart(rules_df).mark_rule(strokeDash=[6, 3]).encode(y="y:Q").properties(height=220)

    labels_df = pd.DataFrame({"y": [x_bar, ucl_x, lcl_x], "text": [f"CL {x_bar:.2f}", f"UCL {ucl_x:.2f}", f"LCL {lcl_x:.2f}"]})
    labels_x = alt.Chart(labels_df).mark_text(align="left", dx=5, dy=-5).encode(y="y:Q", text="text:N")

    zones_df = pd.DataFrame({"y": [z1_up, z1_lo, z2_up, z2_lo]})
    zones = alt.Chart(zones_df).mark_rule(strokeDash=[2, 3], opacity=0.35).encode(y="y:Q")

    x_chart = (line_x + pts_x + rules_x + labels_x + zones).properties(title="Individuals (Class 1 %)")

    base_mr = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
    bar_mr  = base_mr.mark_bar().encode(y=alt.Y("mr:Q", title="Moving range"))
    mr_rules_df = pd.DataFrame({"y": [mr_bar, 3.267 * mr_bar if mr_bar == mr_bar else np.nan, 0.0]})
    rules_mr = alt.Chart(mr_rules_df).mark_rule(strokeDash=[6, 3]).encode(y="y:Q").properties(height=140)

    st.altair_chart(
        alt.vconcat(x_chart, (bar_mr + rules_mr)).resolve_scale(y="independent"),
        use_container_width=True,
    )

# =============================================================
# 3) AUTH + NAVIGATION
# =============================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

st.sidebar.header("Login")
if not st.session_state["authenticated"]:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if authenticate(username, password):
            st.success("Login successful!")
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid username or password.")

if not st.session_state["authenticated"]:
    st.warning("Please log in to access the app.")
    st.stop()

st.title("Lead Scoring Tool")
st.sidebar.header("Navigation")
section = st.sidebar.selectbox("Choose a section:", ["Retrieve Data", "Run Scoring", "View Results", "Generate Summary Reports"])

# =============================================================
# 4) RETRIEVE DATA
# =============================================================
if section == "Retrieve Data":
    st.header("Retrieve Data")

    # ---- Date Range (inclusive)
    today = pd.Timestamp.now().date()
    default_start = today - timedelta(days=14)
    default_end = today
    picked = st.date_input("Pick a date range (inclusive)", [default_start, default_end], max_value=today)
    if not isinstance(picked, (list, tuple)) or len(picked) != 2:
        st.error("Please select a valid date range.")
        st.stop()
    d1, d2 = picked
    if d1 > d2:
        st.error("Start date cannot be after end date.")
        st.stop()

    # Remember in session
    st.session_state["date_min"], st.session_state["date_max"] = str(d1), str(d2)
    st.session_state["run_period_start"], st.session_state["run_period_end"] = d1, d2
    st.success(f"Date Range Selected: {d1} → {d2}")

    # ---- DreamClass fetch/clean (simple viewer)
    st.subheader("DreamClass Data Retrieval")
    default_statuses = ["trial", "trial_expired", "active", "canceled"]
    selected_statuses = st.multiselect("Select statuses to retrieve:", options=default_statuses, default=default_statuses)
    if not selected_statuses:
        st.error("Please select at least one status.")
        st.stop()

    if st.button("Fetch DreamClass Data", type="primary", use_container_width=True):
        try:
            raw_dc = fetch_dreamclass_data(st.secrets["dreamclass_api"]["base_url"], selected_statuses)
            dc = clean_dreamclass_data(raw_dc)
            if "createdAt" in dc.columns and not pd.api.types.is_datetime64_any_dtype(dc["createdAt"]):
                dc["createdAt"] = pd.to_datetime(dc["createdAt"], errors="coerce")
            if "createdAt" in dc.columns:
                try:
                    dc["createdAt"] = dc["createdAt"].dt.tz_localize(None)
                except Exception:
                    pass
            st.session_state["dreamclass_data"] = dc

            # Show only rows within selected window
            in_window = filter_by_period(dc, "createdAt", d1, d2)
            st.session_state["dreamclass_data_in_window"] = in_window

            total, nwin = len(dc), len(in_window)
            win_min = in_window["createdAt"].min() if nwin else None
            win_max = in_window["createdAt"].max() if nwin else None
            st.success(
                f"DreamClass ✓ Total: {total:,} | In period ({d1}→{d2}): {nwin:,} " + (f"({win_min}→{win_max})" if nwin else "(no rows)")
            )
            st.dataframe(in_window.head(1000), use_container_width=True)

        except Exception as e:
            st.error("Failed to retrieve or clean DreamClass data.")
            st.exception(e)

    # ---- GA fetch (optional quick view)
    st.subheader("Google Analytics Data Retrieval")
    if st.button("Fetch Google Analytics Data"):
        try:
            ga = fetch_ga_data(str(d1), str(d2))
            ga = ga.rename(
                columns={
                    "firstUserCampaignName": "First user campaign",
                    "firstUserSourceMedium": "First user source / medium",
                    "customUser:icpGroup": "icp_group",
                    "customUser:schoolType": "school_type",
                    "customUser:userId": "userId",
                    "firstUserGoogleAdsAdGroupName": "Google Ads Ad Group",
                }
            )
            st.session_state["ga_data"] = ga
            st.success(f"Google Analytics ✓ Rows: {len(ga):,}")
            st.dataframe(ga.head(1000), use_container_width=True)
        except Exception as e:
            st.error(f"Failed to fetch GA data: {e}")

# =============================================================
# 5) RUN SCORING
# =============================================================
elif section == "Run Scoring":
    st.header("Run Lead Scoring")

    if "dreamclass_data" not in st.session_state or st.session_state["dreamclass_data"] is None:
        st.info("Please retrieve DreamClass data first.")
        st.stop()

    d1 = st.session_state.get("run_period_start")
    d2 = st.session_state.get("run_period_end")
    dc = st.session_state.get("dreamclass_data")
    ga = st.session_state.get("ga_data")

    # Inclusive filters
    dc_f = filter_by_period(dc, "createdAt", d1, d2)
    if isinstance(ga, pd.DataFrame) and not ga.empty:
        # Replace with your GA date column if different
        ga_date_col = "event_date" if "event_date" in ga.columns else ga.columns[0]
        ga_f = filter_by_period(ga, ga_date_col, d1, d2)
    else:
        ga_f = None

    st.write(f"DreamClass rows in period: {len(dc_f):,}")
    if ga_f is not None:
        st.write(f"GA rows in period: {len(ga_f):,}")

    scored_df = apply_lead_scoring(dc_f, ga_f)
    st.session_state["scored_data"] = scored_df

    st.success("Lead scoring completed! Proceed to 'View Results'.")
    st.dataframe(scored_df.head(30), use_container_width=True)

# =============================================================
# 6) VIEW RESULTS
# =============================================================
elif section == "View Results":
    st.header("View Scoring Results")

    if "scored_data" not in st.session_state:
        st.info("Run lead scoring to view results.")
        st.stop()

    scored_data = st.session_state["scored_data"].copy()
    if "createdAt" in scored_data.columns and not pd.api.types.is_datetime64_any_dtype(scored_data["createdAt"]):
        scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], errors="coerce")
    scored_data["createdAt"] = scored_data["createdAt"].dt.tz_localize(None)

    # ---- Filters
    rp_start = st.session_state.get("run_period_start")
    rp_end = st.session_state.get("run_period_end")

    dmin = scored_data["createdAt"].min()
    dmax = scored_data["createdAt"].max()
    default_start = rp_start or (dmin.date() if pd.notna(dmin) else date.today())
    default_end = rp_end or (dmax.date() if pd.notna(dmax) else date.today())

    start_date, end_date = st.date_input("Select Date Range (inclusive)", [default_start, default_end])

    filtered = filter_by_period(scored_data, "createdAt", start_date, end_date)

    # Lead class & score filters
    if "lead_class" in filtered.columns:
        opts = sorted(filtered["lead_class"].dropna().unique().tolist())
        lead_class_filter = st.multiselect("Lead Class", options=opts, default=opts)
        filtered = filtered[filtered["lead_class"].isin(lead_class_filter)]
    if "total_score" in filtered.columns and not filtered["total_score"].empty:
        mn, mx = float(filtered["total_score"].min()), float(filtered["total_score"].max())
        vmin, vmax = st.slider("Total Score Range", min_value=mn, max_value=mx, value=(mn, mx))
        filtered = filtered[(filtered["total_score"] >= vmin) & (filtered["total_score"] <= vmax)]

    # Sorting
    st.subheader("Sort Results")
    if "lead_class" in filtered.columns:
        sort_by = st.selectbox("Sort by", ["Total Score", "Lead Class"]) 
    else:
        sort_by = "Total Score"
    ascending = st.radio("Order", ["Ascending", "Descending"], horizontal=True) == "Ascending"
    if sort_by == "Total Score" and "total_score" in filtered.columns:
        filtered = filtered.sort_values("total_score", ascending=ascending)
    elif sort_by == "Lead Class" and "lead_class" in filtered.columns:
        filtered = filtered.sort_values("lead_class", ascending=ascending)

    st.dataframe(filtered, use_container_width=True)

    # ---- Pie chart
    if "lead_class" in filtered.columns and not filtered.empty:
        counts = filtered["lead_class"].value_counts().sort_index()
        pct = counts / counts.sum() * 100 if counts.sum() else counts
        st.subheader("Lead Class Distribution")
        def _autopct(pct_val, all_values):
            absolute = int(round(pct_val / 100.0 * sum(all_values)))
            return f"{pct_val:.1f}%\n({absolute})"
        fig, ax = plt.subplots()
        ax.pie(
            pct,
            labels=[f"Class {int(c)}" for c in counts.index],
            autopct=lambda p: _autopct(p, counts),
            startangle=90,
            counterclock=False,
            colors=plt.cm.Paired.colors[: len(counts)],
        )
        ax.set_title(f"Lead Class Distribution (Total Leads: {len(filtered)})")
        ax.axis("equal")
        st.pyplot(fig)

    # ---- Downloads
    fname_base = f"scored_{start_date}_{end_date}"
    c1, c2 = st.columns(2)
    with c1:
        if IS_NIGHTLY:
            st.download_button(
                "Download filtered results (.parquet)",
                data=as_parquet_bytes(filtered),
                file_name=f"{fname_base}.parquet",
                mime="application/octet-stream",
                use_container_width=True,
            )
    with c2:
        st.download_button(
            "Download filtered results (.csv)",
            data=as_csv_bytes(filtered),
            file_name=f"{fname_base}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ---- Save Snapshot (draft)
    st.divider()
    st.subheader("Save Snapshot (draft)")
    note = st.text_input("Optional note", value="", help="Short reason or context")
    if st.button("Save snapshot (draft)", type="primary", use_container_width=True):
        try:
            cutoff = datetime.combine(end_date, time(23, 59, 59, 999999))
            path = f"{end_date:%Y/%m/%d}/manual/{fname_base}.parquet"
            bytes_parquet = as_parquet_bytes(filtered)
            if SB:
                SB.storage.from_(BUCKET).upload(path, bytes_parquet, {"content-type": "application/octet-stream", "x-upsert": "true"})
            kpis = compute_kpis(filtered)
            row = {
                "created_by": "aristeidis",
                "run_type": "manual",
                "is_draft": True,
                "period_start": str(start_date),
                "period_end": str(end_date),
                "observation_cutoff": cutoff.isoformat(),
                "scoring_version": SCORING_VERSION,
                "env": ENV,
                "reason": (note or None),
                "parquet_path": path,
                **kpis,
            }
            if SB:
                SB.table("snapshots").insert(row).execute()
            st.toast("Snapshot saved (draft). Check Reports.", icon="✅")
        except Exception as e:
            st.error("Failed to save snapshot (draft).")
            st.exception(e)

# =============================================================
# 7) GENERATE SUMMARY REPORTS
# =============================================================
elif section == "Generate Summary Reports":
    st.header("Generate Summary Reports")

    # A) Ad-hoc summary over currently scored_data (kept from original)
    if "scored_data" in st.session_state:
        scored_data = st.session_state["scored_data"].copy()
        if "createdAt" in scored_data.columns and not pd.api.types.is_datetime64_any_dtype(scored_data["createdAt"]):
            scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], errors="coerce")
        scored_data["createdAt"] = scored_data["createdAt"].dt.tz_localize(None)

        st.subheader("Controls")
        dmin = scored_data["createdAt"].min(); dmax = scored_data["createdAt"].max()
        start_date, end_date = st.date_input("Select Date Range", [dmin, dmax])
        if pd.to_datetime(start_date) > pd.to_datetime(end_date):
            st.error("Start date cannot be after end date.")
        dimension_mapping = {"Source/Medium": "First user source / medium", "Campaign": "First user campaign"}
        selected_dimensions = st.multiselect("Select dimensions to group by", options=list(dimension_mapping.keys()), default=["Source/Medium"])
        selected_columns = [dimension_mapping[d] for d in selected_dimensions if d in dimension_mapping]
        if st.button("Generate Report"):
            if not selected_columns:
                st.error("Please select at least one grouping dimension.")
            else:
                try:
                    summary = generate_summary(scored_data, pd.to_datetime(start_date), pd.to_datetime(end_date), selected_columns)
                    st.subheader("Summary Report")
                    st.dataframe(summary)
                    st.download_button(
                        label="Download Report",
                        data=summary.to_csv(index=False).encode("utf-8"),
                        file_name=f"summary_report_{pd.to_datetime(start_date).strftime('%Y%m%d')}_to_{pd.to_datetime(end_date).strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"An error occurred: {e}")

    # B) Snapshots list + preview + XmR
    st.subheader("Saved snapshots")
    if not SB:
        st.info("Supabase not configured.")
        st.stop()
    try:
        q = SB.table("snapshots").select("*").eq("env", ENV).order("created_at", desc=True).limit(200).execute()
        df_rep = pd.DataFrame(q.data)
        if df_rep.empty:
            st.info("No snapshots yet. Save a snapshot from View Results.")
        else:
            drafts_only = st.checkbox("Show drafts only", value=IS_NIGHTLY)
            df_view = df_rep[df_rep["is_draft"] == True] if drafts_only and "is_draft" in df_rep.columns else df_rep.copy()
            cols = [
                "created_at","created_by","run_type","is_draft",
                "period_start","period_end","scoring_version",
                "total_leads","class1_count","class1_pct",
                "class2_count","class2_pct","class3_count","class3_pct",
                "class4_count" if "class4_count" in df_rep.columns else None,
                "class4_pct" if "class4_pct" in df_rep.columns else None,
                "parquet_path","reason",
            ]
            cols = [c for c in cols if c and c in df_view.columns]
            st.dataframe(df_view[cols], use_container_width=True)

            st.subheader("XmR: Class 1 % over time")
            render_xmr_class1(df_rep[df_rep["env"] == ENV], drafts_only=drafts_only)

            with st.expander("Open a snapshot"):
                options = df_view.head(50).apply(
                    lambda r: f"{r.get('created_at','')} | {r.get('period_start','')}→{r.get('period_end','')} | {'DRAFT' if r.get('is_draft') else r.get('run_type','').upper()}",
                    axis=1,
                ).tolist()
                if options:
                    sel = st.selectbox("Choose snapshot", options=options, index=0)
                    row = df_view.iloc[options.index(sel)]
                    path = row["parquet_path"]
                    st.write("Storage path:", path)
                    try:
                        file_bytes = SB.storage.from_(BUCKET).download(path)
                        try:
                            df_preview = pd.read_parquet(io.BytesIO(file_bytes))
                        except Exception:
                            df_preview = pd.read_csv(io.BytesIO(file_bytes))
                        st.caption(f"Preview: {len(df_preview)} rows (first 20)")
                        st.dataframe(df_preview.head(20), use_container_width=True)
                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button("Download snapshot file", data=file_bytes, file_name=os.path.basename(path), mime="application/octet-stream", use_container_width=True)
                        with c2:
                            st.download_button("Download as CSV (repacked)", data=df_preview.to_csv(index=False).encode("utf-8"), file_name=os.path.basename(path).replace(".parquet", ".csv"), mime="text/csv", use_container_width=True)
                    except Exception as e:
                        st.error("Failed to open snapshot from storage.")
                        st.exception(e)
    except Exception as e:
        st.error("Failed to load snapshots list.")
        st.exception(e)

    # C) Retro backfill helper — guard to nightly only
    if IS_NIGHTLY:
        st.divider()
        st.subheader("Backfill missing June–July snapshots (aggregate-only)")
        st.caption("Creates aggregate-only Parquet + registers snapshots so XmR has points for these periods.")

        def _parquet_bytes_from_aggregates(period_start: date, period_end: date, counts: dict, pcts: dict) -> bytes:
            rows = []
            total = sum(counts.values())
            for c in (1, 2, 3, 4):
                rows.append({
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "class": c,
                    "count": int(counts.get(c, 0)),
                    "pct": float(pcts.get(c, 0.0)),
                    "total_leads": total,
                    "source": "retro-manual-aggregate",
                })
            df = pd.DataFrame(rows)
            table = pa.Table.from_pandas(df, preserve_index=False)
            md = {b"env": ENV.encode(), b"scoring_version": SCORING_VERSION.encode(), b"note": b"Backfilled from spreadsheet; aggregate-only."}
            table = table.replace_schema_metadata({**(table.schema.metadata or {}), **md})
            buf = io.BytesIO(); pq.write_table(table, buf, compression="snappy"); return buf.getvalue()

        def _register_snapshot(period_start: str, period_end: str, counts: dict, pcts: dict, note: str):
            ps = pd.to_datetime(period_start).date(); pe = pd.to_datetime(period_end).date()
            cutoff = datetime.combine(pe, time(23, 59, 59))
            bucket = BUCKET
            fname = f"manual_agg_{ps}_{pe}.parquet"; path = f"{pe:%Y/%m/%d}/manual/{fname}"
            file_bytes = _parquet_bytes_from_aggregates(ps, pe, counts, pcts)
            SB.storage.from_(bucket).upload(path, file_bytes, {"content-type": "application/octet-stream", "x-upsert": "true"})
            total = int(sum(counts.values()))
            row = {
                "created_by": "aristeidis",
                "run_type": "manual",
                "is_draft": True,
                "period_start": str(ps),
                "period_end": str(pe),
                "observation_cutoff": cutoff.isoformat(),
                "scoring_version": SCORING_VERSION,
                "env": ENV,
                "reason": f"retro backfill — {note}",
                "parquet_path": path,
                "total_leads": total,
                "class1_count": int(counts.get(1, 0)), "class1_pct": float(pcts.get(1, 0.0)),
                "class2_count": int(counts.get(2, 0)), "class2_pct": float(pcts.get(2, 0.0)),
                "class3_count": int(counts.get(3, 0)), "class3_pct": float(pcts.get(3, 0.0)),
                "class4_count": int(counts.get(4, 0)), "class4_pct": float(pcts.get(4, 0.0)),
            }
            SB.table("snapshots").insert(row).execute()
            st.toast(f"Backfilled {ps} → {pe}", icon="✅")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Backfill 2025-06-22 → 2025-07-05", use_container_width=True):
                _register_snapshot("2025-06-22", "2025-07-05", counts={1: 66, 2: 124, 3: 73, 4: 33}, pcts={1: 22.30, 2: 41.89, 3: 24.66, 4: 11.15}, note="spreadsheet aggregates (no per-lead rows)")
        with c2:
            if st.button("Backfill 2025-07-06 → 2025-07-19", use_container_width=True):
                _register_snapshot("2025-07-06", "2025-07-19", counts={1: 67, 2: 122, 3: 74, 4: 31}, pcts={1: 22.79, 2: 41.50, 3: 25.17, 4: 10.54}, note="spreadsheet aggregates (no per-lead rows)")

# =============================================================
# 8) END
# =============================================================
