"""Fix 2026-10-25: the door is open to genuinely NEW exponent systems (as data)."""
import copy
import json
from pathlib import Path

import pytest

from pse_r.methods import door as DOOR
from pse_r.methods.expr import ExprError, parse
from pse_r.methods.pack import MethodPack, PackError, reproduce
from pse_r.methods.system import ExponentSystem
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib.store import store

PACKS = Path(__file__).resolve().parents[2] / "research" / "qrh-2026-10" / "method-packs"


def _raw(name):
    return json.loads((PACKS / name).read_text(encoding="utf-8"))


def test_liu_and_xs_data_systems_agree_with_validated_code():
    for f, B in (("liu.json", 0.874957019420), ("xu-sang.json", 0.874886647040)):
        r = reproduce(MethodPack.from_dict(_raw(f)), check_poly=True)
        assert r["ok"], r["reading"]
        assert r["family_agrees"] is True
        assert r["poly_ok"] is True
        assert abs(r["computed_B"] - B) < 1e-10


def test_xs_claims_the_published_number_not_ours():
    d = _raw("xu-sang.json")
    assert d["claimed_B"] == 0.8748867          # B1 = 8748867/10^7, as published


def test_wrong_polynomial_is_refused():
    d = _raw("liu.json")
    d["exact_poly"] = "133488*B**4 - 376596*B**3 + 384534*B**2 - 167541*B + 26231"
    r = reproduce(MethodPack.from_dict(d), check_poly=True)
    assert not r["ok"] and r["poly_ok"] is False


def test_data_system_that_disagrees_with_its_family_is_refused():
    d = _raw("liu.json")
    d["system"]["branches"][0]["E"] = d["system"]["branches"][0]["E"].replace("5*ell/4", "5*ell/4 + 0.001")
    d["claimed_B"] = MethodPack.from_dict({k: v for k, v in d.items() if k != "family"}) \
        .spec().optimum().B
    r = reproduce(MethodPack.from_dict(d))
    assert not r["ok"] and r["family_agrees"] is False


def test_a_genuinely_new_system_enters_through_the_door_as_data(operator):
    # A hypothetical paper: Xu–Sang's idea with a cheaper amplified moment
    # (only 20% of the row-counting benefit given up). No family, no new code.
    DOOR.install_hooks()
    mid = MIS.create("test-novi-sistem", "Test: novi sistem kroz vrata",
                     "Ulazi li sistem koji nije ugrađen?", "otvoreno", best_B=0.874886647040)
    d = _raw("xu-sang.json")
    d.pop("family"), d.pop("exact_poly")
    d["name"], d["source"] = "hipoteticki-w02", "arxiv:2699.00001"
    for br in d["system"]["branches"]:
        br["E"] = br["E"].replace("(3/4)*h*(1 - R)", "(4/5)*h*(1 - R)")
    sysm = ExponentSystem.from_dict(d["system"])
    B = sysm.optimum().B
    # w = 0.2; the coarse research sweep gave 0.87155365 (2 iterations, coarse b);
    # the converged value at the validated critical x = 1/2 is 0.8715502525.
    assert abs(B - 0.8715502525) < 1e-8
    d["claimed_B"] = round(B, 10)
    out = DOOR.import_pack(d, proposer="model:claude", mission_id=mid)
    assert out["reproduced"] and out["pid"]
    store().decide(out["pid"], True, "novi sistem, reprodukovan")
    m = MIS.get(mid)
    assert "hipoteticki-w02" in m["steps"][-1]["action"]
    assert m["steps"][-1]["outcome"].startswith("bliže")
    assert abs(m["best_B"] - B) < 1e-9


@pytest.mark.parametrize("evil", [
    "__import__('os').system('id')",
    "().__class__",
    "b.real",
    "(lambda: 1)()",
    "x[0]",
    "open('/etc/passwd')",
    "'text'",
    "b if x else ell",
    "b ** ell",                  # non-numeric exponent
    "eval('1')",
])
def test_expressions_can_only_be_arithmetic(evil):
    with pytest.raises(ExprError):
        parse(evil, {"b", "ell", "kappa", "delta", "x", "B"})


def test_evil_system_is_refused_as_a_pack():
    d = _raw("liu.json")
    d["system"]["defs"] = d["system"]["defs"] + [["h2", "__import__('os')"]]
    with pytest.raises(PackError):
        MethodPack.from_dict(d)
