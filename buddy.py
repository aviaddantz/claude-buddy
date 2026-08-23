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
import signal
import time

SOCKET_PATH = "/tmp/claude-buddy.sock"
SESSIONS_FILE = os.path.expanduser("~/.nudge-sessions.json")
SESSIONS_STALE_SECS = 4 * 3600


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
        Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer, QEvent, QObject
    )
    from PyQt6.QtGui import (
        QFont, QFontMetrics, QColor, QPainter, QPainterPath, QPen, QBrush
    )

    class SocketServer(QThread):
        show_signal = pyqtSignal(dict)   # carries payload dict
        hide_signal = pyqtSignal()
        cancel_signal = pyqtSignal(str)  # carries pipe path
        session_start_signal = pyqtSignal(dict)
        session_end_signal = pyqtSignal(str)  # carries session_id
        set_idle_visible_signal = pyqtSignal(bool)
        set_sessions_enabled_signal = pyqtSignal(bool)
        thinking_start_signal = pyqtSignal(str)  # carries session_id
        thinking_stop_signal = pyqtSignal(str)   # carries session_id

        def run(self):
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(SOCKET_PATH)
            server.listen(5)
            while True:
                try:
                    conn, _ = server.accept()
                    chunks = []
                    while True:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    data = b"".join(chunks).decode().strip()
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
                    elif cmd == "cancel":
                        self.cancel_signal.emit(msg.get("pipe", ""))
                    elif cmd == "session_start":
                        self.session_start_signal.emit(msg)
                    elif cmd == "session_end":
                        self.session_end_signal.emit(msg.get("session_id", ""))
                    elif cmd == "set_idle_visible":
                        self.set_idle_visible_signal.emit(bool(msg.get("value", False)))
                    elif cmd == "set_sessions_enabled":
                        self.set_sessions_enabled_signal.emit(bool(msg.get("value", True)))
                    elif cmd == "thinking_start":
                        self.thinking_start_signal.emit(msg.get("session_id", ""))
                    elif cmd == "thinking_stop":
                        self.thinking_stop_signal.emit(msg.get("session_id", ""))
                except Exception:
                    pass

    class SpriteWidget(QWidget):
        """Draws the Claude pixel mascot with sticker effect (white border + drop shadow)."""

        BODY_COLOR   = QColor(0xD6, 0x7E, 0x64)
        BORDER_COLOR = QColor(255, 255, 255)
        EYE_COLOR    = QColor(0x1A, 0x1A, 0x1A)
        SHADOW_COLOR = QColor(0, 0, 0, 60)
        ROPE_COLOR   = QColor(0x66, 0xBB, 0x6A)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._rope_angle = 0.0
            self.show_rope = True

        def hit_rect(self):
            """Tight rect covering just the character body (excludes transparent rope area above)."""
            w = self.width()
            h = self.height()
            unit = w / 15.5
            char_h = 10.5 * unit
            oy = int(h - char_h - unit)
            return self.geometry().adjusted(0, oy, 0, 0)

        def set_rope_angle(self, angle: float):
            self._rope_angle = angle
            self.update()

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

        def _draw_rope(self, painter: QPainter, unit: float):
            import math
            left_x = 0.0 * unit
            right_x = 13.5 * unit
            hand_y = 3.5 * unit
            ctrl_x = 7.0 * unit
            arc_radius = 12.0 * unit
            ctrl_y = hand_y + math.sin(self._rope_angle) * arc_radius

            pen = QPen(self.ROPE_COLOR)
            pen.setWidthF(unit * 0.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            path = QPainterPath()
            path.moveTo(QPointF(left_x, hand_y))
            path.quadTo(QPointF(ctrl_x, ctrl_y), QPointF(right_x, hand_y))
            painter.drawPath(path)

        def paintEvent(self, event):
            w = self.width()
            h = self.height()
            unit = w / 15.5
            char_w = 14 * unit
            char_h = 10.5 * unit
            ox = (w - char_w) / 2
            oy = h - char_h - unit

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

            if self.show_rope:
                self._draw_rope(painter, unit)

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

    class _SessionPill(QWidget):
        """Self-contained pill for one pending session request."""

        approved      = pyqtSignal(str)        # pipe path
        denied        = pyqtSignal(str)        # pipe path
        always        = pyqtSignal(str, str)   # pipe path, destination ("session"/"project")
        go_session    = pyqtSignal(str, str)   # iterm_session, term_program
        activated     = pyqtSignal(int)        # index within parent queue
        expand_changed = pyqtSignal(bool)      # True=expanded, False=collapsed

        def __init__(self, req: dict, index: int, is_active: bool, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._req = req
            self._index = index
            self._is_active = is_active
            self._expanded = False  # always starts collapsed; click to expand

            self.setFixedWidth(200)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # ── Pill background widget ──────────────────────────────────────────
            self._pill_bg = PillWidget(self)
            self._pill_bg.setFixedWidth(200)
            risk = req.get("risk", "medium")
            self._pill_bg.set_risk(risk)
            root.addWidget(self._pill_bg)

            pill_layout = QVBoxLayout(self._pill_bg)
            pill_layout.setContentsMargins(12, 8, 12, 8)
            pill_layout.setSpacing(0)

            # Project / cwd label
            cwd = req.get("cwd", "")
            self._source_label = QLabel(cwd)
            colors = RISK_COLORS.get(risk, RISK_COLORS["medium"])
            self._source_label.setStyleSheet(
                "font-size: 10px; font-weight: 400; color: #666;"
                " padding: 0px; margin: 0px;"
            )
            self._source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._source_label.setFixedHeight(16)
            self._source_label.setVisible(bool(cwd))
            pill_layout.addWidget(self._source_label)

            # Intent (compact, elided)
            intent = req.get("intent", "Waiting for approval")
            self._intent_label = QLabel()
            self._intent_label.setStyleSheet(
                f"font-size: 12px; color: {colors['text']}; padding: 0px; margin: 0px;"
            )
            self._intent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._intent_label.setFixedHeight(18)
            self._intent_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            fm = self._intent_label.fontMetrics()
            # Elide at word boundary instead of mid-character
            elided = fm.elidedText(intent, Qt.TextElideMode.ElideRight, 200 - 24)
            if elided != intent and " " in intent:
                # Qt cut mid-word — find last space before the cut point
                cut_len = len(elided.rstrip("\u2026"))
                boundary = intent[:cut_len].rfind(" ")
                if boundary > 0:
                    elided = intent[:boundary] + "\u2026"
            self._intent_label.setText(elided)
            pill_layout.addWidget(self._intent_label)

            # ── Expanded section ────────────────────────────────────────────────
            from PyQt6.QtWidgets import QFrame
            self._expanded_widget = QWidget()
            self._expanded_widget.setVisible(self._expanded)
            exp_layout = QVBoxLayout(self._expanded_widget)
            exp_layout.setContentsMargins(0, 8, 0, 0)
            exp_layout.setSpacing(8)

            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet("color: #222; background: #222;")
            divider.setFixedHeight(1)
            exp_layout.addWidget(divider)

            # ── Command display (Bash only) ─────────────────────────────────────
            tool_input = req.get("tool_input", {})
            raw_cmd = tool_input.get("command", "").strip() if isinstance(tool_input, dict) else ""
            if req.get("tool", "").lower() == "bash" and raw_cmd:
                # Truncated command — single dim monospace line
                cmd_short = QLabel(raw_cmd)
                cmd_short.setStyleSheet(
                    "font-size: 10px; color: #666; font-family: monospace;"
                    " padding: 0px; margin: 0px;"
                )
                cmd_short.setAlignment(Qt.AlignmentFlag.AlignLeft)
                cmd_short.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                cmd_short.setFixedHeight(14)
                fm_cmd = cmd_short.fontMetrics()
                elided_cmd = fm_cmd.elidedText(raw_cmd, Qt.TextElideMode.ElideRight, 176)
                cmd_short.setText(elided_cmd)
                exp_layout.addWidget(cmd_short)

                # Full command block (hidden by default) — inserted before toggle so toggle stays last
                cmd_full = QLabel(raw_cmd)
                cmd_full.setStyleSheet(
                    "font-size: 10px; color: #888; font-family: monospace;"
                    " background: #0a0a0a; border-radius: 4px; padding: 4px;"
                )
                cmd_full.setWordWrap(True)
                cmd_full.setVisible(False)
                exp_layout.addWidget(cmd_full)

                # Toggle label — always last, always visible
                toggle_lbl = QLabel("show full ▾")
                toggle_lbl.setStyleSheet(
                    "font-size: 10px; color: #444; padding: 0px; margin: 0px;"
                )
                toggle_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                toggle_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                toggle_lbl.setFixedHeight(14)
                exp_layout.addWidget(toggle_lbl)

                # Wire toggle — resize only this pill via targeted method
                def _make_toggle(short, full, lbl, pill_ref):
                    def _toggle(event):
                        if full.isVisible():
                            full.setVisible(False)
                            short.setVisible(True)
                            lbl.setText("show full ▾")
                        else:
                            full.setVisible(True)
                            short.setVisible(False)
                            lbl.setText("hide full ▴")
                        chip = pill_ref.window()
                        if hasattr(chip, "_update_window_size_for_pill"):
                            chip._update_window_size_for_pill(pill_ref)
                            chip._reanchor()
                    return _toggle
                toggle_lbl.mousePressEvent = _make_toggle(cmd_short, cmd_full, toggle_lbl, self)

            mode = req.get("mode", "approval")
            is_attention = mode == "attention"

            approve_btn = QPushButton("Yes")
            approve_btn.setStyleSheet(
                "background: #2d6a4f; border: 1px solid #40916c; color: #d8f3dc;"
                " border-radius: 6px; padding: 6px; font-size: 11px; font-weight: 600;"
            )
            approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            approve_btn.setVisible(not is_attention)
            approve_btn.clicked.connect(lambda: self.approved.emit(req.get("pipe", DECISION_PIPE)))
            exp_layout.addWidget(approve_btn)

            suggestions = req.get("suggestions", [])
            if suggestions:
                dest = suggestions[0].get("destination", "session")
                always_label = "Yes, always allow for project" if dest == "project" else "Yes, always allow for session"
                always_btn = QPushButton(always_label)
                always_btn.setStyleSheet(
                    "background: transparent; border: 1px solid #555; color: #aaa;"
                    " border-radius: 6px; padding: 6px; font-size: 11px;"
                )
                always_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                always_btn.setVisible(not is_attention)
                always_btn.clicked.connect(
                    lambda: self.always.emit(req.get("pipe", DECISION_PIPE), dest)
                )
                exp_layout.addWidget(always_btn)

            deny_btn = QPushButton("No")
            deny_btn.setStyleSheet(
                "background: transparent; border: 1px solid #6b2d2d; color: #c97a7a;"
                " border-radius: 6px; padding: 6px; font-size: 11px;"
            )
            deny_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            deny_btn.setVisible(not is_attention)
            deny_btn.clicked.connect(lambda: self.denied.emit(req.get("pipe", DECISION_PIPE)))
            exp_layout.addWidget(deny_btn)

            if is_attention:
                go_style = (
                    "background: #1a3a4a; border: 1px solid #00bcd4; color: #00bcd4;"
                    " border-radius: 6px; padding: 8px; font-size: 11px; font-weight: 500;"
                )
            else:
                go_style = (
                    "background: transparent; border: none; color: #555;"
                    " padding: 4px; font-size: 10px;"
                )
            _TERM_LABELS = {
                "iterm.app":      "Go to session",
                "apple_terminal": "Open Terminal",
                "warpterminal":   "Open Warp",
                "hyper":          "Open Hyper",
                "ghostty":        "Open Ghostty",
                "vscode":         "Open VS Code",
                "cursor":         "Open Cursor",
            }
            if req.get("iterm_session"):
                _go_label = "Go to session"
            else:
                _go_label = _TERM_LABELS.get(req.get("term_program", "").lower(), "Open Claude")
            go_btn = QPushButton(_go_label)
            go_btn.setStyleSheet(go_style)
            go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            go_btn.clicked.connect(
                lambda: self.go_session.emit(
                    req.get("iterm_session", ""),
                    req.get("term_program", ""),
                )
            )
            exp_layout.addWidget(go_btn)

            pill_layout.addWidget(self._expanded_widget)


            # ── Inactive dimming (stylesheet-only; PillWidget border is QPainter) ──
            if not is_active:
                self._source_label.setStyleSheet(
                    "font-size: 10px; font-weight: 400; color: #444; padding: 0px; margin: 0px;"
                )
                self._intent_label.setStyleSheet(
                    "font-size: 12px; color: #444; padding: 0px; margin: 0px;"
                )

        def enterEvent(self, event):
            if not self._is_active:
                self._source_label.setStyleSheet(
                    "font-size: 10px; font-weight: 400; color: #777; padding: 0px; margin: 0px;"
                )
                self._intent_label.setStyleSheet(
                    "font-size: 12px; color: #777; padding: 0px; margin: 0px;"
                )
            super().enterEvent(event)

        def leaveEvent(self, event):
            if not self._is_active:
                self._source_label.setStyleSheet(
                    "font-size: 10px; font-weight: 400; color: #444; padding: 0px; margin: 0px;"
                )
                self._intent_label.setStyleSheet(
                    "font-size: 12px; color: #444; padding: 0px; margin: 0px;"
                )
            super().leaveEvent(event)

        def toggle_expand(self):
            self._expanded = not self._expanded
            self._expanded_widget.setVisible(self._expanded)
            self._pill_bg.adjustSize()
            self.adjustSize()
            self.expand_changed.emit(self._expanded)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                if self._is_active:
                    self.toggle_expand()
                else:
                    self.activated.emit(self._index)
            super().mousePressEvent(event)

    class _GlobalClickFilter(QObject):
        """Catches clicks within the Qt app while session rows are visible."""
        def __init__(self, widget, callback):
            super().__init__()
            self._widget = widget
            self._callback = callback

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.MouseButtonPress:
                try:
                    gpos = event.globalPosition().toPoint()
                except AttributeError:
                    gpos = event.globalPos()
                if not self._widget.geometry().contains(gpos):
                    self._callback()
            return False

    class _SessionRowWidget(QWidget):
        clicked = pyqtSignal(dict)

        def __init__(self, session: dict, parent=None):
            super().__init__(parent)
            self._session = session
            self._hovered = False
            self.setFixedHeight(28)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(8, 0, 8, 0)
            layout.setSpacing(5)

            dot = QWidget()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet("background: #4CAF50; border-radius: 3px;")
            layout.addWidget(dot)

            folder = session.get("folder", "?")
            intent = session.get("intent", "")

            folder_lbl = QLabel(folder)
            folder_lbl.setStyleSheet(
                "color: #9c8aff; font-size: 11px; font-weight: 600; background: transparent;"
            )
            folder_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            layout.addWidget(folder_lbl)

            if intent:
                sep_lbl = QLabel("|")
                sep_lbl.setStyleSheet("color: #444; font-size: 11px; background: transparent;")
                sep_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
                layout.addWidget(sep_lbl)

                intent_lbl = QLabel()
                intent_lbl.setStyleSheet("color: #777; font-size: 11px; background: transparent;")
                intent_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                # Pre-elide to 130px — intent label gets ~130px after folder and sep
                fm = intent_lbl.fontMetrics()
                intent_lbl.setText(fm.elidedText(intent, Qt.TextElideMode.ElideRight, 130))
                layout.addWidget(intent_lbl, 1)
            else:
                layout.addStretch(1)

        def paintEvent(self, event):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            bg = QColor("#242424") if self._hovered else QColor("#1a1a1a")
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), 4, 4)
            p.fillPath(path, QBrush(bg))
            p.fillRect(0, 0, 2, self.height(), QColor("#7c6af7"))
            p.end()

        def enterEvent(self, event):
            self._hovered = True
            self.update()
            super().enterEvent(event)

        def leaveEvent(self, event):
            self._hovered = False
            self.update()
            super().leaveEvent(event)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self._session)
            super().mousePressEvent(event)

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

            self.setFixedWidth(209)  # 200px pill area + 9px badge overhang on right

            SPRITE_H = 52
            SPRITE_W = 40
            BOB_AMP = 8

            # Request queue
            self._requests = []
            self._current_index = 0
            self._base_x = 0
            self._base_y = 80
            self._drag_offset = None
            self._session_count = 0
            self._sessions: dict = {}  # keyed by session_id, value is session payload dict
            self._session_rows_visible = False
            self._click_filter = None
            self._ns_monitor = None
            self._sessions_enabled = not os.path.exists(os.path.expanduser("~/.nudge-sessions-disabled"))
            self._idle_visible = os.path.exists(os.path.expanduser("~/.nudge-idle-visible"))
            self._thinking_sessions: set = set()
            self._flip_pills_h = 0  # extra Y offset added to sprite when pills are shown above it

            # --- Sprite ---
            self.sprite = SpriteWidget(self)
            self.sprite.setFixedSize(SPRITE_W, SPRITE_H)
            self._sprite_rest_y = BOB_AMP
            self.sprite.move((200 - SPRITE_W) // 2, self._sprite_rest_y)
            self.sprite.raise_()

            self._sprite_h = BOB_AMP + SPRITE_H + 14  # top of sessions container (14px gap below sprite)

            # --- Sessions container ---
            self._container = QWidget(self)
            self._container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._container.move(0, self._sprite_h)
            self._container_layout = QVBoxLayout(self._container)
            self._container_layout.setContentsMargins(0, 0, 0, 0)
            self._container_layout.setSpacing(6)

            # --- Session rows (shown on double-click, above pills) ---
            self._session_rows_container = QWidget(self)
            self._session_rows_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._session_rows_container.setFixedWidth(200)
            self._session_rows_container.move(0, self._sprite_h)
            self._session_rows_container.hide()
            self._session_rows_layout = QVBoxLayout(self._session_rows_container)
            self._session_rows_layout.setContentsMargins(4, 0, 4, 8)
            self._session_rows_layout.setSpacing(5)

            # --- Count badge (window-level, floats at top-right corner of first pill) ---
            self._badge = QLabel("")
            self._badge.setParent(self)
            self._badge.setFixedSize(18, 18)
            self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._badge.setStyleSheet(
                "background: #f44336; color: white; font-size: 10px; font-weight: 700;"
                " border-radius: 9px;"
            )
            # Centered on top-right corner of first pill: pill right=200, pill top=_sprite_h
            self._badge.move(200 - 9, self._sprite_h - 9)
            self._badge.hide()
            self._badge.raise_()

            # Bob animation
            import math
            self._bob_tick = 0
            self._bob_timer = QTimer()
            self._bob_timer.setInterval(30)
            def _bob_step():
                self._bob_tick += 1
                offset = int(BOB_AMP * math.sin(self._bob_tick * 0.12))
                self.sprite.move((200 - SPRITE_W) // 2, self._flip_pills_h + self._sprite_rest_y - offset)
                self.sprite.set_rope_angle(self._bob_tick * 0.12)
            self._bob_timer.timeout.connect(_bob_step)

            # Staleness timer
            self._stale_timer = QTimer()
            self._stale_timer.setInterval(500)
            self._stale_timer.timeout.connect(self._cleanup_stale_requests)
            self._stale_timer.start()

            self.setMouseTracking(True)
            self.winId()  # Force NSWindow creation now so the pin timer finds it
            QTimer.singleShot(100, self._pin_to_all_spaces)
            if self._idle_visible:
                QTimer.singleShot(500, self._show_idle)

        # ── Layout helpers ─────────────────────────────────────────────────────

        def _compute_flip(self):
            screen = QApplication.primaryScreen().geometry()
            return self._base_y > screen.height() * 0.55

        def _apply_flip_layout(self, total_pills_h, rows_h=0):
            """Reposition container, badge, and sprite based on whether the widget is in the lower screen half."""
            if self._compute_flip() and total_pills_h > 0:
                self._flip_pills_h = total_pills_h + rows_h
                self._container.move(0, 0)
                self._badge.move(200 - 9, -9)
            else:
                self._flip_pills_h = 0
                self._container.move(0, self._sprite_h + rows_h)
                self._badge.move(200 - 9, self._sprite_h + rows_h - 9)
            self.sprite.move((200 - 40) // 2, self._flip_pills_h + self._sprite_rest_y)

        def _update_window_size(self):
            total_pills_h = 0
            for i in range(self._container_layout.count()):
                item = self._container_layout.itemAt(i)
                if item and item.widget():
                    item.widget().adjustSize()
                    total_pills_h += item.widget().sizeHint().height()
            spacing = self._container_layout.spacing()
            n = self._container_layout.count()
            total_pills_h += spacing * max(n - 1, 0)
            self._container.setFixedSize(200, max(total_pills_h, 1))
            rows_h = self._session_rows_container.height() if self._session_rows_visible else 0
            total_h = self._sprite_h + rows_h + total_pills_h
            self.setFixedHeight(max(total_h, self._sprite_h + 10))
            self._apply_flip_layout(total_pills_h, rows_h)

        def _update_window_size_for_pill(self, pill):
            """Resize window after a single pill's internal height changed, without touching other pills."""
            pill.adjustSize()
            total_pills_h = 0
            for i in range(self._container_layout.count()):
                item = self._container_layout.itemAt(i)
                if item and item.widget():
                    total_pills_h += item.widget().sizeHint().height()
            spacing = self._container_layout.spacing()
            n = self._container_layout.count()
            total_pills_h += spacing * max(n - 1, 0)
            self._container.setFixedSize(200, max(total_pills_h, 1))
            rows_h = self._session_rows_container.height() if self._session_rows_visible else 0
            total_h = self._sprite_h + rows_h + total_pills_h
            self.setFixedHeight(max(total_h, self._sprite_h + 10))
            self._apply_flip_layout(total_pills_h, rows_h)

        # ── Sessions ───────────────────────────────────────────────────────────

        def _rebuild_sessions(self):
            """Clear and repopulate the sessions container with _SessionPill widgets."""
            # Remove existing pills
            while self._container_layout.count():
                item = self._container_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not self._requests:
                self._update_window_size()
                return

            n = len(self._requests)
            # Update window-level badge
            if n > 1:
                self._badge.setText(str(n))
                self._badge.show()
                self._badge.raise_()
            else:
                self._badge.hide()

            for i, req in enumerate(self._requests):
                is_active = (i == self._current_index)
                pill = _SessionPill(req, i, is_active)

                # Wire signals
                pill.approved.connect(self._on_pill_approved)
                pill.denied.connect(self._on_pill_denied)
                pill.always.connect(self._on_pill_always)
                pill.go_session.connect(self._on_pill_go_session)
                pill.activated.connect(self._on_pill_activated)
                if is_active:
                    pill.expand_changed.connect(self._on_active_pill_expand_changed)

                self._container_layout.addWidget(pill)

            self._update_window_size()
            if self.isVisible():
                self._reanchor()

        def _repopulate_session_rows_layout(self):
            """Clear and refill the session rows layout from self._sessions."""
            while self._session_rows_layout.count():
                item = self._session_rows_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for session in self._sessions.values():
                row = _SessionRowWidget(session)
                row.clicked.connect(self._on_session_row_clicked)
                self._session_rows_layout.addWidget(row)

        def _rebuild_session_rows(self):
            """Repopulate session rows from self._sessions. Auto-hides if store is empty."""
            self._repopulate_session_rows_layout()
            if not self._sessions and self._session_rows_visible:
                self._hide_session_rows()
            elif self._session_rows_visible:
                self._session_rows_container.adjustSize()
                rows_h = self._session_rows_container.sizeHint().height()
                self._session_rows_container.setFixedHeight(rows_h)
                self._container.move(0, self._sprite_h + rows_h)
                self._update_window_size()

        def _refresh_session_intents(self):
            """Re-read intents from transcripts for sessions that still have an empty intent."""
            changed = False
            for sess in self._sessions.values():
                if sess.get('intent') or not sess.get('transcript_path'):
                    continue
                tp = sess['transcript_path']
                try:
                    with open(tp, 'r', errors='replace') as f:
                        for line in f:
                            try:
                                d = json.loads(line)
                                if d.get('type') != 'user':
                                    continue
                                content = d.get('message', {}).get('content', '')
                                text = ''
                                if isinstance(content, list):
                                    for c in content:
                                        if isinstance(c, dict) and c.get('type') == 'text':
                                            text = c['text'].strip()
                                            break
                                elif isinstance(content, str):
                                    text = content.strip()
                                if text and not text.startswith('<') and not text.startswith('['):
                                    sess['intent'] = text[:80]
                                    changed = True
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass
            if changed:
                try:
                    with open(SESSIONS_FILE, 'w') as f:
                        json.dump(self._sessions, f)
                except Exception:
                    pass

        def _deferred_intent_refresh(self, session_id: str):
            sess = self._sessions.get(session_id)
            if not sess or sess.get('intent'):
                return
            self._refresh_session_intents()
            if self._session_rows_visible:
                self._rebuild_session_rows()

        def _show_session_rows(self):
            if self._session_rows_visible:
                return  # already shown, avoid double-installing click filter
            if not self._sessions:
                return
            self._refresh_session_intents()
            self._repopulate_session_rows_layout()
            self._session_rows_container.adjustSize()
            rows_h = self._session_rows_container.sizeHint().height()
            self._session_rows_container.setFixedHeight(rows_h)
            self._session_rows_container.move(0, self._sprite_h)
            self._session_rows_container.show()
            self._session_rows_visible = True
            self._container.move(0, self._sprite_h + rows_h)
            self._update_window_size()
            if not self.isVisible():
                self._position_window()
                self.show()
                self._pin_to_all_spaces()
            self._click_filter = _GlobalClickFilter(self, self._hide_session_rows)
            QApplication.instance().installEventFilter(self._click_filter)
            # Also catch clicks in other apps via NSEvent global monitor
            try:
                from AppKit import NSEvent
                NSLeftMouseDown = 1 << 1
                def _ns_handler(ns_evt):
                    QTimer.singleShot(0, self._hide_session_rows)
                self._ns_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                    NSLeftMouseDown, _ns_handler)
            except Exception:
                self._ns_monitor = None

        def _hide_session_rows(self):
            self._session_rows_container.hide()
            self._session_rows_visible = False
            self._container.move(0, self._sprite_h)
            self._update_window_size()
            if self._click_filter:
                QApplication.instance().removeEventFilter(self._click_filter)
                self._click_filter = None
            if getattr(self, '_ns_monitor', None) is not None:
                try:
                    from AppKit import NSEvent
                    NSEvent.removeMonitor_(self._ns_monitor)
                except Exception:
                    pass
                self._ns_monitor = None
            if self._requests:
                return  # approval pills are showing, leave widget as-is
            if self._idle_visible and self._session_count > 0:
                self._show_idle()
            else:
                self.do_hide()

        def _on_session_row_clicked(self, session: dict):
            iterm_session_id = session.get("iterm_session_id", "")
            source = session.get("source", "unknown")
            cwd = session.get("cwd", "")
            session_id = session.get("session_id", "")
            self._focus_terminal_with_session(iterm_session_id, source=source, cwd=cwd,
                                               session_id=session_id)
            self._hide_session_rows()

        # ── Lifecycle ──────────────────────────────────────────────────────────

        def _cleanup_stale_requests(self):
            """Remove requests whose notify.sh process has exited."""
            if not self._requests:
                return
            stale = []
            for i, req in enumerate(self._requests):
                pipe_path = req.get("pipe", "")
                pid = req.get("notify_pid", 0)

                # Fast path: pipe file removed = EXIT trap ran, request resolved
                if pipe_path and not os.path.exists(pipe_path):
                    stale.append(i)
                    continue

                if not pid:
                    continue

                # Process fully dead
                try:
                    os.kill(pid, 0)
                except OSError:
                    stale.append(i)
                    continue

                # Zombie detection: os.kill(0) succeeds for zombies
                try:
                    result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "state="],
                        capture_output=True, text=True, timeout=1
                    )
                    if result.stdout.strip().startswith("Z"):
                        stale.append(i)
                        continue
                except Exception:
                    pass

                # Transcript-mtime stale: Claude Code ran the tool without waiting for
                # the hook (user responded natively). When the tool result is written,
                # the transcript mtime advances past what we recorded at queue time.
                transcript_path = req.get("transcript_path", "")
                queued_mtime = req.get("_transcript_mtime", 0.0)
                queued_at = req.get("_queued_at", 0.0)
                if (transcript_path and queued_mtime > 0 and
                        time.time() - queued_at > 2.0 and
                        os.path.exists(transcript_path)):
                    try:
                        if os.stat(transcript_path).st_mtime > queued_mtime:
                            stale.append(i)
                            if pid:
                                try:
                                    os.kill(pid, signal.SIGTERM)
                                except OSError:
                                    pass
                            continue
                    except OSError:
                        pass

            if not stale:
                return
            for i in reversed(stale):
                self._requests.pop(i)
            if not self._requests:
                if self._idle_visible and self._session_count > 0:
                    self._show_idle()
                else:
                    self.do_hide()
                return
            self._current_index = min(self._current_index, len(self._requests) - 1)
            self._rebuild_sessions()

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
            self._reanchor()

        def _reanchor(self):
            self.move(self._base_x, self._base_y - self._flip_pills_h)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                if self.sprite.hit_rect().contains(event.position().toPoint()):
                    self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()
                    return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if self._drag_offset is not None and event.buttons() == Qt.MouseButton.LeftButton:
                new_pos = event.globalPosition().toPoint() - self._drag_offset
                self._base_x = new_pos.x()
                # _base_y is the sprite anchor; add current flip offset so sprite tracks the drag
                self._base_y = new_pos.y() + self._flip_pills_h
                self.move(new_pos)
                event.accept()
                return
            if self.sprite.hit_rect().contains(event.position().toPoint()):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()
            super().mouseMoveEvent(event)

        def leaveEvent(self, event):
            self.unsetCursor()
            super().leaveEvent(event)

        def mouseReleaseEvent(self, event):
            if self._drag_offset is not None:
                self._drag_offset = None
                self._update_window_size()  # recompute flip layout for new position
                self._reanchor()
                self._save_position()
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def mouseDoubleClickEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                if self.sprite.hit_rect().contains(event.position().toPoint()):
                    # Cancel any drag that the second click's mousePressEvent may have started
                    self._drag_offset = None
                    self._toggle_session_rows()
                    event.accept()
                    return
            super().mouseDoubleClickEvent(event)

        def _toggle_session_rows(self):
            if not self._sessions_enabled or not self._sessions:
                return
            if self._session_rows_visible:
                self._hide_session_rows()
            else:
                self._show_session_rows()

        def do_show(self, payload: dict):
            # Hide session rows when an approval arrives so the pill takes priority.
            if self._session_rows_visible:
                self._hide_session_rows()
            # Stamp when the request was queued and record current transcript mtime.
            # The stale checker uses this to detect when Claude Code ran the tool
            # without waiting for the hook (i.e. user responded natively).
            payload["_queued_at"] = time.time()
            transcript_path = payload.get("transcript_path", "")
            try:
                payload["_transcript_mtime"] = os.stat(transcript_path).st_mtime if transcript_path else 0.0
            except OSError:
                payload["_transcript_mtime"] = 0.0

            was_empty = len(self._requests) == 0
            self._requests.append(payload)
            if was_empty:
                self._current_index = 0
                self.sprite.show_rope = True
                self._container.show()
                if not self.isVisible():
                    self._position_window()
                    self.show()
                    self._pin_to_all_spaces()
                    QTimer.singleShot(100, self._pin_to_all_spaces)  # re-pin after AppKit settles
                try:
                    from AppKit import NSApp
                    for win in NSApp.windows():
                        win.orderFrontRegardless()
                except Exception as e:
                    print(f"[buddy] orderFrontRegardless failed: {e}", file=sys.stderr)
                self._bob_tick = 0
                self._bob_timer.start()
            self._rebuild_sessions()

        def do_hide(self):
            self._bob_timer.stop()
            self._flip_pills_h = 0
            self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
            self._requests = []
            self._current_index = 0
            self.hide()

        def on_session_start(self, payload: dict):
            session_id = payload.get("session_id", "")
            if session_id:
                self._session_count += 1
                self._sessions[session_id] = payload
                if not payload.get('intent') and payload.get('transcript_path'):
                    QTimer.singleShot(15000, lambda sid=session_id: self._deferred_intent_refresh(sid))
            if self._session_rows_visible:
                self._rebuild_session_rows()
            if self._idle_visible and not self._requests and not self.isVisible():
                self._show_idle()

        def on_session_end(self, session_id: str):
            self._session_count = max(0, self._session_count - 1)
            if session_id and session_id in self._sessions:
                del self._sessions[session_id]
            self._thinking_sessions.discard(session_id)
            if self._session_rows_visible:
                self._rebuild_session_rows()
            if session_id:
                to_kill = [req for req in self._requests
                           if req.get("session_id", "") == session_id]
                self._requests = [req for req in self._requests
                                  if req.get("session_id", "") != session_id]
                for req in to_kill:
                    pid = req.get("notify_pid", 0)
                    if pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except OSError:
                            pass
            if not self._requests:
                if self._thinking_sessions:
                    pass  # another session still thinking — keep bob running
                elif self._idle_visible and self._session_count > 0:
                    self._show_idle()
                else:
                    self.do_hide()
            else:
                self._current_index = min(self._current_index, len(self._requests) - 1)
                self._rebuild_sessions()

        def on_set_idle_visible(self, value: bool):
            self._idle_visible = value
            if value and not self._requests and not self.isVisible():
                self._show_idle()
            elif not value and self.isVisible() and not self._requests:
                self.do_hide()

        def on_set_sessions_enabled(self, value: bool):
            self._sessions_enabled = value
            if not value and self._session_rows_visible:
                self._hide_session_rows()

        def on_thinking_start(self, session_id: str):
            if session_id:
                self._thinking_sessions.add(session_id)
            self.sprite.show_rope = True
            self.sprite.update()
            if not self._bob_timer.isActive():
                self._bob_tick = 0
                self._bob_timer.start()
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

        def on_thinking_stop(self, session_id: str):
            self._thinking_sessions.discard(session_id)
            if self._thinking_sessions:
                return  # other sessions still thinking
            if self._requests:
                return  # approval pending — keep bob running
            self._bob_timer.stop()
            self.sprite.show_rope = False
            self.sprite.update()
            if self._idle_visible and self._session_count > 0:
                self._show_idle()
            else:
                self.do_hide()

        def _show_idle(self):
            """Show widget in idle state: sprite only, no pills, no rope, no animation."""
            if self._thinking_sessions:
                return
            if self._session_rows_visible:
                self._hide_session_rows()
            self._bob_timer.stop()
            self._flip_pills_h = 0
            self.sprite.show_rope = False
            self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
            self.sprite.update()
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
                self._bob_timer.stop()
                self.sprite.move((200 - 40) // 2, self._sprite_rest_y)

        # ── Pill signal handlers ───────────────────────────────────────────────

        def _on_pill_approved(self, pipe: str):
            _write_decision("allow", pipe)
            self._remove_by_pipe(pipe)

        def _on_pill_denied(self, pipe: str):
            _write_decision("deny", pipe)
            self._remove_by_pipe(pipe)

        def _on_pill_always(self, pipe: str, destination: str):
            _write_decision("always_allow", pipe)
            self._remove_by_pipe(pipe)

        def _on_pill_go_session(self, iterm_session: str, term_program: str):
            self._focus_terminal_with_session(iterm_session, term_program)

        def _on_pill_activated(self, index: int):
            self._current_index = index
            self._rebuild_sessions()
            # Auto-expand the newly active pill (saves a click)
            for i in range(self._container_layout.count()):
                item = self._container_layout.itemAt(i)
                if item and item.widget() and item.widget()._is_active:
                    item.widget().toggle_expand()
                    break

        def _on_active_pill_expand_changed(self, expanded: bool):
            if expanded:
                self._bob_timer.stop()
                self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
            else:
                self._bob_tick = 0
                self._bob_timer.start()
            self._update_window_size()
            self._reanchor()

        def _remove_by_pipe(self, pipe: str):
            for i, req in enumerate(self._requests):
                if req.get("pipe", "") == pipe:
                    self._requests.pop(i)
                    if not self._requests:
                        if self._idle_visible and self._session_count > 0:
                            self._show_idle()
                        else:
                            self.do_hide()
                        return
                    self._current_index = min(self._current_index, len(self._requests) - 1)
                    self._rebuild_sessions()
                    return

        # ── Actions ────────────────────────────────────────────────────────────

        def _on_cancel(self, pipe_path: str):
            for i, req in enumerate(self._requests):
                if req.get("pipe", "") == pipe_path:
                    self._requests.pop(i)
                    if not self._requests:
                        if self._idle_visible and self._session_count > 0:
                            self._show_idle()
                        else:
                            self.do_hide()
                        return
                    self._current_index = min(self._current_index, len(self._requests) - 1)
                    self._rebuild_sessions()
                    return

        # ── Terminal focus ─────────────────────────────────────────────────────

        def _focus_terminal_with_session(self, iterm_session: str, term_program: str = "",
                                           source: str = "", cwd: str = "", session_id: str = ""):
            def _is_running(app_name):
                r = subprocess.run(
                    ["osascript", "-e", f'tell application "System Events" to return (name of processes) contains "{app_name}"'],
                    capture_output=True, text=True,
                )
                return r.stdout.strip() == "true"

            # 1. iTerm2: exact session UUID
            if iterm_session:
                claude_uuid = iterm_session.split(":")[1] if ":" in iterm_session else iterm_session
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

            # 2. Known terminal via TERM_PROGRAM env var
            TERM_TO_APP = {
                "iterm.app":      "iTerm2",
                "apple_terminal": "Terminal",
                "warpterminal":   "Warp",
                "hyper":          "Hyper",
                "ghostty":        "Ghostty",
                "vscode":         "Code",
                "cursor":         "Cursor",
            }
            if term_program:
                app = TERM_TO_APP.get(term_program.lower())
                if app:
                    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], capture_output=True)
                    return

            # 3. No UUID — for explicit desktop source, deep-link into Claude Code session
            if source == "desktop":
                if session_id:
                    # claude://code/<session_id> navigates directly to that conversation
                    result = subprocess.run(["open", f"claude://code/{session_id}"], capture_output=True)
                    if result.returncode == 0:
                        return
                if _is_running("Claude"):
                    subprocess.run(["osascript", "-e", 'tell application "Claude" to activate'], capture_output=True)
                return

            # 4. Terminal or unknown: try to find the right iTerm2 tab by CWD
            #    Look for a node (Claude Code CLI) process running in cwd, match its TTY to an iTerm2 session
            if cwd and _is_running("iTerm2"):
                found_uuid = None
                try:
                    script = '''
tell application "iTerm2"
  set out to ""
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        set out to out & (unique ID of s) & "|" & (tty of s) & "\n"
      end repeat
    end repeat
  end repeat
  return out
end tell
'''
                    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
                    for line in r.stdout.strip().splitlines():
                        if '|' not in line:
                            continue
                        uuid, tty = line.split('|', 1)
                        tty_name = tty.strip().replace('/dev/', '')
                        if not tty_name:
                            continue
                        ps_r = subprocess.run(
                            ["ps", "-t", tty_name, "-o", "pid=,comm="],
                            capture_output=True, text=True
                        )
                        for ps_line in ps_r.stdout.splitlines():
                            parts = ps_line.strip().split(None, 1)
                            if len(parts) >= 2 and 'node' in parts[1].lower():
                                lsof_r = subprocess.run(
                                    ["lsof", "-p", parts[0], "-d", "cwd", "-Fn"],
                                    capture_output=True, text=True, timeout=2
                                )
                                for lsof_line in lsof_r.stdout.splitlines():
                                    if lsof_line.startswith('n') and lsof_line[1:] == cwd:
                                        found_uuid = uuid.strip()
                                        break
                            if found_uuid:
                                break
                        if found_uuid:
                            break
                except Exception:
                    pass

                if found_uuid:
                    focus_script = f'''
tell application "iTerm2"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if unique ID of s is "{found_uuid}" then
          tell t to select
          tell w to select
          return
        end if
      end repeat
    end repeat
  end repeat
end tell
'''
                    subprocess.run(["osascript", "-e", focus_script], capture_output=True)
                    return
                # No node process found in cwd — it's probably a desktop session
                if _is_running("Claude"):
                    subprocess.run(["osascript", "-e", 'tell application "Claude" to activate'], capture_output=True)
                    return
                # Fall through to activate iTerm2 generically
                subprocess.run(["osascript", "-e", 'tell application "iTerm2" to activate'], capture_output=True)
                return

            # 5. No iTerm2 — last resort
            if _is_running("Claude"):
                subprocess.run(["osascript", "-e", 'tell application "Claude" to activate'], capture_output=True)
                return
            for app in ["Terminal", "Warp", "Ghostty", "Alacritty", "Hyper"]:
                if _is_running(app):
                    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], capture_output=True)
                    return

        # ── All-spaces pinning ─────────────────────────────────────────────────

        def _pin_to_all_spaces(self):
            try:
                import objc
                from AppKit import (
                    NSApp, NSWorkspace,
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorMoveToActiveSpace,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                    NSWindowCollectionBehaviorStationary,
                    NSWindowCollectionBehaviorIgnoresCycle,
                )

                # Prefer getting NSWindow directly from this widget's native handle.
                # NSApp.windows() is unreliable for NSApplicationActivationPolicyAccessory
                # apps and may be empty if called before the window is first shown.
                windows_to_pin = []
                try:
                    ns_view = objc.objc_id(int(self.winId()))
                    ns_win = ns_view.window()
                    if ns_win is not None:
                        windows_to_pin = [ns_win]
                except Exception:
                    pass

                if not windows_to_pin:
                    windows_to_pin = list(NSApp.windows())

                print(f"[buddy] _pin_to_all_spaces: {len(windows_to_pin)} windows", file=sys.stderr)

                for win in windows_to_pin:
                    behavior = win.collectionBehavior()
                    behavior &= ~NSWindowCollectionBehaviorMoveToActiveSpace
                    behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
                    behavior |= NSWindowCollectionBehaviorFullScreenAuxiliary
                    behavior |= NSWindowCollectionBehaviorStationary
                    behavior |= NSWindowCollectionBehaviorIgnoresCycle
                    win.setCollectionBehavior_(behavior)
                    win.setLevel_(25)

                if not getattr(self, '_space_observer_registered', False):
                    self._space_observer_registered = True
                    def _on_space_change(_notification):
                        if self.isVisible():
                            try:
                                for win in NSApp.windows():
                                    win.orderFrontRegardless()
                            except Exception:
                                pass
                            self._pin_to_all_spaces()  # re-apply in case behavior was lost
                    NSWorkspace.sharedWorkspace().notificationCenter() \
                        .addObserverForName_object_queue_usingBlock_(
                            "NSWorkspaceActiveSpaceDidChangeNotification",
                            None, None, _on_space_change)
            except Exception as e:
                print(f"[buddy] _pin_to_all_spaces failed: {e}", file=sys.stderr)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def _read_intent_from_transcript(transcript_path):
        """Return first real user message from a transcript, or ''."""
        try:
            with open(transcript_path, 'r', errors='replace') as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        if d.get('type') != 'user':
                            continue
                        content = d.get('message', {}).get('content', '')
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get('type') == 'text':
                                    text = c['text'].strip()
                                    if text and not text.startswith('<') and not text.startswith('['):
                                        return text[:80]
                        elif isinstance(content, str):
                            text = content.strip()
                            if text and not text.startswith('<') and not text.startswith('['):
                                return text[:80]
                    except Exception:
                        pass
        except Exception:
            pass
        return ''

    def _load_persisted_sessions():
        """Load sessions from file + scan transcripts as fallback. Returns {session_id: payload}."""
        sessions = {}
        try:
            with open(SESSIONS_FILE) as f:
                sessions = json.load(f)
        except Exception:
            pass

        # Fallback: scan transcripts for recent sessions not already in file
        projects_dir = os.path.expanduser("~/.claude/projects")
        now = time.time()
        if os.path.isdir(projects_dir):
            for encoded in os.listdir(projects_dir):
                project_dir = os.path.join(projects_dir, encoded)
                if not os.path.isdir(project_dir):
                    continue
                folder = encoded.rstrip('-').rsplit('-', 1)[-1] if '-' in encoded else encoded
                try:
                    entries = os.listdir(project_dir)
                except Exception:
                    continue
                for fname in entries:
                    if not fname.endswith('.jsonl'):
                        continue
                    sid = fname[:-6]
                    if sid in sessions:
                        continue
                    fpath = os.path.join(project_dir, fname)
                    try:
                        mtime = os.path.getmtime(fpath)
                        if now - mtime > SESSIONS_STALE_SECS:
                            continue
                        sessions[sid] = {
                            'session_id': sid,
                            'folder': folder,
                            'cwd': '/' + encoded.lstrip('-').replace('-', '/'),
                            'intent': '',
                            'source': 'unknown',
                            'iterm_session_id': '',
                            'transcript_path': fpath,
                            'ts': mtime,
                        }
                    except Exception:
                        pass

        # Prune stale, enrich empty intents, save back if changed
        valid = {}
        changed = False
        for sid, sess in sessions.items():
            tp = sess.get('transcript_path', '')
            if tp and os.path.exists(tp):
                try:
                    if now - os.path.getmtime(tp) > SESSIONS_STALE_SECS:
                        changed = True
                        continue
                except Exception:
                    pass
            if not sess.get('intent') and tp:
                intent = _read_intent_from_transcript(tp)
                if intent:
                    sess['intent'] = intent
                    changed = True
            valid[sid] = sess

        if changed:
            try:
                with open(SESSIONS_FILE, 'w') as f:
                    json.dump(valid, f)
            except Exception:
                pass

        return valid

    window = ChipWidget()

    # Restore sessions from persistent file + transcript scan
    for _sid, _sess in _load_persisted_sessions().items():
        if _sid:
            window._sessions[_sid] = _sess
            window._session_count += 1

    server_thread = SocketServer()
    server_thread.show_signal.connect(window.do_show)
    server_thread.hide_signal.connect(window.do_hide)
    server_thread.cancel_signal.connect(window._on_cancel)
    server_thread.session_start_signal.connect(window.on_session_start)
    server_thread.session_end_signal.connect(window.on_session_end)  # str session_id
    server_thread.set_idle_visible_signal.connect(window.on_set_idle_visible)
    server_thread.set_sessions_enabled_signal.connect(window.on_set_sessions_enabled)
    server_thread.thinking_start_signal.connect(window.on_thinking_start)
    server_thread.thinking_stop_signal.connect(window.on_thinking_stop)
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
