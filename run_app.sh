#!/usr/bin/env bash
# One command: create venv if needed, install deps, build outputs if missing, launch local app (http://localhost:8501).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv && .venv/bin/pip install -q -r requirements.lock; fi
[ -f outputs/submission_report.pdf ] || .venv/bin/python run_all.py
exec .venv/bin/streamlit run app.py --server.headless true --browser.gatherUsageStats false "$@"
