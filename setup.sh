#!/usr/bin/env bash
set -e

PYTHON_BIN="python3"

# Check for python3
if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
    echo "Python3 not found. Attempting to install..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv
    elif command -v brew >/dev/null 2>&1; then
        brew install python
    else
        echo "Could not find a package manager to install Python. Please install Python3 manually." >&2
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_BIN -m venv venv
fi

# Install requirements if needed
source venv/bin/activate
if [ -f requirements.txt ]; then
    echo "Installing requirements..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

deactivate

# Start the server
source venv/bin/activate
exec $PYTHON_BIN app.py

