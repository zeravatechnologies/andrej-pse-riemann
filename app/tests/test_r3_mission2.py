"""Round 3, items 26–27: mission 2, goal menu (operator only, app only proposes),
result kind / degree / assumptions in method packs."""
import pytest

from pse_r.methods import pack as PK
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib.store import store


def test_mission2_seeded_with_transfer_map(operator):
    MIS.seed_second()
    m = MIS.get(MIS.SECOND_ID)
    assert m and int(m["goal"]) == 1
    assert len(m["steps"]) == len(MIS.TRANSFER_MAP)
    assert any("kubna theta" in s["action"] for s in m["steps"])


def test_goal_only_by_operator_and_proposals(operator):
    MIS.seed_second()
    MIS.install_hooks()
    pid = MIS.propose_goal(MIS.SECOND_ID, 2, "korak 3 se prenosi uz poznat gubitak")
    assert int(MIS.get(MIS.SECOND_ID)["goal"]) == 1          # a proposal changes nothing
    store().decide(pid, True)
    assert int(MIS.get(MIS.SECOND_ID)["goal"]) == 2
    MIS.set_goal(MIS.SECOND_ID, 1, "vraćam")
    with pytest.raises(ValueError):
        MIS.set_goal(MIS.SECOND_ID, 4)
    from pse_r.shared_lib import operator as OP
    OP._reset_for_tests()
    with pytest.raises(Exception):
        MIS.set_goal(MIS.SECOND_ID, 3)                       # nobody registered


def test_pack_kind_and_assumptions():
    base = {"name": "t", "source": "arxiv:2610.12234", "claimed_B": 0.9, "family": "line",
            "ell": 0.1}
    p = PK.MethodPack.from_dict({**base, "result_kind": "poluravan", "degree": 2,
                                 "assumptions": ["funkcionalnost do GL(3)"], "conditional": True})
    assert p.degree == 2 and p.conditional and p.to_dict()["assumptions"]
    with pytest.raises(PK.PackError, match="uslovan"):
        PK.MethodPack.from_dict({**base, "assumptions": ["RH"]})
    with pytest.raises(PK.PackError, match="vrsta rezultata"):
        PK.MethodPack.from_dict({**base, "result_kind": "nesto"})
