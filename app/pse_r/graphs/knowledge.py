"""
The knowledge graph as nodes and links (round 3, item 30).

Nodes:  tema (topic cards) · kartica (every other vault card) · metoda (the method
        registry) · misija (missions) · ideja (shown / kept INSPIRACIJE)
Links:  link / depends (between cards, from the vault) · izvor (a method → the card
        whose sources hold its reference) · korak (a mission → the card a step
        refers to) · metoda (a mission → a method it recorded) · inspiracija (an idea
        → its mission)

Layout: a deterministic Fruchterman–Reingold in numpy (no networkx in the package);
the same graph always gets the same picture, and positions are cached by a hash of
the graph so nothing jumps between refreshes.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Optional

import numpy as np

KINDS = {"tema": "#ffc257", "kartica": "#86b3ff", "metoda": "#74d79a", "misija": "#f49090",
         "ideja": "#ba68c8"}


def build() -> tuple[list, list]:
    """(nodes, edges). node = {id, label, kind, status, card}; edge = (a, b, kind)."""
    from ..vault import store as VS
    cards, cedges = VS.graph()
    nodes, edges, ids = [], [], set()

    def add(n):
        if n["id"] not in ids:
            ids.add(n["id"])
            nodes.append(n)
    for c in cards:
        add({"id": c["id"], "label": c["title"], "kind": "tema" if c["id"].startswith("tema-") else "kartica",
             "status": c["status"], "card": c["id"], "type": c.get("type", "")})
    edges += [(a, b, k) for a, b, k in cedges]
    # methods → the card that carries their source reference
    src_to_card: dict = {}
    try:
        from ..vault.store import iter_cards
        for c in iter_cards():
            for s in c.sources:
                src_to_card.setdefault(s.lower(), c.id)
    except Exception:                                   # noqa: BLE001
        pass
    try:
        from ..methods import registry as R
        for m in R.KNOWN:
            mid = f"metoda:{m.name}"
            add({"id": mid, "label": f"metoda {m.name}", "kind": "metoda", "status": "",
                 "card": src_to_card.get((m.source or "").lower(), ""), "type": "metoda"})
            cid = src_to_card.get((m.source or "").lower())
            if cid:
                edges.append((mid, cid, "izvor"))
    except Exception:                                   # noqa: BLE001
        pass
    # missions → cards their steps refer to, and methods they recorded
    try:
        from ..shared_lib import missions as MIS
        for m in MIS.all_missions():
            mid = f"misija:{m['id']}"
            add({"id": mid, "label": m["title"], "kind": "misija", "status": "", "card": "",
                 "type": "misija", "mission": m["id"]})
            for st in (MIS.get(m["id"]) or {}).get("steps", []):
                ref = (st.get("ref") or "").strip()
                if ref in ids:
                    edges.append((mid, ref, "korak"))
                elif ref and f"metoda:{ref}" in ids:
                    edges.append((mid, f"metoda:{ref}", "metoda"))
                elif ref.lower() in src_to_card:
                    edges.append((mid, src_to_card[ref.lower()], "korak"))
                # missions.record_method writes "uvezena i potvrđena metoda NAME (B*=…)"
                mm = re.search(r"metoda (\S+) \(B\*", st.get("action", ""))
                if mm and f"metoda:{mm.group(1)}" in ids:
                    edges.append((mid, f"metoda:{mm.group(1)}", "metoda"))
    except Exception:                                   # noqa: BLE001
        pass
    # ideas the operator sees or kept → their mission
    try:
        from ..shared_lib import ideas as IDEAS
        from ..shared_lib.store import store
        IDEAS._ensure()
        for r in store().rows("SELECT id, title, mission_id, status, source_ref FROM inspiracije "
                              "WHERE status IN ('prikazana', 'zadržana', 'pitanje')"):
            iid = f"ideja:{r['id']}"
            add({"id": iid, "label": r["title"], "kind": "ideja", "status": r["status"], "card": "",
                 "type": "ideja"})
            if f"misija:{r['mission_id']}" in ids:
                edges.append((iid, f"misija:{r['mission_id']}", "inspiracija"))
            cid = src_to_card.get((r["source_ref"] or "").lower())
            if cid:
                edges.append((iid, cid, "izvor"))
    except Exception:                                   # noqa: BLE001
        pass
    edges = list(dict.fromkeys((a, b, k) for a, b, k in edges if a in ids and b in ids and a != b))
    return nodes, edges


def layout(nodes: list, edges: list, iters: int = 300, seed: int = 7) -> dict:
    """Deterministic Fruchterman–Reingold; returns {id: (x, y)} in [-1, 1]²."""
    n = len(nodes)
    if n == 0:
        return {}
    idx = {nd["id"]: i for i, nd in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    # start on a circle ordered by kind, so the result is stable and readable
    order = sorted(range(n), key=lambda i: (list(KINDS).index(nodes[i]["kind"]), nodes[i]["id"]))
    pos = np.zeros((n, 2))
    for r, i in enumerate(order):
        a = 2 * math.pi * r / n
        pos[i] = (math.cos(a), math.sin(a))
    pos += rng.normal(0, 0.01, pos.shape)
    E = np.array([(idx[a], idx[b]) for a, b, _ in edges], dtype=int).reshape(-1, 2)
    k = math.sqrt(4.0 / n)
    t = 0.2
    for _ in range(iters):
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(d, axis=-1) + 1e-9
        rep = (k * k / dist ** 2)[:, :, None] * d
        np.fill_diagonal(rep[:, :, 0], 0)
        np.fill_diagonal(rep[:, :, 1], 0)
        disp = rep.sum(axis=1)
        if len(E):
            de = pos[E[:, 0]] - pos[E[:, 1]]
            le = np.linalg.norm(de, axis=1)[:, None] + 1e-9
            att = de * le / k
            np.add.at(disp, E[:, 0], -att)
            np.add.at(disp, E[:, 1], att)
        disp -= 0.02 * pos                              # gentle gravity keeps islands in view
        ln = np.linalg.norm(disp, axis=1)[:, None] + 1e-9
        pos += disp / ln * np.minimum(ln, t)
        t *= 0.985
    pos -= pos.mean(axis=0)
    pos /= (np.abs(pos).max() or 1.0)
    return {nd["id"]: (float(pos[i, 0]), float(pos[i, 1])) for i, nd in enumerate(nodes)}


def components(nodes: list, edges: list) -> list:
    """Connected groups of node ids, biggest first (union–find)."""
    parent = {n["id"]: n["id"] for n in nodes}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, _k in edges:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
    groups: dict = {}
    for n in nodes:
        groups.setdefault(root(n["id"]), []).append(n["id"])
    return sorted(groups.values(), key=lambda g: (-len(g), sorted(g)[0]))


def packed_layout(nodes: list, edges: list) -> dict:
    """Each connected group laid out on its own, groups packed side by side by size,
    and the lonely nodes (no link at all) in a tidy row at the bottom — so a few
    unlinked cards cannot squash everything else into the middle."""
    by_id = {n["id"]: n for n in nodes}
    groups = components(nodes, edges)
    linked = [g for g in groups if len(g) > 1]
    lonely = [g[0] for g in groups if len(g) == 1]
    out: dict = {}
    x = 0.0
    row_h = 0.0
    for g in linked:
        gs = set(g)
        sub_n = [by_id[i] for i in g]
        sub_e = [e for e in edges if e[0] in gs and e[1] in gs]
        pos = layout(sub_n, sub_e)
        r = 0.35 + 0.18 * math.sqrt(len(g))             # bigger groups get more room
        for i, (px, py) in pos.items():
            out[i] = (x + r + px * r, py * r)
        x += 2 * r + 0.25
        row_h = max(row_h, r)
    width = max(x - 0.25, 2.0)
    if lonely:
        cols = max(1, min(5, int(math.ceil(math.sqrt(len(lonely))))))   # room for the labels
        for k, i in enumerate(sorted(lonely, key=lambda i: (by_id[i]["kind"], i))):
            cx = (k % cols + 0.5) / cols * width
            cy = -row_h - 0.35 - 0.22 * (k // cols)
            out[i] = (cx, cy)
    xs = np.array([p[0] for p in out.values()])
    ys = np.array([p[1] for p in out.values()])
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    sc = max(xs.max() - xs.min(), ys.max() - ys.min(), 1e-9) / 2
    return {i: ((p[0] - cx) / sc, (p[1] - cy) / sc) for i, p in out.items()}


def graph_hash(nodes: list, edges: list) -> str:
    blob = json.dumps([sorted(n["id"] for n in nodes), sorted(edges)], ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def positions(nodes: list, edges: list) -> dict:
    """Cached by the graph's hash (SHARED_LIB kv) — the picture never jumps."""
    from ..shared_lib.store import store
    h = graph_hash(nodes, edges)
    cache = store().kv_get("kg_layout") or {}
    if cache.get("hash") == h:
        return {k: tuple(v) for k, v in cache["pos"].items()}
    pos = packed_layout(nodes, edges)
    store().kv_set("kg_layout", {"hash": h, "pos": pos})
    return pos


def neighbours(node_id: str, edges: list) -> list:
    return sorted({b for a, b, _ in edges if a == node_id} | {a for a, b, _ in edges if b == node_id})


def find(nodes: list, query: str) -> Optional[dict]:
    q = (query or "").strip().lower()
    if not q:
        return None
    for n in nodes:
        if q == n["id"].lower():
            return n
    return next((n for n in nodes if q in n["label"].lower() or q in n["id"].lower()), None)
