#!/bin/sh
set -e

# Config
PYTHON_BIN="python3"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYLIB_DIR="$PROJECT_DIR/pylibs"

echo "==> Checking for $PYTHON_BIN..."

# Check if Python 3 is installed
if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
    echo "Python3 not found. Please install it using: opkg install python3 python3-pip" >&2
    exit 1
fi

# Create local pylibs folder if needed
mkdir -p "$PYLIB_DIR"

# Install requirements
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "==> Installing requirements to $PYLIB_DIR..."
    pip3 install --upgrade pip
    if ! pip3 install --no-warn-script-location --target="$PYLIB_DIR" -r "$PROJECT_DIR/requirements.txt"; then
        echo "\nSome packages failed to build. On OpenWRT you may need to compile them on another machine and copy the 'pylibs' directory." >&2
        exit 1
    fi
else
    echo "requirements.txt not found. Skipping dependency installation."
fi

# Run the app
echo "==> Starting app.py using Python with local dependencies..."
PYTHONPATH="$PYLIB_DIR" $PYTHON_BIN "$PROJECT_DIR/app.py"

