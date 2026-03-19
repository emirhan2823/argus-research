#!/bin/bash
echo "🐍 Argus Analyst Setup"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH."
    exit 1
fi

echo "📦 Installing Dependencies..."
pip3 install -r requirements.txt

echo "✅ Ready! Run using:"
echo "python3 argus_analyst.py /path/to/export_folder"
