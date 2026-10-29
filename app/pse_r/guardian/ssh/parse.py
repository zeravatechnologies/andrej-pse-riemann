"""sshd log lines → events. Pure text, no I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_IP = r"(?P<ip>[0-9a-fA-F:.]+)"
_PID = re.compile(r"sshd(?:-session)?\[(?P<pid>\d+)\]:\s*(?P<msg>.*)$")

FAIL, INVALID, ACCEPT, PREAUTH_CLOSE, MAXAUTH, NOIDENT, BADPROTO = (
    "fail", "invalid_user", "accept", "preauth_close", "max_auth", "no_ident", "bad_proto")

_RULES = [
    (FAIL, re.compile(r"^Failed (?P<method>\S+) for (?:invalid user )?(?P<user>\S*) from "
                      + _IP + r" port \d+")),
    (INVALID, re.compile(r"^Invalid user (?P<user>\S*) from " + _IP)),
    (ACCEPT, re.compile(r"^Accepted (?P<method>\S+) for (?P<user>\S+) from " + _IP)),
    (MAXAUTH, re.compile(r"^(?:error: )?maximum authentication attempts exceeded for "
                         r"(?:invalid user )?(?P<user>\S*) from " + _IP)),
    (PREAUTH_CLOSE, re.compile(r"^(?:Connection closed|Disconnected) by (?:authenticating |"
                               r"invalid )?user (?P<user>\S*) " + _IP + r" port \d+ \[preauth\]")),
    (PREAUTH_CLOSE, re.compile(r"^Connection (?:closed|reset) by " + _IP +
                               r" port \d+ \[preauth\]")),
    (NOIDENT, re.compile(r"^Did not receive identification string from " + _IP)),
    (BADPROTO, re.compile(r"^(?:error: )?(?:kex_exchange_identification|banner exchange)"
                          r".*?(?:from )?" + _IP + r"? ?port")),
]
HOSTILE = {FAIL, INVALID, MAXAUTH, NOIDENT, BADPROTO, PREAUTH_CLOSE}


@dataclass(frozen=True)
class Event:
    kind: str
    ip: str
    user: str = ""
    method: str = ""
    pid: str = ""

    @property
    def hostile(self) -> bool:
        return self.kind in HOSTILE


def parse(line: str) -> Optional[Event]:
    m = _PID.search(line or "")
    if not m:
        return None
    msg, pid = m.group("msg"), m.group("pid")
    for kind, rx in _RULES:
        mm = rx.search(msg)
        if mm:
            gd = mm.groupdict()
            ip = (gd.get("ip") or "").strip()
            if not ip or not re.fullmatch(r"[0-9a-fA-F:.]{3,45}", ip):
                return None
            return Event(kind, ip, gd.get("user") or "", gd.get("method") or "", pid)
    return None
