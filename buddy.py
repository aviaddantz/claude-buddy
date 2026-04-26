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
        Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer
    )
    from PyQt6.QtGui import (
        QFont, QFontMetrics, QColor, QPainter, QPainterPath, QPen, QBrush
    )

    class SocketServer(QThread):
        show_signal = pyqtSignal(dict)   # carries payload dict
        hide_signal = pyqtSignal()
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
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._rope_angle = 0.0

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
        go_session    = pyqtSignal(str)        # iterm_session value
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
            go_btn = QPushButton("Go to session")
            go_btn.setStyleSheet(go_style)
            go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            go_btn.clicked.connect(
                lambda: self.go_session.emit(req.get("iterm_session", ""))
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
                self.sprite.move((200 - SPRITE_W) // 2, self._sprite_rest_y - offset)
                self.sprite.set_rope_angle(self._bob_tick * 0.12)
            self._bob_timer.timeout.connect(_bob_step)

            # Staleness timer
            self._stale_timer = QTimer()
            self._stale_timer.setInterval(1000)
            self._stale_timer.timeout.connect(self._cleanup_stale_requests)
            self._stale_timer.start()

            self.setCursor(Qt.CursorShape.PointingHandCursor)
            QTimer.singleShot(100, self._pin_to_all_spaces)

        # ── Layout helpers ─────────────────────────────────────────────────────

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
            total_h = self._sprite_h + total_pills_h
            self.setFixedHeight(max(total_h, self._sprite_h + 10))

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
            total_h = self._sprite_h + total_pills_h
            self.setFixedHeight(max(total_h, self._sprite_h + 10))

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
                    os.kill(pid, 0)
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
            self._rebuild_sessions()

        def _position_window(self):
            screen = QApplication.primaryScreen().geometry()
            self._update_window_size()
            self._base_y = 80
            self._base_x = screen.width() - self.width() - 20
            self.move(self._base_x, self._base_y)

        def _reanchor(self):
            """Re-apply top-right position after height changes."""
            screen = QApplication.primaryScreen().geometry()
            self._base_x = screen.width() - self.width() - 20
            self.move(self._base_x, self._base_y)

        def do_show(self, payload: dict):
            was_empty = len(self._requests) == 0
            self._requests.append(payload)
            if was_empty:
                self._current_index = 0
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
            self._rebuild_sessions()

        def do_hide(self):
            self._bob_timer.stop()
            self.sprite.move((200 - 40) // 2, self._sprite_rest_y)
            self._requests = []
            self._current_index = 0
            self.hide()

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

        def _on_pill_go_session(self, iterm_session: str):
            self._focus_terminal_with_session(iterm_session)

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
                        self.do_hide()
                        return
                    self._current_index = min(self._current_index, len(self._requests) - 1)
                    self._rebuild_sessions()
                    return

        # ── Terminal focus ─────────────────────────────────────────────────────

        def _focus_terminal_with_session(self, iterm_session: str):
            claude_uuid = iterm_session
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
