"""Live test rc2: after Ctrl+K (and „zaboravi ključeve“) and reopening online AI
the app stayed "bez AI" although the keys and models worked. Reopen now brings
back the main and the skeptic chosen before, when their keys are there."""
import pytest

from pse_r import settings as S
from pse_r.guardian import killswitch as KS
from pse_r.guardian import secrets as SEC
from pse_r.llm import selection as SEL

KEYS = {"GEMINI_API_KEY": "g" * 24, "OPENROUTER_API_KEY": "o" * 24}


@pytest.fixture(autouse=True)
def _reset(operator):
    KS._reset_for_tests()
    for k, v in KEYS.items():
        SEC.store().set(k, v)
    S.set_(SEL.MAIN_KEY, "gemini")
    S.set_(SEL.SKEPTIC_KEY, "openrouter")
    S.set_(SEL.PREV_MAIN_KEY, "")
    S.set_(SEL.PREV_SKEPTIC_KEY, "")
    yield
    if KS.closed():
        KS.reopen("Test Operater")
    for k in KEYS:
        SEC.store().set(k, "")
    KS._reset_for_tests()


def test_reopen_brings_back_main_and_skeptic():
    KS.close("test", actor="Test Operater")
    assert SEL.get_main() is None
    back = KS.reopen("Test Operater")
    assert back["main"] == "gemini" and SEL.get_main() == "gemini"
    assert SEL.get_skeptic() == "openrouter"


def test_second_close_keeps_the_remembered_main():
    KS.close("ctrl+k", actor="Test Operater")
    KS.close("zaboravi", actor="Test Operater")            # second close, no forgetting
    assert S.get(SEL.PREV_MAIN_KEY) == "gemini"
    assert KS.reopen("Test Operater")["main"] == "gemini"


def test_forgotten_keys_say_so_and_setup_restores():
    KS.close("ctrl+k", actor="Test Operater")
    KS.close("zaboravi", actor="Test Operater", forget_keys=True)
    back = KS.reopen("Test Operater")
    assert back["main"] is None and set(back["missing"]) == {"gemini", "openrouter"}
    assert SEL.get_main() is None                          # no key: honestly "bez AI"
    for k, v in KEYS.items():                              # operator types them again
        SEC.store().set(k, v)
    S.set_(SEL.MAIN_KEY, "gemini")                         # Podešavanje → apply
    S.set_(SEL.SKEPTIC_KEY, "openrouter")
    assert SEL.get_main() == "gemini" and SEL.get_skeptic() == "openrouter"


def test_operator_choice_made_while_closed_wins():
    KS.close("ctrl+k", actor="Test Operater")
    S.set_(SEL.MAIN_KEY, "openrouter")                     # chose another meanwhile
    S.set_(SEL.SKEPTIC_KEY, "")
    assert KS.reopen("Test Operater")["main"] == "openrouter"
    assert SEL.get_main() == "openrouter"
