#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
pkill -f "buddy.py daemon" 2>/dev/null
sleep 0.5
python3 "$SCRIPT_DIR/buddy.py" daemon > /tmp/claude-buddy.log 2>&1 &
