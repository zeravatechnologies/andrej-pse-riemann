"""
Template-only messages for critical things (round 3, item 17; Perun P6).

Alarms, healing steps and warnings are NEVER model text: each is one of the
fixed sentences below, and every slot is checked against its type before it is
filled. A value that does not fit is refused, not cleaned — so neither a
model nor attacker-controlled log text (a user name in an SSH log) can put
words into a critical message.
"""
from __future__ import annotations

import ipaddress
import re

_SLOT = {
    "ip": lambda v: str(ipaddress.ip_address(str(v))),
    "int": lambda v: str(int(v)),
    "num": lambda v: f"{float(v):.4g}",
    "name": lambda v: _re(r"[A-Za-z0-9._@-]{1,32}", v),          # account / user name
    "word": lambda v: _re(r"[A-Za-zčćžšđČĆŽŠĐ0-9 _./:-]{1,60}", v),
    "cmd": lambda v: _re(r"[A-Za-z0-9 _./:=@'-]{1,200}", v),
    "url": lambda v: _re(r"https://[A-Za-z0-9./_?=&#-]{4,200}", v),
}


def _re(rx: str, v) -> str:
    s = str(v)
    if not re.fullmatch(rx, s):
        raise ValueError(f"vrijednost ne odgovara šablonu: {s[:40]!r}")
    return s


TEMPLATES = {
    "ssh.tier1": ("SSH čuvar: izvor {ip:ip} — {n:int} sumnjivih pokušaja; narušeno ključeva: "
                  "{k:int}/3. Praćenje pojačano, zapis u SHARED_LIB."),
    "ssh.blocked": ("SSH čuvar: izvor {ip:ip} BLOKIRAN na 24 h (sva tri ključa „→ ∞“: "
                    "identitet, klaster, cilj {target:name}). Blokada se sama skida {until:word}."),
    "ssh.unblocked": "SSH čuvar: blokada izvora {ip:ip} istekla i uklonjena.",
    "ssh.session_killed": "SSH čuvar: prekinuta SSH sesija (PID {pid:int}) izvora {ip:ip}.",
    "ssh.no_rights": ("OPASNOST: SSH čuvar mora blokirati {ip:ip}, ali NEMA pravo (nema sudoers "
                      "pravila). Napad traje. Uradi ručno: {cmd:cmd} — ili instaliraj usko pravilo "
                      "po vodiču SUDOERS."),
    "ssh.propose_permanent": ("Prijedlog: TRAJNO blokirati {ip:ip} (nepovratno — tvoja odluka). "
                              "Komanda: {cmd:cmd}"),
    "ssh.propose_stop": ("Prijedlog: ugasiti SSH server dok napad traje (tvoja odluka). "
                         "Komanda: {cmd:cmd} · ponovo upaliti: {cmd2:cmd}"),
    "ks.auto": ("ONLINE AI ISKLJUČEN AUTOMATSKI: „→ ∞“ {metric:word} = {value:num} "
                "(L = {L:num}). Opozovi ključeve: {links:word}"),
    "guard.pause": ("„→ ∞“: {metric:word} = {value:num} (L = {L:num}) — pozivi modelu "
                    "pauzirani, model oslobođen. Odobri = nastavi."),
    "integrity": ("NARUŠEN INTEGRITET: {n:int} odluka se ne može ponovo izvesti iz dnevnika "
                  "(zapisi {ids:word}). Provjeri."),
    "heal.queued": "Liječenje [{agent:word}]: {action:word} (traži odobrenje)",
}

# English versions — same slots, fixed text (never translated on the fly)
TEMPLATES_EN = {
    "ssh.tier1": ("SSH guardian: source {ip:ip} — {n:int} suspicious attempts; keys violated: "
                  "{k:int}/3. Watching closer, recorded in SHARED_LIB."),
    "ssh.blocked": ("SSH guardian: source {ip:ip} BLOCKED for 24 h (all three keys “→ ∞”: "
                    "identity, cluster, target {target:name}). The block lifts itself {until:word}."),
    "ssh.unblocked": "SSH guardian: the block on {ip:ip} expired and was removed.",
    "ssh.session_killed": "SSH guardian: SSH session ended (PID {pid:int}) from {ip:ip}.",
    "ssh.no_rights": ("DANGER: the SSH guardian must block {ip:ip} but has NO right to (no sudoers "
                      "rule). The attack goes on. Do it by hand: {cmd:cmd} — or install the narrow "
                      "rule from the SUDOERS guide."),
    "ssh.propose_permanent": ("Proposal: block {ip:ip} PERMANENTLY (irreversible — your decision). "
                              "Command: {cmd:cmd}"),
    "ssh.propose_stop": ("Proposal: stop the SSH server while the attack lasts (your decision). "
                         "Command: {cmd:cmd} · start again: {cmd2:cmd}"),
    "ks.auto": ("ONLINE AI SWITCHED OFF AUTOMATICALLY: “→ ∞” {metric:word} = {value:num} "
                "(L = {L:num}). Revoke the keys: {links:word}"),
    "guard.pause": ("“→ ∞”: {metric:word} = {value:num} (L = {L:num}) — model calls "
                    "paused, model unloaded. Approve = continue."),
    "integrity": ("INTEGRITY BROKEN: {n:int} decisions cannot be re-derived from the journal "
                  "(records {ids:word}). Check."),
    "heal.queued": "Healing [{agent:word}]: {action:word} (needs approval)",
}

_FIELD = re.compile(r"\{(\w+):(\w+)\}")


def render(tid: str, **slots) -> str:
    """Fill a fixed template. Raises KeyError/ValueError on anything unexpected."""
    from ..i18n import lang
    tpl = (TEMPLATES_EN if lang() == "en" else TEMPLATES)[tid]
    need = _FIELD.findall(tpl)
    names = {n for n, _ in need}
    extra = set(slots) - names
    if extra:
        raise ValueError(f"šablon {tid} nema polja {sorted(extra)}")
    out = tpl
    for name, typ in need:
        if name not in slots:
            raise ValueError(f"šablon {tid}: nedostaje {name}")
        out = out.replace("{%s:%s}" % (name, typ), _SLOT[typ](slots[name]))
    return out


def ids() -> list[str]:
    return sorted(TEMPLATES)
