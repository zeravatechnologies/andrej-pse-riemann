"""Review fix 8: SHARED_LIB actually runs — keepers, healing, arXiv → extraction → door."""
import json
import os
from pathlib import Path

from pse_r import config
from pse_r.methods import door as DOOR
from pse_r.methods import extract as EXT
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import reports as RP
from pse_r.shared_lib import runtime as RT
from pse_r.shared_lib.store import store

PACKS = Path(__file__).resolve().parents[2] / "research" / "qrh-2026-10" / "method-packs"


def test_new_report_is_sealed_and_tampering_is_restored(operator):
    p = RT.write_final_report("izvjestaj-test", "# Izvještaj\n\nB* = 0.874957019420 [liu]\n")
    assert RP.verify(p)["sealed"] and RP.verify(p)["ok"]
    # a foreign writer changes it behind the gate's back
    os.chmod(p, 0o644)
    p.write_text("# lažno\n", encoding="utf-8")
    out = RT.keepers_round()
    assert str(p.resolve()) in out["tampered"]
    assert "0.874957019420" in p.read_text(encoding="utf-8")       # restored from seal
    assert out["keepers"] >= 1


def test_unsealed_file_dropped_in_reports_gets_sealed(operator):
    config.DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    f = config.DIR_REPORTS / "ubacen.md"
    f.write_text("x\n", encoding="utf-8")
    out = RT.keepers_round()
    assert "ubacen.md" in out["sealed_now"]


def test_harmful_chat_output_freezes_until_operator_decides(operator):
    """Faza 6d: the chat unit's harmful output → Doctor's measure → operator."""
    from pse_r.pse import path as PATH
    from pse_r.shared_lib import pse_registry as PR
    PR.reset_for_tests()
    RT.install_hooks()
    text = "Dokazao sam Riemannovu hipotezu."
    r = PATH.words("chat", text, harms=PATH.screen(text))
    assert r.finding and r.finding["bad"]
    assert not PATH.may_irreversible("chat")
    pend = [i for i in store().open_items(PR.QUEUE_MEASURE) if i["payload"]["agent"] == "chat"]
    assert pend
    store().decide(pend[-1]["id"], False, "pregledano")
    assert PATH.may_irreversible("chat")


def test_clean_output_is_not_a_harm(operator):
    from pse_r.pse import path as PATH
    assert PATH.screen("Granica iz rada je izvedena u lab-u [run-1].") == []


def test_arxiv_round_queues_new_papers_once(operator):
    from pse_r.shared_lib import missions as MIS
    MIS.seed_first()                     # the QRH feed belongs to the first mission (rule 38)
    class It:
        def __init__(self, ref, title):
            self.source_ref, self.title, self.abstract = ref, title, ""
    items = [It("arxiv:2699.11111", "Further quasi-Riemann"), It("arxiv:2699.22222", "Another")]
    r1 = RT.arxiv_round(force=True, fetch=lambda: items)
    r2 = RT.arxiv_round(force=True, fetch=lambda: items)
    assert set(r1["new"]) == {"arxiv:2699.11111", "arxiv:2699.22222"} and r2["new"] == []
    titles = [i["title"] for i in store().open_items(RT.ARXIV_KIND)]
    assert any("Further quasi-Riemann" in t for t in titles)


def test_extraction_by_main_ai_goes_through_the_door(operator):
    DOOR.install_hooks()
    mid = MIS.seed_first()
    raw = json.loads((PACKS / "xu-sang.json").read_text(encoding="utf-8"))
    raw.pop("family")
    reply = "Evo paketa:\n```json\n" + json.dumps(raw) + "\n```"
    out = EXT.extract_and_propose("arxiv:2610.15291", "Amplified moments",
                                  paper_text="(tekst rada)", ask=lambda prompt: reply)
    assert out["reproduced"] and out["pid"]
    assert abs(out["result"]["computed_B"] - 0.874886647040) < 1e-9


def test_extraction_with_wrong_number_never_reaches_the_queue(operator):
    DOOR.install_hooks()
    raw = json.loads((PACKS / "liu.json").read_text(encoding="utf-8"))
    raw.pop("family"); raw.pop("exact_poly")
    raw["claimed_B"] = 0.8                     # the model "made up" a better number
    before = len(store().open_items(DOOR.METHOD_KIND))
    out = EXT.extract_and_propose("arxiv:2699.33333", "", paper_text="x",
                                  ask=lambda p: "```json\n" + json.dumps(raw) + "\n```")
    assert out["reproduced"] is False
    assert len(store().open_items(DOOR.METHOD_KIND)) == before


def test_extraction_prompt_carries_paper_and_rules():
    seen = {}
    raw = json.loads((PACKS / "liu.json").read_text(encoding="utf-8"))

    def ask(prompt):
        seen["p"] = prompt
        return "```json\n" + json.dumps(raw) + "\n```"
    EXT.extract_pack("arxiv:2610.12234", "Liu", paper_text="PAPER-BODY-MARKER", ask=ask)
    assert "PAPER-BODY-MARKER" in seen["p"] and "claimed_B" in seen["p"]


def test_public_edition_has_no_qrh_feed(monkeypatch):
    from pse_r.shared_lib import missions as MIS
    monkeypatch.setattr(MIS, "get", lambda mid: None)
    r = RT.arxiv_round(force=True, fetch=lambda: [])
    assert r.get("skipped") and r.get("no_mission")


def test_new_mission_by_operator(operator):
    from pse_r.shared_lib import missions as MIS
    mid = MIS.new_mission("Moja misija ć", "Šta tačno?")
    assert mid.startswith("misija-moja-misija") and MIS.get(mid)["state"] == "otvorena"
