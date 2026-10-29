"""Round 3, item 5 (Svarog S4): every action declares reversibility;
undeclared = irreversible; only reversible actions run without the operator."""
import pytest

from pse_r.core import actions as A
from pse_r.guardian import harms as HRM
from pse_r.shared_lib.store import store


def test_undeclared_is_irreversible_and_refused():
    s = A.spec("nešto-što-niko-nije-deklarisao")
    assert not s.declared and not s.reversible and not s.auto and s.tier == 2
    with pytest.raises(A.NotAllowed):
        A.require_auto("nešto-što-niko-nije-deklarisao")


def test_reversible_needs_an_undo():
    with pytest.raises(ValueError):
        A.declare("r3-test-bez-undo", reversible=True)


def test_human_tier_is_derived_from_declarations():
    tier2 = {s.name for s in A.all_specs() if not s.auto}
    for name in ("fisija", "zamjena", "smrt", "ponovni-prijem-modela",
                 "vraćanje-fajlova-operatera"):
        assert name in tier2 and not A.may_auto(name)
    for name in ("contain", "boundary-reset", "vraćanje-fajlova-iz-pečata",
                 "označi-REFUTED/SUSPECT", "model.unload", "guard.pause"):
        assert A.may_auto(name) and A.spec(name).undo


def test_pse_fission_fusion_are_declared_reversible_with_undo():
    # Faza 6d, rule 14: SHARED_LIB executes them alone because they are reversible
    from pse_r.shared_lib import pse_registry as PR
    PR.reset_for_tests()
    PR.pse()
    for name in ("pse.fisija", "pse.fuzija", "pse.produzenje", "pse.zamrzavanje"):
        assert A.may_auto(name) and A.spec(name).undo


def test_restore_from_seal_keeps_the_tampered_copy(operator, tmp_path):
    from pse_r import config
    from pse_r.shared_lib import reports as RP
    config.DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    p = config.DIR_REPORTS / "r3-izvjestaj.md"
    p.write_text("original", encoding="utf-8")
    RP.seal(p)
    import os
    os.chmod(p, 0o644)
    p.write_text("izmijenjeno", encoding="utf-8")
    assert RP.restore(p)
    assert p.read_text(encoding="utf-8") == "original"
    kept = list((config.DIR_STATE / "forensic").glob("r3-izvjestaj.md.*.tampered"))
    assert kept and kept[0].read_text(encoding="utf-8") == "izmijenjeno"
