"""Round 3, item 19: the guardian as its own process, single instance, start at
login (XDG autostart or a hardened systemd user unit)."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pse_r import autostart as AS
from pse_r import guardian_app as GA

APP = Path(__file__).resolve().parents[1]


def test_single_instance_lock():
    a, b = GA.Lock(), GA.Lock()
    assert a.acquire()
    assert not b.acquire()                       # second guardian refused
    assert GA.running_pid() == os.getpid()
    a.release()
    assert GA.running_pid() is None


def test_headless_guardian_runs_and_stops_on_sigterm():
    env = dict(os.environ)
    p = subprocess.Popen([sys.executable, str(APP / "main.py"), "--guardian", "--headless"],
                         cwd=str(APP), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            if GA.running_pid():
                break
            time.sleep(0.1)
        assert GA.running_pid() == p.pid
        # a second one exits at once, leaving the first in charge
        q = subprocess.run([sys.executable, str(APP / "main.py"), "--guardian", "--headless"],
                           cwd=str(APP), env=env, capture_output=True, timeout=60)
        assert q.returncode == 0 and GA.running_pid() == p.pid
        assert GA.stop()
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    assert GA.running_pid() is None


def test_xdg_autostart_and_unit_text(monkeypatch):
    path = AS.enable_xdg()
    txt = path.read_text()
    assert "--guardian" in txt and "Exec=" in txt
    u = AS.unit_text(has_sudo_rule=False)
    assert "NoNewPrivileges=yes" in u and "--headless" in u and "ProtectKernelTunables=yes" in u
    u2 = AS.unit_text(has_sudo_rule=True)
    assert "NoNewPrivileges=no" in u2 and "sudo" in u2
    AS.disable_all()
    assert not path.exists()


def test_setup_applies_autostart():
    from pse_r import setup_flow as SF
    SF.apply(SF.SetupChoices(operator="Andrej Test", main=SF.ModelChoice("none"),
                             guardian_autostart=True))
    assert AS.desktop_path().exists()
    SF.apply(SF.SetupChoices(operator="Andrej Test", main=SF.ModelChoice("none"),
                             guardian_autostart=False))
    assert not AS.desktop_path().exists()
