"""
The interactive Lab plot (round 3, item 29, step 6): the lab's plots move from a
static PNG to the same kind of view as the Grafovi tab — zoom (wheel, + / −),
move up/down/left/right (drag, arrow keys — Shift = bigger step, ◀ ▲ ▼ ▶),
⌂ = reset, the value under the mouse, ⤢ = spread. The PNG is kept: every run still
writes it (cards link to it), and "Sačuvaj PNG" saves the current view (also SVG, CSV).
Old runs without stored specs fall back to their PNG.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QLabel, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..i18n import tr
from ..lab import plots as PL
from .widgets import button, flow_row

BG, AX, GRID, TXT, MUTED = "#12151d", "#171b25", "#262d3a", "#e9ecf3", "#9aa4b5"
PAN_STEP, PAN_BIG = 0.10, 0.40


class SeriesCanvas(FigureCanvasQTAgg):
    hovered = Signal(str)

    def __init__(self, parent=None):
        self.fig = Figure(facecolor=BG, layout="constrained")
        super().__init__(self.fig)
        self.setParent(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.ax = self.fig.add_subplot(111)
        self._home = None
        self._drag = None
        self.spec: dict = {}
        self.series: dict = {}
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("button_release_event", lambda ev: setattr(self, "_drag", None))
        self.mpl_connect("motion_notify_event", self._on_motion)

    def show_spec(self, spec: dict, series: dict):
        from .widgets import _BASE_PT
        self.spec, self.series = spec, series
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(AX)
        fs = max(7.0, _BASE_PT[0] * 0.62)
        PL.draw(self.ax, spec, series, self.fig, fs)
        PL.style(self.ax, spec, fs, dark=True)
        for s in self.ax.spines.values():
            s.set_color(GRID)
        leg = self.ax.get_legend()
        if leg is not None:
            leg.get_frame().set_facecolor(AX)
            for t in leg.get_texts():
                t.set_color(TXT)
        self._home = (self.ax.get_xlim(), self.ax.get_ylim())
        self.draw_idle()

    # ---- navigation (same keys and buttons as the Grafovi tab) -------- #
    def pan(self, fx: float, fy: float):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        self.ax.set_xlim(x0 + (x1 - x0) * fx, x1 + (x1 - x0) * fx)
        self.ax.set_ylim(y0 + (y1 - y0) * fy, y1 + (y1 - y0) * fy)
        self.draw_idle()

    def zoom(self, factor: float, cx: Optional[float] = None, cy: Optional[float] = None):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        cx = (x0 + x1) / 2 if cx is None else cx
        cy = (y0 + y1) / 2 if cy is None else cy
        self.ax.set_xlim(cx + (x0 - cx) * factor, cx + (x1 - cx) * factor)
        self.ax.set_ylim(cy + (y0 - cy) * factor, cy + (y1 - cy) * factor)
        self.draw_idle()

    def home(self):
        if self._home:
            self.ax.set_xlim(*self._home[0])
            self.ax.set_ylim(*self._home[1])
            self.draw_idle()

    def keyPressEvent(self, ev):
        big = PAN_BIG if ev.modifiers() & Qt.ShiftModifier else PAN_STEP
        moves = {Qt.Key_Left: (-big, 0), Qt.Key_Right: (big, 0),
                 Qt.Key_Up: (0, big), Qt.Key_Down: (0, -big)}
        k = ev.key()
        if k in moves:
            self.pan(*moves[k])
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(0.8)
        elif k == Qt.Key_Minus:
            self.zoom(1.25)
        elif k == Qt.Key_Home:
            self.home()
        else:
            super().keyPressEvent(ev)

    def _on_scroll(self, ev):
        if ev.xdata is not None:
            self.zoom(0.85 if ev.button == "up" else 1 / 0.85, ev.xdata, ev.ydata)

    def _on_press(self, ev):
        self.setFocus()
        if ev.inaxes is self.ax and ev.button == 1:
            self._drag = (ev.x, ev.y, self.ax.get_xlim(), self.ax.get_ylim())

    def _on_motion(self, ev):
        if self._drag is not None and ev.x is not None:
            x0p, y0p, (xa, xb), (ya, yb) = self._drag
            w, h = self.ax.bbox.width, self.ax.bbox.height
            dx, dy = (ev.x - x0p) / w * (xb - xa), (ev.y - y0p) / h * (yb - ya)
            self.ax.set_xlim(xa - dx, xb - dx)
            self.ax.set_ylim(ya - dy, yb - dy)
            self.draw_idle()
            return
        if ev.inaxes is not self.ax or ev.xdata is None:
            return
        best = None
        for ln in self.ax.get_lines():
            xs, ys = (np.asarray(a, float) for a in ln.get_data())
            if xs.size == 0 or xs.ndim != 1:
                continue
            pts = self.ax.transData.transform(np.column_stack([xs, ys]))
            d = np.hypot(pts[:, 0] - ev.x, pts[:, 1] - ev.y)
            d[~np.isfinite(d)] = np.inf
            k = int(np.argmin(d))
            if d[k] < 12 and (best is None or d[k] < best[0]):
                best = (d[k], ln.get_label(), xs[k], ys[k])
        if best:
            lab = "" if str(best[1]).startswith("_") else f"{best[1]} · "
            self.hovered.emit(f"{lab}x = {best[2]:.10g}, y = {best[3]:.10g}")
        else:
            self.hovered.emit(f"x = {ev.xdata:.6g}, y = {ev.ydata:.6g}")

    def visible_rows(self) -> list:
        x0, x1 = self.ax.get_xlim()
        out = []
        for ln in self.ax.get_lines():
            xs, ys = (np.asarray(a, float) for a in ln.get_data())
            if xs.ndim != 1:
                continue
            lab = ln.get_label()
            for x, y in zip(xs, ys):
                if x0 <= x <= x1:
                    out.append([lab, repr(float(x)), repr(float(y))])
        return out


class LabPlotView(QWidget):
    """Interactive plot area of the Lab tab (falls back to the PNG for old runs)."""
    expand = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.which = QComboBox()
        self.which.currentIndexChanged.connect(self._show_current)
        self.canvas = SeriesCanvas()
        c = self.canvas
        self.b_expand = button("⤢", self.expand.emit)
        v.addWidget(flow_row(
            QLabel(tr("graf:")), self.which,
            button("◀", lambda: c.pan(-PAN_STEP, 0)), button("▲", lambda: c.pan(0, PAN_STEP)),
            button("▼", lambda: c.pan(0, -PAN_STEP)), button("▶", lambda: c.pan(PAN_STEP, 0)),
            button("+", lambda: c.zoom(0.8)), button("−", lambda: c.zoom(1.25)), button("⌂", c.home),
            button(tr("Sačuvaj PNG"), lambda: self.save("png")), button(tr("SVG"), lambda: self.save("svg")),
            button(tr("CSV"), self.save_csv), self.b_expand))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.canvas)
        self.png = QLabel()
        self.png.setAlignment(Qt.AlignCenter)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.png)
        self.stack.addWidget(sc)
        v.addWidget(self.stack, 1)
        self.hover = QLabel("")
        self.hover.setStyleSheet(f"color:{MUTED};")
        v.addWidget(self.hover)
        self.canvas.hovered.connect(self.hover.setText)
        self._rec: dict = {}
        self._dir: Optional[Path] = None
        self.clear()                                    # dark and empty until the first run

    def show_record(self, rec: dict, run_dir: Path):
        self._rec, self._dir = rec, Path(run_dir)
        specs = rec.get("plot_specs") or []
        self.which.blockSignals(True)
        self.which.clear()
        if specs:
            for i, sp in enumerate(specs):
                self.which.addItem(sp.get("title") or f"graf {i + 1}", i)
        else:
            for i, name in enumerate(rec.get("plots") or []):
                self.which.addItem(name, i)
        self.which.blockSignals(False)
        self._show_current()

    def clear(self):
        self._rec = {}
        self.which.clear()
        self.canvas.fig.clear()
        self.canvas.ax = self.canvas.fig.add_subplot(111)
        ax = self.canvas.ax
        ax.set_facecolor(AX)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.text(0.5, 0.5, tr("graf se pojavi posle pokretanja eksperimenta"), transform=ax.transAxes,
                ha="center", va="center", color=MUTED)
        self.canvas.draw_idle()
        self.png.clear()

    def _show_current(self):
        i = self.which.currentData()
        if i is None:
            return
        specs = self._rec.get("plot_specs") or []
        if specs:
            self.stack.setCurrentWidget(self.canvas)
            self.canvas.show_spec(specs[i], self._rec.get("series") or {})
        else:                                           # an older run: only its PNG exists
            self.stack.setCurrentIndex(1)
            names = self._rec.get("plots") or []
            if self._dir and i < len(names):
                pm = QPixmap(str(self._dir / names[i]))
                if not pm.isNull():
                    self.png.setPixmap(pm.scaledToWidth(min(760, pm.width()), Qt.SmoothTransformation))

    def save(self, fmt: str, path: Optional[str] = None) -> Optional[str]:
        """Save the CURRENT view (zoomed/moved as you see it) as PNG or SVG."""
        name = f"{self._rec.get('run_id', 'lab')}.{fmt}"
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, tr("Sačuvaj graf"), name, f"*.{fmt}")
        if not path:
            return None
        if self.stack.currentWidget() is self.canvas:
            self.canvas.fig.savefig(path, format=fmt, facecolor=BG)
        else:
            pm = self.png.pixmap()
            if pm is not None:
                pm.save(path)
        return path

    def save_csv(self, path: Optional[str] = None) -> Optional[str]:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, tr("Izvezi podatke"),
                                                  f"{self._rec.get('run_id', 'lab')}.csv", "*.csv")
        if not path:
            return None
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["series", "x", "y"])
            w.writerows(self.canvas.visible_rows())
        return path
