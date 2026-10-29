"""
First-run setup window (round 3, item 8) — before the main window.

Five steps: operator · main AI · skeptic · declarations · guardian & sources.
The window only collects choices; setup_flow.apply() changes state. The same
window is reachable later from the palette ("Podešavanje — prvo podešavanje").
"""
from __future__ import annotations

from ..i18n import tr

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import setup_flow as SF
from ..llm import providers as P
from .widgets import button, hline, small

CUSTOM, GGUF, NONE, NO_SKEPTIC = "__custom__", "__gguf__", "__none__", "__noskeptic__"


class _Job(QObject):
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:                          # noqa: BLE001 — shown to the user
            self.done.emit(e)


class _Relay(QObject):
    """Lives in the GUI thread: the job's result is delivered HERE (queued), never in
    the worker thread. Live test rc3: the OpenRouter model list (hundreds of names)
    was put into the combo from the worker thread and the app crashed."""

    def __init__(self, cb, parent):
        super().__init__(parent)
        self.cb = cb

    @Slot(object)
    def deliver(self, res):
        self.cb(res)


def _run_bg(owner, fn, on_done):
    th, job = QThread(), _Job(fn)
    job.moveToThread(th)
    th.started.connect(job.run)

    def fin(res):
        th.quit()
        th.wait(2000)
        owner._jobs.discard((th, job, relay))
        relay.deleteLater()
        on_done(res)
    relay = _Relay(fin, owner)
    job.done.connect(relay.deliver)                     # queued: relay is in the GUI thread
    owner._jobs.add((th, job, relay))
    th.start()


class ModelPicker(QWidget):
    """List of every option on the left, details of the selected one on the right."""

    def __init__(self, skeptic: bool = False, parent=None):
        super().__init__(parent)
        self._jobs: set = set()
        self.skeptic = skeptic
        self.gguf_info: dict = {}
        h = QHBoxLayout(self)
        self.lst = QListWidget()
        from .. import screen as SCR
        self.lst.setFixedWidth(int(340 * SCR.k()))
        if skeptic:
            self._add(NO_SKEPTIC, tr("Bez skeptika"), tr("samo determinističke provjere"))
        for pid, pr in P.PRESETS.items():
            self._add(pid, tr(pr.label), tr(pr.note))
        self._add(CUSTOM, tr("Vlastita adresa…"), tr("bilo koji OpenAI-kompatibilan servis"))
        self._add(GGUF, tr("Lokalni GGUF…"), tr("sa bilo kog mjesta, bez kopiranja"))
        if not skeptic:
            self._add(NONE, tr("Bez AI za sada"), tr("šta radi, a šta ne"))
        h.addWidget(self.lst)
        self.detail = QVBoxLayout()
        box = QWidget()
        box.setLayout(self.detail)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # wrap, never cut
        sc.setWidget(box)
        h.addWidget(sc, 1)

        self.key = QLineEdit(); self.key.setEchoMode(QLineEdit.Password)
        self.key.editingFinished.connect(self._key_entered)      # key typed → real model list
        self.model = QComboBox(); self.model.setEditable(True)
        self.c_name = QLineEdit(); self.c_url = QLineEdit(); self.c_url.setPlaceholderText(
            "https://moj-server.example/v1")
        self.g_path = QLineEdit()
        self.status = small("")
        self.lst.currentRowChanged.connect(lambda _: self._show())
        self.lst.setCurrentRow(1 if skeptic else 0)

    def _add(self, key, text, tip=""):
        it = QListWidgetItem(text)
        it.setData(Qt.UserRole, key)
        it.setToolTip(tip)
        self.lst.addItem(it)

    def current(self) -> str:
        it = self.lst.currentItem()
        return it.data(Qt.UserRole) if it else ""

    def _clear(self):
        # the input fields live across option switches: park them on self first,
        # or Qt deletes them together with the container they sat in
        for keep in (self.key, self.model, self.c_name, self.c_url, self.g_path, self.status):
            keep.hide()
            keep.setParent(self)
        while self.detail.count():
            w = self.detail.takeAt(0).widget()
            if w is not None:
                w.setParent(None)

    def _show(self):
        self._clear()
        k = self.current()
        d = self.detail
        self.status.setText("")
        if k in P.PRESETS:
            pr = P.PRESETS[k]
            adv = P.billing_advice(k)
            d.addWidget(QLabel(tr("<h3>{0}</h3>").format(tr(pr.label))))
            d.addWidget(small(tr("✓ bolje kada: {0}<br>✗ slabije kada: {1}").format(tr(pr.better), tr(pr.worse))))
            d.addWidget(small(tr("<b>Naplata pri prekidu:</b> {0}").format(tr(adv['text'])),
                              "#ffc257" if adv.get("caps") == "strict" else "#7bc67b"))
            f = QFormLayout()
            from ..guardian import secrets as SEC
            self.key.setText(SEC.store().get(pr.key_name))
            self.key.setPlaceholderText(pr.key_name)
            f.addRow(tr("ključ:"), self.key)
            # live test: the menu offered ONE model — now the saved choice first, and the
            # server's real list loads by itself as soon as there is a key
            from .. import settings as _S
            saved = (_S.get("models") or {}).get(k) or pr.default_model
            self.model.clear()
            self.model.addItems(list(dict.fromkeys([saved, pr.default_model])))
            self.model.setCurrentText(saved)
            if self.key.text().strip():
                self._load_models(quiet=True)
            f.addRow(tr("model:"), self.model)
            w = QWidget(); w.setLayout(f); d.addWidget(w)
            row = QHBoxLayout()
            row.addWidget(button(tr("Učitaj prave modele"), self._load_models))
            row.addWidget(button(tr("Testiraj (1 pravi poziv)"), self._test))
            row.addStretch(1)
            rw = QWidget(); rw.setLayout(row); d.addWidget(rw)
            d.addWidget(small(tr("Ključ praviš / opozivaš ovdje: {0}").format(pr.console)))
        elif k == CUSTOM:
            d.addWidget(QLabel(tr("<h3>Vlastita OpenAI-kompatibilna adresa</h3>")))
            d.addWidget(small(tr("Bilo koji servis koji govori OpenAI chat-completions. Adresa se "
                              "NE otvara sama: postaje deklaracija koju potvrđuješ u 4. koraku. "
                              "Samo https. Ključ ide isključivo na tu adresu. Naplata pri "
                              "prekidu je nepoznata — računa se najgori slučaj.")))
            f = QFormLayout()
            f.addRow(tr("ime:"), self.c_name); f.addRow(tr("adresa (base URL):"), self.c_url)
            self.model.clear(); f.addRow(tr("model:"), self.model)
            self.key.setText(""); f.addRow(tr("ključ:"), self.key)
            w = QWidget(); w.setLayout(f); d.addWidget(w)
        elif k == GGUF:
            d.addWidget(QLabel(tr("<h3>Lokalni GGUF</h3>")))
            d.addWidget(small(tr("Model ostaje gdje jeste (bez kopiranja). Prima se po sha256: "
                              "poredim sa objavljenim hash-om; ako ga nema, deklarišeš ga ti. "
                              "Radi bez interneta i ne smije se obratiti nijednoj adresi osim "
                              "ovog računara.")))
            row = QHBoxLayout()
            row.addWidget(self.g_path, 1)
            row.addWidget(button(tr("Izaberi…"), self._pick_gguf))
            rw = QWidget(); rw.setLayout(row); d.addWidget(rw)
            from .. import machine as MCH
            mp = MCH.profile()
            d.addWidget(small(tr("Ova mašina: {0} · niti {1} · kontekst {2} · rok {3:.0f} s{4}").format(
                tr(mp.label), mp.threads, mp.n_ctx, mp.call_timeout_s,
                "" if mp.measured else tr(" · brojke su procjena")), "#9aa4b5"))
            for note in mp.notes:
                d.addWidget(small("⚠ " + tr(note), "#ffc257"))
            from ..llm import gguf as G
            for m in G.list_models():
                d.addWidget(button(tr("iz models/: {0} ({1} GB)").format(m['name'], m['gb']),
                                   lambda _=False, p=m["path"]: self._set_gguf(p)))
        elif k == NONE:
            d.addWidget(QLabel(tr("<h3>Bez AI za sada</h3>")))
            d.addWidget(small(tr("<b>Radi:</b>") + "<br>• " + "<br>• ".join(tr(x) for x in SF.NO_AI_TEXT["radi"]),
                              "#7bc67b"))
            d.addWidget(small(tr("<b>Ne radi:</b>") + "<br>• " + "<br>• ".join(tr(x) for x in SF.NO_AI_TEXT["ne radi"]),
                              "#e07070"))
            d.addWidget(small(tr("AI dodaješ kad hoćeš (paleta → Podešavanje).")))
        elif k == NO_SKEPTIC:
            d.addWidget(QLabel(tr("<h3>Bez skeptika</h3>")))
            d.addWidget(small(tr("Tvrdnje i dalje napadaju determinističke provjere: test "
                              "reprodukcije, porijeklo brojeva, kapija, nivoi izvora. "
                              "Nezavisni drugi model je jača provjera — preporuka je skeptik.")))
        d.addWidget(self.status)
        d.addStretch(1)
        for keep in (self.key, self.model, self.c_name, self.c_url, self.g_path, self.status):
            if keep.parent() is not self:
                keep.show()

    # -- actions --------------------------------------------------------- #
    def _with_key(self):
        from ..guardian import secrets as SEC
        pr = P.PRESETS[self.current()]
        if self.key.text().strip():
            SEC.store().set(pr.key_name, self.key.text().strip())
        return pr

    def _key_entered(self):
        if self.current() in P.PRESETS and self.key.text().strip():
            self._load_models(quiet=True)

    def _load_models(self, quiet: bool = False):
        pr = self._with_key()
        if not quiet:
            self.status.setText(tr("… pitam server za spisak modela"))
        from ..llm import backend as B
        from ..llm.router import chat_models

        def done(res):
            if isinstance(res, Exception):
                if not quiet:
                    self.status.setText(f"⛔ {str(res)[:240]}")
                return
            names = chat_models(res)
            if not names:
                return
            cur = self.model.currentText()
            self.model.clear()
            self.model.addItems(names)
            self.model.setCurrentText(cur if cur in names else (pr.default_model if pr.default_model in names else names[0]))
            self.status.setText(tr("✅ {0} modela sa servera — izaberi pa „Testiraj“").format(len(names)))
        _run_bg(self, lambda: B.list_models(pr.provider), done)

    def _test(self):
        pr = self._with_key()
        self.status.setText(tr("… jedan pravi poziv"))
        from ..llm.router import router

        model = self.model.currentText().strip()

        def done(res):
            ok, msg = (False, str(res)) if isinstance(res, Exception) else res
            self.status.setText((tr("✅ radi · ") if ok else "⛔ ") + msg[:240])
            from .. import settings as _S                # a recovered model shows in the menu
            got = (_S.get("models") or {}).get(pr.provider)
            if ok and got and got != self.model.currentText():
                if self.model.findText(got) < 0:
                    self.model.addItem(got)
                self.model.setCurrentText(got)
        _run_bg(self, lambda: router().ping(pr.provider, model), done)

    def _pick_gguf(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Izaberi GGUF"), str(Path.home()),
                                           "GGUF (*.gguf)")
        if p:
            self._set_gguf(p)

    def _set_gguf(self, p):
        self.g_path.setText(p)
        self.status.setText(tr("… računam sha256 (veliki fajl: do pola minute)"))

        def done(res):
            if isinstance(res, Exception):
                self.status.setText(f"⛔ {res}")
                return
            self.gguf_info[res["path"]] = res
            self.status.setText(("✅ " if res["published"] else "⚠ ") + res["note"]
                                + "<br><code>{0}</code>".format(res['sha256']))
        _run_bg(self, lambda: SF.gguf_check(p), done)

    def choice(self):
        k = self.current()
        if k in (NONE, NO_SKEPTIC, ""):
            return SF.ModelChoice("none")
        if k in P.PRESETS:
            return SF.ModelChoice("cloud", provider=k, key=self.key.text().strip(),
                                  model=self.model.currentText().strip())
        if k == CUSTOM:
            return SF.ModelChoice("custom", key=self.key.text().strip(),
                                  model=self.model.currentText().strip(),
                                  custom_name=self.c_name.text().strip(),
                                  custom_url=self.c_url.text().strip())
        return SF.ModelChoice("gguf", gguf_path=self.g_path.text().strip())

    def describe(self) -> str:
        c = self.choice()
        if c.kind == "none":
            return tr("bez skeptika") if self.skeptic else tr("bez AI za sada")
        if c.kind == "cloud":
            return "{0} · model {1}".format(P.PRESETS[c.provider].label, c.model)
        if c.kind == "custom":
            return tr("vlastita adresa „{0}“ {1} · model {2}").format(c.custom_name, c.custom_url, c.model)
        info = self.gguf_info.get(str(Path(c.gguf_path).expanduser().resolve()))
        tail = (" · " + info["note"]) if info else tr(" · hash još nije izračunat")
        return tr("GGUF {0}{1}").format(c.gguf_path, tail)


class SetupDialog(QDialog):
    def __init__(self, parent=None, first_run: bool = True):
        super().__init__(parent)
        self.setWindowTitle(tr("PSE Riemann — prvo podešavanje") if first_run
                            else tr("PSE Riemann — podešavanje"))
        from .. import screen as SCR
        SCR.fit(self, 1180, 760, 1000, 640)           # fits the measured screen
        root = QVBoxLayout(self)
        self.title = QLabel("")
        root.addWidget(self.title)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 1 operator
        p1 = QWidget(); v = QVBoxLayout(p1)
        from ..shared_lib import operator as OP
        self.op = QLineEdit(OP.current() or OP.last_used())
        v.addWidget(small(tr("Upiši svoje ime. Bez lozinke: ime se veže za svaki run, upis, "
                          "odluku i izvještaj, a glas SHARED_LIB-a govori samo tebi.")))
        f = QFormLayout(); f.addRow(tr("ime operatera:"), self.op)
        w = QWidget(); w.setLayout(f); v.addWidget(w); v.addStretch(1)
        # 2 main / 3 skeptic
        self.main = ModelPicker(False)
        self.sk = ModelPicker(True)
        # 4 declarations
        p4 = QWidget(); v4 = QVBoxLayout(p4)
        self.decl_view = small("")
        self.decl_view.setWordWrap(True)
        v4.addWidget(self.decl_view)
        self.cb_confirm = QCheckBox(tr("Potvrđujem ove deklaracije (inače čekaju u „Čeka tvoju "
                                    "odluku“)"))
        self.cb_confirm.setChecked(True)
        v4.addWidget(self.cb_confirm); v4.addStretch(1)
        # 5 guardian + sources
        p5 = QWidget(); v5 = QVBoxLayout(p5)
        self.cb_auto = QCheckBox(tr("Pokreni čuvara (SSH + domaćin) automatski pri prijavi u sistem"))
        v5.addWidget(self.cb_auto)
        v5.addWidget(small(tr("Čuvar je zaseban proces sa ikonom u traci; radi i kad zatvoriš "
                           "prozor. Ovo se kasnije mijenja u podešavanju.")))
        v5.addWidget(hline())
        from ..guardian import secrets as SEC
        self.email = QLineEdit(SEC.store().get("CONTACT_EMAIL"))
        self.email.setPlaceholderText(tr("ti@primjer.com (opciono — Crossref/OpenAlex polite pool)"))
        f5 = QFormLayout(); f5.addRow(tr("email za izvore:"), self.email)
        w5 = QWidget(); w5.setLayout(f5); v5.addWidget(w5)
        g = QGroupBox(tr("⚠ Prvi kontakt sa mrežom"))
        gl = QVBoxLayout(g)
        from ..guardian.egress import network_id
        gl.addWidget(small(tr("Trenutna mreža: <code>{0}</code>. TLS ključevi servera se pamte pri prvom kontaktu — uradi prvi test sa mreže kojoj vjeruješ (kuća).").format(network_id())))
        v5.addWidget(g); v5.addStretch(1)

        self.pages = [(tr("1 / 5 · Operater"), p1), (tr("2 / 5 · Glavni AI"), self.main),
                      (tr("3 / 5 · Skeptik (drugi model)"), self.sk),
                      (tr("4 / 5 · Deklaracije"), p4), (tr("5 / 5 · Čuvar i izvori"), p5)]
        for _, pg in self.pages:
            self.stack.addWidget(pg)

        nav = QHBoxLayout()
        self.b_back = button(tr("← Nazad"), lambda: self._go(-1))
        self.b_next = button(tr("Dalje →"), lambda: self._go(+1), primary=True)
        self.b_done = button(tr("Završi"), self._finish, primary=True)
        nav.addWidget(self.b_back); nav.addStretch(1)
        nav.addWidget(self.b_next); nav.addWidget(self.b_done)
        root.addLayout(nav)
        self._go(0)

    def _go(self, step: int):
        i = self.stack.currentIndex() + step
        if step > 0 and self.stack.currentIndex() == 0:
            from ..shared_lib import operator as OP
            if not OP.valid_name(self.op.text().strip()):
                QMessageBox.warning(self, tr("Ime"), tr("Ime: 2–40 slova (bez posebnih znakova)."))
                return
        if step > 0 and self.stack.currentWidget() is self.main \
                and self.main.choice().kind == "none":
            i += 1                                       # no main AI → no skeptic step
        if step < 0 and i == 2 and self.main.choice().kind == "none":
            i -= 1
        i = max(0, min(i, len(self.pages) - 1))
        self.stack.setCurrentIndex(i)
        self.title.setText(tr("<h2>{0}</h2>").format(self.pages[i][0]))
        self.b_back.setEnabled(i > 0)
        self.b_next.setVisible(i < len(self.pages) - 1)
        self.b_done.setVisible(i == len(self.pages) - 1)
        if self.pages[i][1] is self.stack.widget(3):
            self.decl_view.setText(
                tr("<b>Glavni AI:</b> ") + self.main.describe() + "<br><br>"
                + (tr("<b>Skeptik:</b> ") + self.sk.describe() + "<br><br>"
                   if self.main.choice().kind != "none" else "")
                + tr("GGUF: hash se poredi sa objavljenim i upisuje kao deklaracija. "
                  "Vlastita adresa: postaje deklarisana tek kad je potvrdiš. Cloud preset: "
                  "ključ ide samo njegovom hostu (allowlista)."))

    def _finish(self):
        c = SF.SetupChoices(
            operator=self.op.text().strip(), main=self.main.choice(),
            skeptic=(self.sk.choice() if self.main.choice().kind != "none" else None),
            confirm_declarations=self.cb_confirm.isChecked(),
            guardian_autostart=self.cb_auto.isChecked(), contact_email=self.email.text())
        try:
            out = SF.apply(c)
        except Exception as e:                           # noqa: BLE001 — shown, stays open
            QMessageBox.warning(self, tr("Podešavanje"), str(e))
            return
        QMessageBox.information(
            self, tr("Podešeno"),
            tr("Glavni: {0}\nSkeptik: {1}\n\n").format(out['main'] or 'bez AI', out['skeptic'] or 'nema')
            + "\n".join("• " + n for n in out["notes"]))
        self.accept()
