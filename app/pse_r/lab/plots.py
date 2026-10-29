"""
Plot rendering — matplotlib on the Agg backend, straight to PNG.

Agg only: no Qt backend, no interactive canvas, no second event loop competing
with PySide6 for the 4 GB. The GUI loads the finished PNG. Figures are closed
explicitly after every render because matplotlib leaks them otherwise, and on
this machine that shows up within an afternoon.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402

from .. import config                    # noqa: E402

DPI = config.LIM["plot_dpi"]
FIGSIZE = (7.2, 4.2)


def style(ax, spec: dict, fs: float = 9.0, dark: bool = False) -> None:
    """Title, labels, grid and reference lines — shared by PNG and the live view."""
    kw = {"color": "#9aa4b5"} if dark else {}             # PNG keeps matplotlib's defaults
    ax.set_title(spec.get("title", ""), fontsize=fs * 1.2, **kw)
    ax.set_xlabel(spec.get("xlabel", ""), fontsize=fs, **kw)
    ax.set_ylabel(spec.get("ylabel", ""), fontsize=fs, **kw)
    ax.tick_params(labelsize=fs * 0.9, **({"colors": kw["color"]} if dark else {}))
    ax.grid(True, alpha=0.25, linewidth=0.5)
    if spec.get("zeroline"):
        ax.axhline(0.0, color="#888", linewidth=0.8)
    if spec.get("hline") is not None:
        ax.axhline(spec["hline"], color="#c0392b", linewidth=0.9, linestyle="--")


def _finish(fig, ax, spec: dict, out: Path) -> Path:
    style(ax, spec)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return out


def render(spec: dict, series: dict, out: Path) -> Path:
    """The PNG kept with every lab run (cards link to it)."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    draw(ax, spec, series, fig)
    return _finish(fig, ax, spec, out)


def draw(ax, spec: dict, series: dict, fig=None, fs: float = 8.0) -> None:
    """Draw one plot spec into an existing Axes (PNG and the interactive view)."""
    kind = spec.get("kind", "line")

    if kind == "line":
        xs, ys = _xy(series.get(spec["series"], []))
        ax.plot(xs, ys, linewidth=0.9, label=spec.get("series"))
        marks = spec.get("marks")
        if marks and series.get(marks):
            mx, my = _xy(series[marks])
            ax.plot(mx, my, "o", markersize=3.5, color="#c0392b", label=marks)

    elif kind == "step":
        xs, ys = _xy(series.get(spec["series"], []))
        ax.step(xs, ys, where="post", linewidth=0.9, label=spec.get("series"))

    elif kind == "scatter":
        xs, ys = _xy(series.get(spec["series"], []))
        ax.plot(xs, ys, ".", markersize=3, label=spec.get("series"))

    elif kind == "stem":
        xs, ys = _xy(series.get(spec["series"], []))
        ax.vlines(xs, 0, ys, linewidth=0.8)
        ax.plot(xs, ys, "o", markersize=3, label=spec.get("series"))

    elif kind == "two_lines":
        names = spec["series"]
        labels = spec.get("labels", names)
        for nm, lb in zip(names, labels):
            xs, ys = _xy(series.get(nm, []))
            ax.plot(xs, ys, linewidth=1.0, label=lb)
        ax.legend(fontsize=fs)

    elif kind == "hist_vs_curves":
        xs, ys = _xy(series.get(spec["series"], []))
        w = (xs[1] - xs[0]) if len(xs) > 1 else 0.1
        labels = spec.get("labels", [])
        ax.bar(xs, ys, width=w * 0.9, alpha=0.55,
               label=labels[0] if labels else "izmjereno")
        for i, cname in enumerate(spec.get("curves", []), start=1):
            cx, cy = _xy(series.get(cname, []))
            ax.plot(cx, cy, linewidth=1.4,
                    label=labels[i] if i < len(labels) else cname)
        ax.legend(fontsize=fs)

    elif kind == "field":
        import numpy as np
        d = spec["data"]
        arr = np.array(d["mod"])
        ext = d["extent"]
        im = ax.imshow(arr, origin="lower", aspect="auto", extent=ext,
                       cmap="magma")
        if fig is not None:
            fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02).set_label(
                "log|ζ|", fontsize=fs)
        cl = spec.get("critical_line")
        if cl is not None:
            ax.axvline(cl, color="#4fc3f7", linewidth=1.0, linestyle="--")


def _xy(pairs):
    if not pairs:
        return [], []
    return [p[0] for p in pairs], [p[1] for p in pairs]
