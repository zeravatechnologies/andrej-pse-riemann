"""
Running an experiment and turning it into a COMPUTED card.

The run record is the reproducibility contract:

    vault/lab/<run_id>/
        result.json     parameters, numbers, series, timings, versions
        script.py       the exact source of the function that produced it
        *.png           plots

`script_sha256` in the card is the hash of that `script.py`. Recomputing means
re-running that source with the recorded parameters under the recorded mpmath
version. Without it the gate refuses the card, and it is right to: an unverifiable
number in a knowledge base is worse than no number, because it looks the same as
a verified one six months later.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import platform
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import mpmath as mp

from .. import config
from ..core import journal as J
from ..vault.card import Card, COMPUTED
from ..vault.gate import Verdict, gate
from . import experiments as EX
from . import plots as PL


class LabError(Exception):
    pass


def _script_source(exp: EX.Experiment) -> str:
    """The runnable provenance: the experiment function plus the zeta module."""
    from . import zeta as Z
    header = (f"# PSE Riemann — reproducible source for experiment '{exp.key}'\n"
              f"# mpmath {mp.__version__} · python {platform.python_version()}\n"
              f"# Run:  python3 script.py  (after `pip install mpmath numpy`)\n\n")
    try:
        fn = inspect.getsource(exp.run)
    except (OSError, TypeError):
        fn = f"# (source unavailable for {exp.run})\n"
    # QRH experiments depend on the method explorer, not on zeta.py — record the
    # module that actually produced the number, so the run is truly reproducible.
    if exp.key.startswith("qrh_"):
        try:
            from ..methods import core as MC
            dep = "# ---- methods/core.py ----\n" + inspect.getsource(MC)
        except (OSError, TypeError, ImportError):
            dep = ""
    else:
        try:
            dep = "# ---- zeta.py ----\n" + inspect.getsource(Z)
        except (OSError, TypeError):
            dep = ""
    return header + dep + "\n\n# ---- experiment ----\n" + fn


def validate_params(exp: EX.Experiment, params: dict) -> dict:
    out = {}
    for p in exp.params:
        v = params.get(p.name, p.default)
        try:
            v = int(v) if p.kind == "int" else float(v)
        except (TypeError, ValueError):
            raise LabError(f"parametar '{p.name}' nije broj: {v!r}")
        if v < p.lo or v > p.hi:
            raise LabError(f"parametar '{p.name}' = {v} je van opsega "
                           f"[{p.lo}, {p.hi}]")
        out[p.name] = v
    unknown = set(params) - {p.name for p in exp.params}
    if unknown:
        raise LabError(f"nepoznati parametri: {sorted(unknown)}")
    return out


def run(key: str, params: Optional[dict] = None, make_card: bool = True
        ) -> dict:
    """
    Execute one experiment end to end. Returns a dict with the run record, the
    paths that were written, and the gate verdict for the card (if requested).
    """
    exp = EX.get(key)
    if exp is None:
        raise LabError(f"nepoznat eksperiment '{key}'")
    p = validate_params(exp, params or {})

    src = _script_source(exp)
    sha = hashlib.sha256(src.encode()).hexdigest()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    phash = hashlib.sha1(json.dumps(p, sort_keys=True).encode()).hexdigest()[:6]
    run_id = f"{key}-{stamp}-{phash}"
    run_dir = config.DIR_LAB / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    try:
        res: EX.Result = exp.run(**p)
    except Exception as e:                              # noqa: BLE001
        J.log(J.LAB, "lab", {"experiment": key, "params": p,
                             "error": f"{type(e).__name__}: {e}"},
              subject=run_id, verdict="error")
        raise LabError(f"eksperiment '{key}' je pukao: {type(e).__name__}: {e}") from e
    elapsed = time.monotonic() - t0

    (run_dir / "script.py").write_text(src, encoding="utf-8")

    png_paths = []
    for i, spec in enumerate(res.plots):
        try:
            out = PL.render(spec, res.series, run_dir / f"plot{i + 1}.png")
            png_paths.append(out.name)
        except Exception as e:                          # noqa: BLE001
            res.warnings.append(f"crtanje '{spec.get('title','')}' nije uspjelo: {e}")

    record = {
        "run_id": run_id, "experiment": key, "title": exp.title,
        "params": p, "numbers": res.numbers, "reading": res.reading,
        "warnings": res.warnings, "plots": png_paths,
        # the specs too, so the Lab tab can redraw them interactively (item 29, step 6);
        # the PNGs stay — cards link to them and "Sačuvaj PNG" is always there
        "plot_specs": list(res.plots),
        "elapsed_s": round(elapsed, 3),
        "script_sha256": sha,
        "mpmath": mp.__version__, "python": platform.python_version(),
        "when": datetime.now().astimezone().isoformat(timespec="seconds"),
        # series can be large; keep them, they are the raw data
        "series": {k: v for k, v in res.series.items()},
    }
    (run_dir / "result.json").write_text(
        json.dumps(record, indent=1, default=str), encoding="utf-8")

    J.log(J.LAB, "lab",
          {"experiment": key, "params": p, "numbers": res.numbers,
           "elapsed_s": record["elapsed_s"], "sha": sha[:16],
           "warnings": res.warnings},
          subject=run_id, verdict="ok")

    out = {"record": record, "dir": str(run_dir), "verdict": None,
           "card_id": None}
    if make_card:
        v, cid = _write_card(exp, p, record, png_paths)
        out["verdict"], out["card_id"] = v, cid
    return out


def _write_card(exp: EX.Experiment, params: dict, rec: dict,
                pngs: list[str]) -> tuple[Verdict, Optional[str]]:
    pstr = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                     for k, v in params.items())
    body = [f"**Pitanje.** {exp.question}", "",
            f"**Parametri.** `{pstr}`", "",
            "**Rezultat.**", "",
            "| veličina | vrijednost |", "|---|---|"]
    for k, v in rec["numbers"].items():
        body.append(f"| `{k}` | {v} |")
    body += ["", rec["reading"]]
    if pngs:
        body.append("")
        for f in pngs:
            body.append(f"![{exp.title}](../lab/{rec['run_id']}/{f})")
    if rec["warnings"]:
        body += ["", "**Upozorenja.**"] + [f"- {w}" for w in rec["warnings"]]
    branch = EX.BRANCH_OF.get(exp.key, "numerics")
    body += ["", "---",
             f"Reproducibilnost: `lab/{rec['run_id']}/script.py`, "
             f"sha256 `{rec['script_sha256'][:16]}…`, mpmath {rec['mpmath']}, "
             f"trajanje {rec['elapsed_s']} s.",
             "", f"Grana: [[tema-{branch}]]"]

    card = Card(
        title=f"{exp.title} — {pstr}",
        type="numeric-fact",
        status=COMPUTED,
        author="lab",
        lab_run=rec["run_id"],
        script_sha256=rec["script_sha256"],
        tags=["lab", exp.key],
        confidence=1.0,
        body="\n".join(body),
    )
    v = gate().submit(card, actor="lab")
    return v, (card.id if v.ok else None)


def list_runs(limit: int = 50) -> list[dict]:
    out = []
    if not config.DIR_LAB.exists():
        return out
    for d in sorted(config.DIR_LAB.iterdir(), reverse=True):
        f = d / "result.json"
        if not f.is_file():
            continue
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({k: rec.get(k) for k in
                    ("run_id", "experiment", "title", "params", "numbers",
                     "when", "elapsed_s", "plots")})
        if len(out) >= limit:
            break
    return out


def load_run(run_id: str) -> Optional[dict]:
    f = config.DIR_LAB / run_id / "result.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def catalog() -> list[dict]:
    return [{"key": e.key, "title": e.title, "question": e.question,
             "why": e.why, "cost": e.cost,
             "params": [asdict(p) for p in e.params]} for e in EX.CATALOG]
