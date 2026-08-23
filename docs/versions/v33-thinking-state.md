# Claude Buddy v33 — Thinking State

## What Changed from v32

Previously the sprite only bobbed with a jump rope when an approval pill was on screen. Between the time you submitted a message and the first tool request, the widget was either hidden or static — giving no signal that Claude was processing. This version makes the rope animation the indicator of Claude activity, and the pill is just an overlay on top of it.

---

## Changes

### 1. Sprite bobs with rope whenever Claude is processing

**Before:** Bob animation started only when an approval pill appeared, and stopped the moment the last pill was dismissed.

**After:** Bob animation starts when `UserPromptSubmit` fires (you hit enter on any message) and stops when `Stop` fires (Claude finishes the full response). Approval pills appear on top of the already-running animation. The widget is always visible during a thinking session, regardless of the `idle_visible` setting.

### 2. New hooks: UserPromptSubmit and Stop

**Before:** Only `SessionStart`, `SessionEnd`, and `PermissionRequest` hooks were wired to the daemon.

**After:** `UserPromptSubmit` → `notify.sh thinking_start`, `Stop` → `notify.sh thinking_stop` (alongside the existing axcli Stop entry). Both are now in `~/.claude/settings.json`.

### 3. Two new modes in notify.sh

**Before:** `notify.sh` handled `session_start`, `session_end`, `idle_on`, `idle_off`, `sessions_on`, `sessions_off`, and `approval`.

**After:** Added `thinking_start` and `thinking_stop` modes. Both read `session_id` from stdin JSON, send a socket command to the daemon, and exit 0 immediately (non-blocking, unlike `approval`).

### 4. Per-session thinking state in buddy.py

**Before:** No concept of "Claude is actively processing" in the daemon.

**After:** `ChipWidget` maintains `_thinking_sessions: set`. `on_thinking_start` adds a session and starts the animation; `on_thinking_stop` removes it and stops the animation only when all sessions have stopped thinking and no approval is pending. `on_session_end` discards from the set so a killed or crashed session never leaves the animation stuck.

### 5. do_hide paths guarded against active thinking sessions

**Before:** When the last approval pill was dismissed (`_remove_by_pipe`, `_on_cancel`, `_cleanup_stale_requests`) or session rows were hidden (`_hide_session_rows`), the widget called `do_hide()` unconditionally if `idle_visible` was off.

**After:** All four callsites check `_thinking_sessions` first. If any session is still thinking, they skip `do_hide()` and leave the animation running. This is the same pattern introduced in `on_session_end`.

---

## What Stayed the Same

* Approval pill appearance and behavior — unchanged
* Session list (double-click sprite) — unchanged
* `idle_visible` flag behavior for the static idle sprite — unchanged
* Risk classification and auto-approve logic — unchanged
* All-spaces pinning, drag behavior, session focus — unchanged

## Known Issues (logged for v34)

* Sleeping sprite for the idle state (Claude waiting for user input) — deferred during brainstorming, intentionally not in this version
* No docstrings on `on_thinking_start` and `on_thinking_stop` — minor consistency gap with peer methods
