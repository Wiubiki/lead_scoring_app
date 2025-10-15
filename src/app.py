# Lead Scoring App — refactored scaffold (v3)
# ------------------------------------------------------------
# Goals of this refactor
# - Clear sections & navigation
# - One place for config/env & Supabase client
# - Robust datetime handling (inclusive end-date)
# - Small, testable helpers (export, KPIs, period filter)
# - Safer plotting (lazy Altair import)
# - Snapshot save/list preview
# ------------------------------------------------------------

from __future__ import annotations

# ========== Standard imports
import io
import os
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import streamlit as st

# ========== App-specific imports (existing modules)
# NOTE: These must exist in your repo as they did before
from auth_library import authenticate
from dreamclass_data_handler import fetch_dreamclass_data, clean_dreamclass_data
from ga_data_retrieval import fetch_ga_data
from lead_scoring_tool import apply_lead_scoring

# ------------------------------------------------------------
# 0) CONFIG & ENV
# ------------------------------------------------------------
APP_SECRETS = st.secrets.get("app", {})
ENV = APP_SECRETS.get("env", "prod")
IS_NIGHTLY = (ENV == "nightly")
TIMEZONE = APP_SECRETS.get("timezone", "Europe/Athens")
SCORING_VERSION = APP_SECRETS.get("scoring_version", "3.0.0")

# Nightly guardrails
ALLOW_PUBLISH = APP_SECRETS.get("allow_publish", False)
if IS_NIGHTLY:
    # Nightly must never publish; use this assert as a tripwire
    assert not ALLOW_PUBLISH, "Nightly must not allow publishing"

# ------------------------------------------------------------
# 1) SUPABASE CLIENT
# ------------------------------------------------------------
try:
    from supabase import create_client
except Exception:
    create_client = None

@dataclass
class SBConfig:
    url: str | None
    service_key: str | None
    bucket: str


def get_supabase() -> tuple[object | None, SBConfig]:
    cfg = st.secrets.get("supabase", {})
    url = cfg.get("url")
    key = cfg.get("service_key")
    bucket = cfg.get("bucket", "snapshots-nightly")
    if not create_client or not url or not key:
        return None, SBConfig(url, key, bucket)
    return create_client(url, key), SBConfig(url, key, bucket)


SB, SBCFG = get_supabase()
if SB:
    # Simple ping + bucket presence hint
    try:
        buckets = SB.storage.list_buckets()
        names = [b.get("name") if isinstance(b, dict) else getattr(b, "name", None) for b in buckets]
        st.sidebar.success(f"Supabase connected ({len(buckets)} buckets)")
        if SBCFG.bucket in names:
            st.sidebar.success(f"Bucket '{SBCFG.bucket}' ready")
        else:
            st.sidebar.warning(f"Bucket '{SBCFG.bucket}' missing (expected '{SBCFG.bucket}')")
    except Exception as e:
        st.sidebar.error("Supabase connection failed")
        st.sidebar.exception(e)
else:
    st.sidebar.warning("Supabase not configured")


# ------------------------------------------------------------
# 2) HELPERS
# ------------------------------------------------------------
# 2.1 Datetime parsing & inclusive period filter

def parse_created_at(series: pd.Series, *, prefer_dayfirst: bool | None = None) -> pd.Series:
    """Robustly parse timestamps. Returns NAIVE datetimes (no tz)."""
    s = series.astype("string").str.strip()

    def _try(src: pd.Series, **kw) -> pd.Series:
        return pd.to_datetime(src, errors="coerce", utc=False, **kw)

    base = _try(s)
    dfirst = _try(s, dayfirst=True)
    if prefer_dayfirst is True:
        dt = dfirst.fillna(base)
    elif prefer_dayfirst is False:
        dt = base.fillna(dfirst)
    else:
        dt = base.fillna(dfirst)

    # 10s / 13ms epochs
    m10 = dt.isna() & s.str.match(r"^\d{10}(\.\d+)?$").fillna(False)
    if m10.any():
        dt.loc[m10] = pd.to_datetime(s[m10].astype(float), unit="s", errors="coerce")
    m13 = dt.isna() & s.str.match(r"^\d{13}$").fillna(False)
    if m13.any():
        dt.loc[m13] = pd.to_datetime(s[m13].astype(float), unit="ms", errors="coerce")

    return pd.to_datetime(dt).dt.tz_localize(None)


def filter_by_period(df: pd.DataFrame, col: str, start_d: date, end_d: date) -> pd.DataFrame:
    """Inclusive date-range filter by date component."""
    if not pd.api.types.is_datetime64_any_dtype(df[col]):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df[df[col].dt.date.between(start_d, end_d)]


# 2.2 Export helpers (Parquet/CSV)

def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Datetime → UTC-aware for Arrow (we drop tz back to naive on read/UI)
    for c in out.columns:
        s = out[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            out[c] = pd.to_datetime(s, utc=True)
        elif s.dtype == "object":
            # make nested structures JSON-safe strings
            if s.map(lambda x: isinstance(x, (dict, list, tuple, set))).any():
                out[c] = s.map(lambda v: io.StringIO() or (pd.io.json.dumps(v) if isinstance(v, (dict, list, tuple, set)) else str(v))).astype("string")
    # Known text columns → string
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


# 2.3 KPIs & filenames

def compute_kpis_dynamic(df: pd.DataFrame, class_col: str = "lead_class") -> dict:
    total = int(len(df))
    out: dict[str, float | int] = {"total_leads": total}
    if total == 0 or class_col not in df.columns:
        for c in (1, 2, 3, 4):
            out[f"class{c}_count"] = 0
            out[f"class{c}_pct"] = 0.0
        return out
    counts = df[class_col].value_counts().sort_index()
    for c, n in counts.items():
        out[f"class{int(c)}_count"] = int(n)
        out[f"class{int(c)}_pct"] = round(100.0 * n / total, 2)
    # ensure all 1..4 exist
    for c in (1, 2, 3, 4):
        out.setdefault(f"class{c}_count", 0)
        out.setdefault(f"class{c}_pct", 0.0)
    return out


def make_snapshot_fname(start_d: date, end_d: date) -> str:
    return f"scored_{start_d}_{end_d}"


# 2.4 XmR plot (lazy import Altair + WECO/Nelson signals)

def render_xmr_class1(df_snapshots: pd.DataFrame, *, show_drafts_only: bool) -> None:
    try:
        import altair as alt  # lazy import to avoid hard dependency at startup
    except Exception as e:
        st.warning("Altair not available. Upgrade requirements and refresh.")
        st.exception(e)
        return

    if df_snapshots.empty or "class1_pct" not in df_snapshots.columns:
        st.info("No snapshots with class1_pct found.")
        return

    df = df_snapshots.copy()
    if show_drafts_only and "is_draft" in df.columns:
        df = df[df["is_draft"] == True]

    # order by period_end
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.date
    df = df.sort_values("period_end").reset_index(drop=True)

    x = pd.to_numeric(df["class1_pct"], errors="coerce").astype(float)
    idx = df["period_end"].astype(str)

    # mR & sigma
    mr = x.diff().abs()
    mr_bar = mr[1:].mean() if len(mr) > 1 else np.nan
    d2 = 1.128
    sigma = (mr_bar / d2) if (mr_bar == mr_bar and mr_bar > 0) else np.nan
    x_bar = x.mean() if len(x) else np.nan

    # Limits (clamped 0-100)
    def clamp(v):
        return float(np.clip(v, 0.0, 100.0)) if v == v else np.nan

    ucl_x = clamp(x_bar + 3 * sigma) if sigma == sigma else np.nan
    lcl_x = clamp(x_bar - 3 * sigma) if sigma == sigma else np.nan
    z1_up, z1_low, z2_up, z2_low = (np.nan, np.nan, np.nan, np.nan)
    if sigma == sigma:
        z1_up, z1_low = clamp(x_bar + 1 * sigma), clamp(x_bar - 1 * sigma)
        z2_up, z2_low = clamp(x_bar + 2 * sigma), clamp(x_bar - 2 * sigma)
    ucl_mr = 3.267 * mr_bar if mr_bar == mr_bar else np.nan

    # WECO signals
    z = (x - x_bar) / sigma if sigma == sigma and sigma not in (0, np.inf) else pd.Series([np.nan] * len(x))
    sign = np.sign(z)
    N = len(x)
    r1 = (np.abs(z) > 3).fillna(False).to_numpy() if sigma == sigma else np.zeros(N, dtype=bool)
    r2 = np.zeros(N, dtype=bool)
    r3 = np.zeros(N, dtype=bool)
    r4 = np.zeros(N, dtype=bool)

    if sigma == sigma and sigma not in (0, np.inf):
        # 2 of 3 beyond 2σ same side
        for i in range(2, N):
            w = z.iloc[i - 2 : i + 1]
            if (w > 2).sum() >= 2 or (w < -2).sum() >= 2:
                r2[(w.index.min()) : (w.index.max() + 1)] = True
        # 4 of 5 beyond 1σ same side
        for i in range(4, N):
            w = z.iloc[i - 4 : i + 1]
            if (w > 1).sum() >= 4 or (w < -1).sum() >= 4:
                r3[(w.index.min()) : (w.index.max() + 1)] = True
        # 8 in a row same side
        run_len, last = 0, 0
        for i in range(N):
            s = sign.iloc[i]
            if s == 0 or np.isnan(s):
                run_len, last = 0, 0
                continue
            if s == last:
                run_len += 1
            else:
                run_len, last = 1, s
            if run_len >= 8:
                r4[i - 7 : i + 1] = True

    rules_txt = []
    for i in range(N):
        hits = []
        if r1[i]:
            hits.append("WECO-1 >3σ")
        if r2[i]:
            hits.append("WECO-2 2/3>2σ")
        if r3[i]:
            hits.append("WECO-3 4/5>1σ")
        if r4[i]:
            hits.append("WECO-4 8-run")
        rules_txt.append(", ".join(hits))
    flags = (r1 | r2 | r3 | r4)

    plot_df = pd.DataFrame({
        "period_end": idx,
        "class1_pct": x,
        "mr": mr,
        "flag": flags,
        "rules": rules_txt,
    })

    base_x = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
    line_x = base_x.mark_line().encode(y=alt.Y("class1_pct:Q", title="Class 1 %"))
    pts_ok = base_x.mark_circle(size=60, color="#4c78a8").encode(
        y="class1_pct:Q",
        tooltip=[
            alt.Tooltip("period_end:N", title="Period end"),
            alt.Tooltip("class1_pct:Q", title="Class1 %", format=".2f"),
        ],
    ).transform_filter(alt.datum.flag == False)
    pts_bad = base_x.mark_circle(size=100, color="#e45756").encode(
        y="class1_pct:Q",
        tooltip=[
            alt.Tooltip("period_end:N", title="Period end"),
            alt.Tooltip("class1_pct:Q", title="Class1 %", format=".2f"),
            alt.Tooltip("rules:N", title="Signals"),
        ],
    ).transform_filter(alt.datum.flag == True)

    rules_x = alt.Chart(pd.DataFrame({"y": [x_bar, ucl_x, lcl_x]})).mark_rule(strokeDash=[6, 3]).encode(y="y:Q").properties(height=220)
    labels_x = alt.Chart(pd.DataFrame({
        "y": [x_bar, ucl_x, lcl_x],
        "text": [f"CL {x_bar:.2f}", f"UCL {ucl_x:.2f}", f"LCL {lcl_x:.2f}"],
    })).mark_text(align="left", dx=5, dy=-5).encode(y="y:Q", text="text:N")

    # Zone lines (±1σ, ±2σ)
    zones_df = pd.DataFrame({"y": [z1_up, z1_low, z2_up, z2_low]})
    zones = alt.Chart(zones_df).mark_rule(strokeDash=[2, 3], opacity=0.35).encode(y="y:Q")

    x_chart = (line_x + pts_ok + pts_bad + rules_x + labels_x + zones).properties(title="Individuals (Class 1 %)")

    base_mr = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
    bar_mr = base_mr.mark_bar().encode(y=alt.Y("mr:Q", title="Moving range"))
    rules_mr = alt.Chart(pd.DataFrame({"y": [mr_bar, 3.267 * mr_bar if mr_bar == mr_bar else np.nan, 0.0]})).mark_rule(
        strokeDash=[6, 3]
    ).encode(y="y:Q").properties(height=140)

    st.altair_chart(
        alt.vconcat(x_chart, (bar_mr + rules_mr)).resolve_scale(y="independent"),
        use_container_width=True,
    )


# ------------------------------------------------------------
# 3) AUTH + NAV
# ------------------------------------------------------------
user = authenticate()  # your existing auth returns user info or halts
st.sidebar.markdown("🧪 **NIGHTLY** — not for official KPIs" if IS_NIGHTLY else "**Production**")

SECTIONS = [
    "Retrieve Data",
    "Run Scoring",
    "View Results",
    "Generate Summary Reports",
    "About",
]
section = st.sidebar.radio("Navigate", SECTIONS, index=0)


# ------------------------------------------------------------
# 4) RETRIEVE DATA
# ------------------------------------------------------------
if section == "Retrieve Data":
    st.header("Retrieve Data")

    # ---- Date picker for intended period (stored for later pages)
    today = date.today()
    default_start = today - timedelta(days=14)
    default_end = today - timedelta(days=1)
    d1, d2 = st.date_input("Select period (inclusive)", [default_start, default_end])
    st.session_state["date_min"], st.session_state["date_max"] = d1, d2
    st.session_state["run_period_start"], st.session_state["run_period_end"] = d1, d2

    # ---- DreamClass fetch/clean (simple viewer)
    st.subheader("DreamClass Data")
    selected_statuses = st.multiselect("Statuses", ["trial", "active", "inactive", "customer"], default=["trial", "active"])  # adjust
    if st.button("Fetch DreamClass Data", use_container_width=True):
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

            # Show only rows inside selected period
            in_win = filter_by_period(dc, "createdAt", d1, d2)
            st.session_state["dreamclass_data_in_window"] = in_win

            total, nwin = len(dc), len(in_win)
            win_min = in_win["createdAt"].min() if nwin else None
            win_max = in_win["createdAt"].max() if nwin else None
            st.success(
                f"DreamClass ✓ Total: {total:,} | In period ({d1}→{d2}): {nwin:,} "
                + (f"({win_min}→{win_max})" if nwin else "(no rows in this window)")
            )
            st.dataframe(in_win.head(1000), use_container_width=True)
        except Exception as e:
            st.error("Failed to retrieve or clean DreamClass data.")
            st.exception(e)

    # ---- GA fetch (optional quick view)
    st.subheader("Google Analytics Data Retrieval")
    if st.button("Fetch GA4 Data", use_container_width=True):
        try:
            ga = fetch_ga_data(d1, d2)  # your existing function signature
            st.session_state["ga_data"] = ga
            st.success(f"GA4 ✓ Rows: {len(ga):,}")
            st.dataframe(ga.head(1000), use_container_width=True)
        except Exception as e:
            st.error("Failed to retrieve GA4 data.")
            st.exception(e)


# ------------------------------------------------------------
# 5) RUN SCORING (single uninterrupted workflow step)
# ------------------------------------------------------------
elif section == "Run Scoring":
    st.header("Run Scoring")

    d1 = st.session_state.get("run_period_start")
    d2 = st.session_state.get("run_period_end")
    if not d1 or not d2:
        st.info("Pick a period in 'Retrieve Data' first.")
        st.stop()

    dc = st.session_state.get("dreamclass_data")
    ga = st.session_state.get("ga_data")
    if dc is None or len(dc) == 0:
        st.warning("No DreamClass data loaded yet.")
        st.stop()

    # Inclusive date filters
    dc_f = filter_by_period(dc, "createdAt", d1, d2)

    # TODO: decide if GA is required; filter if present
    if isinstance(ga, pd.DataFrame) and len(ga) > 0:
        # Replace 'event_date' with your actual GA date column
        col = "event_date" if "event_date" in ga.columns else ga.columns[0]
        ga_f = filter_by_period(ga, col, d1, d2)
    else:
        ga_f = None

    st.write(f"DreamClass rows in period: {len(dc_f):,}")
    if ga_f is not None:
        st.write(f"GA rows in period: {len(ga_f):,}")

    # Apply your scoring pipeline
    scored_df = apply_lead_scoring(dc_f, ga_f)  # keep your existing signature

    # Store for View Results
    st.session_state["scored_data"] = scored_df
    st.success("Scoring complete. Proceed to 'View Results'.")
    st.dataframe(scored_df.head(30), use_container_width=True)


# ------------------------------------------------------------
# 6) VIEW RESULTS (filters, chart, exports, save snapshot)
# ------------------------------------------------------------
elif section == "View Results":
    st.header("View Scoring Results")
    if "scored_data" not in st.session_state:
        st.info("Run scoring to view results.")
        st.stop()

    scored_data = st.session_state["scored_data"].copy()
    if "createdAt" in scored_data.columns and not pd.api.types.is_datetime64_any_dtype(scored_data["createdAt"]):
        scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], errors="coerce")
    scored_data["createdAt"] = scored_data["createdAt"].dt.tz_localize(None)

    # Filters
    st.subheader("Filter Results")
    rp_start = st.session_state.get("run_period_start")
    rp_end = st.session_state.get("run_period_end")

    # Use intended window as defaults; allow adjusting
    dmin = scored_data["createdAt"].min()
    dmax = scored_data["createdAt"].max()
    default_start = rp_start or (dmin.date() if pd.notna(dmin) else date.today())
    default_end = rp_end or (dmax.date() if pd.notna(dmax) else date.today())

    start_date, end_date = st.date_input(
        "Select Date Range (inclusive)", [default_start, default_end]
    )

    # Inclusive filter
    filtered = filter_by_period(scored_data, "createdAt", start_date, end_date)

    # Lead class & score filters (if present)
    if "lead_class" in filtered.columns:
        opts = sorted(filtered["lead_class"].dropna().unique().tolist())
        lead_class_filter = st.multiselect("Lead Class", options=opts, default=opts)
        filtered = filtered[filtered["lead_class"].isin(lead_class_filter)]
    if "total_score" in filtered.columns:
        mn, mx = float(filtered["total_score"].min()), float(filtered["total_score"].max())
        vmin, vmax = st.slider("Total Score Range", min_value=mn, max_value=mx, value=(mn, vmax if mx >= mn else mn))
        filtered = filtered[(filtered["total_score"] >= vmin) & (filtered["total_score"] <= vmax)]

    # Sorting
    st.subheader("Sort Results")
    sort_by = st.selectbox("Sort by", ["Total Score", "Lead Class"]) if "lead_class" in filtered.columns else "Total Score"
    ascending = st.radio("Order", ["Ascending", "Descending"], horizontal=True) == "Ascending"
    if sort_by == "Total Score" and "total_score" in filtered.columns:
        filtered = filtered.sort_values("total_score", ascending=ascending)
    elif sort_by == "Lead Class" and "lead_class" in filtered.columns:
        filtered = filtered.sort_values("lead_class", ascending=ascending)

    st.dataframe(filtered, use_container_width=True)

    # Pie (lead-class distribution)
    if "lead_class" in filtered.columns:
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

    # Exports
    fname_base = make_snapshot_fname(start_date, end_date)
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

    # Save Snapshot (draft)
    st.divider()
    st.subheader("Save Snapshot (draft)")
    note = st.text_input("Optional note", value="", help="Short reason or context")
    save_btn = st.button("Save snapshot (draft)", type="primary", use_container_width=True)

    if save_btn:
        try:
            cutoff = datetime.combine(end_date, time(23, 59, 59, 999999))
            # Upload parquet
            path = f"{end_date:%Y/%m/%d}/manual/{fname_base}.parquet"
            bytes_parq = as_parquet_bytes(filtered)
            if SB:
                SB.storage.from_(SBCFG.bucket).upload(path, bytes_parq, {"content-type": "application/octet-stream", "x-upsert": "true"})

            # Insert snapshot row (draft)
            kpis = compute_kpis_dynamic(filtered)
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


# ------------------------------------------------------------
# 7) GENERATE SUMMARY REPORTS (list snapshots + XmR)
# ------------------------------------------------------------
elif section == "Generate Summary Reports":
    st.header("Reports")
    if not SB:
        st.info("Supabase not configured.")
        st.stop()

    try:
        q = (
            SB.table("snapshots")
            .select("*")
            .eq("env", ENV)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        df_rep = pd.DataFrame(q.data)
        if df_rep.empty:
            st.info("No snapshots yet. Save a snapshot from View Results.")
        else:
            drafts_only = st.checkbox("Show drafts only", value=IS_NIGHTLY)
            show_cols = [
                "created_at",
                "created_by",
                "run_type",
                "is_draft",
                "period_start",
                "period_end",
                "scoring_version",
                "total_leads",
                "class1_count",
                "class1_pct",
                "class2_count",
                "class2_pct",
                "class3_count",
                "class3_pct",
                "class4_count" if "class4_count" in df_rep.columns else None,
                "class4_pct" if "class4_pct" in df_rep.columns else None,
                "parquet_path",
                "reason",
            ]
            show_cols = [c for c in show_cols if c and c in df_rep.columns]
            df_view = df_rep.copy()
            if drafts_only and "is_draft" in df_view.columns:
                df_view = df_view[df_view["is_draft"] == True]
            st.dataframe(df_view[show_cols], use_container_width=True)

            st.subheader("XmR — Class 1 %")
            render_xmr_class1(df_rep[df_rep["env"] == ENV], show_drafts_only=drafts_only)

            with st.expander("Open a snapshot"):
                opts = df_view.head(50).apply(
                    lambda r: f"{r.get('created_at','')} | {r.get('period_start','')}→{r.get('period_end','')} | "
                    f"{'DRAFT' if r.get('is_draft') else r.get('run_type','').upper()}",
                    axis=1,
                ).tolist()
                if opts:
                    idx = st.selectbox("Choose snapshot", options=opts, index=0)
                    i = opts.index(idx)
                    row = df_view.iloc[i]
                    path = row["parquet_path"]
                    st.write("Storage path:", path)
                    try:
                        file_bytes = SB.storage.from_(SBCFG.bucket).download(path)
                        # Try Parquet then CSV
                        try:
                            df_preview = pd.read_parquet(io.BytesIO(file_bytes))
                        except Exception:
                            df_preview = pd.read_csv(io.BytesIO(file_bytes))
                        st.caption(f"Preview: {len(df_preview)} rows (first 20)")
                        st.dataframe(df_preview.head(20), use_container_width=True)
                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button(
                                "Download snapshot file",
                                data=file_bytes,
                                file_name=os.path.basename(path),
                                mime="application/octet-stream",
                                use_container_width=True,
                            )
                        with c2:
                            st.download_button(
                                "Download as CSV (repacked)",
                                data=df_preview.to_csv(index=False).encode("utf-8"),
                                file_name=os.path.basename(path).replace(".parquet", ".csv"),
                                mime="text/csv",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error("Failed to open snapshot from storage (file missing?).")
                        st.exception(e)
    except Exception as e:
        st.error("Failed to load snapshots.")
        st.exception(e)


# ------------------------------------------------------------
# 8) ABOUT
# ------------------------------------------------------------
else:
    st.header("About")
    st.markdown(
        """
        **Lead Scoring App v3 (scaffold)**  
        - Nightly / Prod env guards  
        - Inclusive date filtering (full end-day)  
        - Robust datetime parsing  
        - Parquet/CSV export  
        - Snapshots (draft) with Supabase Storage + table  
        - XmR Class 1% with WECO/Nelson signals  
        \n
        **Notes**  
        - If the source purges older data (e.g., DreamClass before 2025‑07‑10), history must come from snapshots.  
        - Scheduled biweekly snapshots are recommended for consistency.  
        """
    )
