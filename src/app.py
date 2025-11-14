import os
import sys
import runpy

# Absolute path to repo root: /mount/src/lead_scoring_app
ROOT = os.path.dirname(os.path.dirname(__file__))

# Ensure repo root is on PYTHONPATH so "ui", "data", "scoring" import correctly
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MAIN = os.path.join(ROOT, "app.py")

runpy.run_path(MAIN, run_name="__main__")
