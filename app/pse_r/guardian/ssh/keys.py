"""
Counting by the three keys of master §10.6, each under "→ ∞" (§5).

  IDENTITY  who asks              — the source IP
  CLUSTER   which family of text  — the SHAPE of the attempt (kind + auth method,
                                    e.g. "invalid_user:-" or "fail:password"), the
                                    "family of similar messages" of master §10.2: an
                                    attacker rotating user names, or IPs, still
                                    accumulates here. (Round 3 benchmark: with the user
                                    name as cluster a one-IP dictionary attack never
                                    tripped all three keys and was never blocked.)
  TARGET    what on this host     — the real account attacked, or "sshd" itself
                                    (invalid users, protocol abuse). The strongest key.

A count is kept per time window. A key "tends to infinity" when the current
window is above its limit L, or when it grew three windows running (four
rising windows). The limits L are the operator's (settings "ssh_L").
"""
from __future__ import annotations

import pwd
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_L = {"identity": 10, "cluster": 10, "target": 10}
WINDOW_S = 300
KEEP = 8


def local_accounts() -> set[str]:
    try:
        return {p.pw_name for p in pwd.getpwall()}
    except Exception:                                   # noqa: BLE001
        return set()


@dataclass
class Series:
    windows: deque = field(default_factory=lambda: deque(maxlen=KEEP))   # [start, count]

    def add(self, t: float, w: int = WINDOW_S) -> None:
        start = int(t // w) * w
        if self.windows and self.windows[-1][0] == start:
            self.windows[-1][1] += 1
            return
        # empty windows in between count as zero (a pause breaks a climb)
        if self.windows:
            nxt = self.windows[-1][0] + w
            while nxt < start and len(self.windows) < KEEP * 4:
                self.windows.append([nxt, 0])
                nxt += w
        self.windows.append([start, 1])

    def current(self) -> int:
        return self.windows[-1][1] if self.windows else 0

    def diverging(self, L: float) -> bool:
        if self.current() > L:
            return True
        c = [x[1] for x in list(self.windows)[-4:]]
        return len(c) == 4 and c[0] < c[1] < c[2] < c[3]


class ThreeKeys:
    def __init__(self, limits: Optional[dict] = None, accounts: Optional[set] = None):
        self.L = {**DEFAULT_L, **(limits or {})}
        self.accounts = accounts if accounts is not None else local_accounts()
        self.s: dict[str, dict[str, Series]] = {"identity": {}, "cluster": {},
                                                "target": {}}

    def target_of(self, user: str) -> str:
        return user if user and user in self.accounts else "sshd"

    def keys_of(self, ip: str, user: str, shape: str = "") -> dict:
        return {"identity": ip, "cluster": shape or "(nepoznat oblik)",
                "target": self.target_of(user)}

    def observe(self, ip: str, user: str, t: Optional[float] = None,
                shape: str = "") -> dict:
        """Count one hostile event. Returns {key: {"value", "count", "diverging"}}."""
        t = t or time.time()
        out = {}
        for key, val in self.keys_of(ip, user, shape).items():
            ser = self.s[key].setdefault(val, Series())
            ser.add(t)
            out[key] = {"value": val, "count": ser.current(),
                        "diverging": ser.diverging(self.L[key])}
        return out

    @staticmethod
    def violated(result: dict) -> int:
        return sum(1 for r in result.values() if r["diverging"])

    def top(self, key: str, n: int = 10) -> list:
        return sorted(((v, s.current()) for v, s in self.s[key].items()),
                      key=lambda x: -x[1])[:n]
