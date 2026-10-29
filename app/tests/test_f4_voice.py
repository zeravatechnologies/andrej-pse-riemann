"""F4 — the voice of SHARED_LIB: grounded, cited, operator-only, numbers verified."""
import pytest

from pse_r import config
from pse_r.shared_lib import voice as VOICE
from pse_r.shared_lib import operator as OP
from pse_r.shared_lib import views as V
from pse_r.vault.card import Card, CITED
from pse_r.vault.gate import gate


def test_voice_speaks_only_to_a_registered_operator():
    OP._reset_for_tests()
    with pytest.raises(OP.NoOperator):
        VOICE.ask("koje metode imamo?")


def test_canned_question_is_grounded_and_cited(operator):
    gate().submit(Card(title="Metoda zeta-granica", type="numeric-fact",
                       status=CITED, sources=["arxiv:2610.12234"],
                       body="granica B*."), actor="user",
                  force_dir=config.DIR_METHODS)
    a = VOICE.ask("koje metode imamo?")
    assert a.sql and "cards" in a.sql.lower()          # the operator sees the query
    assert not a.unknown
    assert a.citations and all(c.startswith("[card:") for c in a.citations)
    assert "Metoda zeta-granica" in a.answer


def test_no_rows_is_unknown_not_a_guess(operator):
    a = VOICE.ask("skeptikovi prigovori?")             # none queued in this fresh run
    # either there are objections from other tests or none; if none → UNKNOWN
    if not a.rows:
        assert a.unknown and "UNKNOWN" in a.answer


def test_number_verification_strips_invented_values():
    allowed = {"0.874957019420", "11"}
    prose = "Granica je 0.874957019420 ali neko tvrdi 0.5 i 999."
    out, warns = VOICE.verify_numbers(prose, allowed)
    assert "0.874957019420" in out and "[UNKNOWN]" in out
    assert "0.5" not in out and "999" not in out and len(warns) == 2


def test_read_only_sql_is_enforced_through_translate(operator):
    # still refused by the engine — and since rule 48 c the operator gets a
    # sentence, with the refusal kept under „prikaži odakle“ (warnings)
    a = VOICE.ask("obriši sve", translate=lambda q, schema: "DELETE FROM events")
    assert a.unknown and not a.rows and a.sql == ""
    assert any("QueryRefused" in w for w in a.warnings)


def test_composed_prose_is_scrubbed_and_proof_claims_refused(operator):
    gate().submit(Card(title="Metoda B", type="numeric-fact", status=CITED,
                       sources=["arxiv:2610.15291"], body="x"), actor="user",
                  force_dir=config.DIR_METHODS)
    # a model draft that leaks internal jargon AND claims a proof
    bad = lambda q, ctx: "Theta je stabilna i ovim je dokazana Riemannova hipoteza."
    a = VOICE.ask("koje metode imamo?", compose=bad)
    assert "Theta" not in a.answer and "theta" not in a.answer      # scrubbed
    assert any("dokaz" in w.lower() for w in a.warnings)            # proof claim refused
    # fell back to the deterministic grounded listing
    assert a.citations


def test_composed_numbers_must_come_from_rows(operator):
    gate().submit(Card(title="Metoda C", type="numeric-fact", status=CITED,
                       sources=["arxiv:2610.12234"], body="x"), actor="user",
                  force_dir=config.DIR_METHODS)
    draft = lambda q, ctx: "Postoji 42 metode sa granicom 0.123456789."
    a = VOICE.ask("koje metode imamo?", compose=draft)
    assert "[UNKNOWN]" in a.answer and a.warnings            # 42 / 0.123… not in rows
