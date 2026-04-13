# Claude Buddy v1 — Show/Hide Overlay

**Status:** Superseded by v2
**Architecture:** Single fixed-size floating window, plain socket protocol

---

## What It Did

A PyQt6 always-on-top frameless window showing only the pixel Claude mascot sprite — nothing else. No text, no risk color, no intent, no buttons. It appeared when Claude Code needed tool approval and disappeared when done. The only information it conveyed was "Claude is waiting for something."

The sprite was clickable: clicking it focused the active Claude Code terminal session (iTerm2 session by UUID if available, otherwise the first matching terminal app). This was the only interactive feature in v1.

---

## How It Worked

### notify.sh
* Called by the `PermissionRequest` hook with `approval` argument, and by the `Stop` hook with `done`
* On `approval`: sent `show` to the Unix socket, then immediately returned `{"decision": "allow"}` — no waiting, no user input
* On `done`: sent `hide` to the socket

### buddy.py daemon
* Listened on `/tmp/claude-buddy.sock`
* Socket protocol: plain strings — `"show"` or `"hide"` (read 64 bytes max)
* `BuddyWindow`: fixed 64×53px frameless window, always-on-top, all-spaces pinned
* On `show`: displayed the window with a bobbing animation (QPropertyAnimation on position)
* On `hide`: hid the window

### SpriteWidget
* Custom QPainter drawing of the Claude pixel mascot
* Body, arms, 4 legs, 2 eyes — drawn as QPainterPaths
* White sticker border + drop shadow effect
* Unchanged across all versions

---

## File Snapshot

### notify.sh (v1)
```bash
#!/bin/bash
MODE="${1:-approval}"
if [ "$MODE" != "approval" ]; then
    python3 ~/Development/nudge/buddy.py hide 2>/dev/null
    exit 0
fi
python3 ~/Development/nudge/buddy.py show 2>/dev/null
echo '{"decision": "allow"}'
```

### buddy.py (v1) — key classes

**SocketServer:**
```python
class SocketServer(QThread):
    show_signal = pyqtSignal()
    hide_signal = pyqtSignal()

    def run(self):
        # removes existing socket, binds, listens
        while True:
            conn, _ = server.accept()
            data = conn.recv(64).decode().strip()
            conn.close()
            if data == "show":
                self.show_signal.emit()
            elif data == "hide":
                self.hide_signal.emit()
```

**BuddyWindow:**
```python
class BuddyWindow(QWidget):
    # Fixed 64x53 frameless always-on-top window
    # SpriteWidget fills the window
    # QPropertyAnimation bobs the window up/down 10px, 900ms, infinite loop
    # _pin_to_all_spaces() via AppKit NSWindowCollectionBehaviorCanJoinAllSpaces
    # mousePressEvent → _focus_terminal(): focuses iTerm2 session by UUID, or fallback terminal app
```

---

## Limitations That Led to v2

* Just the sprite — no text, no context, no color coding
* Clicking the sprite focused the terminal, but the user still had to read the approval prompt and type a response there — the widget itself had no approval surface
* Approval was automatic — notify.sh returned `allow` immediately without waiting for user input
* Plain socket protocol carried no metadata (just "show" / "hide")
* No named pipe — no mechanism to communicate a decision back from the widget
