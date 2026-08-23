# Claude Buddy v36 — Idle Stuck Fix

## What Changed from v35

After an interrupted approval (notify.sh killed mid-flight), the widget could get stuck visible in rope/flag state with no way to recover via the idle toggle. Toggling "show idle" off/on had no effect because the guard in `on_set_idle_visible` required the widget to already be hidden before it would show idle.

---

## Changes

### 1. Removed `not self.isVisible()` guard in `on_set_idle_visible`
**Before:** `if value and not self._requests and not self.isVisible()`
**After:** `if value and not self._requests`

The guard was intended to avoid redundantly showing an already-visible idle widget, but it also blocked recovery: if the widget was stuck visible (rope/flag state from a stale request) and the user toggled idle, the condition was False and nothing happened. Removing the guard means enabling idle always triggers `_show_idle()` when no requests are pending, which correctly resets animation state regardless of current visibility.

## What Stayed the Same

* Flag animation logic (v35)
* Thinking state / rope transition behavior
* Stale request cleanup timer
* All session management

## Known Issues (logged for v37)

* If `thinking_stop` never fires (daemon restarted mid-session, process killed without Stop hook), `_thinking_sessions` retains a stale entry and `_show_idle()` silently returns early — widget stays in rope state. Fix: dead-process check in `_cleanup_stale_requests` similar to how stale notify.sh pipes are detected.
* Rope arc clips at widget boundary — doesn't visibly clear below the feet. Pending user option selection for rope extension.
