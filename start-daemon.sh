#!/bin/bash
pkill -f "buddy.py daemon" 2>/dev/null
sleep 0.5
python3 ~/Development/nudge/buddy.py daemon > /tmp/claude-buddy.log 2>&1 &
