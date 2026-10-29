"""
The working paper from missions 2 and 3 (round 3, item 33).

The app assembles a draft — introduction, methods, computations (each with its lab
run), figures (the runs' PNGs), sources with their tiers, open questions — labelled
NAŠE-NERECENZIRANO from the first line to the last. Before the operator sees it:

  * the GATE reads it: any sentence asserting a proof of an open problem is refused
    (the draft is not written, the reason is shown);
  * every number carries a source or a lab run on the same line — `unsourced()` finds
    the lines that do not, and the draft is not released while there are any;
  * the SKEPTIC attacks it (objections go into the draft, honestly "unavailable" if
    there is no second model) and the ADVERSARIAL mode's latest findings for the
    methods it uses are attached.

"Kompleksna verzija ne daje ništa novo" is a result too, and it is written.
The draft is written as a sealed report (the keepers guard it) and a queue item asks
the operator to read it; approving means "read", never "reviewed by a referee".
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, Optional

from ..core import journal as J

LABEL = "NAŠE-NERECENZIRANO"
KIND = "paper-draft"
_NUM = re.compile(r"(?<![\w.])\d+\.\d{3,}")
_CITE = re.compile(r"\[lab:[^\]]+\]|\[\[[^\]]+\]\]|\(izvor:[^)]+\)|\[kod:[^\]]+\]|\[istraživanje:[^\]]+\]")


class PaperRefused(Exception):
    pass


def unsourced(md: str) -> list:
    """Lines with a number (≥ 3 decimals) but no citation on the same line."""
    bad = []
    for i, line in enumerate(md.splitlines(), 1):
        if line.lstrip().startswith(("#", "|---", "```")):
            continue
        if _NUM.search(line) and not _CITE.search(line):
            bad.append((i, line.strip()[:160]))
    return bad


def proof_claims(md: str) -> list:
    """Sentences the vault gate would refuse as a proof claim."""
    from ..vault.gate import _claims_proof
    out = []
    for para in re.split(r"\n\s*\n", md):
        bad, why = _claims_proof(para)
        if bad:
            out.append((para.strip()[:200], why))
    return out


def _latest_run(experiment: str, match: Optional[Callable[[dict], bool]] = None) -> Optional[dict]:
    from ..lab import runner as LR
    for r in LR.list_runs(200):
        if r.get("experiment") != experiment:
            continue
        rec = LR.load_run(r["run_id"])
        if rec and (match is None or match(rec)):
            return rec
    return None


def _ensure_runs() -> dict:
    """The computations the draft cites; run what is missing (deterministic, minutes)."""
    from ..lab import runner as LR
    runs = {}
    for fam in (0, 1):
        name = "liu" if fam == 0 else "xs"
        rec = _latest_run("qrh_complex", lambda r, n=name: r["numbers"].get("metoda") == n)
        if rec is None:
            rec = LR.run("qrh_complex", {"family": fam, "n": 41}, make_card=False)["record"]
        runs[f"complex-{name}"] = rec
        rec = _latest_run("qrh_adversary", lambda r, n=name: r["numbers"].get("metoda") == n)
        if rec is None:
            rec = LR.run("qrh_adversary", {"family": fam, "eps_exp": 6}, make_card=False)["record"]
        runs[f"adv-{name}"] = rec
    return runs


def _sources() -> list:
    from ..vault.store import iter_cards
    from ..vault import tiers as T
    out = []
    for c in iter_cards():
        if c.type != "source":
            continue
        tags = set(c.tags or [])
        if not ({"langlands", "visi-stepen", "qrh"} & tags) and not c.id.startswith(("izvor-liu", "izvor-xu")):
            continue
        tier = T.source_tier(c.sources[0]) if c.sources else "?"
        out.append((c.id, c.title, tier))
    return sorted(out)


def assemble(runs: Optional[dict] = None) -> str:
    from . import missions as MIS
    runs = runs or _ensure_runs()
    m2, m3 = MIS.get(MIS.SECOND_ID), MIS.get(MIS.THIRD_ID)
    cl, cx = runs["complex-liu"], runs["complex-xs"]
    al, ax = runs["adv-liu"], runs["adv-xs"]
    nl, nx = cl["numbers"], cx["numbers"]
    L = [f"# Radni tekst: granica 7/8 u višem stepenu i u kompleksnoj ravni",
         "",
         f"**{LABEL}.** Radni tekst koji je sastavila aplikacija PSE Riemann ({time.strftime('%Y-%m-%d')}). "
         "Nije recenziran i ne tvrdi dokaz ničega; svaki broj nosi lab run ili izvor u istom redu.",
         "",
         "## 1. Uvod",
         "",
         "Metode Liu i Xu–Sang daju poluravan bez nula Re s > B za ζ i Dirichletove L-funkcije "
         "(nivo izvora: PREPRINT; vidi §6). Ovaj tekst prati dva pitanja aplikacije: misija 2 "
         "(„" + (m2["title"] if m2 else "viši stepen") + "“) i misija 3 („" + (m3["title"] if m3 else "kompleksna verzija") + "“).",
         "",
         "## 2. Metode",
         "",
         "Eksponent visoke strane E(b, ℓ, κ, δ, x) uzet je iz koda aplikacije [kod:methods/core.py]; "
         "granica metode je najveće ℓ za koje je max_δ E ≤ 0, uz licencu κ = 2B − 1 i x = 1/2, "
         "a B = 11/12 − ℓ/4. Sve računa Python deterministički; svaki račun je lab run sa skriptom i sha256.",
         "",
         "## 3. Misija 2 — viši stepen (mapa prenosivosti)",
         ""]
    if m2:
        L.append(f"Pitanje: {m2['question']}")
        L.append("")
        for st in m2["steps"]:
            ref = st.get("ref") or ""
            cite = f"[[{ref}]]" if ref.startswith(("izvor-", "tema-")) else (f"[lab:{ref[4:]}]" if ref.startswith("lab:") else f"[kod:{ref}]" if ref else "")
            L.append(f"- {st['action']} → **{st['outcome']}** {cite}".rstrip())
        L.append("")
        L.append(f"Stanje: {m2['state']}")
    L += ["",
          "## 4. Misija 3 — kompleksna verzija",
          "",
          "**(a) σ*(γ).** U Liu/Xu–Sang sistemima E ne sadrži γ, pa je u okviru tih metoda σ*(γ) ≡ B "
          "[istraživanje:misija3-2026-10] — čitanje formalizma, ne teorema.",
          "",
          "**(b) E sa kompleksnim δ.** Brojilac E(δ) pri x = 1/2 je kvadratni polinom u δ; granica metode je nula diskriminante "
          "[kod:methods/complexver.py].",
          "",
          "| | Liu | Xu–Sang |",
          "|---|---|---|",
          f"| ℓ* (optimum) | {nl['ℓ* (optimum)']:.15f} [lab:{cl['run_id']}] | {nx['ℓ* (optimum)']:.15f} [lab:{cx['run_id']}] |",
          f"| ℓ iz nule diskriminante | {nl['ℓ (diskriminanta = 0)']:.15f} [lab:{cl['run_id']}] | {nx['ℓ (diskriminanta = 0)']:.15f} [lab:{cx['run_id']}] |",
          f"| razlika | {nl['razlika']:.1e} [lab:{cl['run_id']}] | {nx['razlika']:.1e} [lab:{cx['run_id']}] |",
          f"| δ* | {nl['δ* (dvostruki korijen)']:.10f} [lab:{cl['run_id']}] | {nx['δ* (dvostruki korijen)']:.10f} [lab:{cx['run_id']}] |",
          f"| c u Im δ ≈ c·√(ℓ* − ℓ) | {nl['c u |Im δ| ≈ c·√(ℓ* − ℓ)']:.4f} [lab:{cl['run_id']}] | {nx['c u |Im δ| ≈ c·√(ℓ* − ℓ)']:.4f} [lab:{cx['run_id']}] |",
          "",
          "**Rezultat: kompleksna verzija ne daje novo B.** Daje algebarsku karakterizaciju granice (nula diskriminante) "
          "i mjeru margine (Im δ). I to je rezultat [istraživanje:misija3-2026-10].",
          "",
          "## 5. Adversarijalna provjera tvrdnji",
          ""]
    for rec, name in ((al, "Liu"), (ax, "Xu–Sang")):
        n = rec["numbers"]
        L.append(f"- {name}: tvrđeno B = {n['tvrđeno B']:.12f}, najbolje uz uslove metode {n['najbolje B uz uslove']:.12f} "
                 f"({'NIJE optimum' if n['bolje od tvrdnje'] else 'tvrdnja odolijeva'}); "
                 f"{n['tačaka bolje uz kršenje']} tačaka sa boljim B krši licencu ili zid; certifikat praznine za "
                 f"B ∈ [{n['certifikat: B od']:.6f}, {n['certifikat: B do']:.9f}] "
                 f"({'kompletan' if n['certifikat kompletan'] else 'DJELIMIČAN'}) [lab:{rec['run_id']}]")
    L += ["", "## 6. Izvori i nivoi", ""]
    for cid, title, tier in _sources():
        L.append(f"- {title} — nivo **{tier}** [[{cid}]]")
    L += ["", "## 7. Slike", ""]
    for rec in (cl, cx, al, ax):
        for png in rec.get("plots") or []:
            L.append(f"- `{rec['run_id']}/{png}` — {rec['title']} [lab:{rec['run_id']}]")
    L += ["", "## 8. Otvorena pitanja", ""]
    for m in (m2, m3):
        if not m:
            continue
        for st in m["steps"]:
            if "otvoren" in st["outcome"].lower() or "otvoreno pitanje" in st["action"].lower():
                L.append(f"- ({m['title']}) {st['action']}")
    L += ["- (misija 3) σ*(γ) van Liu/Xu–Sang formalizma, uz eksplicitne stepene log γ umjesto ε.",
          "- (misija 3) prenosi li se „nula diskriminante“ na sisteme sa više grana E.",
          "- (misija 2) postoji li GL(2) zamjena za korak „Gaussove sume → kubna theta“.",
          "", f"---", f"_{LABEL} · sastavljeno automatski · kapija, skeptik i adversarijalni mod prije operatera._"]
    # a mathematical star next to a letter (σ*, ℓ*, δ*, B*) would open Markdown emphasis
    return re.sub(r"(?<=[σℓδBκ])\*", "∗", "\n".join(L))


def build(ask_skeptic=None, runs: Optional[dict] = None) -> dict:
    """Assemble → gate → sources check → skeptic; then seal + queue. Raises PaperRefused
    when the gate or the source check fails (nothing is written)."""
    from ..pse import measure as PM
    from ..pse import path as PATH
    ok, why = PATH.may_act("paper")
    if not ok:                                          # Faza 6d: a frozen unit does not act
        raise PaperRefused(f"sastavljač rada: {why}")
    md = assemble(runs)
    claims = proof_claims(md)
    if claims:
        PATH.work("paper", [PM.Action("sastavlja tekst", "f"),
                            PM.Action("odbija tekst koji tvrdi dokaz", "s", justified=True)],
                  note="kapija")
        raise PaperRefused("kapija: tekst tvrdi dokaz — " + "; ".join(w for _p, w in claims[:3]))
    bad = unsourced(md)
    if bad:
        PATH.work("paper", [PM.Action("sastavlja tekst", "f"),
                            PM.Action("odbija brojeve bez izvora", "s", justified=True)],
                  note="izvori")
        raise PaperRefused("brojevi bez izvora/lab run-a u redovima: " + ", ".join(str(i) for i, _ in bad[:10]))
    from ..llm import skeptic as SK
    try:
        r = SK.attack("Radni tekst (misije 2 i 3)", md[:12000], subject="paper",
                      ask=ask_skeptic, queue=False)
    except PATH.Refused as e:
        r = {"available": True, "objections": [], "error": str(e)}
    sk = ["", "## Prigovori skeptika (prije operatera)", ""]
    if not r["available"]:
        sk.append("- _skeptik nedostupan (nema drugog modela) — samo determinističke provjere: kapija, izvori, adversarijalni mod_")
    elif r.get("error"):
        sk.append(f"- _skeptik je pao: {r['error'][:200]}_")
    elif not r["objections"]:
        sk.append("- _nema prigovora_")
    for o in r["objections"]:
        sk.append(f"- **[{o.ozbiljnost}]** {o.prigovor} — {o.razlog} ({o.gdje})")
    md = md + "\n" + "\n".join(sk) + "\n"
    from . import runtime as RT
    from .store import store
    path = RT.write_final_report(f"radni-tekst-misije-2-3-{time.strftime('%Y%m%d-%H%M%S')}", md)
    pid = store().propose(KIND, f"Radni tekst (misije 2 i 3) spreman — pročitaj ({LABEL})",
                          {"path": str(path), "skeptic": r["available"],
                           "objections": len(r["objections"])}, proposer="paper")
    PATH.work("paper", [PM.Action("sastavlja tekst", "f"), PM.Action("kapija i izvori", "f"),
                        PM.Action("šalje radni tekst operateru", "o")],
              entity=("operater", "human"), note=Path(path).name)
    J.log(J.REPORT, "paper", {"event": "draft", "path": str(path), "label": LABEL,
                              "objections": len(r["objections"])}, subject=Path(path).name, verdict="draft")
    return {"path": str(path), "pid": pid, "markdown": md, "objections": len(r["objections"]),
            "skeptic": r["available"]}
