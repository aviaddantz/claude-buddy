# Claude Buddy v34 — Thinking State Fixes

## What Changed from v33

Two bugs discovered immediately after v33 shipped. The ESC bug left approval pills frozen on screen when cancelled during an active thinking session. The animation was also too busy — the sprite bobbing up and down while the rope spun was distracting during long Claude runs.

---

## Changes

### 1. Rope-only animation during thinking

**Before:** The bob step moved the sprite vertically (sine wave offset) while also rotating the rope angle. During the thinking state this created constant up-down movement.

**After:** The bob step only updates the rope angle. The sprite stays stationary. The rope spins, the sprite doesn't move.

### 2. ESC during thinking no longer leaves pill frozen

**Before:** When ESC was pressed in Claude Code while an approval pill was pending, `_on_cancel` and `_remove_by_pipe` hit `if self._thinking_sessions: pass` — they removed the request from `_requests` but never called `_rebuild_sessions()`. The pill widget stayed rendered in the layout. The widget would only clear if the `Stop` hook later called `do_hide()`, which was timing-dependent.

**After:** Both callsites now call `_rebuild_sessions()`, `_container.hide()`, and `_badge.hide()` when `_thinking_sessions` is non-empty. The pill clears immediately, the bob keeps running, and the widget stays visible showing just the sprite with the spinning rope.

---

## What Stayed the Same

* All thinking state logic from v33 — hooks, session tracking, show/hide guards
* Pill appearance and approval flow
* Widget visibility rules during thinking

## Known Issues (logged for v35)

* Alert pulse (colored ring expanding from sprite on pill arrival) — designed but not yet built
* Sleeping sprite for idle state — still deferred
