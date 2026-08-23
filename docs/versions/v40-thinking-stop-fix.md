# Claude Buddy v40 — Thinking-Stop Reliability

## What Changed from v39

The rope animation was getting stuck after Claude finished working — sometimes indefinitely (up to the 600s watchdog), sometimes permanently. Root cause was `thinking_stop` failing to clear `_thinking_sessions` due to session_id mismatches.

---

## Changes

### 1. Robust session_id extraction in notify.sh
**Before:** `thinking_start` and `thinking_stop` used `d.get('session_id', '')` — if the `Stop` hook payload delivers `session_id` as an object `{key: uuid}` rather than a plain string (which Claude Code does in some hook types), `print()` would output `{'key': 'value'}` instead of the UUID. This never matched the string stored during `thinking_start`, so `_thinking_sessions.pop()` was a no-op and the rope stayed on.
**After:** The extraction now checks `isinstance(sid, dict)` and takes the first value. Same logic the axcli hook command already uses. Both `thinking_start` and `thinking_stop` share one code path.

### 2. Empty session_id fallback in on_thinking_stop
**Before:** If session_id arrived as empty string (stdin parse failure), `_thinking_sessions.pop("", None)` was a no-op — existing entries untouched, rope stuck.
**After:** Empty session_id clears all thinking sessions. A concurrent session's next `PreToolUse` will restart its rope immediately via the keepalive.

### 3. Watchdog timeout 600s → 45s
**Before:** Stale thinking sessions (where `thinking_stop` never arrived) were pruned after 10 minutes.
**After:** Pruned after 45 seconds. Safe because `PreToolUse` refreshes the timestamp on every tool call — the 45s clock only starts after the last tool call completes. Any response that takes longer than 45s to generate after the last tool call would have been stuck for 45s anyway.

### 4. README updated
Added full 6-hook configuration block, thinking-state flow diagram, "Always show" menu bar entry, and rope animation in the features list.

## What Stayed the Same

* `thinking_start` logic
* `PreToolUse` keepalive behavior
* Multi-session support
* All approval/pill behavior

## Known Issues (logged for v41)

* Rope arc clips at widget boundary — doesn't visibly clear below the feet.
* Right-pointing flag requires wider sprite canvas.
* No transition animation between rope and flag states.
