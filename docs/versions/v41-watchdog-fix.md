# Claude Buddy v41 — Watchdog Fix

## What Changed from v40

The v40 watchdog (45s) was too aggressive. During a long text-only response with no tool calls, `PreToolUse` never fires to refresh the thinking-session timestamp, so the 45s clock was reaching zero while Claude was still actively generating. The rope would stop and the idle sprite would show mid-response.

---

## Changes

### 1. Watchdog no longer prunes active sessions by time
**Before:** Any thinking session older than 45s was pruned, regardless of whether the session was still active.
**After:** Sessions that are still present in `_sessions` (confirmed active via `session_start`/`session_end` tracking) are never pruned by time. Only two conditions prune a session:
* The session left `_sessions` (ended) but `thinking_stop` never fired — reliable fast path.
* `_sessions` is empty entirely (session tracking not working) — 5-minute last-resort fallback.

## What Stayed the Same

* `notify.sh` robust session_id extraction (v40)
* Empty session_id fallback in `on_thinking_stop` (v40)
* All other thinking-state and approval behavior

## Known Issues (logged for v42)

* Rope arc clips at widget boundary.
* Right-pointing flag requires wider sprite canvas.
* No transition animation between rope and flag states.
