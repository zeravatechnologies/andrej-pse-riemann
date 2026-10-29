"""Faza 6d R4b (plan 33b, agreement rule 35): translation only on request."""
import pytest

from pse_r.shared_lib import translator as TR
from pse_r.shared_lib.store import store


def fake(prefix="EN: "):
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return prefix + prompt.split("<tekst>\n", 1)[1].split("\n</tekst>")[0]
    ask.calls = calls
    return ask


def test_translate_caches_and_never_changes_original(tmp_path):
    src = tmp_path / "biljeska.md"
    src.write_text("Zid je kod ℓ ≈ 0,1668 [card:x].", encoding="utf-8")
    ask = fake()
    out = TR.translate(src.read_text(encoding="utf-8"), "en", source_path=str(src), ask=ask)
    assert out["text"].startswith("EN: ") and not out["cached"]
    assert src.read_text(encoding="utf-8") == "Zid je kod ℓ ≈ 0,1668 [card:x]."
    f = tmp_path / "biljeska.en-masinski.md"
    assert f.exists() and "mašinski prevod" in f.read_text(encoding="utf-8")
    again = TR.translate(src.read_text(encoding="utf-8"), "en", source_path=str(src), ask=ask)
    assert again["cached"] and len(ask.calls) == 1               # no second model call


def test_changed_original_keeps_old_translation_with_date(tmp_path):
    src = tmp_path / "n.md"
    src.write_text("prvo", encoding="utf-8")
    TR.translate("prvo", "en", source_path=str(src), ask=fake())
    src.write_text("drugo", encoding="utf-8")
    TR.translate("drugo", "en", source_path=str(src), ask=fake())
    names = sorted(p.name for p in tmp_path.iterdir())
    assert "n.en-masinski.md" in names
    assert any(n.startswith("n.en-masinski.") and n != "n.en-masinski.md" for n in names)


def test_machine_files_are_not_cards(tmp_path):
    from pse_r import config
    from pse_r.vault import store as VS
    d = config.VAULT / "notes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.en-masinski.md").write_text("---\nid: x.en-masinski\ntitle: t\n---\n", encoding="utf-8")
    assert all("-masinski" not in p.stem for p in VS.iter_paths())


def test_licensed_only_local_gguf(monkeypatch):
    from pse_r.llm import selection as SEL
    monkeypatch.setattr(SEL, "get_main", lambda: "claude")
    with pytest.raises(TR.TranslationRefused):
        TR.translate("licencirani tekst", "en", licensed=True)


def test_without_ai_it_says_so(monkeypatch):
    from pse_r.llm import selection as SEL
    monkeypatch.setattr(SEL, "get_main", lambda: None)
    with pytest.raises(TR.TranslationRefused):
        TR.translate("nešto novo za prevod 123", "en")


def test_estimate_flags_long_text():
    assert TR.estimate("a" * 20000)["long"] and not TR.estimate("kratko")["long"]


def test_translator_is_a_unit_and_its_moves_are_measured():
    from pse_r.shared_lib import pse_registry as PR
    PR.reset_for_tests()
    TR.translate("jedinica prevodioca radi", "en", ask=fake())
    u = PR.pse().unit("translator")
    n = store().rows("SELECT COUNT(*) n FROM pse_moves WHERE unit_id=?", (u.unit_id,))[0]["n"]
    assert n >= 1 and u.uses_model


def test_viewer_menu_translates_and_shows_original():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.widgets import MarkdownView
    v = MarkdownView()
    v.set_markdown("Dobar dan, ovo je **test** preglednika.")
    acts = [a.text() for a in v._tr_menu().actions()]
    assert len(acts) == 3
    v.translate_to("en", ask=fake("EN: "), confirm=False)
    app.processEvents()
    assert "EN: " in v._md and v._orig is not None
    v.show_original()
    assert v._md.startswith("Dobar dan") and v._orig is None
