"""Round 3, item 25: the Langlands / higher-degree source cards pass the gate
with the right tiers, and nothing claims a transfer of 7/8."""
from pse_r.vault import langlands_seed as LS
from pse_r.vault import tiers as T
from pse_r.vault.card import Card
from pse_r.vault.gate import gate


def test_seed_passes_gate_with_tiers(operator):
    out = LS.seed()
    assert all(v in ("ok", "skip") for v in out.values()), out
    nt = Card.load(gate().find("izvor-newton-thorne-i"))
    assert T.card_tier(nt) == "REFEREED"
    glc = Card.load(gate().find("izvor-glc-i-2405-03599"))
    assert T.card_tier(glc) == "PREPRINT"
    topic = Card.load(gate().find(LS.TOPIC_ID))
    assert topic.status == "FOLKLORE" and "Otvoreno pitanje" in topic.body
    assert LS.is_seeded()
