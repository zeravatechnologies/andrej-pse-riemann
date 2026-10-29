"""Round 3, item 30: the knowledge graph as nodes and links — topics, cards, methods,
missions, ideas; a click opens the card; deterministic, cached layout."""
from PySide6.QtWidgets import QApplication

from pse_r.graphs import knowledge as K


def _seeded():
    from pse_r.shared_lib import missions as MIS
    from pse_r.vault import qrh_seed as QS, langlands_seed as LS
    if not QS.is_seeded():
        QS.seed_qrh()
    if not LS.is_seeded():
        LS.seed()
    MIS.seed_first()
    MIS.seed_second()


def test_graph_has_every_kind_and_real_links(operator):
    _seeded()
    nodes, edges = K.build()
    kinds = {n["kind"] for n in nodes}
    assert {"tema", "kartica", "metoda", "misija"} <= kinds
    ids = {n["id"] for n in nodes}
    assert all(a in ids and b in ids for a, b, _ in edges)
    # mission 2's transfer map points at its source cards
    assert ("misija:misija-visi-stepen", "izvor-newton-thorne-i", "korak") in edges
    # a method points at the card carrying its source reference
    assert any(a == "metoda:liu" and k == "izvor" for a, b, k in edges)


def test_layout_is_deterministic_cached_and_separates_groups(operator):
    _seeded()
    nodes, edges = K.build()
    p1 = K.packed_layout(nodes, edges)
    p2 = K.packed_layout(nodes, edges)
    assert p1 == p2 and set(p1) == {n["id"] for n in nodes}
    assert all(-1.0001 <= x <= 1.0001 and -1.0001 <= y <= 1.0001 for x, y in p1.values())
    assert K.positions(nodes, edges) == K.positions(nodes, edges)
    groups = K.components(nodes, edges)
    assert len(groups[0]) >= len(groups[-1])


def test_click_opens_card_and_search_finds(operator):
    _seeded()
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.knowledge_view import KnowledgeView
    v = KnowledgeView()
    v.resize(1000, 700)
    v.show()
    v.refresh()
    app.processEvents()
    opened = []
    v.open_card.connect(opened.append)
    v._clicked("izvor-liu-2610-12234")
    assert opened == ["izvor-liu-2610-12234"]
    v._clicked("misija:misija-visi-stepen")                  # a mission has no card: info only
    assert opened == ["izvor-liu-2610-12234"] and "Viši stepen" in v.info.text()
    v.search.setText("newton-thorne-i")
    v._find()
    assert v.canvas.selected == "izvor-newton-thorne-i"
    v.checks["kartica"].setChecked(False)
    assert "kartica" not in v.canvas.show_kinds
    x0 = v.canvas.ax.get_xlim()
    v.canvas.pan(0.1, 0)
    assert v.canvas.ax.get_xlim()[0] > x0[0]
