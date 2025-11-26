# utils/advanced_analytics.py

import pandas as pd
import numpy as np
from utils.supabase_client import supabase


# =====================================================
# 1. Load the canonical lead quality time-series
# =====================================================

def load_lead_quality_timeseries() -> pd.DataFrame:
    """
    Loads the aggregated lead quality metrics (1 row per period)
    from lead_quality_timeseries.
    """
    resp = (
        supabase.table("lead_quality_timeseries")
        .select(
            "period_start, period_end, total_leads, "
            "class_1_pct, class_2_pct, class_3_pct, class_4_pct"
        )
        .order("period_end")
        .execute()
    )

    rows = resp.data or []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["period_start"] = pd.to_datetime(df["period_start"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


# =====================================================
# 2. XmR ENGINE
# =====================================================

def compute_xmr(series: pd.Series) -> dict:
    """
    Computes XmR statistics for a 1D numeric series.
    Returns a dict with x, mr, mean, ucl, lcl, mr_bar, ucl_mr.
    """

    x = series.astype(float).values
    if len(x) < 2:
        raise ValueError("Need at least 2 points for XmR charts")

    # moving range
    mr = np.abs(np.diff(x))
    mr_bar = mr.mean()

    mean_x = x.mean()

    # Control limits (standard XmR)
    ucl_x = mean_x + 2.66 * mr_bar
    lcl_x = mean_x - 2.66 * mr_bar
    ucl_mr = 3.268 * mr_bar

    return {
        "x": x,
        "mr": mr,
        "mean": mean_x,
        "ucl": ucl_x,
        "lcl": lcl_x,
        "mr_bar": mr_bar,
        "ucl_mr": ucl_mr,
    }


# =====================================================
# 3. Interpretation helpers
# =====================================================

def _find_long_runs(x: np.ndarray, mean_x: float, run_length: int = 8):
    """
    Find runs of >= run_length consecutive points on the same side of the mean.
    Returns a list of (start_idx, end_idx, side) where side is +1 or -1.
    """
    # side: +1 above mean, -1 below mean, 0 exactly on mean
    side = np.sign(x - mean_x)

    runs = []
    current_side = 0
    start_idx = 0

    for i, s in enumerate(side):
        if s == 0:
            # break any ongoing run
            if current_side != 0 and (i - start_idx) >= run_length:
                runs.append((start_idx, i - 1, current_side))
            current_side = 0
            continue

        if s == current_side:
            # continuing the same run
            continue
        else:
            # side changed; close previous run if long enough
            if current_side != 0 and (i - start_idx) >= run_length:
                runs.append((start_idx, i - 1, current_side))
            # start new run
            current_side = s
            start_idx = i

    # close tail run
    if current_side != 0 and (len(side) - start_idx) >= run_length:
        runs.append((start_idx, len(side) - 1, current_side))

    return runs


def _has_short_run_near_limits(
    x: np.ndarray,
    mean_x: float,
    ucl_x: float,
    lcl_x: float,
    min_run: int = 3,
    max_run: int = 4,
):
    """
    Detects whether there is a run of 3–4 consecutive points that are
    closer to a control limit than to the mean.
    Returns (found: bool, start_idx: int | None, end_idx: int | None).
    """
    # distance to mean vs nearest limit
    dist_mean = np.abs(x - mean_x)
    dist_limit = np.minimum(np.abs(x - ucl_x), np.abs(x - lcl_x))

    near_limit = dist_limit < dist_mean  # True if closer to limit than mean

    run_start = None
    for i, is_near in enumerate(near_limit):
        if is_near:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                run_len = i - run_start
                if min_run <= run_len <= max_run:
                    return True, run_start, i - 1
                run_start = None

    # tail run
    if run_start is not None:
        run_len = len(near_limit) - run_start
        if min_run <= run_len <= max_run:
            return True, run_start, len(near_limit) - 1

    return False, None, None


# =====================================================
# 4. Interpretation / Narrative Builder
# =====================================================

def xmr_interpretation(dates: pd.Series, series: pd.Series, stats: dict) -> str:
    """
    Interpretation focused on three classic XmR checks:
      1) Special-cause outliers (points beyond limits)
      2) Long runs (>= 8 points on one side of mean)
      3) Short runs near limits (3–4 points closer to limit than mean)
    Plus a comment on the latest point.
    """

    x = stats["x"]
    mean_x = stats["mean"]
    ucl_x = stats["ucl"]
    lcl_x = stats["lcl"]

    latest = x[-1]
    latest_date = dates.iloc[-1].strftime("%Y-%m-%d")

    bullets = []

    # -------------------------------------------------
    # Latest point vs mean / limits
    # -------------------------------------------------
    if latest > ucl_x:
        bullets.append(
            f"- Latest value ({latest:.1f}) on {latest_date} is **above the upper control limit** "
            f"(mean {mean_x:.1f})."
        )
    elif latest < lcl_x:
        bullets.append(
            f"- Latest value ({latest:.1f}) on {latest_date} is **below the lower control limit** "
            f"(mean {mean_x:.1f})."
        )
    elif latest > mean_x:
        bullets.append(
            f"- Latest value ({latest:.1f}) on {latest_date} is **above** the long-term mean ({mean_x:.1f})."
        )
    elif latest < mean_x:
        bullets.append(
            f"- Latest value ({latest:.1f}) on {latest_date} is **below** the long-term mean ({mean_x:.1f})."
        )
    else:
        bullets.append(
            f"- Latest value ({latest:.1f}) on {latest_date} is exactly at the long-term mean."
        )

    # -------------------------------------------------
    # 1) Special-cause outliers
    # -------------------------------------------------
    mask_ooc = (x > ucl_x) | (x < lcl_x)
    num_ooc = int(mask_ooc.sum())

    if num_ooc == 0:
        bullets.append(
            "- No single-point outliers beyond control limits (no obvious special-cause spikes)."
        )
    else:
        first_ooc_idx = int(np.where(mask_ooc)[0][0])
        first_ooc_date = dates.iloc[first_ooc_idx].strftime("%Y-%m-%d")
        bullets.append(
            f"- {num_ooc} point(s) fall outside the control limits (special-cause events). "
            f"First occurred around {first_ooc_date} — worth investigating that period."
        )

    # -------------------------------------------------
    # 2) Long runs (shift in average)
    # -------------------------------------------------
    long_runs = _find_long_runs(x, mean_x, run_length=8)
    if not long_runs:
        bullets.append(
            "- No long run of 8+ points on one side of the mean "
            "(no clear sustained shift in average)."
        )
    else:
        # Report only the first run for brevity
        start_idx, end_idx, side = long_runs[0]
        side_str = "above" if side > 0 else "below"
        start_date = dates.iloc[start_idx].strftime("%Y-%m-%d")
        end_date = dates.iloc[end_idx].strftime("%Y-%m-%d")
        bullets.append(
            f"- Detected a long run of {end_idx - start_idx + 1} points {side_str} the mean "
            f"from {start_date} to {end_date} — this indicates a real shift in the process."
        )

    # -------------------------------------------------
    # 3) Short runs near limits (change in routine variation)
    # -------------------------------------------------
    has_short_run, sr_start, sr_end = _has_short_run_near_limits(
        x, mean_x, ucl_x, lcl_x, min_run=3, max_run=4
    )

    if not has_short_run:
        bullets.append(
            "- No 3–4 point run hugging a control limit "
            "(no clear change in routine variation around the limits)."
        )
    else:
        start_date = dates.iloc[sr_start].strftime("%Y-%m-%d")
        end_date = dates.iloc[sr_end].strftime("%Y-%m-%d")
        bullets.append(
            f"- Detected a run of {sr_end - sr_start + 1} points closer to the limits than the mean "
            f"between {start_date} and {end_date}, suggesting a change in routine variation."
        )

    return "\n".join(bullets)
