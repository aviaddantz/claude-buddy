# Claude Buddy v23 — Full-Screen Space Follow

## What Changed from v22

The chip widget appeared correctly on the active full-screen Space when a request came in, but did not follow when switching to a different full-screen app's Space (e.g., Claude Desktop → iTerm). `NSWindowCollectionBehaviorCanJoinAllSpaces` pins the window to all Spaces at creation time, but does not re-front it when the active Space changes. v23 subscribes to `NSWorkspaceActiveSpaceDidChangeNotification` and calls `orderFrontRegardless()` on every Space switch, so the chip appears on whichever full-screen Space the user navigates to.

---

## Changes

### 1. Space-change observer in `_pin_to_all_spaces`
**Before:** `_pin_to_all_spaces()` set collection behaviors and window level once, at show time. Switching to a different full-screen Space left the chip invisible on that Space.
**After:** On the first call to `_pin_to_all_spaces()`, a one-time observer is registered for `NSWorkspaceActiveSpaceDidChangeNotification`. The observer callback calls `orderFrontRegardless()` on all windows if the widget is currently visible. Registration is guarded by `_space_observer_registered` so the observer is only added once per daemon lifetime.

---

## What Stayed the Same

* Collection behavior flags (`CanJoinAllSpaces`, `FullScreenAuxiliary`, `Stationary`, `IgnoresCycle`) — unchanged
* Window level (25, NSStatusWindowLevel) — unchanged
* All chip UI, pill layout, approve/deny/always-allow flow — unchanged
* `notify.sh`, `classify.py`, risk classification — unchanged

## Known Issues (logged for v24)

* **Observer is never removed** — if the daemon restarts without process exit, the observer could accumulate (in practice the daemon process exits on restart, so this is benign)
* **`orderFrontRegardless()` fires on every space switch** even when the chip is hidden — guarded by `isVisible()` check, so no visible effect, but the check runs unconditionally
* Carried from v22: "Open Claude" doesn't navigate to specific conversation; `TERM_PROGRAM` not set in all terminals; menu bar icon legibility; no restart feedback; SMAppService in /Applications; `swift build` CLT bug
