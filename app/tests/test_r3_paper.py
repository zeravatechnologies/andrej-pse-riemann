"""Round 3, item 33: the working paper from missions 2 and 3 — every number sourced,
the gate refuses proof claims, the skeptic speaks first, sealed + queued."""
import json

import pytest

from pse_r.shared_lib import paper as P


@pytest.fixture
def seeded(operator):
    from pse_r.shared_lib import missions as MIS
    from pse_r.vault import qrh_seed as QS, langlands_seed as LS
    if not QS.is_seeded():
        QS.seed_qrh()
    if not LS.is_seeded():
        LS.seed()
    MIS.seed_first()
    MIS.seed_second()
    MIS.seed_third()
    return operator


def test_unsourced_and_proof_checks():
    assert P.unsourced("B = 0.874957 bez izvora") and not P.unsourced("B = 0.874957 [lab:x]")
    assert P.proof_claims("Ovim smo dokazali Riemannovu hipotezu.")
    assert not P.proof_claims("Ovo nije dokaz Riemannove hipoteze; otvoren problem ostaje.")


def test_paper_is_built_sourced_sealed_and_queued(seeded, monkeypatch):
    from pse_r.llm import selection as SEL
    monkeypatch.setattr(SEL, "skeptic_available", lambda: True)
    ask = lambda t, x, c: json.dumps([{"prigovor": "nema recenzije", "razlog": "preprint",
                                       "gdje": "§1", "ozbiljnost": "srednja"}])
    r = P.build(ask_skeptic=ask)
    md = r["markdown"]
    assert md.count("NAŠE-NERECENZIRANO") >= 2 and "ne daje novo B" in md
    assert not P.unsourced(md) and not P.proof_claims(md)
    assert "Prigovori skeptika" in md and "nema recenzije" in md and r["objections"] == 1
    from pathlib import Path
    from pse_r.shared_lib import reports as RP
    from pse_r.shared_lib.store import store
    assert Path(r["path"]).exists()
    assert store().get(r["pid"])["kind"] == P.KIND


def test_a_proof_claim_stops_the_paper(seeded, monkeypatch):
    real = P.assemble
    monkeypatch.setattr(P, "assemble", lambda runs=None: real(runs) + "\n\nTime je Riemannova hipoteza dokazana.\n")
    with pytest.raises(P.PaperRefused, match="kapija"):
        P.build()
