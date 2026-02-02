#!/bin/bash
# Wrapper for Retroactive Calibration Backfill

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 --pack <path> OR --all [--force]"
    exit 1
fi

python3 -m argus_py.reporting.backfill "$@"
