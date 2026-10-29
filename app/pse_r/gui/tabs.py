"""
The workspace tabs — the left 70%.

Lab · Corpus · Editor · Graph · Guardian · Plan. Every long-running action
(experiment, harvest, triage) runs on a worker thread; the GUI thread never
blocks, because on this machine a blocked GUI looks identical to a crash.
"""
from __future__ import annotations

from ..i18n import tr

import time

import json
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QProgressBar,
                               QScrollArea, QSpinBox, QSplitter, QTextEdit,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from .. import config
from ..core import briefing as BR
from ..core import journal as J
from ..guardian import host as HOST
from ..guardian.unit import guardian
from ..ingest import curator as CU
from ..ingest import reading as RD
from ..lab import runner as LR
from ..vault import index as IX
from ..vault import store as VS
from ..vault.card import Card, SUSPECT, VERIFIED_STATUSES
from ..vault.gate import gate
from .widgets import MarkdownView, button, hline, small, status_chip


class Job(QObject):
    """Run any callable off the GUI thread and hand the result back."""
    done = Signal(object, str)

    def __init__(self, fn, *a, **kw):
        super().__init__()
        self.fn, self.a, self.kw = fn, a, kw

    def run(self):
        try:
            self.done.emit(self.fn(*self.a, **self.kw), "")
        except Exception as e:                          # noqa: BLE001
            self.done.emit(None, f"{type(e).__name__}: {e}")


class JobMixin:
    """
    Run work off the GUI thread and come back ON it.

    The callback must be delivered as a QUEUED connection, which Qt only does
    when the receiver is a QObject with GUI-thread affinity. Connecting a plain
    closure here would give a direct connection: the callback would execute in
    the worker thread, touch widgets from the wrong thread, and make the worker
    wait on itself. That is a crash waiting for a slow network — so the
    receiver is a bound method of the widget, deliberately.
    """

    def start_job(self, fn, cb, *a, **kw):
        self._cb = cb
        self._thr = QThread()
        self._job = Job(fn, *a, **kw)
        self._job.moveToThread(self._thr)
        self._thr.started.connect(self._job.run)
        self._job.done.connect(self._job_finished)      # queued: widget lives in GUI thread
        self._thr.start()

    def _job_finished(self, res, err):
        thr = getattr(self, "_thr", None)
        if thr is not None:
            thr.quit()
            thr.wait(5000)
            self._thr = None
        cb, self._cb = getattr(self, "_cb", None), None
        if cb:
            cb(res, err)


# --------------------------------------------------------------------------- #
class LabTab(QWidget, JobMixin):
    card_written = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog = LR.catalog()
        self.inputs: dict = {}

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("lab")
        split.setChildrenCollapsible(False)
        left = QSplitter(Qt.Vertical)          # list / history draggable too
        left.setObjectName("lab_left")
        lv_host = QWidget()
        lv = QVBoxLayout(lv_host)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel(tr("<b>Eksperimenti</b>")))
        self.list = QListWidget()
        for e in self.catalog:
            it = QListWidgetItem(f"{tr(e['title'])}   ({tr(e['cost'])})")
            it.setData(Qt.UserRole, e["key"])
            self.list.addItem(it)
        self.list.currentRowChanged.connect(self._select)
        lv.addWidget(self.list, 1)
        left.addWidget(lv_host)
        runs_host = QWidget()
        rl = QVBoxLayout(runs_host)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel(tr("<b>Prethodna pokretanja</b>")))
        self.runs = QListWidget()
        self.runs.itemClicked.connect(self._open_run)
        rl.addWidget(self.runs, 1)
        left.addWidget(runs_host)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        self.title = QLabel("")
        from .widgets import _BASE_PT
        self.title.setStyleSheet(
            f"font-size:{_BASE_PT[0]*1.25:.1f}pt;font-weight:600;")
        rv.addWidget(self.title)
        self.question = small("", "#8ab")
        self.why = small("")
        rv.addWidget(self.question)
        rv.addWidget(self.why)
        self.form_box = QGroupBox(tr("Parametri"))
        self.form = QFormLayout(self.form_box)
        rv.addWidget(self.form_box)
        row = QHBoxLayout()
        self.b_run = button(tr("▶ Pokreni"), self._run, primary=True)
        row.addWidget(self.b_run)
        self.prog = QProgressBar()
        self.prog.setRange(0, 0)
        self.prog.hide()
        row.addWidget(self.prog, 1)
        rv.addLayout(row)
        rv.addWidget(hline())
        outsplit = QSplitter(Qt.Vertical)      # text vs plot, draggable
        outsplit.setObjectName("lab_out")
        outsplit.setChildrenCollapsible(False)
        self.out = MarkdownView()
        outsplit.addWidget(self.out)
        from .lab_plot import LabPlotView           # round 3, item 29 step 6: interactive
        self.plot = LabPlotView()
        self.plot.expand.connect(lambda: self._lab_expand(outsplit))
        outsplit.addWidget(self.plot)
        outsplit.setSizes([300, 300])
        rv.addWidget(outsplit, 1)
        split.addWidget(right)
        split.setSizes([260, 700])

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addWidget(split)
        self.refresh_runs()
        if self.catalog:
            self.list.setCurrentRow(0)

    def _select(self, row: int):
        if row < 0:
            return
        e = self.catalog[row]
        self.title.setText(tr(e["title"]))
        self.question.setText("❓ " + tr(e["question"]))
        self.why.setText(tr(e["why"]))
        while self.form.rowCount():
            self.form.removeRow(0)
        self.inputs = {}
        for p in e["params"]:
            if p["kind"] == "int":
                w = QSpinBox()
                w.setRange(int(p["lo"]), int(p["hi"]))
                w.setValue(int(p["default"]))
            else:
                w = QDoubleSpinBox()
                w.setRange(float(p["lo"]), float(p["hi"]))
                w.setDecimals(3)
                w.setValue(float(p["default"]))
            w.setToolTip(tr(p["help"]))
            self.inputs[p["name"]] = w
            self.form.addRow(f"{p['name']} — {tr(p['help'])}", w)

    def _run(self):
        row = self.list.currentRow()
        if row < 0:
            return
        key = self.catalog[row]["key"]
        params = {k: w.value() for k, w in self.inputs.items()}
        self.b_run.setEnabled(False)
        self.prog.show()
        self.out.set_markdown(tr("_računa…_"))
        self.start_job(LR.run, self._done, key, params)

    def _done(self, res, err):
        self.b_run.setEnabled(True)
        self.prog.hide()
        if err:
            self.out.set_markdown(tr("### ⛔ Greška\n\n```\n{0}\n```").format(err))
            return
        rec = res["record"]
        v = res["verdict"]
        md = [f"## {rec['title']}", "", rec["reading"], "",
              tr("| veličina | vrijednost |"), "|---|---|"]
        md += [f"| `{k}` | {v2} |" for k, v2 in rec["numbers"].items()]
        if rec["warnings"]:
            md += [""] + [f"> ⚠ {w}" for w in rec["warnings"]]
        md += ["", tr("_{0} s · sha256 `{1}…`_").format(rec['elapsed_s'], rec['script_sha256'][:12])]
        if v is not None:
            md += ["", (tr("✅ kartica upisana: `%s`") % res["card_id"]) if v.ok
                   else (tr("⛔ kapija odbila karticu: ") + v.reason)]
        self.out.set_markdown("\n".join(md))
        self.plot.show_record(rec, Path(res["dir"]))
        self.refresh_runs()
        self.card_written.emit()

    def _lab_expand(self, outsplit):
        """⤢ on the plot: the plot takes the whole output area (again = back)."""
        self.out.setVisible(not self.out.isVisible())
        self.plot.b_expand.setText("⤢" if self.out.isVisible() else "⤡")

    def refresh_runs(self):
        self.runs.clear()
        for r in LR.list_runs(40):
            it = QListWidgetItem(f"{r['when'][5:16]}  {r['experiment']}")
            it.setData(Qt.UserRole, r["run_id"])
            self.runs.addItem(it)

    def _open_run(self, item):
        rec = LR.load_run(item.data(Qt.UserRole))
        if not rec:
            return
        md = [f"## {rec['title']}", "", f"_{rec['when']}_", "", rec["reading"],
              "", tr("| veličina | vrijednost |"), "|---|---|"]
        md += [f"| `{k}` | {v} |" for k, v in rec["numbers"].items()]
        self.out.set_markdown("\n".join(md))
        self.plot.show_record(rec, config.DIR_LAB / rec["run_id"])


# --------------------------------------------------------------------------- #
class CorpusTab(QWidget, JobMixin):
    open_card = Signal(str)
    to_context = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText(tr("pretraga vaulta i inboxa…"))
        self.q.returnPressed.connect(self.search)
        bar.addWidget(self.q, 1)
        bar.addWidget(button(tr("Traži"), self.search))
        bar.addWidget(button(tr("↻ index"), self.reindex))
        bar.addWidget(button(tr("⬇ Skupi"), self.harvest))
        bar.addWidget(button(tr("Trijaža"), self.triage))
        root.addLayout(bar)
        self.status = small("")
        root.addWidget(self.status)

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("corpus")
        split.setChildrenCollapsible(False)
        self.results = QListWidget()
        self.results.itemClicked.connect(self._show)
        split.addWidget(self.results)
        rp = QWidget()
        rv = QVBoxLayout(rp)
        self.view = MarkdownView(on_card=self.open_card.emit)
        rv.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.b_ctx = button(tr("→ u kontekst chata"), self._to_ctx)
        self.b_promote = button(tr("Promoviši u karticu"), self._promote)
        self.b_drop = button(tr("Odbaci"), self._drop)
        self.b_read = button(tr("📖 Pročitaj rad"), self._read)
        self.b_skeptic = button(tr("⚔ Skeptik"), self._skeptic)
        row.addWidget(self.b_ctx)
        row.addWidget(self.b_promote)
        row.addWidget(self.b_read)
        row.addWidget(self.b_skeptic)
        row.addWidget(self.b_drop)
        row.addStretch(1)
        rv.addLayout(row)
        self.b_writeprops = button(tr("Upiši prijedloge"), self._write_props,
                                   primary=True)
        self.b_writeprops.setEnabled(False)
        row.addWidget(self.b_writeprops)
        split.addWidget(rp)
        split.setSizes([340, 620])
        root.addWidget(split, 1)
        self._current = None
        self._current_rec = {}
        self._proposals = []
        self.refresh()

    def refresh(self):
        c = CU.counts()
        st = VS.stats()
        self.status.setText(
            tr("vault: {0} kartica ({1} provjerenih) · inbox: {2} (novo {3}, prošlo grubu {4}, trijažirano {5}, promovisano {6}, odbačeno {7})").format(st.total, st.verified, c.get('total',0), c.get('new',0), c.get('coarse_ok',0), c.get('triaged',0), c.get('promoted',0), c.get('dropped',0)))

    def reindex(self):
        self.status.setText(tr("indeksiram…"))
        self.start_job(IX.index().reindex,
                       lambda r, e: (self.status.setText(
                           f"index: {r}" if not e else e), self.refresh()))

    def search(self):
        rows = IX.search(self.q.text(), 60)
        self.results.clear()
        for r in rows:
            it = QListWidgetItem(tr("[{0:8s}] {1}").format(r['kind'][:8], r['title'][:70]))
            it.setData(Qt.UserRole, r)
            self.results.addItem(it)
        self.status.setText(tr("{0} rezultata").format(len(rows)))

    def _show(self, item):
        r = item.data(Qt.UserRole)
        self._current = r
        if r["kind"] == "inbox":
            try:
                d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            d["_path"] = r["path"]
            self._current_rec = d
            md = [f"# {d.get('title','')}", "",
                  f"`{d.get('source_ref','')}` · {d.get('origin','')} · "
                  f"{d.get('year','')}", ""]
            if d.get("authors"):
                md += ["*" + ", ".join(d["authors"][:8]) + "*", ""]
            if d.get("_triage"):
                t = d["_triage"]
                md += [tr("**Trijaža** ({0}): {1}/100 · {2} — {3}").format(t.get('by',''), t.get('score'), t.get('branch',''), t.get('why','')), ""]
            if d.get("injection_hits"):
                md += [tr("> ⚠ Guardian: tekst sadrži obrasce koji liče na pokušaj "
                       "ubacivanja instrukcija modelu. Tretiraj kao podatak."), ""]
            md += [d.get("abstract", "")]
            self.view.set_markdown("\n".join(md))
        else:
            c = VS.get(r["id"])
            if c:
                self.view.set_markdown(
                    tr("# {0}\n\n`{1}` · `{2}` · izvori: {3}\n\n{4}").format(c.title, c.status, c.type, ', '.join(c.sources) or '—', c.body))

    def _to_ctx(self):
        if self._current and self._current["kind"] != "inbox":
            self.to_context.emit(self._current["id"])

    def _promote(self):
        if not self._current or self._current["kind"] != "inbox":
            return
        ok, msg = CU.promote(self._current_rec, actor="user")
        self.status.setText(("✅ " if ok else "⛔ ") + str(msg))
        self.refresh()

    def _drop(self):
        if self._current and self._current["kind"] == "inbox":
            CU.drop(self._current_rec, "ručno odbačeno")
            self.status.setText(tr("odbačeno"))
            self.refresh()

    def _read(self):
        """Fetch an arXiv paper's full text and let the strong model extract cards."""
        ref = ""
        if self._current and self._current["kind"] == "inbox":
            ref = self._current_rec.get("source_ref", "")
        elif self._current:
            c = VS.get(self._current["id"])
            ref = (c.sources[0] if c and c.sources else "")
        if not ref.startswith("arxiv:"):
            self.status.setText(tr("puni tekst je dostupan samo za arXiv radove"))
            return
        self.status.setText(tr("čitam {0} preko ar5iv… (ne blokira)").format(ref))
        self.b_read.setEnabled(False)
        self.start_job(RD.read_paper, self._read_done, ref)

    def _read_done(self, res, err):
        self.b_read.setEnabled(True)
        if err:
            self.status.setText("⛔ " + err[:200])
            return
        self._proposals = res["cards"]
        md = [tr("# Pročitano ({0})").format(res['provider']), ""]
        if res["hits"]:
            md += [tr("> ⚠ Guardian: u tekstu rada nađeni obrasci koji liče na "
                   "pokušaj ubacivanja instrukcija modelu. Instrukcije iz "
                   "teksta su ignorisane."), ""]
        md += [res["reply"] or "", "",
               tr("## Prijedlozi kartica ({0})").format(len(res['cards'])), ""]
        for i, c in enumerate(res["cards"], 1):
            md += [f"**{i}. [{c.get('status','?')}] {c.get('title','')}**",
                   f"izvori: {', '.join(c.get('sources') or [])}", "",
                   (c.get("body") or "")[:700], "", "---", ""]
        md += [tr("_Klikni 'Upiši prijedloge' da prođu kroz kapiju._")]
        self.view.set_markdown("\n".join(md))
        self.b_writeprops.setEnabled(bool(res["cards"]))
        self.status.setText(tr("{0} prijedloga — pregledaj pa upiši").format(len(res['cards'])))

    def _write_props(self):
        ok = bad = 0
        msgs = []
        for meta in getattr(self, "_proposals", []):
            good, msg = RD.write_proposal(meta, actor="model:reading")
            if good:
                ok += 1
            else:
                bad += 1
                msgs.append(msg[:90])
        self.status.setText(tr("upisano {0}, odbijeno {1}").format(ok, bad)
                            + ("  · " + "; ".join(msgs[:2]) if msgs else ""))
        self._proposals = []
        self.b_writeprops.setEnabled(False)
        self.refresh()

    def _skeptic(self):
        if not self._current or self._current["kind"] == "inbox":
            self.status.setText(tr("skeptik napada karticu iz vaulta, ne inbox stavku"))
            return
        cid = self._current["id"]
        self.status.setText(tr("skeptik napada {0}…").format(cid))
        self.b_skeptic.setEnabled(False)
        self.start_job(RD.attack_card, self._skeptic_done, cid)

    def _skeptic_done(self, res, err):
        self.b_skeptic.setEnabled(True)
        if err:
            self.status.setText("⛔ " + err[:200])
            return
        if not res.get("ran"):
            self.status.setText(tr("skeptik nije mogao da radi: ") +
                                str(res.get("attack", ""))[:150])
            return
        if res.get("survives"):
            self.status.setText(tr("✅ kartica je izdržala napad ({0})").format(res.get('by','')))
        else:
            self.status.setText(
                tr("⚔ POGODAK ({0}): {1} — kartica je sada SUSPECT").format(res.get('severity'), res.get('attack','')[:160]))
            self._show(self.results.currentItem())
        self.refresh()

    def harvest(self):
        self.status.setText(tr("skupljam sa interneta… (ne blokira)"))
        self.start_job(CU.harvest, self._after_job, 1, 8)

    def triage(self):
        self.status.setText(tr("gruba + trijaža modelom…"))

        def _both():
            a = CU.coarse_pass()
            b = CU.triage_pass(20)
            return {"coarse": a, "triage": b}
        self.start_job(_both, self._after_job)

    def _after_job(self, res, err):
        self.status.setText(f"⛔ {err}" if err else f"gotovo: {res}")
        self.refresh()


# --------------------------------------------------------------------------- #
class EditorTab(QWidget):
    card_written = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        self.picker = QComboBox()
        self.picker.setMinimumWidth(320)
        self.picker.currentIndexChanged.connect(self._load)
        bar.addWidget(self.picker, 1)
        bar.addWidget(button(tr("Dnevnik danas"), self._daily))
        bar.addWidget(button(tr("Nova bilješka"), self._new))
        bar.addWidget(button(tr("💾 Sačuvaj"), self._save, primary=True))
        bar.addWidget(button("↻", self.refresh))
        root.addLayout(bar)
        self.info = small("")
        root.addWidget(self.info)
        split = QSplitter(Qt.Horizontal)
        split.setObjectName("editor")
        split.setChildrenCollapsible(False)
        self.edit = QPlainTextEdit()
        from .widgets import _BASE_PT
        self.edit.setStyleSheet(
            f"font-family:monospace;font-size:{_BASE_PT[0]*0.95:.1f}pt;")
        self.edit.textChanged.connect(self._preview)
        # 33b: "Prevedi" in the editor too — the translation shows in the preview,
        # beside the original, which is never changed
        self.edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.edit.customContextMenuRequested.connect(self._edit_menu)
        split.addWidget(self.edit)
        self.view = MarkdownView()
        split.addWidget(self.view)
        split.setSizes([500, 500])
        root.addWidget(split, 1)
        self.path: Path | None = None
        self.refresh()

    def refresh(self):
        self.picker.blockSignals(True)
        self.picker.clear()
        files = []
        for sub in ("notes", "daily", "knowledge", "speculation", "sources"):
            d = config.VAULT / sub
            if d.exists():
                files += sorted(d.glob("*.md"))
        for f in (config.VAULT / "PLAN.md", config.VAULT / "OPEN_QUESTIONS.md"):
            if f.exists():
                files.insert(0, f)
        for f in files:
            self.picker.addItem(f"{f.parent.name}/{f.name}", str(f))
        self.picker.blockSignals(False)
        if files:
            self._load(0)

    def _load(self, idx: int):
        p = self.picker.currentData()
        if not p:
            return
        self.path = Path(p)
        self.view.source_path = str(self.path)
        try:
            self.edit.setPlainText(self.path.read_text(encoding="utf-8"))
        except OSError as e:
            self.edit.setPlainText(tr("(ne mogu da otvorim: {0})").format(e))
        self.info.setText(str(self.path))

    def _preview(self):
        self.view.set_markdown(self.edit.toPlainText())

    def _edit_menu(self, pos):
        m = self.edit.createStandardContextMenu()
        m.addSeparator()
        m.addAction(tr("Prevedi na srpski"), lambda: self.view.translate_to("sr"))
        m.addAction(tr("Prevedi na engleski"), lambda: self.view.translate_to("en"))
        a = m.addAction(tr("Prikaži original"), self.view.show_original)
        a.setEnabled(self.view._orig is not None)
        m.exec(self.edit.mapToGlobal(pos))

    def open_path(self, p: Path):
        for i in range(self.picker.count()):
            if self.picker.itemData(i) == str(p):
                self.picker.setCurrentIndex(i)
                return
        self.refresh()
        for i in range(self.picker.count()):
            if self.picker.itemData(i) == str(p):
                self.picker.setCurrentIndex(i)
                return

    def _save(self):
        if not self.path:
            return
        if not config.inside_vault(self.path):
            QMessageBox.warning(self, tr("Odbijeno"),
                                tr("Upis van vaulta nije dozvoljen."))
            return
        try:
            self.path.write_text(self.edit.toPlainText(), encoding="utf-8")
            J.log(J.GATE, "user", {"path": str(self.path), "direct_edit": True},
                  subject=self.path.stem, verdict="edit")
            self.info.setText(tr("✅ sačuvano {0}").format(self.path))
            self.card_written.emit()
        except OSError as e:
            self.info.setText(f"⛔ {e}")

    def _daily(self):
        p = BR.daily_note()
        self.refresh()
        self.open_path(p)

    def _new(self):
        name, _ = QFileDialog.getSaveFileName(
            self, tr("Nova bilješka"), str(config.DIR_NOTES / "biljeska.md"),
            "Markdown (*.md)")
        if not name:
            return
        p = Path(name)
        if not config.inside_vault(p):
            QMessageBox.warning(self, tr("Odbijeno"), tr("Samo unutar vaulta."))
            return
        p.write_text("# \n\n", encoding="utf-8")
        self.refresh()
        self.open_path(p)


# --------------------------------------------------------------------------- #
class GraphTab(QWidget):
    open_card = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        bar.addWidget(button(tr("↻ Osvježi"), self.refresh))
        # round 3, item 30: the same graph as a tree or as nodes and links
        self.b_tree = button(tr("Stablo"), lambda: self._view(0))
        self.b_net = button(tr("Mreža"), lambda: self._view(1))
        bar.addWidget(self.b_tree)
        bar.addWidget(self.b_net)
        self.info = small("")
        bar.addWidget(self.info, 1)
        root.addLayout(bar)
        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("čvor"), "status", "tip", "veze"])
        self.tree.itemDoubleClicked.connect(
            lambda it, _: self.open_card.emit(it.data(0, Qt.UserRole) or ""))
        self.stack.addWidget(self.tree)
        from .knowledge_view import KnowledgeView
        self.net = KnowledgeView()
        self.net.open_card.connect(self.open_card.emit)
        self.stack.addWidget(self.net)
        root.addWidget(self.stack, 1)
        self.refresh()
        self._view(1)                                   # the picture first; the tree is one click away

    def _view(self, i: int):
        self.stack.setCurrentIndex(i)
        self.b_tree.setProperty("kind", "" if i else "primary")
        self.b_net.setProperty("kind", "primary" if i else "")
        for b in (self.b_tree, self.b_net):
            b.style().unpolish(b)
            b.style().polish(b)

    def refresh(self):
        nodes, edges = VS.graph()
        out: dict = {}
        for a, b, kind in edges:
            out.setdefault(a, []).append((b, kind))
        self.tree.clear()
        by_id = {n["id"]: n for n in nodes}
        topics = [n for n in nodes if n["id"].startswith("tema-")]
        others = [n for n in nodes if not n["id"].startswith("tema-")]
        incoming: dict = {}
        for a, b, _k in edges:
            incoming.setdefault(b, []).append(a)

        for t in sorted(topics, key=lambda x: x["title"]):
            root_item = QTreeWidgetItem(
                [t["title"], t["status"], t["type"],
                 str(len(incoming.get(t["id"], [])))])
            root_item.setData(0, Qt.UserRole, t["id"])
            for child in incoming.get(t["id"], []):
                c = by_id.get(child)
                if not c:
                    continue
                ci = QTreeWidgetItem([c["title"][:70], c["status"], c["type"], ""])
                ci.setData(0, Qt.UserRole, c["id"])
                root_item.addChild(ci)
            self.tree.addTopLevelItem(root_item)

        linked = {b for _a, b, _k in edges} | {a for a, _b, _k in edges}
        orphan = [n for n in others if n["id"] not in linked]
        if orphan:
            oi = QTreeWidgetItem([tr("⚠ bez veza ({0})").format(len(orphan)), "", "", ""])
            for n in orphan:
                ci = QTreeWidgetItem([n["title"][:70], n["status"], n["type"], ""])
                ci.setData(0, Qt.UserRole, n["id"])
                oi.addChild(ci)
            self.tree.addTopLevelItem(oi)
        self.tree.expandToDepth(0)
        self.info.setText(tr("{0} čvorova · {1} veza · {2} bez veza").format(len(nodes), len(edges), len(orphan)))
        if hasattr(self, "net"):
            self.net.refresh()


# --------------------------------------------------------------------------- #
class GuardianTab(QWidget, JobMixin):
    def _ssh_md(self) -> list:
        """SSH guardian (round 3, Phase 4): process, θ, rights, blocks, sources."""
        from .. import guardian_app as GA
        from ..guardian import containment as C
        from ..guardian.ssh import unit as U
        from ..shared_lib.store import store
        pid = GA.running_pid()
        ok, detail = C.have_rights()
        st = store().kv_get(U.KV_STATE, {}) or {}
        ser = st.get("theta") or []
        th = f"{sum(ser[-30:]) / len(ser[-30:]):.1f}" if ser else "—"
        L = [tr("## SSH čuvar"),
             tr("- proces: {0}").format(tr("radi (PID {0})").format(pid) if pid else tr("⛔ NE RADI")),
             tr("- θ (zadnjih 30): {0} · generacija jedinice {1}").format(th, st.get('generation', 1)),
             tr("- pravo na povratne mjere: {0}{1}").format('✅ ' if ok else tr("⛔ nema — "), tr(detail))
             + ("" if ok else tr(" (vodič: SUDOERS-SR.md)")), ""]
        act = C.active()
        L += [tr("### Aktivne blokade (skidaju se same)"), ""]
        L += [tr("- `{0}` do {1}").format(r['target'], time.strftime('%d.%m. %H:%M', time.localtime(r['until'])))
              for r in act] or ["- —"]
        srcs = store().kv_get(U.KV_SOURCES, {}) or {}
        top = sorted(srcs.items(), key=lambda x: -x[1].get("hostile", 0))[:10]
        L += ["", tr("### Izvori (SHARED_LIB)"), "", tr("| IP | sumnjivo | neuspjelo | imena |"),
              "|---|---|---|---|"]
        L += [f"| `{ip}` | {r.get('hostile', 0)} | {r.get('failed', 0)} | "
              f"{', '.join(r.get('users', [])[:5])} |" for ip, r in top] or ["| — | | | |"]
        return L + [""]

    def run_bench(self):
        """Round 3, item 22: measured FP/FN in a throwaway vault; the numbers go
        into a sealed final report in the real one."""
        import subprocess
        import sys
        from .. import config

        def work():
            exe = [sys.executable, str(config.APP_ROOT / "main.py")] \
                if (config.APP_ROOT / "main.py").exists() else [sys.argv[0]]
            r = subprocess.run(exe + ["--bench", "--report"], capture_output=True,
                               text=True, timeout=600)
            return r.stdout[-6000:] or r.stderr[-2000:]
        self.view.set_markdown(self._md(tr("_Benchmark radi u zasebnom privremenom vaultu…_")))
        self.start_job(work, lambda res, err: self.view.set_markdown(
            self._md(f"⛔ {err}" if err else res)))

    def check_rights(self):
        from ..guardian import containment as C
        ok, detail = C.have_rights(refresh=True)
        self.view.set_markdown(self._md((tr("✅ Čuvar ima usko pravo: ") if ok else
                                         tr("⛔ Čuvar NEMA pravo (vodič SUDOERS-SR.md): ")) + detail))

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        bar.addWidget(button(tr("↻ Provjeri host"), self.refresh_host))
        bar.addWidget(button(tr("Test mreže"), self.preflight))
        bar.addWidget(button(tr("Ponovo snimi TLS pinove…"),
                             lambda: getattr(self.window(), "rescan_pins", lambda: None)()))
        bar.addWidget(button(tr("Oslobodi host iz karantina"), self.release))
        bar.addWidget(button(tr("Provjeri prava čuvara"), self.check_rights))
        bar.addWidget(button(tr("Benchmark → izvještaj"), self.run_bench))
        bar.addStretch(1)
        root.addLayout(bar)
        self.view = MarkdownView()
        root.addWidget(self.view, 1)
        self.refresh_host()

    def _md(self, extra: str = "") -> str:
        g = guardian()
        sc = g.self_check()
        from ..guardian.tls import pins
        from ..guardian.egress import egress
        L = [tr("# Guardian"), ""]
        if extra:
            L += [extra, ""]
        L += [tr("## Stanje"),
              tr("- mreža: `{0}`").format(egress().network),
              tr("- posmatrano: {0} zahtjeva prema {1} hostova").format(sc['observations'], sc['hosts']),
              tr("- intervencije: {0} tier-1, {1} tier-2").format(sc['tier1'], sc['tier2']),
              tr("- karantin: {0}").format(', '.join(sc['quarantined']) or '—'), ""]
        L += self._ssh_md()
        if sc["problems"]:
            L += [tr("## ⚠ Guardian sam nije zdrav")] + \
                 [f"- {p}" for p in sc["problems"]] + [""]
        L += [tr("## TLS pinovi"),
              tr("| host | pinova | naučeno na mreži |"), "|---|---|---|"]
        ps = pins()
        for h in ps.hosts():
            L.append(f"| `{h}` | {len(ps.pins(h))} | "
                     f"`{ps.trusted_network(h) or '?'}` |")
        if not ps.hosts():
            L.append(tr("| _(nijedan još)_ | | |"))
        L += ["", tr("## Host"), ""]
        p = HOST.check()
        for f in p.findings:
            icon = {"high": "⛔", "warn": "⚠", "info": "•"}[f.level]
            L.append(f"**{icon} {f.title}**")
            L.append(f"{f.detail}")
            if f.fix:
                L.append(f"```\n{f.fix}\n```")
            L.append("")
        recent = J.journal().tail(15, J.THREAT)
        if recent:
            L += [tr("## Posljednji događaji"), ""]
            for e in recent[::-1]:
                pl = e.get("payload") or {}
                L.append(f"- `{e['verdict']}` **{e['subject']}** — "
                         f"{pl.get('reason', '')[:120]}")
        return "\n".join(L)

    def refresh_host(self):
        self.view.set_markdown(self._md())

    def preflight(self):
        from ..guardian.egress import egress
        self.view.set_markdown(tr("_provjeravam mrežu…_"))
        self.start_job(egress().preflight, lambda r, e: self.view.set_markdown(
            self._md(tr("**Test mreže:** `{0}`").format(r or e))))

    def release(self):
        g = guardian()
        if not g.quarantined:
            self.view.set_markdown(self._md(tr("_nema hostova u karantinu_")))
            return
        host = sorted(g.quarantined)[0]
        ans = QMessageBox.question(
            self, tr("Oslobodi host"),
            tr("Osloboditi `{0}` iz karantina?\n\nUradi ovo samo ako si siguran da je bila lažna uzbuna. Na tuđoj mreži pretpostavka treba da bude presretanje.").format(host))
        if ans == QMessageBox.Yes:
            g.release(host, "ručno oslobođeno iz GUI-ja")
            self.view.set_markdown(self._md(tr("_oslobođen `{0}`_").format(host)))


# --------------------------------------------------------------------------- #
class PlanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        bar = QHBoxLayout()
        bar.addWidget(button(tr("↻ Briefing"), self.refresh))
        bar.addWidget(button(tr("Sedmični izvještaj"), self.report))
        bar.addStretch(1)
        root.addLayout(bar)
        self.view = MarkdownView()
        root.addWidget(self.view, 1)
        self.refresh()

    def refresh(self):
        self.view.set_markdown(BR.briefing())

    def report(self):
        p = BR.write_weekly_report(7)
        self.view.set_markdown(BR.weekly_report(7) +
                               tr("\n\n---\n_snimljeno u `{0}`_").format(p))
