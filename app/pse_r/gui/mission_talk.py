"""
The conversation in the mission workspace (plan 33f; agreement rules 42–45).

It sits in the lower right of the Missions tab. A click on a mission starts the
agent at once (rule 43): it reads the state, the memory of the last session
and the session's papers, writes the first message and waits. The paper strip
folds open ("N od M izabrano ▾"); papers new since the last session are marked.
„Zadaj da čita…“ hands the agent a paper, an arXiv full text, a card, a report
or a note (rule 44). „Završi razgovor“, a switch to another mission or closing
the app ends the session: the agent proposes the memory, saved at once as
unreviewed until the operator reviews it (rule 45). Model calls run in the
background; the window never freezes, and errors are said in the conversation,
not in a pop-up.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QTextEdit,
                               QToolButton, QVBoxLayout, QWidget)

from ..i18n import tr
from ..shared_lib import mission_agent as MA
from .widgets import MarkdownView, button, small


class _Bridge(QObject):
    done = Signal(object, object, str)          # callback, result, error


class MissionTalk(QWidget):
    proposed = Signal()                          # conclusion items went to the queue
    memory_ready = Signal(str)                   # mission id: a memory proposal was saved
    ended = Signal(str)                          # mission id: the session ended

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mid = None
        self.conv = None
        self._convs: dict = {}                   # mission id -> live Conversation
        self._busy = False
        self._dirty_refs = False
        self._note = ""                          # a line shown above the talk (no pop-ups)
        self._br = _Bridge()
        self._br.done.connect(self._done)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)

        # the paper strip (rule 42): folds open
        strip = QHBoxLayout()
        self.b_papers = QToolButton()
        self.b_papers.setCheckable(True)
        self.b_papers.toggled.connect(self._toggle_papers)
        strip.addWidget(self.b_papers)
        self.b_assign = QToolButton()
        self.b_assign.setText(tr("Zadaj da čita…"))
        self.b_assign.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(self.b_assign)
        m.addAction(tr("Rad iz liste…"), self._assign_paper)
        m.addAction(tr("Puni tekst arXiv rada…"), self._assign_fulltext)
        m.addAction(tr("Karticu…"), self._assign_card)
        m.addAction(tr("Izvještaj…"), self._assign_report)
        m.addAction(tr("Bilješku…"), self._assign_note)
        self.b_assign.setMenu(m)
        strip.addWidget(self.b_assign)
        self.state = small("")
        strip.addWidget(self.state, 1)
        v.addLayout(strip)
        self.papers = QListWidget()
        self.papers.setMaximumHeight(170)
        self.papers.itemChanged.connect(self._paper_changed)
        self.papers.hide()
        v.addWidget(self.papers)

        self.view = MarkdownView()
        v.addWidget(self.view, 1)
        self.input = QTextEdit()
        self.input.setPlaceholderText(tr("Odgovori agentu ili ga pitaj…"))
        self.input.setMaximumHeight(64)
        v.addWidget(self.input)
        row = QHBoxLayout()
        self.b_send = button(tr("Pošalji"), self._say, primary=True)
        self.b_start = button(tr("Počni razgovor"), self._start, primary=True)
        self.b_conclude = button(tr("Sastavi zaključak"), self._conclude)
        self.b_end = button(tr("Završi razgovor"), self.end_session)
        for b in (self.b_start, self.b_send, self.b_conclude, self.b_end):
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self._count()
        self._buttons()

    # ------------------------------------------------------------------ #
    def open_for(self, mid: str, autostart: bool = True) -> None:
        """Show the mission's session; start the agent on a click (rule 43)."""
        if self.mid and self.mid != mid and self._dirty_refs:
            self._apply_refs()
        self.mid = mid
        self.conv = self._convs.get(mid)
        self._note = ""
        self._fill_papers()
        if self.conv is not None:
            self._render()
        elif autostart:
            self._start()
        else:
            self.view.set_markdown(tr("_Klikni na misiju (ili „Počni razgovor“): agent pročita "
                                      "stanje, pamćenje i radove i napiše prvu poruku._"))
        self._buttons()

    def _fill_papers(self) -> None:
        self.papers.blockSignals(True)
        self.papers.clear()
        sp = MA.session_papers(self.mid) if self.mid else []
        chosen = set(self.conv.refs) if self.conv is not None else {p["ref"] for p in sp if p["chosen"]}
        for p in sp:
            mark = tr("🆕 novo · ") if p["new"] else ""
            it = QListWidgetItem(f"{mark}[{tr(p['origin'])}] {p['title'][:100]} — {p['ref']}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if p["ref"] in chosen else Qt.Unchecked)
            it.setData(Qt.UserRole, p["ref"])
            self.papers.addItem(it)
        if not sp:
            self.papers.addItem(QListWidgetItem(tr("(misija još nema radova; razgovor ide o stanju misije)")))
        self.papers.blockSignals(False)
        self._dirty_refs = False
        self._count()

    def _refs(self) -> list:
        return [self.papers.item(i).data(Qt.UserRole) for i in range(self.papers.count())
                if self.papers.item(i).data(Qt.UserRole)
                and self.papers.item(i).checkState() == Qt.Checked]

    def _count(self) -> None:
        n = sum(1 for i in range(self.papers.count()) if self.papers.item(i).data(Qt.UserRole))
        arrow = "▴" if self.papers.isVisible() else "▾"
        self.b_papers.setText(tr("{0} od {1} radova izabrano {2}").format(len(self._refs()), n, arrow))

    def _toggle_papers(self, on: bool) -> None:
        self.papers.setVisible(on)
        if not on and self._dirty_refs:
            self._apply_refs()
        self._count()

    def _paper_changed(self, _it) -> None:
        self._dirty_refs = True
        self._count()

    def _apply_refs(self) -> None:
        """The strip's choice reaches the agent from its next move (no model call)."""
        self._dirty_refs = False
        if self.conv is not None and set(self._refs()) != set(self.conv.refs):
            MA.set_refs(self.conv, self._refs())
            self._render()

    # ------------------------------------------------------------------ #
    def _run(self, fn, label: str, cb, gate: bool = True) -> None:
        if gate:
            if self._busy:
                return
            self._busy = True
        self.state.setText(label)
        self._buttons()

        def work():
            try:
                self._br.done.emit(cb, fn(), "")
            except Exception as e:                       # noqa: BLE001 — said in the talk
                self._br.done.emit(cb, None, str(e) or type(e).__name__)
        threading.Thread(target=work, name="mission-talk", daemon=True).start()

    def _done(self, cb, res, err: str) -> None:
        cb(res, err)
        self._buttons()

    def _free(self) -> None:
        self._busy = False
        self.state.setText("")

    def _buttons(self) -> None:
        live = self.conv is not None
        self.b_start.setVisible(not live)
        self.b_start.setEnabled(bool(self.mid) and not self._busy)
        for b in (self.b_send, self.b_conclude, self.b_end):
            b.setVisible(live)
            b.setEnabled(live and not self._busy)
        self.b_assign.setEnabled(live and not self._busy)

    def _say_error(self, err: str) -> None:
        self._note = "> ⚠ " + err.replace("\n", " ")
        if self.conv is not None:
            self._render()
        else:
            self.view.set_markdown(self._note)

    def _render(self) -> None:
        if self.conv is None:
            return
        md = MA.to_markdown(self.conv)
        i = md.find("\n### ")                         # the workspace shows the turns, not the file head
        md = md[i + 1:] if i >= 0 else ""
        if self._note:
            md += "\n\n" + self._note
        self.view.set_markdown(md)
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        if not self.mid:
            return
        mid, refs = self.mid, (self._refs() if self.papers.count() else None)

        def cb(res, err):
            self._free()
            if err:
                if mid == self.mid:
                    self._say_error(err)
                return
            self._convs[mid] = res
            if mid == self.mid:
                self.conv = res
                self._note = ""
                self._fill_papers()
                self._render()
        self.view.set_markdown(tr("_Agent čita stanje misije, pamćenje i radove…_"))
        self._run(lambda: MA.start(mid, refs), tr("agent čita…"), cb)

    def _after(self, res, err):
        self._free()
        if err:
            self._say_error(err)
            return
        self._note = ""
        self._render()

    def _say(self) -> None:
        txt = self.input.toPlainText().strip()
        if not txt or self.conv is None or self._busy:
            return
        if self._dirty_refs:
            self._apply_refs()
        self.input.clear()
        conv = self.conv
        self._run(lambda: MA.say(conv, txt), tr("agent razmišlja…"), self._after)

    def _conclude(self) -> None:
        if self.conv is None:
            return
        conv = self.conv

        def cb(res, err):
            self._after(res, err)
            if not err:
                self.proposed.emit()
        self._run(lambda: MA.conclude(conv), tr("sastavljam zaključak…"), cb)

    # ---- „Zadaj da čita…“ (rule 44) ----------------------------------- #
    def _assign(self, kind: str, ref: str, text: str = "") -> None:
        conv = self.conv
        if conv is None:
            return

        def cb(res, err):
            self._after(res, err)
            self._fill_papers()
        self._run(lambda: MA.assign(conv, kind, ref, text), tr("agent dobija štivo…"), cb)

    def _assign_paper(self) -> None:
        if self.conv is None:
            return
        rest = [p for p in MA.session_papers(self.mid) if p["ref"] not in self.conv.refs]
        if not rest:
            self._say_error(tr("Svi radovi misije su već izabrani."))
            return
        labels = [f"{p['title'][:80]} — {p['ref']}" for p in rest]
        lab, ok = QInputDialog.getItem(self, tr("Zadaj da čita"), tr("Koji rad?"), labels, 0, False)
        if ok and lab:
            self._assign("rad", rest[labels.index(lab)]["ref"])

    def _assign_fulltext(self) -> None:
        if self.conv is None:
            return
        arx = [p["ref"] for p in MA.session_papers(self.mid) if p["ref"].startswith("arxiv:")]
        if not arx:
            self._say_error(tr("Puni tekst postoji samo za arXiv radove; ova misija ih nema."))
            return
        ref, ok = QInputDialog.getItem(self, tr("Puni tekst"), tr("Koji arXiv rad?"), arx, 0, False)
        if ok and ref:
            self._assign("puni", ref)

    def _assign_card(self) -> None:
        cid, ok = QInputDialog.getText(self, tr("Zadaj da čita"), tr("ID kartice:"))
        if ok and cid.strip():
            self._assign("kartica", cid.strip())

    def _assign_report(self) -> None:
        from .. import config
        p, _ = QFileDialog.getOpenFileName(self, tr("Izvještaj"), str(config.RESULTS_DIR),
                                           tr("Tekst (*.md *.txt)"))
        if p:
            self._assign("izvjestaj", p)

    def _assign_note(self) -> None:
        txt, ok = QInputDialog.getMultiLineText(self, tr("Bilješka"), tr("Šta agent treba da pročita:"))
        if ok and txt.strip():
            self._assign("biljeska", "", txt)

    # ---- end of the session (rule 45) ---------------------------------- #
    def end_session(self, mid: str = "") -> None:
        """Završi razgovor / another mission: the agent proposes the memory in the
        background; it is saved at once as unreviewed."""
        mid = mid or self.mid
        conv = self._convs.pop(mid, None)
        if mid == self.mid:
            if self._dirty_refs:
                self._apply_refs()
            self.conv = None
            self._note = ""
            self.view.set_markdown(tr("_Razgovor je završen i sačuvan u rezultatima._"))
        self.ended.emit(mid)
        if conv is None or not MA._talked(conv):
            self._buttons()
            return

        def cb(res, err):
            self.state.setText("")
            if err:
                if mid == self.mid:
                    self._say_error(tr("Pamćenje nije predloženo: {0}").format(err))
                return
            if mid == self.mid and res:
                self.view.set_markdown(tr("_Razgovor je završen i sačuvan u rezultatima. Agent je "
                                          "predložio pamćenje ({0} stavki) — pregledaj ga gore "
                                          "desno i „Sačuvaj pamćenje“._").format(len(res)))
            self.memory_ready.emit(mid)
        self._run(lambda: MA.propose_memory(conv), tr("agent predlaže pamćenje…"), cb, gate=False)

    def end_all_blocking(self, timeout: float = 30.0) -> int:
        """Closing the app: propose the memory of every live session, waiting at
        most `timeout` seconds in all. Returns how many were saved."""
        import time as _t
        convs = [c for c in self._convs.values() if MA._talked(c)]
        self._convs.clear()
        done = []

        def work():
            for c in convs:
                try:
                    if MA.propose_memory(c):
                        done.append(c.mid)
                except Exception:                        # noqa: BLE001 — the talk stays saved
                    pass
        t = threading.Thread(target=work, name="mission-memory-exit", daemon=True)
        t.start()
        end = _t.time() + timeout
        while t.is_alive() and _t.time() < end:
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            t.join(0.1)
        return len(done)

    def live(self) -> bool:
        return any(MA._talked(c) for c in self._convs.values())
