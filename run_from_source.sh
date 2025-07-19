#!/bin/bash
# Script to run Claude-Code-Usage-Monitor from source without installing

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SRC_DIR="$SCRIPT_DIR/src"

# Check if src directory exists
if [ ! -d "$SRC_DIR" ]; then
    echo "Error: src directory not found at $SRC_DIR"
    exit 1
fi

# Change to src directory
cd "$SRC_DIR"

# Run with all arguments passed to this script
python3 -m claude_monitor "$@"