# Claude Buddy v28 — Idle Sprite Fixes

## What Changed from v27

v27 shipped the idle sprite and drag features but several things didn't work in practice: the sprite didn't appear when toggling "Show when idle" on, Resume Nudge showed nothing and froze the menu, Quit Nudge left the sprite on screen, and the sprite animated when it should have been still. This version fixes all of that.

---

## Changes

### 1. Show idle sprite immediately on toggle-on
**Before:** `on_set_idle_visible` required `_session_count > 0` before showing. Since the daemon starts with count=0 (existing sessions don't re-fire their hook), toggling "Show when idle" on did nothing.
**After:** Guard removed. When the user explicitly enables the toggle, the sprite shows immediately regardless of session count.

### 2. Resume Nudge now shows the idle sprite
**Before:** `startDaemon()` started the daemon but never sent `session_start`, so `_session_count` stayed at 0 and the sprite didn't appear even with "Show when idle" on.
**After:** `startDaemon()` sends `session_start` 2 seconds after the daemon is up (when `idleVisible` is true), giving the sprite a session count to act on.

### 3. Quit Nudge now kills the daemon before exiting
**Before:** `stopDaemon()` runs async. `NSApp.terminate(nil)` fired first, the Swift process died, and `stop-daemon.sh` never ran. Daemon kept running, sprite stayed on screen.
**After:** New synchronous `quit()` method blocks on `stop-daemon.sh` before `NSApp.terminate(nil)` is called.

### 4. No animation or rope in idle state
**Before:** Idle sprite bobbed and showed the skip rope — same as active state.
**After:** `_show_idle()` stops the bob timer, resets sprite to rest position, and sets `show_rope = False`. Bob and rope are restored in `do_show()` when a permission request arrives.

### 5. Fixed Python path in start-daemon.sh
**Before:** `python3` resolved to the system Python (no PyQt6) when launched from the Swift app, which runs without a login shell and has a stripped PATH. Every Resume/Restart silently crashed.
**After:** Hardcoded `/usr/local/bin/python3` where PyQt6 is installed.

## What Stayed the Same

* Drag behavior and position persistence
* Session tracking (session_start/session_end hooks)
* Permission request flow, pill UI, approve/deny/always buttons
* Risk classification and auto-approve logic
* Pause/resume disabled-flag behavior

## Known Issues (logged for v29)

* `_session_count` is optimistic — `startDaemon()` sends `session_start` even if no Claude session is actually running. The sprite appears on Resume regardless of whether Claude Code is open.
* `stop-daemon.sh` uses `/usr/local/bin` is implicit via `pkill` — only the start path was fixed. If Python moves, both need updating.
* `bundle.sh` doesn't auto-copy to `/Applications` — requires manual `cp -r Nudge.app /Applications/` after every Swift rebuild.
