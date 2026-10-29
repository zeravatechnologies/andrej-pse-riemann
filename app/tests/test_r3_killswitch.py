"""Round 3, item 12: the online-AI kill switch."""
import pytest

from pse_r import settings as S
from pse_r.guardian import egress as EG
from pse_r.guardian import killswitch as KS
from pse_r.guardian import secrets as SEC
from pse_r.llm import selection as SEL
from pse_r.shared_lib.store import store


@pytest.fixture(autouse=True)
def _reset(operator):
    KS._reset_for_tests()
    SEC.store().set("OPENAI_API_KEY", "sk-test-0123456789abcdefghij")
    S.set_(SEL.MAIN_KEY, "openai")
    yield
    if KS.closed():
        KS.reopen("Test Operater")
    SEC.store().set("OPENAI_API_KEY", "")
    KS._reset_for_tests()


def test_close_blocks_cloud_hangs_up_and_locks_keys(monkeypatch):
    hung = {"n": 0}
    monkeypatch.setattr(EG.egress(), "kill_streams", lambda: hung.__setitem__("n", 2) or 2)
    out = KS.close("test", actor="Test Operater")
    assert KS.closed() and out["hung_up"] == 2
    assert SEC.store().get("OPENAI_API_KEY") == ""                 # out of memory
    assert SEC.store().path.read_text().count("sk-test-0123456789") == 1   # still on disk
    with pytest.raises(EG.EgressBlocked, match="ISKLJUČEN"):
        EG.egress().request("POST", "https://api.openai.com/v1/chat/completions",
                            secret_name="OPENAI_API_KEY", auth_style="bearer")
    assert SEL.get_main() != "openai"                               # fell back
    # anonymous literature sources are NOT affected by the switch
    from pse_r.guardian import policy
    assert "llm" not in policy.rule_for("export.arxiv.org").tags


def test_survives_restart_and_only_operator_reopens():
    KS.close("test")
    SEC._STORE = None                                   # a fresh process…
    KS.on_startup()
    assert KS.closed() and SEC.store().get("OPENAI_API_KEY") == ""
    from pse_r.shared_lib import operator as OP
    OP._reset_for_tests()
    with pytest.raises(Exception):
        KS.reopen("")                                   # nobody registered
    OP.set_operator("Test Operater")
    KS.reopen("Test Operater")
    assert not KS.closed()
    assert SEC.store().get("OPENAI_API_KEY").startswith("sk-test")


def test_forget_keys_removes_them_from_disk():
    KS.close("test", forget_keys=True)
    assert "sk-test-0123456789" not in SEC.store().path.read_text()
    KS.reopen("Test Operater")
    assert SEC.store().get("OPENAI_API_KEY") == ""      # forgotten means forgotten


def test_auto_trip_on_runaway_calls():
    S.set_("killswitch_L", {"calls_per_10min": 5, "tokens_per_call": 10**9,
                            "usd_per_hour": 10**9})
    reason = None
    for i in range(10):
        reason = KS.observe_cloud_call("openai", 100, 0.0, now=1000.0 + i)
        if reason:
            break
    assert reason and "calls_per_10min" in reason and KS.closed()
    items = store().open_items(KS.CLOSED_KIND)
    assert items and items[0]["payload"]["revoke"]          # revoke links for the operator
    assert any("openai.com" in r["url"] for r in items[0]["payload"]["revoke"])
    S.set_("killswitch_L", {})


def test_one_huge_call_trips():
    S.set_("killswitch_L", {"tokens_per_call": 1000})
    assert KS.observe_cloud_call("openai", 50_000, 0.0)
    S.set_("killswitch_L", {})
