"""
Screenshot at any moment (round 3, item 29b; Andrej 2026-10-26).

F12 = the active window (the main window, or whichever dialog is in front),
Shift+F12 = only the active tab, 📷 in the top bar = the main window.
A PNG named pse-riemann_YYYY-MM-DD_HH-MM-SS[_tab].png goes to ~/Pictures/PSE-Riemann/
(the operator can choose another folder). No pop-up: a status-bar message with the
path and "Otvori folder". The journal records the file NAME, never the content.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

KEY = "screenshot_dir"


def default_dir() -> Path:
    from .. import config
    if config.is_packaged() and config.RESULTS_DIR != config.VAULT:
        return config.RESULTS_DIR / "snimci ekrana"          # beside the results (Andrej)
    pics = None
    try:
        out = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True,
                             timeout=2).stdout.strip()
        if out and Path(out).is_dir() and Path(out) != Path.home():
            pics = Path(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return (pics or Path.home() / "Pictures") / "PSE-Riemann"


def folder() -> Path:
    from .. import settings as S
    d = S.get(KEY) or ""
    return Path(d) if d else default_dir()


def set_folder(path: str) -> None:
    from .. import settings as S
    S.set_(KEY, str(path))


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9čćšđžČĆŠĐŽ_-]+", "-", s).strip("-")[:40]


def take(widget, label: str = "", directory: Optional[Path] = None) -> Path:
    """Grab `widget` (as drawn now) to a PNG; returns the path."""
    d = Path(directory) if directory else folder()
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    name = f"pse-riemann_{stamp}" + (f"_{_slug(label)}" if label else "") + ".png"
    p = d / name
    n = 1
    while p.exists():                                   # two shots in the same second
        n += 1
        p = d / name.replace(".png", f"_{n}.png")
    if not widget.grab().save(str(p), "PNG"):
        raise OSError(f"snimak nije zapisan: {p}")
    try:
        from ..core import journal as J
        from ..shared_lib import operator as OP
        J.log(J.SYSTEM, OP.current() or "app", {"event": "screenshot", "file": p.name,
                                                "what": label or "prozor"}, verdict="saved")
    except Exception:                                   # noqa: BLE001 — a shot never fails on the journal
        pass
    return p
