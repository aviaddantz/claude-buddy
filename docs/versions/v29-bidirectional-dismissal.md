# Claude Buddy v29 — Bidirectional Dismissal

## What Changed from v28

Previously, if the user responded to a permission request directly from the Claude Code session (not via the widget), the widget stayed on screen indefinitely. Claude Code runs PermissionRequest hooks asynchronously — when the user responds natively, Claude Code processes the decision and runs the tool without killing the hook process. notify.sh remained alive (pipe intact, PID alive), so the stale checker never cleared the pill. This version makes dismissal bidirectional: either side responding clears the widget.

---

## Changes

### 1. Transcript mtime stale detection

**Before:** The stale checker only dismissed pills when the notify.sh PID was dead or the pipe file was removed. If Claude Code processed the decision natively and orphaned notify.sh, the pill stayed forever.

**After:** When a request is queued, the daemon stamps it with the current transcript mtime and a queue timestamp. The stale checker (every 500ms) compares the current transcript mtime against the stamped value. If the transcript has advanced (tool result written = tool ran = decision was made) and at least 2 seconds have elapsed since queuing (grace period to avoid false positives), the pill is dismissed and SIGTERM is sent to the orphaned notify.sh process.

### 2. TERM trap fix in notify.sh

**Before:** `trap '...' TERM` only logged "SIGTERM received" and let the script continue. In bash, a defined trap suppresses the signal's default action, so SIGTERM had no effect — the script kept running.

**After:** `trap '...; exit 1' TERM`. SIGTERM now terminates notify.sh, triggering the EXIT trap which removes the pipe and sends `cancel` to the daemon.

### 3. Session-end dismissal by session_id

**Before:** The Stop hook sent `{"cmd":"session_end"}` with no session identity. `on_session_end` only decremented the session counter and hid the widget if there were no pending requests. Orphaned pills from an ended session were never cleared.

**After:** The Stop hook reads session_id from stdin (the hook JSON) and includes it in the command. `on_session_end(session_id)` filters `_requests` by session_id, dismisses all matching pills, and sends SIGTERM to their notify.sh processes. Falls back to the previous count-only behavior if session_id is empty.

### 4. session_id and transcript_path in the show payload

**Before:** notify.sh didn't include `session_id` or `transcript_path` in the "show" payload sent to the daemon.

**After:** Both fields are extracted from the hook JSON and passed as additional argv to the payload builder. The daemon uses `transcript_path` for mtime tracking and `session_id` for session-end matching.

---

## What Stayed the Same

* Widget → session direction: approve/deny via the widget still writes to the named pipe, which notify.sh reads and returns to Claude Code. Unchanged.
* Pill UI, risk colors, always-allow flow, expand/collapse behavior
* Bob animation and idle sprite behavior
* Auto-approve for low-risk tools
* Drag and position persistence

## Known Issues (logged for v30)

* Denial in session (user denies via Claude Code's native UI, tool doesn't run) is not detected — transcript doesn't advance on denial, so the pill stays until session end or process death.
* The 2-second grace period means the widget lingers briefly after a fast session-side approval before being dismissed by the stale checker.
* `_session_count` is still optimistic — `on_session_end` decrements unconditionally, even for sessions that never fired `on_session_start`.
