"""
Automatic machine profile (round 3, item 24).

The app knows the two machines it runs on and tunes the model limits itself:

  dell   Dell OptiPlex, Intel i5-6600(T), 4 cores / 4 threads, 16 GB
         measured 2026-10-25: DeepSeek-R1-8B Q5_K_M ≈ 0.44–0.62 s/token
  acer   Acer, Intel i3, 2 cores / 4 threads, 16 GB
         NOT measured yet — the numbers below are an estimate (about half the
         Dell's speed: half the physical cores) until the live test (item 35)

Anything else gets a profile derived from its own core count and RAM.
Override: env PSE_RIEMANN_MACHINE=dell|acer|generic (tests simulate the Acer
this way) or the setting "machine_profile" (default "auto").
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    threads: int                 # llama-cpp threads (physical cores matter)
    n_ctx: int
    think_budget: int
    max_output: int
    call_timeout_s: float
    s_per_token_L: float         # "→ ∞" ceiling for generation speed
    expected_s_per_token: float  # what "normal" looks like here
    measured: bool               # False = estimate, say so
    notes: tuple = field(default_factory=tuple)


DELL = Profile("dell", "Dell OptiPlex · i5-6600 · 4 jezgra / 16 GB", 3, 8192, 1500, 2000,
               120.0, 2.0, 0.5, True)
ACER = Profile("acer", "Acer · i3 · 2 jezgra / 4 niti / 16 GB", 2, 4096, 800, 1200,
               240.0, 4.0, 1.0, False,
               ("DeepSeek-R1-8B je na Aceru spor (procjena ~1 s po tokenu, dug <think>) — "
                "za brz rad izaberi cloud glavni AI, a DeepSeek ostavi kao skeptika.",))


def _cpuinfo() -> dict:
    model, cores, threads = "", 0, os.cpu_count() or 1
    phys = set()
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            cur = {}
            for line in f:
                if not line.strip():
                    if cur:
                        phys.add((cur.get("physical id", "0"), cur.get("core id", "0")))
                    cur = {}
                    continue
                k, _, v = line.partition(":")
                cur[k.strip()] = v.strip()
                if k.strip() == "model name" and not model:
                    model = v.strip()
            if cur:
                phys.add((cur.get("physical id", "0"), cur.get("core id", "0")))
    except OSError:
        pass
    cores = len(phys) or threads
    ram = 0.0
    try:
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    ram = int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError):
        pass
    return {"model": model, "cores": cores, "threads": threads, "ram_gb": round(ram, 1)}


def generic(info: dict) -> Profile:
    cores = max(1, info["cores"])
    small = cores <= 2
    return Profile("generic", f"{info['model'] or 'nepoznat CPU'} · {cores} jezgra",
                   max(1, cores - (0 if small else 1)), 4096 if small else 8192,
                   800 if small else 1500, 1200 if small else 2000,
                   240.0 if small else 120.0, 4.0 if small else 2.0,
                   1.0 if small else 0.5, False)


def classify(info: dict) -> Profile:
    m = (info.get("model") or "").lower()
    if re.search(r"i5-6600", m):
        return DELL
    if re.search(r"\bi3\b|i3-", m) and info.get("cores", 0) <= 2:
        return ACER
    return generic(info)


_CACHE: Optional[Profile] = None


def profile(refresh: bool = False) -> Profile:
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    forced = os.environ.get("PSE_RIEMANN_MACHINE", "")
    if not forced:
        try:
            from . import settings as S
            forced = S.get("machine_profile") or ""
        except Exception:                               # noqa: BLE001
            forced = ""
    forced = "" if forced == "auto" else forced
    info = _cpuinfo()
    _CACHE = {"dell": DELL, "acer": ACER}.get(forced) or (
        generic(info) if forced == "generic" else classify(info))
    return _CACHE


def gguf_warning(model_id: str) -> str:
    """The "kad birati" warning for a local model on this machine, or ""."""
    p = profile()
    if "deepseek" in (model_id or "").lower() and p.key == "acer":
        return p.notes[0]
    return ""
