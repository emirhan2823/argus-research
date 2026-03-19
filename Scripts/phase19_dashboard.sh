#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO_ROOT=$(pwd)

echo "Starting Phase 19 Dashboard..."
echo "Ensure requirements are installed: pip install -r requirements_phase19_ui.txt"

# Run streamlit
# server.port 8501 is default, but explicit is good
# server.headless for headless environments, but local is usually interactive.
python3 -m streamlit run Scripts/phase19_dashboard.py --server.port 8501
