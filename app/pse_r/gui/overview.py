"""
Pregled (overview) — the first tab, Svarog style: metric tiles, the mission
front, what waits for the operator, and the latest events. Every number here is
ONE read-only SELECT over the SHARED_LIB fact views (shared_lib.views), so the
overview can never say anything the library does not contain.
"""
from __future__ import annotations

from ..i18n import tr

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from .widgets import MarkdownView, button


def _metric(key: str) -> tuple[QFrame, QLabel]:
    f = QFrame()
    f.setObjectName("metric")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 10, 14, 10)
    k = QLabel(key)
    k.setObjectName("metricK")
    val = QLabel("…")
    val.setObjectName("metricV")
    v.addWidget(k)
    v.addWidget(val)
    return f, val


def _card(title: str) -> tuple[QFrame, MarkdownView]:
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 10, 14, 10)
    h = QLabel(title)
    h.setObjectName("cardH")
    v.addWidget(h)
    md = MarkdownView()
    v.addWidget(md, 1)
    return f, md


Q = {
    "kartice": "SELECT COUNT(*) FROM cards",
    "provjerene": "SELECT COUNT(*) FROM cards WHERE status IN ('CITED','COMPUTED')",
    "lab": "SELECT COUNT(*) FROM lab_runs",
    "događaji": "SELECT COUNT(*) FROM events",
    "čeka": "SELECT COUNT(*) FROM pending WHERE status='open'",
    "metode": "SELECT COUNT(*) FROM events WHERE kind='method' AND verdict='accept'",
    "pečati": "SELECT COUNT(*) FROM seals",
    "front": "SELECT MIN(best_B) FROM missions",
}


class OverviewTab(QWidget):
    open_queue = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("<b>Pregled</b> — sve brojke su upiti nad SHARED_LIB-om")))
        top.addStretch(1)
        top.addWidget(button(tr("Osvježi"), self.refresh))
        v.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(11)
        self.vals: dict[str, QLabel] = {}
        labels = [("front", tr("front misije (najniže B)")), ("čeka", tr("čeka tvoju odluku")),
                  ("metode", tr("potvrđene metode")), ("pečati", tr("zapečaćeni izvještaji")),
                  ("kartice", tr("kartice")), ("provjerene", tr("provjerene (CITED/COMPUTED)")),
                  ("lab", tr("lab run-ova")), ("događaji", tr("događaja u dnevniku"))]
        self._tiles = []
        for i, (key, lab) in enumerate(labels):
            f, val = _metric(lab)
            self.vals[key] = val
            self._tiles.append(f)
            grid.addWidget(f, i // 4, i % 4)
        self._grid, self._cols = grid, 4
        v.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(12)
        f1, self.md_queue = _card(tr("Čeka tvoju odluku"))
        f2, self.md_events = _card(tr("Zadnji događaji"))
        row.addWidget(f1, 1)
        row.addWidget(f2, 1)
        v.addLayout(row, 1)
        from .widgets import add_expand                 # ⤢ on both cards
        self._cards = (f1, f2)
        for f in (f1, f2):
            add_expand(f, lambda: [*self._cards, *self._tiles])
        b = button(tr("Otvori red odluka"), self.open_queue.emit, kind="primary")
        v.addWidget(b, 0, Qt.AlignRight)
        self.refresh()

    def resizeEvent(self, ev):
        """Screen fitting: 4 tiles per row when there is room, else 2 (or 1)."""
        super().resizeEvent(ev)
        tile = max(t.minimumSizeHint().width() for t in self._tiles) + self._grid.spacing()
        cols = 4 if self.width() >= 4 * tile + 28 else 2 if self.width() >= 2 * tile + 28 else 1
        if cols != self._cols:
            self._cols = cols
            for t in self._tiles:
                self._grid.removeWidget(t)
            for i, t in enumerate(self._tiles):
                self._grid.addWidget(t, i // cols, i % cols)

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        tile = max(t.minimumSizeHint().width() for t in self._tiles) + self._grid.spacing()
        return QSize(tile + 28, super().minimumSizeHint().height())

    def refresh(self) -> None:
        from ..shared_lib import views as V
        try:
            conn = V.connect()
        except Exception as e:                              # noqa: BLE001
            self.md_events.set_markdown(tr("_činjenični sloj nedostupan: {0}_").format(e))
            return
        try:
            for key, sql in Q.items():
                try:
                    r = V.query(sql, conn=conn)["rows"]
                    val = r[0][0] if r else None
                except V.QueryRefused:
                    val = None
                if key == "front":
                    self.vals[key].setText("—" if val is None else f"{val:.9f}")
                else:
                    self.vals[key].setText("0" if val is None else str(val))
            try:
                q = V.query("SELECT kind, title FROM pending WHERE status='open' "
                            "ORDER BY created LIMIT 8", conn=conn)["rows"]
            except V.QueryRefused:
                q = []
            self.md_queue.set_markdown(
                "\n".join(f"- **{k}** — {t}" for k, t in q) or tr("_ništa ne čeka_"))
            ev = V.query("SELECT time, kind, actor, verdict, subject FROM events "
                         "ORDER BY id DESC LIMIT 12", conn=conn)["rows"]
            self.md_events.set_markdown("\n".join(
                f"- `{t[11:19] if t else ''}` **{k}** · {a} · {vd or ''} {s or ''}"
                for t, k, a, vd, s in ev) or "_prazno_")
        finally:
            conn.close()
