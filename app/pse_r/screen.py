"""
Screen fitting (Andrej, 2026-10-25): measure the screen the app starts on and
adapt to it, instead of a fixed 1420×900 window and a 26 pt font tuned for one
panel (the Surface: 1920×1080 across 235 mm, ~207 real DPI).

  * real DPI = pixels / physical inches (QScreen.physicalSize). Text is sized so
    it has the same PHYSICAL size everywhere (~12 pt on paper): 26 pt on the
    Surface, ~12 pt on an ordinary 24" monitor. If the screen does not report a
    believable physical size (VMs, some projectors), we fall back to the old
    default — never a guess presented as a measurement.
  * the font is capped so a narrow screen still holds ~70 characters per width.
  * the window opens at 92 % of the AVAILABLE area (taskbar excluded), centred;
    a remembered geometry is used only if it still fits the current screen
    (a laptop ↔ monitor switch must not leave the window off-screen).

The operator's own text size (Ctrl +/−, stored `font_pt`) always wins.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

PHYS_PT = 12.0            # target physical text size (pt at true 96 DPI)
FALLBACK_PT = 26.0        # the old default, for screens without a usable size
MIN_PT, MAX_PT = 9.0, 32.0
CHARS_ACROSS = 70         # a narrow screen must still hold ~70 characters
WINDOW_FRACTION = 0.92


@dataclass
class Profile:
    width_px: int            # device pixels of the available area
    height_px: int
    dpi: Optional[float]     # real DPI, None if the screen did not tell us
    font_pt: float
    win_w: int               # logical pixels (what Qt's resize() takes)
    win_h: int
    measured: bool
    avail_x: int = 0         # logical position of the available area (multi-monitor)
    avail_y: int = 0
    name: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def compute(width_px: int, height_px: int, width_mm: float, height_mm: float,
            scale: float = 1.0, full_width_px: Optional[int] = None) -> Profile:
    """Pure function (tested): device pixels + physical mm → font and window size.
    `width_px`/`height_px` are the AVAILABLE area; `full_width_px` the whole panel
    (the physical size belongs to the whole panel)."""
    scale = scale or 1.0
    fw = full_width_px or width_px
    dpi = None
    if width_mm and width_mm > 50 and fw > 0:
        d = fw / (width_mm / 25.4)
        if 60 <= d <= 400:                    # believable; else the screen lies
            dpi = d
    # unmeasured: the old default, but a small panel still holds ~100 characters
    pt = PHYS_PT * dpi / 96.0 if dpi else min(FALLBACK_PT, width_px / (100 * 4 / 3 * 0.55 * scale))
    # 1 pt at QT_FONT_DPI 96 = 4/3 px, an average glyph ≈ 0.55 em; ui_scale multiplies it
    if width_px:
        pt = min(pt, width_px / (CHARS_ACROSS * 4 / 3 * 0.55 * scale))
    pt = round(max(MIN_PT, min(MAX_PT, pt)), 1)
    win_w = int(width_px / scale * WINDOW_FRACTION)
    win_h = int(height_px / scale * WINDOW_FRACTION)
    return Profile(width_px, height_px, round(dpi, 1) if dpi else None, pt,
                   max(640, win_w), max(480, win_h), dpi is not None)


_CURRENT: Optional[Profile] = None


def detect(app=None) -> Optional[Profile]:
    """Measure the primary screen (needs a QApplication). Never raises."""
    global _CURRENT
    try:
        from PySide6.QtGui import QGuiApplication
        from . import settings as S
        from PySide6.QtGui import QCursor
        # the screen the operator works on = the one under the mouse (two monitors here)
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if scr is None:
            return None
        s = float(S.get("ui_scale", 1.0) or 1.0)
        av, full, mm = scr.availableGeometry(), scr.geometry(), scr.physicalSize()
        _CURRENT = compute(int(av.width() * s), int(av.height() * s), mm.width(), mm.height(),
                           s, int(full.width() * s))
        _CURRENT.avail_x, _CURRENT.avail_y, _CURRENT.name = av.x(), av.y(), scr.name()
    except Exception:                                   # noqa: BLE001 — headless, odd platform
        _CURRENT = None
    return _CURRENT


def current() -> Optional[Profile]:
    return _CURRENT


def fits(geom_w: int, geom_h: int, x: int, y: int, avail) -> bool:
    """Does a remembered window rectangle still fit the available area?"""
    return (geom_w <= avail.width() + 8 and geom_h <= avail.height() + 8
            and avail.x() - 50 <= x <= avail.x() + avail.width() - 200
            and avail.y() - 50 <= y <= avail.y() + avail.height() - 100)


DESIGN_PT = 26.0          # the dialogs' fixed sizes were drawn at this text size


def k() -> float:
    """How much smaller/larger than the design text this screen's text is."""
    from . import settings as S
    return max(0.55, min(1.25, S.base_font_pt() / DESIGN_PT))


def available():
    """Available area in logical pixels: (x, y, w, h). From the measurement if any."""
    from . import settings as S
    s = float(S.get("ui_scale", 1.0) or 1.0)
    if _CURRENT is not None:
        return (_CURRENT.avail_x, _CURRENT.avail_y,
                int(_CURRENT.width_px / s), int(_CURRENT.height_px / s))
    try:
        from PySide6.QtGui import QGuiApplication
        g = QGuiApplication.primaryScreen().availableGeometry()
        return g.x(), g.y(), g.width(), g.height()
    except Exception:                                   # noqa: BLE001
        return 0, 0, 1366, 738


def fit(widget, want_w: int, want_h: int, min_w: int = 0, min_h: int = 0,
        frac_w: float = 0.92, frac_h: float = 0.90, grow: bool = True) -> tuple:
    """Size a window from its design size, scaled to this screen's text and capped
    to the available area; minimum size capped too; centred. Returns (w, h)."""
    x, y, aw, ah = available()
    f = k()
    gw, gh = (aw * 0.5, ah * 0.6) if grow else (0, 0)  # a dialog never shrinks to a stamp
    w = int(min(max(want_w * f, gw), aw * frac_w))
    h = int(min(max(want_h * f, gh), ah * frac_h))
    if min_w or min_h:
        widget.setMinimumSize(int(min(min_w * f, aw * frac_w)), int(min(min_h * f, ah * frac_h)))
    widget.resize(w, h)
    widget.move(x + (aw - w) // 2, y + (ah - h) // 2)
    return w, h
