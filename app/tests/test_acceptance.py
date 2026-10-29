"""
ACCEPTANCE TEST (plan §0 — the definition of success).

Replays the real history through the real door and the real mission:

  1. Start: OpenAI 7/8 and 11/12 are known (seeded source cards; packs reproduce
     them as points on the line B=11/12−ℓ/4).
  2. Import Liu (arXiv 2610.12234) → proposal → reproduction test passes
     (0.874957019420, cubic) → operator confirms → frontier moves from 7/8, the
     mission updates ("bliže").
  3. Import Xu–Sang (arXiv 2610.15291) → polynomial of degree 4, 0.874886647040,
     T = E_XS − E_Liu exact → operator confirms → mission updates again.

If this passes, the thing the whole project is for works end to end: a new QRH
paper becomes a reproduced, operator-confirmed point that moves the mission.
"""
from pathlib import Path

from pse_r.methods import core as C
from pse_r.methods import door as DOOR
from pse_r.methods import arxiv as AX
from pse_r.methods.pack import MethodPack, reproduce
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib.store import store
from pse_r.vault import qrh_seed as QS
from pse_r.vault import tiers as T

PACKS = Path(__file__).resolve().parents[2] / "research" / "qrh-2026-10" / "method-packs"


def _pack(name):
    return MethodPack.from_file(PACKS / name)


def test_all_four_extracted_packs_reproduce():
    for f in ("liu.json", "xu-sang.json", "openai-11-12.json", "openai-7-8.json"):
        r = reproduce(_pack(f))
        assert r["ok"], (f, r["reading"])


def test_acceptance_replay_history(operator):
    DOOR.install_hooks()
    QS.seed_qrh()
    mid = MIS.seed_first()

    # 1. START — OpenAI 7/8 and 11/12 are known in the library.
    assert QS.gate().find("izvor-openai-7-8") is not None
    assert QS.gate().find("izvor-openai-11-12") is not None
    assert reproduce(_pack("openai-7-8.json"))["computed_B"] == 0.875

    # 2. IMPORT LIU → reproduce → operator confirms → mission moves.
    liu = _pack("liu.json")
    outL = DOOR.import_pack(liu, proposer="model:claude", mission_id=mid)
    assert outL["reproduced"] and abs(outL["result"]["computed_B"] - 0.874957019420) < 1e-9
    store().decide(outL["pid"], True, "reprodukovano, potvrđujem")
    mL = MIS.get(mid)
    assert abs(mL["best_B"] - 0.874957019420) < 1e-7
    assert mL["steps"][-1]["outcome"].startswith(("bliže", "prva"))
    # the method card is in the library at PREPRINT tier (arXiv)
    from pse_r.shared_lib import views as V
    r = V.query("SELECT tier FROM cards WHERE title LIKE 'Metoda liu%'")
    assert r["rows"] and r["rows"][0][0] == T.PREPRINT

    # 3. IMPORT XU–SANG → quartic, 0.874886647040 → operator confirms → moves again.
    xs = _pack("xu-sang.json")
    outX = DOOR.import_pack(xs, proposer="model:claude", mission_id=mid)
    assert outX["reproduced"] and abs(outX["result"]["computed_B"] - 0.874886647040) < 1e-9
    store().decide(outX["pid"], True, "kvartna se slaže, potvrđujem")
    mX = MIS.get(mid)
    assert abs(mX["best_B"] - 0.874886647040) < 1e-7
    assert mX["steps"][-1]["outcome"].startswith("bliže")      # lower than Liu → closer

    # T = E_XS − E_Liu is exact on the Xu–Sang optimum geometry.
    opt = C.optimum(C.E_xs, 1 / 8)
    assert C.transform_residual(opt.b, opt.l, opt.k, n=500) < 1e-12

    # The mission's history now has both points, in order.
    actions = [s["action"] for s in mX["steps"]]
    assert any("liu" in a for a in actions) and any("xu-sang" in a for a in actions)


def test_bogus_paper_is_refused_at_the_door(operator):
    # A paper that claims a number its recipe does not yield never reaches the queue.
    DOOR.install_hooks()
    mid = MIS.seed_first()
    before = len(store().open_items(DOOR.METHOD_KIND))
    out = AX.propose_from_recipe("arxiv:2699.99999", "liu", 0.5,
                                 proposer="model:claude", dlo=1e-6, mission_id=mid)
    assert out["reproduced"] is False and out["pid"] is None
    assert len(store().open_items(DOOR.METHOD_KIND)) == before
