"""Round 3, item 7 (S8 + P3): the journal is trimmed only behind an archive
anchor; the archive is sealed by sha256 and the chain continues across it."""
import os
import sqlite3

import pytest

from pse_r.core import archive as AR
from pse_r.core import journal as J
from pse_r.core import replay as R


def _fill(n):
    for i in range(n):
        J.log(J.SYSTEM, "test", {"event": "r3-fill", "i": i})


def test_plain_delete_still_forbidden():
    _fill(3)
    jr = J.journal()
    top = jr._conn.execute("SELECT MAX(id) FROM events").fetchone()[0]
    with pytest.raises(sqlite3.DatabaseError):
        jr._conn.execute("DELETE FROM events WHERE id = ?", (top,))
    jr._conn.rollback()


def test_archive_then_trim_keeps_the_chain(operator):
    from pse_r.vault.card import Card
    from pse_r.vault.gate import gate
    gate().submit(Card(title="r3 arhiva", status="FOLKLORE", type="note", body="x"),
                  actor="user")                    # a replayable decision gets archived
    _fill(30)
    jr = J.journal()
    top = jr._conn.execute("SELECT MAX(id) FROM events").fetchone()[0]
    before_replay = R.replay_all(notify=False).checked
    a = AR.archive_upto(top - 5)
    assert a and a["count"] >= 30
    assert jr._conn.execute("SELECT MIN(id) FROM events").fetchone()[0] == a["upto_id"] + 1
    ok, bad = jr.verify_chain()
    assert ok, bad
    aok, problems = AR.verify_archives()
    assert aok, problems
    assert not os.access(AR.archive_dir() / a["file"], os.W_OK) or os.geteuid() == 0
    # archived decisions are still replayable
    assert R.replay_all(notify=False).checked == before_replay
    # anchors themselves cannot be removed
    with pytest.raises(sqlite3.DatabaseError):
        jr._conn.execute("DELETE FROM anchors")
    jr._conn.rollback()


def test_tampered_archive_is_detected():
    _fill(10)
    jr = J.journal()
    top = jr._conn.execute("SELECT MAX(id) FROM events").fetchone()[0]
    a = AR.archive_upto(top - 2)
    p = AR.archive_dir() / a["file"]
    os.chmod(p, 0o644)
    data = p.read_bytes()
    p.write_bytes(data[:-10] + b"0123456789")
    aok, problems = AR.verify_archives()
    assert not aok and any(a["file"] in x for x in problems)
    p.write_bytes(data)                              # put it back for later tests
    os.chmod(p, 0o444)
    assert AR.verify_archives()[0]


def test_retention_policy_keeps_minimum_live():
    _fill(40)
    jr = J.journal()
    n = jr._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    out = AR.retention_round(keep_days=0, keep_min=15, max_live=20)
    assert out["archived"]
    assert jr._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] in range(15, 18)
    assert AR.retention_round(keep_days=0, keep_min=15, max_live=10_000)["archived"] is False
    assert jr.verify_chain()[0] and AR.verify_archives()[0]
