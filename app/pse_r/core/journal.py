"""
Append-only journal — the swarm's memory of what actually happened.

Every gate decision, every egress attempt, every theta event, every lab run and
every model call lands here. The table is append-only AT THE DATABASE LEVEL:
SQLite triggers RAISE(ABORT) on UPDATE and DELETE, so a bug (or a compromised
component) cannot quietly rewrite history. That property is the whole point —
the claim ledger's credibility rests on it.

Secrets never reach this file: every payload passes through guardian.secrets.redact
before serialization.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from .. import config

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    kind        TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    subject     TEXT,
    verdict     TEXT,
    payload     TEXT    NOT NULL,
    prev_hash   TEXT    NOT NULL,
    hash        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_subj ON events(subject);

CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'journal is append-only: UPDATE forbidden'); END;

-- Archive anchors (round 3, item 7; Perun P3). An anchor says: every event up
-- to `upto_id` has been written to `file` (sha256 = `sha256`), and the chain
-- continues from `last_hash`. Anchors are append-only like events.
CREATE TABLE IF NOT EXISTS anchors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    from_id     INTEGER NOT NULL,
    upto_id     INTEGER NOT NULL,
    count       INTEGER NOT NULL,
    first_prev  TEXT    NOT NULL,
    last_hash   TEXT    NOT NULL,
    file        TEXT    NOT NULL,
    sha256      TEXT    NOT NULL
);
CREATE TRIGGER IF NOT EXISTS anchors_no_update
BEFORE UPDATE ON anchors
BEGIN SELECT RAISE(ABORT, 'anchors are append-only: UPDATE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS anchors_no_delete
BEFORE DELETE ON anchors
BEGIN SELECT RAISE(ABORT, 'anchors are append-only: DELETE forbidden'); END;
"""

# DELETE is allowed ONLY for events already covered by an archive anchor; every
# other delete still aborts. (Round 2 had an unconditional ban; replaced on boot.)
_DELETE_TRIGGER = """
CREATE TRIGGER events_no_delete
BEFORE DELETE ON events
WHEN OLD.id > (SELECT COALESCE(MAX(upto_id), 0) FROM anchors)
BEGIN SELECT RAISE(ABORT, 'journal is append-only: DELETE forbidden (not archived)'); END;
"""

# Event kinds (keep the vocabulary small and stable — reports parse these)
GATE = "gate"                 # a write was accepted / rejected by the vault gate
EGRESS = "egress"             # an outbound request was allowed / blocked
THREAT = "threat"             # guardian tier-1 / tier-2 intervention
THETA = "theta"               # theta event (single gate for all theta changes)
LAB = "lab"                   # numerical experiment run
MODEL = "model"               # llm call (provider, role, tokens, cost)
INGEST = "ingest"             # source fetched / promoted / dropped
SYSTEM = "system"             # startup, wizard, config change
# v2 (SHARED_LIB layer)
DECISION = "decision"         # human queue: proposed / approved / rejected / withdrawn
METHOD = "method"             # method packs: imported, reproduced, refused
MISSION = "mission"           # mission state changes
REPORT = "report"             # final reports: issued, sealed, attacked, restored
UNIT = "unit"                 # PSE units: spawned, assigned, replaced, terminated
HEAL = "heal"                 # infection detection, containment, treatment
VOICE = "voice"               # SHARED_LIB voice: question, SQL, answer, refusals


class Journal:
    """Thread-safe append-only event log with a per-row hash chain."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or config.JOURNAL_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            row = self._conn.execute("SELECT sql FROM sqlite_master WHERE type='trigger'"
                                     " AND name='events_no_delete'").fetchone()
            if row is None or "anchors" not in (row["sql"] or ""):
                self._conn.execute("DROP TRIGGER IF EXISTS events_no_delete")
                self._conn.executescript(_DELETE_TRIGGER)
            self._conn.commit()

    # -- write ------------------------------------------------------------- #
    def append(self, kind: str, actor: str, payload: dict,
               subject: str = "", verdict: str = "") -> int:
        """Append one event. Returns its rowid. Never raises on payload content."""
        from ..guardian.secrets import redact          # local import: avoids a cycle
        safe = redact(payload)
        blob = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
        ts = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
            prev = row["hash"] if row else "genesis"
            h = hashlib.sha256(
                f"{prev}|{ts}|{kind}|{actor}|{subject}|{verdict}|{blob}".encode()
            ).hexdigest()
            cur = self._conn.execute(
                "INSERT INTO events (ts,kind,actor,subject,verdict,payload,prev_hash,hash)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (ts, kind, actor, subject, verdict, blob, prev, h))
            self._conn.commit()
            return int(cur.lastrowid)

    # -- read -------------------------------------------------------------- #
    def tail(self, n: int = 50, kind: str = "") -> list[dict]:
        q = "SELECT * FROM events"
        args: list[Any] = []
        if kind:
            q += " WHERE kind=?"
            args.append(kind)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(n)
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows][::-1]

    def since(self, ts: float, kind: str = "") -> list[dict]:
        q = "SELECT * FROM events WHERE ts>=?"
        args: list[Any] = [ts]
        if kind:
            q += " AND kind=?"
            args.append(kind)
        q += " ORDER BY id ASC"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows]

    def with_replay(self, batch: int = 500):
        """Every event that carries a replay record, oldest first (streamed)."""
        last = 0
        while True:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT * FROM events WHERE id > ? AND payload LIKE '%\"replay\":%'"
                    " ORDER BY id LIMIT ?", (last, batch)).fetchall()
            if not rows:
                return
            for r in rows:
                last = r["id"]
                yield self._row(r)

    def count(self, kind: str = "") -> int:
        with self._lock:
            if kind:
                r = self._conn.execute(
                    "SELECT COUNT(*) c FROM events WHERE kind=?", (kind,)).fetchone()
            else:
                r = self._conn.execute("SELECT COUNT(*) c FROM events").fetchone()
        return int(r["c"])

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
        return d

    # -- integrity ---------------------------------------------------------- #
    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """
        Recompute the hash chain. Returns (ok, first_bad_id).
        A break means the db file was tampered with out-of-process — the triggers
        stop in-process rewrites, this catches everything else.
        """
        prev = "genesis"
        with self._lock:
            rows = self._conn.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
            a = self._conn.execute("SELECT * FROM anchors ORDER BY upto_id DESC LIMIT 1"
                                   ).fetchone()
        if a is not None and rows and rows[0]["id"] > 1:
            # the head was archived: the chain must continue exactly from the anchor
            if rows[0]["id"] != a["upto_id"] + 1:
                return False, int(rows[0]["id"])
            prev = a["last_hash"]
        for r in rows:
            h = hashlib.sha256(
                f"{prev}|{r['ts']}|{r['kind']}|{r['actor']}|{r['subject']}|"
                f"{r['verdict']}|{r['payload']}".encode()).hexdigest()
            if h != r["hash"] or r["prev_hash"] != prev:
                return False, int(r["id"])
            prev = r["hash"]
        return True, None

    def anchors(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM anchors ORDER BY upto_id").fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_JOURNAL: Optional[Journal] = None


def journal() -> Journal:
    """Process-wide singleton. Everything logs through this."""
    global _JOURNAL
    if _JOURNAL is None:
        _JOURNAL = Journal()
    return _JOURNAL


def log(kind: str, actor: str, payload: dict, subject: str = "", verdict: str = "") -> int:
    """Append an event; the registered operator (if any) is bound to every event."""
    try:
        from ..shared_lib.operator import current
        op = current()
    except Exception:                                   # noqa: BLE001
        op = None
    if op and isinstance(payload, dict) and "operator" not in payload:
        payload = {**payload, "operator": op}
    return journal().append(kind, actor, payload, subject, verdict)
