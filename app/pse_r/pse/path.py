"""
The unit's path [agreement §4 "Ruter"; rules 3, 15, 18, 19, 20]:

    agent → its PSE unit → PSE-L generator → model → generator → move (θ, PVP,
    Doctor) → back to the agent

This is the ONLY way an agent reaches a model. There is no role table: the
unit IS the role. `ask()` refuses for a dead or frozen unit; it runs the call
through every brake (budget and "→ ∞", kill switch, disclosure §17.2, egress,
local-only §17.3 for GGUF), speaks only through the generator (system prompt +
scrub = the unit's register and veto), screens the output with the harm sensor
and records the move. `work()` is the same move for agents without a model.
"""
from __future__ import annotations

import threading
from typing import Optional

from ..llm import backend as B
from . import measure as M
from . import unit as U

# the role each agent's unit uses for the generator register and tuning
AGENT_ROLE = {
    "chat": B.CHAT, "voice": B.MATH, "skeptic": B.SKEPTIC, "extractor": B.MATH,
    "reader": B.MATH, "curator": B.TRIAGE, "ideas": B.CURATE, "whiteboard": B.VISION,
    "mission-agent": B.CHAT,
}


_CURRENT = threading.local()


def current_unit() -> Optional[U.PSEUnit]:
    """The unit whose model call is running on this thread (for the brakes)."""
    return getattr(_CURRENT, "unit", None)


def brake_tripped(why: str, trigger: Optional[str] = None) -> None:
    """A brake fired during a unit's call: suspicion on that unit [rule 20 (5)]."""
    from . import doctor as DR
    u = current_unit()
    if u is not None and u.alive:
        _lib().report_brake(u, trigger or DR.T_INFINITY, note=why)


class Refused(RuntimeError):
    """The unit cannot act now (dead, frozen, or no model). The message is
    meant for the operator."""


def _lib():
    from ..shared_lib.pse_registry import pse
    return pse()


def unit(agent: str) -> U.PSEUnit:
    return _lib().unit(agent)


def screen(text: str, *, data_in_context: str = "", final: bool = False,
           sources: Optional[list] = None) -> list:
    """The harm sensor over a model output (the three harms of round 2)."""
    from ..guardian import harms as HRM
    findings = HRM.to_agent(text_from_data=data_in_context, reply=text)
    if final:
        findings += HRM.to_human(text, sources=sources or [])
    else:
        findings += HRM.chat_human(text)
        from ..vault.gate import _claims_proof
        claims, sentence = _claims_proof(text or "")
        if claims:
            findings.append(HRM.Finding(HRM.HUMAN, "tvrdnja-o-dokazu", sentence[:200],
                                        HRM.HIGH))
    return findings


def ask(agent: str, messages: list, *, system_extra: str = "", max_tokens: int = 0,
        to_human: bool = False, entity: Optional[tuple] = None,
        data_in_context: str = "", final: bool = False, sources: Optional[list] = None,
        actions: Optional[list] = None, remaining_work: Optional[int] = None,
        role: Optional[str] = None) -> B.Reply:
    """One model call by `agent`'s unit. Returns the reply; `reply.pse` holds
    the move (θ, triggers, the Doctor's finding) and `reply.harms` the findings.
    Raises Refused when the unit may not act."""
    from ..llm.router import router
    lib = _lib()
    u = lib.unit(agent)
    try:
        u.require_active()
    except U.UnitFrozen as e:
        raise Refused(f"Jedinica „{u.unit_id}“ je zamrznuta ({u.freeze_reason}). "
                      "Doktorova mjera čeka tvoju odluku u „Čeka tvoju odluku“.") from e
    except U.UnitDead as e:
        raise Refused(str(e)) from e
    role = role or AGENT_ROLE.get(agent, B.CHAT)
    from ..guardian import killswitch as KS
    from ..guardian.disclosure import DisclosureExceeded
    from ..guardian.egress import EgressBlocked
    from . import doctor as DR
    ks_before = KS.closed()
    _CURRENT.unit = u
    try:
        with lib.acting(u):
            reply = router().unit_call(u, role, messages, system_extra=system_extra,
                                       max_tokens=max_tokens)
    except DisclosureExceeded as e:                 # rule 20 (10): a protected object
        lib.report_brake(u, DR.T_PROTECTED, note=str(e)[:200])
        raise
    except EgressBlocked as e:                      # rule 20 (9): outside the destinations
        msg = str(e)
        if "allowlist" in msg or "nije dozvoljen" in msg:   # not network trouble
            lib.report_brake(u, DR.T_DESTINATION, note=msg[:200])
        raise
    finally:
        _CURRENT.unit = None
    if KS.closed() and not ks_before:               # the kill switch tripped itself
        lib.report_brake(u, DR.T_INFINITY, note="prekidač online AI-ja se sam isključio")
    harms = screen(reply.text or "", data_in_context=data_in_context, final=final,
                   sources=sources)
    last_user = next((getattr(m, "text", "") or "" for m in reversed(messages)
                      if getattr(m, "role", "") == "user"), "")
    acts = list(actions or [])
    if data_in_context:
        acts.append(M.Action("čita spoljni tekst", "f", checked=True, external=True))
    res = lib.move(u, words=reply.text or "", message=last_user, actions=acts,
                   entity=entity or (("operater", "human") if to_human else None),
                   to_human=to_human, via_generator=True, harms=harms,
                   remaining_work=remaining_work, note=f"{reply.provider}:{reply.model}")
    reply.pse = res
    reply.harms = harms
    return reply


def work(agent: str, actions: list, *, entity: Optional[tuple] = None,
         words: str = "", remaining_work: Optional[int] = None, harms: Optional[list] = None,
         note: str = ""):
    """A move of an agent without a model (or the non-model part of one)."""
    lib = _lib()
    u = lib.unit(agent)
    return lib.move(u, words=words, actions=actions, entity=entity,
                    remaining_work=remaining_work, harms=harms, note=note)


def words(agent: str, text: str, *, message: str = "", entity: Optional[tuple] = None,
          actions: Optional[list] = None, harms: Optional[list] = None, note: str = ""):
    """Record the words of an agent whose model output arrived another way
    (an injected `ask` in tests and the GUI's offline paths) as its move."""
    lib = _lib()
    return lib.move(lib.unit(agent), words=text or "", message=message, actions=actions,
                    entity=entity, harms=harms, note=note)


def may_act(agent: str) -> tuple[bool, str]:
    """Whether the agent's unit may act now; (False, why) otherwise."""
    u = _lib().unit(agent)
    if not u.alive:
        return False, f"{u.unit_id} je mrtva"
    if u.frozen:
        return False, f"{u.unit_id} je zamrznuta ({u.freeze_reason})"
    return True, ""


def may_irreversible(agent: str) -> bool:
    lib = _lib()
    return lib.may_irreversible(lib.unit(agent))


# --- the reader: a DIFFERENT model reads the agent's words [rules 3, 18] ---- #
def _reader_spec() -> Optional[M.ReaderSpec]:
    from ..llm import selection as SEL
    from ..llm.router import router, NoProvider
    sk, main = SEL.get_skeptic(), SEL.get_main()
    if not sk and not main:
        return None
    role = B.SKEPTIC if sk else B.MATH
    mid = sk or main
    ident = mid if mid.startswith("gguf:") else f"{mid}:{router().models.get(mid, '')}"

    def ask_(prompt: str) -> str:
        try:
            return router().sensor_call(role, prompt, max_tokens=200)
        except NoProvider:
            return ""
    return M.ReaderSpec(ask_, ident, self_read=not sk)


def install_reader() -> None:
    M.set_reader(_reader_spec)
