"""
DANGER alert (round 3, item 16): a big window, a red pill, a SHARED_LIB record
and a beep that keeps going — every 2 seconds — until the operator clicks
"U redu". Used when the SSH guardian must remove an attacker and has no right
to (no narrow sudoers rule), or a login succeeded after an attack. The text is
always a fixed template (guardian/templates.py), never model output.
"""
from __future__ import annotations

from ..i18n import tr

import re
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QPushButton,
                               QTextBrowser, QVBoxLayout)

SOUND = Path("/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga")
_open: list = []


def _beep(owner) -> None:
    if shutil.which("canberra-gtk-play"):
        args = ["-f", str(SOUND)] if SOUND.exists() else ["-i", "bell"]
        QProcess.startDetached("canberra-gtk-play", args)
    elif shutil.which("paplay") and SOUND.exists():
        QProcess.startDetached("paplay", [str(SOUND)])
    else:
        QApplication.beep()


class DangerDialog(QDialog):
    def __init__(self, alarm: dict, parent=None, sound: bool = True):
        super().__init__(parent)
        self.alarm = alarm
        self.setWindowTitle(tr("PSE Riemann — OPASNOST"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        from .. import screen as SCR
        _x, _y, aw, ah = SCR.available()
        SCR.fit(self, aw * 0.8 / SCR.k(), ah * 0.7 / SCR.k())
        self.setStyleSheet("QDialog { background:#1a0b0d; }")
        v = QVBoxLayout(self)
        pill = QLabel(tr("  ⛔  OPASNOST  "))
        pill.setAlignment(Qt.AlignCenter)
        pill.setStyleSheet("background:#c62828; color:white; font-size:34pt; font-weight:800;"
                           " border-radius:28px; padding:10px 30px;")
        v.addWidget(pill, 0, Qt.AlignHCenter)
        text = alarm.get("text", "")
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("color:#ffe3e3; font-size:24pt; font-weight:600; padding:20px;")
        v.addWidget(msg, 1)
        cmd = self._command(text)
        if cmd:
            tb = QTextBrowser()
            tb.setPlainText(cmd)
            tb.setMaximumHeight(90)
            tb.setStyleSheet("background:#0d0f14; color:#ffc257; font-family:monospace; "
                             "font-size:18pt;")
            v.addWidget(tb)
        row = QHBoxLayout()
        if cmd:
            cp = QPushButton(tr("Kopiraj komandu"))
            cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(cmd))
            row.addWidget(cp)
        row.addStretch(1)
        ok = QPushButton(tr("U redu"))
        ok.setStyleSheet("background:#ffc257; color:#3a2a06; font-size:22pt; font-weight:700;"
                         " padding:10px 40px;")
        ok.clicked.connect(self._ack)
        row.addWidget(ok)
        v.addLayout(row)
        v.addWidget(QLabel(tr("<span style='color:#c9a0a0'>Zapisano u SHARED_LIB. Usko sudoers "
                           "pravilo: vodič SUDOERS-SR.md (u Pomoći / repou).</span>")))
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: _beep(self))
        if sound:
            self.timer.start(2000)
            _beep(self)

    @staticmethod
    def _command(text: str) -> str:
        m = re.search(r"(sudo [A-Za-z0-9 _./:=@'-]+)", text)
        return m.group(1).strip().rstrip(".") if m else ""

    def _ack(self):
        from ..guardian.ssh import unit as U
        from ..shared_lib import operator as OP
        U.acknowledge_alarm(OP.current() or "operator")
        self.timer.stop()
        self.accept()

    def closeEvent(self, ev):
        # closing the window is not an acknowledgement: it comes back
        if self.timer.isActive():
            ev.ignore()
            return
        super().closeEvent(ev)

    def reject(self):                       # Esc does not silence it either
        if not self.timer.isActive():
            super().reject()


def show_if_pending(parent=None, sound: bool = True):
    """Open the danger window if an unacknowledged alarm exists (once)."""
    from ..guardian.ssh import unit as U
    a = U.pending_alarm()
    if not a or any(d.isVisible() for d in _open):
        return None
    d = DangerDialog(a, parent, sound=sound)
    _open.append(d)
    d.finished.connect(lambda _=0: _open.remove(d) if d in _open else None)
    d.show()
    d.raise_()
    return d
