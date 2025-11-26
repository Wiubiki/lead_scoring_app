import io
import datetime as dt
import streamlit as st
import pandas as pd
from supabase import create_client, Client

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_SERVICE_KEY = st.secrets["supabase"]["service_key"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# -------------------------------------------------------------------
# Save scoring run data to supabase and update scoring_runs 
# & lead_quality_timeseries tables
# -------------------------------------------------------------------

def save_scoring_run(
    scored_df: pd.DataFrame,
    period_start: dt.date,
    period_end: dt.date,
    env: str = "nightly",
    created_by: str = "admin_results_page",
) -> dict:
    """
    Saves a scoring run to Supabase:

    1. Uploads full parquet to storage
    2. Upserts a row into scoring_runs
    3. Inserts metrics into lead_quality_timeseries
    4. Returns the scoring_runs row
    """

    # -----------------------------
    # Normalize period
    # -----------------------------
    if isinstance(period_start, dt.datetime):
        period_start = period_start.date()
    if isinstance(period_end, dt.datetime):
        period_end = period_end.date()

    start_str = period_start.isoformat()
    end_str = period_end.isoformat()
    year_str = str(period_start.year)

    # -----------------------------
    # Build file_key
    # -----------------------------
    bucket_name = "scoring-runs-nightly"
    file_key = f"full/{year_str}/{start_str}__{end_str}.parquet"

    # -----------------------------
    # Clean the DataFrame
    # -----------------------------
    df_to_save = scored_df.copy()

    # coerce sign_up only if exists
    if "sign_up" in df_to_save.columns:
        df_to_save["sign_up"] = pd.to_numeric(df_to_save["sign_up"], errors="coerce")

    # serialize parquet
    buffer = io.BytesIO()
    df_to_save.to_parquet(buffer, index=False)
    buffer.seek(0)
    file_bytes = buffer.getvalue()

    # -----------------------------
    # Upload parquet to storage
    # -----------------------------
    supabase.storage.from_(bucket_name).upload(
        path=file_key,
        file=file_bytes,
        file_options={"upsert": "true"},
    )

    # -----------------------------
    # Upsert metadata row in scoring_runs (retrieve row)
    # -----------------------------
    payload = {
        "env": env,
        "data_type": "full",
        "period_start": start_str,
        "period_end": end_str,
        "file_key": file_key,
        "lead_count": int(len(scored_df)),
        "created_by": created_by,
        "notes": None,
    }

    resp = supabase.table("scoring_runs").upsert(
        payload,
        returning="representation"
    ).execute()

    if not resp.data:
        raise RuntimeError("Failed to insert scoring_runs row")

    run_row = resp.data[0]
    run_id = run_row["id"]

    # -----------------------------
    # Insert into lead_quality_timeseries
    # -----------------------------
    df_metrics = scored_df.copy()

    # normalize class column
    if "lead_class" not in df_metrics.columns:
        if "class" in df_metrics.columns:
            df_metrics = df_metrics.rename(columns={"class": "lead_class"})
        elif "score_class" in df_metrics.columns:
            df_metrics = df_metrics.rename(columns={"score_class": "lead_class"})

    if "lead_class" in df_metrics.columns:
        class_counts = df_metrics["lead_class"].value_counts().to_dict()
        total = int(len(df_metrics))

        c1 = int(class_counts.get(1, 0))
        c2 = int(class_counts.get(2, 0))
        c3 = int(class_counts.get(3, 0))
        c4 = int(class_counts.get(4, 0))

        def pct(n: int) -> float:
            return (n / total) if total else 0.0

        metrics_payload = {
            "source_run_id": run_id,
            "period_start": start_str,
            "period_end": end_str,
            "total_leads": total,
            "class_1_count": c1,
            "class_2_count": c2,
            "class_3_count": c3,
            "class_4_count": c4,
            "class_1_pct": pct(c1),
            "class_2_pct": pct(c2),
            "class_3_pct": pct(c3),
            "class_4_pct": pct(c4),
            "data_type": "full",
        }

        supabase.table("lead_quality_timeseries").insert(metrics_payload).execute()

    return run_row