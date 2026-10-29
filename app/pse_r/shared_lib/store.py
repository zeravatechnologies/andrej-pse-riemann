"""
Mutable SHARED_LIB state, in vault/.state/shared_lib.db.

The journal is the append-only memory of what HAPPENED; this store holds what
IS: the human queue, declarations, and (from later phases) methods, missions,
reports and units. Every mutation here is also written to the journal, so the
store can be audited — and reconstructed — from history.

The human queue ("Čeka tvoju odluku") is the single place where anything that
needs a human waits: method proposals, skeptic objections, declarations,
healing actions of tier 2. A decision needs a registered operator and is
journalled with the operator's name.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .. import config
from ..core import journal as J
from . import operator as OP

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS pending (
        id          TEXT PRIMARY KEY,
        kind        TEXT NOT NULL,
        title       TEXT NOT NULL,
        payload     TEXT NOT NULL,
        proposer    TEXT NOT NULL,
        created     REAL NOT NULL,
        status      TEXT NOT NULL DEFAULT 'open',
        decided_by  TEXT,
        decided_at  REAL,
        reason      TEXT,
        consumed_at REAL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pending_status ON pending(status)",
    """CREATE TABLE IF NOT EXISTS declarations (
        version      INTEGER PRIMARY KEY,
        data         TEXT NOT NULL,
        confirmed_by TEXT NOT NULL,
        confirmed_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS kv (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
]

OPEN, APPROVED, REJECTED, WITHDRAWN = "open", "approved", "rejected", "withdrawn"
DECISION = "decision"           # journal kind for every human-queue event


class Store:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or config.SHARED_LIB_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._on_decision: dict[str, list[Callable[[dict, bool], None]]] = {}
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            for ddl in _SCHEMA:
                self._conn.execute(ddl)
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(pending)")}
            if "consumed_at" not in cols:           # databases from round 2
                self._conn.execute("ALTER TABLE pending ADD COLUMN consumed_at REAL")
            self._conn.commit()

    # ---- schema extension (later phases add their tables) -------------- #
    def ensure(self, ddl: list[str]) -> None:
        with self._lock:
            for s in ddl:
                self._conn.execute(s)
            self._conn.commit()

    def execute(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        """Write access for SHARED_LIB modules only (never exposed to models)."""
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def rows(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    # ---- human queue ---------------------------------------------------- #
    def propose(self, kind: str, title: str, payload: dict, proposer: str) -> str:
        pid = f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        self.execute("INSERT INTO pending (id,kind,title,payload,proposer,created)"
                     " VALUES (?,?,?,?,?,?)",
                     (pid, kind, title, blob, proposer, time.time()))
        J.log(DECISION, proposer, {"event": "proposed", "id": pid, "kind": kind,
                                   "title": title}, subject=pid, verdict="open")
        return pid

    def get(self, pid: str) -> Optional[dict]:
        r = self.rows("SELECT * FROM pending WHERE id=?", (pid,))
        if not r:
            return None
        d = r[0]
        d["payload"] = json.loads(d["payload"])
        return d

    def open_items(self, kind: str = "") -> list[dict]:
        q, a = "SELECT * FROM pending WHERE status='open'", ()
        if kind:
            q, a = q + " AND kind=?", (kind,)
        out = self.rows(q + " ORDER BY created", a)
        for d in out:
            d["payload"] = json.loads(d["payload"])
        return out

    def on_decision(self, kind: str, fn: Callable[[dict, bool], None]) -> None:
        """Register what happens after a human decides an item of `kind`.
        Idempotent: registering the same function twice must not make one
        human decision take effect twice."""
        fns = self._on_decision.setdefault(kind, [])
        if fn not in fns:
            fns.append(fn)

    def decide(self, pid: str, approve: bool, reason: str = "") -> dict:
        """
        One decision = one execution (fixes A4; S2 + P5 without rank).
        The open → decided transition is a single conditional UPDATE, so of two
        racing decisions exactly one wins and the other gets "već odlučeno".
        The winner then CONSUMES the decision (another conditional UPDATE) and
        only the consumer runs the hooks — a decision can never take effect
        twice, not even if decide() is re-entered or the hooks are re-run.
        """
        who = OP.require_operator()
        item = self.get(pid)
        if item is None:
            raise KeyError(pid)
        status = APPROVED if approve else REJECTED
        cur = self.execute("UPDATE pending SET status=?, decided_by=?, decided_at=?, reason=?"
                           " WHERE id=? AND status='open'",
                           (status, who, time.time(), reason, pid))
        if cur.rowcount != 1:
            now = self.get(pid)
            raise ValueError(f"'{pid}' je već odlučeno ({now['status'] if now else '?'})")
        J.log(DECISION, who, {"event": status, "id": pid, "kind": item["kind"],
                              "reason": reason}, subject=pid, verdict=status)
        item = self.get(pid)
        if self.consume(pid):
            for fn in self._on_decision.get(item["kind"], []):
                try:
                    fn(item, approve)
                except Exception as e:              # noqa: BLE001
                    J.log(DECISION, "system", {"event": "hook_failed", "id": pid,
                                               "kind": item["kind"], "error": str(e)[:300]},
                          subject=pid, verdict="hook_failed")
                    raise
        return item

    def consume(self, pid: str) -> bool:
        """Atomically mark a decided item as executed. True exactly once."""
        cur = self.execute("UPDATE pending SET consumed_at=? WHERE id=? AND "
                           "status IN ('approved','rejected') AND consumed_at IS NULL",
                           (time.time(), pid))
        if cur.rowcount == 1:
            J.log(DECISION, "system", {"event": "consumed", "id": pid},
                  subject=pid, verdict="consumed")
            return True
        return False

    def withdraw(self, pid: str, actor: str, reason: str) -> None:
        self.execute("UPDATE pending SET status=?, reason=? WHERE id=? AND status='open'",
                     (WITHDRAWN, reason, pid))
        J.log(DECISION, actor, {"event": WITHDRAWN, "id": pid, "reason": reason},
              subject=pid, verdict=WITHDRAWN)

    # ---- kv -------------------------------------------------------------- #
    def kv_get(self, key: str, default=None):
        r = self.rows("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(r[0]["value"]) if r else default

    def kv_set(self, key: str, value) -> None:
        self.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO "
                     "UPDATE SET value=excluded.value",
                     (key, json.dumps(value, ensure_ascii=False, default=str)))

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_STORE: Optional[Store] = None


def store() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store()
    return _STORE


def _reset_for_tests() -> None:
    global _STORE
    if _STORE is not None:
        _STORE.close()
    _STORE = None
