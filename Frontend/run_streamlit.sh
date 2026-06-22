#!/bin/bash

# Pakistan NAVAREA IX GIS Real-Time Agent - Streamlit Frontend Launcher (Linux/macOS)
# This script sets up and runs the Streamlit frontend

set -e

echo ""
echo "============================================================"
echo "Pakistan NAVAREA IX - Streamlit Frontend"
echo "============================================================"
echo ""

# Find Python interpreter
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

echo "[1/4] Python detected:"
"$PYTHON_EXE" --version

# Activate virtual environment if it exists
echo ""
echo "[2/4] Preparing environment..."
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# Install dependencies
echo ""
echo "[3/4] Installing Streamlit dependencies..."
"$PYTHON_EXE" -m pip install -q -r streamlit_requirements.txt || echo "Dependencies install skipped or failed; continuing with existing packages."

# Create .streamlit directory if it doesn't exist
echo ""
echo "[4/4] Configuring Streamlit..."
mkdir -p .streamlit
if [ ! -f ".streamlit/config.toml" ]; then
    echo "Copying configuration..."
    cp .streamlit_config.toml .streamlit/config.toml
fi
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "Copying secrets template..."
    cp secrets.toml .streamlit/secrets.toml
fi

# Run Streamlit app
echo ""
echo "============================================================"
echo "Starting Streamlit Frontend..."
echo ""
echo "The dashboard will open at: http://localhost:8501"
echo "API Backend should be running at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"
echo "============================================================"
echo ""

"$PYTHON_EXE" -m streamlit run streamlit_app.py --client.toolbarMode=viewer
