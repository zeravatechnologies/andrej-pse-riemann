"""
The method explorer (plan F8, master §0.5.4 — the "open door").

A QRH "method" is a proof strategy that excludes zeros of ζ (and the Dirichlet /
Hecke L-functions) in a half-plane Re s > B. The number B is not pulled from the
L-functions themselves but from where two EXPONENT functions из the proof cross:
a low-side estimate and a high-side estimate. This package is the machinery that,
given a method's exponent family E(δ, x; ℓ, b, κ):

    core        computes V(ℓ)=max_{δ,x} E, the optimum B*, the exact minimal
                polynomial of B* (sympy, resultants — validated on Liu's cubic),
                the transform T between two methods, its t/w extensions, the
                admissibility walls, and a verdict closer / farther / wall
    registry    the known methods (the common line, Liu, Xu–Sang) as data
    pack        the method-pack file format and its mandatory reproduction test
    door        the ONLY way a method enters: through the gate, reproduction test
                first, then the human queue ("Čeka tvoju odluku")

The deterministic reproduction test — not any model — decides whether a method
pack is admitted. A pack whose recipe does not reproduce the number its paper
claims is refused at the door.
"""
from .registry import MethodSpec, KNOWN, by_name
from .pack import MethodPack, reproduce, PackError
from .door import import_pack, install_hooks
from . import core

__all__ = ["MethodSpec", "KNOWN", "by_name", "MethodPack", "reproduce",
           "PackError", "import_pack", "install_hooks", "core"]
