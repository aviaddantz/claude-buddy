# Claude Buddy v18 -- Auto-Start Daemon

## What Changed from v17

If the buddy daemon wasn't running when a permission request arrived (crashed mid-session, new install before restarting Claude Code, or any other reason), notify.sh would silently fail to connect and then hang forever waiting for a decision on a pipe nobody was writing to. Now notify.sh auto-starts the daemon on connect failure and falls through to "allow" if it still can't start.

---

## Changes

### 1. Auto-start on connect failure (notify.sh)
**Before:** Socket connect failure was swallowed (`|| true`). The pipe was already created, so the script hung in the poll loop waiting for a decision that would never come.
**After:** Tracks connect success via `BUDDY_CONNECTED` flag. On failure, runs `start-daemon.sh`, waits 1.5s for the socket to appear, and retries the connect once.

### 2. Fallthrough to allow (notify.sh)
**Before:** No fallback. If the daemon was unreachable, the hook blocked indefinitely, freezing Claude Code.
**After:** If the daemon is still unreachable after the auto-start attempt, cleans up the pipe, logs the failure, and returns `{"behavior": "allow"}`. Claude Code continues without the widget.

## What Stayed the Same

* Widget UI, sprite, pill layout -- untouched
* Risk classification (classify.py) -- untouched
* buddy.py daemon code -- untouched
* start-daemon.sh -- untouched (reused as-is for auto-start)
* Happy path (daemon already running) -- no behavior change

## Known Limitations

* **1.5s delay on first request after auto-start:** The daemon needs time to initialize PyQt6 and bind the socket. The first permission request after an auto-start sees a ~1.5s delay before the widget appears.
* **Silent fallthrough if PyQt6 is broken:** If the daemon can't start (missing dependency, Python error), the user gets no widget and no warning beyond a log line in `/tmp/claude-buddy.log`. They might not realize Buddy isn't working.
* **Terminal approval delay:** (carried from v17) When the user approves from the terminal, the pill stays until the tool completes due to Claude Code not signaling the hook process.
* **Multiple pills for parallel requests:** (carried from v17) Parallel tool calls show multiple pills simultaneously.
