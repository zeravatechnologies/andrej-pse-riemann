"""
Secret custody + redaction.

Two jobs:
  1. Keys live in ~/.config/pse-riemann/secrets.json, mode 0600, OUTSIDE the vault.
     The vault is meant to be readable, syncable, and shareable; a key in it would
     eventually end up in a note, a git repo, or a screenshot.
  2. redact() scrubs secret material out of ANYTHING before it is journalled,
     logged, shown in the UI, or sent to a model. It scrubs by exact value (every
     key we hold) and by shape (provider key patterns, bearer tokens, cookies),
     so a key we do not know about still gets caught.

On hostile WiFi the realistic loss is not "someone reads my notes" — it is
"my API key leaked and someone else spends it". This module is that boundary.
"""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Optional

from .. import config

REDACTED = "«REDACTED»"

# Shape-based patterns. Deliberately broad: a false redaction costs nothing,
# a missed key costs the trip.
_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),          # Anthropic
    re.compile(r"\bgsk_[A-Za-z0-9]{20,}"),              # Groq
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),           # Google / Gemini
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),               # OpenAI-compatible
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"), # Authorization headers
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*[\"']?"
               r"([A-Za-z0-9._\-]{16,})"),
]
_SENSITIVE_KEYS = {"api_key", "apikey", "key", "token", "authorization", "auth",
                   "secret", "password", "cookie", "set-cookie", "x-api-key"}


class SecretStore:
    """Reads/writes the 0600 secrets file. Values never leave via journal or UI."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or config.SECRETS_FILE)
        self._data: dict[str, str] = {}
        self._locked: set[str] = set()      # kill switch: names the app may not read
        self._had: set[str] = set()         # locked names that had a value
        self.load()

    def load(self) -> dict[str, str]:
        if self.path.exists():
            self._warn_if_loose()
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        for n in self._locked:                  # a reload must not bring them back
            if self._data.pop(n, None):
                self._had.add(n)
        return dict(self._data)

    def _warn_if_loose(self) -> None:
        try:
            mode = stat.S_IMODE(self.path.stat().st_mode)
        except OSError:
            return
        if mode & 0o077:
            # Tighten rather than merely complain.
            try:
                self.path.chmod(0o600)
            except OSError:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        tmp = self.path.with_suffix(".tmp")
        # Create with 0600 from the start — never a window where it is world-readable.
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        os.replace(tmp, self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        _refresh_known_values()

    def get(self, name: str) -> str:
        if name in self._locked:
            return ""
        return self._data.get(name, "") or os.environ.get(name, "")

    # ---- kill switch (round 3, item 12) ------------------------------- #
    def lock(self, names) -> None:
        """Take these keys out of the app's memory (file untouched)."""
        for n in names:
            self._locked.add(n)
            if self._data.pop(n, None) or os.environ.get(n):
                self._had.add(n)
        _refresh_known_values()

    def forget(self, names) -> None:
        """Remove these keys from secrets.json for good."""
        disk = {}
        if self.path.exists():
            try:
                disk = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                disk = {}
        for n in names:
            disk.pop(n, None)
        keep = self._data
        self._data = disk
        self.save()
        self._data = {k: v for k, v in keep.items() if k not in set(names)}

    def unlock(self) -> None:
        self._locked.clear()
        self._had.clear()
        self.load()
        _refresh_known_values()

    def was_locked(self, name: str) -> bool:
        return name in self._had

    def set(self, name: str, value: str) -> None:
        if value:
            self._data[name] = value
        else:
            self._data.pop(name, None)
        self.save()

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    def names(self) -> list[str]:
        return sorted(self._data.keys())

    def values(self) -> list[str]:
        return [v for v in self._data.values() if isinstance(v, str) and len(v) >= 8]


_STORE: Optional[SecretStore] = None
_KNOWN_VALUES: list[str] = []


def store() -> SecretStore:
    global _STORE
    if _STORE is None:
        _STORE = SecretStore()
        _refresh_known_values()
    return _STORE


def _refresh_known_values() -> None:
    global _KNOWN_VALUES
    vals: list[str] = []
    if _STORE is not None:
        vals.extend(_STORE.values())
    locked = _STORE._locked if _STORE is not None else set()
    for k, v in os.environ.items():
        if k in locked:
            continue
        if any(t in k.upper() for t in ("API_KEY", "TOKEN", "SECRET")) and len(v) >= 16:
            vals.append(v)
    # longest first so a prefix does not shadow a longer key
    _KNOWN_VALUES = sorted(set(vals), key=len, reverse=True)


def redact(obj: Any) -> Any:
    """Recursively scrub secrets out of strings/dicts/lists. Structure preserved."""
    if not _KNOWN_VALUES and _STORE is None:
        # Lazy: journal may fire before the store is ever opened.
        _refresh_known_values()
    if isinstance(obj, str):
        return _redact_str(obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                out[k] = REDACTED if v else v
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        t = type(obj)
        return t(redact(v) for v in obj)
    return obj


def _redact_str(s: str) -> str:
    for v in _KNOWN_VALUES:
        if v and v in s:
            s = s.replace(v, REDACTED)
    for pat in _PATTERNS:
        s = pat.sub(lambda m: (m.group(0)[:6] + REDACTED)
                    if len(m.group(0)) > 12 else REDACTED, s)
    return s


def contains_secret(s: str) -> bool:
    """True if the string carries key material — used by the egress gate."""
    if not isinstance(s, str) or not s:
        return False
    if not _KNOWN_VALUES:
        _refresh_known_values()
    if any(v and v in s for v in _KNOWN_VALUES):
        return True
    return any(p.search(s) for p in _PATTERNS)
