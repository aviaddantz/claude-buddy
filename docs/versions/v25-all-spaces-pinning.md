# Claude Buddy v25 — All-Spaces Pinning Fix

## What Changed from v24

The chip was not reliably visible when switching to a different Space or a full-screen app. The `NSWindowCollectionBehaviorCanJoinAllSpaces` flag was supposed to make the widget exist on all Spaces simultaneously, but the code applying it was silently failing in two ways: (1) the startup timer fired before Qt created the native NSWindow, so there was nothing to pin, and (2) `NSApp.windows()` is unreliable for apps running as `NSApplicationActivationPolicyAccessory` — it can return an empty or incomplete list. v25 fixes both by getting the NSWindow directly from the widget's native handle, and adds redundant re-pin calls to ensure the flag survives space switches.

---

## Changes

### 1. Force native window creation in `__init__` (`buddy.py`)
**Before:** `QTimer.singleShot(100, self._pin_to_all_spaces)` fired 100ms after init while the widget was hidden. Qt defers native NSWindow creation until the first `show()`, so `NSApp.windows()` returned empty — the initial pin was a no-op.
**After:** `self.winId()` called immediately before the timer. Calling `winId()` on a QWidget forces Qt to create the native NSWindow even if the widget hasn't been shown yet. The 100ms timer now finds the window.

### 2. Direct NSWindow lookup via `winId()` in `_pin_to_all_spaces()` (`buddy.py`)
**Before:** `_pin_to_all_spaces()` iterated `NSApp.windows()` to find windows to pin. For apps with `NSApplicationActivationPolicyAccessory`, `NSApp.windows()` can be incomplete, meaning the collection behavior was applied to 0 windows.
**After:** Uses `objc.objc_id(int(self.winId())).window()` to get the NSWindow directly from this widget's native view handle, bypassing `NSApp.windows()` entirely. Falls back to `NSApp.windows()` only if the direct path fails. A log line `[buddy] _pin_to_all_spaces: N windows` now confirms how many windows were found each time.

### 3. Deferred re-pin after `show()` in `do_show()` (`buddy.py`)
**Before:** `_pin_to_all_spaces()` called once immediately after `self.show()`. If AppKit hadn't fully processed the show event yet, the NSWindow might not be fully registered.
**After:** An additional `QTimer.singleShot(100, self._pin_to_all_spaces)` fires 100ms after show as a safety net, ensuring the flags are set even if the immediate call raced with AppKit.

### 4. Re-apply flags on every space switch (`buddy.py`)
**Before:** The `NSWorkspaceActiveSpaceDidChangeNotification` observer only called `orderFrontRegardless()`, which moves the window forward in z-order within its current space but does nothing if the window isn't already in that space.
**After:** Observer now also calls `self._pin_to_all_spaces()` on every space change, re-applying the collection behavior flags in case they were lost.

---

## What Stayed the Same

* Widget always positions at top-right of the primary monitor — unchanged
* Risk classification, chip UI, approve/deny flow, always-allow — unchanged
* `notify.sh`, `start-daemon.sh`, Swift app — unchanged
* Window level (`setLevel_(25)`) — unchanged

## Known Issues (logged for v26)

* Carried from v24: space observer never removed on daemon restart (benign); "Open Claude" doesn't navigate to specific conversation; menu bar icon legibility; SMAppService in /Applications.
* The `objc.objc_id` bridge hasn't been stress-tested across macOS versions — if it fails, the code falls back to `NSApp.windows()` which was the prior behavior.
* Full-screen app spaces (not just virtual desktops) still need real-usage validation — the fix is theoretically sound but untested in that specific scenario.
