# Claude Buddy: Draggable Widget + Idle Sprite

**Date:** 2026-07-13

---

## Overview

Two connected features: (1) the widget can be dragged to any screen position and remembers it, and (2) the Claude sprite floats persistently while any Claude session is active, disappearing only when all sessions end. Both features are controlled by a new "Show when idle" menu bar toggle.

---

## Widget States

| State | Trigger | What's visible |
|---|---|---|
| Hidden | No active sessions | Nothing |
| Idle | Session active, no pending request, toggle on | Sprite only (pill container hidden) |
| Active | Pending permission request | Sprite + pill(s) |
| Paused | User clicked "Pause Nudge" | Nothing (existing behavior) |

When "Show when idle" is toggled OFF, the idle state is skipped — widget only appears for permission requests (current behavior).

---

## Session Tracking

Uses existing Claude Code hooks. The daemon maintains `_session_count: int`.

**`session_start` command** (new): increment count. If `_session_count == 1` and no pending requests and toggle is on, show sprite-only (idle state).

**`session_end` command** (new): decrement count. If `_session_count == 0` and no pending requests, hide widget.

`notify.sh` `done` mode currently calls `buddy.py hide` — change to send `session_end` to the daemon socket instead (same as other commands).

`~/.claude/settings.json` SessionStart hook: keep existing `start-daemon.sh` call, add a second command that sends `session_start` to the socket.

Multiple parallel sessions work correctly because count tracks each independently.

---

## Drag

Drag handle is the sprite area only (top ~52px). Pill buttons are unaffected.

On `mousePressEvent` (sprite): record `_drag_offset = event.globalPos() - window.pos()`.
On `mouseMoveEvent` (sprite): `window.move(event.globalPos() - _drag_offset)`.
On `mouseReleaseEvent` (sprite): write `{"x": window.x(), "y": window.y()}` to `~/.nudge-position`.

`_position_window()` (called on first show): load from `~/.nudge-position`; fallback to top-right if file absent or unreadable.

`_reanchor()` (called when pill height changes): currently recalculates `_base_x` from right edge. After this change, keep `_base_x` as-is (user's chosen x) and only update `_base_y` if the window would go off-screen vertically.

---

## Menu Bar Toggle

New item in `NudgeApp.swift`: `Toggle("Show when idle", isOn: ...)`.

Backed by flag file `~/.nudge-idle-visible` — file exists → toggle is ON. Same pattern as the existing `~/.nudge-autoapprove-disabled` flag.

`DaemonController` exposes `idleVisible: Bool` (published). `toggleIdleVisible()` creates/removes the flag file.

When toggled ON mid-session (sessions are active, no pending request): send `session_start` to daemon to trigger idle show immediately.
When toggled OFF mid-session (widget is in idle state): send `session_end` to daemon to hide it.

---

## Changes by File

**`buddy.py`**
- `ChipWidget`: add `_session_count`, `_idle_visible` flag, `_drag_offset`
- New socket commands: `session_start`, `session_end`
- `_show_idle()`: show widget with pill container hidden
- `_hide_idle()`: hide widget (only if no pending requests)
- `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` on sprite area
- `_position_window()`: load saved position
- `_reanchor()`: preserve user x, only clamp to screen bounds

**`notify.sh`**
- `done` mode: replace `buddy.py hide` subprocess call with socket `session_end` command

**`NudgeApp/Sources/Nudge/NudgeApp.swift`**
- Add `Toggle("Show when idle", ...)` menu item

**`NudgeApp/Sources/Nudge/DaemonController.swift`**
- Add `idleVisible: Bool` published property
- Add `toggleIdleVisible()` method (flag file create/remove)
- On toggle-on with active session: send `session_start` to socket
- On toggle-off: send `session_end` to socket

**`~/.claude/settings.json`** (user's settings, not in repo)
- SessionStart hook: add `session_start` socket command after `start-daemon.sh`

---

## What Stays the Same

- Permission request flow (notify.sh → socket → show pill) — untouched
- Risk classification — untouched
- Pill UI, approve/deny/always buttons — untouched
- Auto-approve low-risk — untouched
- Pause/resume behavior — untouched
