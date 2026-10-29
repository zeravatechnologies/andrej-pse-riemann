"""
The read-only fact layer of SHARED_LIB.

Every question asked of SHARED_LIB — by the operator directly, or by a model
translating the operator's words — becomes ONE SELECT over the views below.
Nothing else is executable here:

  * the statement must be a single SELECT / WITH
  * an SQLite authorizer allows only SELECT, READ, FUNCTION and RECURSIVE
    actions, so INSERT/UPDATE/DELETE/ATTACH/PRAGMA/CREATE are refused by the
    engine itself, not by a regex we hope is complete
  * the source databases are attached with mode=ro
  * a progress handler aborts runaway queries

That is what "cold hard facts" means mechanically: an answer about the library
is a row set produced by the engine, with the SQL shown beside it.

Views
  cards            every vault card (id, title, type, status, tier, author, …, body)
  lab_runs         every lab run record (run_id, experiment, params, numbers, sha)
  events           the append-only journal (time, kind, actor, subject, verdict, payload)
  guardian_events  journal rows of kind egress / threat
  pending, declarations, … every table of the mutable SHARED_LIB store
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from .. import config
from ..vault import store as VS
from ..vault import tiers as _TIERS

MAX_ROWS = 500
MAX_STEPS = 5_000_000           # progress-handler budget (~ a few seconds)

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                    sqlite3.SQLITE_FUNCTION, getattr(sqlite3, "SQLITE_RECURSIVE", 33)}
_FORBIDDEN_FUNCS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class QueryRefused(Exception):
    pass


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.S).strip()


def _check_shape(sql: str) -> str:
    s = _strip_comments(sql).rstrip().rstrip(";").strip()
    if ";" in s:
        raise QueryRefused("dozvoljena je tačno jedna SELECT naredba")
    if not re.match(r"(?is)^(select|with)\b", s):
        raise QueryRefused("dozvoljeno je samo čitanje (SELECT / WITH)")
    return s


def _authorizer(action, arg1, arg2, dbname, source):
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _FORBIDDEN_FUNCS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _ro_uri(p: Path) -> str:
    return Path(p).resolve().as_uri() + "?mode=ro"


def _load_cards(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TEMP TABLE cards (id TEXT, title TEXT, type TEXT,
        status TEXT, tier TEXT, author TEXT, created TEXT, updated TEXT,
        lab_run TEXT, script_sha256 TEXT, sources TEXT, depends_on TEXT,
        tags TEXT, dir TEXT, body TEXT)""")
    rows = []
    for p in VS.iter_paths():
        try:
            c = VS.Card.load(p)
        except (OSError, UnicodeDecodeError):
            continue
        rows.append((c.id, c.title, c.type, c.status, _TIERS.card_tier(c),
                     c.author, c.created, c.updated, c.lab_run, c.script_sha256,
                     json.dumps(c.sources, ensure_ascii=False),
                     json.dumps(c.depends_on, ensure_ascii=False),
                     json.dumps(c.tags, ensure_ascii=False), p.parent.name, c.body))
    conn.executemany("INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def _load_lab_runs(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TEMP TABLE lab_runs (run_id TEXT, experiment TEXT,
        title TEXT, created TEXT, script_sha256 TEXT, params TEXT, numbers TEXT,
        reading TEXT, elapsed_s REAL)""")
    rows = []
    if config.DIR_LAB.exists():
        for f in sorted(config.DIR_LAB.glob("*/result.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rows.append((d.get("run_id", f.parent.name), d.get("experiment", ""),
                         d.get("title", ""), d.get("when", ""),
                         d.get("script_sha256", ""),
                         json.dumps(d.get("params", {}), ensure_ascii=False),
                         json.dumps(d.get("numbers", {}), ensure_ascii=False),
                         d.get("reading", ""), d.get("elapsed_s", 0.0)))
    conn.executemany("INSERT INTO lab_runs VALUES (?,?,?,?,?,?,?,?,?)", rows)


def connect() -> sqlite3.Connection:
    """A fresh read-only fact connection with every view in place."""
    config.ensure_vault()
    # Make sure the SHARED_LIB store and its standard tables exist, so the fact
    # layer always exposes pending / declarations / missions (even when empty).
    from .store import store
    store()
    try:
        from . import missions as _M
        _M._ensure()
    except Exception:                                   # noqa: BLE001
        pass
    conn = sqlite3.connect(":memory:", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _load_cards(conn)
    _load_lab_runs(conn)
    if config.JOURNAL_DB.exists():
        conn.execute("ATTACH DATABASE ? AS j", (_ro_uri(config.JOURNAL_DB),))
        conn.execute("""CREATE TEMP VIEW events AS SELECT id, ts,
            datetime(ts,'unixepoch','localtime') AS time, kind, actor, subject,
            verdict, payload, hash FROM j.events""")
    else:
        conn.execute("""CREATE TEMP TABLE events (id INTEGER, ts REAL, time TEXT,
            kind TEXT, actor TEXT, subject TEXT, verdict TEXT, payload TEXT, hash TEXT)""")
    conn.execute("CREATE TEMP VIEW guardian_events AS SELECT * FROM events "
                 "WHERE kind IN ('egress','threat')")
    if config.SHARED_LIB_DB.exists():
        conn.execute("ATTACH DATABASE ? AS s", (_ro_uri(config.SHARED_LIB_DB),))
        for (name,) in conn.execute(
                "SELECT name FROM s.sqlite_master WHERE type='table' "
                "AND name!='kv' AND name NOT LIKE 'sqlite_%'"):
            conn.execute(f'CREATE TEMP VIEW "{name}" AS SELECT * FROM s."{name}"')
    return conn


def schema() -> dict[str, list[str]]:
    """View name -> column names. Fed to whoever translates words into SQL."""
    conn = connect()
    try:
        out = {}
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_temp_master WHERE type IN ('table','view') "
                "ORDER BY name"):
            out[name] = [r[1] for r in conn.execute(f'PRAGMA temp.table_info("{name}")')]
        return out
    finally:
        conn.close()


def query(sql: str, params: tuple = (), limit: int = MAX_ROWS,
          conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    Run ONE read-only SELECT. Returns {"sql", "columns", "rows", "truncated"}.
    Raises QueryRefused for anything that is not a read.
    """
    stmt = _check_shape(sql)
    own = conn is None
    conn = conn or connect()
    steps = {"n": 0}

    def _progress():
        steps["n"] += 1
        return 1 if steps["n"] * 1000 > MAX_STEPS else 0

    try:
        conn.set_authorizer(_authorizer)
        conn.set_progress_handler(_progress, 1000)
        try:
            cur = conn.execute(stmt, params)
        except sqlite3.DatabaseError as e:
            msg = str(e)
            if "not authorized" in msg or "prohibited" in msg:
                raise QueryRefused("upit pokušava nešto osim čitanja — odbijeno") from e
            if "interrupted" in msg:
                raise QueryRefused("upit traje predugo — prekinut") from e
            raise QueryRefused(f"SQL greška: {msg}") from e
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(limit + 1)
        return {"sql": stmt, "columns": cols,
                "rows": [list(r) for r in rows[:limit]],
                "truncated": len(rows) > limit}
    finally:
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)
        if own:
            conn.close()
