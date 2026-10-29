"""
The knowledge graph drawn as nodes and links (round 3, item 30): topics, cards,
methods, missions and ideas; a click on a node opens its card (or, for a mission /
method / idea, shows what it is and highlights its neighbours). Same movement as the
Grafovi tab: wheel / + / − zoom, drag / arrows / ◀ ▲ ▼ ▶ move, ⌂ resets.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..graphs import knowledge as K
from ..i18n import tr
from .lab_plot import AX, BG, GRID, MUTED, PAN_STEP, TXT, SeriesCanvas
from .widgets import button, flow_row

KIND_LABEL = {"tema": "teme", "kartica": "kartice", "metoda": "metode", "misija": "misije",
              "ideja": "ideje"}


class KnowledgeCanvas(SeriesCanvas):
    node_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes: list = []
        self.edges: list = []
        self.pos: dict = {}
        self.show_kinds = set(K.KINDS)
        self.selected: Optional[str] = None
        self._xy = np.zeros((0, 2))
        self._ids: list = []
        self.mpl_connect("button_release_event", self._on_click)
        self._press_at = None

    def set_graph(self, nodes, edges, pos):
        self.nodes, self.edges, self.pos = nodes, edges, pos
        self.draw_graph(reset=True)

    def draw_graph(self, reset: bool = False):
        from .widgets import _BASE_PT
        xl, yl = self.ax.get_xlim(), self.ax.get_ylim()
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(AX)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for s in self.ax.spines.values():
            s.set_color(GRID)
        fs = max(7.0, _BASE_PT[0] * 0.55)
        vis = [n for n in self.nodes if n["kind"] in self.show_kinds]
        vid = {n["id"] for n in vis}
        near = set(K.neighbours(self.selected, self.edges)) if self.selected else set()
        for a, b, kind in self.edges:
            if a in vid and b in vid:
                (x1, y1), (x2, y2) = self.pos[a], self.pos[b]
                hot = self.selected in (a, b)
                self.ax.plot([x1, x2], [y1, y2], color="#ffc257" if hot else GRID,
                             linewidth=1.6 if hot else 0.8, linestyle=":" if kind == "inspiracija" else "-",
                             zorder=1)
        deg: dict = {}
        for a, b, _k in self.edges:
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
        self._ids = [n["id"] for n in vis]
        self._xy = np.array([self.pos[i] for i in self._ids]).reshape(-1, 2)
        for kind, col in K.KINDS.items():
            ns = [n for n in vis if n["kind"] == kind]
            if not ns:
                continue
            xy = np.array([self.pos[n["id"]] for n in ns])
            sz = [40 + 25 * deg.get(n["id"], 0) for n in ns]
            ec = ["#ffffff" if n["id"] == self.selected else ("#ffc257" if n["id"] in near else BG) for n in ns]
            self.ax.scatter(xy[:, 0], xy[:, 1], s=sz, c=col, edgecolors=ec, linewidths=1.5, zorder=3,
                            label=f"{tr(KIND_LABEL[kind])} ({len(ns)})")
            for n in ns:                                # labels: topics, missions, methods, selection
                if kind in ("tema", "misija", "metoda") or n["id"] == self.selected or n["id"] in near:
                    lone = deg.get(n["id"], 0) == 0
                    cut = 22 if lone else 34                    # lonely rows are tight
                    lab = n["label"] if len(n["label"]) <= cut else n["label"][:cut - 1] + "…"
                    self.ax.annotate(lab, self.pos[n["id"]], xytext=(6, 4), textcoords="offset points",
                                     color=TXT, fontsize=fs, zorder=4)
        leg = self.ax.legend(loc="lower left", fontsize=fs, facecolor=AX, edgecolor=GRID, labelcolor=TXT,
                             markerscale=0.6)
        leg.set_draggable(True)
        if reset or self._home is None:
            self.ax.set_xlim(-1.25, 1.25)
            self.ax.set_ylim(-1.2, 1.2)
            self._home = (self.ax.get_xlim(), self.ax.get_ylim())
        else:
            self.ax.set_xlim(*xl)
            self.ax.set_ylim(*yl)
        self.draw_idle()

    def node_at(self, ev, px: float = 14.0) -> Optional[dict]:
        if ev.x is None or len(self._ids) == 0:
            return None
        pts = self.ax.transData.transform(self._xy)
        d = np.hypot(pts[:, 0] - ev.x, pts[:, 1] - ev.y)
        k = int(np.argmin(d))
        if d[k] > px:
            return None
        return next((n for n in self.nodes if n["id"] == self._ids[k]), None)

    def _on_press(self, ev):
        super()._on_press(ev)
        self._press_at = (ev.x, ev.y)

    def _on_click(self, ev):
        if self._press_at is None or ev.x is None:
            return
        moved = abs(ev.x - self._press_at[0]) + abs(ev.y - self._press_at[1]) > 3
        self._press_at = None
        if moved:
            return
        n = self.node_at(ev)
        if n is not None:
            self.selected = n["id"]
            self.draw_graph()
            self.node_clicked.emit(n["id"])

    def _on_motion(self, ev):
        if self._drag is not None:
            return super()._on_motion(ev)
        n = self.node_at(ev)
        if n is None:
            self.hovered.emit("")
            return
        extra = f" · {n['status']}" if n.get("status") else ""
        self.hovered.emit(f"[{tr(n['kind'])}] {n['label']}{extra} — " +
                          (tr("klik = otvori karticu") if n.get("card") else tr("klik = veze")))


class KnowledgeView(QWidget):
    open_card = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.canvas = KnowledgeCanvas()
        c = self.canvas
        self.checks = {}
        boxes = []
        for kind in K.KINDS:
            cb = QCheckBox(tr(KIND_LABEL[kind]))
            cb.setChecked(True)
            cb.toggled.connect(self._filter)
            self.checks[kind] = cb
            boxes.append(cb)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("nađi čvor…"))
        self.search.returnPressed.connect(self._find)
        v.addWidget(flow_row(*boxes, self.search,
                             button("◀", lambda: c.pan(-PAN_STEP, 0)), button("▲", lambda: c.pan(0, PAN_STEP)),
                             button("▼", lambda: c.pan(0, -PAN_STEP)), button("▶", lambda: c.pan(PAN_STEP, 0)),
                             button("+", lambda: c.zoom(0.8)), button("−", lambda: c.zoom(1.25)),
                             button("⌂", c.home), button(tr("PNG"), self._png)))
        v.addWidget(self.canvas, 1)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet(f"color:{MUTED};")
        v.addWidget(self.info)
        self.canvas.hovered.connect(lambda s: self.info.setText(s) if s else None)
        self.canvas.node_clicked.connect(self._clicked)

    def refresh(self):
        nodes, edges = K.build()
        self.canvas.set_graph(nodes, edges, K.positions(nodes, edges))
        self.info.setText(tr("{0} čvorova · {1} veza · nivo veza: iz vaulta, registra metoda, misija i ideja").format(len(nodes), len(edges)))

    def _filter(self):
        self.canvas.show_kinds = {k for k, cb in self.checks.items() if cb.isChecked()}
        self.canvas.draw_graph()

    def _find(self):
        n = K.find(self.canvas.nodes, self.search.text())
        if n is None:
            self.info.setText(tr("nema čvora za „{0}“").format(self.search.text()))
            return
        x, y = self.canvas.pos[n["id"]]
        self.canvas.selected = n["id"]
        self.canvas.draw_graph()
        x0, x1 = self.canvas.ax.get_xlim()
        y0, y1 = self.canvas.ax.get_ylim()
        w, h = (x1 - x0) / 2, (y1 - y0) / 2
        self.canvas.ax.set_xlim(x - w, x + w)
        self.canvas.ax.set_ylim(y - h, y + h)
        self.canvas.draw_idle()
        self._clicked(n["id"], open_card=False)

    def _clicked(self, nid: str, open_card: bool = True):
        n = next((x for x in self.canvas.nodes if x["id"] == nid), None)
        if n is None:
            return
        near = K.neighbours(nid, self.canvas.edges)
        self.info.setText(tr("[{0}] {1} · veze ({2}): {3}").format(
            tr(n["kind"]), n["label"], len(near), ", ".join(near[:8]) + ("…" if len(near) > 8 else "")))
        if open_card and n.get("card"):
            self.open_card.emit(n["card"])

    def _png(self):
        from PySide6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getSaveFileName(self, tr("Sačuvaj graf"), "graf-znanja.png", "*.png")
        if p:
            self.canvas.fig.savefig(p, facecolor=BG)
