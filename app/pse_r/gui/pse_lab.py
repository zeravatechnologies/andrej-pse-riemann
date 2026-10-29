"""
Tab "Laboratorija" (Faza 6d, rule 26) and the dialog "SHARED_LIB → Težine glasova"
(rule 17).

The Laboratory shows every PSE unit — test units and the real agents — with its
θ, attractor and state, and lets the operator act on them: a test move, fission,
fusion, sending the Doctor, freeze / unfreeze, the death of a unit, and undoing a
fission or fusion (through "Čeka tvoju odluku"). It ACTS ON THE REAL AGENTS:
opening it sounds a 3-second alarm (first time in a session only) and a red
banner stays while the tab is open. Every action is journalled as
"operater, iz laboratorije".
"""
from __future__ import annotations

import io
import math
import struct
import subprocess
import threading
import wave

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView)

from ..core import journal as J
from ..i18n import tr
from .widgets import MarkdownView, button, flow_row, hline

ACTOR = "operater, iz laboratorije"
DOC_STATUS = {"ceka": "mjera čeka", "nista": "ništa loše", "odobreno": "odobreno",
              "odbijeno": "odbijeno", "zamrznuta-dok-mjera-ceka": "zamrznuta dok mjera čeka",
              "tendencija": "teži ka (meki znak)",
              "ukinuto-ponovni-pregled": "ukinuto (ponovni pregled)"}
_BEEPED = False                       # once per session (process)


def _tone_wav(seconds: float = 3.0, freq: float = 1760.0, rate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(32000 * math.sin(2 * math.pi * freq * i / rate)))
                               for i in range(n)))
    return buf.getvalue()


def alarm() -> str:
    """3 s loud beep, first time in the session only. Returns how it sounded."""
    global _BEEPED
    if _BEEPED:
        return "već-bilo"
    _BEEPED = True
    import os
    if os.environ.get("PSE_RIEMANN_SILENT"):            # tests / automatic screenshots
        J.log(J.UNIT, ACTOR, {"event": "lab_opened", "alarm": "tiho (PSE_RIEMANN_SILENT)"},
              subject="laboratorija")
        return "tiho"

    def play():
        try:
            p = subprocess.run(["aplay", "-q", "-"], input=_tone_wav(), timeout=6,
                               capture_output=True)
            if p.returncode == 0:
                return
        except Exception:                               # noqa: BLE001
            pass
        for _ in range(6):                              # no audio device: system beeps
            QApplication.beep()
    threading.Thread(target=play, name="lab-alarm", daemon=True).start()
    J.log(J.UNIT, ACTOR, {"event": "lab_opened", "alarm": True}, subject="laboratorija")
    return "zvuk"


def _reader_line(uid: str) -> str:
    """Rule 48 d: the reader's state on the unit's last 30 moves — a cut JSON
    is shown, never silently counted as "no reader"."""
    import json as _json
    from ..shared_lib.store import store
    notes = []
    for r in store().rows("SELECT reading FROM pse_moves WHERE unit_id=? ORDER BY id DESC "
                          "LIMIT 30", (uid,)):
        try:
            notes.append((_json.loads(r["reading"] or "{}") or {}).get("note", ""))
        except ValueError:
            notes.append("")
    if not notes:
        return tr("**Čitač:** još nema poteza")
    cut = sum(1 for n in notes if n == "čitač odsječen")
    none = sum(1 for n in notes if n == "bez čitača")
    last = notes[0] or tr("pročitao")
    line = tr("**Čitač (zadnji potez):** {0} · zadnjih {1}: odsječen {2}, bez čitača {3}").format(
        tr(last), len(notes), cut, none)
    return ("⚠ " + line) if cut else line


def _lib():
    from ..shared_lib.pse_registry import pse
    return pse()


class LabTab(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        self.banner = QLabel(tr("⚠ LABORATORIJA AKTIVNA — utiče na prave agente"))
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setStyleSheet("background:#b3261e;color:white;font-weight:bold;"
                                  "padding:8px;border-radius:6px;")
        v.addWidget(self.banner)
        v.addWidget(flow_row(
            button(tr("Nova probna jedinica"), self._new_lab),
            button(tr("Probni potez: provjeren"), lambda: self._test_move("ok")),
            button(tr("Probni potez: bez provjere"), lambda: self._test_move("c")),
            button(tr("Probni potez: odbija bez razloga"), lambda: self._test_move("n")),
            button(tr("Osvježi"), self.refresh)))
        v.addWidget(flow_row(
            button(tr("Fisija"), self._fission), button(tr("Fuzija (dvije označene)"), self._fusion),
            button(tr("Pošalji Doktora"), self._doctor), button(tr("Zamrzni"), self._freeze),
            button(tr("Odmrzni"), self._unfreeze), button(tr("Smrt jedinice"), self._kill, kind="no"),
            button(tr("Poništi fisiju/fuziju…"), self._undo)))
        v.addWidget(hline())
        split = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([tr("jedinica"), tr("agent"), tr("θ"), tr("obrazac"),
                                              tr("stanje"), tr("vijek"), tr("gen."), tr("proba")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._show)
        split.addWidget(self.table)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.view = MarkdownView()
        rv.addWidget(self.view, 2)
        rv.addWidget(QLabel(tr("<b>Dnevnik Doktora</b>")))
        self.doc = QListWidget()
        rv.addWidget(self.doc, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        v.addWidget(split, 1)
        self.state = QLabel("")
        v.addWidget(self.state)

    # ------------------------------------------------------------------ #
    def opened(self) -> None:
        """Called when the tab becomes visible."""
        how = alarm()
        self.state.setText(tr("Alarm: {0}").format(tr(how)))
        self.refresh()

    def refresh(self) -> None:
        rows = [r for r in _lib().state() if r["alive"]]
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            st = ("❄ zamrznuta" if r["frozen"] else "⏳ mjera čeka" if r["restricted"]
                  else "radi")
            vals = [r["unit"], r["agent"], f"{r['theta']:.1f}", r["attractor"] or "—", st,
                    "∞" if r["steps_remaining"] is None else str(r["steps_remaining"]),
                    str(r["generation"]), "da" if r["lab"] else ""]
            for j, val in enumerate(vals):
                it = QTableWidgetItem(tr(val) if j == 4 else val)
                if j == 0:
                    it.setData(Qt.UserRole, r["unit"])
                self.table.setItem(i, j, it)
        self.table.resizeColumnsToContents()
        self.doc.clear()
        from ..shared_lib.store import store
        for d in store().rows("SELECT * FROM pse_doctor ORDER BY id DESC LIMIT 60"):
            self.doc.addItem(QListWidgetItem(
                f"{d['unit_id']} · {tr(DOC_STATUS.get(d['status'], d['status']))} · "
                f"{d['measure'] or '—'} · {d['triggers']}"))

    def _selected(self) -> list:
        lib = _lib()
        out = []
        for idx in sorted({i.row() for i in self.table.selectedIndexes()}):
            uid = self.table.item(idx, 0).data(Qt.UserRole)
            u = lib.units.get(uid)
            if u is None:
                rows = lib.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))
                u = lib._load(rows[0]) if rows else None
            if u is not None:
                out.append(u)
        return out

    def _show(self) -> None:
        sel = self._selected()
        if not sel:
            self.view.set_markdown("")
            return
        u = sel[0]
        rep = _lib().assess(u)              # rules 50–53: only AI-read moves
        ser = u.theta.series[-30:]
        spark = " ".join(f"{x:.0f}" for x in ser)
        md = [f"### {u.unit_id}",
              tr("**Misija:** {0} → {1} → {2}").format(*(tr(x) for x in u.core.mission.as_dict().values())),
              tr("**θ:** {0:.2f} · σ(RMSSD) {1:.2f} · obrazac **{2}**").format(
                  u.theta.current, rep.sigma, rep.attractor),
              tr("**θ zadnjih 30:** {0}").format(spark or "—"),
              tr("**Atraktor iz poteza sa AI čitačem:** {0} od {1} poteza · okreta u prozoru: {2}").format(
                  len(u.theta.attr_series), len(u.theta.series), rep.turns),
              (tr("**Teži ka:** {0} za ~{1} poteza — {2}").format(rep.tend, rep.tend_in, tr(rep.tend_why))
               if rep.tend else tr("**Teži ka:** — (nema tendencije)")),
              tr("**Granica:** {0}").format(", ".join(f"{k} ({e.alpha:.2f})"
                                                      for k, e in u.boundary.entities.items()) or "—"),
              tr("**Organeli:** {0}").format(", ".join(f"{k} ({o.weight:.2f}{', privremen' if o.provisional else ''})"
                                                       for k, o in u.organelles.items.items()) or "—"),
              tr("**Stanje:** {0}").format(u.freeze_reason or (tr("⏳ mjera čeka") if u.restricted else tr("radi"))),
              _reader_line(u.unit_id),
              "", "```", "\n".join(rep.reasons) or "—", "```"]
        self.view.set_markdown("\n\n".join(md))

    # ------------------------------------------------------------------ #
    def _log(self, what: str, uid: str) -> None:
        J.log(J.UNIT, ACTOR, {"event": "lab_action", "action": what, "unit": uid},
              subject=uid, verdict=what)

    def _done(self, msg: str) -> None:
        self.state.setText(msg)
        self.refresh()
        self.changed.emit()

    def _new_lab(self):
        lib = _lib()
        u = lib._spawn("lab", lab=True)
        self._log("nova-probna", u.unit_id)
        self._done(tr("Nova probna jedinica: {0}").format(u.unit_id))

    def _test_move(self, kind: str):
        from ..pse import measure as PM
        sel = self._selected()
        if not sel:
            return self._done(tr("Označi jedinicu."))
        u = sel[0]
        act = {"ok": PM.Action("probni potez", "f", checked=True),
               "c": PM.Action("probni potez bez provjere", "o", checked=False),
               "n": PM.Action("probno odbijanje bez razloga", "s", justified=False)}[kind]
        r = _lib().move(u, actions=[act], note="laboratorija")
        self._log(f"potez-{kind}", u.unit_id)
        self._done(tr("θ {0:.1f} (Δ {1:+.1f}) · okidači: {2}").format(
            r.theta, r.delta, ", ".join(r.triggers) or "—"))

    def _fission(self):
        sel = self._selected()
        if not sel:
            return self._done(tr("Označi jedinicu."))
        u = sel[0]
        kids = _lib().fission(u, max(2, (u.core.steps_remaining or 20)), actor=ACTOR)
        self._log("fisija", u.unit_id)
        self._done(tr("Fisija: {0} → {1}").format(u.unit_id, ", ".join(k.unit_id for k in kids)))

    def _fusion(self):
        sel = self._selected()
        if len(sel) != 2:
            return self._done(tr("Označi tačno dvije jedinice istog agenta."))
        a, b = sel
        if a.agent != b.agent:
            return self._done(tr("Fuzija samo za jedinice istog agenta."))
        c = _lib().fusion(a, b, actor=ACTOR)
        self._log("fuzija", f"{a.unit_id}+{b.unit_id}")
        self._done(tr("Fuzija: {0}").format(c.unit_id) if c else
                   tr("Fuzija odbijena: (θa+θb)/2 nije u [25, 35]"))

    def _doctor(self):
        from ..pse import doctor as DR
        sel = self._selected()
        if not sel:
            return self._done(tr("Označi jedinicu."))
        u = sel[0]
        f = _lib().suspect(u, [DR.T_PAC], note="operater poslao Doktora iz laboratorije")
        self._log("doktor", u.unit_id)
        self._done(tr("Doktor: {0}").format((f.why if f else "zamrznuta dok mjera čeka")))

    def _freeze(self):
        for u in self._selected():
            _lib().freeze(u, "operater (laboratorija)", ACTOR)
            self._log("zamrzni", u.unit_id)
        self._done(tr("Zamrznuto."))

    def _unfreeze(self):
        for u in self._selected():
            _lib().unfreeze(u, ACTOR)
            self._log("odmrzni", u.unit_id)
        self._done(tr("Odmrznuto."))

    def _kill(self):
        sel = self._selected()
        if not sel:
            return
        if QMessageBox.question(self, tr("Smrt jedinice"),
                                tr("Ugasiti {0}? Sve iz nje ide u SHARED_LIB; agent dobija "
                                   "novu generaciju.").format(", ".join(u.unit_id for u in sel))) \
                != QMessageBox.Yes:
            return
        for u in sel:
            _lib().end(u, "smrt (operater, laboratorija)", successor=not getattr(u, "lab", False))
            self._log("smrt", u.unit_id)
        self._done(tr("Ugašeno; podaci su u SHARED_LIB-u."))

    def _undo(self):
        from ..shared_lib.store import store
        ev = store().rows("SELECT * FROM pse_events WHERE kind IN ('fisija','fuzija') "
                          "ORDER BY id DESC LIMIT 1")
        if not ev:
            return self._done(tr("Nema fisije ni fuzije za poništavanje."))
        pid = _lib().propose_undo(int(ev[0]["id"]), actor=ACTOR)
        self._done(tr("Poništavanje {0} ({1}) čeka tvoju odluku: {2}").format(
            ev[0]["kind"], ev[0]["unit_id"], pid))


class WeightsDialog(QDialog):
    """SHARED_LIB → Težine glasova (rule 17)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("SHARED_LIB → Težine glasova"))
        v = QVBoxLayout(self)
        self.view = MarkdownView()
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addWidget(button(tr("Predloži sada"), self._now, primary=True))
        row.addWidget(button(tr("Zatvori"), self.accept))
        v.addLayout(row)
        self.refresh()
        self.resize(720, 560)

    def refresh(self) -> None:
        from ..pse import constants as K
        from ..pse import weights as WT
        from ..shared_lib.store import store
        st = store()
        ver, w = WT.current(st)
        md = [tr("### Težine glasova — verzija {0} (aktivna)").format(ver), "",
              tr("SHARED_LIB predlaže jednom sedmično; prijedlog traži bar {0} odlučenih "
                 "slučajeva; jedna težina se pomjera najviše ±{1:.0f} %. Ti odobravaš u "
                 "„Čeka tvoju odluku“.").format(K.WEIGHTS_MIN_CASES, 100 * K.WEIGHTS_MAX_STEP), "",
              "| " + tr("težina") + " | " + tr("vrijednost") + " |", "|---|---|"]
        md += [f"| {k} | {v:.4f} |" for k, v in sorted(w.items())]
        md += ["", tr("### Istorija"), ""]
        for h in WT.history(st)[:12]:
            md.append(f"- v{h['version']} · {h['status']} · {h.get('cases') or 0} "
                      + tr("slučajeva") + f" · {h.get('by') or ''}")
        self.view.set_markdown("\n".join(md))

    def _now(self) -> None:
        from ..pse import weights as WT
        from ..shared_lib.store import store
        r = WT.propose(store(), actor="operater", force=True)
        msg = {"nedovoljno-podataka": tr("Nedovoljno podataka: {0}/{1} slučajeva.").format(
                   r.get("cases", 0), r.get("needed", 0)),
               "prijedlog-vec-ceka": tr("Prijedlog već čeka u „Čeka tvoju odluku“."),
               "predlozeno": tr("Predloženo: v{0} — odluka je u „Čeka tvoju odluku“.").format(
                   r.get("version"))}.get(r["status"], r["status"])
        QMessageBox.information(self, tr("Težine glasova"), msg)
        self.refresh()
