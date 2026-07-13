# Claude Buddy v26 -- Pause Race Condition Fix

## What Changed from v25

Clicking "Pause Nudge" from the menu bar would often leave the widget on screen. The daemon was killed correctly, but it was immediately restarted by a concurrent `notify.sh` process before the disabled flag could be written.

---

## Root Cause

v18 added auto-start: if `notify.sh` can't reach the daemon, it calls `start-daemon.sh` and retries. The problem is that with many parallel permission requests in flight, there's always a `notify.sh` ready to trigger this. `stop-daemon.sh` was killing the process first and writing the flag second -- leaving a window where the daemon was dead but the guard didn't exist yet.

## Changes

### 1. Write disabled flag before killing (stop-daemon.sh)
**Before:** `pkill` fired first, then `touch /tmp/claude-buddy-disabled`. Any `notify.sh` checking `start-daemon.sh` in that gap would restart the daemon.
**After:** Flag is written first, then `pkill`. `start-daemon.sh` checks the flag on entry, so restarts are blocked from the moment pause is triggered.

### 2. Guard auto-start on disabled flag (notify.sh)
**Before:** `if [ "$BUDDY_CONNECTED" = false ]` -- unconditionally tried to restart.
**After:** `if [ "$BUDDY_CONNECTED" = false ] && [ ! -f /tmp/claude-buddy-disabled ]` -- skips restart if nudge is intentionally paused.

### 3. Removed transcript mtime check (notify.sh)
The transcript mtime check was false-triggering constantly -- Claude Code writes to the transcript during normal execution, causing immediate auto-approve before the user could interact with the widget. Removed entirely.

### 4. Added structured logging (notify.sh)
Added log lines for classification result, daemon connect attempt/result, and wait loop entry to make future debugging faster.

## What Stayed the Same

* Widget UI, sprite, pill layout -- untouched
* Risk classification (classify.py) -- untouched
* buddy.py daemon code -- untouched
* Happy path (daemon running, no pause) -- no behavior change
