"""Round 3, item 31: the adversarial mode — numbers attack a claim: a better B under
the method's own conditions, what must be broken for a better one, and a strict
interval certificate that nothing admissible lies above B*."""
import pytest

from pse_r.methods import adversary as A
from pse_r.methods import core as C
from pse_r.methods import registry as R


def test_liu_claim_withstands_and_better_needs_breaking():
    rep = A.search("liu", nb=31, nk=13)
    assert not rep.better_than_claim
    assert abs(rep.best_B - 0.874957019420) < 1e-9
    assert rep.breaks and all(br["krši"] for br in rep.breaks)
    assert all(br["B"] < rep.claimed_B for br in rep.breaks)


@pytest.fixture
def clean_registry():
    known, by = list(R.KNOWN), dict(R._BY_NAME)
    yield
    R.KNOWN[:] = known
    R._BY_NAME.clear()
    R._BY_NAME.update(by)


def test_a_claim_that_is_not_the_optimum_is_caught(clean_registry):
    R.register(R.MethodSpec("lazna-liu", "liu", "test:lazna", claimed_B=0.8755))
    rep = A.search("lazna-liu", nb=31, nk=9)
    assert rep.better_than_claim and rep.best_B < 0.8755
    assert "NIJE OPTIMUM" in rep.summary()


def test_emptiness_certificate_is_strict_and_honest():
    l_star = C.optimum(C.E_liu, 1 / 8).l
    c = A.certify_empty("liu", l_star, eps=1e-5)
    assert c["complete"] and c["undecided"] == 0 and c["cells"] > 0
    assert c["B_low"] == pytest.approx(11 / 12 - 0.2 / 4) and c["B_high"] < 0.874957019420
    tight = A.certify_empty("liu", l_star, eps=1e-8, max_cells=300)
    assert not tight["complete"] and tight["undecided"] > 0      # says PARTIAL, never pretends


def test_system_pack_is_refused_with_the_reason(clean_registry):
    spec = R.MethodSpec("sistem-x", "liu", "test:s", claimed_B=0.87, system={"defs": {}, "E": ["0"]})
    R.KNOWN.append(spec)
    R._BY_NAME[spec.name] = spec
    with pytest.raises(ValueError, match="podatak"):
        A.family("sistem-x")
    with pytest.raises(ValueError, match="funkciju eksponenta"):
        A.family("line")


def test_attack_goes_to_queue_lab_and_grafovi(operator):
    from pse_r.shared_lib import missions as MIS
    from pse_r.shared_lib.store import store
    MIS.seed_first()
    A.install_hooks()
    out = A.attack("liu", eps=1e-5)
    from pse_r.lab import runner as LR
    rec = LR.load_run(out["run_id"])
    assert rec and rec["plots"] and rec["numbers"]["certifikat kompletan"]
    item = store().get(out["pid"])
    assert item["kind"] == A.KIND and not item["payload"]["better"]
    pts = store().kv_get(A.POINTS_KEY)
    assert any(p["method"] == "liu" for p in pts)
    n0 = len(MIS.get(MIS.FIRST_ID)["steps"])
    store().decide(out["pid"], True)
    steps = MIS.get(MIS.FIRST_ID)["steps"]
    assert len(steps) == n0 + 1 and "adversarijalni" in steps[-1]["action"]
