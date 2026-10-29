"""
The look, taken from Svarog's console (andrejristic/svarog, webapp/index.html):
a dark slate base, layered panels, one warm amber accent, pill-shaped tabs and
status pills, rounded cards, and semantic green / amber / red for state.

Everything visual reads from PALETTE, so the whole app changes in one place.
"""
from __future__ import annotations

PALETTE = {
    "bg": "#12151d", "panel": "#171b25", "panel2": "#1a1f2b", "panel3": "#222a37",
    "line": "#262d3a", "field": "#12151b",
    "txt": "#e9ecf3", "muted": "#9aa4b5", "faint": "#6b7585",
    "accent": "#ffc257", "accent_soft": "#ffcf7a", "accent_bg": "#2a2211",
    "accent_ink": "#3a2a06",
    "blue": "#86b3ff", "blue_bg": "#16233a",
    "ok": "#74d79a", "ok_bg": "#15301f",
    "warn": "#ffcc7a", "warn_bg": "#302611",
    "danger": "#f49090", "danger_bg": "#301618",
}

_QSS = """
QWidget {{ background:{bg}; color:{txt}; font-size:{fs:.1f}pt; }}
QMainWindow, QDialog {{ background:{bg}; }}
QToolTip {{ background:{panel3}; color:{txt}; border:1px solid {line}; padding:4px 8px; }}

/* tabs as pills (Svarog .tabs/.tab) */
QTabWidget::pane {{ border:1px solid {line}; border-radius:12px; background:{panel};
                   top:-1px; }}
QTabBar {{ background:{bg}; }}
QTabBar::tab {{ background:transparent; color:{muted}; padding:6px 14px; margin:3px 2px;
               border:none; border-radius:8px; font-weight:500; }}
QTabBar::tab:selected {{ background:{accent_bg}; color:{accent}; }}
QTabBar::tab:hover:!selected {{ color:{txt}; }}

/* fields (Svarog input/textarea/select) */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background:{field}; border:1px solid {line}; border-radius:9px; padding:5px 9px;
    selection-background-color:{accent_bg}; selection-color:{accent}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border:1px solid {accent}; }}
QComboBox QAbstractItemView {{ background:{panel2}; border:1px solid {line};
    selection-background-color:{accent_bg}; selection-color:{accent}; }}

/* buttons (Svarog button / .primary / .go / .no) */
QPushButton {{ background:{panel3}; color:{txt}; border:1px solid #333c4c;
              border-radius:9px; padding:5px 13px; font-weight:500; }}
QPushButton:hover {{ background:#2a3242; }}
QPushButton:disabled {{ color:{faint}; background:{panel2}; }}
QPushButton[kind="primary"] {{ background:{accent}; color:{accent_ink}; border:none;
                              font-weight:600; }}
QPushButton[kind="primary"]:hover {{ background:{accent_soft}; }}
QPushButton[kind="go"] {{ background:{ok_bg}; color:{ok}; border:none; }}
QPushButton[kind="go"]:hover {{ background:#1a3a27; }}
QPushButton[kind="no"] {{ background:{danger_bg}; color:{danger}; border:none; }}
QPushButton[kind="no"]:hover {{ background:#3a1c1c; }}

QListWidget, QTreeWidget, QTableWidget {{ background:{panel2}; border:1px solid {line};
    border-radius:10px; }}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background:{accent_bg}; color:{accent}; }}
QHeaderView::section {{ background:{panel3}; color:{muted}; border:none; padding:4px 8px; }}

QScrollBar:vertical {{ background:{bg}; width:10px; }}
QScrollBar::handle:vertical {{ background:{panel3}; border-radius:5px; min-height:24px; }}
QScrollBar:horizontal {{ background:{bg}; height:10px; }}
QScrollBar::handle:horizontal {{ background:{panel3}; border-radius:5px; min-width:24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}

QSplitter::handle {{ background:{line}; }}
QSplitter::handle:horizontal {{ width:7px; }}
QSplitter::handle:vertical {{ height:7px; }}
QSplitter::handle:hover {{ background:{accent}; }}

QStatusBar {{ background:{panel2}; color:{muted}; border-top:1px solid {line}; }}
QGroupBox {{ border:1px solid {line}; border-radius:12px; margin-top:10px; padding-top:10px;
            background:{panel2}; }}
QGroupBox::title {{ subcontrol-origin:margin; left:10px; color:{accent}; }}

/* Svarog building blocks */
QFrame#topbar {{ background:{panel2}; border-bottom:1px solid {line}; }}
QLabel#title {{ font-weight:600; font-size:{fs_title:.1f}pt; background:transparent; }}
QFrame#card {{ background:{panel2}; border:1px solid {line}; border-radius:12px; }}
QFrame#metric {{ background:{panel2}; border:1px solid {line}; border-radius:12px; }}
QLabel#metricK {{ color:{muted}; font-size:{fs_small:.1f}pt; background:transparent; }}
QLabel#metricV {{ font-size:{fs_big:.1f}pt; font-weight:600; background:transparent; }}
QLabel#cardH {{ font-weight:600; background:transparent; }}
"""

PILL = ("QLabel {{ background:{bg}; color:{fg}; border:1px solid {bd}; border-radius:11px;"
        " padding:2px 11px; font-size:{fs:.1f}pt; font-weight:500; }}")


def qss(font_pt: float) -> str:
    return _QSS.format(fs=font_pt, fs_title=font_pt * 1.05, fs_small=font_pt * 0.82,
                       fs_big=font_pt * 1.6, **PALETTE)


def pill_style(kind: str, font_pt: float) -> str:
    """kind: ok | warn | danger | info | plain (Svarog .pill / .pill.ok / .pill.warn)."""
    P = PALETTE
    bg, fg, bd = {
        "ok": (P["ok_bg"], P["ok"], P["ok_bg"]),
        "warn": (P["accent_bg"], P["accent"], P["accent_bg"]),
        "danger": (P["danger_bg"], P["danger"], P["danger_bg"]),
        "info": (P["blue_bg"], P["blue"], P["blue_bg"]),
        "plain": ("transparent", P["muted"], P["line"]),
    }.get(kind, ("transparent", P["muted"], P["line"]))
    return PILL.format(bg=bg, fg=fg, bd=bd, fs=font_pt * 0.8)
