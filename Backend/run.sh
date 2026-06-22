#!/bin/bash

# Pakistan NAVAREA IX GIS Real-Time Agent - Linux/macOS Quick Start
# This script automates setup and running on Linux/macOS

set -e

echo ""
echo "============================================================"
echo "Pakistan NAVAREA IX GIS Real-Time Agent"
echo "============================================================"
echo ""

# Check Python installation
PYTHON_EXE=""
if [ -x ".venv/bin/python" ]; then
    PYTHON_EXE=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON_EXE="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_EXE="$(command -v python)"
fi

if [ -z "$PYTHON_EXE" ]; then
    echo "ERROR: No Python interpreter found."
    echo "Please install Python 3.9+ or create a local virtual environment."
    exit 1
fi

echo "[1/5] Python detected:"
"$PYTHON_EXE" --version

# Activate virtual environment if it exists
echo ""
echo "[2/5] Preparing environment..."
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Install dependencies if pip is available
echo ""
echo "[3/5] Installing dependencies..."
"$PYTHON_EXE" -m pip install -q -r requirements.txt || echo "Dependencies install skipped or failed; continuing with existing packages."

# Run agent
echo ""
echo "[4/5] Starting agent..."
echo ""
echo "============================================================"
echo "Agent starting..."
echo "API will be available at: http://localhost:8000"
echo "Documentation at: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo "============================================================"
echo ""

"$PYTHON_EXE" main.py --run --host 127.0.0.1 --port 8000
