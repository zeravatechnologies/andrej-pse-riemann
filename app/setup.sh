#!/usr/bin/env bash
# PSE Riemann — one-time setup on THIS machine (Linux Mint host).
#
# Why a venv: Mint's system Python is PEP-668 "externally managed", so
# `pip install` into it is refused by design. The venv lives next to the app in
# app/.venv, touches nothing system-wide, and is removed by deleting that folder.
#
# Run once, at home, before the trip:
#     ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="${PSE_BASE_PYTHON:-python3}"

echo "PSE Riemann — setup"
echo "  osnovni python : $($PY -V 2>&1)  ($(command -v "$PY"))"
echo "  venv           : $(pwd)/$VENV"
echo

if ! "$PY" -c "import venv" 2>/dev/null; then
    echo "⛔ Nedostaje modul 'venv'. Instaliraj ga pa ponovi:"
    echo "     sudo apt install python3-venv"
    exit 1
fi

if [ ! -d "$VENV" ]; then
    echo "→ pravim venv…"
    "$PY" -m venv "$VENV"
fi

VPY="$VENV/bin/python"
echo "→ podižem pip…"
"$VPY" -m pip install --upgrade pip --quiet

echo "→ instaliram numpy, mpmath, matplotlib…"
"$VPY" -m pip install --quiet numpy mpmath matplotlib sympy scipy pytest

echo "→ instaliram PySide6 (prvo Essentials, ~4× manji od punog)…"
if ! "$VPY" -m pip install --quiet PySide6-Essentials; then
    echo "   Essentials nije prošao — probam puni PySide6…"
    "$VPY" -m pip install --quiet PySide6
fi

# Opciono: lokalni GGUF skeptik (F3). Nije obavezno — bez njega radi oblak ili
# samo determinističke provjere. CPU wheel (bez kompajliranja). PSE_SKIP_GGUF=1 preskače.
if [ "${PSE_SKIP_GGUF:-}" != "1" ]; then
    echo "→ (opciono) llama-cpp-python za lokalni GGUF…"
    "$VPY" -m pip install --quiet --only-binary :all: \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
        llama-cpp-python || echo "   llama-cpp nije instaliran (preskačem — nije obavezno)"
fi

echo
echo "→ provjera:"
"$VPY" - <<'PY'
import importlib, sys
ok = True
for mod, what in (("PySide6.QtWidgets", "GUI"),
                  ("PySide6.QtSvg", "SVG (tabla)"),
                  ("mpmath", "numerika"),
                  ("numpy", "nizovi"),
                  ("matplotlib", "grafici")):
    try:
        importlib.import_module(mod)
        print(f"   ✅ {mod:22s} {what}")
    except Exception as e:
        ok = False
        print(f"   ⛔ {mod:22s} {type(e).__name__}: {e}")
print()
print("✅ Spremno." if ok else "⛔ Nešto nedostaje — vidi gore.")
sys.exit(0 if ok else 1)
PY

echo
echo "Sad pokreni:"
echo "     ./run.sh --selftest"
echo "     ./run.sh"
