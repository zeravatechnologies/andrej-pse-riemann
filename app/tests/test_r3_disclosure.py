"""Round 3, item 21 (Perun P7): disclosure budgets + competing hypotheses."""
import pytest

from pse_r.guardian import disclosure as D
from pse_r.guardian import harms as HRM


def test_private_and_secret_have_zero_budget():
    with pytest.raises(D.DisclosureExceeded):
        D.check_and_spend("api.example.org", "moj ruter je 192.168.1.1")
    with pytest.raises(D.DisclosureExceeded):
        D.check_and_spend("api.example.org", "ključ sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX")
    assert D.check_and_spend("api.example.org", "nula ζ na 14.1347") == \
        {"secret": 0, "private": 0, "licensed": 0}


def test_licensed_paper_text_has_a_small_budget(monkeypatch):
    words = " ".join(f"rijec{i}" for i in range(400))
    monkeypatch.setattr(D, "_licensed_shingles",
                        lambda: frozenset(" ".join(words.split()[i:i + D.SHINGLE])
                                          for i in range(0, 400 - D.SHINGLE + 1, 2)))
    short = " ".join(words.split()[:20])                 # a short quote fits
    assert D.check_and_spend("api.lic.org", short)["licensed"] > 0
    with pytest.raises(D.DisclosureExceeded):            # the whole paper does not
        D.check_and_spend("api.lic.org", words)


def test_cloud_call_refused_before_sending(monkeypatch):
    from pse_r.guardian import egress as EG
    from pse_r.llm import backend as B
    sent = {"n": 0}
    monkeypatch.setattr(EG.egress(), "stream_post",
                        lambda *a, **k: sent.__setitem__("n", 1) or iter(()))
    with pytest.raises(EG.EgressBlocked, match="budžet otkrivanja"):
        B.make("openai").chat([B.Msg("user", "pogledaj /home/andrej/tajno i 10.0.0.7")])
    assert sent["n"] == 0                                 # nothing left the machine


