"""Round 3, item 28: the inspiration engine ("Ideje") — ideas, never claims;
skeptic first; at most N a week; no duplicates; operator decides; never in the vault."""
import json

import pytest

from pse_r.shared_lib import ideas as IDEAS
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib.store import store
from pse_r.llm import selection as SEL

IDEAS._SYNC_FOR_TESTS = True


class _It:
    def __init__(self, ref, title, abstract=""):
        self.source_ref, self.title, self.abstract = ref, title, abstract
        self.injection_hits = []


QRH = "zero-free half-plane for Dirichlet L-functions via large sieve, quasi-Riemann"
GL2 = "large sieve for GL(2) automorphic L-functions and symmetric power functoriality"


@pytest.fixture
def clean(operator, monkeypatch):
    MIS.seed_first()
    MIS.seed_second()
    MIS.install_hooks()
    IDEAS._ensure()
    store().execute("DELETE FROM inspiracije")
    store().kv_set(IDEAS.CAP_KEY, 3)
    store().kv_set(MIS.ACTIVE_KEY, None)
    store().execute("UPDATE missions SET parked=0, background='freeze'")
    monkeypatch.setattr(SEL, "skeptic_available", lambda: True)
    return operator


def _skeptic(title, text, ctx):
    return json.dumps([{"prigovor": "sažetak ne daje eksponent", "razlog": "nema broja",
                        "gdje": "sažetak", "ozbiljnost": "srednja"}])


def test_candidate_ranked_by_mission_and_template_never_claims(clean):
    ids = IDEAS.consider([_It("arxiv:2610.10001v2", "A", QRH),
                          _It("arxiv:2610.10002", "B", GL2),
                          _It("arxiv:2610.10003", "C", "unrelated topology of knots")],
                         ask_main=False)
    assert len(ids) == 2                                         # unrelated → no idea
    a, b = IDEAS.get(ids[0]), IDEAS.get(ids[1])
    assert a["mission_id"] == MIS.FIRST_ID and b["mission_id"] == MIS.SECOND_ID
    assert a["oznaka"] == "INSPIRACIJA" and a["title"].startswith("INSPIRACIJA")
    assert not IDEAS.is_claim(a["idea"]) and a["method_hint"]


def test_no_duplicates_same_source_or_title(clean):
    IDEAS.consider([_It("arxiv:2610.20001v1", "Zero-free regions for Dirichlet L", QRH)], ask_main=False)
    assert not IDEAS.consider([_It("arxiv:2610.20001v3", "x", QRH)], ask_main=False)
    assert not IDEAS.consider([_It("doi:10.1/zz", "Zero-free regions for Dirichlet L", QRH)],
                              ask_main=False)


def test_model_claim_refused_falls_back_to_template(clean):
    ask = lambda t, a, m: json.dumps({"ideja": "Ovim je dokazana RH.", "zasto": "z",
                                      "metoda": "m"})
    iid = IDEAS.consider([_It("arxiv:2610.30001", "T", QRH)], ask_main=ask)[0]
    r = IDEAS.get(iid)
    assert r["origin"].startswith("šablon") and "dokazan" not in r["idea"]
    ok = lambda t, a, m: json.dumps({"ideja": "Možda large sieve zamjena", "zasto": "korak 3",
                                     "metoda": "paket metode kroz vrata"})
    iid = IDEAS.consider([_It("arxiv:2610.30002", "U", QRH)], ask_main=ok)[0]
    assert IDEAS.get(iid)["origin"] == "model"


def test_weekly_cap_skeptic_first_and_badge(clean):
    titles = ["Mollifiers near the edge", "Exponential sums over primes", "Dense zero counting",
              "Hybrid large sieve bounds", "Short interval averages"]
    IDEAS.consider([_It(f"arxiv:2610.4000{i}", t, QRH) for i, t in enumerate(titles)],
                   ask_main=False)
    shown = IDEAS.publish(ask_skeptic=_skeptic)
    assert len(shown) == 3 and IDEAS.badge() == 3                 # at most 3 a week
    assert not IDEAS.publish(ask_skeptic=_skeptic)                 # week is full
    r = IDEAS.get(shown[0])
    assert r["skeptic_state"] == "napao" and r["skeptic"][0]["prigovor"]
    IDEAS.set_cap(4)
    assert len(IDEAS.publish(ask_skeptic=_skeptic)) == 1
    assert "Sedmični pregled" in IDEAS.weekly_review()


def test_skeptic_unavailable_is_said_not_hidden(clean, monkeypatch):
    monkeypatch.setattr(SEL, "skeptic_available", lambda: False)
    IDEAS.consider([_It("arxiv:2610.50001", "S", QRH)], ask_main=False)
    sid = IDEAS.publish()[0]
    assert IDEAS.get(sid)["skeptic_state"] == "nedostupan"


def test_operator_decides_once_question_becomes_mission_step(clean):
    IDEAS.consider([_It("arxiv:2610.60001", "Q1", QRH), _It("arxiv:2610.60002", "Q2", GL2),
                    _It("arxiv:2610.60003", "Q3", GL2 + " theta")], ask_main=False)
    a, b, c = IDEAS.publish(ask_skeptic=_skeptic)
    mid = IDEAS.get(a)["mission_id"]
    n0 = len(MIS.get(mid)["steps"])
    IDEAS.decide(a, "question")
    steps = MIS.get(mid)["steps"]
    assert len(steps) == n0 + 1 and "INSPIRACIJE" in steps[-1]["action"]
    with pytest.raises(ValueError):
        IDEAS.decide(a, "keep")                                    # one decision only
    IDEAS.decide(b, "drop")
    IDEAS.decide(c, "snooze")
    assert IDEAS.badge() == 0
    import time
    back = IDEAS.publish(ask_skeptic=_skeptic, now=time.time() + IDEAS.SNOOZE_S + 10)
    assert c in back                                               # snoozed comes back
    from pse_r.shared_lib import operator as OP
    OP._reset_for_tests()
    with pytest.raises(Exception):
        IDEAS.decide(c, "keep")                                    # nobody registered


def test_never_in_vault_and_frozen_mission_gets_none(clean):
    from pse_r.vault import store as VS
    before = VS.stats().total
    IDEAS.consider([_It("arxiv:2610.70001", "V", GL2)], ask_main=False)
    IDEAS.publish(ask_skeptic=_skeptic)
    assert VS.stats().total == before
    MIS.set_active(MIS.FIRST_ID)
    MIS.set_active(MIS.SECOND_ID, "pauza")                          # mission 1 parked, frozen
    assert not IDEAS.consider([_It("arxiv:2610.70002", "W", QRH)], ask_main=False,
                              missions=[MIS.FIRST_ID])
    MIS.set_background(MIS.FIRST_ID, MIS.COLLECT)                   # quiet: candidate, not shown
    iid = IDEAS.consider([_It("arxiv:2610.70003", "W2", QRH)], ask_main=False,
                         missions=[MIS.FIRST_ID])[0]
    assert iid not in IDEAS.publish(ask_skeptic=_skeptic)
    MIS.set_active(MIS.FIRST_ID, "nazad")
    assert iid in IDEAS.publish(ask_skeptic=_skeptic)


def test_geometric_langlands_only_as_inspiration(clean):
    iid = IDEAS.seed_geometric_langlands()
    r = IDEAS.get(iid)
    assert r["mission_id"] == MIS.SECOND_ID and r["oznaka"] == "INSPIRACIJA"
    assert "Gaussove sume" in r["idea"] and not IDEAS.is_claim(r["idea"])
    assert IDEAS.seed_geometric_langlands() is None                 # idempotent


def test_ideas_round_reads_per_mission(clean):
    seen = []

    def fetch(q):
        seen.append(q)
        return [_It(f"arxiv:2610.8{len(seen):04d}", f"R{len(seen)} {q}", QRH + " " + GL2)]
    r = IDEAS.ideas_round(force=True, fetch=fetch, ask_main=False, ask_skeptic=_skeptic)
    for qs in IDEAS.QUERIES.values():                               # other test missions may add
        assert all(q in seen for q in qs)                           # their own (title) queries
    assert r["candidates"] and len(r["shown"]) <= 3
    assert IDEAS.ideas_round(fetch=fetch)["skipped"]                # weekly
