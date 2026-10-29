"""F8 — method explorer + the open door (reproduction test above every model)."""
import sympy as sp

import pytest

from pse_r import config
from pse_r.methods import core as C
from pse_r.methods import pack as PK
from pse_r.methods import door as DOOR
from pse_r.methods import registry as REG
from pse_r.shared_lib.store import store


# ---- the exponent math reproduces the published numbers -------------------- #
def test_optima_reproduce_liu_and_xu_sang():
    assert abs(C.optimum(C.E_liu, 1e-6).B - 0.874957019420) < 1e-9
    assert abs(C.optimum(C.E_xs, 1 / 8).B - 0.874886647040) < 1e-9


def test_exact_polynomials_are_the_known_cubic_and_quartic():
    B = sp.symbols("B")
    pl, rootl = C.exact_polynomial("liu")
    assert pl.degree() == 3 and abs(rootl - 0.874957019420) < 1e-12
    px, rootx = C.exact_polynomial("xs")
    target = 133488 * B**4 - 376596 * B**3 + 384534 * B**2 - 167541 * B + 26231
    assert px.degree() == 4 and abs(rootx - 0.874886647040) < 1e-12
    assert sp.simplify(sp.Poly(px, B).monic().as_expr()
                       - sp.Poly(target, B).monic().as_expr()) == 0


def test_transform_is_exact_and_walls_bottom_at_5_6():
    assert C.transform_residual(0.0869, 0.1671, 0.75, n=400) < 1e-12
    # geometry ladder, computed directly (fast numpy), bottoms out at ≈ 5/6
    from pse_r.lab.experiments import _run_qrh_walls
    res = _run_qrh_walls(1201, 801)
    assert abs(res.numbers["najniže B (strukturni zid)"] - 5 / 6) < 1e-3


# ---- the method pack and its reproduction test ----------------------------- #
def _pack(name, family, source, claimed, dlo=1 / 8, tol=1e-7):
    return PK.MethodPack.from_dict({"name": name, "family": family,
                                    "source": source, "claimed_B": claimed,
                                    "dlo": dlo, "tol": tol})


def test_pack_reproduction_accepts_real_and_rejects_bogus():
    good = PK.reproduce(_pack("liu", "liu", "arxiv:2610.12234",
                              0.874957019420, dlo=1e-6))
    assert good["ok"] and good["error"] < 1e-7
    bogus = PK.reproduce(_pack("bogus", "liu", "arxiv:9999.99999", 0.5, dlo=1e-6))
    assert not bogus["ok"] and bogus["error"] > 0.3


def test_malformed_pack_is_an_error():
    with pytest.raises(PK.PackError):
        PK.MethodPack.from_dict({"name": "x"})               # missing fields
    with pytest.raises(PK.PackError):
        PK.MethodPack.from_dict({"name": "x", "family": "nope",
                                 "source": "arxiv:1", "claimed_B": 0.9})


# ---- the door: reproduce first, human queue only then ---------------------- #
def test_door_refuses_a_pack_that_does_not_reproduce(operator):
    DOOR.install_hooks()
    before = len(store().open_items(DOOR.METHOD_KIND))
    out = DOOR.import_pack(_pack("fake", "liu", "arxiv:9999.99999", 0.5, dlo=1e-6),
                           proposer="model:test")
    assert out["reproduced"] is False and out["pid"] is None
    assert len(store().open_items(DOOR.METHOD_KIND)) == before   # never queued


def test_door_queues_a_reproduced_pack_then_approval_registers_it(operator):
    DOOR.install_hooks()
    name = "doortest"
    out = DOOR.import_pack(_pack(name, "liu", "arxiv:2610.12234",
                                 0.874957019420, dlo=1e-6), proposer="model:test")
    assert out["reproduced"] and out["pid"]
    assert any(i["id"] == out["pid"] for i in store().open_items(DOOR.METHOD_KIND))

    # the human approves → method registered + a method card written via the gate
    store().decide(out["pid"], True, "izgleda tačno")
    assert REG.by_name(name) is not None
    cards_dir = config.DIR_METHODS
    written = list(cards_dir.glob("*.md")) if cards_dir.exists() else []
    assert any("metoda" in p.read_text(encoding="utf-8").lower() for p in written)


def test_method_card_lands_at_preprint_tier(operator):
    from pse_r.shared_lib import views as V
    from pse_r.vault import tiers as T
    DOOR.install_hooks()
    out = DOOR.import_pack(_pack("tiertest", "liu", "arxiv:2610.12234",
                                 0.874957019420, dlo=1e-6), proposer="user")
    store().decide(out["pid"], True)
    r = V.query("SELECT tier FROM cards WHERE title LIKE 'Metoda tiertest%'")
    assert r["rows"] and r["rows"][0][0] == T.PREPRINT    # arXiv source → preprint
