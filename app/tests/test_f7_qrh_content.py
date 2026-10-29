"""F7 — QRH content: source cards, topic, barriers; tiers honest; labs → COMPUTED."""
from pse_r.vault import qrh_seed as QS
from pse_r.vault import tiers as T
from pse_r.vault.card import Card, CITED, FOLKLORE
from pse_r.vault.gate import gate


def test_seed_is_idempotent_and_creates_the_topic():
    QS.seed_qrh()
    assert QS.is_seeded()
    assert QS.seed_qrh()["topic"] == "skip"            # idempotent (already seeded)


def test_liu_and_xu_sang_are_cited_preprint_the_rest_folklore():
    QS.seed_qrh()
    liu = gate().find("izvor-liu-2610-12234")
    assert liu is not None
    c = Card.load(liu)
    assert c.status == CITED and T.card_tier(c) == T.PREPRINT
    # OpenAI has no resolvable id in our material → honest FOLKLORE, not a fake CITED
    oa = Card.load(gate().find("izvor-openai-7-8"))
    assert oa.status == FOLKLORE and T.card_tier(oa) == T.UNSOURCED


def test_topic_and_barriers_are_queryable(operator):
    from pse_r.shared_lib import views as V
    QS.seed_qrh()
    r = V.query("SELECT id, type FROM cards WHERE id='tema-quasi-rh'")
    assert r["rows"] and r["rows"][0][1] == "note"
    r2 = V.query("SELECT id FROM cards WHERE type='barrier'")
    assert any(row[0] == "barijere-quasi-rh" for row in r2["rows"])


def test_run_labs_produces_computed_our_results():
    r = QS.seed_qrh(force=True, run_labs=True)
    labs = r.get("labs", {})
    # qrh_poly and qrh_walls are fast and must have produced COMPUTED cards
    assert labs.get("qrh_poly") and not str(labs["qrh_poly"]).startswith("fail")
    card = gate().find(labs["qrh_poly"])
    assert card is not None
    c = Card.load(card)
    assert c.status == "COMPUTED" and T.card_tier(c) == T.OURS      # NAŠE-NERECENZIRANO
