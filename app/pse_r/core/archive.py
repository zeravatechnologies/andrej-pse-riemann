"""
Bounded retention with archive anchors (round 3, item 7; Svarog S8 + Perun P3).

The journal must not grow forever, and it must never lose evidence. So it is
never trimmed — it is ARCHIVED and then trimmed:

  1. the oldest events (beyond the retention window) are written, byte-exact,
     to vault/.state/archive/journal-<from>-<to>.jsonl.gz;
  2. the archive gets a sha256 and is made read-only (its seal);
  3. an ANCHOR is appended (append-only table, in the same database):
     range, count, the prev_hash of the first archived event, the hash of the
     last one, file name and sha256 — and an ordinary journal event records the
     anchor too, so the chain itself carries the proof;
  4. only then are the archived events deleted. The delete trigger permits
     exactly that: an event may be deleted only if an anchor covers it.

verify_archives() re-reads every archive: its sha256 must match the anchor, the
rows inside must hash into an unbroken chain from first_prev to last_hash, and
consecutive anchors must join (anchor n's last_hash = anchor n+1's first_prev).
The live journal then continues from the last anchor (Journal.verify_chain).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterator, Optional

from .. import config
from . import journal as J

ARCHIVE_KIND = "archive"
DEFAULT_KEEP_DAYS = 90          # keep at least this much history live
DEFAULT_KEEP_MIN = 20_000       # …and never fewer than this many events
DEFAULT_MAX_LIVE = 200_000      # above this many events, archive down to KEEP_MIN


def archive_dir() -> Path:
    return config.DIR_STATE / "archive"


def _sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _row_hash(prev: str, r: dict) -> str:
    return hashlib.sha256(
        f"{prev}|{r['ts']}|{r['kind']}|{r['actor']}|{r['subject']}|"
        f"{r['verdict']}|{r['payload']}".encode()).hexdigest()


def archive_upto(upto_id: int, actor: str = "retention") -> Optional[dict]:
    """Archive and then delete every live event with id ≤ upto_id."""
    jr = J.journal()
    with jr._lock:
        rows = [dict(r) for r in jr._conn.execute(
            "SELECT * FROM events WHERE id <= ? ORDER BY id", (upto_id,)).fetchall()]
    if not rows:
        return None
    ok, bad = jr.verify_chain()
    if not ok:
        raise RuntimeError(f"lanac dnevnika je prekinut na {bad} — arhiviranje odbijeno")
    d = archive_dir()
    d.mkdir(parents=True, exist_ok=True)
    first, last = rows[0]["id"], rows[-1]["id"]
    path = d / f"journal-{first:09d}-{last:09d}.jsonl.gz"
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for r in rows:                      # payload stays the exact stored string
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)
    digest = _sha_file(path)
    os.chmod(path, 0o444)                   # the seal: read-only + sha256 in the chain
    anchor = {"ts": time.time(), "from_id": first, "upto_id": last, "count": len(rows),
              "first_prev": rows[0]["prev_hash"], "last_hash": rows[-1]["hash"],
              "file": path.name, "sha256": digest}
    with jr._lock:
        jr._conn.execute(
            "INSERT INTO anchors (ts,from_id,upto_id,count,first_prev,last_hash,file,sha256)"
            " VALUES (:ts,:from_id,:upto_id,:count,:first_prev,:last_hash,:file,:sha256)",
            anchor)
        jr._conn.commit()
    J.log(ARCHIVE_KIND, actor, {"event": "archived", **anchor}, subject=path.name,
          verdict="archived")
    with jr._lock:
        jr._conn.execute("DELETE FROM events WHERE id <= ?", (last,))
        jr._conn.commit()
    return anchor


def retention_round(keep_days: float = DEFAULT_KEEP_DAYS, keep_min: int = DEFAULT_KEEP_MIN,
                    max_live: int = DEFAULT_MAX_LIVE, now: Optional[float] = None) -> dict:
    """Archive when the live journal is over max_live: everything older than
    keep_days, but always leave at least keep_min events live."""
    jr = J.journal()
    with jr._lock:
        n = jr._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if n <= max_live:
            return {"archived": False, "live": n}
        cutoff = (now or time.time()) - keep_days * 86400
        by_age = jr._conn.execute("SELECT MAX(id) FROM events WHERE ts < ?",
                                  (cutoff,)).fetchone()[0] or 0
        by_min = jr._conn.execute(
            "SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?",
            (keep_min,)).fetchone()
    upto = min(by_age, by_min[0] if by_min else 0)
    if upto <= 0:
        return {"archived": False, "live": n}
    a = archive_upto(upto)
    return {"archived": bool(a), "live": n, "anchor": a}


def read_archive(name: str) -> Iterator[dict]:
    with gzip.open(archive_dir() / name, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def verify_archives() -> tuple[bool, list[str]]:
    """Every archive matches its anchor, chains internally, and joins the next."""
    problems = []
    prev_last = None
    for a in J.journal().anchors():
        p = archive_dir() / a["file"]
        if not p.exists():
            problems.append(f"{a['file']}: arhiva nedostaje")
            prev_last = a["last_hash"]
            continue
        if _sha_file(p) != a["sha256"]:
            problems.append(f"{a['file']}: sha256 se ne poklapa sa sidrom")
        if prev_last is not None and a["first_prev"] != prev_last:
            problems.append(f"{a['file']}: ne nastavlja se na prethodno sidro")
        prev, n = a["first_prev"], 0
        try:
            for r in read_archive(a["file"]):
                if r["prev_hash"] != prev or _row_hash(prev, r) != r["hash"]:
                    problems.append(f"{a['file']}: lanac prekinut na {r['id']}")
                    break
                prev, n = r["hash"], n + 1
        except Exception as e:                          # noqa: BLE001 — gzip/zlib/json
            problems.append(f"{a['file']}: ne može se pročitati ({e})")
            continue
        if prev != a["last_hash"] or n != a["count"]:
            problems.append(f"{a['file']}: kraj lanca ili broj zapisa ≠ sidro")
        prev_last = a["last_hash"]
    return (not problems), problems


def archived_events_with_replay() -> Iterator[dict]:
    """Archived events that carry a replay record (for core.replay)."""
    for a in J.journal().anchors():
        try:
            for r in read_archive(a["file"]):
                if '"replay":' in r["payload"]:
                    r = dict(r)
                    r["payload"] = json.loads(r["payload"])
                    yield r
        except Exception:                               # noqa: BLE001
            continue
