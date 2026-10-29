"""
App settings — small, persisted, and separate from secrets.

Lives in ~/.config/pse-riemann/settings.json next to (but not mixed with)
secrets.json. Anything here is safe to read, log, and show on screen; anything
in secrets.json is not.

The one setting that matters on this machine is `ui_scale`. The Surface runs its
desktop at Xft.dpi 240 (2.5×) plus a 1.25 text-scaling factor, which Qt happily
multiplies together into an unusable window. Rather than fight the desktop, the
app opts out of desktop scaling entirely and renders at its own size — see
`qt_env()`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Optional

from . import config

DEFAULTS: dict[str, Any] = {
    "ui_scale": 1.0,        # 1.0 = normal desktop size, independent of Xft.dpi
    "font_pt": 0,           # 0 = derive from ui_scale; otherwise an absolute pt
    "geometry": "",         # base64 QMainWindow geometry
    "win_state": "",
    "splits": {},           # name -> [sizes]
    "daily_cap": 5.0,
    # "→ ∞" ceilings L, set by the operator (master §5)
    # s/token comes from the machine profile unless the operator sets it here
    "limits_L": {"rss_gb": 12.0, "queue": 8},
    "machine_profile": "auto",
    # journal retention (archive + anchor, never plain delete)
    "journal_keep_days": 90, "journal_keep_min": 20000, "journal_max_live": 200000,
}

_CACHE: Optional[dict] = None


def load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data = dict(DEFAULTS)
    p = config.SETTINGS_FILE
    if p.exists():
        try:
            data.update(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    _CACHE = data
    return data


def save() -> None:
    if _CACHE is None:
        return
    p = config.SETTINGS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(_CACHE, indent=1), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def get(key: str, default: Any = None) -> Any:
    return load().get(key, DEFAULTS.get(key, default))


def set_(key: str, value: Any) -> None:
    load()[key] = value
    save()


# --------------------------------------------------------------------------- #
# Display scaling
# --------------------------------------------------------------------------- #
def detect_desktop_scale() -> float:
    """
    What the desktop is telling applications to do. Informational only — we
    override it — but it is worth showing in the UI so the number in the
    settings dialog means something.
    """
    for var in ("QT_SCALE_FACTOR", "GDK_SCALE"):
        v = os.environ.get(var, "").strip()
        if v:
            try:
                return float(v)
            except ValueError:
                pass
    try:
        out = subprocess.run(["xrdb", "-query"], capture_output=True, text=True,
                             timeout=3).stdout
        m = re.search(r"Xft\.dpi:\s*([0-9.]+)", out)
        if m:
            return round(float(m.group(1)) / 96.0, 3)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return 1.0


def qt_env(scale: Optional[float] = None) -> dict:
    """
    Environment that must be set BEFORE QApplication exists.

    We deliberately switch OFF Qt's desktop-driven scaling and pin the font DPI
    to 96, then apply exactly one factor of our own. The result: `ui_scale = 1.0`
    looks like a plain 100% desktop no matter what the system is set to, and the
    slider actually means something instead of multiplying with two other
    hidden factors.
    """
    s = float(scale if scale is not None else get("ui_scale", 1.0))
    s = max(0.5, min(s, 3.0))
    return {
        "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
        "QT_ENABLE_HIGHDPI_SCALING": "0",
        "QT_SCREEN_SCALE_FACTORS": "",
        "QT_FONT_DPI": "96",
        "QT_SCALE_FACTOR": f"{s:g}",
    }


def apply_qt_env(scale: Optional[float] = None) -> float:
    """Set the vars in os.environ. Returns the scale actually applied."""
    env = qt_env(scale)
    for k, v in env.items():
        if v == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return float(env["QT_SCALE_FACTOR"])


# The reading size. This panel is 1920x1080 across 235 mm (~207 real DPI) with
# desktop scaling switched off, and this app is for reading mathematics for
# hours — so the default is deliberately large. It sets text size only:
# `ui_scale` is what changes the window, and it stays at 1.0.
DEFAULT_FONT_PT = 26.0


def base_font_pt() -> float:
    """Point size for the app stylesheet. Independent of ui_scale on purpose:
    ui_scale resizes everything, this nudges only text."""
    v = float(get("font_pt", 0) or 0)
    if v > 0:
        return v                                  # the operator's own size always wins
    from . import screen as SCR                   # else: measured from this screen
    prof = SCR.current()
    return prof.font_pt if prof else DEFAULT_FONT_PT
