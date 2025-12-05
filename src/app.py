import streamlit as st

NEW_URL = "https://dreamclass-leadscoringapp.streamlit.app"

st.set_page_config(
    page_title="Lead Scoring App – Moved",
    page_icon="📦",
    layout="centered",
)

st.markdown(
    f"""
    <h2 style='text-align:center;'>🚧 The Lead Scoring App Has Moved</h2>

    <p style='text-align:center;font-size:1.2rem;'>
        This URL is no longer the active version of the Lead Scoring App.<br>
        Please update your bookmarks.
    </p>

    <p style='text-align:center;margin-top:2rem;'>
        <a href="{NEW_URL}" style="
            background:#05a988;
            padding:0.8rem 1.4rem;
            color:white;
            text-decoration:none;
            border-radius:8px;
            font-weight:600;
            font-size:1.1rem;
        ">Go to the New App →</a>
    </p>

    <script>
        setTimeout(() => {{
            window.location.href = "{NEW_URL}";
        }}, 2500);
    </script>
    """,
    unsafe_allow_html=True,
)
