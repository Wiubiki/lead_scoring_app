import streamlit as st
import pandas as pd
import io
import os, secrets
import numpy as np
import altair as alt
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
from lead_scoring_tool import apply_lead_scoring
from generate_summary_reports import generate_summary
from ga_data_retrieval import fetch_ga_data
from dreamclass_data_handler import fetch_dreamclass_data 
from dreamclass_data_handler import clean_dreamclass_data
from auth_library import authenticate
from datetime import datetime, time
from math import isnan


# Enviromental flags & guards
APP = st.secrets.get("app", {})
ENV = APP.get("env", "prod")
IS_NIGHTLY = ENV == "nightly"
ALLOW_PUBLISH = APP.get("allow_publish", ENV == "prod")

if IS_NIGHTLY:
    st.sidebar.caption("🧪 NIGHTLY — not for official KPIs")
    # Belt-and-suspenders:
    assert not ALLOW_PUBLISH, "Nightly must not allow publishing"


# ---- Supabase connection check ----
import streamlit as st

try:
    from supabase import create_client
except Exception:
    st.sidebar.error("Supabase client not installed. Add 'supabase' to requirements.txt.")
    st.stop()

def get_supabase():
    cfg = st.secrets.get("supabase", {})
    url, key = cfg.get("url"), cfg.get("service_key")
    if not url or not key:
        return None
    return create_client(url, key)

SB = get_supabase()
cfg = st.secrets.get("supabase", {})
BUCKET = cfg.get("bucket", "snapshots-nightly")  # keep default or set in secrets

if SB:
    try:
        buckets = SB.storage.list_buckets()
        # works for dicts or objects depending on client version
        names = [b.get("name") if isinstance(b, dict) else getattr(b, "name", None) for b in buckets]

        # connection ping
        st.sidebar.success(f"Supabase connected ({len(buckets)} buckets)")

        # bucket presence check
        if BUCKET in names:
            st.sidebar.success(f"Bucket '{BUCKET}' ready")
        else:
            st.sidebar.warning(f"Bucket '{BUCKET}' missing (expected '{BUCKET}')")
    except Exception as e:
        st.sidebar.error("Supabase connection failed")
        st.exception(e)
else:
    st.sidebar.warning("Supabase not configured")
# -----------------------------------------------------------------------


# ---- downloads helpers ----

def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make all columns Arrow-friendly:
    - Dict/List/Tuple/Set -> JSON string
    - Mixed-type object columns -> string
    - Force some known text columns to string
    - Datetime -> UTC-aware
    """
    out = df.copy()

    # Convert nested python objects to JSON strings
    def _to_json_if_nested(v):
        if isinstance(v, (dict, list, tuple, set)):
            try:
                return json.dumps(v, ensure_ascii=False, default=str)
            except Exception:
                return str(v)
        return v

    for col in out.columns:
        s = out[col]

        # Datetime handling
        if pd.api.types.is_datetime64_any_dtype(s):
            out[col] = pd.to_datetime(s, utc=True)
            continue

        # Object columns: check for nested or mixed types
        if s.dtype == "object":
            if s.map(lambda x: isinstance(x, (dict, list, tuple, set))).any():
                out[col] = s.map(_to_json_if_nested).astype("string")
            else:
                # If multiple non-null python types appear, coerce to string
                types = s.map(lambda x: type(x).__name__ if pd.notna(x) else "NA").unique().tolist()
                non_na_types = [t for t in types if t != "NA"]
                if len(non_na_types) > 1:
                    out[col] = s.astype("string")

    # Force some known textual columns to string (adjust as needed)
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
# ---------------------------



# Authenticate logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

st.sidebar.header("Login")

if not st.session_state["authenticated"]:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    login_button = st.sidebar.button("Login")

    if login_button:
        if authenticate(username, password):
            st.success("Login successful!")
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid username or password.")

if st.session_state["authenticated"]:


    st.title("Lead Scoring Tool")

    # Sidebar Navigation
    st.sidebar.header("Navigation")
    section = st.sidebar.selectbox(
        "Choose a section:",
        ["Retrieve Data", "Run Scoring", "View Results", "Generate Summary Reports"]
    )

    # Placeholder data variables
    dreamclass_data = None
    ga_data = None
    scored_data = None
    if "dreamclass_data" not in st.session_state:
        st.session_state["dreamclass_data"] = None

    # Retrieve Data Section with Date Range Picker
    if section == "Retrieve Data":
        st.header("Retrieve Data")
    
        # Date Range Picker
        st.subheader("Pick a Date Range (Mandatory)")
    
        # Initialize the default date range (e.g., for the last year)
        today = pd.Timestamp.now()
        default_start = today - pd.Timedelta(days=14)
        default_end = today
    
        # Let users pick a date range
        user_date_range = st.date_input(
            "Pick a date range",
            [default_start.date(), default_end.date()],
            min_value=pd.Timestamp("2023-01-01").date(),  # Adjust as needed
            max_value=today.date(),
        )
    
        # Validate user input
        if isinstance(user_date_range, (list, tuple)) and len(user_date_range) == 2:
            user_start_date, user_end_date = user_date_range
            if user_start_date and user_end_date:  # Ensure both dates are selected
                start_date = pd.Timestamp(user_start_date).strftime("%Y-%m-%d")
                end_date = pd.Timestamp(user_end_date).strftime("%Y-%m-%d")
                st.session_state["date_min"] = start_date
                st.session_state["date_max"] = end_date
                st.success(f"Date Range Selected: {start_date} to {end_date}")
            else:
                st.error("Please select both start and end dates to proceed.")
                st.stop()
        else:
            st.error("Please select a valid date range to proceed.")
            st.stop()
        
    
        # Display the selected date range
        st.write(f"Selected Date Range: {st.session_state['date_min']} to {st.session_state['date_max']}")
    
        # DreamClass Data Retrieval
        st.subheader("DreamClass Data Retrieval")
        
        # Status selection for DreamClass retrieval
        default_statuses = ["trial", "trial_expired", "active", "canceled"]
        selected_statuses = st.multiselect(
            "Select statuses to retrieve:",
            options=default_statuses,
            default=default_statuses  # Pre-select all statuses
        )
        
        if not selected_statuses:
            st.error("Please select at least one status to retrieve data.")
            st.stop()
        
        # --- Fetch and Clean DreamClass Data (simple + windowed view) ---
        if st.button("Fetch DreamClass Data", type="primary", use_container_width=True):
            try:
                # 1) Fetch raw
                raw_dreamclass_data = fetch_dreamclass_data(
                    st.secrets["dreamclass_api"]["base_url"],
                    selected_statuses,
                )

                # 2) Clean (keeps createdAt as datetime; no stringifying)
                dreamclass_data = clean_dreamclass_data(raw_dreamclass_data)

                # Ensure createdAt is datetime & naive
                if "createdAt" in dreamclass_data.columns and not pd.api.types.is_datetime64_any_dtype(dreamclass_data["createdAt"]):
                    dreamclass_data["createdAt"] = pd.to_datetime(dreamclass_data["createdAt"], errors="coerce")
                if "createdAt" in dreamclass_data.columns:
                    try:
                        dreamclass_data["createdAt"] = dreamclass_data["createdAt"].dt.tz_localize(None)
                    except Exception:
                        pass

                # Save full dataset (pipeline may need it)
                st.session_state["dreamclass_data"] = dreamclass_data

                # 3) Show only rows in the selected date window
                rp_start = pd.to_datetime(st.session_state.get("date_min")).date() if st.session_state.get("date_min") else None
                rp_end   = pd.to_datetime(st.session_state.get("date_max")).date() if st.session_state.get("date_max") else None

                # Fallback to data bounds if picker values missing
                if not (rp_start and rp_end):
                    dmin = dreamclass_data["createdAt"].min()
                    dmax = dreamclass_data["createdAt"].max()
                    rp_start = (dmin.date() if pd.notna(dmin) else pd.Timestamp.today().date())
                    rp_end   = (dmax.date() if pd.notna(dmax) else pd.Timestamp.today().date())

                mask = (dreamclass_data["createdAt"].dt.date >= rp_start) & (dreamclass_data["createdAt"].dt.date <= rp_end)
                in_window = dreamclass_data.loc[mask].copy()
                st.session_state["dreamclass_data_in_window"] = in_window

                total = len(dreamclass_data)
                n_win = len(in_window)
                win_min = in_window["createdAt"].min() if n_win else None
                win_max = in_window["createdAt"].max() if n_win else None

                st.success(
                    f"DreamClass data retrieved ✓  Total rows: {total:,}  |  "
                    f"In selected period ({rp_start} → {rp_end}): {n_win:,} "
                    + (f"({win_min} → {win_max})" if n_win else "(no rows in this window)")
                )

                # One simple table (cap for speed)
                st.dataframe(in_window.head(1000), use_container_width=True)

                # Remember intended window for later pages
                st.session_state["run_period_start"] = rp_start
                st.session_state["run_period_end"]   = rp_end

            except Exception as e:
                st.error("Failed to retrieve or clean DreamClass data.")
                st.exception(e)
        # --- end Fetch and Clean DreamClass Data ---


        
    
        # Fetch Google Analytics Data
        st.subheader("Google Analytics Data Retrieval")
        if st.button("Fetch Google Analytics Data"):
            try:
                ga_data = fetch_ga_data(start_date, end_date)
                ga_data = ga_data.rename(columns={
                    'firstUserCampaignName': 'First user campaign',
                    'firstUserSourceMedium': 'First user source / medium',
                    'customUser:icpGroup': 'icp_group',
                    'customUser:schoolType': 'school_type',
                    'customUser:userId': 'userId',
                    'firstUserGoogleAdsAdGroupName': 'Google Ads Ad Group'
                })
                st.session_state["ga_data"] = ga_data
                st.success("Google Analytics data retrieved and processed successfully!")
                st.dataframe(ga_data)
            except Exception as e:
                st.error(f"Failed to fetch GA data: {e}")

    # Run Scoring Section
    if section == "Run Scoring":
        st.header("Run Lead Scoring")
    
        # Check if data is in session state
        if "dreamclass_data" in st.session_state and "ga_data" in st.session_state:
            dreamclass_data = st.session_state["dreamclass_data"]
            ga_data = st.session_state["ga_data"]
    
            # Convert createdAt to datetime for filtering
            dreamclass_data["createdAt"] = pd.to_datetime(dreamclass_data["createdAt"], format="%Y-%m-%d", errors="coerce")
    
            # Filter DreamClass data within the selected date range
            filtered_dreamclass_data = dreamclass_data[
                (pd.to_datetime(dreamclass_data["createdAt"]) >= pd.to_datetime(st.session_state["date_min"])) &
                (pd.to_datetime(dreamclass_data["createdAt"]) <= pd.to_datetime(st.session_state["date_max"]))
            ]
            
            # Perform lead scoring on filtered data
            scored_data = apply_lead_scoring(filtered_dreamclass_data, ga_data)
            st.session_state["scored_data"] = scored_data  # Store scored data in session state
            st.success("Lead scoring completed!")
            st.write("Scored Leads Sample", scored_data.head())
        else:
            st.info("Please upload data files first in the 'Retrieve Data' section.")
            

    
    # View Results section

    elif section == "View Results":
        st.header("View Scoring Results")

        # Check if scored data is available in session state
        if "scored_data" in st.session_state:
            scored_data = st.session_state["scored_data"]

            # Convert `createdAt` to datetime if it isn't already
            scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], format="%d/%m/%Y", errors="coerce")


            # Filtering options
            st.subheader("Filter Results")

            # Date Range Filter
            date_min = scored_data["createdAt"].min()
            date_max = scored_data["createdAt"].max()
            start_date, end_date = st.date_input(
                "Select Date Range",
                [date_min, date_max],
                min_value=date_min,
                max_value=date_max
            )

            # Convert selected dates to datetime format to match `createdAt`
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            # Filter by Date Range
            filtered_data = scored_data[(scored_data["createdAt"] >= start_date) & (scored_data["createdAt"] <= end_date)]

            # Lead Class and Score Filters
            lead_class_filter = st.multiselect("Select Lead Class", options=sorted(filtered_data["lead_class"].unique()), default=sorted(filtered_data["lead_class"].unique()))
            min_score, max_score = st.slider("Total Score Range", min_value=float(filtered_data["total_score"].min()), max_value=float(filtered_data["total_score"].max()), value=(float(filtered_data["total_score"].min()), float(filtered_data["total_score"].max())))

            # Apply Lead Class and Score Filters
            filtered_data = filtered_data[
                (filtered_data["lead_class"].isin(lead_class_filter)) &
                (filtered_data["total_score"] >= min_score) &
                (filtered_data["total_score"] <= max_score)
            ]

            # Sorting options
            st.subheader("Sort Results")
            sort_by = st.selectbox("Sort by", ["Total Score", "Lead Class"])
            ascending = st.radio("Order", ["Ascending", "Descending"]) == "Ascending"

            # Sort the data
            if sort_by == "Total Score":
                filtered_data = filtered_data.sort_values(by="total_score", ascending=ascending)
            elif sort_by == "Lead Class":
                filtered_data = filtered_data.sort_values(by="lead_class", ascending=ascending)

            # Display filtered and sorted data
            st.write("Filtered and Sorted Results", filtered_data)

            # Calculate lead class distribution
            lead_class_counts = filtered_data["lead_class"].value_counts()

            # Sort lead_class_counts by index to ensure proper order (Class 1, Class 2, etc.)
            lead_class_counts = lead_class_counts.sort_index()

            # Calculate percentages based on the sorted lead_class_counts
            lead_class_percentages = lead_class_counts / lead_class_counts.sum() * 100

            # Pie Chart Visualization
            st.subheader("Lead Class Distribution")

            # Function to format the autopct text
            def autopct_format(pct, all_values):
                absolute = int(round(pct / 100. * sum(all_values)))
                return f"{pct:.1f}%\n({absolute})"  # Show percentage and count

            # Generate Pie Chart
            fig, ax = plt.subplots()
            ax.pie(
                lead_class_percentages,
                labels=[f"Class {int(cls)}" for cls in lead_class_counts.index],  # Ensure labels match sorted order
                autopct=lambda pct: autopct_format(pct, lead_class_counts),  # Custom formatting
                startangle=90,  # Starting angle for the first pie slice
                counterclock=False,  # Clockwise sorting
                colors=plt.cm.Paired.colors[:len(lead_class_counts)]  # Ensure enough colors for all slices
            )
            ax.set_title(f"Lead Class Distribution (Total Leads: {len(filtered_data)})")
            ax.axis("equal")  # Equal aspect ratio ensures the pie chart is a circle

            # Display pie chart in Streamlit
            st.pyplot(fig)

            # --- Downloads (filtered_data) ---
            from datetime import date

            try:
                fname_base = f"scored_{start_date.date()}_{end_date.date()}"
            except Exception:
                fname_base = f"scored_{date.today().isoformat()}"

            left, right = st.columns(2)
            with left:
                if IS_NIGHTLY:
                    st.download_button(
                        label="Download filtered results (.parquet)",
                        data=as_parquet_bytes(filtered_data),
                        file_name=f"{fname_base}.parquet",
                        mime="application/octet-stream",
                        use_container_width=True,
                    )
            with right:
                st.download_button(
                    label="Download filtered results (.csv)",
                    data=as_csv_bytes(filtered_data),
                    file_name=f"{fname_base}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            # -------------------------------


            # Save data snashot to supabase
            try:
                from zoneinfo import ZoneInfo  # py3.9+
            except Exception:
                from backports.zoneinfo import ZoneInfo

            # --- helpers for KPIs + path ---
            def compute_kpis(df: pd.DataFrame):
                total = int(len(df))
                def cnt(c):
                    return int(df.loc[df["lead_class"] == c].shape[0]) if "lead_class" in df.columns else 0
                def pct(n):
                    return round(100.0 * n / total, 2) if total else 0.0
                c1 = cnt(1); c2 = cnt(2); c3 = cnt(3)
                return dict(
                    total_leads=total,
                    class1_count=c1, class1_pct=pct(c1),
                    class2_count=c2, class2_pct=pct(c2),
                    class3_count=c3, class3_pct=pct(c3),
                )

            def make_parquet_path(period_end: datetime.date, run_type: str, fname_hint: str = ""):
                run_id = secrets.token_hex(8)
                base = f"{period_end:%Y/%m/%d}/{run_type}/{run_id}"
                if fname_hint:
                    return f"{base}_{fname_hint}.parquet"
                return f"{base}.parquet"

            # --- UI: Save Snapshot (draft) ---
            st.divider()
            st.subheader("Save Snapshot (draft)")

            left_action, right_action = st.columns([1,1])
            with left_action:
                save_btn = st.button("Save snapshot (draft)", type="primary", use_container_width=True)
            with right_action:
                note = st.text_input("Optional note", value="", help="Short reason or context")

            if save_btn:
                try:
                    # 1) Derive period & cutoff
                    tz = st.secrets.get("app", {}).get("timezone", "Europe/Athens")
                    cutoff = datetime.combine(end_date, time(23,59,59)).replace(tzinfo=ZoneInfo(tz))

                    # 2) Upload Parquet to Supabase Storage
                    cfg = st.secrets["supabase"]
                    bucket = cfg.get("bucket", "snapshots-nightly")
                    # use a readable hint in filename (optional)
                    fname_hint = f"{start_date}_{end_date}"
                    path = make_parquet_path(end_date, run_type="manual", fname_hint=fname_hint)
                    bytes_parquet = as_parquet_bytes(filtered_data)
                    SB.storage.from_(bucket).upload(path, bytes_parquet, {
                        "content-type": "application/octet-stream",
                        "x-upsert": "true"
                    })

                    # 3) Compute KPIs
                    kpis = compute_kpis(filtered_data)

                    # 4) Insert row in snapshots as DRAFT
                    app_env = st.secrets["app"]["env"]
                    scoring_version = st.secrets.get("app", {}).get("scoring_version", "3.0.0")
                    created_by = "aristeidis"  # set your display name/email as you prefer

                    row = {
                        "created_by": created_by,
                        "run_type": "manual",
                        "is_draft": True,
                        "period_start": str(start_date),
                        "period_end": str(end_date),
                        "observation_cutoff": cutoff.isoformat(),
                        "scoring_version": scoring_version,
                        "env": app_env,
                        "reason": (note or None),
                        "parquet_path": path,
                        **kpis
                    }
                    SB.table("snapshots").insert(row).execute()
                    st.toast("Snapshot saved (draft). Check Reports.", icon="✅")
                except Exception as e:
                    st.error("Failed to save snapshot (draft).")
                    st.exception(e)
                #-----------------------------------------------------------------
        else:
            st.info("Run lead scoring to view results.")




            
    # Generate Summary Reports Section

    elif section == "Generate Summary Reports":
        st.header("Generate Summary Reports")

        # Check if scored data is available in session state
        if "scored_data" in st.session_state:
            scored_data = st.session_state["scored_data"]

            # Convert `createdAt` to datetime if not already
            if scored_data["createdAt"].dtype != "datetime64[ns]":
                scored_data["createdAt"] = pd.to_datetime(scored_data["createdAt"], format="%d/%m/%Y", errors="coerce")

            # Controls Section
            st.subheader("Controls")

            # Date Range Selection
            date_min = scored_data["createdAt"].min()
            date_max = scored_data["createdAt"].max()
            start_date, end_date = st.date_input(
                "Select Date Range",
                [date_min, date_max],
                min_value=date_min,
                max_value=date_max
            )

            # Ensure selected dates are in datetime format
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            if start_date > end_date:
                st.error("Start date cannot be after end date.")

            # Dimension Mapping for human-readable dimensions
            dimension_mapping = {
                "Source/Medium": "First user source / medium",
                "Campaign": "First user campaign"
            }

            # Dimension Selection
            st.write("**Choose dimensions for grouping:**")
            selected_dimensions = st.multiselect(
                "Select dimensions to group by",
                options=list(dimension_mapping.keys()),  # Dropdown labels
                default=['Source/Medium']  # Default selection
            )

            # Map selected options to dataset column names
            selected_columns = [dimension_mapping[dim] for dim in selected_dimensions if dim in dimension_mapping]

            if not selected_columns:
                st.warning("Please select at least one dimension for grouping.")

            # Button to generate the report
            if st.button("Generate Report"):
                if not start_date or not end_date:
                    st.error("Please specify both start and end dates.")
                elif not selected_columns:
                    st.error("Please select at least one grouping dimension.")
                else:
                    # Generate the report
                    try:
                        summary = generate_summary(scored_data, start_date, end_date, selected_columns)

                        # Display the report
                        st.subheader("Summary Report")
                        st.dataframe(summary)

                        # Download option
                        st.download_button(
                            label="Download Report",
                            data=summary.to_csv(index=False).encode("utf-8"),
                            file_name=f"summary_report_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"An error occurred: {e}")

            # View snapshot reports
            st.subheader("Saved snapshots")

            try:
                # fetch latest snapshots for this environment
                q = (
                    SB.table("snapshots")
                    .select("*")
                    .eq("env", st.secrets["app"]["env"])  # "nightly" or "prod"
                    .order("created_at", desc=True)
                    .limit(200)
                    .execute()
                )
                df_rep = pd.DataFrame(q.data)

                if df_rep.empty:
                    st.info("No snapshots yet. Save a snapshot from View Results.")
                else:
                    # Optional: show only drafts in nightly
                    show_drafts_only = st.checkbox("Show drafts only", value=True if IS_NIGHTLY else False)
                    if show_drafts_only:
                        df_rep = df_rep[df_rep["is_draft"] == True]

                    # nice, compact set of columns to display
                    cols = [
                        "created_at","created_by","run_type","is_draft",
                        "period_start","period_end","scoring_version",
                        "total_leads","class1_count","class1_pct",
                        "class2_count","class2_pct","class3_count","class3_pct",
                        "parquet_path","reason"
                    ]
                    cols = [c for c in cols if c in df_rep.columns]
                    st.dataframe(df_rep[cols], use_container_width=True)

                    # (optional) select one snapshot to preview / download
                    with st.expander("Open a snapshot"):
                        # pick from most recent 50 for convenience
                        options = df_rep.head(50).apply(
                            lambda r: f"{r['created_at']} | {r['period_start']}→{r['period_end']} | {'DRAFT' if r['is_draft'] else r['run_type'].upper()}",
                            axis=1
                        ).tolist()
                        idx = st.selectbox("Choose snapshot", options=options, index=0)
                        row = df_rep.iloc[options.index(idx)]
                        st.write("Storage path:", row["parquet_path"])

                        # preview top rows (Parquet or CSV) using the storage API
                        try:
                            path = row["parquet_path"]
                            bucket = st.secrets["supabase"].get("bucket","snapshots-nightly")
                            # download file bytes from storage
                            file_bytes = SB.storage.from_(bucket).download(path)
                            # try parquet, fall back to csv
                            import io, pandas as pd
                            try:
                                import pyarrow.parquet as pq
                                df_preview = pd.read_parquet(io.BytesIO(file_bytes))
                            except Exception:
                                df_preview = pd.read_csv(io.BytesIO(file_bytes))
                            st.caption(f"Preview: {len(df_preview)} rows (showing first 20)")
                            st.dataframe(df_preview.head(20), use_container_width=True)

                            # quick download buttons (re-serve bytes)
                            c1, c2 = st.columns(2)
                            with c1:
                                st.download_button(
                                    "Download snapshot file",
                                    data=file_bytes,
                                    file_name=path.split("/")[-1],
                                    mime="application/octet-stream",
                                    use_container_width=True,
                                )
                            with c2:
                                # also offer CSV on the fly (small previews only—ok for testing)
                                st.download_button(
                                    "Download as CSV (repacked)",
                                    data=df_preview.to_csv(index=False).encode("utf-8"),
                                    file_name=path.split("/")[-1].replace(".parquet",".csv"),
                                    mime="text/csv",
                                    use_container_width=True,
                                )
                        except Exception as e:
                            st.error("Failed to open snapshot from storage.")
                            st.exception(e)

            except Exception as e:
                st.error("Failed to load snapshots list.")
                st.exception(e)
            # --- end Snapshots (nightly) ---

            # ---- XmR for class1_pct ----
           
            st.subheader("XmR: Class 1 % over time")

            # Use the same df_rep you already built from SB.table("snapshots")
            df_xmr = df_rep.copy()

            # Filter to current env (already done), let user choose drafts vs all
            only_drafts = st.checkbox("Show drafts only (nightly)", value=IS_NIGHTLY)
            if only_drafts and "is_draft" in df_xmr.columns:
                df_xmr = df_xmr[df_xmr["is_draft"] == True]

            # Require required cols
            required = {"period_end", "class1_pct"}
            if df_xmr.empty or not required.issubset(df_xmr.columns):
                st.info("No snapshots with class1_pct found.")
            else:
                # Sort by period_end, coerce to date
                df_xmr["period_end"] = pd.to_datetime(df_xmr["period_end"]).dt.date
                df_xmr = df_xmr.sort_values("period_end").reset_index(drop=True)

                # Build a tidy series
                x = pd.to_numeric(df_xmr["class1_pct"], errors="coerce").astype(float)
                idx = df_xmr["period_end"].astype(str)

                # Moving range (skip first NaN)
                mr = x.diff().abs()
                mr_bar = mr[1:].mean() if len(mr) > 1 else np.nan
                d2 = 1.128
                sigma = (mr_bar / d2) if (mr_bar is not None and not isnan(mr_bar)) else 0.0

                x_bar = x.mean() if len(x) else 0.0
                ucl_x = max(0.0, min(100.0, x_bar + 3*sigma))
                lcl_x = max(0.0, min(100.0, x_bar - 3*sigma))
                ucl_mr = 3.267 * mr_bar if mr_bar == mr_bar else np.nan  # keep NaN if mr_bar NaN
                lcl_mr = 0.0

                plot_df = pd.DataFrame({
                    "period_end": idx,
                    "class1_pct": x,
                    "mr": mr
                })

                # X chart
                base_x = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
                line_x = base_x.mark_line().encode(y=alt.Y("class1_pct:Q", title="Class 1 %"))
                pts_x  = base_x.mark_circle(size=60).encode(
                    y="class1_pct:Q",
                    tooltip=[
                        alt.Tooltip("period_end:N", title="Period end"),
                        alt.Tooltip("class1_pct:Q", title="Class1 %", format=".2f")
                    ]
                )
                rules_x = alt.Chart(pd.DataFrame({
                    "y": [x_bar, ucl_x, lcl_x],
                    "label": ["CL", "UCL", "LCL"]
                })).mark_rule(strokeDash=[6,3]).encode(y="y:Q").properties(height=220)

                labels_x = alt.Chart(pd.DataFrame({
                    "y": [x_bar, ucl_x, lcl_x],
                    "text": [f"CL {x_bar:.2f}", f"UCL {ucl_x:.2f}", f"LCL {lcl_x:.2f}"]
                })).mark_text(align="left", dx=5, dy=-5).encode(y="y:Q", text="text:N")

                x_chart = (line_x + pts_x + rules_x + labels_x).properties(title="Individuals (Class 1 %)")

                # mR chart
                base_mr = alt.Chart(plot_df).encode(x=alt.X("period_end:N", title="Period end", sort=None))
                bar_mr  = base_mr.mark_bar().encode(y=alt.Y("mr:Q", title="Moving range"))
                rules_mr = alt.Chart(pd.DataFrame({"y": [mr_bar, ucl_mr, lcl_mr],
                                                "label": ["CL(mR)", "UCL(mR)", "LCL(mR)"]})
                        ).mark_rule(strokeDash=[6,3]).encode(y="y:Q").properties(height=140)
                labels_mr = alt.Chart(pd.DataFrame({"y": [mr_bar, ucl_mr, lcl_mr],
                                                    "text": [f"CL {mr_bar:.2f}" if mr_bar==mr_bar else "CL -",
                                                            f"UCL {ucl_mr:.2f}" if ucl_mr==ucl_mr else "UCL -",
                                                            "LCL 0.00"]})
                        ).mark_text(align="left", dx=5, dy=-5).encode(y="y:Q", text="text:N")

                st.altair_chart(alt.vconcat(x_chart, (bar_mr + rules_mr + labels_mr)).resolve_scale(y='independent'), use_container_width=True)

                # Tiny legend of what to look for
                with st.expander("How to read this"):
                    st.write(
                        "- Points outside UCL/LCL suggest **special-cause** variation.\n"
                        "- Runs/shifts (e.g., 8 points on one side of CL) can also signal changes; we can add rules later.\n"
                        "- mR spikes suggest periods where the process changed sharply from the prior point."
                    )
            # ---- end XmR ----




        else:
            st.info("Run lead scoring to generate summary reports.")
else:
    st.warning("Please log in to access the app.")
