"""
SR/EN for the whole interface (round 3, item 23).

Serbian (ijekavian, Latin) is the source language. `tr(text)` returns the
English translation when the interface language is "en", otherwise the text
unchanged. Text with values uses a template: `tr("Čeka tvoju odluku: {0}").format(n)`.
A missing translation shows the Serbian text (never an empty label), and the
selftest lists how many are missing.

The language is a setting ("lang"); the top bar switch changes it and reopens
the window. Critical messages (guardian/templates.py) have their own fixed
English templates — they are never translated on the fly.
"""
from __future__ import annotations

from typing import Optional

_LANG: Optional[str] = None


def lang() -> str:
    global _LANG
    if _LANG is None:
        try:
            from . import settings as S
            _LANG = S.get("lang") or "sr"
        except Exception:                               # noqa: BLE001
            _LANG = "sr"
    return _LANG


def set_lang(code: str) -> None:
    global _LANG
    if code not in ("sr", "en"):
        raise ValueError("jezik: sr ili en")
    from . import settings as S
    S.set_("lang", code)
    _LANG = code


def tr(text: str) -> str:
    if lang() != "en" or not text:
        return text
    from .i18n_en import EN
    return EN.get(text, text)


def missing() -> list[str]:
    """Interface strings that have no English yet (for the selftest)."""
    from .i18n_en import EN
    from .i18n_strings import STRINGS
    return [s for s in STRINGS if s not in EN]
