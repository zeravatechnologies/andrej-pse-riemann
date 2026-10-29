"""Faza 6d R3 (plan 33e, rule 33): SHARED_LIB talks like a colleague; facts only
from the rows; the SQL stays one click away."""
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import voice as VO


def test_canned_answer_is_sentences_not_rows(operator):
    MIS.seed_first()
    a = VO.ask("koje misije imam?")
    assert a.answer.startswith("Imaš ") and "stanje:" in a.answer
    assert "(mission:" in a.answer                  # rule 47: the name is the link to the row
    assert "=" not in a.answer.split("(mission:")[0]   # no "col=value" dump
    assert a.sql.lower().startswith("select")


def test_unknown_is_said_plainly(operator):
    a = VO.ask("šta čeka skeptik?")
    if not a.rows:
        assert "nema u biblioteci" in a.answer.lower()


def test_numbers_only_from_rows(operator):
    res = {"columns": ["id", "state", "best_B"], "rows": [["m1", "s", 0.874957019420]]}
    txt = VO.human("misije", res, ["[card:m1]"])
    assert "0.87495701942" in txt
