#!/bin/bash
touch /tmp/claude-buddy-disabled
pkill -f "buddy.py daemon" 2>/dev/null
echo "Claude Buddy stopped. Will not auto-start next session."
echo "To re-enable: rm /tmp/claude-buddy-disabled"
