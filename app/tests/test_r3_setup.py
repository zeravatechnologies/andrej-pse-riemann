"""Round 3, item 8: first-run setup (logic) and the setup window (smoke)."""
import pytest

from pse_r import settings as S
from pse_r import setup_flow as SF
from pse_r.guardian import policy
from pse_r.guardian import secrets as SEC
from pse_r.llm import selection as SEL
from pse_r.shared_lib import declarations as DECL
from pse_r.shared_lib import operator as OP
from pse_r.shared_lib.store import store


def test_cloud_main_gguf_skeptic_declared(tmp_path, monkeypatch):
    from pse_r.llm import gguf as G
    monkeypatch.setattr(G, "have_llama", lambda: True)
    f = tmp_path / "x" / "skeptik.gguf"
    f.parent.mkdir()
    f.write_bytes(b"GGUF-test")
    out = SF.apply(SF.SetupChoices(
        operator="Andrej Ristić",
        main=SF.ModelChoice("cloud", provider="openai", key="sk-test-abcdefghijklmnop123",
                            model="gpt-5-mini"),
        skeptic=SF.ModelChoice("gguf", gguf_path=str(f)),
        guardian_autostart=True))
    assert OP.current() == "Andrej Ristić"
    assert out["main"] == "openai" and SEL.get_main() == "openai"
    assert out["skeptic"] == f"gguf:{f.resolve()}" and SEL.get_skeptic() == out["skeptic"]
    assert DECL.model_hash(str(f.resolve())) == SF.gguf_check(str(f))["sha256"]
    assert S.get("models")["openai"] == "gpt-5-mini"
    assert S.get(SF.AUTOSTART_KEY) is True and not SF.needed()
    assert SEC.store().get("OPENAI_API_KEY").startswith("sk-test")
    SEC.store().set("OPENAI_API_KEY", "")


def test_custom_address_declared_on_confirm():
    out = SF.apply(SF.SetupChoices(
        operator="Andrej Test",
        main=SF.ModelChoice("custom", custom_name="kucni", custom_url="https://ai.example.net/v1",
                            model="m", key="kljuc-za-kucni-server-1234")))
    assert out["main"] == "custom:kucni"
    assert policy.rule_for("ai.example.net").key_env == "CUSTOM_KUCNI_API_KEY"


def test_unconfirmed_custom_address_stays_closed():
    out = SF.apply(SF.SetupChoices(
        operator="Andrej Test", confirm_declarations=False,
        main=SF.ModelChoice("custom", custom_name="zatvoreno",
                            custom_url="https://closed.example.net/v1", model="m")))
    assert out["main"] is None                      # not reachable until confirmed
    assert any("čeka potvrdu" in n for n in out["notes"])
    assert policy.rule_for("closed.example.net") is None
    assert any("closed.example.net" in str(it["payload"]) for it in store().open_items())


def test_no_ai_for_now():
    out = SF.apply(SF.SetupChoices(operator="Andrej Test", main=SF.ModelChoice("none")))
    assert out["main"] is None and SEL.get_main() is None and not SEL.skeptic_available()
    assert "radi" in SF.NO_AI_TEXT and "ne radi" in SF.NO_AI_TEXT


def test_setup_window_builds_and_walks(qapp_offscreen=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.setup import SetupDialog, NONE
    d = SetupDialog()
    d.op.setText("Andrej Test")
    d._go(+1)
    assert d.stack.currentIndex() == 1
    for _ in range(2):                                   # every option renders, twice
        for i in range(d.main.lst.count()):              # (switching back must not crash)
            d.main.lst.setCurrentRow(i)
            d.main.key.text(); d.main.model.currentText(); d.main.g_path.text()
    for i in range(d.main.lst.count()):
        if d.main.lst.item(i).data(0x0100) == NONE:
            d.main.lst.setCurrentRow(i)
    d._go(+1)
    assert d.stack.currentIndex() == 3                   # skeptic skipped when no AI
    d._go(+1)
    assert d.b_done.isVisible() or d.stack.currentIndex() == 4
    d.close()
    import shiboken6
    shiboken6.delete(d)          # now, without running the event loop (other tests'
                                 # windows have pending timers that would start threads)
