"""F2 — source tiers: a preprint may not prop up an established claim."""
import pytest

from pse_r.vault import tiers as T
from pse_r.vault.card import Card, CITED, COMPUTED, SPECULATION, is_resolvable_source
from pse_r.vault.gate import gate


def test_source_tier_by_scheme():
    assert T.source_tier("doi:10.1112/plms/s3-27.3.496") == T.REFEREED
    assert T.source_tier("book:Edwards 1974, ch. 6") == T.REFEREED
    assert T.source_tier("lmfdb:zeros/zeta") == T.REFEREED
    assert T.source_tier("oeis:A000040") == T.REFEREED
    assert T.source_tier("lean:Mathlib.NumberTheory.Zeta") == T.LEAN
    assert T.source_tier("arxiv:2610.12234") == T.PREPRINT
    assert T.source_tier("wikipedia:Riemann_zeta_function") == T.PREPRINT
    assert T.source_tier("url:https://example.org/x") == T.PREPRINT
    assert T.source_tier("not a scheme") is None


def test_lean_is_a_resolvable_source():
    assert is_resolvable_source("lean:Mathlib.NumberTheory.LSeries.RiemannZeta")


def test_card_tier_from_status_author_sources():
    referee = Card(title="A", type="theorem", status=CITED, sources=["doi:10.1/x"])
    preprint = Card(title="B", type="theorem", status=CITED, sources=["arxiv:2610.12234"])
    both = Card(title="C", type="theorem", status=CITED,
                sources=["arxiv:2610.12234", "doi:10.1/x"])
    computed = Card(title="D", type="numeric-fact", status=COMPUTED,
                    author="lab", lab_run="r1", script_sha256="0" * 64)
    ai = Card(title="E", type="theorem", status=CITED, author="model:claude",
              sources=["doi:10.1/x"])
    spec = Card(title="F", status=SPECULATION, body="ideja")

    assert T.card_tier(referee) == T.REFEREED
    assert T.card_tier(preprint) == T.PREPRINT
    assert T.card_tier(both) == T.REFEREED              # strongest source wins
    assert T.card_tier(computed) == T.OURS
    assert T.card_tier(ai) == T.AI_UNREVIEWED           # AI rendering unreviewed despite DOI
    assert T.card_tier(spec) == T.UNSOURCED

    assert T.is_established(referee) and not T.is_established(preprint)
    assert not T.is_established(ai) and not T.is_established(computed)


def test_gate_refuses_preprint_support_under_established_claim():
    g = gate()
    # A refereed card and an external preprint both enter the vault fine.
    ref = g.submit(Card(title="Refereed osnova", type="theorem", status=CITED,
                        sources=["doi:10.1112/plms/x"]), actor="user")
    pre = g.submit(Card(title="Preprint tvrdnja", type="conjecture", status=CITED,
                        sources=["arxiv:2610.12234"]), actor="user")
    assert ref.ok and pre.ok
    ref_id = ref.path.stem
    pre_id = pre.path.stem

    # An established claim resting on the preprint is refused...
    bad = g.submit(Card(title="Utvrđeno na preprintu", type="theorem", status=CITED,
                        sources=["doi:10.1112/plms/y"], depends_on=[pre_id]),
                   actor="user")
    assert not bad.ok and "oslonac utvrđene" in bad.reason

    # ...but resting on the refereed card is accepted.
    good = g.submit(Card(title="Utvrđeno na recenziranom", type="theorem", status=CITED,
                         sources=["doi:10.1112/plms/z"], depends_on=[ref_id]),
                    actor="user")
    assert good.ok


def test_preprint_card_carries_a_warning():
    g = gate()
    v = g.submit(Card(title="Samo preprint", type="note", status=CITED,
                      sources=["arxiv:2610.15291"]), actor="user")
    assert v.ok
    assert any("PREPRINT" in w or "utvrđena" in w for w in v.warnings), v.warnings


def test_views_expose_the_tier(operator):
    from pse_r.shared_lib import views as V
    g = gate()
    g.submit(Card(title="Za pogled nivoa", type="theorem", status=CITED,
                  sources=["doi:10.1112/abc"]), actor="user")
    r = V.query("SELECT tier FROM cards WHERE title='Za pogled nivoa'")
    assert r["rows"] and r["rows"][0][0] == T.REFEREED
