"""
Reversible containment with automatic undo (round 3, item 15; Svarog S3).

Automatic (declared reversible in core/actions.py):
  ssh.kill-session   end one sshd session (the source may connect again)
  ssh.block-ip-24h   temporary block; removed by itself after 24 h — the record
                     is on disk, so the undo happens even across a restart
Never automatic (irreversible → a proposal to the operator WITH the exact command):
  permanent block, stopping the SSH server.

Root work goes through ONE validated helper (packaging/pse-guard-helper) that a
narrow sudoers rule allows; without that rule nothing is done silently — a
DANGER alarm is raised instead (item 16). Protected targets are refused before
the helper is ever called: loopback, unspecified, this machine's own addresses,
the default gateway, multicast and broadcast.
"""
from __future__ import annotations

import ipaddress
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from ..core import actions as A
from ..core import journal as J
from . import templates as T

BLOCK_S = 24 * 3600
HELPER_PATHS = (Path("/usr/lib/pse-riemann/pse-guard-helper"),
                Path(__file__).resolve().parents[2] / "packaging" / "pse-guard-helper")
_DDL = ["""CREATE TABLE IF NOT EXISTS containment (
    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, target TEXT NOT NULL,
    created REAL NOT NULL, until REAL, undone_at REAL, detail TEXT)"""]

A.declare("ssh.kill-session", True, "izvor se može ponovo povezati; ništa trajno",
          "prekini jednu sshd sesiju")
A.declare("ssh.block-ip-24h", True, "blokada se sama skida posle 24 h (zapis na disku)",
          "privremena blokada IP adrese")
A.declare("ssh.block-ip-permanent", False, description="trajna blokada — operater")
A.declare("ssh.stop-server", False, description="gašenje SSH servera — operater")


class NoRights(PermissionError):
    """The narrow sudoers rule is not installed — nothing was done."""


class Protected(ValueError):
    """The target is one the guardian must never touch."""


def _store():
    from ..shared_lib.store import store
    s = store()
    s.ensure(_DDL)
    return s


def _safe(p: Path) -> bool:
    """Only a helper that ROOT owns and nobody else can write may be run with
    sudo — a user-writable helper behind a sudoers rule would be a root shell."""
    try:
        st = p.stat()
    except OSError:
        return False
    return st.st_uid == 0 and not (st.st_mode & 0o022)


def helper() -> Optional[str]:
    for p in HELPER_PATHS:
        if p.is_file() and _safe(p):
            return str(p)
    return None


_RIGHTS: dict = {"at": 0.0, "ok": False, "detail": ""}
HELPER_MISSING = ("pomoćni program nije instaliran kao root "
                  "(/usr/lib/pse-riemann/pse-guard-helper) — instaliraj .deb")


def have_rights(refresh: bool = False) -> tuple[bool, str]:
    """Can the helper run as root without a password (sudo -n)?"""
    if not refresh and time.time() - _RIGHTS["at"] < 60:
        return _RIGHTS["ok"], _RIGHTS["detail"]
    h = helper()
    ok, detail = False, HELPER_MISSING
    if h and shutil.which("sudo"):
        try:
            r = subprocess.run(["sudo", "-n", h, "check"], capture_output=True, timeout=10)
            ok = r.returncode == 0
            detail = (r.stdout or r.stderr).decode("utf-8", "replace").strip()[:200]
        except (OSError, subprocess.SubprocessError) as e:
            detail = str(e)[:200]
    _RIGHTS.update(at=time.time(), ok=ok, detail=detail)
    return ok, detail


def _own_addresses() -> set:
    out = {"127.0.0.1", "::1", "0.0.0.0", "::"}
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(socket.gethostname(), None):
            out.add(sa[0])
    except OSError:
        pass
    try:
        r = subprocess.run(["ip", "-o", "addr"], capture_output=True, timeout=5, text=True)
        for ln in r.stdout.splitlines():
            parts = ln.split()
            if "inet" in parts or "inet6" in parts:
                i = parts.index("inet") if "inet" in parts else parts.index("inet6")
                out.add(parts[i + 1].split("/")[0])
        r = subprocess.run(["ip", "route", "show", "default"], capture_output=True,
                           timeout=5, text=True)
        for ln in r.stdout.splitlines():
            p = ln.split()
            if "via" in p:
                out.add(p[p.index("via") + 1])
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def check_target(ip: str) -> str:
    a = ipaddress.ip_address(ip)
    if a.is_loopback or a.is_unspecified or a.is_multicast or str(a) == "255.255.255.255":
        raise Protected(f"{ip} je zaštićena adresa — nikad se ne blokira")
    if str(a) in _own_addresses():
        raise Protected(f"{ip} je adresa ovog računara ili gateway — nikad se ne blokira")
    return str(a)


def _helper(verb: str, arg: str) -> str:
    ok, detail = have_rights()
    if not ok:
        raise NoRights(detail or "nema sudoers pravila")
    r = subprocess.run(["sudo", "-n", helper(), verb, arg], capture_output=True, timeout=20)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).decode("utf-8", "replace")[:300])
    return r.stdout.decode("utf-8", "replace")[:300]


def block_ip_24h(ip: str, reason: str, now: Optional[float] = None) -> dict:
    A.require_auto("ssh.block-ip-24h")
    ip = check_target(ip)
    for r in active():
        if r["action"] == "block-ip" and r["target"] == ip:
            return r                                  # already blocked
    now = now or time.time()
    _helper("block-ip", ip)
    s = _store()
    s.execute("INSERT INTO containment(action,target,created,until,detail) VALUES (?,?,?,?,?)",
              ("block-ip", ip, now, now + BLOCK_S, reason[:300]))
    until = time.strftime("%d.%m. %H:%M", time.localtime(now + BLOCK_S))
    J.log(J.THREAT, "ssh-guardian", {"event": "ip_blocked_24h", "ip": ip, "until": now + BLOCK_S,
                                     "reason": reason[:300]}, subject=ip, verdict="contained")
    return {"action": "block-ip", "target": ip, "until": now + BLOCK_S, "until_text": until}


def kill_session(pid: str, ip: str) -> None:
    A.require_auto("ssh.kill-session")
    check_target(ip)
    _helper("kill-session", str(int(pid)))
    J.log(J.THREAT, "ssh-guardian", {"event": "session_killed", "pid": int(pid), "ip": ip},
          subject=ip, verdict="contained")


def active(now: Optional[float] = None) -> list[dict]:
    return _store().rows("SELECT * FROM containment WHERE undone_at IS NULL ORDER BY created")


def undo_expired(now: Optional[float] = None) -> list[str]:
    """Remove every block whose time is up. Runs at start and on every tick."""
    now = now or time.time()
    done = []
    for r in active():
        if r["action"] != "block-ip" or (r["until"] or 0) > now:
            continue
        try:
            _helper("unblock-ip", r["target"])
        except NoRights:
            return done                               # try again when rights exist
        except RuntimeError as e:
            J.log(J.THREAT, "ssh-guardian", {"event": "unblock_failed", "ip": r["target"],
                                             "error": str(e)[:200]}, subject=r["target"],
                  verdict="error")
            continue
        _store().execute("UPDATE containment SET undone_at=? WHERE id=?", (now, r["id"]))
        J.log(J.THREAT, "ssh-guardian", {"event": "ip_unblocked", "ip": r["target"]},
              subject=r["target"], verdict="undone")
        done.append(r["target"])
    return done


def permanent_block_command(ip: str) -> str:
    return f"sudo ufw insert 1 deny from {ip} to any"


STOP_SSH = "sudo systemctl stop ssh"
START_SSH = "sudo systemctl start ssh"


def propose_permanent(ip: str) -> str:
    from ..shared_lib.store import store
    ip = check_target(ip)
    return store().propose("ssh-permanent", T.render(
        "ssh.propose_permanent", ip=ip, cmd=permanent_block_command(ip)),
        {"ip": ip, "command": permanent_block_command(ip)}, proposer="ssh-guardian")


def propose_stop_ssh() -> str:
    from ..shared_lib.store import store
    for it in store().open_items("ssh-stop"):
        return it["id"]
    return store().propose("ssh-stop", T.render("ssh.propose_stop", cmd=STOP_SSH,
                                                 cmd2=START_SSH),
                           {"command": STOP_SSH, "undo": START_SSH}, proposer="ssh-guardian")
