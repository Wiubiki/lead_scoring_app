# ui/widgets/xmr_charts.py

import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st


D2_FOR_2 = 1.128  # constant used in XmR sigma estimate


def render_xmr_chart(
    title: str,
    dates: pd.Series,
    values: pd.Series,
    stats: dict | None = None,
    y_label: str = "Metric",
):
    """
    Render Individuals + Moving Range charts with XmR styling.

    We *do not* rely on the shape of `stats` here – we compute all
    needed XmR quantities (mean, MR, limits) from `values` directly,
    so this stays compatible with any compute_xmr implementation.
    """

    # Ensure proper numeric series
    values = pd.Series(values).astype(float)
    dates = pd.Series(dates)

    # Build base dataframe
    df = pd.DataFrame({"x": values.values}, index=dates)

    # --- Moving Range (MR) ---
    mr = values.diff().abs()
    mr.iloc[0] = np.nan
    df["mr"] = mr

    # --- XmR statistics (same formulas as standalone tool) ---
    mean_x = values.mean()
    mean_mr = mr[1:].mean()

    sigma = mean_mr / D2_FOR_2 if mean_mr and mean_mr > 0 else np.nan

    ucl_x = mean_x + 3 * sigma
    lcl_x = mean_x - 3 * sigma

    ucl_mr = mean_mr * 3.267 if mean_mr and mean_mr > 0 else np.nan
    lcl_mr = 0.0

    # ------------------------------------------------------
    # INDIVIDUALS (X) CHART
    # ------------------------------------------------------
    fig_x = go.Figure()

    # Midpoints between mean and limits
    mid_upper = (mean_x + ucl_x) / 2 if pd.notna(ucl_x) else np.nan
    mid_lower = (mean_x + lcl_x) / 2 if pd.notna(lcl_x) else np.nan

    x_min, x_max = df.index.min(), df.index.max()

    # Shaded zones between midpoints and limits (soft yellow)
    if pd.notna(mid_upper) and pd.notna(ucl_x):
        fig_x.add_shape(
            type="rect",
            x0=x_min,
            x1=x_max,
            y0=mid_upper,
            y1=ucl_x,
            fillcolor="rgba(255, 215, 0, 0.12)",
            line_width=0,
            layer="below",
        )

    if pd.notna(mid_lower) and pd.notna(lcl_x):
        fig_x.add_shape(
            type="rect",
            x0=x_min,
            x1=x_max,
            y0=lcl_x,
            y1=mid_lower,
            fillcolor="rgba(255, 215, 0, 0.12)",
            line_width=0,
            layer="below",
        )

    # Color-code each point
    colors = []
    for v in df["x"]:
        if pd.isna(v) or pd.isna(ucl_x) or pd.isna(lcl_x):
            colors.append("lightgray")
        elif v > ucl_x or v < lcl_x:
            colors.append("red")          # outlier
        elif (pd.notna(mid_upper) and v >= mid_upper) or (
            pd.notna(mid_lower) and v <= mid_lower
        ):
            colors.append("gold")         # near-limit / hugging
        else:
            colors.append("dodgerblue")   # normal

    # Add X trace
    fig_x.add_trace(
        go.Scatter(
            x=df.index,
            y=df["x"],
            mode="lines+markers",
            name=y_label,
            marker=dict(color=colors, size=8),
            line=dict(color="gray"),
            hovertemplate="%{x}<br>%{y:.3f}<extra></extra>",
        )
    )

    # Reference lines: mean, UCL, LCL, midpoints
    if pd.notna(mean_x):
        fig_x.add_hline(
            y=mean_x,
            line_dash="dash",
            annotation_text="Mean",
        )
    if pd.notna(ucl_x):
        fig_x.add_hline(
            y=ucl_x,
            line_dash="dot",
            annotation_text="UCL",
        )
    if pd.notna(lcl_x):
        fig_x.add_hline(
            y=lcl_x,
            line_dash="dot",
            annotation_text="LCL",
        )
    if pd.notna(mid_upper):
        fig_x.add_hline(
            y=mid_upper,
            line_dash="dot",
            line_color="darkgray",
            opacity=0.5,
            annotation_text="midpoint_upper",
        )
    if pd.notna(mid_lower):
        fig_x.add_hline(
            y=mid_lower,
            line_dash="dot",
            line_color="darkgray",
            opacity=0.5,
            annotation_text="midpoint_lower",
        )

    fig_x.update_layout(
        title="X Chart",
        xaxis_title="Observation",
        yaxis_title=y_label,
        hovermode="x unified",
    )

    # ------------------------------------------------------
    # MOVING RANGE (MR) CHART
    # ------------------------------------------------------
    fig_mr = go.Figure()

    mr_mid = (mean_mr + ucl_mr) / 2 if pd.notna(ucl_mr) else np.nan

    if pd.notna(mr_mid) and pd.notna(ucl_mr):
        fig_mr.add_shape(
            type="rect",
            x0=x_min,
            x1=x_max,
            y0=mr_mid,
            y1=ucl_mr,
            fillcolor="rgba(255, 215, 0, 0.12)",
            line_width=0,
            layer="below",
        )

    # Color-code MR points
    mr_colors = []
    for v in df["mr"]:
        if pd.isna(v) or pd.isna(ucl_mr):
            mr_colors.append("lightgray")
        elif v > ucl_mr:
            mr_colors.append("red")
        elif pd.notna(mr_mid) and v >= mr_mid:
            mr_colors.append("gold")
        else:
            mr_colors.append("dodgerblue")

    fig_mr.add_trace(
        go.Scatter(
            x=df.index,
            y=df["mr"],
            mode="lines+markers",
            name="MR",
            marker=dict(color=mr_colors, size=8),
            line=dict(color="gray"),
            hovertemplate="%{x}<br>MR=%{y:.3f}<extra></extra>",
        )
    )

    if pd.notna(mean_mr):
        fig_mr.add_hline(
            y=mean_mr,
            line_dash="dash",
            annotation_text="MR Mean",
        )
    if pd.notna(ucl_mr):
        fig_mr.add_hline(
            y=ucl_mr,
            line_dash="dot",
            annotation_text="UCL",
        )
    fig_mr.add_hline(
        y=lcl_mr,
        line_dash="dot",
        annotation_text="LCL",
    )
    if pd.notna(mr_mid):
        fig_mr.add_hline(
            y=mr_mid,
            line_dash="dot",
            line_color="darkgray",
            opacity=0.5,
            annotation_text="midpoint",
        )

    fig_mr.update_layout(
        title="Moving Range (mR) Chart",
        xaxis_title="Observation",
        yaxis_title="Moving Range",
        hovermode="x unified",
    )

    # ------------------------------------------------------
    # RENDER BOTH
    # ------------------------------------------------------
    st.plotly_chart(fig_x, use_container_width=True)
    st.plotly_chart(fig_mr, use_container_width=True)
