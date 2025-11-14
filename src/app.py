# shim for Streamlit Cloud (nightly)
# Streamlit Cloud is still trying to launch src/app.py
# but our real entry point is now top-level app.py.

import os, runpy

ROOT = os.path.dirname(os.path.dirname(__file__))  # /mount/src/lead_scoring_app
MAIN = os.path.join(ROOT, "app.py")

runpy.run_path(MAIN, run_name="__main__")
