#!/bin/bash
[ -f /tmp/claude-buddy-disabled ] && exit 0
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
pkill -f "buddy.py daemon" 2>/dev/null
sleep 0.5
# setsid puts the daemon in its own session and process group. Backgrounding alone left it
# in the caller's group, so anything that reaped the launching hook or shell also killed
# the widget. macOS ships no setsid binary, hence perl's POSIX::setsid.
nohup perl -e 'use POSIX qw(setsid); setsid(); exec @ARGV or die $!' \
    /usr/local/bin/python3 "$SCRIPT_DIR/buddy.py" daemon \
    > /tmp/claude-buddy.log 2>&1 &
disown 2>/dev/null || true
