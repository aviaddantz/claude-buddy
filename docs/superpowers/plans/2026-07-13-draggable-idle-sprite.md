# Draggable Widget + Idle Sprite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Claude Buddy widget draggable (position persists) and add a persistent idle-sprite mode that shows whenever a Claude session is active, controlled by a menu bar toggle.

**Architecture:** Session tracking uses two new socket commands (`session_start` / `session_end`) emitted by Claude Code hooks. The widget enters idle state (sprite only, no pill) when sessions are active and no requests are pending. Drag is handled on the `ChipWidget` level — mouse press in the sprite zone (y < `_sprite_h`) starts a drag; release writes position to `~/.nudge-position`.

**Tech Stack:** Python 3 / PyQt6 (`buddy.py`), Bash (`notify.sh`), Swift/SwiftUI (`NudgeApp`), macOS AppKit.

## Global Constraints

- macOS only — AppKit APIs used throughout
- No test suite — validate manually after each task by running `bash ~/Development/nudge/start-daemon.sh` and exercising the feature
- PyQt6 `QPoint` API: use `event.globalPosition().toPoint()` and `event.position()` (PyQt6 dropped the old `globalPos()`)
- Flag file pattern: file exists = feature ON (same as `~/.nudge-autoapprove-disabled`)
- New flag files: `~/.nudge-idle-visible` (idle sprite on) and `~/.nudge-position` (saved position JSON)
- SOCKET_PATH = `/tmp/claude-buddy.sock`
- After any Swift change: rebuild with `cd ~/Development/nudge/NudgeApp && swift build -c release 2>&1 | tail -5`

---

### Task 1: Position persistence + drag in `buddy.py`

**Files:**
- Modify: `buddy.py` — `ChipWidget.__init__`, `_position_window`, `_reanchor`, add `_load_saved_position`, `_save_position`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`

**Interfaces:**
- Produces: `ChipWidget._base_x` / `_base_y` now reflect user-dragged position; `_reanchor()` no longer recalculates x from screen edge; `~/.nudge-position` written on drag-release

- [ ] **Step 1: Add `_drag_offset` and position helpers to `ChipWidget.__init__`**

In `ChipWidget.__init__`, after the line `self._base_y = 80` (around line 520), add:

```python
self._drag_offset = None
```

Then add two new methods to `ChipWidget`, just before `_position_window`:

```python
POSITION_FILE = os.path.expanduser("~/.nudge-position")

def _load_saved_position(self):
    try:
        with open(os.path.expanduser("~/.nudge-position")) as f:
            data = json.load(f)
            x, y = data.get("x"), data.get("y")
            if isinstance(x, int) and isinstance(y, int):
                return x, y
    except Exception:
        pass
    return None, None

def _save_position(self):
    try:
        with open(os.path.expanduser("~/.nudge-position"), "w") as f:
            json.dump({"x": self._base_x, "y": self._base_y}, f)
    except Exception:
        pass
```

- [ ] **Step 2: Update `_position_window` to load saved position**

Replace the existing `_position_window` method (lines ~695-700):

```python
def _position_window(self):
    self._update_window_size()
    saved_x, saved_y = self._load_saved_position()
    if saved_x is not None:
        self._base_x = saved_x
        self._base_y = saved_y
    else:
        screen = QApplication.primaryScreen().geometry()
        self._base_y = 80
        self._base_x = screen.width() - self.width() - 20
    self.move(self._base_x, self._base_y)
```

- [ ] **Step 3: Update `_reanchor` to preserve user's x position**

Replace the existing `_reanchor` method (lines ~702-706):

```python
def _reanchor(self):
    # Keep user's x; only re-apply position after height changes
    self.move(self._base_x, self._base_y)
```

- [ ] **Step 4: Add mouse event handlers for drag**

Add these three methods to `ChipWidget`, after `_reanchor`:

```python
def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        if event.position().y() < self._sprite_h:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
    super().mousePressEvent(event)

def mouseMoveEvent(self, event):
    if self._drag_offset is not None and event.buttons() == Qt.MouseButton.LeftButton:
        new_pos = event.globalPosition().toPoint() - self._drag_offset
        self._base_x = new_pos.x()
        self._base_y = new_pos.y()
        self.move(new_pos)
        event.accept()
        return
    super().mouseMoveEvent(event)

def mouseReleaseEvent(self, event):
    if self._drag_offset is not None:
        self._drag_offset = None
        self._save_position()
        event.accept()
        return
    super().mouseReleaseEvent(event)
```

- [ ] **Step 5: Change cursor on sprite area to indicate draggability**

The widget currently sets `self.setCursor(Qt.CursorShape.PointingHandCursor)` globally. Change this to `OpenHandCursor` so the sprite area communicates drag intent:

Find the line (around line 571):
```python
self.setCursor(Qt.CursorShape.PointingHandCursor)
```
Replace with:
```python
self.setCursor(Qt.CursorShape.OpenHandCursor)
```

- [ ] **Step 6: Restart daemon and test drag**

```bash
bash ~/Development/nudge/start-daemon.sh
sleep 2
python3 ~/Development/nudge/buddy.py show
```

Expected: widget appears. Click and hold the sprite area (top ~52px), drag it around — window follows. Release — `~/.nudge-position` should now exist:

```bash
cat ~/.nudge-position
# Expected: {"x": NNN, "y": NNN}
```

Kill and restart daemon — widget should reappear at dragged position.

- [ ] **Step 7: Commit**

```bash
git add buddy.py
git commit -m "feat: draggable widget with saved position (v27 step 1)"
```

---

### Task 2: Session tracking signals in `buddy.py`

**Files:**
- Modify: `buddy.py` — `SocketServer.run`, add `session_start_signal` / `session_end_signal` / `set_idle_visible_signal`; wire to new `ChipWidget` methods

**Interfaces:**
- Produces:
  - `SocketServer.session_start_signal: pyqtSignal()` 
  - `SocketServer.session_end_signal: pyqtSignal()`
  - `SocketServer.set_idle_visible_signal: pyqtSignal(bool)`
  - `ChipWidget.on_session_start()` 
  - `ChipWidget.on_session_end()`
  - `ChipWidget.on_set_idle_visible(value: bool)`

- [ ] **Step 1: Add three new signals to `SocketServer`**

In `SocketServer` class, after the existing signal declarations (lines ~63-65):

```python
show_signal = pyqtSignal(dict)
hide_signal = pyqtSignal()
cancel_signal = pyqtSignal(str)
session_start_signal = pyqtSignal()
session_end_signal = pyqtSignal()
set_idle_visible_signal = pyqtSignal(bool)
```

- [ ] **Step 2: Handle new commands in `SocketServer.run`**

In the `if/elif` chain inside `SocketServer.run` (after the `cancel` branch, around line 95), add:

```python
elif cmd == "session_start":
    self.session_start_signal.emit()
elif cmd == "session_end":
    self.session_end_signal.emit()
elif cmd == "set_idle_visible":
    self.set_idle_visible_signal.emit(bool(msg.get("value", False)))
```

- [ ] **Step 3: Add session state to `ChipWidget.__init__`**

In `ChipWidget.__init__`, after `self._drag_offset = None`, add:

```python
self._session_count = 0
self._idle_visible = os.path.exists(os.path.expanduser("~/.nudge-idle-visible"))
```

- [ ] **Step 4: Add session handler methods to `ChipWidget`**

Add these three methods after `do_hide`:

```python
def on_session_start(self):
    self._session_count += 1
    if self._idle_visible and not self._requests and not self.isVisible():
        self._show_idle()

def on_session_end(self):
    self._session_count = max(0, self._session_count - 1)
    if self._session_count == 0 and not self._requests:
        self.do_hide()

def on_set_idle_visible(self, value: bool):
    self._idle_visible = value
    if value and self._session_count > 0 and not self._requests and not self.isVisible():
        self._show_idle()
    elif not value and self.isVisible() and not self._requests:
        self.do_hide()

def _show_idle(self):
    """Show widget in idle state: sprite only, no pills."""
    self._container.hide()
    self._badge.hide()
    if not self.isVisible():
        saved_x, saved_y = self._load_saved_position()
        if saved_x is not None:
            self._base_x = saved_x
            self._base_y = saved_y
        else:
            screen = QApplication.primaryScreen().geometry()
            self._base_y = 80
            self._base_x = screen.width() - self.width() - 20
        self.setFixedHeight(self._sprite_h + 10)
        self.move(self._base_x, self._base_y)
        self.show()
        self._pin_to_all_spaces()
        QTimer.singleShot(100, self._pin_to_all_spaces)
        self._bob_tick = 0
        self._bob_timer.start()
```

- [ ] **Step 5: Update `do_show` to restore container when first request arrives during idle**

In `do_show`, replace the `if was_empty:` block to restore the container if it was hidden:

```python
def do_show(self, payload: dict):
    was_empty = len(self._requests) == 0
    self._requests.append(payload)
    if was_empty:
        self._current_index = 0
        self._container.show()
        if not self.isVisible():
            self._position_window()
            self.show()
            self._pin_to_all_spaces()
            QTimer.singleShot(100, self._pin_to_all_spaces)
        try:
            from AppKit import NSApp
            for win in NSApp.windows():
                win.orderFrontRegardless()
        except Exception as e:
            print(f"[buddy] orderFrontRegardless failed: {e}", file=sys.stderr)
        self._bob_tick = 0
        self._bob_timer.start()
    self._rebuild_sessions()
```

- [ ] **Step 6: Update `_remove_by_pipe` and `_cleanup_stale_requests` to return to idle instead of hiding**

In `_remove_by_pipe`, find the `if not self._requests:` block and change:

```python
if not self._requests:
    if self._idle_visible and self._session_count > 0:
        self._show_idle()
    else:
        self.do_hide()
    return
```

In `_cleanup_stale_requests`, find the same `if not self._requests:` block (around line 689-691) and change:

```python
if not self._requests:
    if self._idle_visible and self._session_count > 0:
        self._show_idle()
    else:
        self.do_hide()
    return
```

- [ ] **Step 7: Wire new signals in `run_daemon` at the bottom of the file**

Find the signal connection block (around lines 921-923):

```python
server_thread.show_signal.connect(window.do_show)
server_thread.hide_signal.connect(window.do_hide)
server_thread.cancel_signal.connect(window._on_cancel)
```

Add three more lines after:

```python
server_thread.session_start_signal.connect(window.on_session_start)
server_thread.session_end_signal.connect(window.on_session_end)
server_thread.set_idle_visible_signal.connect(window.on_set_idle_visible)
```

- [ ] **Step 8: Restart daemon and test session signals manually**

```bash
bash ~/Development/nudge/start-daemon.sh
sleep 2
```

Simulate a session_start:
```bash
python3 -c "
import socket, json
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/tmp/claude-buddy.sock')
s.sendall(json.dumps({'cmd': 'session_start'}).encode())
s.close()
"
```

Expected: widget does NOT appear yet (idle_visible toggle is off by default — `~/.nudge-idle-visible` doesn't exist).

Now create the flag and test:
```bash
touch ~/.nudge-idle-visible
python3 -c "
import socket, json
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/tmp/claude-buddy.sock')
s.sendall(json.dumps({'cmd': 'set_idle_visible', 'value': True}).encode())
s.close()
"
```

Expected: sprite appears on screen in idle state (no pill below it).

Simulate session_end:
```bash
python3 -c "
import socket, json
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/tmp/claude-buddy.sock')
s.sendall(json.dumps({'cmd': 'session_end'}).encode())
s.close()
"
```

Expected: widget disappears.

- [ ] **Step 9: Commit**

```bash
git add buddy.py
git commit -m "feat: session tracking and idle sprite state (v27 step 2)"
```

---

### Task 3: Update `notify.sh` with session modes

**Files:**
- Modify: `notify.sh` — add `session_start`, `session_end`, `idle_on`, `idle_off` modes; update `done` mode to send `session_end` via socket

**Interfaces:**
- Produces: `bash notify.sh session_start`, `bash notify.sh session_end`, `bash notify.sh idle_on`, `bash notify.sh idle_off` all send the appropriate socket JSON and exit 0

- [ ] **Step 1: Replace the `done`/non-approval early-exit block with session-aware handling**

At the top of notify.sh, after the `MODE` assignment, find the existing early-exit block:

```bash
if [ "$MODE" != "approval" ]; then
    python3 "$SCRIPT_DIR/buddy.py" hide 2>/dev/null || true
    exit 0
fi
```

Replace it with:

```bash
_send_socket_cmd() {
    python3 -c "
import socket, json, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(sys.argv[1])
    s.sendall(sys.argv[2].encode())
    s.close()
except Exception:
    pass
" "$SOCKET_PATH" "$1" 2>/dev/null || true
}

if [ "$MODE" = "session_start" ]; then
    _send_socket_cmd '{"cmd":"session_start"}'
    exit 0
fi

if [ "$MODE" = "session_end" ] || [ "$MODE" = "done" ]; then
    _send_socket_cmd '{"cmd":"session_end"}'
    exit 0
fi

if [ "$MODE" = "idle_on" ]; then
    touch "$HOME/.nudge-idle-visible"
    _send_socket_cmd '{"cmd":"set_idle_visible","value":true}'
    exit 0
fi

if [ "$MODE" = "idle_off" ]; then
    rm -f "$HOME/.nudge-idle-visible"
    _send_socket_cmd '{"cmd":"set_idle_visible","value":false}'
    exit 0
fi

if [ "$MODE" != "approval" ]; then
    exit 0
fi
```

- [ ] **Step 2: Verify the new modes work**

```bash
bash ~/Development/nudge/start-daemon.sh && sleep 2

bash ~/Development/nudge/notify.sh session_start
# Expected: idle sprite appears if ~/.nudge-idle-visible exists

bash ~/Development/nudge/notify.sh session_end
# Expected: widget hides

bash ~/Development/nudge/notify.sh idle_on
# Now ~/.nudge-idle-visible exists. If a session were active, sprite would show.

bash ~/Development/nudge/notify.sh idle_off
# Expected: ~/.nudge-idle-visible removed

bash ~/Development/nudge/notify.sh done
# Expected: session_end sent (same as session_end mode)
```

- [ ] **Step 3: Commit**

```bash
git add notify.sh
git commit -m "feat: notify.sh session_start/session_end/idle_on/idle_off modes (v27 step 3)"
```

---

### Task 4: Swift — `DaemonController` idle toggle + `NudgeApp` menu item

**Files:**
- Modify: `NudgeApp/Sources/Nudge/DaemonController.swift` — add `idleVisible`, `toggleIdleVisible()`
- Modify: `NudgeApp/Sources/Nudge/NudgeApp.swift` — add menu toggle

**Interfaces:**
- Produces: `DaemonController.idleVisible: Bool` (Published), `DaemonController.toggleIdleVisible()` updates flag file and sends socket command

- [ ] **Step 1: Add `idleVisible` property and `toggleIdleVisible()` to DaemonController**

In `DaemonController.swift`, after the existing `@Published var autoApproveLow: Bool` line, add:

```swift
@Published var idleVisible: Bool
```

After the `private let autoApproveFlagPath: String` line, add:

```swift
private let idleVisibleFlagPath: String
```

In `init()`, after the `autoApproveLow = ...` line, add:

```swift
idleVisibleFlagPath = NSString("~/.nudge-idle-visible").expandingTildeInPath
idleVisible = FileManager.default.fileExists(atPath: idleVisibleFlagPath)
```

Add this new method after `toggleAutoApproveLow()`:

```swift
func toggleIdleVisible() {
    if idleVisible {
        try? FileManager.default.removeItem(atPath: idleVisibleFlagPath)
        runBackground("bash '\(scriptDir)/notify.sh' idle_off")
    } else {
        FileManager.default.createFile(atPath: idleVisibleFlagPath, contents: nil)
        runBackground("bash '\(scriptDir)/notify.sh' idle_on")
    }
    idleVisible.toggle()
}
```

- [ ] **Step 2: Add menu toggle to `NudgeApp.swift`**

In `NudgeApp.swift`, after the existing `Toggle("Auto-approve safe operations", ...)` block, add a new toggle:

```swift
Toggle("Show when idle", isOn: Binding(
    get: { daemon.idleVisible },
    set: { _ in daemon.toggleIdleVisible() }
))
```

- [ ] **Step 3: Build the Swift app**

```bash
cd ~/Development/nudge/NudgeApp && swift build -c release 2>&1 | tail -10
```

Expected: `Build complete!`

- [ ] **Step 4: Bundle and install**

```bash
cd ~/Development/nudge/NudgeApp && bash bundle.sh
```

Expected: `Nudge.app` updated in `NudgeApp/Nudge.app`.

- [ ] **Step 5: Restart the menu bar app**

```bash
osascript -e 'tell application "Nudge" to quit' 2>/dev/null || true
sleep 1
open ~/Development/nudge/NudgeApp/Nudge.app
```

- [ ] **Step 6: Verify menu bar toggle**

Open the menu bar Nudge icon. Expected: new "Show when idle" toggle is present.

Toggle it ON. Expected:
- `~/.nudge-idle-visible` now exists: `ls ~/.nudge-idle-visible`
- If a Claude session is active, idle sprite appears

Toggle it OFF. Expected:
- `~/.nudge-idle-visible` removed
- If widget was in idle state, it hides

- [ ] **Step 7: Commit Swift changes**

```bash
cd ~/Development/nudge
git add NudgeApp/Sources/Nudge/DaemonController.swift NudgeApp/Sources/Nudge/NudgeApp.swift
git commit -m "feat: Show-when-idle menu bar toggle (v27 step 4)"
```

---

### Task 5: Wire Claude Code hooks in `~/.claude/settings.json`

**Files:**
- Modify: `~/.claude/settings.json` (user's settings, not in repo)

**Interfaces:**
- Produces: `SessionStart` hook fires `notify.sh session_start` after daemon start; `SessionEnd` hook fires `notify.sh session_end`

- [ ] **Step 1: Read current hook config**

```bash
python3 -c "
import json, os
with open(os.path.expanduser('~/.claude/settings.json')) as f:
    d = json.load(f)
print(json.dumps(d.get('hooks', {}), indent=2))
"
```

- [ ] **Step 2: Add `session_start` command to `SessionStart` hook**

The `SessionStart` array currently has one entry (the axcli command). Add a second entry after it. Edit `~/.claude/settings.json` — find the `SessionStart` block and add:

```json
"SessionStart": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "/Users/aviadda/.local/bin/axcli _session-start"
      }
    ]
  },
  {
    "hooks": [
      {
        "type": "command",
        "command": "bash ~/Development/nudge/notify.sh session_start"
      }
    ]
  }
]
```

- [ ] **Step 3: Add `session_end` command to `SessionEnd` hook**

The `SessionEnd` array currently has one entry (the axcli command). Add a second:

```json
"SessionEnd": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "/Users/aviadda/.local/bin/axcli _session-end"
      }
    ]
  },
  {
    "hooks": [
      {
        "type": "command",
        "command": "bash ~/Development/nudge/notify.sh session_end"
      }
    ]
  }
]
```

- [ ] **Step 4: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open(os.path.expanduser('~/.claude/settings.json'))); print('valid')"
```

Expected: `valid`

- [ ] **Step 5: End-to-end test**

1. Ensure "Show when idle" is ON in menu bar
2. Start a new Claude Code session (open a new terminal, run `claude` in any directory)
3. Expected: idle sprite appears within 1-2 seconds
4. Trigger a permission request — expected: pill appears below sprite
5. Approve it — expected: pill disappears, sprite stays
6. End the Claude session (`/exit` or Ctrl+C)
7. Expected: sprite disappears

---

### Task 6: Version doc + push

- [ ] **Step 1: Write version doc**

Create `docs/versions/v27-draggable-idle-sprite.md`:

```markdown
# Claude Buddy v27 — Draggable Widget + Idle Sprite

## What Changed from v26

Two new features:

**Draggable position.** The widget can be dragged by clicking and holding the Claude sprite area (top ~52px). Position saves to `~/.nudge-position` on release and is restored on next show. `_reanchor()` no longer snaps back to the right edge after pill height changes — it keeps the user's chosen x.

**Idle sprite mode.** When "Show when idle" is enabled (menu bar toggle), the Claude sprite floats persistently whenever a Claude Code session is active — even with no pending permission requests. The pill container is hidden in idle state. When a permission request arrives, the container appears below the sprite as usual. When the last request resolves, the widget returns to idle (sprite only). When all sessions end, the widget hides entirely.

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

`session_start`, `session_end`, `idle_on`, `idle_off` — all send the appropriate socket command and exit.

## What Stayed the Same

- Permission request flow, pill UI, approve/deny/always buttons
- Risk classification
- Auto-approve low-risk
- Pause/resume behavior
```

- [ ] **Step 2: Commit and push**

```bash
git add docs/versions/v27-draggable-idle-sprite.md
git commit -m "feat: v27 draggable widget + idle sprite"
git pull --rebase origin main && git push origin main
```
