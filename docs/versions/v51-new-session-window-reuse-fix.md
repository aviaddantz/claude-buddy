# Claude Buddy v51 — New Session Window Reuse Fix

## What Changed from v50

`launch_session()` (the "New Session" action) sometimes just switched focus to an existing iTerm2 window instead of opening a new one, with no error surfaced anywhere. This version detects that failure mode and forces a real new window when it happens.

---

## Changes

### 1. Detect when iTerm2 silently reuses a window
**Before:** `create window with default profile` was trusted at face value. The AppleScript exited 0 and got logged as `iterm: opened <cwd>` even when iTerm2 handed back a reference to an *already-existing* window instead of creating a new one — a known iTerm2 AppleScript quirk. Result: the widget's "activate" brought an existing window forward, no new session opened, and nothing in the log indicated a problem.
**After:** the script captures window ids before the `create window` call and compares the new window's id against that set. If the id was already present, the window was reused, not created.

### 2. Fallback to Cmd+N when reuse is detected
**Before:** no recovery path — a reused window meant a silently failed launch.
**After:** on detected reuse, a second AppleScript activates iTerm2, sends Cmd+N via System Events to force a genuinely new window, waits 0.5s, then writes the `cd && claude` command into the current session of that new window. Both outcomes ("created" directly, or "created via fallback") are distinguished in `/tmp/claude-buddy.log`.

## What Stayed the Same
* The two-step `activate` → `create window with default profile` path remains the primary attempt; the fallback only runs when reuse is detected.
* Command construction (`cd <cwd> && claude`) and login-shell PATH resolution unchanged.
* No changes to the socket protocol, ChipWidget, or any other launch target (Claude desktop focus logic untouched).

## Known Issues (logged for v52)
* The Cmd+N fallback assumes iTerm2 is the frontmost/active app when the keystroke fires; if some other app steals focus in the 0.5s window, the keystroke could land elsewhere. Not yet observed, but not guarded against.
* Root cause of the iTerm2 window-reuse quirk itself (why `create window with default profile` occasionally returns an existing window) is still unknown — this is a workaround, not a fix at the source.
