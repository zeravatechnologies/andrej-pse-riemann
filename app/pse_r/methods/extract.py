"""
Extraction: a QRH paper → a method pack, by the MAIN AI (plan F9).

The main model reads the paper (ar5iv full text, through the guardian egress)
and writes ONE method pack whose `system` carries the paper's exponent
comparison system as data. It is a proposal, nothing more:

  * the pack must parse (methods.expr: arithmetic only, or it is refused);
  * it then goes through THE door: the deterministic reproduction test must hit
    the number the paper states, a claimed polynomial must change sign at B*;
  * the skeptic (another model) attacks it; the operator decides.

The model is told the number must be the paper's own, and that a system which
does not reproduce it will simply be refused — there is nothing to gain by
guessing. The paper text is external data: it is sanitised by the guardian and
the model's output is screened for the three harms like any other output.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from ..core import journal as J

MAX_PAPER_CHARS = 60_000
_FOCUS = re.compile(r"(?i)(zero[- ]free|exponent|half[- ]plane|admissib|large sieve|"
                    r"amplif|moment|licen|kappa|κ|ℓ|\\ell|delta|δ|parameter)")

PROMPT = """Iz rada ispod izvuci SISTEM POREĐENJA EKSPONENATA koji daje granicu
B (poluravan bez nula Re s > B) i vrati JEDAN JSON objekat — paket metode.

Pravila (provjerava ih kapija, ne čovjek):
- "claimed_B" je broj KOJI RAD TVRDI (ne tvoja procjena).
- "system" nosi sistem kao podatak: "defs" (lista [ime, izraz] redom),
  "branches" (lista {{"E": izraz visoke strane, "delta": [lo, hi]}}),
  "x_grid", "line" (B kao funkcija ell), "licence" (kappa kao funkcija B),
  "b_range", "ell_range", "walls" (uslovi dopustivosti, npr. "6*kappa*ell > 3/4").
- Izrazi smiju sadržati SAMO brojeve, + - * / **, zagrade, imena b, ell, kappa,
  delta, x, B, ranije definicije i funkcije sqrt, log, exp, abs, min, max.
- "exact_poly" (opciono): minimalni polinom granice, U PROMJENLJIVOJ B.
- Ako granica nije izvodiva iz sistema, ne izmišljaj: vrati {{"error": "zašto"}}.
- Sistem koji ne reprodukuje broj iz rada biće ODBIJEN — nagađanje ne pomaže.

Primjer ispravnog paketa (Liu, arXiv 2610.12234):
```json
{example}
```

Rad: {ref} — {title}
-----
{paper}
-----
Vrati samo JSON u bloku ```json ... ```."""


def _example() -> str:
    from .pack import default_packs_dir
    d = default_packs_dir()
    if d and (d / "liu.json").exists():
        raw = json.loads((d / "liu.json").read_text(encoding="utf-8"))
        raw.pop("family", None)
        return json.dumps(raw, ensure_ascii=False, indent=1)
    return "{}"


def focus_text(text: str, limit: int = MAX_PAPER_CHARS) -> str:
    """Keep the paragraphs that talk about exponents/parameters, up to `limit`."""
    if len(text) <= limit:
        return text
    paras = re.split(r"\n\s*\n", text)
    head = "\n\n".join(paras[:6])
    keep = [p for p in paras[6:] if _FOCUS.search(p)]
    out = head
    for p in keep:
        if len(out) + len(p) + 2 > limit:
            break
        out += "\n\n" + p
    return out


def parse_pack_json(reply: str) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", reply or "", re.S)
    raw = m.group(1) if m else (reply or "").strip()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"model nije vratio ispravan JSON: {e}") from e
    if not isinstance(d, dict):
        raise ValueError("model nije vratio objekat")
    if "error" in d and "system" not in d:
        raise ValueError(f"model kaže da se sistem ne može izvesti: {d['error']}")
    return d


def extract_pack(ref: str, title: str = "", paper_text: Optional[str] = None,
                 ask: Optional[Callable[[str], str]] = None) -> dict:
    """Paper → pack dict (not yet reproduced). `ask(prompt) -> reply` for tests."""
    if paper_text is None:
        from ..ingest import sources as S
        rep = S.ar5iv_fulltext(ref)
        paper_text = rep.text
    prompt = PROMPT.format(example=_example(), ref=ref, title=title,
                           paper=focus_text(paper_text))
    from ..pse import path as PATH
    src = ref if ref.startswith(("arxiv:", "doi:", "url:")) else f"arxiv:{ref}"
    if ask is None:
        from ..llm import backend as B
        reply = PATH.ask("extractor", [B.Msg("user", prompt)], max_tokens=12000,
                         data_in_context=paper_text[:20000], entity=(src, "document")).text
    else:
        reply = ask(prompt)
        from ..pse import measure as PM
        PATH.words("extractor", reply, message=prompt[:4000], entity=(src, "document"),
                   actions=[PM.Action("čita spoljni tekst", "f", external=True)],
                   harms=PATH.screen(reply, data_in_context=paper_text[:20000]), note="ask")
    d = parse_pack_json(reply)
    d["source"] = ref if ref.startswith(("arxiv:", "doi:", "url:")) else f"arxiv:{ref}"
    d.setdefault("name", ref.split(":")[-1])
    d.setdefault("tags", ["qrh", "arxiv", "izvučeno"])
    return d


def extract_and_propose(ref: str, title: str = "", paper_text: Optional[str] = None,
                        ask: Optional[Callable[[str], str]] = None) -> dict:
    """Extract with the main AI, then send through the door (reproduce → queue)."""
    from ..llm import selection as SEL
    from ..shared_lib import missions as MIS
    from . import door as DOOR
    d = extract_pack(ref, title, paper_text, ask)
    J.log(J.METHOD, "extract", {"event": "extracted", "ref": ref,
                                "claimed_B": d.get("claimed_B")}, subject=ref,
          verdict="extracted")
    proposer = f"model:{SEL.get_main() or 'nepoznat'}"
    return DOOR.import_pack(d, proposer=proposer, mission_id=MIS.FIRST_ID)
