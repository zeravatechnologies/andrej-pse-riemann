"""
Reading the SSH log without root, and surviving log rotation (Svarog S6).

Two readers, chosen at start:
  JournalSource   `journalctl -u ssh -u sshd -o json --follow` (the user is in the
                  `adm` / `systemd-journal` group); position kept by cursor, so a
                  restart resumes exactly where it stopped.
  AuthLogTail     /var/log/auth.log, readable by group `adm`. Rotation-safe: the
                  file is identified by (device, inode); when the inode changes
                  (logrotate moved it) the rest of the OLD file is read through
                  its still-open handle, then the new file is opened from the
                  start; a file that shrank (copytruncate) is re-read from 0.
Both yield raw text lines; parse.py turns them into events.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterator, Optional

AUTH_LOG = Path("/var/log/auth.log")


class AuthLogTail:
    def __init__(self, path: Path = AUTH_LOG, state: Optional[dict] = None,
                 from_end: bool = True):
        self.path = Path(path)
        self.fh = None
        self.ident = None
        self.pos = 0
        self.head = b""            # first bytes: a file truncated and refilled to the
                                   # same length is caught by its changed beginning
        st = state or {}
        self._resume = (st.get("ident"), st.get("pos")) if st else None
        self._from_end = from_end

    def state(self) -> dict:
        return {"ident": list(self.ident) if self.ident else None, "pos": self.pos}

    def _open(self, start_at_end: bool) -> bool:
        try:
            fh = open(self.path, "rb")
        except OSError:
            return False
        st = os.fstat(fh.fileno())
        self.fh, self.ident = fh, (st.st_dev, st.st_ino)
        if self._resume and self._resume[0] and tuple(self._resume[0]) == self.ident \
                and (self._resume[1] or 0) <= st.st_size:
            self.pos = int(self._resume[1] or 0)
        else:
            self.pos = st.st_size if start_at_end else 0
        self._resume = None
        fh.seek(0)
        self.head = fh.read(128)
        fh.seek(self.pos)
        return True

    def _drain(self) -> list[str]:
        out = []
        while True:
            line = self.fh.readline()
            if not line:
                break
            if not line.endswith(b"\n"):          # half-written line: come back later
                self.fh.seek(self.pos)
                break
            self.pos += len(line)
            out.append(line.decode("utf-8", "replace").rstrip("\n"))
        return out

    def poll(self) -> list[str]:
        if self.fh is None:
            if not self._open(start_at_end=self._from_end):
                return []
        lines = self._drain()
        try:
            st = os.stat(self.path)
        except OSError:
            return lines                           # mid-rotation: keep the old handle
        if (st.st_dev, st.st_ino) != self.ident:
            lines += self._drain()                 # rest of the rotated file
            self.fh.close()
            if self._open(start_at_end=False):     # new file: from its beginning
                lines += self._drain()
        elif st.st_size < self.pos or self._head_changed():   # truncated in place
            self.fh.seek(0)
            self.pos = 0
            lines += self._drain()
            self.fh.seek(0)
            self.head = self.fh.read(128)
            self.fh.seek(self.pos)
        elif not self.head and self.pos:
            self.fh.seek(0)
            self.head = self.fh.read(128)
            self.fh.seek(self.pos)
        return lines

    def _head_changed(self) -> bool:
        if not self.head:
            return False
        cur = self.fh.tell()
        self.fh.seek(0)
        now = self.fh.read(len(self.head))
        self.fh.seek(cur)
        return now != self.head

    def close(self):
        if self.fh:
            self.fh.close()
            self.fh = None


class JournalSource:
    UNITS = ("ssh.service", "sshd.service")

    def __init__(self, state: Optional[dict] = None):
        self.cursor = (state or {}).get("cursor")

    @staticmethod
    def available() -> bool:
        if not shutil.which("journalctl"):
            return False
        try:
            r = subprocess.run(["journalctl", "-n", "1", "-u", "ssh", "-q", "--no-pager"],
                               capture_output=True, timeout=5)
            return r.returncode == 0 and b"permission" not in r.stderr.lower()
        except (OSError, subprocess.SubprocessError):
            return False

    def state(self) -> dict:
        return {"cursor": self.cursor}

    def poll(self) -> list[str]:
        cmd = ["journalctl", "-o", "json", "--no-pager", "-q"]
        for u in self.UNITS:
            cmd += ["-u", u]
        if self.cursor:
            cmd += ["--after-cursor", self.cursor]
        else:
            cmd += ["-n", "0"]                     # first start: from now on
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return []
        out = []
        for raw in r.stdout.splitlines():
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            self.cursor = d.get("__CURSOR", self.cursor)
            msg = d.get("MESSAGE")
            if isinstance(msg, list):              # journal stores binary as byte list
                msg = bytes(msg).decode("utf-8", "replace")
            if msg:
                pid = d.get("_PID", "")
                out.append(f"sshd[{pid}]: {msg}")
        if not self.cursor and not out:
            # remember "now" so the next poll does not re-read history
            try:
                r = subprocess.run(["journalctl", "-n", "1", "-o", "json", "-q",
                                    "--no-pager"] + sum((["-u", u] for u in self.UNITS), []),
                                   capture_output=True, timeout=10)
                last = r.stdout.splitlines()[-1:] if r.stdout else []
                if last:
                    self.cursor = json.loads(last[0]).get("__CURSOR")
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
        return out


def default_source(state: Optional[dict] = None):
    """Journal if this user may read it, else auth.log, else None."""
    st = state or {}
    if st.get("kind") == "journal" or (not st.get("kind") and JournalSource.available()):
        return "journal", JournalSource(st)
    if os.access(AUTH_LOG, os.R_OK):
        return "authlog", AuthLogTail(AUTH_LOG, st)
    return None, None
