#!/usr/bin/env bash
# PSE Riemann launcher.
#
# Picks an interpreter that actually has the dependencies, in this order:
#   1. $PSE_PYTHON              — you override it explicitly
#   2. app/.venv/bin/python     — what ./setup.sh creates (the normal case)
#   3. python3 on PATH          — only if it can import everything
# and if none of them can, it says exactly what to run instead of dying on a
# traceback. On Mint the system Python is PEP-668 locked, so (2) is the answer.
set -euo pipefail
cd "$(dirname "$0")"

need_check() {
    "$1" - <<'PY' >/dev/null 2>&1
import PySide6.QtWidgets, PySide6.QtSvg, mpmath, numpy, matplotlib
PY
}

PY=""
if [ -n "${PSE_PYTHON:-}" ] && [ -x "${PSE_PYTHON}" ]; then
    PY="${PSE_PYTHON}"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1 && need_check python3; then
    PY="python3"
fi

# Headless modes don't need Qt — let them run on a bare python if that is all
# there is, so --selftest and --lab still work when the GUI stack is missing.
if [ -z "$PY" ] && [ "${1:-}" != "" ]; then
    case "${1}" in
        --selftest|--lab|--harvest|--briefing|--report)
            if command -v python3 >/dev/null 2>&1 && \
               python3 -c "import mpmath" >/dev/null 2>&1; then
                PY="python3"
            fi
            ;;
    esac
fi

if [ -z "$PY" ]; then
    cat <<'MSG'
⛔ Nedostaju biblioteke (PySide6 / mpmath / numpy / matplotlib).

   Pokreni jednom, ovdje:

       ./setup.sh

   To pravi venv u app/.venv i instalira sve u njega. Ništa se ne dira
   sistemski — Mint blokira pip u sistemski Python (PEP 668), pa je venv
   jedini ispravan put. Brisanje foldera app/.venv poništava sve.

   Ako već imaš python sa svim potrebnim:

       PSE_PYTHON=/putanja/do/python ./run.sh
MSG
    exit 1
fi

exec "$PY" main.py "$@"
