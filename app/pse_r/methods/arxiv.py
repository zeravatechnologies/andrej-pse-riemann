"""
arXiv watching for the QRH line (plan F9).

The srž of the project: a new paper on the quasi-Riemann hypothesis arrives, the
main AI extracts a candidate method (its exponent family + the number the paper
claims) as a method pack, and that pack goes through THE SAME door as any other
(methods.door): the deterministic reproduction test first, the human queue after.
No paper enters as an assertion; it enters as a recipe to be re-derived.

The network fetch reuses ingest.sources.arxiv_search, which is already behind the
guardian egress gate. Offline, `watch()` returns an empty list rather than
raising — the lab, the gate and the explorer keep working without the internet
(plan §1, "Bez interneta").

Extraction itself (reading 200 pages into an (E, params) recipe) is the main
AI's job and lands with F3; here we build the plumbing and accept a recipe from
a caller, so the pipeline is testable end to end today with a known recipe.
"""
from __future__ import annotations

from typing import Optional

QRH_QUERY = "quasi-Riemann hypothesis"


def watch(max_results: int = 25) -> list:
    """
    Candidate QRH papers from arXiv, newest first. Returns ingest.sources.Item
    objects. Never raises on a network/egress failure — returns [] instead.
    """
    try:
        from ..ingest import sources as S
        from ..guardian.egress import EgressBlocked
    except ImportError:
        return []
    try:
        return S.arxiv_search(QRH_QUERY, max_results=max_results)
    except Exception:                                      # noqa: BLE001
        # EgressBlocked, URLError, parse errors, offline — all mean "no papers now"
        return []


def propose_from_recipe(source_ref: str, family: str, claimed_B: float,
                        proposer: str, dlo: float = 1 / 8, tol: float = 1e-7,
                        exact_poly: str = "", note: str = "",
                        mission_id: Optional[str] = None,
                        name: Optional[str] = None,
                        system: Optional[dict] = None) -> dict:
    """
    Turn an extracted recipe into a method pack and send it through the door.
    `source_ref` is the paper (arxiv:… / doi:…); `family` selects the exponent
    family; `claimed_B` is what the paper states. The door runs the reproduction
    test and only then queues it for the operator. If `mission_id` is given, the
    linked mission is updated when the operator approves.
    """
    from . import door as DOOR
    from . import pack as PK
    nm = name or source_ref.split(":")[-1]
    d = {"name": nm, "source": source_ref, "claimed_B": claimed_B, "dlo": dlo,
         "tol": tol, "exact_poly": exact_poly, "note": note, "tags": ["qrh", "arxiv"]}
    if family:
        d["family"] = family
    if system:
        d["system"] = system           # a genuinely new paper: its system AS DATA
    pack = PK.MethodPack.from_dict(d)
    return DOOR.import_pack(pack, proposer=proposer, mission_id=mission_id)
