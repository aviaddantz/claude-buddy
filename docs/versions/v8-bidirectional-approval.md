# Claude Buddy v8 — Bidirectional Approval

## What Changed from v7

v7 left the widget orphaned on screen when the user answered a permission from the Claude Code terminal prompt. The hook process (`notify.sh`) was never killed by Claude Code — it just kept blocking on `cat "$PIPE"` indefinitely. v8 fixes this by polling the session transcript's mtime: when the user answers from the terminal, Claude Code writes to the transcript within milliseconds, the poll detects the change, and the widget hides within ~1 second.

---

## Changes

### 1. Transcript mtime polling replaces blocking pipe read

**Before:** `DECISION=$(cat "$PIPE" 2>/dev/null || echo "approve")` — blocks forever if terminal answers first. Claude Code does not kill `notify.sh` when the terminal resolves a permission; the process becomes an orphan and the widget stays on screen indefinitely.

**After:** A 1-second timeout poll loop replaces the blocking read:
```bash
while [ -z "$DECISION" ]; do
    DECISION=$(timeout 1 cat "$PIPE" 2>/dev/null || true)
    if [ -z "$DECISION" ]; then
        # transcript mtime changed → Claude Code moved on (terminal answered)
        CURRENT_MTIME=$(stat -f "%m" "$TRANSCRIPT" 2>/dev/null || echo "")
        if [ "$CURRENT_MTIME" != "$TRANSCRIPT_MTIME" ]; then
            DECISION="approve"
        fi
    fi
done
```
The transcript path comes from `HOOK_JSON.transcript_path`, already present in the hook payload. Mtime is snapshotted before the widget shows. When it changes, the orphan exits cleanly, the EXIT trap fires, and the widget hides.

### 2. Pending sentinel for back-to-back requests

**Before:** No mechanism to unblock an orphaned `notify.sh` when a new permission fires immediately after a terminal answer.

**After:** Each new `notify.sh` invocation touches `/tmp/claude-buddy-pending` before acquiring the lock. The poll loop also checks for this file. If it exists, the current process is stale — exits with `DECISION="approve"`, clears the path for the new request.

### 3. EXIT trap hides widget

**Before:** The EXIT trap only cleaned up the pipe and lock file. If `notify.sh` was ever killed externally, the widget stayed on screen.

**After:** `python3 "$SCRIPT_DIR/buddy.py" hide` added to the EXIT trap. Widget hides on any exit path — normal decision, transcript mtime trigger, pending sentinel, or external kill.

### 4. SCRIPT_DIR variable

**Before:** `$(dirname "$0")` repeated inline at each call site (non-approval mode exit, classify script path, hide command).

**After:** Resolved once at the top: `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`. All references use `$SCRIPT_DIR`.

---

## What Stayed the Same

* Widget visual design, button styles, risk colors
* Named pipe decision flow (widget approval still works identically)
* Lock file mechanism and stale lock recovery
* `buddy.py` — no changes
* `classify.py` — no changes
* Always Allow, Deny, attention mode — all unchanged

---

## Known Issues (logged for v9)

* Widget hides up to 1 second after terminal answer (poll interval) — not instant
* If Claude Code takes >1s to write to the transcript after terminal answer, the widget may persist slightly longer
* Pending sentinel (`/tmp/claude-buddy-pending`) is not cleaned up if `notify.sh` crashes before acquiring the lock
* Bob animation runs continuously — should stop after ~3s
* AskUserQuestion attention mode pill still shows risk-colored border — should be neutral
* No hover feedback on compact pill border
