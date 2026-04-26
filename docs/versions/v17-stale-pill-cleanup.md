# Claude Buddy v17 -- Stale Pill Cleanup

## What Changed from v16

Pills would linger in the widget after being approved from the terminal. Three cleanup mechanisms existed but each had gaps: the EXIT trap cancel could fail silently, zombie processes fooled the PID-alive check, and the transcript mtime detection was too slow. Now cleanup is reliable via multiple redundant checks, and the poll interval is 3x faster.

---

## Changes

### 1. Pipe-exists check in staleness timer (buddy.py)
**Before:** Staleness timer only checked if the notify.sh process was alive via `os.kill(pid, 0)`. If the EXIT trap's cancel socket message failed, the pill lingered forever.
**After:** Also checks if the named pipe file still exists. When notify.sh exits (EXIT trap fires), it removes the pipe *before* sending the cancel. Missing pipe = request resolved, even if the cancel message was lost.

### 2. Zombie detection (buddy.py)
**Before:** `os.kill(pid, 0)` returns success for zombie processes (dead but not reaped). Pill stayed because buddy.py thought the process was alive.
**After:** When `os.kill` says "alive," a `ps -p <pid> -o state=` check catches zombies (state "Z").

### 3. Faster staleness timer (buddy.py)
**Before:** Checked every 1000ms.
**After:** Checks every 500ms.

### 4. Faster poll interval (notify.sh)
**Before:** `timeout 1 cat "$PIPE"` polled once per second.
**After:** `timeout 0.3` polls ~3x per second. Detects transcript changes and parent death faster.

### 5. Reparenting detection (notify.sh)
**Before:** Only checked if parent PID was alive (`kill -0 $PPID`).
**After:** Also checks if the current parent PID changed (process was adopted by launchd after parent was killed). Catches cases where the parent becomes a zombie that `kill -0` doesn't detect.

### 6. EXIT trap logging (notify.sh)
**Before:** EXIT trap ran silently.
**After:** Logs one line to `/tmp/claude-buddy.log` for diagnosing future cleanup issues.

## What Stayed the Same

* Widget UI, sprite, pill layout -- untouched
* Risk classification (classify.py) -- untouched
* Socket protocol between notify.sh and buddy.py -- untouched
* Approving/denying from the widget -- already worked, still works

## Known Limitations

* **Terminal approval delay:** When the user approves from the terminal (not the widget), the pill stays until the tool completes. Claude Code doesn't write a "permission granted" event to the transcript, and doesn't kill or signal the hook process. The transcript only updates when the tool result arrives. For WebSearch, this can be ~20 seconds. This is a Claude Code limitation, not a Buddy bug. Workaround: approve from the widget instead (instant).
* **Multiple pills for parallel requests:** When Claude Code fires parallel tool calls (e.g., 4 WebSearch calls from a subagent), all 4 pills appear at once even though the terminal only shows one prompt. This is correct behavior (all hooks fire simultaneously), but can be confusing.
