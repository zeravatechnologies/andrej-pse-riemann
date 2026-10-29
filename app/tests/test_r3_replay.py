"""Round 3, item 6 (Perun P1): every automatic decision can be re-derived from
the journal; a disagreement is an integrity violation."""
import copy

from pse_r.core import journal as J
from pse_r.core import replay as R
from pse_r.shared_lib.store import store
from pse_r.vault.card import Card
from pse_r.vault.gate import gate


def _events(decider):
    return [e for e in J.journal().with_replay()
            if e["payload"]["replay"]["decider"] == decider]


def test_gate_decisions_replay_identically(operator):
    gate().submit(Card(title="r3 replay ok", status="FOLKLORE", type="note",
                       body="nešto"), actor="user")
    gate().submit(Card(title="r3 replay odbij", status="CITED", type="note",
                       body="bez izvora"), actor="user")
    evs = _events("gate.decide")[-2:]
    assert [e["verdict"] for e in evs] == ["accept", "reject"]
    rep = R.replay_all(evs, notify=False)
    assert rep.checked == 2 and rep.ok == 2 and rep.intact


def test_tampered_record_is_an_integrity_violation(operator):
    gate().submit(Card(title="r3 replay laž", status="CITED", type="note",
                       body="bez izvora"), actor="user")
    ev = copy.deepcopy(_events("gate.decide")[-1])
    ev["payload"]["replay"]["out"]["ok"] = True          # someone "fixed" a reject
    rep = R.replay_all([ev])                             # cache cannot hide a forged out
    assert not rep.intact and rep.mismatches[0][1] == "gate.decide"
    items = store().open_items(R.INTEGRITY_KIND)
    assert items and "NARUŠEN INTEGRITET" in items[0]["title"]


def test_tampered_inputs_are_caught_by_their_hash(operator):
    gate().submit(Card(title="r3 replay ulaz", status="FOLKLORE", type="note",
                       body="x"), actor="user")
    ev = copy.deepcopy(_events("gate.decide")[-1])
    ev["payload"]["replay"]["in"]["actor"] = "model:neko"
    assert R.replay_event(ev) == "redacted"              # not comparable, not silent ok


def test_doctor_and_guard_trip_replay(operator):
    from pse_r.guardian import harms as HRM
    from pse_r.llm import limits as L
    from pse_r.pse import unit as PU
    from pse_r.shared_lib import pse_registry as PR
    from pse_r.shared_lib import runtime as RT
    PR.reset_for_tests()
    lib = PR.pse()
    lib.define(PR.AgentSpec("lab-replay", PU.Mission("s", "a", "o"), 50, "lab", False))
    u = lib._spawn("lab-replay", lab=True)
    lib.move(u, words="x", harms=[HRM.Finding(HRM.AGENT, "injekcija", "x", HRM.HIGH)])
    lib.end(u, "kraj testa")
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()
    RT.install_hooks()
    L.configure(L.Limits(L_latency_s=2.0))
    L.observe("latency", 3.0)
    rep = R.replay_all(_events("doctor.examine")[-1:] + _events("guard.trip")[-1:], notify=False)
    assert rep.checked == 2 and rep.ok == 2
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()


def test_door_reproduction_replays(operator):
    from pse_r.methods import door as D
    from pse_r.methods import pack as PK
    d = PK.default_packs_dir()
    packs = sorted(d.glob("*.json")) if d else []
    assert packs, "nema paketa metoda"
    D.import_pack(packs[0], proposer="test")
    rep = R.replay_all(_events("door.reproduce")[-1:], notify=False)
    assert rep.checked == 1 and rep.ok == 1


def test_egress_policy_record_is_replayable():
    from pse_r.guardian.egress import _policy_record
    for host in ("export.arxiv.org", "zlo.example.com"):
        rec = _policy_record(host)
        ev = {"id": 0, "payload": {"replay": rec}}
        assert R.replay_event(ev) == "ok"
    rec = _policy_record("export.arxiv.org")
    rec["in"]["policy_sha"] = "0" * 64
    rec["in_sha"] = R.sha(rec["in"])
    assert R.replay_event({"payload": {"replay": rec}}) == "other_version"


def test_whole_journal_replays_clean():
    rep = R.replay_all(notify=False)
    assert rep.checked > 0
    # the deliberately tampered copies above were never written to the journal
    assert rep.intact, rep.mismatches


def test_cache_skips_only_unchanged_records(operator, monkeypatch):
    gate().submit(Card(title="r3 keš", status="FOLKLORE", type="note", body="x"),
                  actor="user")
    ev = _events("gate.decide")[-1]
    assert R.replay_all([ev], notify=False).ok == 1
    calls = []
    real = R._DECIDERS["gate.decide"].fn
    monkeypatch.setattr(R._DECIDERS["gate.decide"], "fn",
                        lambda i: calls.append(1) or real(i))
    assert R.replay_all([ev], notify=False).ok == 1 and not calls     # cached
    monkeypatch.setattr(R, "_CODE_SHA", "drugi-kod")                    # code changed
    assert R.replay_all([ev], notify=False).ok == 1 and calls          # re-derived
