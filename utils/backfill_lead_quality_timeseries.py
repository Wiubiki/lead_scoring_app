import io
from typing import Dict, Any, List

import pandas as pd

from utils.supabase_client import supabase


BUCKET_NAME = "scoring-runs-nightly"


def get_existing_metrics_ids() -> set:
    """
    Return set of source_run_id values already present in lead_quality_timeseries
    so we don't double-insert on backfill.
    """
    resp = (
        supabase.table("lead_quality_timeseries")
        .select("source_run_id")
        .execute()
    )
    rows = resp.data or []
    return {r["source_run_id"] for r in rows if r.get("source_run_id")}


def fetch_scoring_runs() -> List[Dict[str, Any]]:
    """
    Fetch all scoring runs we want to backfill from.
    For now: all env='nightly'.
    """
    resp = (
        supabase.table("scoring_runs")
        .select(
            "id, env, period_start, period_end, file_key, lead_count, data_type"
        )
        .eq("env", "nightly")
        .order("period_start")
        .execute()
    )
    return resp.data or []


def load_summary_counts(file_key: str) -> Dict[int, int]:
    """
    Load a SUMMARY parquet and return per-class counts + total.

    Expected schema (confirmed):
      period_start
      period_end
      class_1_count
      class_2_count
      class_3_count
      class_4_count
      total_leads
      data_type
    """
    file_bytes = supabase.storage.from_(BUCKET_NAME).download(file_key)
    df = pd.read_parquet(io.BytesIO(file_bytes))

    if df.empty:
        return {"total": 0, 1: 0, 2: 0, 3: 0, 4: 0}

    row = df.iloc[0]

    def safe(col: str) -> int:
        return int(row[col]) if col in df.columns and pd.notna(row[col]) else 0

    return {
        "total": safe("total_leads"),
        1: safe("class_1_count"),
        2: safe("class_2_count"),
        3: safe("class_3_count"),
        4: safe("class_4_count"),
    }


def load_full_counts(file_key: str) -> Dict[int, int]:
    """
    Load a FULL parquet (row-level leads) and compute per-class counts + total.

    We normalise:
      - 'class' or 'score_class' -> 'lead_class' if needed.
    """
    file_bytes = supabase.storage.from_(BUCKET_NAME).download(file_key)
    df = pd.read_parquet(io.BytesIO(file_bytes))

    if "lead_class" not in df.columns:
        if "class" in df.columns:
            df = df.rename(columns={"class": "lead_class"})
        elif "score_class" in df.columns:
            df = df.rename(columns={"score_class": "lead_class"})

    if "lead_class" not in df.columns:
        # worst case: no class info; treat everything as unknown
        total = len(df)
        return {"total": total, 1: 0, 2: 0, 3: 0, 4: 0}

    vc = df["lead_class"].value_counts().to_dict()
    total = int(len(df))

    return {
        "total": total,
        1: int(vc.get(1, 0)),
        2: int(vc.get(2, 0)),
        3: int(vc.get(3, 0)),
        4: int(vc.get(4, 0)),
    }


def build_payload_for_run(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a lead_quality_timeseries row for a single scoring_runs record.
    Uses summary or full parquet depending on data_type.
    """
    run_id = run["id"]
    file_key = run.get("file_key")
    data_type = (run.get("data_type") or "").lower()

    if not file_key:
        raise ValueError(f"Run {run_id} has no file_key")

    if data_type == "summary":
        counts = load_summary_counts(file_key)
    elif data_type == "full":
        counts = load_full_counts(file_key)
    else:
        raise ValueError(f"Run {run_id} has unsupported data_type='{data_type}'")

    total = counts["total"] if counts["total"] is not None else 0
    c1 = int(counts.get(1, 0))
    c2 = int(counts.get(2, 0))
    c3 = int(counts.get(3, 0))
    c4 = int(counts.get(4, 0))

    def pct(n: int) -> float:
        return (n / total) if total else 0.0

    payload = {
        "source_run_id": run_id,
        "period_start": run["period_start"],
        "period_end": run["period_end"],
        "total_leads": total,
        "class_1_count": c1,
        "class_2_count": c2,
        "class_3_count": c3,
        "class_4_count": c4,
        "class_1_pct": pct(c1),
        "class_2_pct": pct(c2),
        "class_3_pct": pct(c3),
        "class_4_pct": pct(c4),
        "data_type": data_type,
    }

    return payload


def backfill():
    existing = get_existing_metrics_ids()
    runs = fetch_scoring_runs()

    print(f"Found {len(runs)} scoring_runs rows (env='nightly').")
    print(f"{len(existing)} already present in lead_quality_timeseries.")

    to_insert: List[Dict[str, Any]] = []

    for run in runs:
        run_id = run["id"]
        if run_id in existing:
            print(f"- Skipping run {run_id} ({run['period_start']} → {run['period_end']}) – already in metrics.")
            continue

        try:
            payload = build_payload_for_run(run)
            to_insert.append(payload)
            print(f"+ Prepared metrics for run {run_id} ({run['period_start']} → {run['period_end']}).")
        except Exception as e:
            print(f"! ERROR building metrics for run {run_id}: {e}")

    if not to_insert:
        print("Nothing to insert. Backfill complete.")
        return

    # Insert in one or a few batches to avoid huge payloads
    CHUNK = 50
    for i in range(0, len(to_insert), CHUNK):
        chunk = to_insert[i : i + CHUNK]
        resp = supabase.table("lead_quality_timeseries").insert(chunk).execute()
        if resp.data is None:
            print(f"! Insert chunk {i//CHUNK} returned no data; check Supabase logs.")
        else:
            print(f"Inserted {len(resp.data)} rows into lead_quality_timeseries.")


if __name__ == "__main__":
    backfill()
