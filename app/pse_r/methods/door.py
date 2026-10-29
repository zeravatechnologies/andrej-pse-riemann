"""
The "open door" (master §0.5.4): the ONLY way a method enters the system.

A method pack never takes effect by being proposed. It must first pass the
deterministic reproduction test (pack.reproduce), and only then is it placed in
the human queue ("Čeka tvoju odluku"). A pack that does not reproduce its paper's
number is refused at the door and never reaches the queue — no model can wave it
through, because the gate, not a model, runs the test.

On human approval the method is registered and a method card is written through
the vault gate into DIR_METHODS (a CITED card whose source is the paper, so it
lands at the correct source tier — PREPRINT for an arXiv method).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .. import config
from ..core import journal as J
from ..vault.card import Card, CITED
from ..vault.gate import gate
from ..shared_lib.store import store
from . import pack as PK
from . import registry as REG

METHOD_KIND = "method"             # human-queue kind and journal kind


def import_pack(source: Union[str, Path, dict, PK.MethodPack], proposer: str,
                mission_id: Optional[str] = None) -> dict:
    """
    Parse → reproduce → (only if reproduced) propose to the human queue.
    Returns {"reproduced", "pid"|None, "result"}. Raises PackError for a
    malformed pack (that is an error, not a verdict).
    """
    if isinstance(source, PK.MethodPack):
        pack = source
    elif isinstance(source, dict):
        pack = PK.MethodPack.from_dict(source)
    else:
        pack = PK.MethodPack.from_file(Path(source))

    res = PK.reproduce(pack, check_poly=True)
    from ..core import replay as RPL
    from ..core.replay_deciders import reproduce_out
    rec = RPL.record("door.reproduce", {"pack": pack.to_dict()}, reproduce_out(res))
    if not res["ok"]:
        J.log(METHOD_KIND, proposer,
              {"event": "refused_at_door", "name": pack.name,
               "claimed_B": pack.claimed_B, "computed_B": res["computed_B"],
               "error": res["error"], "replay": rec}, subject=pack.name, verdict="refused")
        return {"reproduced": False, "pid": None, "result": res}

    pid = store().propose(
        METHOD_KIND,
        f"Metoda „{pack.name}“ ({pack.source}) — reprodukovano B*={res['computed_B']:.12f}",
        {"pack": pack.to_dict(), "mission_id": mission_id,
         "result": {k: res[k] for k in
         ("computed_B", "claimed_B", "error", "poly_ok", "broken_walls")}},
        proposer)
    J.log(METHOD_KIND, proposer,
          {"event": "reproduced_queued", "name": pack.name, "pid": pid,
           "computed_B": res["computed_B"], "replay": rec},
          subject=pack.name, verdict="reproduced")

    # reproduction test → skeptic → operator (plan F9). The skeptic (a different
    # model) attacks the reproduced method; its objections queue alongside. If no
    # distinct skeptic is available, only the deterministic test stands — fine.
    skeptic = None
    try:
        from ..llm import skeptic as SK
        if SK.SEL.skeptic_available():
            claim = (f"Metoda {pack.name}: granica B*={res['computed_B']:.12f} "
                     f"(izvor {pack.source}). Narušeni zidovi: {res['broken_walls']}.")
            skeptic = SK.attack(f"Metoda {pack.name}", claim, subject=pack.name)
    except Exception:                                  # noqa: BLE001
        skeptic = None
    return {"reproduced": True, "pid": pid, "result": res, "skeptic": skeptic}


def _on_decision(item: dict, approved: bool) -> None:
    if not approved:
        return
    d = item["payload"]["pack"]
    pack = PK.MethodPack.from_dict(d)
    try:
        REG.register(pack.spec())
    except ValueError:
        pass                                   # already registered — idempotent
    who = item.get("decided_by", "operator")
    _write_method_card(pack, item["payload"].get("result", {}), who)
    try:                                       # item 31: numbers attack every new claim too
        from . import adversary as ADV
        ADV.attack_in_background(pack.name)
    except Exception:                          # noqa: BLE001 — never blocks the approval
        pass
    mission_id = item["payload"].get("mission_id")
    if mission_id and pack.result_kind != "poluravan":
        # a proportion on the line or a density bound is NOT a point of the
        # zero-free-half-plane front — never compared or drawn together (item 27)
        J.log(METHOD_KIND, who, {"event": "not_on_front", "name": pack.name,
                                 "result_kind": pack.result_kind}, subject=pack.name,
              verdict="other_kind")
        mission_id = None
    if mission_id:
        from ..shared_lib import missions as MIS
        res = item["payload"].get("result", {})
        B = res.get("computed_B", pack.spec().optimum().B)
        try:
            MIS.record_method(mission_id, pack.name, B, source=pack.source)
        except KeyError:
            pass                                   # mission gone — nothing to update


def _write_method_card(pack: PK.MethodPack, result: dict, who: str) -> None:
    opt = pack.spec().optimum()
    walls = result.get("broken_walls", [])
    body = [
        f"**Metoda** `{pack.name}` iz izvora `{pack.source}`.",
        "",
        f"Granica koju familija dozvoljava: **B\\* = {opt.B:.12f}** "
        f"(ℓ={opt.l:.9f}, b={opt.b:.6f}, κ={opt.k:.9f}).",
        f"Isključuje netrivijalne nule u poluravni Re s > B\\*.",
        "",
        f"Rad tvrdi {pack.claimed_B:.12f}; naš pipeline reprodukuje "
        f"(razlika {abs(opt.B - pack.claimed_B):.2e} ≤ tol {pack.tol:.0e}).",
    ]
    if pack.exact_poly:
        body += ["", f"Minimalni polinom (tvrđen): `{pack.exact_poly}`."]
    body += ["", f"Narušeni uslovi dopustivosti na optimumu: "
             f"{walls if walls else 'nijedan'}.",
             "", "---",
             f"Ušlo kroz vrata uz test reprodukcije; potvrdio operater **{who}**.",
             "", "Grana: [[tema-quasi-rh]]"]
    card = Card(
        title=f"Metoda {pack.name} — granica B*",
        type="numeric-fact",
        status=CITED,
        sources=[pack.source],
        author="user",
        tags=list(pack.tags) + ["metoda"],
        body="\n".join(body),
    )
    v = gate().submit(card, actor="user", force_dir=config.DIR_METHODS)
    J.log(METHOD_KIND, who, {"event": "registered", "name": pack.name,
                             "card": card.id, "accepted": v.ok,
                             "reason": "" if v.ok else v.reason},
          subject=pack.name, verdict="accept" if v.ok else "reject")


def install_hooks() -> None:
    store().on_decision(METHOD_KIND, _on_decision)
