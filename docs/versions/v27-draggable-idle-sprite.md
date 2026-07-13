# Claude Buddy v27 — Draggable Widget + Idle Sprite

## What Changed from v26

Two new features:

**Draggable position.** The widget can be dragged by clicking and holding the Claude sprite area (top ~74px). Position saves to `~/.nudge-position` on release and is restored on next show. `_reanchor()` no longer snaps back to the right edge after pill height changes — it keeps the user's chosen x.

**Idle sprite mode.** When "Show when idle" is enabled (menu bar toggle), the Claude sprite floats persistently whenever a Claude Code session is active — even with no pending permission requests. The pill container is hidden in idle state. When a permission request arrives, the container appears below the sprite as usual. When the last request resolves (via approve, deny, cancel, or stale cleanup), the widget returns to idle. When all sessions end, the widget hides entirely.

## New socket commands

| Command | Effect |
|---|---|
| `session_start` | Increment session count; show idle sprite if toggle on |
| `session_end` | Decrement session count; hide if zero sessions and no requests |
| `set_idle_visible` | Toggle idle mode at runtime (sent by menu bar app) |

## New flag files

| File | Meaning |
|---|---|
| `~/.nudge-idle-visible` | Idle sprite toggle is ON |
| `~/.nudge-position` | Saved widget position `{"x": N, "y": N}` |

## notify.sh new modes

`session_start`, `session_end`, `idle_on`, `idle_off` — all send the appropriate socket command via `_send_socket_cmd` helper and exit. `done` mode now sends `session_end` instead of calling `buddy.py hide`.

## Hooks wired

`~/.claude/settings.json` SessionStart and SessionEnd hooks now call `notify.sh session_start` / `notify.sh session_end` alongside the existing axcli hooks.

## What Stayed the Same

- Permission request flow, pill UI, approve/deny/always buttons
- Risk classification
- Auto-approve low-risk
- Pause/resume behavior
