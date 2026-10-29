"""
Report keepers (plan F5, master §10).

The moment a final report exists, SHARED_LIB guards it "like gold": a sealed
copy plus its sha256 go into the journal chain, the original is made read-only,
and a keeper patrol verifies it. If a sealed report is changed on disk, the
keeper restores it from the seal, holds, and tells the operator.

Keepers are PSE units with one mission — guard these files — and they are
allocated in proportion to resources, never one-per-file: a few keepers can
watch many reports. A keeper that "sleeps" (never reports though files change —
the schizoid pattern, §10.7) is replaced; that lives with healing.py.

The seal records live in the SHARED_LIB store (table `seals`), so they are part
of the read-only fact layer like everything else.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from .. import config
from ..core import journal as J
from . import operator as OP
from .store import store

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS seals (
        path        TEXT PRIMARY KEY,
        sha256      TEXT NOT NULL,
        sealed_copy TEXT NOT NULL,
        sealed_at   REAL NOT NULL,
        sealed_by   TEXT NOT NULL
    )""",
]


def _ensure() -> None:
    store().ensure(_SCHEMA)


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def keepers_for(n_reports: int, free_ram_gb: Optional[float] = None,
                cores: Optional[int] = None) -> int:
    """
    How many keeper units to dispatch — proportional to resources, NOT 1:1.
    A few keepers watch many files; none are spawned when there is nothing to
    guard, and the count is capped so guarding never starves the real work.
    """
    if n_reports <= 0:
        return 0
    from ..llm import limits as L
    ram = free_ram_gb if free_ram_gb is not None else L.free_ram_gb()
    cpu = cores if cores is not None else L.cpu_count()
    budget = max(1, min(int(ram // 4), cpu - 1))        # ~1 keeper per 4 GB free, < cores
    return max(1, min(budget, (n_reports + 3) // 4))    # ~1 keeper per 4 reports


def seal(path, actor: Optional[str] = None) -> dict:
    """Seal a final report: hash it, copy it aside, make it read-only, journal it."""
    _ensure()
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    who = actor or OP.current() or "system"
    digest = sha256_of(p)
    config.DIR_SEALS.mkdir(parents=True, exist_ok=True)
    sealed_copy = config.DIR_SEALS / f"{p.name}.{digest[:12]}.seal"
    shutil.copy2(p, sealed_copy)
    try:
        os.chmod(p, 0o444)                              # read-only original
    except OSError:
        pass
    store().execute(
        "INSERT INTO seals(path,sha256,sealed_copy,sealed_at,sealed_by) VALUES(?,?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, "
        "sealed_copy=excluded.sealed_copy, sealed_at=excluded.sealed_at, "
        "sealed_by=excluded.sealed_by",
        (str(p), digest, str(sealed_copy), time.time(), who))
    J.log(J.REPORT, who, {"event": "sealed", "path": str(p), "sha256": digest},
          subject=p.name, verdict="sealed")
    return {"path": str(p), "sha256": digest, "sealed_copy": str(sealed_copy)}


def _record(path: Path) -> Optional[dict]:
    _ensure()
    r = store().rows("SELECT * FROM seals WHERE path=?", (str(path.resolve()),))
    return r[0] if r else None


def verify(path) -> dict:
    """Compare the file on disk to its seal. {sealed, ok, sha256, current}."""
    p = Path(path).resolve()
    rec = _record(p)
    if rec is None:
        return {"sealed": False, "ok": True, "sha256": "", "current": ""}
    cur = sha256_of(p) if p.is_file() else ""
    return {"sealed": True, "ok": cur == rec["sha256"], "sha256": rec["sha256"],
            "current": cur}


def restore(path, actor: Optional[str] = None) -> bool:
    """Put the sealed copy back over a tampered/missing original."""
    p = Path(path).resolve()
    rec = _record(p)
    if rec is None:
        return False
    who = actor or OP.current() or "system"
    from ..core import actions as A
    A.require_auto("vraćanje-fajlova-iz-pečata")
    try:
        os.chmod(p, 0o644)
    except OSError:
        pass
    kept = ""
    if p.is_file():                         # keep the tampered version: reversible
        fdir = config.DIR_STATE / "forensic"
        fdir.mkdir(parents=True, exist_ok=True)
        bad = sha256_of(p)
        dst = fdir / f"{p.name}.{bad[:12]}.{time.strftime('%Y%m%d-%H%M%S')}.tampered"
        shutil.copy2(p, dst)
        kept = str(dst)
    shutil.copy2(rec["sealed_copy"], p)
    try:
        os.chmod(p, 0o444)
    except OSError:
        pass
    J.log(J.REPORT, who, {"event": "restored", "path": str(p),
                          "sha256": rec["sha256"], "tampered_copy": kept},
          subject=p.name, verdict="restored")
    return True


def patrol(actor: Optional[str] = None, auto_restore: bool = True) -> list[dict]:
    """
    The keeper's round: check every sealed report. For each tampered one, record
    a threat and (by default) restore it from the seal. Returns the events seen.
    """
    _ensure()
    who = actor or OP.current() or "keeper"
    events = []
    for rec in store().rows("SELECT * FROM seals"):
        p = Path(rec["path"])
        v = verify(p)
        if not v["ok"]:
            J.log(J.THREAT, who, {"event": "seal_broken", "path": rec["path"],
                                  "expected": rec["sha256"][:16],
                                  "found": v["current"][:16]},
                  subject=p.name, verdict="threat")
            restored = restore(p, who) if auto_restore else False
            events.append({"path": rec["path"], "tampered": True,
                           "restored": restored})
    return events


def sealed() -> list[dict]:
    _ensure()
    return store().rows("SELECT path, sha256, sealed_at, sealed_by FROM seals "
                        "ORDER BY sealed_at")
