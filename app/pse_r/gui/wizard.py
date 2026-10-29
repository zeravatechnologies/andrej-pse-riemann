"""
First-run wizard — two screens, and the second one is mostly good news.

Screen 1 · the brain. Four providers, each tested with one real call so you
leave with a green tick rather than a hope. Free tiers are labelled, because
the routing is built so the free ones carry the bulk of the work.

Screen 2 · the sources. Every literature source this app uses is keyless. The
screen says so instead of presenting a wall of empty key fields: each source
shows READY, or OPTIONAL BOOST (a free key that only raises a quota, with the
link), or OFF. The only thing genuinely asked of you is an email — for the
Crossref/OpenAlex polite pool — and it says exactly where that email goes.

There is also one security instruction here that matters more than any setting:
do the first run at home. TLS pins are learned on first contact, so the network
you are on when you first connect is the network you are trusting.
"""
from __future__ import annotations

from ..i18n import tr

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..guardian import policy, secrets as SEC
from ..guardian.egress import network_id
from ..llm.backend import provider_info
from ..llm.router import router
from .widgets import button, hline, small


class _Ping(QObject):
    done = Signal(str, bool, str)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def run(self):
        ok, msg = router().ping(self.provider)
        self.done.emit(self.provider, ok, msg)


class Wizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("PSE Riemann — prvo pokretanje"))
        from .. import screen as SCR
        SCR.fit(self, 880, 660)                         # fits the measured screen
        self._threads: dict = {}
        self.key_edits: dict = {}
        self.status_labels: dict = {}

        root = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_providers())
        self.stack.addWidget(self._page_sources())
        from .widgets import scroll_wrap
        root.addWidget(scroll_wrap(self.stack), 1)    # taller than the screen → scrolls

        nav = QHBoxLayout()
        self.b_back = button(tr("← Nazad"), lambda: self.stack.setCurrentIndex(0))
        self.b_next = button(tr("Dalje →"), self._next, primary=True)
        self.b_done = button(tr("Završi"), self._finish, primary=True)
        self.b_done.hide()
        nav.addWidget(self.b_back)
        nav.addStretch(1)
        nav.addWidget(self.b_next)
        nav.addWidget(self.b_done)
        root.addLayout(nav)
        self.b_back.setEnabled(False)

    # ------------------------------------------------------------------ #
    def _page_providers(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(tr("<h2>1 / 2 · Mozak</h2>")))
        v.addWidget(small(
            tr("Treba ti bar jedan. Tri od četiri imaju besplatan tier, i "
            "aplikacija je namjerno tako rutirana: besplatni modeli rade "
            "trijažu literature i skeptika, a plaćeni samo matematiku i "
            "čitanje table. Ključ ide u ~/.config/pse-riemann/secrets.json "
            "(prava 0600), nikad u vault.")))
        v.addWidget(hline())

        s = SEC.store()
        for info in provider_info():
            g = QGroupBox(f"{info['provider']}   ·   {info['note']}")
            gl = QGridLayout(g)
            e = QLineEdit(s.get(info["key"]))
            e.setEchoMode(QLineEdit.Password)
            e.setPlaceholderText(info["key"])
            self.key_edits[info["provider"]] = (info["key"], e)
            gl.addWidget(QLabel(tr("ključ:")), 0, 0)
            gl.addWidget(e, 0, 1)
            b = button(tr("Testiraj"), lambda _=False, p=info["provider"]: self._test(p))
            gl.addWidget(b, 0, 2)
            st = small("")
            self.status_labels[info["provider"]] = st
            gl.addWidget(st, 1, 1, 1, 2)
            gl.addWidget(small(f"model: {info['default_model']}"
                               + (tr("  ·  vidi slike (tabla)") if info["vision"]
                                  else "")), 2, 1, 1, 2)
            v.addWidget(g)
        v.addStretch(1)
        return w

    def _test(self, provider: str):
        name, edit = self.key_edits[provider]
        val = edit.text().strip()
        if val:
            SEC.store().set(name, val)
        if not SEC.store().has(name):
            self.status_labels[provider].setText(tr("⛔ nema ključa"))
            return
        self.status_labels[provider].setText(tr("… testiram (jedan pravi poziv)"))
        thr = QThread()
        pg = _Ping(provider)
        pg.moveToThread(thr)
        thr.started.connect(pg.run)
        pg.done.connect(self._tested)
        self._threads[provider] = (thr, pg)
        thr.start()

    def _tested(self, provider, ok, msg):
        lb = self.status_labels.get(provider)
        if lb:
            lb.setText((tr("✅ radi · odgovor: ") + msg) if ok
                       else ("⛔ " + msg[:220]))
            from .widgets import _BASE_PT
            lb.setStyleSheet("color:%s;font-size:%.1fpt;" %
                             ("#7bc67b" if ok else "#e07070", _BASE_PT[0] * 0.85))
        t = self._threads.pop(provider, None)
        if t:
            t[0].quit()
            t[0].wait(3000)

    # ------------------------------------------------------------------ #
    def _page_sources(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.addWidget(QLabel(tr("<h2>2 / 2 · Izvori</h2>")))
        outer.addWidget(small(
            tr("<b>Nijedan izvor ne traži plaćen ključ.</b> Većina ne traži "
            "nikakav. Dva imaju opcioni besplatan ključ koji samo diže kvotu. "
            "Jedino što aplikacija stvarno traži od tebe je email — i to samo "
            "zato što Crossref i OpenAlex mole da se predstaviš; ide u "
            "User-Agent i u <code>mailto</code> parametar, nigdje drugdje.")))

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)

        s = SEC.store()
        em = QLineEdit(s.get("CONTACT_EMAIL"))
        em.setPlaceholderText(tr("ti@primjer.com  (opciono, ali pristojno)"))
        self.email = em
        f = QFormLayout()
        f.addRow(tr("email za polite pool:"), em)
        v.addLayout(f)
        v.addWidget(hline())

        cred = [r for r in policy.describe() if r["class"] == "credentialed"]
        anon = [r for r in policy.describe() if r["class"] == "anonymous"]
        self.opt_edits = {}

        v.addWidget(QLabel(tr("<b>Izvori literature i podataka</b>")))
        for r in anon:
            row = QHBoxLayout()
            if r["optional_key"]:
                state, color = tr("OPCIONO POJAČANJE"), "#ef6c00"
            else:
                state, color = tr("SPREMAN"), "#2e7d32"
            tag = QLabel(state)
            from .widgets import _BASE_PT
            tag.setStyleSheet(f"background:{color};color:white;padding:2px 8px;"
                              f"border-radius:3px;"
                              f"font-size:{_BASE_PT[0]*0.72:.1f}pt;"
                              f"font-weight:600;")
            tag.setMinimumWidth(150)
            row.addWidget(tag)
            row.addWidget(QLabel(tr("<code>{0}</code>").format(r['host'])), 0)
            row.addWidget(small(r["why"]), 1)
            if r["optional_key"]:
                e = QLineEdit(s.get(r["key"]))
                e.setPlaceholderText(r["key"] + tr(" (besplatan, diže kvotu)"))
                e.setMaximumWidth(260)
                self.opt_edits[r["key"]] = e
                row.addWidget(e)
            v.addLayout(row)

        v.addWidget(hline())
        v.addWidget(QLabel(tr("<b>Model API-ji</b> (podešeni na prethodnom ekranu)")))
        for r in cred:
            ok = SEC.store().has(r["key"])
            v.addWidget(small(("✅ " if ok else "○ ") + r["host"] + " — " + r["why"],
                              "#7bc67b" if ok else "#888"))

        v.addWidget(hline())
        warn = QGroupBox(tr("⚠ Prije puta — pročitaj ovo"))
        wl = QVBoxLayout(warn)
        wl.addWidget(small(
            tr("Trenutna mreža: <code>{0}</code><br><br>Aplikacija pamti javne ključeve (TLS pinove) svakog servera pri <b>prvom kontaktu</b> i poslije odbija da razgovara sa serverom koji ih ne pokazuje. To je odbrana od presretanja na tuđem WiFi-ju — ali vrijedi tačno onoliko koliko vrijedi mreža na kojoj je prvi kontakt napravljen.<br><br><b>Zato: uradi prvi test svih provajdera i jedno 'Skupi' sa mreže kojoj vjeruješ (kuća), prije nego što kreneš.</b> Poslije toga, ako se na hotelskom WiFi-ju pojavi drugačiji sertifikat, aplikacija će stati i reći ti.").format(network_id()), "#ddd"))
        v.addWidget(warn)
        v.addStretch(1)

        sc.setWidget(inner)
        outer.addWidget(sc, 1)
        return w

    # ------------------------------------------------------------------ #
    def _next(self):
        self._save_keys()
        if not router().available():
            r = QMessageBox.question(
                self, tr("Nema nijednog provajdera"),
                tr("Nijedan model nije podešen. Lab, whiteboard i editor rade i "
                "bez modela, ali chat, trijaža i transkripcija neće.\n\n"
                "Nastaviti ipak?"))
            if r != QMessageBox.Yes:
                return
        self.stack.setCurrentIndex(1)
        self.b_back.setEnabled(True)
        self.b_next.hide()
        self.b_done.show()

    def _save_keys(self):
        s = SEC.store()
        for _p, (name, edit) in self.key_edits.items():
            v = edit.text().strip()
            if v:
                s.set(name, v)

    def _finish(self):
        self._save_keys()
        s = SEC.store()
        if self.email.text().strip():
            s.set("CONTACT_EMAIL", self.email.text().strip())
        for k, e in self.opt_edits.items():
            if e.text().strip():
                s.set(k, e.text().strip())
        s.set("_WIZARD_DONE", "1")
        self.accept()


def needed() -> bool:
    return not SEC.store().has("_WIZARD_DONE")
