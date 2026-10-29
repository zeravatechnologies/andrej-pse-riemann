"""
The guardian as its own process (round 3, item 19).

`pse-riemann --guardian` runs the SSH guardian (and the reversible-containment
undo timer) without the main window, with an icon in the system tray:

    Otvori · Stanje θ · Prekini online AI · Ugasi čuvara

It keeps running when the main window is closed ("Zatvori prozor, čuvar
ostaje"). One instance per user (a lock file). `--headless` runs the same loop
without Qt (for the optional systemd user service); alarms then go to the
desktop notification daemon and to SHARED_LIB.
"""
from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from . import config

POLL_S = 5


def lock_path() -> Path:
    return config.DIR_STATE / "guardian.lock"


def pid_path() -> Path:
    return config.DIR_STATE / "guardian.pid"


class Lock:
    def __init__(self):
        self.fh = None

    def acquire(self) -> bool:
        lock_path().parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(lock_path(), "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            return False
        pid_path().write_text(str(os.getpid()))
        return True

    def release(self):
        if self.fh:
            try:
                pid_path().unlink()
            except OSError:
                pass
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()
            self.fh = None


def running_pid() -> Optional[int]:
    """PID of the running guardian, or None (the lock is the truth, not the file)."""
    try:
        fh = open(lock_path(), "w")
    except OSError:
        return None
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh, fcntl.LOCK_UN)
        return None                                      # nobody holds it
    except OSError:
        try:
            return int(pid_path().read_text().strip())
        except (OSError, ValueError):
            return -1
    finally:
        fh.close()


def launch_command() -> list[str]:
    exe = Path(sys.argv[0]).resolve()
    if exe.suffix == ".py":
        return [sys.executable, str(exe), "--guardian"]
    return [str(exe), "--guardian"]


def ensure_running() -> bool:
    """Start the guardian process if it is not running ("radi uvijek")."""
    if running_pid():
        return False
    subprocess.Popen(launch_command(), start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def stop() -> bool:
    pid = running_pid()
    if pid and pid > 0:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False
    return False


# --------------------------------------------------------------------------- #
def _tick(g, notify) -> None:
    from .guardian.ssh import unit as U
    out = g.poll()
    for msg in out.get("tier2", []):
        notify("SSH čuvar", msg, critical=True)
    for msg in out.get("alarms", []):
        notify("PSE Riemann — OPASNOST", msg, critical=True)
    if U.pending_alarm():
        pass                                             # the tray shows the window


def _notify_send(title: str, msg: str, critical: bool = False) -> None:
    try:
        subprocess.run(["notify-send", "-u", "critical" if critical else "normal",
                        title, msg[:400]], timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


def run_headless() -> int:
    config.ensure_vault()
    lk = Lock()
    if not lk.acquire():
        print("čuvar već radi", file=sys.stderr)
        return 0
    from .core import journal as J
    from .guardian.ssh import unit as U
    stop_flag = {"stop": False}
    signal.signal(signal.SIGTERM, lambda *_: stop_flag.__setitem__("stop", True))
    J.log(J.UNIT, "ssh-guardian", {"event": "started", "mode": "headless"}, verdict="started")
    g = U.SSHGuardian()
    try:
        while not stop_flag["stop"]:
            _tick(g, _notify_send)
            time.sleep(POLL_S)
    finally:
        J.log(J.UNIT, "ssh-guardian", {"event": "stopped"}, verdict="stopped")
        lk.release()
    return 0


def run_tray() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
    config.ensure_vault()
    lk = Lock()
    if not lk.acquire():
        return 0
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from .core import journal as J
    from .guardian.ssh import unit as U
    J.log(J.UNIT, "ssh-guardian", {"event": "started", "mode": "tray"}, verdict="started")
    g = U.SSHGuardian()
    icon_p = next((p for p in (config.APP_ROOT / "packaging" / "pse-riemann.png",
                               Path("/usr/share/icons/hicolor/256x256/apps/pse-riemann.png"))
                   if p.exists()), None)
    tray = QSystemTrayIcon(QIcon(str(icon_p)) if icon_p else QIcon())
    tray.setToolTip("PSE Riemann — čuvar radi")
    menu = QMenu()

    def open_app():
        exe = launch_command()[:-1]
        subprocess.Popen(exe, start_new_session=True)

    def show_theta():
        h = g.health()
        from .guardian import killswitch as KS
        QMessageBox.information(None, "Stanje čuvara",
                                f"θ = {h.get('theta')}  (σ {h.get('sigma')})\n"
                                f"stanje: {h.get('status')}\n"
                                f"generacija jedinice: {g.generation}\n"
                                f"online AI: {'ISKLJUČEN' if KS.closed() else 'uključen'}")

    def kill_ai():
        from .guardian import killswitch as KS
        out = KS.close("operater (meni ikone u traci)", actor="operator")
        tray.showMessage("Online AI isključen",
                         f"Prekinuto poziva: {out['hung_up']} · sada: {out['fallback']}")

    def quit_guard():
        if QMessageBox.question(None, "Ugasi čuvara",
                                "Ugasiti SSH čuvara? Dok je ugašen, niko ne prati SSH "
                                "napade.") == QMessageBox.Yes:
            app.quit()

    for text, fn in (("Otvori", open_app), ("Stanje θ", show_theta),
                     ("Prekini online AI", kill_ai), ("Ugasi čuvara", quit_guard)):
        a = QAction(text, menu)
        a.triggered.connect(fn)
        menu.addAction(a)
    tray.setContextMenu(menu)
    tray.show()

    def notify(title, msg, critical=False):
        tray.showMessage(title, msg, QSystemTrayIcon.Critical if critical
                         else QSystemTrayIcon.Information, 15000)

    def tick():
        try:
            _tick(g, notify)
            from .gui.danger import show_if_pending
            show_if_pending(None)
        except Exception as e:                           # noqa: BLE001 — never die silently
            J.log(J.UNIT, "ssh-guardian", {"event": "tick_error", "error": str(e)[:300]},
                  verdict="error")
    t = QTimer()
    t.timeout.connect(tick)
    t.start(POLL_S * 1000)
    QTimer.singleShot(500, tick)
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    sig_timer = QTimer()                     # lets Python see SIGTERM while Qt runs
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(500)
    try:
        return app.exec()
    finally:
        J.log(J.UNIT, "ssh-guardian", {"event": "stopped"}, verdict="stopped")
        lk.release()
