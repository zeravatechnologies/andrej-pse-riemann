"""
The operator — whoever is using the app. They type a name and that is all
(decision 2026-10-25: no password). The name is bound to every journal event,
every decision in the human queue and every report.

The voice of SHARED_LIB speaks ONLY to a registered operator. Until a name is
set, anything that needs one raises NoOperator.
"""
from __future__ import annotations

import re
from typing import Optional

from .. import settings as S

_NAME_RE = re.compile(r"^[\w .'\-ČĆŽŠĐčćžšđ]{2,40}$", re.UNICODE)
_CURRENT: Optional[str] = None


class NoOperator(Exception):
    pass


def valid_name(name: str) -> bool:
    return bool(_NAME_RE.match((name or "").strip()))


def set_operator(name: str) -> str:
    """Register the operator for this session. Remembered as the default next time."""
    global _CURRENT
    name = (name or "").strip()
    if not valid_name(name):
        raise ValueError("ime operatera: 2–40 slova, brojeva, razmaka, . ' -")
    _CURRENT = name
    S.set_("operator_name", name)
    from ..core import journal as J
    J.log(J.SYSTEM, "operator", {"event": "operator_set", "operator": name})
    return name


def current() -> Optional[str]:
    """The operator of THIS session (None until set). Never guessed from settings."""
    return _CURRENT


def last_used() -> str:
    """Pre-fill for the name prompt."""
    return S.get("operator_name", "") or ""


def require_operator() -> str:
    if not _CURRENT:
        raise NoOperator("nema registrovanog operatera — upiši ime pri pokretanju")
    return _CURRENT


def _reset_for_tests() -> None:
    global _CURRENT
    _CURRENT = None
