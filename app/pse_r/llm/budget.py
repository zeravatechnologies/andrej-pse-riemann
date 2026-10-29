"""
Token and cost meter with a hard daily stop.

Twenty days on the road with four API keys is exactly the situation where a
runaway loop quietly spends a month's budget overnight. So the cap is a hard
stop, not a warning: `check()` raises before the request is made.

Honesty about prices: only the Anthropic rates below are authoritative (verified
against the current model table). Groq, Mistral and Gemini are used here on
their free tiers, where the constraint is a request/token quota rather than a
dollar amount — they are recorded at 0.0 and labelled as such rather than given
an invented price. If you move any of them to a paid tier, put the real number
in `PRICES` instead of guessing.
"""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from .. import config
from ..core import journal as J

# USD per million tokens: (input, output)
PRICES: dict[str, tuple[float, float]] = {        # Anthropic table, cached 2026-10-06
    "claude-fable-5-1": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
}
# Other providers: the operator enters the real price (Postavke → cijene,
# settings "prices": {provider: [in, out]} USD per 1M tokens). No invented numbers.
FREE_TIER = {"groq", "mistral", "gemini"}      # quota-limited, not dollar-limited

DEFAULT_DAILY_CAP_USD = 5.00


class Budget:
    def __init__(self, path: Optional[Path] = None,
                 daily_cap: float = DEFAULT_DAILY_CAP_USD):
        self.path = Path(path or config.BUDGET_STORE)
        self.daily_cap = daily_cap
        self._lock = threading.RLock()
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------ #
    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._data.setdefault("days", {})
        self.daily_cap = float(self._data.get("daily_cap", self.daily_cap))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data["daily_cap"] = self.daily_cap
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _today(self) -> dict:
        key = date.today().isoformat()
        return self._data["days"].setdefault(
            key, {"usd": 0.0, "calls": 0, "by_provider": {}, "by_role": {}})

    # ------------------------------------------------------------------ #
    @staticmethod
    def price(model: str, in_tok: int, out_tok: int, provider: str = "") -> float:
        p = PRICES.get(model)
        if p is None and provider:
            try:
                from .. import settings as S
                op = (S.load().get("prices") or {}).get(provider)
                if op:
                    p = (float(op[0]), float(op[1]))
            except Exception:                           # noqa: BLE001
                p = None
        if p is None:
            # unknown / free-tier model: no dollar figure invented
            return 0.0
        return (in_tok / 1e6) * p[0] + (out_tok / 1e6) * p[1]

    @staticmethod
    def worst_case_out(provider: str, reply_out: int, max_tokens: int, cut: bool,
                       usage_reported: bool) -> int:
        """Item 11: what to COUNT. A provider that bills the full completion on a
        hang-up is charged max_tokens when we cut it; a reply without usage
        numbers is charged max_tokens too. Never less than what was reported."""
        from . import providers as P
        if not usage_reported:
            return max(reply_out, max_tokens)
        if cut and not P.cancel_stops_billing(provider):
            return max(reply_out, max_tokens)
        return reply_out

    def check(self, provider: str) -> None:
        """Raise before spending if the daily cap is already reached."""
        if provider in FREE_TIER:
            return
        with self._lock:
            spent = self._today()["usd"]
        if spent >= self.daily_cap:
            raise BudgetExceeded(
                f"dnevni limit ${self.daily_cap:.2f} je dostignut (potrošeno "
                f"${spent:.2f}). Plaćeni pozivi su zaustavljeni do sutra — "
                f"besplatni provajderi (Groq/Mistral/Gemini) i dalje rade. "
                f"Limit mijenjaš u Postavkama.")

    def record(self, provider: str, model: str, role: str,
               in_tok: int, out_tok: int, worst_case: bool = False) -> float:
        usd = self.price(model, in_tok, out_tok, provider)
        with self._lock:
            d = self._today()
            d["usd"] = round(d["usd"] + usd, 6)
            d["calls"] += 1
            bp = d["by_provider"].setdefault(
                provider, {"usd": 0.0, "in": 0, "out": 0, "calls": 0})
            bp["usd"] = round(bp["usd"] + usd, 6)
            bp["in"] += in_tok
            bp["out"] += out_tok
            bp["calls"] += 1
            br = d["by_role"].setdefault(role, {"calls": 0, "usd": 0.0})
            br["calls"] += 1
            br["usd"] = round(br["usd"] + usd, 6)
            self.save()
        J.log(J.MODEL, f"model:{provider}",
              {"model": model, "role": role, "in": in_tok, "out": out_tok,
               "usd": round(usd, 6), "free_tier": provider in FREE_TIER,
               "worst_case": worst_case},
              subject=provider)
        return usd

    # ------------------------------------------------------------------ #
    def today(self) -> dict:
        with self._lock:
            return dict(self._today())

    def status_line(self) -> str:
        """
        What was SPENT today, never what is left. The earlier wording
        ("2 poziva (2 besplatnih)") read like an allowance of two calls, which
        it never was — so the label now says "danas" out loud and puts the
        counter after the money.
        """
        d = self.today()
        free_calls = sum(v["calls"] for p, v in d["by_provider"].items()
                         if p in FREE_TIER)
        paid_calls = d["calls"] - free_calls
        from ..i18n import tr
        return tr("danas ${0:.2f} od ${1:.2f} · {2} poziva ({3} bespl. / {4} plać.)").format(
            d["usd"], self.daily_cap, d["calls"], free_calls, paid_calls)

    def tooltip(self) -> str:
        from ..i18n import tr
        d = self.today()
        lines = [tr("Potrošeno DANAS (nije preostalo — potrošeno)."), "",
                 tr("Dnevni limit vrijedi samo za plaćene provajdere: ${0:.2f}.").format(self.daily_cap), ""]
        if d["by_provider"]:
            lines.append(tr("Po provajderu:"))
            for p, v in sorted(d["by_provider"].items()):
                tag = tr("besplatan tier") if p in FREE_TIER else f"${v['usd']:.4f}"
                lines.append(tr("  {0}: {1} poziva · {2} · {3}→{4} tokena").format(
                    p, v["calls"], tag, v["in"], v["out"]))
        else:
            lines.append(tr("Danas još nijedan poziv."))
        if any(p in FREE_TIER for p in d["by_provider"]):
            lines += ["", tr("Besplatni tierovi (Groq/Gemini/Mistral) imaju kvotu po zahtjevima i "
                             "tokenima koju vodi sam provajder — ova aplikacija je ne vidi i ne "
                             "broji. Ako te odbiju, to je njihova kvota, ne ovaj limit.")]
        lines += ["", tr("Ukupno od početka: ${0:.2f}").format(self.total())]
        return "\n".join(lines)

    def history(self, days: int = 20) -> list[tuple[str, float]]:
        with self._lock:
            items = sorted(self._data["days"].items())
        return [(k, v["usd"]) for k, v in items][-days:]

    def total(self) -> float:
        with self._lock:
            return round(sum(v["usd"] for v in self._data["days"].values()), 4)

    def set_cap(self, usd: float) -> None:
        with self._lock:
            self.daily_cap = max(0.0, float(usd))
            self.save()


class BudgetExceeded(Exception):
    pass


_B: Optional[Budget] = None


def budget() -> Budget:
    global _B
    if _B is None:
        _B = Budget()
    return _B
