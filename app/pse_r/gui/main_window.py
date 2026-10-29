"""
The main window — 70% workspace on the left, 30% chat on the right, and a
status bar that tells you the four things you need to know at a glance:
the source/derivation balance, the spend, the network state, and whether the
Guardian has anything to say.

Ctrl+Shift+P is the command palette (Ctrl+K is the online-AI kill switch). On a laptop keyboard on a train, a palette beats
a menu bar.
"""
from __future__ import annotations

from ..i18n import tr

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QMainWindow, QMessageBox,
                               QSplitter, QStatusBar, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import config
from .. import settings as S
from ..core import briefing as BR
from ..core import journal as J
from ..guardian.unit import guardian
from ..llm.budget import budget
from ..vault import index as IX
from ..vault import seed, store as VS
from .chat import ChatPanel
from .tabs import (CorpusTab, EditorTab, GraphTab, GuardianTab, LabTab, PlanTab)
from .whiteboard import WhiteboardTab
from .widgets import MarkdownView, dark_qss, set_base_pt, small


_LIVE_THREADS: set = set()            # background QThreads still running (see _check_net)

class Palette(QDialog):
    def __init__(self, actions: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Komande"))
        from .. import screen as SCR
        SCR.fit(self, 520, 400, grow=False)
        self.actions_ = actions
        v = QVBoxLayout(self)
        self.q = QLineEdit()
        self.q.setPlaceholderText(tr("komanda…"))
        self.q.textChanged.connect(self._filter)
        self.q.returnPressed.connect(self._go)
        v.addWidget(self.q)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._go())
        v.addWidget(self.list, 1)
        self._filter("")

    def _filter(self, text):
        self.list.clear()
        for name in self.actions_:
            if text.lower() in name.lower():
                self.list.addItem(name)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _go(self):
        it = self.list.currentItem()
        if it:
            self.accept()
            self.actions_[it.text()]()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} {config.VERSION}")
        from .. import screen as SCR
        _prof = SCR.current() or SCR.detect()
        self.resize(_prof.win_w, _prof.win_h) if _prof else self.resize(1420, 900)
        self.font_pt = S.base_font_pt()
        set_base_pt(self.font_pt)
        self.setStyleSheet(dark_qss(self.font_pt))

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("main")
        split.setChildrenCollapsible(False)
        self.main_split = split
        self.tabs = QTabWidget()
        self.tab_plan = PlanTab()
        self.tab_lab = LabTab()
        self.tab_corpus = CorpusTab()
        self.tab_board = WhiteboardTab()
        self.tab_editor = EditorTab()
        self.tab_graph = GraphTab()
        from .grafovi import GrafoviTab
        self.tab_grafovi = GrafoviTab()                 # round 3, item 29
        self.tab_guard = GuardianTab()
        from .qrh_tabs import MissionsTab, QueueTab
        from .overview import OverviewTab
        self.tab_overview = OverviewTab()
        self.tab_missions = MissionsTab()
        self.tab_queue = QueueTab()
        from .ideas import IdeasTab
        self.tab_ideas = IdeasTab()                     # round 3, item 28
        from .pse_lab import LabTab as PseLabTab
        self.tab_pselab = PseLabTab()                   # Faza 6d, rule 26
        self.tab_pselab.changed.connect(lambda: self.topbar.refresh())
        self.tab_queue.decided.connect(self.tab_missions.refresh)
        self.tab_queue.decided.connect(self.tab_overview.refresh)
        self.tab_missions.switched.connect(lambda: self.topbar.refresh())
        self.tab_missions.switched.connect(lambda: self.tab_ideas.refresh())
        self.tab_ideas.changed.connect(self.tab_missions.refresh)
        self.tab_ideas.changed.connect(self._ideas_badge)
        self.tab_queue.decided.connect(lambda: self.topbar.refresh())
        self.tab_overview.open_queue.connect(lambda: self.tabs.setCurrentWidget(self._tab(self.tab_queue)))
        from .widgets import scroll_wrap
        self._wraps: dict = {}
        for w, name in ((self.tab_overview, tr("Pregled")),
                        (self.tab_missions, tr("Misije")), (self.tab_queue, tr("Čeka tvoju odluku")),
                        (self.tab_ideas, tr("Ideje")),
                        (self.tab_grafovi, tr("Grafovi")),
                        (self.tab_plan, tr("Plan")), (self.tab_lab, tr("Lab")),
                        (self.tab_corpus, tr("Corpus")),
                        (self.tab_board, tr("Tabla")), (self.tab_editor, tr("Editor")),
                        (self.tab_graph, tr("Graf")), (self.tab_guard, tr("Guardian")),
                        (self.tab_pselab, tr("Laboratorija"))):
            # a narrow screen scrolls the page; the mission workspace (rule 42) fits
            # the window itself and scrolls inside its panels, so the talk's input
            # never drops below the window
            self._wraps[w] = w if w is self.tab_missions else scroll_wrap(w)
            self.tabs.addTab(self._wraps[w], tr(name))
        # item 33c: the last "tab" is the setup (provider, keys, models, skeptic) — it opens
        # the dialog and goes back to the tab you were on
        self._setup_tab = QWidget()
        self.tabs.addTab(self._setup_tab, tr("⚙ Podešavanje"))
        self.tabs.setTabToolTip(self.tabs.count() - 1,
                                tr("Promijeni provajdera AI-ja, ključeve, modele i skeptika"))
        self._last_tab = 0
        self.tabs.currentChanged.connect(self._tab_changed)
        split.addWidget(self.tabs)

        self.chat = ChatPanel()
        split.addWidget(self.chat)
        split.setStretchFactor(0, 7)
        split.setStretchFactor(1, 3)
        split.setSizes([int(self.width() * 0.7), int(self.width() * 0.3)])
        # Svarog layout: top bar with status pills above everything
        from .topbar import TopBar
        self.topbar = TopBar(self.font_pt)
        self.topbar.open_queue.connect(lambda: self.tabs.setCurrentWidget(self._tab(self.tab_queue)))
        self.topbar.toggle_online.connect(self.toggle_online_ai)
        self.topbar.toggle_lang.connect(self.toggle_language)
        self.topbar.snapshot.connect(lambda: self.snapshot("main"))
        self.topbar.open_results.connect(self.open_results)
        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(self.topbar)
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(10, 10, 10, 6)
        bv.addWidget(split)
        cv.addWidget(body, 1)
        self.setCentralWidget(central)
        self.chat.expand_toggled.connect(self.toggle_chat_expand)
        QShortcut(QKeySequence("Escape"), self, self._unexpand_chat)
        self._restore_layout()
        # ⤢ / ⤡ on every split panel where it makes sense (Andrej): Editor, Tabla, Corpus,
        # Lab (list, history, result text), Ideje. Grafovi, the Lab plot and the chat
        # already have their own; the main tabs|chat split is the chat's own ⤢.
        from .widgets import expand_splitter
        for sp in self.findChildren(QSplitter):
            if sp.objectName() in ("main", "grafovi"):
                continue
            expand_splitter(sp, skip=[w for w in (getattr(self.tab_lab, "plot", None),) if w])
        # screen fitting: a combo box must not grow with its longest entry (a long queue
        # title widened the whole tab); the full text is shown when the list opens
        from PySide6.QtWidgets import QComboBox
        for cb in self.findChildren(QComboBox):
            if cb.sizeAdjustPolicy() != QComboBox.AdjustToMinimumContentsLengthWithIcon:
                cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                cb.setMinimumContentsLength(16)

        # wiring
        self.tab_corpus.to_context.connect(self.chat.add_context)
        self.tab_corpus.open_card.connect(self.open_card)
        self.tab_graph.open_card.connect(self.open_card)
        self.tab_grafovi.open_card.connect(self.open_card)
        self.chat.open_card.connect(self.open_card)
        for sig in (self.tab_lab.card_written, self.chat.card_written,
                    self.tab_editor.card_written, self.tab_board.card_written):
            sig.connect(self.after_write)

        # status bar: messages only — the state lives in the top bar's pills
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lb_theta = QLabel("")
        self.lb_budget = QLabel("")
        self.lb_net = QLabel("")
        self.lb_guard = QLabel("")
        self.lb_vault = QLabel("")
        self.lb_ai = QLabel("")
        self.lb_op = self.topbar.pills["op"]             # kept for callers/tests
        # (legacy labels are still updated by refresh_status but not shown: the
        # top bar replaced them; network/model state is in its pills)
        self.refresh_status()
        self._build_menu()                              # 6d R5 (rule 37)
        QTimer.singleShot(2500, self.tls_notice)        # said explicitly, once
        self._start_runtime()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(15000)

        # round 3: Ctrl+K is the online-AI kill switch; the palette moved
        QShortcut(QKeySequence("Ctrl+K"), self, self.toggle_online_ai)
        # item 29b: a screenshot from anywhere, dialogs included (application-wide)
        for seq, fn in (("F12", lambda: self.snapshot("window")),
                        ("Shift+F12", lambda: self.snapshot("tab"))):
            sc = QShortcut(QKeySequence(seq), self, fn)
            sc.setContext(Qt.ApplicationShortcut)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.palette_)
        # live text zoom — no restart, changes only font size
        for seq in ("Ctrl+=", "Ctrl++"):
            QShortcut(QKeySequence(seq), self, lambda: self.zoom(+0.8))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self.zoom(-0.8))
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.zoom(0))
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_active)
        QShortcut(QKeySequence("Ctrl+1"), self,
                  lambda: self.tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+2"), self,
                  lambda: self.tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("Ctrl+3"), self,
                  lambda: self.tabs.setCurrentIndex(2))

    # ------------------------------------------------------------------ #
    def _build_menu(self):
        """Menu bar (agreement rule 37): SHARED_LIB · Laboratorija · Podešavanje ·
        Jezik · Pomoć."""
        mb = self.menuBar()
        m = mb.addMenu(tr("SHARED_LIB"))
        m.addAction(tr("Težine glasova…"), self.open_weights)
        m.addAction(tr("Čeka tvoju odluku"),
                    lambda: self.tabs.setCurrentWidget(self._tab(self.tab_queue)))
        m.addAction(tr("Stanje roja…"), self.open_swarm)
        m = mb.addMenu(tr("Laboratorija"))
        m.addAction(tr("Otvori Laboratoriju (utiče na prave agente)"),
                    lambda: self.tabs.setCurrentWidget(self._tab(self.tab_pselab)))
        m = mb.addMenu(tr("Podešavanje"))
        m.addAction(tr("Podešavanje — operater, glavni AI, skeptik, čuvar…"), self.open_setup)
        m.addSeparator()
        m.addAction(tr("Ponovo snimi TLS pinove…"), self.rescan_pins)
        m = mb.addMenu(tr("Jezik"))
        from .. import i18n
        a_sr = m.addAction(tr("Srpski (SR)"), lambda: i18n.lang() != "sr" and self.toggle_language())
        a_en = m.addAction(tr("English (EN)"), lambda: i18n.lang() != "en" and self.toggle_language())
        for a, code in ((a_sr, "sr"), (a_en, "en")):
            a.setCheckable(True)
            a.setChecked(i18n.lang() == code)
        m = mb.addMenu(tr("Pomoć"))
        m.addAction(tr("Vodič"), self.open_guide)
        m.addAction(tr("TLS pinovi — šta su i kad ih ponovo snimiti"),
                    lambda: self.tls_notice(force=True))

    # ---- TLS pins: said explicitly, and re-scanned on request -------------- #
    def _tls_text(self) -> str:
        from ..guardian import tls as TLS
        n = len(TLS.pins().hosts())
        return tr("<b>TLS pinovi se uče pri prvom kontaktu.</b><br><br>"
                  "Kad aplikacija prvi put razgovara sa nekim serverom (model, arXiv, "
                  "Crossref …), zapamti njegove javne ključeve. Posle toga odbija svaki "
                  "server koji nema te ključeve — to štiti od presretanja na tuđem WiFi-ju "
                  "(hotel, aerodrom).<br><br>"
                  "<b>Jedina slabost:</b> ako je baš taj prvi kontakt bio presretnut, "
                  "aplikacija zapamti presretača. Zato prvi kontakt treba da bude sa mreže "
                  "kojoj vjeruješ (kuća): pokreni Corpus → Skupi i Guardian → Test mreže.<br><br>"
                  "<b>Ako nešto pođe naopako</b> (uzbuna „sertifikat NE odgovara“, a znaš da "
                  "je mreža tvoja, ili sumnjaš da su pinovi naučeni na tuđoj mreži): "
                  "<b>Podešavanje → Ponovo snimi TLS pinove…</b> — samo sa mreže kojoj "
                  "vjeruješ.<br><br>Sada zapamćeno: {0} servera.").format(n)

    def tls_notice(self, force: bool = False) -> None:
        """Rule (Andrej, rc5): the operator is TOLD that pins are learned on first
        contact. Shown until acknowledged; always from Pomoć. Non-blocking."""
        from PySide6.QtWidgets import QMessageBox
        from .. import settings as S
        from ..guardian import tls as TLS
        if not force and S.get(TLS.NOTICE_KEY):
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr("TLS pinovi"))
        box.setTextFormat(Qt.RichText)
        box.setText(self._tls_text())
        ok = box.addButton(tr("Razumijem"), QMessageBox.AcceptRole)
        again = box.addButton(tr("Ponovo snimi pinove sada…"), QMessageBox.ActionRole)

        def done(_r=0):
            if box.clickedButton() in (ok, again):
                S.set_(TLS.NOTICE_KEY, True)
            if box.clickedButton() is again:
                self.rescan_pins()
        box.finished.connect(done)
        box.open()
        self._tls_box = box

    def rescan_pins(self) -> None:
        """Podešavanje → Ponovo snimi TLS pinove…: confirm, then re-learn in the
        background; a host that cannot be reached keeps its old pins."""
        import threading
        from PySide6.QtCore import QObject, Signal as _Sig
        from PySide6.QtWidgets import QMessageBox
        from ..guardian import tls as TLS
        from ..shared_lib import operator as OP
        if not OP.current():
            QMessageBox.warning(self, tr("TLS pinovi"), tr("Prvo se prijavi kao operater."))
            return
        hosts = TLS.rescan_hosts()
        if QMessageBox.question(self, tr("Ponovo snimi TLS pinove"), tr(
                "Zaboraviti zapamćene ključeve za {0} servera i naučiti ih ponovo, sada?\n\n"
                "Uradi ovo SAMO na mreži kojoj vjeruješ (kuća). Na tuđem WiFi-ju bi "
                "aplikacija mogla zapamtiti presretača.\n\nServer koji sada nije dostupan "
                "zadržava stare ključeve.").format(len(hosts))) != QMessageBox.Yes:
            return

        class _B(QObject):
            done = _Sig(object, str)
        if getattr(self, "_pins_bridge", None) is None:
            self._pins_bridge = _B()
            self._pins_bridge.done.connect(self._pins_done)
        br = self._pins_bridge
        self.statusBar().showMessage(tr("Snimam TLS pinove za {0} servera…").format(len(hosts)))

        def work():
            try:
                br.done.emit(TLS.rescan(hosts), "")
            except Exception as e:                       # noqa: BLE001 — shown
                br.done.emit(None, str(e))
        threading.Thread(target=work, name="tls-rescan", daemon=True).start()

    def _pins_done(self, res, err: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        self.statusBar().clearMessage()
        if err:
            QMessageBox.warning(self, tr("TLS pinovi"), err)
            return
        ok = [r["host"] for r in res if r["ok"]]
        bad = [r for r in res if not r["ok"]]
        txt = tr("Ponovo snimljeno: {0} od {1} servera.").format(len(ok), len(res))
        if bad:
            txt += "\n\n" + tr("Nije dostupno (stari ključevi ostaju):") + "\n" + "\n".join(
                f"• {r['host']} — {r['detail'][:120]}" for r in bad)
        QMessageBox.information(self, tr("TLS pinovi"), txt)
        self.refresh_status()

    def open_swarm(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout as _V
        from ..shared_lib.pse_registry import pse
        lib = pse()
        sw = lib.swarm()
        rows = [r for r in lib.state() if r["alive"] and not r["lab"]]
        md = [tr("### Stanje roja"), "",
              tr("Živih jedinica: {0} · prosječan θ {1:.1f} · zamrznute: {2} · Doktorove mjere čekaju: {3}").format(
                  sw["units"], sw["theta_mean"], len(sw["frozen"]), sw["measures"]), "",
              "| " + tr("jedinica") + " | θ | " + tr("obrazac") + " | " + tr("stanje") + " |",
              "|---|---|---|---|"]
        for r in rows:
            st = (tr("❄ zamrznuta") if r["frozen"] else tr("⏳ mjera čeka") if r["restricted"]
                  else tr("radi"))
            md.append(f"| {r['unit']} | {r['theta']:.1f} | {r['attractor'] or '—'} | {st} |")
        d = QDialog(self)
        d.setWindowTitle(tr("Stanje roja"))
        lay = _V(d)
        mv = MarkdownView()
        mv.set_markdown("\n".join(md))
        lay.addWidget(mv)
        from .. import screen as SCR
        SCR.fit(d, 900, 700)
        d.exec()

    def open_guide(self):
        """Pomoć → Vodič: the complete guide for the whole app, in the interface
        language, in the shared viewer (with "Prevedi")."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QVBoxLayout as _V
        from .. import config, i18n
        name = "GUIDE-EN.md" if i18n.lang() == "en" else "VODIC-SR.md"
        for base in (config.APP_ROOT.parent, config.APP_ROOT / "docs",
                     config.APP_ROOT.parent / "docs", Path("/usr/share/doc/pse-riemann")):
            q = base / name
            if q.exists():
                text = q.read_text(encoding="utf-8")
                add = base / ("GUIDE-EN-MISSIONS.md" if i18n.lang() == "en" else "VODIC-SR-MISIJE.md")
                if config.personal() and add.exists():          # rule 39: "Tvoje misije"
                    text += "\n" + add.read_text(encoding="utf-8")
                d = QDialog(self)
                d.setWindowTitle(tr("Vodič"))
                lay = _V(d)
                mv = MarkdownView()
                mv.source_path = str(q)
                mv.image_base = str(base)                      # the guide's pictures
                mv.set_markdown(text)
                lay.addWidget(mv)
                from .. import screen as SCR
                SCR.fit(d, 1100, 900)
                d.exec()
                return
        QMessageBox.information(self, tr("Vodič"), tr("Vodič nije nađen ({0}).").format(name))

    def toggle_language(self):
        """SR/EN for the whole interface (round 3, item 23): saved, then the
        window is reopened in the new language (one restart, no half-translated UI)."""
        import sys
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QMessageBox
        from .. import i18n
        new = "en" if i18n.lang() == "sr" else "sr"
        i18n.set_lang(new)
        r = QMessageBox.question(self, "SR / EN",
                                 "Interface language: English. Restart now?" if new == "en"
                                 else "Jezik interfejsa: srpski. Ponovo pokrenuti sada?")
        if r == QMessageBox.Yes:
            self._closing_confirmed = True              # the guardian keeps running
            QProcess.startDetached(sys.executable, sys.argv)
            self.close()

    def toggle_online_ai(self):
        """Ctrl+K / top-bar button: close at once; reopen only after a question."""
        from PySide6.QtWidgets import QMessageBox
        from ..guardian import killswitch as KS
        from ..shared_lib import operator as OP
        if not KS.closed():
            out = KS.close("operater (dugme / Ctrl+K)", actor=OP.current() or "operator")
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("Online AI isključen"))
            box.setText(tr("Online AI je ISKLJUČEN. Prekinuto poziva u toku: {0}. Ključevi su sklonjeni iz memorije. Sada radi: {1}.").format(out['hung_up'], out['fallback']))
            box.setInformativeText(tr("Da li da ključeve i TRAJNO zaboravim (obrišem iz "
                                   "secrets.json)? Tada ih moraš ponovo upisati."))
            forget = box.addButton(tr("Zaboravi ključeve"), QMessageBox.DestructiveRole)
            box.addButton(tr("Ne, samo isključi"), QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is forget:
                KS.close("operater: trajno zaboravi ključeve", actor=OP.current() or "operator",
                         forget_keys=True)
        else:
            r = QMessageBox.question(
                self, tr("Uključiti online AI?"),
                tr("Online AI je isključen ({0}).\n\nUključiti ponovo? Ključevi se vraćaju iz secrets.json (ako ih nisi zaboravio), a sa njima i glavni AI i skeptik koje si imao.").format(KS.state().get('reason', '')))
            if r == QMessageBox.Yes:
                try:
                    back = KS.reopen(OP.current() or "")
                except Exception as e:                       # noqa: BLE001
                    QMessageBox.warning(self, tr("Online AI"), str(e))
                    back = None
                if back is not None:
                    self.refresh_status()
                    if back.get("main"):
                        QMessageBox.information(self, tr("Online AI"), tr(
                            "Online AI je uključen. Glavni: {0} · skeptik: {1}.").format(
                            back["main"], back.get("skeptic") or tr("nedostupan")))
                    elif QMessageBox.question(self, tr("Online AI"), tr(
                            "Online AI je uključen, ali glavni AI nije izabran (ključevi su "
                            "zaboravljeni ili ih nema). Otvoriti Podešavanje da upišeš ključ i "
                            "izabereš model?")) == QMessageBox.Yes:
                        self.open_setup()
        self.refresh_status()

    def palette_(self):
        acts = {
            "Online AI — isključi / uključi (Ctrl+K)": self.toggle_online_ai,
            "Podešavanje — operater, glavni AI, skeptik, čuvar": self.open_setup,
            "SHARED_LIB → Težine glasova": self.open_weights,
            "Laboratorija — PSE jedinice (utiče na prave agente)":
                lambda: self.tabs.setCurrentWidget(self._tab(self.tab_pselab)),
            "Lab — pokreni eksperiment": lambda: self.tabs.setCurrentWidget(self._tab(self.tab_lab)),
            "Corpus — pretraga": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_corpus)),
                                          self.tab_corpus.q.setFocus()),
            "Corpus — skupi sa interneta": self.tab_corpus.harvest,
            "Corpus — trijaža": self.tab_corpus.triage,
            "Tabla — crtaj": lambda: self.tabs.setCurrentWidget(self._tab(self.tab_board)),
            "Editor — dnevnik danas": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_editor)),
                                               self.tab_editor._daily()),
            "Graf — osvježi": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_graph)),
                                       self.tab_graph.refresh()),
            "Guardian — provjeri host": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_guard)),
                                                 self.tab_guard.refresh_host()),
            "Guardian — test mreže": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_guard)),
                                              self.tab_guard.preflight()),
            "Plan — briefing": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_plan)),
                                        self.tab_plan.refresh()),
            "Plan — sedmični izvještaj": lambda: (self.tabs.setCurrentWidget(self._tab(self.tab_plan)),
                                                  self.tab_plan.report()),
            "Vault — reindeksiraj": self.tab_corpus.reindex,
            "Vault — zasij teme (seed)": self._seed,
            "Provajderi — čarobnjak": self.open_wizard,
            "Budžet — postavi dnevni limit": self._set_cap,
            "Chat — očisti kontekst": self.chat.clear_context,
            "Prikaz — veličina interfejsa (restart)": self.set_ui_scale,
            "Snimak ekrana — sada (F12)": lambda: self.snapshot("main"),
            "Rezultati — otvori folder": self.open_results,
            "Snimak ekrana — folder…": self._choose_shot_folder,
            "Prikaz — tekst veći (Ctrl +)": lambda: self.zoom(+0.8),
            "Prikaz — tekst manji (Ctrl -)": lambda: self.zoom(-0.8),
            "Prikaz — vrati podrazumijevano (Ctrl 0)": lambda: self.zoom(0),
            "Prikaz — resetuj raspored panela": self._reset_layout,
        }
        acts = {tr(k): v for k, v in acts.items()}
        Palette(acts, self).exec()

    def zoom(self, delta: float):
        """Live text zoom. Ctrl+0 resets. Applies instantly — no restart."""
        if delta == 0:
            # clear the stored override FIRST — otherwise base_font_pt() reads
            # back the value we are trying to reset away from
            S.set_("font_pt", 0)
            self.font_pt = S.DEFAULT_FONT_PT
        else:
            step = max(1.0, self.font_pt * 0.08)   # proportional, not a flat pt
            self.font_pt = max(7.0, min(
                self.font_pt + step * (1 if delta > 0 else -1), 48.0))
            S.set_("font_pt", self.font_pt)
        set_base_pt(self.font_pt)
        self.setStyleSheet(dark_qss(self.font_pt))
        # already-rendered markdown carries its own inline sizes, so it has to
        # be laid out again or half the window ignores the change
        for v in self.findChildren(MarkdownView):
            v.rerender()
        self.statusBar().showMessage(tr("veličina teksta: {0:.1f} pt (Ctrl+0 vraća na podrazumijevanu)").format(self.font_pt), 3000)

    def set_ui_scale(self):
        """Whole-UI scale. Needs a restart — Qt reads it before the app exists."""
        cur = float(S.get("ui_scale", 1.0))
        v, ok = QInputDialog.getDouble(
            self, tr("Veličina interfejsa"),
            tr("Skala cijelog interfejsa (0.5–3.0).\nTvoj desktop prijavljuje {0}×, ali aplikacija to ignoriše i koristi samo ovaj broj.\n1.0 = kao normalan 100% desktop.\n\nPrimjenjuje se poslije ponovnog pokretanja.").format(S.detect_desktop_scale()),
            cur, 0.5, 3.0, 2)
        if ok:
            S.set_("ui_scale", v)
            QMessageBox.information(
                self, tr("Sačuvano"),
                tr("UI skala = {0:g}. Zatvori i pokreni ponovo.\n\nIz terminala odmah: ./run.sh --scale {1:g}").format(v, v))

    def _save_layout(self):
        try:
            S.set_("geometry", bytes(self.saveGeometry().toBase64()).decode())
            S.set_("win_state", bytes(self.saveState().toBase64()).decode())
            splits = {}
            for sp in self.findChildren(QSplitter):
                if sp.objectName():
                    splits[sp.objectName()] = sp.sizes()
            S.set_("splits", splits)
        except Exception:                                # noqa: BLE001
            pass

    def _restore_layout(self):
        from PySide6.QtCore import QByteArray
        g = S.get("geometry", "")
        restored = False
        if g:
            try:
                self.restoreGeometry(QByteArray.fromBase64(g.encode()))
                restored = True
            except Exception:                            # noqa: BLE001
                pass
        # the remembered window must still fit THIS screen (laptop ↔ monitor)
        from .. import screen as SCR
        from PySide6.QtCore import QRect
        av = QRect(*SCR.available())                     # the measured area (same as fit())
        if True:
            fg = self.frameGeometry()
            if not restored or not SCR.fits(fg.width(), fg.height(), fg.x(), fg.y(), av):
                if self.isMaximized():
                    self.showNormal()
                prof = SCR.current()
                w = min(prof.win_w if prof else 1420, av.width())
                h = min(prof.win_h if prof else 900, av.height())
                self.resize(w, h)
                self.move(av.x() + (av.width() - w) // 2, av.y() + (av.height() - h) // 2)
        splits = S.get("splits", {}) or {}
        for sp in self.findChildren(QSplitter):
            name = sp.objectName()
            if name and name in splits and splits[name]:
                try:
                    sp.setSizes([int(x) for x in splits[name]])
                except Exception:                        # noqa: BLE001
                    pass

    def _seed(self):
        r = seed.seed_all()
        QMessageBox.information(self, tr("Seed"), str(r))
        self.after_write()

    def _set_cap(self):
        v, ok = QInputDialog.getDouble(
            self, tr("Dnevni limit"), tr("USD po danu (plaćeni provajderi):"),
            budget().daily_cap, 0.0, 500.0, 2)
        if ok:
            budget().set_cap(v)
            self.refresh_status()

    def _save_active(self):
        if self.tabs.currentWidget() is self._tab(self.tab_editor):
            self.tab_editor._save()

    def _tab_changed(self, i: int):
        if self.tabs.widget(i) is self._setup_tab:
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(self._last_tab)
            self.tabs.blockSignals(False)
            self.open_setup()
        else:
            self._last_tab = i
            if self.tabs.widget(i) is self._wraps.get(self.tab_pselab):
                self.tab_pselab.opened()

    def open_weights(self):
        from .pse_lab import WeightsDialog
        WeightsDialog(self).exec()
        self.refresh_status()

    def open_setup(self):
        from .setup import SetupDialog
        SetupDialog(self, first_run=False).exec()
        self.refresh_status()

    def open_wizard(self):
        from .wizard import Wizard
        Wizard(self).exec()
        self.refresh_status()

    # ------------------------------------------------------------------ #
    def open_card(self, card_id: str):
        if card_id.startswith("mission:"):              # rule 47: a mission link
            self.open_mission(card_id[len("mission:"):])
            return
        from ..vault import store as _VS
        p = _VS.path_of(card_id)
        if p is None:
            self.statusBar().showMessage(tr("nema kartice '{0}'").format(card_id), 4000)
            return
        self.tabs.setCurrentWidget(self._tab(self.tab_editor))
        self.tab_editor.refresh()
        self.tab_editor.open_path(p)

    def open_mission(self, mid: str):
        """The mission's workspace in the Missions tab (rules 42, 47)."""
        self.tabs.setCurrentWidget(self._tab(self.tab_missions))
        if not self.tab_missions.open_mission(mid):
            self.statusBar().showMessage(tr("nema misije '{0}'").format(mid), 4000)

    def after_write(self):
        self.tab_corpus.refresh()
        self.tab_plan.refresh()
        self.refresh_status()

    # ---- SHARED_LIB heartbeat + connectivity (review fix 8) -------------- #
    def _start_runtime(self):
        try:                                            # rule 54: open measures re-read
            from ..shared_lib.pse_registry import pse as _pse
            _pse().review_open_measures()
        except Exception:                               # noqa: BLE001 — never blocks the start
            pass
        from ..shared_lib import runtime as RT
        from ..methods import door as DOOR
        RT.install_hooks()
        DOOR.install_hooks()
        from ..shared_lib import missions as _MIS
        _MIS.install_hooks()
        from ..methods import adversary as _ADV
        _ADV.install_hooks()
        self._online = None
        self._rt_timer = QTimer(self)
        self._rt_timer.timeout.connect(self._tick)
        self._rt_timer.start(60_000)
        self._net_timer = QTimer(self)
        self._net_timer.timeout.connect(self._check_net)
        self._net_timer.start(10 * 60_000)
        QTimer.singleShot(1500, self._tick)
        QTimer.singleShot(3000, self._check_net)

    def _tick(self):
        from ..shared_lib import runtime as RT
        try:
            out = RT.tick(online=bool(self._online))
            if out["keepers"]["tampered"]:
                self.statusBar().showMessage(
                    tr("⚠ čuvar: izmijenjen zapečaćen izvještaj — vraćen iz pečata"), 15000)
        except Exception as e:                          # noqa: BLE001
            self.statusBar().showMessage(tr("SHARED_LIB otkucaj: {0}").format(e), 8000)
        self.tab_overview.refresh()
        self.topbar.refresh()
        self._ideas_badge()

    def snapshot(self, what: str = "window"):
        """F12: the active window (a dialog if one is in front); Shift+F12: the active
        tab; 📷: the main window. The path goes to the status bar — never a pop-up."""
        from . import snapshot as SNAP
        if what == "tab":
            w, label = self.tabs.currentWidget(), self.tabs.tabText(self.tabs.currentIndex())
        elif what == "window":
            w = QApplication.activeWindow() or self
            label = "" if w is self else (w.windowTitle() or "dijalog")
        else:
            w, label = self, ""
        try:
            p = SNAP.take(w, label)
        except Exception as e:                          # noqa: BLE001
            self.statusBar().showMessage(tr("Snimak nije uspio: {0}").format(e), 10000)
            return None
        self._shot_path = p
        self.statusBar().showMessage(tr("📷 Snimak: {0}").format(p), 15000)
        if getattr(self, "_shot_open", None) is None:
            from PySide6.QtWidgets import QPushButton
            self._shot_open = QPushButton(tr("Otvori folder"))
            self._shot_open.clicked.connect(self._open_shot_folder)
            self.statusBar().addPermanentWidget(self._shot_open)
        self._shot_open.show()
        QTimer.singleShot(15000, self._shot_open.hide)
        return p

    def open_results(self):
        """📂: the folder with everything the app produced (Andrej, live test)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import config
        config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.RESULTS_DIR)))
        self.statusBar().showMessage(tr("Rezultati: {0}").format(config.RESULTS_DIR), 10000)

    def _open_shot_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from . import snapshot as SNAP
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(SNAP.folder())))

    def _choose_shot_folder(self):
        from PySide6.QtWidgets import QFileDialog
        from . import snapshot as SNAP
        d = QFileDialog.getExistingDirectory(self, tr("Folder za snimke ekrana"), str(SNAP.folder()))
        if d:
            SNAP.set_folder(d)
            self.statusBar().showMessage(tr("Snimci ekrana idu u: {0}").format(d), 8000)

    def _tab(self, w):
        """The tab page as the QTabWidget holds it (wrapped in a scroll area)."""
        return self._wraps.get(w, w)

    def _ideas_badge(self):
        """Item 28: a small badge on the tab instead of pop-ups."""
        try:
            from ..shared_lib import ideas as IDEAS
            n = IDEAS.badge()
        except Exception:                               # noqa: BLE001
            n = 0
        i = self.tabs.indexOf(self._tab(self.tab_ideas))
        self.tabs.setTabText(i, tr("Ideje") + (f" ({n})" if n else ""))

    def _check_net(self):
        from PySide6.QtCore import QThread, QObject, Signal as _Sig

        class _W(QObject):
            done = _Sig(bool)

            def run(self):
                from ..llm import selection as SEL
                try:
                    self.done.emit(SEL.main_reachable())
                finally:
                    QThread.currentThread().quit()      # ends even if the window is gone
        if getattr(self, "_net_thread", None) is not None:
            return
        self._net_thread = QThread()
        self._net_worker = _W()
        self._net_worker.moveToThread(self._net_thread)
        self._net_thread.started.connect(self._net_worker.run)
        self._net_worker.done.connect(self._net_result)
        # a running thread is kept alive by the module, not by the window: a window
        # destroyed mid-check must not destroy a running QThread (that aborts Qt)
        th, wk = self._net_thread, self._net_worker
        _LIVE_THREADS.add((th, wk))
        th.finished.connect(lambda: _LIVE_THREADS.discard((th, wk)))
        self._net_thread.start()

    def _net_result(self, online: bool):
        if self._net_thread is not None:
            self._net_thread.quit()
            self._net_thread.wait(2000)
        self._net_thread = None
        changed = online != self._online
        self._online = online
        if changed:
            from .offline import handle_connectivity
            handle_connectivity(self, online)
            self.topbar.refresh()

    def toggle_chat_expand(self):
        exp = not self.tabs.isHidden()
        self.tabs.setVisible(not exp)
        self.chat.b_expand.setText("⤡" if exp else "⤢")

    def _unexpand_chat(self):
        if self.tabs.isHidden():
            self.toggle_chat_expand()

    def refresh_status(self):
        try:
            from .danger import show_if_pending
            show_if_pending(self)                       # item 16: never silent
        except Exception:                               # noqa: BLE001
            pass
        if hasattr(self, "topbar"):
            self.topbar.refresh()
        from ..shared_lib.pse_registry import pse
        sw = pse().swarm()
        colour = {"healthy": "#7bc67b", "sick": "#ffb74d", "measure": "#ffb74d",
                  "frozen": "#e07070"}[sw["status"]]
        self.lb_theta.setText(
            tr("<span style='color:{0}'>⚖ roj {1}</span> <span style='color:#777'>θ̄ {2:.1f}</span>").format(colour, sw['units'], sw['theta_mean']))
        self.lb_theta.setToolTip(
            tr("Svaki agent je PSE jedinica sa svojim θ (zdravo 30 ± 5).\nZamrznute: {0} · Doktorove mjere čekaju: {1}").format(", ".join(sw["frozen"]) or "—", sw["measures"]))
        st = VS.stats()
        self.lb_vault.setText(f"📚 {st.verified}/{st.total}")
        self.lb_vault.setToolTip(tr("provjerene / ukupno kartica"))
        self.lb_budget.setText("💵 " + budget().status_line())
        self.lb_budget.setToolTip(budget().tooltip())
        g = guardian().self_check()
        if g["quarantined"]:
            self.lb_guard.setText(
                tr("<span style='color:#e07070'>🛡 KARANTIN: {0}</span>").format(', '.join(g['quarantined'])))
        elif g["problems"]:
            self.lb_guard.setText(tr("<span style='color:#ffb74d'>🛡 provjeri</span>"))
        else:
            self.lb_guard.setText(tr("<span style='color:#7bc67b'>🛡 ok</span>").format())
        self.lb_guard.setToolTip(
            tr("{0} zahtjeva · {1} tier-1 · {2} tier-2").format(g['observations'], g['tier1'], g['tier2']))
        # main AI + skeptic pills (plan F3/F6)
        try:
            from ..llm import selection as SEL
            main = SEL.get_main() or "—"
            sk = SEL.get_skeptic() if SEL.skeptic_available() else "nedostupan"
            self.lb_ai.setText(f"🤖 {main} · 🗡 {sk}")
            self.lb_ai.setToolTip(tr("glavni model · skeptik (uvijek drugi model)"))
        except Exception:                               # noqa: BLE001
            self.lb_ai.setText("")
        from ..llm.router import router
        provs = router().available()
        self.lb_net.setText(("🔌 " + ", ".join(provs)) if provs
                            else tr("<span style='color:#ffb74d'>🔌 nema modela</span>"))

    def _reset_layout(self):
        S.set_("splits", {})
        S.set_("geometry", "")
        QMessageBox.information(self, tr("Raspored"),
                                tr("Raspored je resetovan. Vidjećeš ga poslije "
                                "ponovnog pokretanja."))

    def closeEvent(self, e):
        # round 3, item 19: the guardian is a separate process — ask what to close
        if not getattr(self, "_closing_confirmed", False):
            from PySide6.QtWidgets import QMessageBox
            from .. import guardian_app as GA
            if GA.running_pid():
                box = QMessageBox(self)
                box.setWindowTitle(tr("Zatvaranje"))
                box.setText(tr("Čuvar (SSH + prekidač) radi kao poseban proces."))
                b_all = box.addButton(tr("Ugasi sve"), QMessageBox.DestructiveRole)
                b_win = box.addButton(tr("Zatvori prozor, čuvar ostaje"), QMessageBox.AcceptRole)
                box.addButton(tr("Odustani"), QMessageBox.RejectRole)
                box.setDefaultButton(b_win)
                box.exec()
                if box.clickedButton() is b_all:
                    GA.stop()
                elif box.clickedButton() is not b_win:
                    e.ignore()
                    return
        try:                                             # rule 45: closing ends the sessions
            if self.tab_missions.talk.live():
                self.statusBar().showMessage(tr("Agent misije predlaže pamćenje sesije…"))
                self.tab_missions.talk.end_all_blocking(30.0)
        except Exception:                                # noqa: BLE001 — never block the exit
            pass
        th = getattr(self, "_net_thread", None)          # no QThread left running at exit
        if th is not None:
            th.quit()
            th.wait(3000)
        try:
            self._save_layout()
            J.log(J.SYSTEM, "app", {"event": "shutdown"})
        except Exception:                               # noqa: BLE001
            pass
        super().closeEvent(e)
