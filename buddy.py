#!/usr/bin/env python3
"""
Claude Buddy -- floating always-on-top overlay that alerts you when Claude needs approval.

Usage:
  python3 buddy.py daemon   -- run the persistent background daemon
  python3 buddy.py show     -- signal daemon to show the buddy
  python3 buddy.py hide     -- signal daemon to hide the buddy
"""

import sys
import os
import json
import socket
import subprocess

SOCKET_PATH = "/tmp/claude-buddy.sock"


def send_command(cmd: str) -> bool:
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(SOCKET_PATH)
        sock.sendall(cmd.encode())
        sock.close()
        return True
    except Exception:
        return False


DECISION_PIPE = "/tmp/claude-buddy-decision"

def _write_decision(decision: str, pipe_path: str = DECISION_PIPE):
    """Write approve/deny to the named pipe that notify.sh is waiting on."""
    import threading
    def _write():
        try:
            with open(pipe_path, "w") as f:
                f.write(decision)
        except Exception as e:
            print(f"[buddy] _write_decision failed: {e}", file=sys.stderr)
    threading.Thread(target=_write, daemon=True).start()


RISK_COLORS = {
    "low":    {"border": "#4CAF50", "bg": "#0a0a0a", "text": "#a5d6a7"},
    "medium": {"border": "#ffaa00", "bg": "#0a0a0a", "text": "#ffe082"},
    "high":   {"border": "#f44336", "bg": "#0a0a0a", "text": "#ef9a9a"},
}


def run_daemon():
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton
    from PyQt6.QtCore import (
        Qt, QThread, pyqtSignal, QRectF, QTimer
    )
    from PyQt6.QtGui import (
        QFont, QFontMetrics, QColor, QPainter, QPainterPath, QPen, QBrush
    )

    class SocketServer(QThread):
        show_signal = pyqtSignal(dict)   # carries payload dict
        hide_signal = pyqtSignal()
        approve_signal = pyqtSignal()
        deny_signal = pyqtSignal()
        cancel_signal = pyqtSignal(str)  # carries pipe path

        def run(self):
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(SOCKET_PATH)
            server.listen(5)
            while True:
                try:
                    conn, _ = server.accept()
                    data = conn.recv(4096).decode().strip()
                    conn.close()
                    try:
                        msg = json.loads(data)
                        cmd = msg.get("cmd", "")
                    except json.JSONDecodeError:
                        cmd = data
                        msg = {}
                    if cmd == "show":
                        self.show_signal.emit(msg)
                    elif cmd == "hide":
                        self.hide_signal.emit()
                    elif cmd == "approve":
                        self.approve_signal.emit()
                    elif cmd == "deny":
                        self.deny_signal.emit()
                    elif cmd == "cancel":
                        self.cancel_signal.emit(msg.get("pipe", ""))
                except Exception:
                    pass

    class SpriteWidget(QWidget):
        """Draws the Claude pixel mascot with sticker effect (white border + drop shadow)."""

        BODY_COLOR   = QColor(0xD6, 0x7E, 0x64)
        BORDER_COLOR = QColor(255, 255, 255)
        EYE_COLOR    = QColor(0x1A, 0x1A, 0x1A)
        SHADOW_COLOR = QColor(0, 0, 0, 60)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        def _build_silhouette(self, unit: float) -> QPainterPath:
            path = QPainterPath()
            path.addRect(QRectF(2*unit, 1*unit, 10*unit, 7*unit))
            path.addRect(QRectF(0.5*unit, 2.5*unit, 1.5*unit, 2*unit))
            path.addRect(QRectF(12*unit, 2.5*unit, 1.5*unit, 2*unit))
            leg_w = 1.8 * unit
            leg_h = 2.5 * unit
            leg_y = 8 * unit
            leg_xs = [2.2, 4.7, 7.2, 9.7]
            for lx in leg_xs:
                path.addRect(QRectF(lx * unit, leg_y, leg_w, leg_h))
            return path.simplified()

        def _build_left_eye(self, unit: float) -> QPainterPath:
            path = QPainterPath()
            path.addRect(QRectF(3.0 * unit, 2.5 * unit, 1.0 * unit, 1.0 * unit))
            return path

        def _build_right_eye(self, unit: float) -> QPainterPath:
            path = QPainterPath()
            path.addRect(QRectF(10.0 * unit, 2.5 * unit, 1.0 * unit, 1.0 * unit))
            return path

        def paintEvent(self, event):
            w = self.width()
            h = self.height()
            unit = min(w / 15.5, h / 12.0)
            char_w = 14 * unit
            char_h = 10.5 * unit
            ox = (w - char_w) / 2
            oy = (h - char_h) / 2

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(ox, oy)

            silhouette = self._build_silhouette(unit)
            left_eye   = self._build_left_eye(unit)
            right_eye  = self._build_right_eye(unit)

            border_width = unit * 0.7
            shadow_offset = unit * 0.4
            painter.save()
            painter.translate(shadow_offset, shadow_offset)
            pen = QPen(self.SHADOW_COLOR)
            pen.setWidthF(border_width * 2.5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(self.SHADOW_COLOR)
            painter.drawPath(silhouette)
            painter.restore()

            pen = QPen(self.BORDER_COLOR)
            pen.setWidthF(border_width * 2)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(self.BORDER_COLOR)
            painter.drawPath(silhouette)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.BODY_COLOR)
            painter.drawPath(silhouette)

            painter.setBrush(self.EYE_COLOR)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(left_eye)
            painter.drawPath(right_eye)

            painter.end()

    class PillWidget(QWidget):
        """The bordered pill background."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._risk = "medium"

        def set_risk(self, risk):
            self._risk = risk
            self.update()

        def paintEvent(self, event):
            colors = RISK_COLORS.get(self._risk, RISK_COLORS["medium"])
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(1, 1, -1, -1)
            path = QPainterPath()
            path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 12, 12)
            painter.fillPath(path, QColor(colors["bg"]))
            pen = QPen(QColor(colors["border"]))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.drawPath(path)
            painter.end()

    class ChipWidget(QWidget):
        """Single chip with multi-session queue support."""

        def __init__(self):
            super().__init__()
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.Tool |
                Qt.WindowType.NoDropShadowWindowHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

            # Request queue
            self._requests = []    # list of payload dicts
            self._current_index = 0

            self._expanded = False
            self._anchor_x = 0

            self.setFixedWidth(200)

            SPRITE_H = 32
            SPRITE_W = 40
            SPRITE_GAP = 14
            BOB_AMP = 8

            # --- Sprite ---
            self.sprite = SpriteWidget(self)
            self.sprite.setFixedSize(SPRITE_W, SPRITE_H)
            self._sprite_rest_y = BOB_AMP
            self.sprite.move((200 - SPRITE_W) // 2, self._sprite_rest_y)
            self.sprite.raise_()

            # --- Pill ---
            self._pill = PillWidget(self)
            self._pill.setFixedWidth(200)
            self._pill_top = BOB_AMP + SPRITE_H + SPRITE_GAP
            self._pill.move(0, self._pill_top)
            self._pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            pill_layout = QVBoxLayout(self._pill)
            pill_layout.setContentsMargins(12, 8, 12, 8)
            pill_layout.setSpacing(0)

            # Source / project label (prominent)
            self._source_label = QLabel("")
            self._source_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #aaa; padding: 0px; margin: 0px;")
            self._source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._source_label.setFixedHeight(16)
            pill_layout.addWidget(self._source_label)

            # Intent label (compact, elided)
            self._intent_label = QLabel("")
            self._intent_label.setStyleSheet("font-size: 12px; padding: 0px; margin: 0px;")
            self._intent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._intent_label.setFixedHeight(18)
            self._intent_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            pill_layout.addWidget(self._intent_label)

            # --- Expanded section ---
            from PyQt6.QtWidgets import QFrame
            self._expanded_widget = QWidget()
            self._expanded_widget.setVisible(False)
            exp_layout = QVBoxLayout(self._expanded_widget)
            exp_layout.setContentsMargins(0, 8, 0, 0)
            exp_layout.setSpacing(8)

            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet("color: #222; background: #222;")
            divider.setFixedHeight(1)
            exp_layout.addWidget(divider)

            self._full_intent_label = QLabel("")
            self._full_intent_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
            self._full_intent_label.setWordWrap(True)
            self._full_intent_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            exp_layout.addWidget(self._full_intent_label)

            self._approve_btn = QPushButton("Yes")
            self._approve_btn.setStyleSheet(
                "background: #2d6a4f; border: 1px solid #40916c; color: #d8f3dc;"
                " border-radius: 6px; padding: 6px; font-size: 11px; font-weight: 600;"
            )
            self._approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._approve_btn.clicked.connect(self._on_approve)
            exp_layout.addWidget(self._approve_btn)

            self._always_allow_btn = QPushButton("Yes, always allow for session")
            self._always_allow_btn.setStyleSheet(
                "background: transparent; border: 1px solid #555; color: #aaa;"
                " border-radius: 6px; padding: 6px; font-size: 11px;"
            )
            self._always_allow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._always_allow_btn.clicked.connect(self._on_always_allow)
            self._always_allow_btn.setVisible(False)
            exp_layout.addWidget(self._always_allow_btn)

            self._deny_btn = QPushButton("No")
            self._deny_btn.setStyleSheet(
                "background: transparent; border: 1px solid #6b2d2d; color: #c97a7a;"
                " border-radius: 6px; padding: 6px; font-size: 11px;"
            )
            self._deny_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._deny_btn.clicked.connect(self._on_deny)
            exp_layout.addWidget(self._deny_btn)

            self._go_btn = QPushButton("Go to session")
            self._go_btn.setStyleSheet(
                "background: transparent; border: none; color: #555;"
                " padding: 4px; font-size: 10px;"
            )
            self._go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._go_btn.clicked.connect(self._on_go_session)
            exp_layout.addWidget(self._go_btn)

            pill_layout.addWidget(self._expanded_widget)

            # Bob animation
            import math
            self._bob_tick = 0
            self._bob_timer = QTimer()
            self._bob_timer.setInterval(30)
            def _bob_step():
                self._bob_tick += 1
                offset = int(BOB_AMP * math.sin(self._bob_tick * 0.12))
                self.sprite.move((200 - SPRITE_W) // 2, self._sprite_rest_y - offset)
            self._bob_timer.timeout.connect(_bob_step)

            # Staleness timer: remove requests whose notify.sh process has died
            # Catches SIGKILL cases where the EXIT trap can't fire
            self._stale_timer = QTimer()
            self._stale_timer.setInterval(1000)
            self._stale_timer.timeout.connect(self._cleanup_stale_requests)
            self._stale_timer.start()

            self.setCursor(Qt.CursorShape.PointingHandCursor)
            QTimer.singleShot(100, self._pin_to_all_spaces)

        # ── Queue helpers ──────────────────────────────────────────────────────

        def _switch_to(self, index: int):
            """Switch displayed request to the given queue index."""
            self._current_index = index
            self._display_request(index)

        def _display_request(self, index: int):
            """Update chip content to show the request at index."""
            if not self._requests:
                return
            req = self._requests[index]
            tool = req.get("tool", "Tool")
            intent = req.get("intent", "Waiting for approval")
            risk = req.get("risk", "medium")
            cwd = req.get("cwd", "")
            suggestions = req.get("suggestions", [])
            mode = req.get("mode", "approval")

            self._pill.set_risk(risk)
            colors = RISK_COLORS.get(risk, RISK_COLORS["medium"])

            self._source_label.setText(cwd)
            self._source_label.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: #aaa; padding: 0px; margin: 0px;"
            )
            self._source_label.setVisible(bool(cwd))

            fm = self._intent_label.fontMetrics()
            available_w = self._pill.width() - 24
            elided = fm.elidedText(intent, Qt.TextElideMode.ElideRight, available_w)
            self._intent_label.setText(elided)
            self._intent_label.setStyleSheet(
                f"font-size: 12px; color: {colors['text']}; padding: 0px; margin: 0px;"
            )

            self._full_intent_label.setText(intent)

            # Always-allow button
            if suggestions:
                s = suggestions[0]
                dest = s.get("destination", "session")
                label = "Yes, always allow for project" if dest == "project" else "Yes, always allow for session"
                self._always_allow_btn.setText(label)
            self._always_allow_btn.setVisible(bool(suggestions))

            # Attention mode: show only go-to-session
            is_attention = mode == "attention"
            self._approve_btn.setVisible(not is_attention)
            self._always_allow_btn.setVisible(not is_attention and bool(suggestions))
            self._deny_btn.setVisible(not is_attention)
            self._go_btn.setVisible(True)
            if is_attention:
                self._go_btn.setStyleSheet(
                    "background: #1a3a4a; border: 1px solid #00bcd4; color: #00bcd4;"
                    " border-radius: 6px; padding: 8px; font-size: 11px; font-weight: 500;"
                )
            else:
                self._go_btn.setStyleSheet(
                    "background: transparent; border: none; color: #555;"
                    " padding: 4px; font-size: 10px;"
                )

            # Only force compact height when not expanded — preserve expanded state on tab switch
            if not self._expanded:
                compact_h = 8 + (16 if cwd else 0) + 18 + 8
                self._pill.setFixedHeight(compact_h)
            self._pill.adjustSize()

        # ── Lifecycle ──────────────────────────────────────────────────────────

        def _cleanup_stale_requests(self):
            """Remove requests whose notify.sh process has exited (including SIGKILL)."""
            if not self._requests:
                return
            stale = []
            for i, req in enumerate(self._requests):
                pid = req.get("notify_pid", 0)
                if not pid:
                    continue
                try:
                    os.kill(pid, 0)  # signal 0 = existence check only
                except OSError:
                    stale.append(i)
            if not stale:
                return
            for i in reversed(stale):
                self._requests.pop(i)
            if not self._requests:
                self.do_hide()
                return
            self._current_index = min(self._current_index, len(self._requests) - 1)
            self._display_request(self._current_index)

        def _apply_risk_style(self):
            if not self._requests:
                return
            req = self._requests[self._current_index]
            risk = req.get("risk", "medium")
            self._pill.set_risk(risk)

        def _position_window(self):
            screen = QApplication.primaryScreen().geometry()
            self._base_y = 80
            self.move(screen.width() - self.width() - 20, self._base_y)

        def do_show(self, payload: dict):
            was_empty = len(self._requests) == 0
            self._requests.append(payload)

            if was_empty:
                self._current_index = 0
                self._collapse()
                self._display_request(0)
                self._position_window()
                self.show()
                self._pin_to_all_spaces()
                try:
                    from AppKit import NSApp
                    for win in NSApp.windows():
                        win.orderFrontRegardless()
                except Exception as e:
                    print(f"[buddy] orderFrontRegardless failed: {e}", file=sys.stderr)
                self._bob_tick = 0
                self._bob_timer.start()

        def do_hide(self):
            self._bob_timer.stop()
            self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
            self._collapse()
            self._requests = []
            self._current_index = 0
            self.hide()

        def _resolve_current(self, decision: str):
            """Write decision for current request and advance queue."""
            if not self._requests:
                return
            req = self._requests[self._current_index]
            pipe = req.get("pipe", DECISION_PIPE)
            _write_decision(decision, pipe)
            self._requests.pop(self._current_index)

            if not self._requests:
                self.do_hide()
                return

            # Clamp index and show next
            self._current_index = min(self._current_index, len(self._requests) - 1)
            self._collapse()
            self._display_request(self._current_index)

        def _expand(self):
            if self._expanded:
                return
            self._expanded = True
            self._pill.setMaximumHeight(16777215)
            self._pill.setMinimumHeight(0)
            self._expanded_widget.setVisible(True)
            self._pill.adjustSize()

        def _collapse(self):
            if not self._expanded:
                return
            self._expanded = False
            self._expanded_widget.setVisible(False)
            if self._requests:
                req = self._requests[self._current_index]
                cwd = req.get("cwd", "")
                compact_h = 8 + (16 if cwd else 0) + 18 + 8
                self._pill.setFixedHeight(compact_h)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                if self._expanded:
                    self._collapse()
                    self._bob_timer.start()
                else:
                    self._bob_timer.stop()
                    self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
                    self._expand()
            super().mousePressEvent(event)

        # ── Actions ────────────────────────────────────────────────────────────

        def _on_go_session(self):
            """Focus terminal for current request — no decision written, widget stays."""
            self._focus_terminal()

        def _on_cancel(self, pipe_path: str):
            """Remove a request from the queue when its notify.sh was interrupted."""
            for i, req in enumerate(self._requests):
                if req.get("pipe", "") == pipe_path:
                    self._requests.pop(i)
                    if not self._requests:
                        self.do_hide()
                        return
                    self._current_index = min(self._current_index, len(self._requests) - 1)
                    self._collapse()
                    self._display_request(self._current_index)
                    return

        def _on_approve(self):
            self._resolve_current("approve")

        def _on_deny(self):
            self._resolve_current("deny")

        def _on_always_allow(self):
            self._resolve_current("always_allow")

        # ── Terminal focus ─────────────────────────────────────────────────────

        def _focus_terminal(self):
            if not self._requests:
                return
            req = self._requests[self._current_index]
            claude_uuid = req.get("iterm_session", "")
            if claude_uuid:
                claude_uuid = claude_uuid.split(":")[1] if ":" in claude_uuid else claude_uuid
                script = f'''
tell application "iTerm2"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if unique ID of s is "{claude_uuid}" then
          tell t to select
          tell w to select
          return
        end if
      end repeat
    end repeat
  end repeat
end tell
'''
                subprocess.run(["osascript", "-e", script], capture_output=True)
                return
            for app in ["Terminal", "Warp", "Alacritty", "Hyper", "iTerm2"]:
                result = subprocess.run(
                    ["osascript", "-e", f'tell application "System Events" to return (name of processes) contains "{app}"'],
                    capture_output=True, text=True
                )
                if result.stdout.strip() == "true":
                    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], capture_output=True)
                    return

        # ── All-spaces pinning ─────────────────────────────────────────────────

        def _pin_to_all_spaces(self):
            try:
                from AppKit import (
                    NSApp,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorMoveToActiveSpace,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                )
                for win in NSApp.windows():
                    behavior = win.collectionBehavior()
                    behavior &= ~NSWindowCollectionBehaviorMoveToActiveSpace
                    behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
                    behavior |= NSWindowCollectionBehaviorFullScreenAuxiliary
                    win.setCollectionBehavior_(behavior)
            except Exception as e:
                print(f"[buddy] _pin_to_all_spaces failed: {e}", file=sys.stderr)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = ChipWidget()

    server_thread = SocketServer()
    server_thread.show_signal.connect(window.do_show)
    server_thread.hide_signal.connect(window.do_hide)
    server_thread.approve_signal.connect(window._on_approve)
    server_thread.deny_signal.connect(window._on_deny)
    server_thread.cancel_signal.connect(window._on_cancel)
    server_thread.daemon = True
    server_thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daemon"

    if mode == "daemon":
        run_daemon()
    elif mode in ("show", "hide"):
        success = send_command(mode)
        sys.exit(0 if success else 1)
    else:
        print(f"Usage: buddy.py [daemon|show|hide]")
        sys.exit(1)
