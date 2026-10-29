"""
Disclosure budgets (round 3, item 21; Perun P7): how much PROTECTED content may
leave this computer, per destination and per day.

What is protected, and its default daily budget per destination:
  secret       key material (secrets store values, key-shaped strings)     0
  private      this machine's identity: private IP / MAC, home paths,
               host name, the operator's local user name                   0
  licensed     text of the locally kept papers (papers-local/, licence-
               restricted): 8-word shingles that match                      2 000 chars
Every model request to the cloud is measured BEFORE it is sent; over budget →
refused (nothing leaves) and journalled. A local GGUF is not a destination
(nothing leaves). The operator can raise a budget (settings "disclosure_L").
"""
from __future__ import annotations

import getpass
import json
import re
import socket
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..core import journal as J

DEFAULT_L = {"secret": 0, "private": 0, "licensed": 2000}
SHINGLE = 8
KV = "disclosure_spent"

_IP_PRIV = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
                      r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
_MAC = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b")
_HOME = re.compile(r"/home/[A-Za-z0-9._-]+")


class DisclosureExceeded(PermissionError):
    pass


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9čćžšđ]+", (text or "").lower())


@lru_cache(maxsize=1)
def _licensed_shingles() -> frozenset:
    from .. import config
    root = config.PROJECT_ROOT / "research"
    out = set()
    if not root.exists():
        return frozenset()
    for d in root.glob("*/papers-local"):
        for p in d.rglob("*"):
            if p.suffix.lower() not in (".tex", ".txt", ".md") or not p.is_file():
                continue
            try:
                w = _words(p.read_text("utf-8", errors="replace"))
            except OSError:
                continue
            for i in range(0, max(0, len(w) - SHINGLE + 1), 2):
                out.add(" ".join(w[i:i + SHINGLE]))
    return frozenset(out)


def measure(text: str) -> dict:
    """Amount of each protected kind in `text` (chars; secrets/private: hits)."""
    from . import secrets as SEC
    out = {"secret": 0, "private": 0, "licensed": 0}
    if not text:
        return out
    if SEC.contains_secret(text):
        out["secret"] = 1
    priv = len(_IP_PRIV.findall(text)) + len(_MAC.findall(text)) + len(_HOME.findall(text))
    for ident in {socket.gethostname(), getpass.getuser()}:
        if ident and len(ident) >= 3 and re.search(r"\b" + re.escape(ident) + r"\b", text):
            priv += 1
    out["private"] = priv
    sh = _licensed_shingles()
    if sh:
        w = _words(text)
        covered = set()
        for i in range(max(0, len(w) - SHINGLE + 1)):
            if " ".join(w[i:i + SHINGLE]) in sh:
                covered.update(range(i, i + SHINGLE))
        out["licensed"] = sum(len(w[i]) + 1 for i in covered)   # chars of matching text
    return out


def _limits() -> dict:
    try:
        from .. import settings as S
        return {**DEFAULT_L, **(S.load().get("disclosure_L") or {})}
    except Exception:                                   # noqa: BLE001
        return dict(DEFAULT_L)


def _spent(dest: str) -> dict:
    from ..shared_lib.store import store
    day = time.strftime("%Y-%m-%d")
    all_ = store().kv_get(KV, {}) or {}
    return (all_.get(day) or {}).get(dest, {"secret": 0, "private": 0, "licensed": 0})


def check_and_spend(dest: str, text: str, actor: str = "model") -> dict:
    """Measure; refuse if any budget would be exceeded; else record the spend."""
    from ..shared_lib.store import store
    m = measure(text)
    L = _limits()
    sp = _spent(dest)
    over = [k for k, v in m.items() if v and sp.get(k, 0) + v > L.get(k, 0)]
    if over:
        J.log(J.THREAT, "disclosure", {"event": "refused", "dest": dest, "kinds": over,
                                       "amount": {k: m[k] for k in over}},
              subject=dest, verdict="refused")
        raise DisclosureExceeded(
            f"budžet otkrivanja prema {dest} bi bio prekoračen ({', '.join(over)}) — "
            f"ništa nije poslato. Ukloni zaštićeni sadržaj ili podigni budžet u postavkama.")
    if any(m.values()):
        day = time.strftime("%Y-%m-%d")
        all_ = store().kv_get(KV, {}) or {}
        d = all_.setdefault(day, {}).setdefault(dest, {"secret": 0, "private": 0,
                                                        "licensed": 0})
        for k, v in m.items():
            d[k] = d.get(k, 0) + v
        for old in sorted(all_)[:-14]:                    # keep two weeks
            all_.pop(old, None)
        store().kv_set(KV, all_)
        J.log(J.SYSTEM, "disclosure", {"event": "spent", "dest": dest, "amount": m},
              subject=dest, verdict="spent")
    return m


def payload_text(payload: dict) -> str:
    """Every string in a request payload (what would actually leave)."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in ("data", "url") or not isinstance(v, str) or len(v) < 2000:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(payload)
    return "\n".join(out)
