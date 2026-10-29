"""
"Čeka tvoju odluku" in groups (plan 33d; agreement rule 32).

A tree: kind of item → group (the mission for mission items, the corpus branch
for papers — taken deterministically from title + abstract) → items. The
operator ticks one, several or all items (or a whole group) and decides them
together — but only items whose decision can be undone may be decided in bulk.
A Doctor's measure and every irreversible item are decided one by one.
"""
from __future__ import annotations

from typing import Optional

from .store import store

KIND_LABEL = {
    "doctor-measure": "Doktorove mjere",
    "doctor-review": "Doktor: ponovni pregled mjera",
    "pse-undo": "Poništavanje fisije/fuzije",
    "vote-weights": "Težine glasova",
    "arxiv-paper": "Novi radovi (arXiv)",
    "mission-proposal": "Prijedlozi iz razgovora o misiji",
    "mission-goal": "Cilj misije",
    "mission-switch": "Promjena aktivne misije",
    "skeptic": "Prigovori skeptika",
    "adversary": "Adversarijalni nalazi",
    "method": "Metode (prošle vrata)",
    "paper-draft": "Radni tekst",
    "declarations": "Deklaracije",
    "quarantine": "Karantin hosta",
    "guard-pause": "„→ ∞“: pauza poziva modelu",
    "online-ai-closed": "Online AI isključen",
    "integrity": "Integritet dnevnika",
    "archive": "Arhiva dnevnika",
    "ssh-permanent": "SSH: trajna blokada",
    "ssh-stop": "SSH: zaustavljanje servera",
}

# Decisions that can be undone (or only add something the operator can remove
# later): these may be decided in bulk. Everything else — and every kind not
# listed — is one by one [rule 32].
BULK_OK = {"arxiv-paper", "mission-proposal", "skeptic", "adversary", "paper-draft",
           "mission-switch", "mission-goal"}
ONE_BY_ONE_REASON = "Doktorova mjera ili nepovratna odluka — samo jedna po jedna"


def bulk_allowed(item: dict) -> bool:
    return item.get("kind") in BULK_OK


def _mission_title(mid: str) -> str:
    from . import missions as MIS
    m = MIS.get(mid) if mid else None
    return m["title"] if m else (mid or "")


def _topic(item: dict) -> str:
    from ..ingest import topics as T
    p = item.get("payload") or {}
    text = f"{p.get('title') or item.get('title', '')} {p.get('abstract') or ''}"
    key, score = T.best_branch(text)
    if not key or score <= 0:
        return "ostalo"
    b = T.BY_KEY.get(key)
    return b.title if b else key


def subgroup(item: dict) -> str:
    p = item.get("payload") or {}
    kind = item.get("kind", "")
    if kind == "arxiv-paper":
        return _topic(item)
    mid = p.get("mission") or p.get("mission_id")
    if mid:
        return _mission_title(mid)
    if kind in ("doctor-measure", "doctor-review"):
        return p.get("agent") or p.get("unit", "")
    return ""


def title_of(item: dict) -> str:
    """The item's title in the interface language. A Doctor's measure is composed
    from its payload (it is stored before anyone knows the reader's language)."""
    if item.get("kind") == "doctor-review":
        from ..i18n import tr
        p = item.get("payload") or {}
        return tr("Doktor, ponovni pregled: ukinuti mjeru za {0}?").format(p.get("unit", ""))
    if item.get("kind") != "doctor-measure":
        return item.get("title", "")
    from ..i18n import lang, tr
    from ..pse import doctor as DR
    p = item.get("payload") or {}
    lad = (DR.LADDER_EN if lang() == "en" else DR.LADDER_SR).get(p.get("measure"), p.get("measure"))
    return tr("Doktor: {0} za {1}").format(lad, p.get("unit", ""))


def _why(p: dict) -> str:
    from ..i18n import lang
    f = p.get("finding") or {}
    labels = p.get("labels_en" if lang() == "en" else "labels_sr") or f.get("triggers") or []
    att = f.get("attractor")
    return ", ".join(labels) + (f" · θ: {att}" if att and att not in ("H", "?") else "")


def tree(items: Optional[list] = None) -> list[dict]:
    """[{kind, label, bulk, groups: [{name, items: [...]}]}], sorted by kind label."""
    items = store().open_items() if items is None else items
    kinds: dict = {}
    for it in items:
        k = it.get("kind", "?")
        kinds.setdefault(k, {}).setdefault(subgroup(it), []).append(it)
    out = []
    for k, groups in kinds.items():
        out.append({"kind": k, "label": KIND_LABEL.get(k, k), "bulk": k in BULK_OK,
                    "groups": [{"name": g, "items": groups[g]} for g in sorted(groups)]})
    order = list(KIND_LABEL)
    out.sort(key=lambda d: (order.index(d["kind"]) if d["kind"] in order else 99, d["label"]))
    return out


def decide_many(ids: list, approve: bool, reason: str = "") -> dict:
    """Decide several items; refuses (does nothing) if any of them may not be
    decided in bulk. Returns {"done": [...], "failed": {id: error}}."""
    items = [store().get(i) for i in ids]
    if len(ids) > 1:
        bad = [i["id"] for i in items if i and not bulk_allowed(i)]
        if bad:
            raise ValueError(f"{ONE_BY_ONE_REASON}: {', '.join(bad)}")
    done, failed = [], {}
    for i in ids:
        try:
            store().decide(i, approve, reason or ("grupna odluka" if len(ids) > 1 else ""))
            done.append(i)
        except Exception as e:                          # noqa: BLE001 — reported per item
            failed[i] = str(e)[:200]
    return {"done": done, "failed": failed}


def detail_md(item: dict) -> str:
    """Everything about one item (the full abstract included), SR or EN."""
    from ..i18n import lang, tr
    p = item.get("payload") or {}
    L = [f"### {title_of(item)}", "",
         tr("**{0}** · predložio: {1}").format(tr(KIND_LABEL.get(item["kind"], item["kind"])),
                                              item.get("proposer", ""))
         + ("" if bulk_allowed(item) else f" · _{tr(ONE_BY_ONE_REASON)}_"), ""]
    if p.get("abstract"):
        L += [tr("**Sažetak:**"), "", p["abstract"], ""]
    if p.get("ref"):
        L.append(tr("**Izvor:** `{0}`").format(p["ref"]))
    if item["kind"] == "doctor-measure":
        f = p.get("finding") or {}
        labels = p.get("labels_en" if lang() == "en" else "labels_sr") or f.get("triggers") or []
        L += [tr("**Jedinica:** {0} · **mjera:** {1}").format(p.get("unit"), p.get("measure")),
              tr("**Zašto:** {0}").format(_why(p)),
              tr("**Okidači:** {0}").format(", ".join(labels))]
    if item["kind"] == "doctor-review":
        old, new = p.get("old") or {}, p.get("new") or {}
        L += [tr("**Jedinica:** {0}").format(p.get("unit")),
              tr("**Bilo (stara pravila):** atraktor {0} — {1}").format(
                  old.get("attractor", "?"), old.get("why", "")),
              tr("**Sada (pravila {0}):** atraktor {1}, okreta {2}, poteza sa AI čitačem {3}").format(
                  p.get("rules_version"), new.get("attractor"), new.get("turns"), new.get("moves")),
              tr("**Odobri** = mjera se ukida i jedinica odmrzava · **Ne odobri** = mjera ostaje.")]
    res = p.get("result") or {}
    if res.get("computed_B") is not None:
        L.append(tr("**Reprodukcija:** naš B*={0:.12f}, rad {1}, razlika {2:.1e}").format(
            res["computed_B"], res.get("claimed_B"), res.get("error", 0)))
    for k in ("text", "reason", "summary", "command", "path"):
        if p.get(k):
            L.append(f"**{k}:** {str(p[k])[:2000]}")
    return "\n\n".join(x for x in L if x is not None)
