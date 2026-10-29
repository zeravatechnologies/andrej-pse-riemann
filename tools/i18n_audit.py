#!/usr/bin/env python3
"""
Interface language audit (Faza 6d R4, agreement rule 34): the interface must be
correct in Serbian AND in English. Finds
  1. strings passed through tr() that have no English yet,
  2. text handed straight to a widget without tr() (would stay Serbian in EN),
  3. f-strings handed to a widget (cannot be translated; use tr("…{0}").format()).
Exit 1 when anything is found. Run: python3 tools/i18n_audit.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "pse_r"
sys.path.insert(0, str(ROOT.parent))

UI_FUNCS = {"QLabel", "button", "small", "QPushButton", "QCheckBox", "QGroupBox",
            "QRadioButton", "QAction", "status_chip"}
UI_METHODS = {"setText", "setToolTip", "setPlaceholderText", "setWindowTitle", "addItem",
              "addItems", "setTabToolTip", "information", "warning", "question", "critical",
              "setHorizontalHeaderLabels", "addTab", "setTitle", "addMenu", "addAction",
              "showMessage", "getText", "getItem", "getMultiLineText"}
WORD = re.compile(r"[A-Za-zČĆŽŠĐčćžšđ]{3,}")
# technical strings that are the same in both languages
SAME = re.compile(r"^(SQL|PNG|SVG|CSV|JSON|GGUF|URL|API|SHARED_LIB|PSE[- ]?L?|arXiv|DOI|"
                  r"Claude|Gemini|OpenAI|Groq|Mistral|DeepSeek|xAI|OpenRouter|Together|"
                  r"Fireworks|Ctrl\S*|F\d+|OK|θ.*|σ.*|ζ.*|B\*.*|SR \| EN|.*\.(png|svg|csv|md|json)|"
                  r"#[0-9a-fA-F]{3,8}|https?://\S+|PSE Riemann.*|.* / interface language.*)$")


def _is_text(node) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        v = re.sub(r"<[^>]+>", " ", node.value).strip()
        return bool(WORD.search(v)) and not SAME.match(v)
    return False


def _tr_wrapped(node) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"


def scan() -> list:
    hits = []
    for p in sorted((ROOT / "gui").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            name = (n.func.id if isinstance(n.func, ast.Name) else
                    n.func.attr if isinstance(n.func, ast.Attribute) else "")
            if name not in UI_FUNCS and name not in UI_METHODS:
                continue
            args = list(n.args)
            for a in args:
                items = a.elts if isinstance(a, (ast.List, ast.Tuple)) else [a]
                for x in items:
                    if _tr_wrapped(x):
                        continue
                    if _is_text(x):
                        hits.append((rel, x.lineno, "bez tr()", x.value[:80]))
                    elif isinstance(x, ast.JoinedStr):
                        lit = "".join(v.value for v in x.values if isinstance(v, ast.Constant))
                        if WORD.search(re.sub(r"<[^>]+>", " ", lit)):
                            hits.append((rel, x.lineno, "f-string bez tr()", lit[:80]))
    return hits


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import i18n_collect
    from pse_r.i18n_en import EN
    live = i18n_collect.collect()                      # what the code uses NOW
    miss = [s for s in live if s not in EN]
    for s in live:
        if s in EN and sorted(re.findall(r"\{[^}]*\}", s)) != sorted(re.findall(r"\{[^}]*\}", EN[s])):
            miss.append(f"(polja se ne poklapaju) {s}")
    for s in miss:
        print(f"bez EN prevoda: {s[:100]}")
    hits = scan()
    for rel, ln, why, txt in hits:
        print(f"{rel}:{ln}: {why}: {txt}")
    n = len(miss) + len(hits)
    print(f"\nRevizija jezika: {len(miss)} bez prevoda, {len(hits)} van tr()" +
          (" — ČISTO" if not n else ""))
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
