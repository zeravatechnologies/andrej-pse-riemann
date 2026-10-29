"""Rule 47 and 48 c (round 3, R10): mission names are `mission:` links; a
question that asks for judgment is sent to the mission agent; a bad SQL gets
one retry with the error, then a human sentence — never the raw error."""
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import voice as VO


def test_judgment_detected():
    for q in ("Koji je najlakši sljedeći korak?", "šta da radim sa misijom 2",
              "What should I do next?", "šta mi preporučuješ"):
        assert VO.needs_judgment(q), q
    for q in ("koje misije imam", "šta čeka moju odluku", "zadnja lab računanja"):
        assert not VO.needs_judgment(q), q


def test_judgment_answer_links_mission_talk(operator):
    mid = MIS.new_mission("Probna misija za sud", "Šta tačno?")
    calls = []
    a = VO.ask("Koji je najlakši sljedeći korak?", translate=lambda q, s: calls.append(q) or "x")
    assert not calls                                # no SQL for a judgment question
    assert "ne odgovara" in a.answer and f"(mission:{mid})" in a.answer
    assert "Razgovaraj o misiji:" in a.answer


def test_mission_rows_are_links(operator):
    mid = MIS.seed_first()
    a = VO.ask("koje misije imam?")
    assert f"(mission:{mid})" in a.answer and "[card:misija" not in a.answer


def test_model_card_cites_become_links(operator):
    mid = MIS.seed_first()
    title = MIS.get(mid)["title"]
    out = VO.link_missions(f"Misija je otvorena [card:{mid}] i ima [card:drugo].")
    assert f"(mission:{mid})" in out and title.split()[0] in out and "[card:drugo]" in out


def test_bad_sql_retried_with_error(operator):
    MIS.seed_first()
    seen = []

    def translate(q, schema, error="", bad_sql=""):
        seen.append((error, bad_sql))
        return "SELEC nonsense" if not error else "SELECT id, title FROM missions"
    a = VO.ask("koliko misija postoji", translate=translate)
    assert len(seen) == 2 and seen[1][0] and seen[1][1] == "SELEC nonsense"
    assert a.rows and not a.unknown


def test_bad_sql_twice_is_a_human_sentence(operator):
    def translate(q, schema, error="", bad_sql=""):
        return "DROP TABLE missions"
    a = VO.ask("koliko misija postoji", translate=translate)
    assert a.unknown and "Nisam uspio" in a.answer
    assert "Refused" not in a.answer and "DROP" not in a.answer
    assert any(w.startswith("SQL:") for w in a.warnings)


def test_old_translate_without_error_hook_still_retries(operator):
    n = []

    def translate(q, schema):
        n.append(1)
        return "nije sql"
    a = VO.ask("koliko misija postoji", translate=translate)
    assert len(n) == 2 and a.unknown


def test_chat_keeps_raw_error_out_of_answer():
    from pse_r.gui import chat as C
    assert not C._human_warning("SQL: QueryRefused: samo SELECT")
    assert not C._human_warning("QueryRefused: x")
    assert C._human_warning("broj 3.5 nije u redovima — uklonjen")


def test_mission_link_click_routes(qtbot=None):
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from pse_r.gui.widgets import MarkdownView
    got = []
    mv = MarkdownView(on_card=got.append)
    mv._clicked(QUrl("mission:misija-x-1"))
    mv._clicked(QUrl("card:abc"))
    assert got == ["mission:misija-x-1", "abc"]
