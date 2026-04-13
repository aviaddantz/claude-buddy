# Claude Buddy v10 — All-Spaces Visibility

## What Changed from v9

v9 used `NSWindowCollectionBehaviorCanJoinAllSpaces` but the widget only appeared on the main desktop. Two bugs caused this: the collection behavior flags were missing `NSWindowCollectionBehaviorFullScreenAuxiliary`, and `_pin_to_all_spaces()` was called before `show()`, meaning the NSApp window list was empty at pin time so the flags were never actually applied.

---

## Changes

### 1. Added `NSWindowCollectionBehaviorFullScreenAuxiliary` (`buddy.py`)

**Before:** Only `CanJoinAllSpaces` was set (minus `MoveToActiveSpace`).

**After:** `FullScreenAuxiliary` is also added to the behavior mask. This flag tells macOS the window is an auxiliary overlay, which is required for it to appear over fullscreen spaces.

### 2. Moved `_pin_to_all_spaces()` to after `show()` (`buddy.py`)

**Before:** `_pin_to_all_spaces()` was called before `self.show()`. At that point the Qt window hadn't been added to the NSApp window list yet, so the `for win in NSApp.windows()` loop found nothing and the collection behavior was never set.

**After:** `_pin_to_all_spaces()` is called immediately after `self.show()`, ensuring the window is present in the NSApp window list when the behavior flags are applied.

---

## What Stayed the Same

- Risk classification logic (`classify.py`) — unchanged
- Multi-session queue and tab navigation
- All other `_pin_to_all_spaces` logic
- Bob animation, sprite, expanded view buttons
- `start-daemon.sh` lifecycle script

---

## Known Issues (carried from v9)

- Widget does not appear on fullscreen spaces (dedicated macOS Spaces created by fullscreen apps). `FullScreenAuxiliary` + various window level approaches were tried but either broke multi-desktop visibility or had no effect. Left for a future version.
- 1s staleness delay after terminal acceptance
- Bob animation runs indefinitely
- Attention mode (AskUserQuestion) shows risk-colored border instead of neutral