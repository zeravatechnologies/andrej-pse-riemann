#!/usr/bin/env python3
"""
PSE audit (Faza 6d, rule 25: "samo PSE native"): no agent may reach a model, θ
or the Doctor outside its PSE unit. Prints every old entry point it finds and
exits 1 if there is any; exit 0 = clean. Run: python3 tools/pse_audit.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
SRC = [ROOT / "pse_r", ROOT / "main.py"]

# (pattern, why, files allowed to contain it)
RULES = [
    (r"router\(\)\.call\(", "poziv modela mimo jedinice (Router.call je uklonjen)", ()),
    (r"router\(\)\.skeptic\(", "stari skeptik mimo jedinice", ()),
    (r"\.unit_call\(", "unit_call smije zvati samo put jedinice", ("pse/path.py", "llm/router.py")),
    (r"\.sensor_call\(", "čitač je senzor SHARED_LIB-a", ("pse/path.py", "llm/router.py")),
    (r"role_backend\(", "direktan backend mimo jedinice", ()),
    (r"core\.theta|core import theta|TH\.record|TH\.meter", "globalni θ (θ je po jedinici)", ()),
    (r"check_output\(|is_contained\(", "stari lanac dijagnoza/liječenje", ()),
    (r"guardian\.healing|guardian import healing|guardian\.diagnosis|guardian import diagnosis",
     "stari Fizičar (sada Doktor u pse/doctor.py)", ()),
    (r"\bFizičar\b|\bFizicar\b", "ime je Doktor (pravilo 11)", ()),
    (r"\.chat\(", "direktan poziv backenda",
     ("llm/router.py", "llm/backend.py", "llm/gguf.py", "llm/selection.py", "llm/providers.py")),
    (r"backend_for\(|B\.make\(", "pravljenje backenda van rutera",
     ("llm/router.py", "llm/backend.py", "llm/gguf.py", "llm/selection.py", "llm/providers.py")),
    (r"_write\(U\._METER|_METER\b", "θ piše samo mjerač SHARED_LIB-a",
     ("pse/unit.py", "shared_lib/pse_registry.py")),
]


def scan() -> list:
    hits = []
    files = []
    for s in SRC:
        files += [s] if s.is_file() else sorted(s.rglob("*.py"))
    for f in files:
        rel = f.relative_to(ROOT / "pse_r").as_posix() if "pse_r" in f.parts else f.name
        txt = f.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(txt.splitlines(), 1):
            code = line.split("#", 1)[0]
            if not code.strip() or code.strip().startswith(('"', "'")):
                continue
            for pat, why, allowed in RULES:
                if re.search(pat, code) and rel not in allowed:
                    hits.append((rel, i, why, line.strip()[:120]))
    return hits


def main() -> int:
    hits = scan()
    for rel, i, why, line in hits:
        print(f"{rel}:{i}: {why}\n    {line}")
    print(f"\nPSE revizija: {len(hits)} starih ulaza" + (" — ČISTO" if not hits else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
