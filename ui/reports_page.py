# ui/reports_page.py
# v3 placeholder:
#   - Old summary/XmR reporting pipeline is not wired into nightly yet.
#   - This page deliberately does NOT import legacy `reports.*` modules.

import streamlit as st


def render() -> None:
    st.title("Reports")

    st.warning(
        "Summary / XmR reports are not yet implemented in the v3 nightly app.\n\n"
        "For now, use the production Lead Scoring app to view historical summary reports. "
        "This page will eventually:\n"
        "- Load saved scored runs (merged_data_leads) from Supabase\n"
        "- Let you pick one or more past scoring windows\n"
        "- Show class-distribution pie charts and XmR charts by Class%\n"
        "- Provide advanced breakdowns by `First user source / medium` and campaign."
    )

    st.caption(
        "The current nightly build focuses on getting data fetching, normalization, "
        "and scoring rock-solid. Reporting will be re-attached once we have "
        "Supabase storage for scored snapshots."
    )
