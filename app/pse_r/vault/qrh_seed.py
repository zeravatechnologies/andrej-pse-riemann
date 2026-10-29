"""
QRH content (plan F7): source cards, the quasi-RH topic, barriers and our own
(unreviewed) results.

Cold facts rule: only Liu and Xu–Sang carry a resolvable reference (their arXiv
ids, from the research note), so only those are CITED — at PREPRINT tier. The
OpenAI announcements, Siegel and the Quanta piece have no resolvable id in our
material, so they are FOLKLORE orientation cards, clearly marked "bez izvora",
never something a verified card may lean on. Our own numbers (the quartic, the
w-cliff, the 5/6 wall) are NAŠE-NERECENZIRANO — and the honest way to get that
tier is to RUN the lab experiments (run_labs=True), which produce COMPUTED cards
with a lab run and a script hash, not static prose.

Chronology (research note, 2026-10):
  30.09 OpenAI: no zeros for Re s > 7/8 (ζ and all Dirichlet L; Hecke over ℚ(√−3)); Lean, nerecenzirano
  01.10 OpenAI: uniform exclusion of Landau–Siegel zeros; Lean
  05.10 OpenAI: shorter argument for 11/12 (human-edited)
  08–12.10 Liu, arXiv 2610.12234: B ≈ 0.874957019420
  15.10 Xu–Sang, arXiv 2610.15291: B ≈ 0.874886647040
  19.10 Quanta: Radziwiłł; Sarnak awaits human verification
"""
from __future__ import annotations

from .. import config
from ..core import journal as J
from .card import Card, CITED, FOLKLORE
from .gate import gate

QRH_TOPIC_ID = "tema-quasi-rh"


def _submit(card: Card, force: bool, force_dir=None) -> str:
    if gate().find(card.id) and not force:
        return "skip"
    v = gate().submit(card, actor="seed", force_dir=force_dir)
    return "ok" if v.ok else f"fail: {v.reason[:80]}"


def _topic() -> Card:
    body = [
        "> Orijentaciona mapa grane kvazi-Rimanove hipoteze (QRH), bez izvora. "
        "Ne oslanjaj provjerenu karticu na ovu — ona je mapa, ne tvrdnja.", "",
        "**Šta je QRH.** Niz rezultata iz 2026. koji isključuju netrivijalne nule "
        "ζ (i Dirichletovih/Hecke L-funkcija) u poluravni Re s > B, za B < 1. "
        "Granice ne nastaju presjekom L-funkcija nego presjekom funkcija "
        "eksponenata iz dokaza (niska vs visoka strana).", "",
        "**Zajednička prava.** Sve metode leže na B(ℓ) = 11/12 − ℓ/4; 11/12 je "
        "ℓ=0, 7/8 je ℓ=1/6.", "",
        "**Metode (vidi `methods/` i lab `qrh_*`).** Liu (kubna, 0.874957019420), "
        "Xu–Sang (kvartna, 0.874886647040).", "",
        "**Ciljevi.** 0.87 · 5/6 ≈ 0.8333 · 3/4 · 1/2. Naši računi: familija ne "
        "vodi ispod ~0.870/5/6.", "",
        "## Otvorena pitanja", "",
        "- Da li je OpenAI visoka strana 7/8 neiscijeđena (naše čitanje grafa)?",
        "- Zašto rad o 11/12 traži ϑ ≤ 1/10?",
        "- Postoji li geometrija izvan Liu/Xu–Sang familije koja vodi prema 1/2?",
    ]
    return Card(id=QRH_TOPIC_ID, title="Tema: kvazi-Rimanova hipoteza (QRH)",
                type="note", status=FOLKLORE, author="seed",
                tags=["tema", "quasi-rh"], body="\n".join(body))


def _sources() -> list[Card]:
    cards = []
    # resolvable → CITED (PREPRINT tier)
    cards.append(Card(id="izvor-liu-2610-12234", title="Izvor: Liu (arXiv 2610.12234)",
                      type="source", status=CITED, sources=["arxiv:2610.12234"],
                      author="seed", tags=["quasi-rh", "liu"],
                      body="Liu, 08–12.10.2026. Granica B ≈ 0.874957019420 kao "
                           "korijen kubne; tri ravni L₀, L_K, H_ξ se sijeku u "
                           "jednoj tački; licenca κ = 2B − 1. Preprint, Lean.\n\n"
                           "Grana: [[tema-quasi-rh]]"))
    cards.append(Card(id="izvor-xu-sang-2610-15291",
                      title="Izvor: Xu–Sang (arXiv 2610.15291)",
                      type="source", status=CITED, sources=["arxiv:2610.15291"],
                      author="seed", tags=["quasi-rh", "xu-sang"],
                      body="Xu–Sang, 15.10.2026. 69991/80000 → 0.8748867 u dvije "
                           "faze; sistemski optimum 0.874886647040 (kvartna). "
                           "Uslovno na OpenAI ulaze. Preprint.\n\n"
                           "Grana: [[tema-quasi-rh]]"))
    # no resolvable id → FOLKLORE orientation (honest: bez izvora)
    folklore = [
        ("izvor-openai-7-8", "Izvor (orijentacija): OpenAI 7/8",
         "OpenAI, 30.09.2026 (199 str.): isključene netrivijalne nule za Re s > "
         "7/8 za ζ i sve Dirichletove L-funkcije (i Hecke nad ℚ(√−3)). Lean "
         "formalizovano, nerecenzirano. Bez razrješivog izvora u našem "
         "materijalu — orijentaciona kartica."),
        ("izvor-openai-11-12", "Izvor (orijentacija): OpenAI 11/12",
         "OpenAI, 05.10.2026 (49 str., jedini ljudski uređen): kraći argument za "
         "11/12. Bez Lean-a; eksperti uglavnom vjeruju. Bez razrješivog izvora."),
        ("izvor-siegel-uniform", "Izvor (orijentacija): Landau–Siegel (OpenAI)",
         "OpenAI, 01.10.2026: uniformno isključenje Landau–Siegelovih nula. Lean, "
         "nerecenzirano. Bez razrješivog izvora u našem materijalu."),
        ("izvor-quanta-2026-10-19", "Izvor (orijentacija): Quanta (19.10.2026)",
         "Quanta: Radziwiłł — tekst loše napisan ali vjerovatno tačan; Sarnak "
         "čeka ljudsku provjeru. Novinski izvor, orijentacija."),
    ]
    for cid, title, text in folklore:
        cards.append(Card(id=cid, title=title, type="source", status=FOLKLORE,
                          author="seed", tags=["quasi-rh"],
                          body=text + "\n\n> Bez izvora — ne oslanjaj provjerenu "
                                      "karticu na ovu.\n\nGrana: [[tema-quasi-rh]]"))
    return cards


def _barriers() -> Card:
    body = [
        "> Orijentacija (bez izvora). Brojevi se dobijaju iz lab eksperimenata "
        "`qrh_walls` / `qrh_transform` kao COMPUTED (NAŠE-NERECENZIRANO).", "",
        "**Ljestvica zidova (NAŠE).** Skidanjem uslova dopustivosti (Xu–Sang "
        "§6.2) najniže B pada do ≈ **5/6** (strukturni zid l_x > ℓ). Nijedna "
        "kontinualna deformacija ove geometrije ne prolazi ispod 5/6.", "",
        "**Litica po w (NAŠE).** Xu–Sang sjede na litici: w ≥ 0.26 → metoda "
        "puca. Jeftiniji pojačani moment je najjača poluga (~30× od t) — "
        "hipoteza.", "",
        "**Polinom 4. stepena (NAŠE).** Optimum Xu–Sang sistema je korijen "
        "133488B⁴ − 376596B³ + 384534B² − 167541B + 26231 (B = 0.874886647040).",
        "", "Pokreni `qrh_walls`, `qrh_poly`, `qrh_transform` za COMPUTED kartice.",
        "", "Grana: [[tema-quasi-rh]]",
    ]
    return Card(id="barijere-quasi-rh", title="Barijere: QRH familija do ~0.870 / 5/6",
                type="barrier", status=FOLKLORE, author="seed",
                tags=["quasi-rh", "barijera"], body="\n".join(body))


def seed_qrh(force: bool = False, run_labs: bool = False) -> dict:
    """Seed QRH content. Idempotent. run_labs=True also runs the qrh_* lab
    experiments to produce COMPUTED (NAŠE-NERECENZIRANO) result cards."""
    results = {"topic": _submit(_topic(), force),
               "barriers": _submit(_barriers(), force, force_dir=config.DIR_NOTES),
               "sources": {}}
    for c in _sources():
        results["sources"][c.id] = _submit(c, force)
    if run_labs:
        results["labs"] = _run_qrh_labs()
    J.log(J.SYSTEM, "seed", {"event": "qrh_seed", "run_labs": run_labs,
                             "sources": len(results["sources"])})
    return results


def _run_qrh_labs() -> dict:
    from ..lab import runner as RUN
    out = {}
    for key, params in (("qrh_poly", {"family": 1}), ("qrh_walls", {"nl": 1201, "nb": 801}),
                        ("qrh_transform", {"n_points": 500})):
        try:
            r = RUN.run(key, params)
            out[key] = r.get("card_id")
        except Exception as e:                          # noqa: BLE001
            out[key] = f"fail: {type(e).__name__}: {e}"
    return out


def is_seeded() -> bool:
    return gate().find(QRH_TOPIC_ID) is not None
