"""
The Grafovi tab (round 3, item 29) — modelled on "Calculus Tools" (Andrej): three
parts side by side on a computer screen,

    Funkcije      the functions (unlimited, each its own colour) + parameter sliders
    Grafovi       the plot: dark, zoom (wheel, + / −), move up/down/left/right
                  (drag, arrow keys — Shift = bigger step, ◀ ▲ ▼ ▶), ⌂ = reset;
                  the mouse shows everything known about the point under it
    Kalkulacije   "sve o tački" for the clicked point + calculations on demand:
                  cheap ones at once, expensive ones only offered with an estimate,
                  run in the background with "Prekini"

"⤢" spreads the plot over the whole tab (and back). Every plot is stamped with the
levels of what it shows (RAD / NAŠE-NERECENZIRANO / KORISNIK). Export: PNG, SVG, CSV.
The guide is docs/VODIC-GRAFOVI-SR.md ("?").
"""
from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGridLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QSlider,
                               QSplitter, QVBoxLayout, QWidget)

from ..graphs import compute as C
from ..graphs import fexpr as FX
from ..graphs import functions as F
from ..i18n import tr
from .widgets import MarkdownView, button, flow_row

BG, AX, GRID, TXT, MUTED = "#12151d", "#171b25", "#262d3a", "#e9ecf3", "#9aa4b5"
SLIDERS = {  # name: (label, lo, hi)
    "l": ("ℓ", 0.0, 0.3), "b": ("b", 0.0, 0.3), "k": ("κ", 0.5, 1.0), "t": ("t", 0.0, 1.0),
    "w": ("w", 0.0, 0.25), "d": ("d", 1.0, 4.0), "low": ("niska strana", 0.0, 0.3),
    "delta": ("Δ", 0.0, 0.3)}
PAN_STEP, PAN_BIG = 0.10, 0.40


def _base_pt() -> float:
    from .widgets import _BASE_PT
    return _BASE_PT[0]


def _samples() -> int:
    try:
        from .. import machine as MC
        return 300 if MC.profile().key == "acer" else 600
    except Exception:                                   # noqa: BLE001
        return 500


class _Bridge(QObject):
    """Worker threads → GUI thread."""
    job_done = Signal(str, dict)
    coarse_done = Signal()


# --------------------------------------------------------------------------- #
# the plot
# --------------------------------------------------------------------------- #
class GraphCanvas(FigureCanvasQTAgg):
    hovered = Signal(str)
    clicked = Signal(str, float)          # function id, x            (curves)
    clicked_xy = Signal(str, float, float)  # function id, x, y       (paths, polar, field)
    card = Signal(str)

    def __init__(self, parent=None):
        self.fig = Figure(facecolor=BG, layout="constrained")   # tick labels never clipped
        super().__init__(self.fig)
        self.setParent(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.ax = self.fig.add_subplot(111)
        self.funcs: list = []
        self.params: dict = dict(F.PARAMS)
        self.show_targets = True
        self.show_walls = True
        self.home_view = ((0.0, 0.3), (0.80, 0.95))
        self._drag = None
        self._moved = False
        self._lines: dict = {}            # fid -> (xs, ys)
        self._coarse: dict = {}           # (fid, params) -> (xs, ys) for expensive builtins
        self._pending: set = set()
        self.bridge = _Bridge()
        self.bridge.coarse_done.connect(self.redraw)
        self.ax.set_xlim(*self.home_view[0])
        self.ax.set_ylim(*self.home_view[1])
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self._annot = None
        self.mode = "cartesian"
        self.color_by = ""                # 4th dimension: colour a surface by another one
        self.anim_param = "w"             # 5th dimension: slider for animation / small multiples
        self.axes: list = []
        self.ax2 = None
        self._cgrid = None                # (f, extent, W) of the complex view
        self.shade = None                 # (fid, gid, a, b) after an "area" calculation
        self._field = None                # (f, X, Y, Z) of the field mode

    # ---- navigation -------------------------------------------------- #
    def pan(self, fx: float, fy: float) -> None:
        """Move the view by a fraction of its width/height (+x right, +y up);
        in 3D the same buttons rotate the surface."""
        if self.mode == "3d":
            self.ax.view_init(elev=self.ax.elev + 90 * fy, azim=self.ax.azim + 90 * fx)
            self.draw_idle()
            return
        if self.mode in ("multiples", "parallel"):
            return
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        dx, dy = (x1 - x0) * fx, (y1 - y0) * fy
        self.ax.set_xlim(x0 + dx, x1 + dx)
        self.ax.set_ylim(y0 + dy, y1 + dy)
        self.redraw()

    def zoom(self, factor: float, cx: Optional[float] = None, cy: Optional[float] = None) -> None:
        if self.mode in ("3d", "multiples", "parallel"):
            return
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        cx = (x0 + x1) / 2 if cx is None else cx
        cy = (y0 + y1) / 2 if cy is None else cy
        self.ax.set_xlim(cx + (x0 - cx) * factor, cx + (x1 - cx) * factor)
        self.ax.set_ylim(cy + (y0 - cy) * factor, cy + (y1 - cy) * factor)
        self.redraw()

    def home(self) -> None:
        if self.mode in ("3d", "multiples", "parallel"):
            self._layout({"3d": "3d", "multiples": "multi"}.get(self.mode, "one"))
            if hasattr(self.ax, "view_init"):
                self.ax.view_init(elev=30, azim=-60)
            self.redraw()
            return
        self.ax.set_xlim(*self.home_view[0])
        self.ax.set_ylim(*self.home_view[1])
        self.redraw()

    def keyPressEvent(self, ev):
        big = PAN_BIG if ev.modifiers() & Qt.ShiftModifier else PAN_STEP
        k = ev.key()
        if self.mode == "3d" and k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 30 if ev.modifiers() & Qt.ShiftModifier else 10     # arrows rotate in 3D
            az, el = self.ax.azim, self.ax.elev
            az += {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0)
            el += {Qt.Key_Up: step, Qt.Key_Down: -step}.get(k, 0)
            self.ax.view_init(elev=el, azim=az)
            self.draw_idle()
            return
        moves = {Qt.Key_Left: (-big, 0), Qt.Key_Right: (big, 0),
                 Qt.Key_Up: (0, big), Qt.Key_Down: (0, -big)}
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
        if self.mode in ("3d", "multiples", "parallel") or ev.xdata is None:
            return
        self.zoom(0.85 if ev.button == "up" else 1 / 0.85, ev.xdata, ev.ydata)

    def _on_press(self, ev):
        self.setFocus()
        if self.mode in ("3d", "multiples", "parallel"):
            return                                    # 3D: matplotlib rotates with the mouse
        if ev.inaxes is not self.ax or ev.button != 1:
            return
        if ev.dblclick:
            hit = self.nearest(ev)
            if hit and hit[0].card:
                self.card.emit(hit[0].card)
            return
        self._drag = (ev.x, ev.y, self.ax.get_xlim(), self.ax.get_ylim())
        self._moved = False

    def _on_release(self, ev):
        drag, self._drag = self._drag, None
        if drag is None or self._moved or ev.xdata is None:
            return
        if self.mode == "field" and self._field is not None:
            self.clicked_xy.emit(self._field[0].id, float(ev.xdata), float(ev.ydata))
            return
        if self.mode == "complex" and self._cgrid is not None and ev.inaxes is self.ax:
            self.clicked_xy.emit(self._cgrid[0].id, float(ev.xdata), float(ev.ydata))
            return
        hit = self.nearest(ev)
        if not hit:
            return
        f, x, y = hit
        if F.shape(f) == "curve":
            self.clicked.emit(f.id, x)
        else:
            self.clicked_xy.emit(f.id, x, y)

    def _on_motion(self, ev):
        if self.mode in ("3d", "multiples", "parallel"):
            if self.mode == "parallel" and ev.inaxes is self.ax and ev.ydata is not None:
                self._hover_parallel(ev)
            return
        if self._drag is not None and ev.x is not None:
            x0p, y0p, (xa, xb), (ya, yb) = self._drag
            if abs(ev.x - x0p) + abs(ev.y - y0p) > 3:
                self._moved = True
            w, h = self.ax.bbox.width, self.ax.bbox.height
            dx = (ev.x - x0p) / w * (xb - xa)
            dy = (ev.y - y0p) / h * (yb - ya)
            self.ax.set_xlim(xa - dx, xb - dx)
            self.ax.set_ylim(ya - dy, yb - dy)
            self.redraw(fast=True)
            return
        if ev.inaxes is not self.ax:
            return
        if self.mode == "field" and self._field is not None:
            f, X, Y, Z = self._field
            i = int(np.clip(np.searchsorted(Y[:, 0], ev.ydata), 0, Z.shape[0] - 1))
            j = int(np.clip(np.searchsorted(X[0], ev.xdata), 0, Z.shape[1] - 1))
            self.hovered.emit(tr("{0} · ({1:.6g}, {2:.6g}) · vrijednost ≈ {3:.6g} · {4} — klik = sve o tački")
                              .format(f.label, ev.xdata, ev.ydata, Z[i, j], f.level))
            return
        if self.mode == "complex" and self._cgrid is not None:
            f, (x0, x1, y0, y1), W = self._cgrid
            j = int(np.clip((ev.xdata - x0) / (x1 - x0) * (W.shape[1] - 1), 0, W.shape[1] - 1))
            i = int(np.clip((ev.ydata - y0) / (y1 - y0) * (W.shape[0] - 1), 0, W.shape[0] - 1))
            w = W[i, j]
            self.hovered.emit(tr("s = {0:.6g} + {1:.6g}i · f(s) ≈ {2:.4g} · |f| ≈ {3:.4g} · arg ≈ {4:+.3f} — klik = sve o tački")
                              .format(ev.xdata, ev.ydata, w, abs(w), float(np.angle(w))))
            return
        hit = self.nearest(ev)
        if hit is None:
            self.hovered.emit(tr("x = {0:.6g}, y = {1:.6g}").format(ev.xdata, ev.ydata))
            return
        f, x, y = hit
        tgt = C.nearest_target(y)
        self.hovered.emit(tr("{0} · ({1:.9g}, {2:.9g}) · {3} · najbliži cilj {4} (Δ {5:.3g}) — klik = sve o tački")
                          .format(f.label, x, y, f.level, tgt[0], tgt[2]))

    def nearest(self, ev, px: float = 12.0):
        """The drawn curve/path point nearest to the mouse (within px pixels): (f, x, y)."""
        if ev.xdata is None:
            return None
        best = None
        by_id = {f.id: f for f in self.funcs}
        for fid, (xs, ys) in self._lines.items():
            f = by_id.get(fid)
            if f is None or len(xs) == 0:
                continue
            pts = self.ax.transData.transform(np.column_stack([xs, ys]))
            d = np.hypot(pts[:, 0] - ev.x, pts[:, 1] - ev.y)
            d[~np.isfinite(d)] = np.inf
            k = int(np.argmin(d))
            if d[k] <= px and (best is None or d[k] < best[0]):
                best = (float(d[k]), f, float(xs[k]), float(ys[k]))
        return None if best is None else best[1:]

    def _style(self):
        fs = max(7.0, _base_pt() * 0.62)
        ax = self.ax
        ax.set_facecolor(AX)
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=fs)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.9)
        return fs

    def _sample(self, f: F.Function, x0: float, x1: float):
        # built-ins are code with a domain; typed functions are drawn over the whole view
        lo, hi = (max(x0, f.domain[0]), min(x1, f.domain[1])) if f.kind == "builtin" else (x0, x1)
        if hi <= lo:
            return np.array([]), np.array([])
        n = _samples()
        cost = F.eval_cost(f, self.params) * n
        if f.kind == "builtin" and cost > C.CHEAP_S:
            key = (f.id, tuple(sorted(self.params.items())))
            if key in self._coarse:
                return self._coarse[key]
            if key not in self._pending:
                self._pending.add(key)
                k = F.BUILTINS[f.builtin].get("coarse", 9)
                dom = tuple(f.domain)

                def work():
                    xs = np.linspace(dom[0], dom[1], k)
                    try:
                        ys = np.asarray(F.numeric(f, self.params)(xs), float)
                    except Exception:                   # noqa: BLE001
                        ys = np.full(k, np.nan)
                    self._coarse[key] = (xs, ys)
                    self._pending.discard(key)
                    self.bridge.coarse_done.emit()
                threading.Thread(target=work, name="grafovi-coarse", daemon=True).start()
            return np.array([]), np.array([])
        xs = np.linspace(lo, hi, n)
        try:
            ys = np.asarray(F.numeric(f, self.params)(xs), dtype=float)
        except Exception:                               # noqa: BLE001
            ys = np.full(n, np.nan)
        return xs, ys

    def _bg(self, key, fn):
        """Expensive work in the background, once per key; None until it is ready."""
        if key in self._coarse:
            return self._coarse[key]
        if key not in self._pending:
            self._pending.add(key)

            def work():
                try:
                    self._coarse[key] = fn()
                except Exception:                       # noqa: BLE001
                    self._coarse[key] = None
                self._pending.discard(key)
                self.bridge.coarse_done.emit()
            threading.Thread(target=work, name="grafovi-bg", daemon=True).start()
        return None

    def _draw_curves(self, xl, levels, waiting):
        for f in self.funcs:
            if not f.visible or F.shape(f) != "curve":
                continue
            xs, ys = self._sample(f, *xl)
            if len(xs) == 0:
                if any(k[0] == f.id for k in self._pending):
                    waiting.append(f.label)
                continue
            self._lines[f.id] = (xs, ys)
            self.ax.plot(xs, ys, color=f.color, linewidth=1.8, label=f.label,
                         marker="o" if len(xs) < 30 else None, markersize=3)
            levels.add(f.level)

    def _draw_paths(self, levels, waiting):
        for f in self.funcs:
            if not f.visible or F.shape(f) != "path":
                continue
            lo, hi = float(f.domain[0]), float(f.domain[1])
            if f.kind == "builtin":
                k = F.BUILTINS[f.builtin].get("coarse", 7)
                res = self._bg((f.id, tuple(sorted(self.params.items()))),
                               lambda f=f, k=k: F.numeric(f, self.params)(np.linspace(lo, hi, k)))
                if res is None:
                    waiting.append(f.label)
                    continue
                xs, ys = (np.asarray(a, float) for a in res)
            else:
                xs, ys = (np.asarray(a, float) for a in F.numeric(f, self.params)(np.linspace(lo, hi, 400)))
            self._lines[f.id] = (xs, ys)
            self.ax.plot(xs, ys, color=f.color, linewidth=1.8, label=f.label,
                         marker="o" if len(xs) < 30 else None, markersize=4)
            if len(xs) > 1:                     # direction of the parameter
                self.ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]),
                                 arrowprops=dict(arrowstyle="->", color=f.color))
            levels.add(f.level)

    def _draw_polar(self, levels):
        for f in self.funcs:
            if not f.visible or F.shape(f) != "polar":
                continue
            lo, hi = float(f.domain[0]), float(f.domain[1])
            if hi - lo < 1e-9 or (lo, hi) == (0.0, 1.0):
                lo, hi = 0.0, 2 * np.pi
            th = np.linspace(lo, hi, 720)
            r = np.asarray(F.numeric(f, self.params)(th), float)
            xs, ys = r * np.cos(th), r * np.sin(th)
            self._lines[f.id] = (xs, ys)
            self.ax.plot(xs, ys, color=f.color, linewidth=1.8, label=f.label)
            levels.add(f.level)
        self.ax.set_aspect("equal", adjustable="datalim")

    def _draw_field(self, xl, yl, levels, fs):
        f = next((g for g in self.funcs if g.visible and F.shape(g) == "surface"), None)
        self._field = None
        if f is None:
            self.ax.text(0.5, 0.5, tr("Vektorsko polje treba vidljivu površ z = f(x, y)\n(npr. ugrađena „max_δ E_Liu nad (ℓ, κ)“)."),
                         transform=self.ax.transAxes, ha="center", va="center", color=MUTED, fontsize=fs)
            return
        n = 40 if _samples() >= 500 else 24
        X, Y = np.meshgrid(np.linspace(*xl, n), np.linspace(*yl, n))
        Z = np.asarray(F.numeric(f, self.params)(X, Y), float)
        self._field = (f, X, Y, Z)
        lim = np.nanmax(np.abs(Z)) or 1.0
        self.ax.contourf(X, Y, Z, levels=24, cmap="RdBu_r", vmin=-lim, vmax=lim, alpha=0.55)
        try:
            cs = self.ax.contour(X, Y, Z, levels=[0.0], colors=["#ffc257"], linewidths=2.0)
            self.ax.clabel(cs, fmt={0.0: "0"}, fontsize=fs * 0.8)
        except Exception:                               # noqa: BLE001 — no zero in view
            pass
        m = max(8, n // 3)
        Xs, Ys = np.meshgrid(np.linspace(*xl, m), np.linspace(*yl, m))
        h = 1e-4 * max(xl[1] - xl[0], yl[1] - yl[0])
        fn = F.numeric(f, self.params)
        gx = (np.asarray(fn(Xs + h, Ys), float) - np.asarray(fn(Xs - h, Ys), float)) / (2 * h)
        gy = (np.asarray(fn(Xs, Ys + h), float) - np.asarray(fn(Xs, Ys - h), float)) / (2 * h)
        # arrows: steepest DESCENT (toward the method passing), scaled to the axes
        # direction −∇f in data coordinates, drawn with a fixed on-screen length
        sx, sy = (xl[1] - xl[0]), (yl[1] - yl[0])
        un, vn = -gx / sx, -gy / sy
        nrm = np.hypot(un, vn)
        nrm[~np.isfinite(nrm) | (nrm == 0)] = 1.0
        L = 0.45 / m
        self.ax.quiver(Xs, Ys, un / nrm * sx * L, vn / nrm * sy * L, color=TXT, alpha=0.8,
                       angles="xy", scale_units="xy", scale=1, width=0.003)
        self.ax.set_title(tr("strelice: smjer najbržeg pada (prema E ≤ 0); žuto: E = 0 (granica)"),
                          color=MUTED, fontsize=fs * 0.9, loc="left")
        levels.add(f.level)

    def _layout(self, kind: str):
        """one · two (linked) · 3d (rotating) · multi (small multiples, 2×3)."""
        if kind == getattr(self, "_kind", "one"):
            return
        xl, yl = self.ax.get_xlim(), self.ax.get_ylim()
        self.fig.clear()
        self.ax2, self.axes = None, []
        if kind == "two":
            self.ax = self.fig.add_subplot(1, 2, 1)
            self.ax2 = self.fig.add_subplot(1, 2, 2)
        elif kind == "3d":
            self.ax = self.fig.add_subplot(111, projection="3d")
        elif kind == "multi":
            self.axes = [self.fig.add_subplot(2, 3, i + 1) for i in range(6)]
            self.ax = self.axes[0]
        else:
            self.ax = self.fig.add_subplot(111)
        self._kind = kind
        if kind != "3d":
            self.ax.set_xlim(*xl)
            self.ax.set_ylim(*yl)

    def redraw(self, fast: bool = False):
        self._layout({"linked": "two", "3d": "3d", "multiples": "multi"}.get(self.mode, "one"))
        if self.mode in ("3d", "multiples", "parallel"):
            return self._redraw_special()
        xl, yl = self.ax.get_xlim(), self.ax.get_ylim()
        self.ax.clear()
        fs = self._style()
        self.ax.set_xlim(*xl)
        self.ax.set_ylim(*yl)
        self._lines.clear()
        levels, waiting = set(), []
        mode = self.mode
        if mode in ("cartesian", "parametric"):
            self._draw_curves(xl, levels, waiting)
        if mode == "parametric":
            self._draw_paths(levels, waiting)
        if mode == "polar":
            self._draw_polar(levels)
        if mode == "field":
            self._draw_field(xl, yl, levels, fs)
        if mode == "cartesian" and self.shade:
            self._draw_shade(xl)
        if mode in ("cartesian", "parametric"):
            self._draw_overlays(xl, yl, fs)
            self._draw_adversary(xl, yl, fs)
        if mode == "complex":
            self._draw_complex(xl, yl, levels, waiting, fs)
        if mode == "slice":
            self._draw_slice(xl, levels, fs)
        if mode == "linked":
            self._draw_linked(fs, levels)
        if self._lines:
            leg = self.ax.legend(loc="lower left", fontsize=fs * 0.85, facecolor=AX,
                                 edgecolor=GRID, labelcolor=TXT)
            leg.set_draggable(True)
        stamp = " · ".join(sorted(levels)) or "—"
        self.ax.set_title(tr("nivo: {0}").format(stamp) + (tr("   ·   računam: {0}…").format(", ".join(waiting)) if waiting else ""),
                          color=MUTED, fontsize=fs, loc="right")
        self.draw_idle()

    def _draw_shade(self, xl):
        fid, gid, a, b = self.shade
        by = {f.id: f for f in self.funcs}
        f, g = by.get(fid), by.get(gid)
        if not (f and g):
            return
        lo, hi = max(a, xl[0]), min(b, xl[1])
        if hi <= lo:
            return
        xs = np.linspace(lo, hi, 400)
        y1 = np.asarray(F.numeric(f, self.params)(xs), float)
        y2 = np.asarray(F.numeric(g, self.params)(xs), float)
        self.ax.fill_between(xs, y1, y2, color="#ffc257", alpha=0.22, linewidth=0,
                             label=tr("rezerva: {0} − {1}").format(f.label, g.label))

    def _draw_adversary(self, xl, yl, fs):
        """Item 31: points the adversarial mode found, on the (ℓ, B) plane."""
        try:
            from ..shared_lib.store import store
            pts = store().kv_get("adversary_points") or []
        except Exception:                               # noqa: BLE001
            return
        if not any(F.shape(f) in ("curve", "path") and f.builtin in ("B_line", "path_t", "path_w")
                   for f in self.funcs if f.visible):
            return                                      # only where the plane is (ℓ, B)
        for p in pts:
            if p.get("l") is None or not (xl[0] <= p["l"] <= xl[1] and yl[0] <= p["B"] <= yl[1]):
                continue
            red = p["kind"].startswith("krši") or p["kind"] == "kontraprimjer"
            self.ax.plot([p["l"]], [p["B"]], "X" if red else "D", color="#f49090" if red else "#74d79a",
                         markersize=8, zorder=5)
            self.ax.annotate(f" {p['method']}: {p['kind']}", (p["l"], p["B"]), color=TXT, fontsize=fs * 0.75)

    def _draw_overlays(self, xl, yl, fs):
        if self.show_targets:
            for name, v in F.TARGETS.items():
                if yl[0] <= v <= yl[1]:
                    self.ax.axhline(v, color="#6b7585", linewidth=0.8, linestyle="--")
                    self.ax.text(xl[1], v, f" {name}", color=MUTED, fontsize=fs * 0.9,
                                 va="center", ha="right")
        if self.show_walls:
            for name, v in C.WALL_LINES["B"].items():
                if yl[0] <= v <= yl[1]:
                    self.ax.axhline(v, color="#f49090", linewidth=0.9, linestyle=":")
            for name, v in C.WALL_LINES["x"].items():
                if xl[0] <= v <= xl[1]:
                    self.ax.axvline(v, color="#f49090", linewidth=0.9, linestyle=":")
                    self.ax.text(v, yl[1], f" {name}", color="#f49090", fontsize=fs * 0.8,
                                 va="top", rotation=90)

    # ---- complex (step 4) ---------------------------------------------- #
    def _cfunc(self):
        return next((g for g in self.funcs if g.visible and F.shape(g) == "complex"), None)

    def _sigma_star(self) -> float:
        from ..graphs import complex_ as CX
        return CX.sigma_star(self.params.get("low", 0), self.params.get("delta", 0))

    def _regions(self, ax, xl, yl, fs, zeros: bool):
        from ..graphs import complex_ as CX
        ss = self._sigma_star()
        ax.axvline(0, color=MUTED, linewidth=0.8, linestyle="--")
        ax.axvline(1, color=MUTED, linewidth=0.8, linestyle="--")
        ax.axvline(0.5, color=TXT, linewidth=1.0, linestyle="--")
        if ss < 1:
            ax.axvspan(ss, max(xl[1], ss), color="#74d79a", alpha=0.10)
            ax.axvline(ss, color="#74d79a", linewidth=1.4)
            ax.text(ss, yl[1], tr(" bez nula: Re s > σ* = {0:.4f}").format(ss), color="#74d79a",
                    fontsize=fs * 0.8, va="top")
        else:
            ax.text(0.5, 0.95, tr("σ* = {0:.4f} ≥ 1: oblast bez nula je nestala").format(ss),
                    transform=ax.transAxes, color="#f49090", ha="center", fontsize=fs * 0.9)
        if zeros:
            zs = [g for g in CX.zeta_zeros(60) if yl[0] <= g <= yl[1]] + \
                 [-g for g in CX.zeta_zeros(60) if yl[0] <= -g <= yl[1]]
            ax.plot([0.5] * len(zs), zs, "o", color="white", markersize=4, markerfacecolor="none",
                    label=tr("nule ζ (poznate)"))

    def _draw_complex(self, xl, yl, levels, waiting, fs):
        from ..graphs import complex_ as CX
        f = self._cfunc()
        self._cgrid = None
        if f is None:
            self.ax.text(0.5, 0.5, tr("Kompleksni prikaz treba vidljivu kompleksnu funkciju w = f(s)\n(npr. „+ funkcija“ → kompleksna → zeta(s))."),
                         transform=self.ax.transAxes, ha="center", va="center", color=MUTED, fontsize=fs)
            return
        n = 160 if _samples() >= 500 else 100
        key = ("C", f.id, f.expr, round(xl[0], 6), round(xl[1], 6), round(yl[0], 6), round(yl[1], 6), n,
               tuple(sorted(self.params.items())))

        def work(f=f, xl=xl, yl=yl, n=n):
            X, Y = np.meshgrid(np.linspace(*xl, n), np.linspace(*yl, n))
            return np.asarray(F.numeric(f, self.params)(X + 1j * Y), complex)
        W = self._bg(key, work)
        if W is None:
            waiting.append(f.label)
            return
        ext = (xl[0], xl[1], yl[0], yl[1])
        self._cgrid = (f, ext, W)
        self.ax.imshow(CX.phase_rgb(W), extent=ext, origin="lower", aspect="auto", interpolation="bilinear")
        X, Y = np.meshgrid(np.linspace(*xl, W.shape[1]), np.linspace(*yl, W.shape[0]))
        with np.errstate(all="ignore"):
            try:
                self.ax.contour(X, Y, W.real, levels=[0], colors=["#ffffff"], linewidths=0.8)
                self.ax.contour(X, Y, W.imag, levels=[0], colors=["#111111"], linewidths=0.8)
            except Exception:                           # noqa: BLE001
                pass
        if f.kind == "builtin":                         # the δ-plane of mission 3, not the s-plane
            self.ax.axhline(0, color=TXT, linewidth=0.8, linestyle="--")
            self.ax.set_xlabel("Re δ", color=MUTED, fontsize=fs * 0.9)
            self.ax.set_ylabel("Im δ", color=MUTED, fontsize=fs * 0.9)
        else:
            self._regions(self.ax, xl, yl, fs, "zeta" in f.expr)
            self.ax.set_xlabel("Re s = σ", color=MUTED, fontsize=fs * 0.9)
            self.ax.set_ylabel("Im s = t", color=MUTED, fontsize=fs * 0.9)
        self.ax.set_title(tr("boja = arg f, svjetlina = |f|; bijelo: Re f = 0, crno: Im f = 0 (nule su presjeci)"),
                          color=MUTED, fontsize=fs * 0.85, loc="left")
        levels.add(f.level)

    def _draw_slice(self, xl, levels, fs):
        f = self._cfunc()
        if f is None:
            return
        ts = np.linspace(xl[0], xl[1], max(400, _samples()))
        W = np.asarray(F.numeric(f, self.params)(0.5 + 1j * ts), complex)
        for ys, lab, st in ((np.abs(W), f"|{f.label}|", "-"), (W.real, f"Re {f.label}", "--"),
                            (W.imag, f"Im {f.label}", ":")):
            self.ax.plot(ts, ys, st, color=f.color, linewidth=1.6, label=lab)
        self._lines[f.id] = (ts, np.abs(W))
        if "zeta" in f.expr:
            from ..graphs import complex_ as CX
            Zt = np.vectorize(lambda t: float(__import__("mpmath").fp.siegelz(t)))(ts)
            self.ax.plot(ts, Zt, color="#ffb74d", linewidth=1.4, label="Hardy Z(t)")
            for g in CX.zeta_zeros(60):
                if xl[0] <= g <= xl[1]:
                    self.ax.axvline(g, color=GRID, linewidth=0.8)
        self.ax.axhline(0, color=MUTED, linewidth=0.8)
        self.ax.set_xlabel(tr("t (s = 1/2 + it)"), color=MUTED, fontsize=fs * 0.9)
        levels.add(f.level)

    def _draw_linked(self, fs, levels):
        """Left: exponent plane (ℓ, σ) with B(ℓ) and σ*; right: ℂ with the half-plane Re s > σ*.
        The same σ* is the crossing on the left and the edge of the region on the right."""
        ss = self._sigma_star()
        ax, ax2 = self.ax, self.ax2
        xl, yl = ax.get_xlim(), ax.get_ylim()
        ls = np.linspace(xl[0], xl[1], 200)
        ax.plot(ls, 11 / 12 - ls / 4, color="#ffb74d", linewidth=1.8, label="B(ℓ) = 11/12 − ℓ/4")
        ax.axhline(ss, color="#74d79a", linewidth=1.4, label=tr("σ* = 11/16 + niska strana + Δ"))
        l_star = 4 * (11 / 12 - ss)
        ax.plot([l_star], [ss], "o", color="#74d79a", markersize=7)
        ax.annotate(tr(" ℓ = {0:.4f}, σ* = {1:.4f}").format(l_star, ss), (l_star, ss), color=TXT, fontsize=fs * 0.8)
        for name, v in F.TARGETS.items():
            ax.axhline(v, color=GRID, linewidth=0.8, linestyle="--")
        ax.set_xlabel("ℓ", color=MUTED, fontsize=fs * 0.9)
        ax.set_ylabel(tr("σ (eksponent visoke strane)"), color=MUTED, fontsize=fs * 0.9)
        ax.legend(loc="lower left", fontsize=fs * 0.75, facecolor=AX, edgecolor=GRID, labelcolor=TXT)
        ax2.clear()
        ax2.set_facecolor(AX)
        for s_ in ax2.spines.values():
            s_.set_color(GRID)
        ax2.tick_params(colors=MUTED, labelsize=max(7.0, _base_pt() * 0.62))
        ax2.set_xlim(-0.5, 1.5)
        ax2.set_ylim(0, 45)
        self._regions(ax2, (-0.5, 1.5), (0, 45), fs, True)
        ax2.set_xlabel("Re s", color=MUTED, fontsize=fs * 0.9)
        ax2.set_title(tr("Δ do nestanka oblasti: {0:+.4f}").format(1 - ss), color=MUTED, fontsize=fs * 0.85)
        levels.update({F.RAD, F.OURS})

    # ---- step 5: 3D, small multiples, parallel coordinates ------------- #
    def _grid_n(self, kind: str) -> int:
        """The machine profile thins the grid on the Acer."""
        big = _samples() >= 500
        return {"3d": 70 if big else 40, "multi": 60 if big else 36}[kind]

    def _surface_data(self, f, n):
        if F.shape(f) == "complex":
            x0, x1, y0, y1 = -1.0, 2.0, 0.0, 35.0
            X, Y = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y0, y1, n))
            W = np.asarray(F.numeric(f, self.params)(X + 1j * Y), complex)
            return X, Y, W
        d = f.domain if len(f.domain) == 4 else [-2.0, 2.0, -2.0, 2.0]
        X, Y = np.meshgrid(np.linspace(d[0], d[1], n), np.linspace(d[2], d[3], n))
        return X, Y, np.asarray(F.numeric(f, self.params)(X, Y), float)

    def _redraw_special(self):
        from matplotlib import cm
        fs = max(7.0, _base_pt() * 0.62)
        self.fig.set_facecolor(BG)
        self._lines.clear()
        levels, waiting = set(), []
        if self.mode == "3d":
            ax = self.ax
            el, az = ax.elev, ax.azim
            ax.clear()
            ax.set_facecolor(AX)
            ax.view_init(elev=el, azim=az)
            ax.tick_params(colors=MUTED, labelsize=fs * 0.85)
            for a in (ax.xaxis, ax.yaxis, ax.zaxis):
                a.set_pane_color((0.09, 0.11, 0.15, 1.0))
            surfs = [f for f in self.funcs if f.visible and F.shape(f) in ("surface", "complex")]
            if not surfs:
                ax.text2D(0.5, 0.5, tr("3D treba vidljivu površ z = f(x, y) ili kompleksnu f(s)"),
                          transform=ax.transAxes, ha="center", color=MUTED, fontsize=fs)
            n = self._grid_n("3d")
            cmode = self.color_by
            for f in surfs[:2]:                         # at most 3 dimensions on screen + colour
                key = ("3D", f.id, f.expr, n, tuple(sorted(self.params.items())))
                data = self._bg(key, lambda f=f: self._surface_data(f, n))
                if data is None:
                    waiting.append(f.label)
                    continue
                X, Y, W = data
                if F.shape(f) == "complex":
                    Z = np.clip(np.abs(W), 0, 6)
                    cols = cm.hsv((np.angle(W) + np.pi) / (2 * np.pi))     # 4th dim: arg f
                    ax.plot_surface(X, Y, Z, facecolors=cols, linewidth=0, antialiased=False,
                                    rstride=1, cstride=1, shade=False)
                    ax.set_xlabel("Re s", color=MUTED)
                    ax.set_ylabel("Im s", color=MUTED)
                    ax.set_zlabel(tr("|f| (do 6)"), color=MUTED)
                else:
                    other = next((g for g in self.funcs if g.id == cmode and g.id != f.id), None)
                    if other is not None and F.shape(other) == "surface":
                        C4 = np.asarray(F.numeric(other, self.params)(X, Y), float)   # 4th dim
                        lim = np.nanmax(np.abs(C4)) or 1.0
                        cols = cm.RdBu_r((C4 / lim + 1) / 2)
                        ax.plot_surface(X, Y, W, facecolors=cols, linewidth=0, shade=False, alpha=0.9)
                    else:
                        ax.plot_surface(X, Y, W, cmap="viridis" if f is surfs[0] else "magma",
                                        linewidth=0, alpha=0.75)
                levels.add(f.level)
            ids = {f.builtin for f in surfs}
            if {"plane_sigma", "B_surface"} <= ids:      # the two exponent surfaces cross on σ = B(ℓ)
                ls = np.linspace(0, 0.3, 100)
                ax.plot(ls, 11 / 12 - ls / 4, 11 / 12 - ls / 4, color="#ffc257", linewidth=3,
                        label=tr("presjek: σ = B(ℓ)"))
                ax.legend(loc="upper left", fontsize=fs * 0.8, facecolor=AX, labelcolor=TXT)
        elif self.mode == "multiples":
            self._draw_multiples(fs, levels)
        elif self.mode == "parallel":
            self._draw_parallel(fs, levels, waiting)
        stamp = " · ".join(sorted(levels)) or "—"
        title = tr("nivo: {0}").format(stamp) + (tr("   ·   računam: {0}…").format(", ".join(waiting)) if waiting else "")
        self.fig.suptitle(title, color=MUTED, fontsize=fs, x=0.99, ha="right")
        self.draw_idle()

    def _draw_multiples(self, fs, levels):
        """The same picture for 6 values of the chosen parameter (the 5th dimension)."""
        p = self.anim_param
        _lab, lo, hi = SLIDERS[p]
        vals = np.linspace(lo, hi, 6)
        surf = next((f for f in self.funcs if f.visible and F.shape(f) == "surface"), None)
        curves = [f for f in self.funcs if f.visible and F.shape(f) == "curve"]
        n = self._grid_n("multi")
        keep = dict(self.params)
        try:
            for ax, v in zip(self.axes, vals):
                ax.clear()
                ax.set_facecolor(AX)
                ax.tick_params(colors=MUTED, labelsize=fs * 0.7)
                self.params = {**keep, p: float(v)}
                if surf is not None:
                    X, Y, Z = self._surface_data(surf, n)
                    ax.contourf(X, Y, Z, levels=20, cmap="RdBu_r")
                    try:
                        ax.contour(X, Y, Z, levels=[0], colors=["#ffc257"], linewidths=1.5)
                    except Exception:                   # noqa: BLE001
                        pass
                    levels.add(surf.level)
                else:
                    for f in curves:
                        if f.kind == "builtin" and F.eval_cost(f) * 200 > 1.0:
                            continue                    # too expensive for 6 small pictures
                        xs = np.linspace(*(f.domain[:2] if f.kind == "builtin" else (0, 1)), 200)
                        ax.plot(xs, np.asarray(F.numeric(f, self.params)(xs), float), color=f.color)
                        levels.add(f.level)
                ax.set_title(f"{SLIDERS[p][0]} = {v:.4g}", color=TXT, fontsize=fs * 0.85)
        finally:
            self.params = keep

    PARALLEL_AXES = ("ℓ", "b", "κ", "B")

    def _draw_parallel(self, fs, levels, waiting):
        """All method parameters at once: one polyline per method / extension point."""
        def rows():
            from ..methods import core as MC
            out = [("Liu", MC.optimum(MC.E_liu, 1 / 8), "#4fc3f7"),
                   ("Xu–Sang", MC.optimum(MC.E_xs, 1 / 8), "#81c784")]
            for t in (0.25, 0.5, 0.75):
                out.append((f"t = {t}", MC.extend_t(t), "#ffb74d"))
            for w in (0.05, 0.15, 0.2):
                out.append((f"w = {w}", MC.extend_w(w), "#e57373"))
            return [(name, [o.l, o.b, o.k, o.B], col) for name, o, col in out]
        data = self._bg(("PARALLEL",), rows)
        ax = self.ax
        ax.clear()
        self._style()
        if data is None:
            waiting.append(tr("paralelne koordinate (8 metoda)"))
            ax.text(0.5, 0.5, tr("računam 8 optimuma metoda u pozadini (~20–40 s)…"),
                    transform=ax.transAxes, ha="center", color=MUTED, fontsize=fs)
            return
        M = np.array([r[1] for r in data], float)
        lo, hi = M.min(axis=0), M.max(axis=0)
        span = np.where(hi - lo > 0, hi - lo, 1.0)
        N = (M - lo) / span
        xs = np.arange(len(self.PARALLEL_AXES))
        self._par = (data, N)
        for (name, vals, col), row in zip(data, N):
            ax.plot(xs, row, "-o", color=col, linewidth=1.6, markersize=4, label=name)
        for i, a in enumerate(self.PARALLEL_AXES):
            ax.axvline(i, color=GRID, linewidth=1.0)
            ax.text(i, -0.06, f"{lo[i]:.6g}", color=MUTED, ha="center", va="top", fontsize=fs * 0.75)
            ax.text(i, 1.06, f"{hi[i]:.6g}", color=MUTED, ha="center", va="bottom", fontsize=fs * 0.75)
        ax.set_xticks(xs, self.PARALLEL_AXES)
        ax.set_yticks([])
        ax.set_xlim(-0.3, len(xs) - 0.7)
        ax.set_ylim(-0.15, 1.15)
        ax.legend(loc="center right", fontsize=fs * 0.75, facecolor=AX, edgecolor=GRID, labelcolor=TXT)
        levels.update({F.RAD, F.OURS})

    def _hover_parallel(self, ev):
        par = getattr(self, "_par", None)
        if not par:
            return
        data, N = par
        i = int(round(ev.xdata)) if ev.xdata is not None else 0
        i = min(max(i, 0), N.shape[1] - 1)
        k = int(np.argmin(np.abs(N[:, i] - ev.ydata)))
        name, vals, _c = data[k]
        self.hovered.emit(tr("{0}: ℓ = {1:.9g}, b = {2:.6g}, κ = {3:.6g}, B = {4:.12g}").format(name, *vals))

    HOMES = {"cartesian": ((0.0, 0.3), (0.80, 0.95)), "parametric": ((0.14, 0.20), (0.86, 0.885)),
             "polar": ((-2.2, 2.2), (-2.2, 2.2)), "field": ((0.10, 0.22), (0.60, 0.90)),
             "complex": ((-1.0, 2.0), (-2.0, 35.0)), "slice": ((0.0, 50.0), (-4.0, 4.0)),
             "linked": ((0.0, 0.5), (0.5, 1.05))}

    def set_mode(self, mode: str):
        self.mode = mode
        self.ax.set_aspect("auto")
        self.home_view = self.HOMES.get(mode, self.home_view)
        if mode == "complex":
            f = self._cfunc()
            if f is not None and f.kind == "builtin":
                self.home_view = ((f.domain[0], f.domain[1]), (-0.2, 0.2))
        if mode == "field":
            f = next((g for g in self.funcs if g.visible and F.shape(g) == "surface"), None)
            if f is not None and len(f.domain) == 4:
                self.home_view = ((f.domain[0], f.domain[1]), (f.domain[2], f.domain[3]))
        self.home()

    def visible_data(self) -> dict:
        return {fid: (xs.tolist(), ys.tolist()) for fid, (xs, ys) in self._lines.items()}


# --------------------------------------------------------------------------- #
# Funkcije panel
# --------------------------------------------------------------------------- #
class FunctionDialog(QDialog):
    def __init__(self, f: Optional[F.Function] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Funkcija"))
        form = QFormLayout(self)
        self.kind = QComboBox()
        for k, txt in (("real", tr("realna  y = f(x)")), ("complex", tr("kompleksna  w = f(s)")),
                       ("surface", tr("površ  z = f(x, y)")), ("parametric", tr("parametarska  x(u); y(u)")),
                       ("polar", tr("polarna  r = f(th)"))):
            self.kind.addItem(txt, k)
        self.expr = QLineEdit()
        self.expr.setPlaceholderText(tr("npr. 11/12 - x/4   ·   x**3 - 2   ·   zeta(s)   ·   cos(u); sin(u)"))
        self.label = QLineEdit()
        self.lo, self.hi = QLineEdit("0"), QLineEdit("1")
        form.addRow(tr("vrsta:"), self.kind)
        form.addRow(tr("izraz:"), self.expr)
        form.addRow(tr("ime:"), self.label)
        form.addRow(tr("domen od:"), self.lo)
        form.addRow(tr("domen do:"), self.hi)
        form.addRow(QLabel(tr("Dozvoljeno: + − × ÷ **, sin cos tan exp log sqrt abs atan … zeta Z gamma re im arg; "
                              "klizači: l b k t w d low delta. Ništa drugo (provjera prije prevođenja).")))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.result_f: Optional[F.Function] = None
        self._orig = f
        if f is not None:
            self.kind.setCurrentIndex(max(0, self.kind.findData(f.kind)))
            self.expr.setText(f.expr)
            self.label.setText(f.label)
            self.lo.setText(f"{f.domain[0]:g}")
            self.hi.setText(f"{f.domain[1]:g}")

    def _ok(self):
        import time as _t
        try:
            dom = [float(self.lo.text()), float(self.hi.text())]
            if dom[1] <= dom[0]:
                raise ValueError(tr("domen: „do“ mora biti veće od „od“"))
            f = F.Function(id=self._orig.id if self._orig else f"f-{int(_t.time() * 1000)}",
                           label=self.label.text().strip() or self.expr.text().strip(),
                           kind=self.kind.currentData(), expr=self.expr.text().strip(),
                           color=self._orig.color if self._orig else "#ffb74d",
                           level=F.USER, domain=dom)
            F.validate(f)
        except (FX.FExprError, ValueError) as e:
            QMessageBox.warning(self, tr("Funkcija"), str(e))
            return
        self.result_f = f
        self.accept()


def _header(title: str, expand_signal) -> tuple:
    """Panel title + its own ⤢ button (each of the three panels can fill the tab)."""
    b = button("⤢", lambda: expand_signal.emit())
    b.setToolTip(tr("raširi ovaj panel preko cijelog taba (ponovo = vrati)"))
    return flow_row(QLabel(title), b), b


class FunctionsPanel(QWidget):
    changed = Signal()
    expand = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        row, self.b_expand = _header(tr("<b>Funkcije</b>"), self.expand)
        v.addWidget(row)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._toggled)
        self.list.itemDoubleClicked.connect(lambda _it: self._edit())
        v.addWidget(self.list, 1)
        self.b_builtin = button(tr("+ ugrađena"), self._builtin_menu)
        v.addWidget(flow_row(button(tr("+ funkcija"), self._add), self.b_builtin,
                             button(tr("Uredi"), self._edit), button(tr("Boja"), self._color),
                             button(tr("Ukloni"), self._remove)))
        v.addWidget(QLabel(tr("<b>Parametri</b> (klizači)")))
        grid = QGridLayout()
        self.sliders: dict = {}
        self.vals: dict = {}
        for r, (name, (lab, lo, hi)) in enumerate(SLIDERS.items()):
            s = QSlider(Qt.Horizontal)
            s.setRange(0, 1000)
            s.setValue(int(round((F.PARAMS[name] - lo) / (hi - lo) * 1000)))
            val = QLabel("")
            s.valueChanged.connect(lambda _v, n=name: self._slid(n))
            grid.addWidget(QLabel(tr(lab)), r, 0)
            grid.addWidget(s, r, 1)
            grid.addWidget(val, r, 2)
            self.sliders[name], self.vals[name] = s, val
        grid.setColumnStretch(1, 1)
        for s in self.sliders.values():
            s.setMinimumWidth(40)
        v.addLayout(grid)
        self.sigma = QLabel("")                          # σ* = 11/16 + niska strana (own line)
        v.addWidget(self.sigma)
        self.funcs = F.load()
        self.params = dict(F.PARAMS)
        for n in SLIDERS:
            self._slid(n, emit=False)
        self._slid("low", emit=False)
        self._slid("delta", emit=False)
        self.refresh()

    def value(self, name: str) -> float:
        _lab, lo, hi = SLIDERS[name]
        return lo + (hi - lo) * self.sliders[name].value() / 1000

    def _slid(self, name: str, emit: bool = True):
        self.params[name] = self.value(name)
        self.vals[name].setText(f"{self.params[name]:.4f}")
        if name in ("low", "delta") and hasattr(self, "sigma"):
            ss = 11 / 16 + self.params.get("low", 0) + self.params.get("delta", 0)
            self.sigma.setText(tr("  → σ* = 11/16 + niska strana + Δ = {0:.4f}").format(ss)
                               + (tr("  (oblast bez nula nestala)") if ss >= 1 else ""))
        if emit:
            self.changed.emit()

    def refresh(self):
        self.list.blockSignals(True)
        cur = self.current_id()
        self.list.clear()
        for f in self.funcs:
            it = QListWidgetItem(f"{f.label}   [{f.level}]")
            it.setData(Qt.UserRole, f.id)
            it.setForeground(QColor(f.color))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if f.visible else Qt.Unchecked)
            it.setToolTip(f.meaning or f.expr)
            self.list.addItem(it)
            if f.id == cur:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)

    def current_id(self) -> Optional[str]:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _find(self, fid):
        return next((f for f in self.funcs if f.id == fid), None)

    def _save(self):
        F.save(self.funcs)
        self.refresh()
        self.changed.emit()

    def _toggled(self, it):
        f = self._find(it.data(Qt.UserRole))
        if f:
            f.visible = it.checkState() == Qt.Checked
            F.save(self.funcs)
            self.changed.emit()

    def _add(self):
        d = FunctionDialog(parent=self)
        if d.exec() and d.result_f:
            d.result_f.color = F.next_color(self.funcs)
            self.funcs.append(d.result_f)
            self._save()

    def _builtin_menu(self):
        m = QMenu(self)
        for key, b in F.BUILTINS.items():
            m.addAction(f"{b['label']}   [{b['level']}]", lambda k=key: self._add_builtin(k))
        m.exec(self.b_builtin.mapToGlobal(self.b_builtin.rect().bottomLeft()))

    def _add_builtin(self, key):
        if any(f.builtin == key for f in self.funcs):
            return
        self.funcs.append(F.builtin(key, F.next_color(self.funcs)))
        self._save()

    def _edit(self):
        f = self._find(self.current_id())
        if f is None or f.kind == "builtin":
            return
        d = FunctionDialog(f, self)
        if d.exec() and d.result_f:
            self.funcs[self.funcs.index(f)] = d.result_f
            self._save()

    def _color(self):
        f = self._find(self.current_id())
        if f is None:
            return
        c = QColorDialog.getColor(QColor(f.color), self)
        if c.isValid():
            f.color = c.name()
            self._save()

    def _remove(self):
        f = self._find(self.current_id())
        if f is not None:
            self.funcs.remove(f)
            self._save()


# --------------------------------------------------------------------------- #
# Kalkulacije panel
# --------------------------------------------------------------------------- #
def info_md(info: dict) -> str:
    out = [tr("### Sve o tački"), "",
           f"**{info['function']}** · {info['level']}" + (f" · [[{info['card']}]]" if info.get("card") else ""),
           "", f"x = `{info['x']:.12g}`, y = `{info['y']:.12g}`" if F.is_finite(info["y"]) else f"x = `{info['x']:.12g}`"]
    if info.get("z") is not None:
        out += ["", tr("**Vrijednost površi:** `{0:.9g}`").format(info["z"])]
    if info.get("grad") is not None:
        out += ["", tr("**Gradijent:** ({0:.6g}, {1:.6g}) · **Hesijan:** {2}").format(
            info["grad"][0], info["grad"][1], info.get("hess_kind", "?"))]
    if info.get("B_if_boundary") is not None:
        out += ["", tr("**Ako je ovo granica:** B = 11/12 − ℓ/4 = `{0:.9g}`").format(info["B_if_boundary"])]
    if info.get("meaning"):
        out += ["", tr("**Značenje:** {0}").format(info["meaning"])]
    if info.get("flags"):
        out += ["", tr("**Tačka je:** {0}").format("; ".join(info["flags"]))]
    if info.get("dydx") is not None:
        out += ["", f"f′ = `{info['dydx']:.9g}`"]
    if info.get("targets"):
        out += ["", tr("**Udaljenost do ciljeva:** ") + " · ".join(
            f"{k}: {v:+.6g}" for k, v in info["targets"].items())]
    ps = info.get("params", {})
    out += ["", tr("**Parametri:** ") + ", ".join(f"{k}={v:.4g}" for k, v in ps.items())]
    return "\n".join(out)


def result_md(title: str, res: dict) -> str:
    st = res.get("status", "")
    lines = [f"#### {title} — {st}"]
    for k, v in res.items():
        if k in ("status",):
            continue
        if isinstance(v, float):
            v = f"{v:.12g}"
        elif isinstance(v, (dict, list)):
            import json
            v = "`" + json.dumps(v, ensure_ascii=False, default=str)[:600] + "`"
        lines.append(f"- **{k}:** {v}")
    lines.append(tr("_oznaka: NAŠE-NERECENZIRANO — računao Python, deterministički_"))
    return "\n".join(lines)


class CalcPanel(QWidget):
    open_card = Signal(str)
    expand = Signal()
    shade = Signal(str, str, float, float)      # an "area" result → shade it on the plot

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        row, self.b_expand = _header(tr("<b>Kalkulacije</b>"), self.expand)
        v.addWidget(row)
        self.view = MarkdownView()
        if hasattr(self.view, "anchorClicked"):
            self.view.anchorClicked.connect(lambda url: self.open_card.emit(url.toString().split("/")[-1]))
        v.addWidget(self.view, 1)
        # offers as a wrapping list (long sentences must not widen the panel)
        self.offers = QListWidget()
        self.offers.setWordWrap(True)
        self.offers.setMaximumHeight(int(_base_pt() * 9))
        self.offers.itemActivated.connect(self._offer_clicked)
        self.offers.itemClicked.connect(self._offer_clicked)
        v.addWidget(self.offers)
        self.b_cancel = button(tr("Prekini"), lambda: C.JOBS.cancel_all(), kind="no")
        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(flow_row(self.status, self.b_cancel))
        self.bridge = _Bridge()
        self.bridge.job_done.connect(self._job_done)
        self._ctx = None
        self._results: list = []
        self.view.set_markdown(tr("_Klikni na krivu: ovdje se pojavi sve što se zna o toj tački i ponude računa._"))

    def show_point(self, f: F.Function, x: float, funcs: list, params: dict, yspan: float):
        info = C.point_info(f, x, funcs, params, yspan)
        self._ctx = (f, x, funcs, params)
        self._results = []
        self._info_md = info_md(info)
        self.view.set_markdown(self._info_md)
        self.offers.clear()
        offs = C.offers(f, info, funcs)
        main = [o for o in offs if not o.get("more")]
        more = [o for o in offs if o.get("more")]
        self._more = more
        for o in main:
            it = QListWidgetItem("▸ " + self._offer_text(o))
            it.setData(Qt.UserRole, o)
            it.setToolTip(o.get("why", ""))
            self.offers.addItem(it)
        if more:
            it = QListWidgetItem(tr("▸ više… ({0})").format(len(more)))
            it.setData(Qt.UserRole, {"key": "__more__"})
            self.offers.addItem(it)
        # cheap ones right away (tangent is always cheap for typed functions)
        for o in main:
            if not o["ask"] and o["key"] in ("tangent",):
                self._run(o)

    def show_xy(self, f: F.Function, x: float, y: float, params: dict, z=None):
        """A path / polar / surface point: everything known, no curve-only offers."""
        info = C.point_info_xy(f, x, y, params, z)
        self._ctx = None
        self._results = []
        self._info_md = info_md(info)
        self.view.set_markdown(self._info_md)
        self.offers.clear()

    def show_complex(self, f: F.Function, s: complex, params: dict, sigma_s: float, rect):
        from ..graphs import complex_ as CX
        fp = F.precise(f, params)
        info = CX.point_info_c(f.label, f.level, lambda z: complex(fp(z)), s, sigma_s, "zeta" in f.expr)
        self._ctx = (f, s, [f], params)
        self._results = []
        md = [tr("### Sve o tački"), "", f"**{f.label}** · {f.level}", "",
              f"s = `{s.real:.10g} + {s.imag:.10g}i`", "",
              f"f(s) = `{info['f(s)']:.10g}`", "",
              f"|f| = `{info['|f|']:.6g}` · arg f = `{info['arg f']:+.6f}`", "",
              tr("**Udaljenost do prave 1/2:** {0:.6g}").format(info["dist_to_1/2"]), "",
              tr("**Granica oblasti bez nula σ∗:** {0:.6g}").format(sigma_s)]
        if info["flags"]:
            md += ["", tr("**Tačka je:** {0}").format("; ".join(info["flags"]))]
        if info.get("nearest_zero"):
            z = info["nearest_zero"]
            md += ["", tr("**Najbliža poznata nula ζ:** 1/2 + {0:.9g}i (udaljenost {1:.4g})").format(z["s"].imag, z["distance"])]
        self._info_md = "\n".join(md)
        self.view.set_markdown(self._info_md)
        self.offers.clear()
        self._more = []
        for o in C.offers_complex(f, rect):
            it = QListWidgetItem("▸ " + self._offer_text(o))
            it.setData(Qt.UserRole, o)
            self.offers.addItem(it)

    def _offer_text(self, o) -> str:
        est = o["est_s"]
        dur = tr("odmah") if not o["ask"] else (tr("~{0:.0f} s").format(est) if est < 120 else tr("~{0:.0f} min").format(est / 60))
        return tr("Želiš li da izračunam: {0}? ({1})").format(tr(o["title"]).format(*o.get("args", [])), dur) if o["ask"] \
            else tr("{0} ({1})").format(tr(o["title"]).format(*o.get("args", [])), dur)

    def _offer_clicked(self, it):
        o = it.data(Qt.UserRole)
        if not o:
            return
        if o.get("key") == "__more__":
            m = QMenu(self)
            for oo in self._more:
                m.addAction(self._offer_text(oo), lambda x=oo: self._ask(x))
            m.exec(self.offers.mapToGlobal(self.offers.visualItemRect(it).bottomLeft()))
            return
        self._ask(o)

    def _ask(self, o):
        if o["ask"]:
            r = QMessageBox.question(self, tr("Kalkulacije"), self._offer_text(o) + "\n\n" +
                                     tr("Računa se u pozadini; možeš prekinuti dugmetom „Prekini“."))
            if r != QMessageBox.Yes:
                return
        self._run(o)

    def _run(self, o):
        if not self._ctx:
            return
        f, x, funcs, params = self._ctx
        self.status.setText(tr("računam: {0}…").format(tr(o["title"]).format(*o.get("args", []))))
        C.JOBS.submit(o["key"], f, x, funcs, params, extra=o.get("extra"),
                      done=lambda jid, res, t=tr(o["title"]).format(*o.get("args", [])): self.bridge.job_done.emit(t, dict(res)))

    def _job_done(self, title: str, res: dict):
        self.status.setText(tr("{0}: {1}").format(title, res.get("status", "")))
        if res.get("with_id") and self._ctx and res.get("a") is not None:
            self.shade.emit(self._ctx[0].id, res["with_id"], float(res["a"]), float(res["b"]))
        self._results.append(result_md(title, res))
        self.view.set_markdown(self._info_md + "\n\n" + "\n\n".join(self._results))


# --------------------------------------------------------------------------- #
# the tab
# --------------------------------------------------------------------------- #
class GrafoviTab(QWidget):
    open_card = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        self.mode = QComboBox()
        for key, txt in (("cartesian", tr("Kartezijanski")), ("parametric", tr("Parametarski")),
                         ("polar", tr("Polarni")), ("field", tr("Vektorsko polje")),
                         ("complex", tr("Kompleksni (fazni portret)")),
                         ("slice", tr("Presjek duž prave Re s = 1/2")),
                         ("linked", tr("Povezani: ravan eksponenata ↔ ℂ")),
                         ("3d", tr("3D (rotira se mišem ili strelicama)")),
                         ("multiples", tr("Male slike (6 vrijednosti parametra)")),
                         ("parallel", tr("Paralelne koordinate (metode)"))):
            self.mode.addItem(txt, key)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.cb_t = QCheckBox(tr("ciljevi"))
        self.cb_t.setChecked(True)
        self.cb_w = QCheckBox(tr("zidovi"))
        self.cb_w.setChecked(True)
        self.b_expand = button(tr("⤢ raširi"), self.toggle_expand)
        # 4th dimension = colour, 5th = a slider (animation / small multiples)
        self.cb_color = QComboBox()
        self.cb_color.currentIndexChanged.connect(self._color_changed)
        self.cb_anim = QComboBox()
        for name, (lab, _lo, _hi) in SLIDERS.items():
            self.cb_anim.addItem(tr(lab), name)
        self.cb_anim.setCurrentIndex(self.cb_anim.findData("w"))
        self.cb_anim.currentIndexChanged.connect(self._anim_param_changed)
        self.b_play = button("▶", self.toggle_anim)
        self.b_play.setToolTip(tr("animacija: izabrani parametar prolazi kroz svoj opseg"))
        from PySide6.QtCore import QTimer as _QT
        self._anim = _QT(self)
        self._anim.timeout.connect(self._anim_step)
        v.addWidget(flow_row(
            QLabel(tr("<b>Grafovi</b>")), QLabel(tr("prikaz:")), self.mode, self.cb_t, self.cb_w,
            button("◀", lambda: self.canvas.pan(-PAN_STEP, 0)), button("▲", lambda: self.canvas.pan(0, PAN_STEP)),
            button("▼", lambda: self.canvas.pan(0, -PAN_STEP)), button("▶", lambda: self.canvas.pan(PAN_STEP, 0)),
            button("+", lambda: self.canvas.zoom(0.8)), button("−", lambda: self.canvas.zoom(1.25)),
            button("⌂", lambda: self.canvas.home()),
            button(tr("PNG"), lambda: self.export("png")), button(tr("SVG"), lambda: self.export("svg")),
            button(tr("CSV"), self.export_csv), self.b_expand, button("?", self.guide),
            QLabel(tr("boja (4. dim.):")), self.cb_color, QLabel(tr("5. dim.:")), self.cb_anim, self.b_play))
        self.split = QSplitter(Qt.Horizontal)
        self.split.setObjectName("grafovi")
        self.funcs = FunctionsPanel()
        self.canvas = GraphCanvas()
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        self.b_expand_graph = button("⤢", lambda: self.expand_panel("graph"))
        self.b_expand_graph.setToolTip(tr("raširi ovaj panel preko cijelog taba (ponovo = vrati)"))
        mv.addWidget(flow_row(QLabel(tr("<b>Graf</b>")), self.b_expand_graph))
        mv.addWidget(self.canvas, 1)
        self.hover = QLabel("")
        self.hover.setWordWrap(True)
        self.hover.setStyleSheet(f"color:{MUTED};")
        mv.addWidget(self.hover)
        self.calc = CalcPanel()
        from .widgets import scroll_wrap
        # side panels scroll instead of forcing the plot narrow (26 pt on the Surface)
        self._side = (scroll_wrap(self.funcs), scroll_wrap(self.calc))
        for w in (self._side[0], mid, self._side[1]):
            self.split.addWidget(w)
        self._panels = {"funcs": self._side[0], "graph": mid, "calc": self._side[1]}
        self._btns = {"funcs": self.funcs.b_expand, "graph": self.b_expand_graph,
                      "calc": self.calc.b_expand}
        self.funcs.expand.connect(lambda: self.expand_panel("funcs"))
        self.calc.expand.connect(lambda: self.expand_panel("calc"))
        self.split.setStretchFactor(0, 2)
        self.split.setStretchFactor(1, 5)
        self.split.setStretchFactor(2, 3)
        v.addWidget(self.split, 1)
        self.funcs.changed.connect(self.redraw)
        self.cb_t.toggled.connect(self.redraw)
        self.cb_w.toggled.connect(self.redraw)
        self.canvas.hovered.connect(self.hover.setText)
        self.canvas.clicked.connect(self._clicked)
        self.canvas.clicked_xy.connect(self._clicked_xy)
        self.calc.shade.connect(self._shade)
        self.canvas.card.connect(self.open_card.emit)
        self.calc.open_card.connect(self.open_card.emit)
        self._expanded = None
        self._sized = False
        self.setStyleSheet(
            "QSlider::groove:horizontal { height:6px; background:#262d3a; border-radius:3px; }"
            "QSlider::sub-page:horizontal { background:#ffc257; border-radius:3px; }"
            "QSlider::handle:horizontal { background:#e9ecf3; width:14px; margin:-5px 0; border-radius:7px; }")
        self.redraw()

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._sized:                     # the plot gets the most room
            self._sized = True
            w = max(600, self.split.width())
            self.split.setSizes([int(w * 0.22), int(w * 0.50), int(w * 0.28)])

    def redraw(self):
        if hasattr(self, "cb_color"):
            self._refresh_color_choices()
        self.canvas.funcs = self.funcs.funcs
        self.canvas.params = dict(self.funcs.params)
        self.canvas.show_targets = self.cb_t.isChecked()
        self.canvas.show_walls = self.cb_w.isChecked()
        self.canvas.redraw()

    def _refresh_color_choices(self):
        cur = self.cb_color.currentData()
        self.cb_color.blockSignals(True)
        self.cb_color.clear()
        self.cb_color.addItem(tr("visina / arg f"), "")
        for f in self.funcs.funcs:
            if F.shape(f) == "surface":
                self.cb_color.addItem(f.label, f.id)
        self.cb_color.setCurrentIndex(max(0, self.cb_color.findData(cur)))
        self.cb_color.blockSignals(False)

    def _color_changed(self):
        self.canvas.color_by = self.cb_color.currentData() or ""
        self.canvas.redraw()

    def _anim_param_changed(self):
        self.canvas.anim_param = self.cb_anim.currentData()
        if self.canvas.mode == "multiples":
            self.canvas.redraw()

    def toggle_anim(self):
        if self._anim.isActive():
            self._anim.stop()
            self.b_play.setText("▶")
        else:
            self._anim.start(250 if _samples() >= 500 else 500)
            self.b_play.setText("⏸")

    def _anim_step(self):
        s = self.funcs.sliders[self.cb_anim.currentData()]
        s.setValue((s.value() + 25) % 1001)

    def _mode_changed(self):
        self.canvas.set_mode(self.mode.currentData())
        self.canvas.shade = None
        self.redraw()

    def _shade(self, fid: str, gid: str, a: float, b: float):
        self.canvas.shade = (fid, gid, a, b)
        self.canvas.redraw()

    def _clicked_xy(self, fid: str, x: float, y: float):
        f = next((g for g in self.funcs.funcs if g.id == fid), None)
        if f is None:
            return
        if F.shape(f) == "complex":
            xl, yl = self.canvas.ax.get_xlim(), self.canvas.ax.get_ylim()
            self.calc.show_complex(f, complex(x, y), dict(self.funcs.params),
                                   self.canvas._sigma_star(), [[xl[0], yl[0]], [xl[1], yl[1]]])
            return
        z = None
        if F.shape(f) == "surface":
            z = float(np.asarray(F.numeric(f, self.funcs.params)(np.array([x]), np.array([y])))[0])
        self.calc.show_xy(f, x, y, dict(self.funcs.params), z)

    def _clicked(self, fid: str, x: float):
        f = next((g for g in self.funcs.funcs if g.id == fid), None)
        if f is None:
            return
        y0, y1 = self.canvas.ax.get_ylim()
        self.calc.show_point(f, x, self.funcs.funcs, dict(self.funcs.params), y1 - y0)

    def toggle_expand(self):
        """The toolbar "⤢ raširi" = the plot panel's own ⤢."""
        self.expand_panel("graph")

    def expand_panel(self, name: str):
        """Fill the tab with one panel (Funkcije / Graf / Kalkulacije); again = all three."""
        self._expanded = None if self._expanded == name else name
        for key, w in self._panels.items():
            w.setVisible(self._expanded in (None, key))
            self._btns[key].setText("⤡" if self._expanded == key else "⤢")
        self.funcs.setVisible(self._expanded in (None, "funcs"))
        self.calc.setVisible(self._expanded in (None, "calc"))
        self.b_expand.setText(tr("⤡ vrati") if self._expanded == "graph" else tr("⤢ raširi"))

    def export(self, fmt: str):
        p, _ = QFileDialog.getSaveFileName(self, tr("Izvezi graf"), f"graf.{fmt}", f"*.{fmt}")
        if p:
            self.canvas.fig.savefig(p, format=fmt, facecolor=BG)

    def export_csv(self):
        p, _ = QFileDialog.getSaveFileName(self, tr("Izvezi podatke"), "graf.csv", "*.csv")
        if not p:
            return
        write_csv(Path(p), self.canvas, self.funcs.funcs)

    def guide(self):
        from .. import config
        from ..i18n import lang
        name = "VODIC-GRAFOVI-EN.md" if lang() == "en" else "VODIC-GRAFOVI-SR.md"
        for base in (config.APP_ROOT.parent / "docs", config.APP_ROOT / "docs",
                     Path("/usr/share/doc/pse-riemann")):
            q = base / name
            if q.exists():
                d = QDialog(self)
                d.setWindowTitle(tr("Vodič: Grafovi"))
                lay = QVBoxLayout(d)
                mv = MarkdownView()
                mv.set_markdown(q.read_text(encoding="utf-8"))
                lay.addWidget(mv)
                from .. import screen as SCR
                SCR.fit(d, 900, 800)
                d.exec()
                return
        QMessageBox.information(self, tr("Vodič"), tr("Vodič nije pronađen ({0}).").format(name))


def write_csv(path: Path, canvas: GraphCanvas, funcs: list) -> int:
    """The sampled data of every curve in view: function, level, x, y."""
    by_id = {f.id: f for f in funcs}
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["function", "level", "x", "y"])
        for fid, (xs, ys) in canvas.visible_data().items():
            f = by_id.get(fid)
            for x, y in zip(xs, ys):
                w.writerow([f.label if f else fid, f.level if f else "", repr(x), repr(y)])
                n += 1
    return n
