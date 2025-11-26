# ui/widgets/xmr_charts.py

import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd


def render_xmr_chart(title: str, dates: pd.Series, series: pd.Series, stats: dict):
    x = stats["x"]
    mr = stats["mr"]
    mean_x = stats["mean"]
    ucl_x = stats["ucl"]
    lcl_x = stats["lcl"]
    mr_bar = stats["mr_bar"]
    ucl_mr = stats["ucl_mr"]

    date_labels = dates.dt.strftime("%Y-%m-%d").tolist()

    fig, (ax_x, ax_mr) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    # X chart
    ax_x.plot(date_labels, x, marker="o", linestyle="-")
    ax_x.axhline(mean_x, color="gray", linestyle="--", label="Mean")
    ax_x.axhline(ucl_x, color="red", linestyle="--", label="UCL")
    ax_x.axhline(lcl_x, color="red", linestyle="--", label="LCL")
    ax_x.set_title(title)
    ax_x.set_ylabel("Value")
    ax_x.legend(loc="upper right")
    ax_x.grid(True, alpha=0.3)

    # mR chart
    ax_mr.plot(date_labels[1:], mr, marker="o", linestyle="-")
    ax_mr.axhline(mr_bar, color="gray", linestyle="--", label="MR mean")
    ax_mr.axhline(ucl_mr, color="red", linestyle="--", label="MR UCL")
    ax_mr.set_ylabel("mR")
    ax_mr.set_xlabel("Period end")
    ax_mr.legend(loc="upper right")
    ax_mr.grid(True, alpha=0.3)

    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    st.pyplot(fig)
