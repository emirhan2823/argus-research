#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
echo "Running End-to-End Smoke Test..."

# 1. Check Python Config
python3 Scripts/phase19_ui_readers_sanity.py

# 2. Check CTL Syntax
bash Scripts/phase19ctl.sh status > /dev/null

# 3. Check Streamlit dry run (help)
python3 -m streamlit --version

echo "PASS: End-to-End Smoke Test OK."
