"""
Mission 2 content (round 3, item 25): source cards from the Langlands /
higher-degree research (research/langlands-2026-10/REPORT.md), so every
package carries them.

Tiers come from the source kind (vault/tiers.py): a DOI is REFEREED, an arXiv
id is PREPRINT. The topic card is a FOLKLORE map — no verified card may lean on
it. Nothing here claims that 7/8 transfers to higher degree: that is the open
question of mission 2.
"""
from __future__ import annotations

from .card import Card, CITED, FOLKLORE
from .qrh_seed import _submit

TOPIC_ID = "tema-visi-stepen"

_SRC = [
    ("izvor-glc-i-2405-03599", "Izvor: Gaitsgory–Raskin, geometrijski Langlands I (arXiv 2405.03599)",
     ["arxiv:2405.03599"], ["langlands", "geometrijski"],
     "Prvi od pet radova (2024, >800 strana ukupno) za nerazgranatu geometrijsku "
     "Langlandsovu hipotezu, de Rham i Betti, karakteristika 0. Snopovi na krivama nad ℂ — "
     "ne daje eksponente ni nulte oblasti nad ℚ. Kontekst, ne alat za misiju 2."),
    ("izvor-glc-v-2409-09856", "Izvor: geometrijski Langlands V — multiplicity one (arXiv 2409.09856)",
     ["arxiv:2409.09856"], ["langlands", "geometrijski"],
     "Završni rad serije: funktor je ekvivalencija. Preprint u našim izvorima."),
    ("izvor-newton-thorne-i", "Izvor: Newton–Thorne, simetrični stepeni I (Publ. IHÉS 2021)",
     ["doi:10.1007/s10240-021-00127-3"], ["langlands", "funkcionalnost", "gl2"],
     "Automorfnost Sym^n f za svako n (nivo 1). Daje analitičko produženje "
     "L(Sym^n f, s) — preduslov da se za te porodice uopšte postavi pitanje nulte oblasti."),
    ("izvor-newton-thorne-ii-2009-07180", "Izvor: Newton–Thorne II (arXiv 2009.07180)",
     ["arxiv:2009.07180"], ["langlands", "funkcionalnost", "gl2"],
     "Isto za svaku holomorfnu formu bez CM."),
    ("izvor-harcos-thorner-2303-16889", "Izvor: Harcos–Thorner, nulta oblast Rankin–Selberg (arXiv 2303.16889)",
     ["arxiv:2303.16889"], ["visi-stepen", "nulta-oblast"],
     "Nova nulta oblast za GL(1)-uvijanja Rankin–Selberg L-funkcija; tip blizu Re s = 1, "
     "nije poluravan kao 7/8."),
    ("izvor-large-sieve-gln-2508-14888", "Izvor: Large sieves for GL_n (arXiv 2508.14888)",
     ["arxiv:2508.14888"], ["visi-stepen", "large-sieve"],
     "Large sieve za koeficijente automorfnih L-funkcija u porodicama + gustina nula. "
     "Kandidat za zamjenu kvadratnog large sieve-a iz dokaza 7/8 (uz gubitak)."),
    ("izvor-creech-2509-20873", "Izvor: eksplicitna nulta oblast za GL(2) (arXiv 2509.20873)",
     ["arxiv:2509.20873"], ["visi-stepen", "gl2"],
     "Klasična (de la Vallée Poussin) eksplicitna oblast za newform; kontrola."),
    ("izvor-alpoge-furman-2608-13637", "Izvor: Alpöge–Furman, > 2/3 nula prostih i na pravoj (arXiv 2608.13637)",
     ["arxiv:2608.13637"], ["zeta", "udio-na-pravoj"],
     "Drugi TIP rezultata: udio nula na kritičnoj pravoj (2/3; 0.6725 sa optimizovanim "
     "jezgrom), ne poluravan bez nula. Ne porediti i ne crtati zajedno sa 7/8. Argument je "
     "napisao Claude; autori su ga provjerili; Lean; preprint."),
]


def _topic() -> Card:
    body = "\n".join([
        "> Mapa za misiju 2, bez izvora. Ne oslanjaj provjerenu karticu na ovu.", "",
        "**Pitanje.** Prenosi li se metoda 7/8 (Liu, Xu–Sang) na L-funkcije višeg stepena "
        "(GL(2), Artin)? Ako da, kako se eksponent mijenja sa stepenom d i postoji li T_d?", "",
        "**Šta dokaz 7/8 koristi.** Möbiusove sume nad karakterima, sekstične → kubne Gaussove "
        "sume, Kubotina kubna theta i Pattersonovi koeficijenti, kvadratni large sieve. "
        "To su GL(1) alati; analog „Gaussove sume = koeficijenti thete“ za GL(2) nije poznat.", "",
        "**Stanje.** Otvoreno pitanje. Detalji i mapa prenosivosti: "
        "research/langlands-2026-10/REPORT.md.", "",
        "Izvori: [[izvor-newton-thorne-i]] · [[izvor-large-sieve-gln-2508-14888]] · "
        "[[izvor-harcos-thorner-2303-16889]] · [[izvor-glc-i-2405-03599]] · "
        "[[izvor-alpoge-furman-2608-13637]]",
    ])
    return Card(id=TOPIC_ID, title="Tema: viši stepen i Langlands (misija 2)", type="note",
                status=FOLKLORE, author="seed", tags=["tema", "visi-stepen", "langlands"],
                body=body)


def is_seeded() -> bool:
    from .gate import gate
    return gate().find(TOPIC_ID) is not None


def seed(force: bool = False) -> dict:
    out = {}
    for cid, title, src, tags, body in _SRC:
        c = Card(id=cid, title=title, type="source", status=CITED, sources=src,
                 author="seed", tags=tags, body=body + "\n\nGrana: [[" + TOPIC_ID + "]]")
        out[cid] = _submit(c, force)
    out[TOPIC_ID] = _submit(_topic(), force)
    return out
