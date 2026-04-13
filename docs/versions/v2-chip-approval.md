# Claude Buddy v2 — Chip Approval UI

**Status:** Current
**Architecture:** Single ChipWidget with in-place expand, JSON socket protocol, named pipe for decision

---

## What It Does

A single risk-colored chip in the top-right corner shows when Claude Code needs tool approval. The chip displays the intent (plain English), folder name, and risk level by color. Hovering expands the chip downward in-place to reveal the tool name, risk badge, and three action buttons. The user never has to switch to the terminal — approval happens directly in the chip.

---

## How It Works

### notify.sh
1. Reads full `PermissionRequest` JSON from stdin (`tool_name`, `tool_input`, `cwd`)
2. Classifies risk + generates intent locally (rule-based Python, no API call)
3. Creates a PID-unique named pipe: `/tmp/claude-buddy-decision-$$`
4. Sends JSON payload over Unix socket to daemon: `{"cmd":"show","tool":...,"intent":...,"risk":...,"pipe":...,"cwd":...}`
5. Blocks on `cat "$PIPE"` indefinitely — no timeout
6. Reads decision (`approve` or `deny`) from pipe when user clicks
7. Returns `{"decision":"allow"}` or `{"decision":"block","reason":"Denied via Claude Buddy"}`
8. On `done` mode (Stop hook): sends hide command and exits

### Risk classifier (local, rule-based)
| Condition | Risk | Intent |
|-----------|------|--------|
| Read/Glob/Grep/WebFetch | low | "Reading files" |
| Bash with rm/--force/sudo/dd | high | "Deleting files" / "Running as admin" / etc. |
| Bash with ls/cat/echo/pwd | low | "Reading system info" |
| Bash with npm/pip/brew install | medium | "Installing packages" |
| Bash with curl/wget | medium | "Fetching from network" |
| Bash with git commit/add/merge | medium | "Git operation" |
| Write/Edit tool | medium | "Editing {filename}" |
| Agent tool | medium | "Spawning subagent" |
| Default | medium | "Running a command" |

### buddy.py daemon

**Socket protocol (JSON):**
```json
{"cmd": "show", "tool": "Bash", "intent": "Installing packages", "risk": "medium", "pipe": "/tmp/claude-buddy-decision-1234", "cwd": "nudge"}
{"cmd": "hide"}
{"cmd": "approve"}
{"cmd": "deny"}
```
Backward-compatible: plain string commands still work.

**SocketServer:**
* Reads 4096 bytes per message
* Parses JSON; falls back to plain string for backward compat
* `show_signal = pyqtSignal(dict)` — carries full payload dict to main thread

**ChipWidget (single window, two states):**

Compact state (always visible while waiting):
* Frameless, always-on-top, all-spaces pinned
* Risk-colored border + background (green/yellow/red)
* Horizontal layout: SpriteWidget (36×30) | intent label | folder name (dim)
* Bobbing QPropertyAnimation (10px, 900ms, sine, infinite)

Expanded state (on hover):
* Same window grows downward — `_expanded_widget` becomes visible, `adjustSize()` called
* Shows: divider line, tool name + risk badge row, then three buttons:
  * **✓ Approve** (green) — writes `approve` to pipe, chip hides
  * **↗ Go to session** (cyan) — writes `approve` to pipe + focuses terminal, chip hides
  * **✕ Deny** (red) — writes `deny` to pipe, chip hides
* 300ms collapse timer on mouse leave (so cursor can move to buttons without chip collapsing)

**Decision writing:**
* `_write_decision(decision, pipe_path)` runs `open(pipe_path, "w")` on a background thread
* Background thread needed because `open()` on a named pipe blocks until the reader is ready — writing on main thread would freeze Qt

**Terminal focus (`_focus_terminal`):**
* Checks `ITERM_SESSION_ID` env var → targets exact iTerm2 session via AppleScript
* Falls back to checking running processes for Terminal/Warp/Alacritty/Hyper/iTerm2 and activating first match

**All-spaces pinning (`_pin_to_all_spaces`):**
* AppKit `NSWindowCollectionBehaviorCanJoinAllSpaces` via objc bridge
* Falls back to iterating `NSApp.windows()` if direct winId approach fails

---

## Key Constants

```python
SOCKET_PATH = "/tmp/claude-buddy.sock"
DECISION_PIPE = "/tmp/claude-buddy-decision"  # fallback only; real path is PID-unique from notify.sh

RISK_COLORS = {
    "low":    {"border": "#4CAF50", "bg": "#0d1f0d", "text": "#a5d6a7"},
    "medium": {"border": "#ffaa00", "bg": "#1f1a00", "text": "#ffe082"},
    "high":   {"border": "#f44336", "bg": "#1f0a0a", "text": "#ef9a9a"},
}
```

---

## Files

| File | Role |
|------|------|
| `buddy.py` | Daemon: SocketServer + ChipWidget + SpriteWidget |
| `notify.sh` | Hook script: classifier + socket sender + pipe waiter |
| `start-daemon.sh` | Kills existing daemon, starts fresh, logs to `/tmp/claude-buddy.log` |

---

## Claude Code Hook Config (`~/.claude/settings.json`)

```json
{
  "hooks": {
    "SessionStart": [{"command": "bash ~/Development/nudge/start-daemon.sh"}],
    "PermissionRequest": [{"command": "bash ~/Development/nudge/notify.sh approval"}],
    "Stop": [{"command": "bash ~/Development/nudge/notify.sh done"}]
  }
}
```

---

## Known Issues / Decisions

* **No timeout** — intentional. notify.sh blocks until the user clicks. Claude Code will wait indefinitely.
* **Concurrent requests** — if two approvals fire simultaneously, pipes are PID-unique so they don't collide, but only one chip is shown (last one wins). Queuing is out of scope.
* **`WindowDoesNotAcceptFocus` removed** — was needed for the old separate panel approach but prevented button clicks on the chip. Removed in v2.
* **`O_NONBLOCK` removed** — replaced with background thread write. `O_NONBLOCK` caused silent `ENXIO` failures when buddy tried to write before notify.sh's `cat` had opened the pipe for reading.
