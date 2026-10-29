"""
QRH tabs (plan F6): the Missions tab and the "Čeka tvoju odluku" queue.

Missions shows the standing question, the frontier B it has reached, and the
log of {state, action, outcome} steps — the heart of the project (plan §0).

The queue is the single place where everything that needs the operator waits:
method proposals (reproduced, awaiting confirmation), skeptic objections,
declarations, and tier-2 healing actions. Approve / Ne odobri call the SAME
store().decide the backend uses, so a click here is a real, journalled decision
bound to the operator's name. "Uvezi metodu" sends a method pack through the
door (reproduction test first). A small chooser picks the main and skeptic
models.

The visual styling is the shared dark QSS; nothing here needs its own look.
"""
from __future__ import annotations

from ..i18n import tr

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QMessageBox, QVBoxLayout, QWidget)

from ..shared_lib import missions as MIS
from ..shared_lib import operator as OP
from ..shared_lib.store import store
from ..methods import door as DOOR
from ..methods import pack as PK
from ..llm import selection as SEL
from .widgets import MarkdownView, button, flow_row, hline, short_combo, small


class MemoryPanel(QWidget):
    """Rules 45–46: the mission memory the agent proposed — tick, delete or add,
    then „Sačuvaj pamćenje“. It stands beside the operator's „Gdje si stao“."""
    saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QListWidget
        self.mid = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.head = QLabel("")
        self.head.setWordWrap(True)
        v.addWidget(self.head)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        v.addWidget(self.list, 1)
        v.addWidget(flow_row(button(tr("Dodaj"), self._add),
                             button(tr("Obriši"), self._delete),
                             button(tr("Sačuvaj pamćenje"), self._save, primary=True)))

    def show_for(self, mid: str) -> None:
        from PySide6.QtWidgets import QListWidgetItem
        from ..shared_lib import mission_agent as MA
        self.mid = mid
        self.list.clear()
        mem = MA.memory(mid) if mid else None
        if not mem or not mem.get("items"):
            self.head.setText(tr("<b>Pamćenje misije</b> — prazno"))
            self.head.setToolTip(tr("<b>Pamćenje misije</b> — prazno. Agent ga predlaže na kraju "
                                    "sesije (Završi razgovor, druga misija, zatvaranje aplikacije)."))
            return
        state = tr("pregledano") if mem.get("reviewed") else tr("<span style='color:#ffcf7a'>"
                                                               "nepregledano — prijedlog agenta</span>")
        self.head.setText(tr("<b>Pamćenje misije</b> · {0}").format(state))
        for it in mem["items"]:
            self._item(it)

    def _item(self, it: dict):
        from PySide6.QtWidgets import QListWidgetItem
        from ..shared_lib import mission_agent as MA
        lab = tr(MA.MEMORY_KINDS.get(it.get("kind"), it.get("kind") or ""))
        src = f" — {it['source']}" if it.get("source") else ""
        li = QListWidgetItem(f"{lab}: {it['text']}{src}")
        li.setFlags(li.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        li.setCheckState(Qt.Checked)
        li.setData(Qt.UserRole, dict(it))
        li.setToolTip(tr("Štikliraj šta ostaje; dvoklik mijenja tekst."))
        self.list.addItem(li)
        return li

    def _add(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from ..shared_lib import mission_agent as MA
        if not self.mid:
            return
        kinds = list(MA.MEMORY_KINDS)
        labels = [tr(MA.MEMORY_KINDS[k]) for k in kinds]
        lab, ok = QInputDialog.getItem(self, tr("Pamćenje misije"), tr("Vrsta stavke:"), labels, 0, False)
        if not ok:
            return
        txt, ok = QInputDialog.getText(self, tr("Pamćenje misije"), tr("Stavka:"))
        if ok and txt.strip():
            self._item({"kind": kinds[labels.index(lab)], "text": txt.strip(), "source": tr("operater")})

    def _delete(self) -> None:
        for li in self.list.selectedItems():
            self.list.takeItem(self.list.row(li))

    def items(self) -> list:
        """The checked items, with the operator's edits."""
        from ..shared_lib import mission_agent as MA
        out = []
        for i in range(self.list.count()):
            li = self.list.item(i)
            if li.checkState() != Qt.Checked:
                continue
            d = dict(li.data(Qt.UserRole) or {})
            txt = li.text()
            lab = tr(MA.MEMORY_KINDS.get(d.get("kind"), d.get("kind") or "")) + ": "
            if txt.startswith(lab):
                txt = txt[len(lab):]
            if d.get("source") and txt.endswith(f" — {d['source']}"):
                txt = txt[: -len(f" — {d['source']}")]
            d["text"] = txt.strip()
            out.append(d)
        return out

    def _save(self) -> None:
        from ..shared_lib import mission_agent as MA
        if not self.mid:
            return
        try:
            MA.save_memory(self.mid, self.items(), reviewed=True)
        except Exception as e:                       # noqa: BLE001 — e.g. no operator
            QMessageBox.warning(self, tr("Pamćenje misije"), str(e))
            return
        self.show_for(self.mid)
        self.saved.emit()


class MissionsTab(QWidget):
    """Rule 42, layout A: missions as cards on the left; the chosen mission's
    details, „Gdje si stao“ and its memory upper right; the paper strip and the
    conversation lower right (the border between them is dragged)."""
    switched = Signal()                 # item 28a: the active mission changed

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QListWidget, QSplitter
        v = QVBoxLayout(self)
        from .. import config as _CFG
        top = [QLabel(tr("<b>Misije</b>")),
               button(tr("Provjeri arXiv sada"), self._arxiv_now),
               button(tr("Adversarijalni mod…"), self._adversary)]
        if _CFG.personal():                 # rule 38: missions 2 and 3 are Andrej's
            top.append(button(tr("Radni tekst (misije 2 i 3)…"), self._paper))
        top += [button(tr("Izvezi izvještaj misije"), self._export_report),
                button(tr("Osvježi"), self.refresh)]
        v.addWidget(flow_row(*top))

        split = QSplitter(Qt.Horizontal)
        # left: the missions as cards + „+ Nova misija“
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(button(tr("+ Nova misija"), self._new_mission, primary=True))
        self.list = QListWidget()
        self.list.setSpacing(3)
        self.list.setWordWrap(True)
        self.list.itemClicked.connect(self._clicked)
        lv.addWidget(self.list, 1)
        split.addWidget(left)

        # right: details (upper) / papers + conversation (lower), border dragged
        self.rsplit = QSplitter(Qt.Vertical)
        upper = QWidget()
        uv = QVBoxLayout(upper)
        uv.setContentsMargins(0, 0, 0, 0)
        self.head = QLabel("")
        self.head.setWordWrap(True)
        uv.addWidget(self.head)
        # goal and „while it waits“ in one menu: the upper part stays one row high
        from PySide6.QtWidgets import QMenu, QToolButton
        self.b_goal = QToolButton()
        self.b_goal.setPopupMode(QToolButton.InstantPopup)
        self.b_goal.setText(tr("Cilj i pozadina ▾"))
        self.m_goal = QMenu(self.b_goal)
        self.b_goal.setMenu(self.m_goal)
        self.m_goal.aboutToShow.connect(self._fill_goal_menu)
        self.b_activate = button(tr("Aktiviraj"), self._activate, kind="go")
        self.b_park = button(tr("Ostavi za kasnije…"), self._park)
        self.b_close = button(tr("Zatvori misiju…"), self._close_mission, kind="no")
        uv.addWidget(flow_row(self.b_activate, self.b_park, self.b_close, self.b_goal))
        dsplit = QSplitter(Qt.Horizontal)               # rule 46: side by side
        self.view = MarkdownView()                      # details + „Gdje si stao“ (operator's)
        dsplit.addWidget(self.view)
        self.memory = MemoryPanel()                     # the memory (agent's, reviewed)
        self.memory.saved.connect(self._memory_saved)
        dsplit.addWidget(self.memory)
        dsplit.setStretchFactor(0, 3)
        dsplit.setStretchFactor(1, 2)
        dsplit.setChildrenCollapsible(False)
        uv.addWidget(dsplit, 1)
        self.rsplit.addWidget(upper)
        from .mission_talk import MissionTalk
        self.talk = MissionTalk()
        self.talk.proposed.connect(self.refresh)
        self.talk.memory_ready.connect(self._memory_ready)
        self.rsplit.addWidget(self.talk)
        self.rsplit.setStretchFactor(0, 2)
        self.rsplit.setStretchFactor(1, 3)
        self.rsplit.setChildrenCollapsible(False)
        split.addWidget(self.rsplit)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 4)
        split.setChildrenCollapsible(False)
        left.setMinimumWidth(200)
        split.setSizes([240, 900])
        self.rsplit.setSizes([380, 520])
        v.addWidget(split, 1)
        self.mid = None
        self._card_md = ""
        self._last_md = ""
        self.refresh()

    # ---- the cards (left) ---------------------------------------------- #
    def _card_html(self, m: dict, act: str, counts: dict) -> str:
        import html as _h
        st = str(m.get("state") or "")
        st = st if len(st) <= 70 else st[:69] + "…"
        mark = ("▶ " if m["id"] == act and not int(m.get("parked") or 0) else
                "⏸ " if int(m.get("parked") or 0) else
                "✕ " if st.startswith("zatvorena") else "")
        best = tr("front B = {0}").format(f"{m['best_B']:.9f}") if m.get("best_B") is not None \
            else tr("bez fronta")
        n_p, n_w = counts.get(m["id"], (0, 0))
        wait = (f" · <span style='color:#ffcf7a'>{tr('čeka {0}').format(n_w)}</span>" if n_w else "")
        return (f"<b>{mark}{_h.escape(m['title'])}</b><br>"
                f"<span style='color:#9aa4b5'>{_h.escape(tr(st))}</span><br>"
                f"<span style='color:#9aa4b5'>{best} · {tr('radova {0}').format(n_p)}</span>{wait}")

    def refresh(self):
        from PySide6.QtWidgets import QListWidgetItem
        from ..shared_lib import mission_agent as MA
        missions = MIS.all_missions()
        act = MIS.active()
        counts = {}
        for m in missions:
            try:
                n_p = len(MA.papers(m["id"]))
            except Exception:                        # noqa: BLE001
                n_p = 0
            counts[m["id"]] = (n_p, len(MIS._related_open_items(m["id"])))
        if self.mid is None or MIS.get(self.mid) is None:
            self.mid = act
        self.list.blockSignals(True)
        self.list.clear()
        for m in missions:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, m["id"])
            lb = QLabel(self._card_html(m, act, counts))
            lb.setWordWrap(True)
            lb.setTextFormat(Qt.RichText)
            lb.setContentsMargins(6, 4, 6, 4)
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.list.addItem(it)
            self.list.setItemWidget(it, lb)
            self._fit_card(it, lb)
            if m["id"] == self.mid:
                it.setSelected(True)
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if not missions:
            self.view.set_markdown(tr("_Nema misija. „+ Nova misija“ gore lijevo._"))
        self._show()
        self._last_md = self._all_md(missions, act)

    def resizeEvent(self, e):                     # noqa: N802 (Qt) — cards re-wrap
        super().resizeEvent(e)
        for i in range(self.list.count()):
            it = self.list.item(i)
            w = self.list.itemWidget(it)
            if w is not None:
                self._fit_card(it, w)

    def _fit_card(self, it, lb) -> None:
        from PySide6.QtCore import QSize
        wd = max(160, self.list.viewport().width() - 10)
        lb.setFixedWidth(wd)
        it.setSizeHint(QSize(wd, lb.heightForWidth(wd) + 4))

    def _clicked(self, it) -> None:
        """Rule 43: a click on a mission opens its workspace and starts the agent."""
        self.open_mission(it.data(Qt.UserRole))

    def open_mission(self, mid: str) -> bool:
        """Select the mission and start its agent (a click, or a `mission:` link, rule 47)."""
        if MIS.get(mid) is None:
            return False
        prev = self.mid
        if prev and prev != mid and self.talk.mid == prev:
            self.talk.end_session(prev)          # rule 45: switching proposes the memory
        self.mid = mid
        self.refresh()
        self.talk.open_for(mid, autostart=True)
        return True

    # ---- the chosen mission (right) ------------------------------------ #
    def _show(self) -> None:
        mid = self.mid
        m = MIS.get(mid) if mid else None
        for b in (self.b_activate, self.b_park, self.b_close, self.b_goal):
            b.setEnabled(m is not None)
        if m is None:
            self.head.setText("")
            self.memory.show_for(None)
            return
        act = MIS.active()
        parked = int(m.get("parked") or 0)
        mark = (tr(" · ▶ aktivna") if mid == act and not parked else
                tr(" · ⏸ za kasnije") if parked else "")
        self.head.setText(f"<span style='font-size:15pt'><b>{m['title']}</b></span>{mark}")
        self.b_activate.setEnabled(not (mid == act and not parked))
        best = "—" if m["best_B"] is None else f"{m['best_B']:.12f}"
        md = [tr("**Pitanje.** {0}").format(m["question"]), "",
              tr("**Stanje.** {0}").format(m["state"]), "",
              tr("**Cilj.** {0}").format(tr(MIS.GOALS.get(int(m.get("goal") or 1), ""))), "",
              tr("**Front (najniže B).** {0}").format(best), "", tr("**Zadnji koraci.**")]
        steps = m["steps"][-6:]
        if not steps:
            md.append(tr("- _(još nema koraka)_"))
        for s in steps:
            md.append(f"- {s['action']} → **{s['outcome']}**")
        if len(m["steps"]) > 6:
            md.append(tr("_… i još {0} ranijih (Izvezi izvještaj misije)_").format(len(m["steps"]) - 6))
        try:
            wmd = where_md(MIS.where_you_stopped(mid))
        except Exception as e:                       # noqa: BLE001
            wmd = f"_{e}_"
        if self._card_md and self._card_md.startswith(tr("### Gdje si stao: {0}").format(m["title"])):
            wmd = self._card_md                      # right after a switch: with what was released
        self.view.set_markdown("\n".join(md) + "\n\n---\n\n" + wmd)
        self.memory.show_for(mid)

    def _memory_ready(self, mid: str) -> None:
        if mid == self.mid:
            self.memory.show_for(mid)

    def _memory_saved(self) -> None:
        self.talk.state.setText(tr("Pamćenje sačuvano — agent ga čita na početku sljedeće sesije."))

    # ---- mission buttons ------------------------------------------------ #
    def _new_mission(self):
        from PySide6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(self, tr("Nova misija"), tr("Naslov misije:"))
        if not ok or not title.strip():
            return
        q, ok = QInputDialog.getMultiLineText(self, tr("Nova misija"),
                                              tr("Pitanje misije (šta tačno želiš da saznaš):"))
        if not ok or not q.strip():
            return
        try:
            mid = MIS.new_mission(title, q)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, tr("Misije"), str(e))
            return
        self.mid = mid
        self.refresh()

    def _close_mission(self):
        mid = self.mid
        if not mid:
            return
        m = MIS.get(mid)
        if QMessageBox.question(self, tr("Zatvori misiju"),
                                tr("Zatvoriti misiju „{0}“? Agent misije umire, a sve iz njega "
                                   "ide u SHARED_LIB.").format(m["title"] if m else mid)) \
                != QMessageBox.Yes:
            return
        from ..shared_lib import mission_agent as MA
        if self.talk.mid == mid:
            self.talk.end_session(mid)
        try:
            MA.close_mission(mid)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, tr("Misije"), str(e))
        self.refresh()

    def _ask_note(self) -> "str | None":
        from PySide6.QtWidgets import QInputDialog
        cur = MIS.get(MIS.active() or "")
        txt, ok = QInputDialog.getMultiLineText(
            self, tr("Ostavi za kasnije"),
            tr("Gdje si stao u misiji „{0}“? (jedna rečenica za sebe; front, koraci i otvorene stavke se pamte sami)").format(cur["title"] if cur else "—"))
        return txt if ok else None

    def _activate(self):
        mid = self.mid
        if not mid:
            return
        note = self._ask_note() if (MIS.active() and MIS.active() != mid) else ""
        if note is None:
            return
        try:
            card = MIS.set_active(mid, note)
        except Exception as e:                       # noqa: BLE001 — shown, nothing changed
            QMessageBox.warning(self, tr("Misije"), str(e))
            return
        self._card_md = where_md(card)
        self.refresh()
        self.switched.emit()

    def _park(self):
        mid = self.mid
        if not mid:
            return
        from PySide6.QtWidgets import QInputDialog
        m = MIS.get(mid)
        txt, ok = QInputDialog.getMultiLineText(
            self, tr("Ostavi za kasnije"),
            tr("Gdje si stao u misiji „{0}“? (jedna rečenica za sebe; front, koraci i otvorene stavke se pamte sami)").format(m["title"] if m else "—"))
        if not ok:
            return
        try:
            MIS.park(mid, txt)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, tr("Misije"), str(e))
            return
        self._card_md = ""
        self.refresh()
        self.switched.emit()

    def _fill_goal_menu(self) -> None:
        m = MIS.get(self.mid) if self.mid else None
        self.m_goal.clear()
        if m is None:
            return
        self.m_goal.addSection(tr("Cilj misije"))
        cur = int(m.get("goal") or 1)
        for g, txt in MIS.GOALS.items():
            a = self.m_goal.addAction(f"{g} · {tr(txt)}", lambda g=g: self._apply_goal(g))
            a.setCheckable(True)
            a.setChecked(g == cur)
        self.m_goal.addSection(tr("Dok čeka"))
        bg = MIS.background(self.mid)
        for k, txt in MIS.BACKGROUND.items():
            a = self.m_goal.addAction(tr(txt), lambda k=k: self._apply_bg(k))
            a.setCheckable(True)
            a.setChecked(k == bg)

    def _apply_bg(self, mode: str):
        if not self.mid:
            return
        try:
            MIS.set_background(self.mid, mode)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, tr("Misije"), str(e))
        self.refresh()

    def _apply_goal(self, g: int):
        mid = self.mid
        if not mid:
            return
        try:
            MIS.set_goal(mid, int(g), "izbor operatera u meniju misije")
        except Exception as e:                       # noqa: BLE001 — shown, nothing changed
            QMessageBox.warning(self, tr("Cilj misije"), str(e))
            return
        self.refresh()

    def _paper(self):
        """Item 33: assemble the working paper in the background, then show it."""
        import threading
        from PySide6.QtCore import QObject, Signal as _Sig

        class _B(QObject):
            done = _Sig(object, str)
        if getattr(self, "_paper_bridge", None) is None:
            self._paper_bridge = _B()
            self._paper_bridge.done.connect(self._paper_done)
        br = self._paper_bridge

        def work():
            from ..shared_lib import paper as PAP
            try:
                br.done.emit(PAP.build(), "")
            except Exception as e:                       # noqa: BLE001 — PaperRefused included
                br.done.emit(None, str(e))
        threading.Thread(target=work, name="paper", daemon=True).start()
        QMessageBox.information(self, tr("Radni tekst"),
                                tr("Sastavljam u pozadini (lab run-ovi koji fale, kapija, izvori, skeptik). Tekst se otvori kad bude gotov."))

    def _paper_done(self, res, err: str):
        if err:
            QMessageBox.warning(self, tr("Radni tekst"), tr("Nije zapisano: {0}").format(err))
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout as _V, QLabel as _L
        d = QDialog(self)
        d.setWindowTitle(tr("Radni tekst (misije 2 i 3) — NAŠE-NERECENZIRANO"))
        lay = _V(d)
        lay.addWidget(_L(tr("Zapečaćeno: {0} · čeka te u „Čeka tvoju odluku“").format(res["path"])))
        mv = MarkdownView()
        mv.set_markdown(res["markdown"])
        lay.addWidget(mv, 1)
        from .. import screen as SCR
        SCR.fit(d, 1100, 900)
        d.exec()
        self.refresh()

    def _adversary(self):
        """Item 31: attack a method's claim with numbers (background; result in the queue)."""
        from PySide6.QtWidgets import QInputDialog
        from ..methods import adversary as ADV
        from ..methods import registry as R
        names = []
        for m in R.KNOWN:
            try:
                ADV.family(m.name)
                names.append(m.name)
            except (KeyError, ValueError):
                continue
        if not names:
            QMessageBox.information(self, tr("Adversarijalni mod"), tr("Nema metode sa funkcijom eksponenta."))
            return
        name, ok = QInputDialog.getItem(self, tr("Adversarijalni mod"),
                                        tr("Koju tvrdnju da napadnem brojevima? (~5–15 s u pozadini; rezultat ide u „Čeka tvoju odluku“, na Grafove i u Lab)"),
                                        names, 0, False)
        if ok and name:
            ADV.attack_in_background(name)
            QMessageBox.information(self, tr("Adversarijalni mod"),
                                    tr("Pokrenuto za „{0}“. Nalaz stiže u „Čeka tvoju odluku“.").format(name))

    def _arxiv_now(self):
        from ..shared_lib import runtime as RT
        r = RT.arxiv_round(force=True)
        if r.get("found", 0) == 0 and not r.get("new"):
            QMessageBox.information(self, tr("arXiv"), tr("Nema novih QRH radova (ili nema mreže)."))
        else:
            QMessageBox.information(
                self, tr("arXiv"),
                tr("Pronađeno {0}, novih {1}. Novi radovi čekaju u „Čeka tvoju odluku“: odobri izvlačenje metode.").format(r.get('found', 0), len(r.get('new', []))))

    def _export_report(self):
        from ..shared_lib import runtime as RT
        if not OP.current():
            QMessageBox.warning(self, tr("Operater"), tr("Prvo se prijavi kao operater."))
            return
        p = RT.write_final_report(f"misije-{MIS.FIRST_ID}", self._markdown())
        QMessageBox.information(self, tr("Izvještaj"),
                                tr("Zapisan i zapečaćen:\n{0}\n\nČuvari ga od sada čuvaju.").format(p))

    def _markdown(self) -> str:
        self.refresh()
        return self._last_md

    def _all_md(self, missions: list, act) -> str:
        """Every mission as Markdown — the body of „Izvezi izvještaj misije“."""
        md = [tr("# Misije"), ""]
        if not missions:
            md.append(tr("_Nema misija._"))
        for m in missions:
            best = "—" if m["best_B"] is None else f"{m['best_B']:.12f}"
            mark = (tr(" · ▶ aktivna") if m["id"] == act and not int(m.get("parked") or 0) else
                    tr(" · ⏸ za kasnije") if int(m.get("parked") or 0) else "")
            md += [f"## {m['title']}{mark}", "", tr("**Pitanje.** {0}").format(m['question']), "",
                   tr("**Front (najniže B).** {0}").format(best), "",
                   tr("**Cilj.** {0}").format(tr(MIS.GOALS.get(int(m.get("goal") or 1), ""))), "",
                   tr("**Stanje.** {0}").format(m['state']), "", tr("**Koraci.**")]
            full = MIS.get(m["id"])
            steps = full["steps"] if full else []
            if not steps:
                md.append(tr("- _(još nema koraka)_"))
            for s in steps:
                md.append(f"- {s['action']} → **{s['outcome']}**")
            md.append("")
        return "\n".join(md)


def where_md(card: dict) -> str:
    """The "Gdje si stao" card as Markdown (item 28a)."""
    import time as _t
    out = [tr("### Gdje si stao: {0}").format(card["title"]), ""]
    if card.get("parked_at"):
        out.append(tr("Ostavljeno: {0}").format(_t.strftime("%Y-%m-%d %H:%M", _t.localtime(card["parked_at"]))))
    out.append(tr("**Tvoja bilješka:** {0}").format(card["note"] or tr("_(bez bilješke)_")))
    snap = card.get("snapshot") or {}
    if snap:
        best = "—" if snap.get("best_B") is None else f"{snap['best_B']:.9f}"
        out.append(tr("**Tada:** front B = {0}, cilj {1}, koraka {2}.").format(best, snap.get("goal"), snap.get("n_steps")))
        if snap.get("last_step"):
            out.append(tr("**Zadnji korak:** {0} → {1}").format(snap["last_step"]["action"], snap["last_step"]["outcome"]))
    out.append("")
    since, rel = card.get("steps_since") or [], card.get("released") or []
    oi = (card.get("now") or {}).get("open_items") or []
    if not since and not rel:
        out.append(tr("**Dok te nije bilo:** ništa novo") + (tr(" (misija je bila zamrznuta).") if card.get("background") == MIS.FREEZE else "."))
    else:
        out.append(tr("**Dok te nije bilo:** {0} novih koraka, {1} radova sa arXiv-a (sada u „Čeka tvoju odluku“).").format(len(since), len(rel)))
        for st in since[-5:]:
            out.append(f"- {st['action']} → **{st['outcome']}**")
    if oi:
        out.append(tr("**Otvoreno u redu za ovu misiju:** {0}").format(len(oi)))
    return "\n".join(out)


class QueueTab(QWidget):
    """The "Čeka tvoju odluku" queue + model chooser + import-method."""
    decided = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)

        # model chooser (main + skeptic)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Glavni:")))
        self.cb_main = QComboBox()
        self.cb_skeptic = QComboBox()
        row.addWidget(self.cb_main)
        row.addWidget(QLabel(tr("Skeptik:")))
        row.addWidget(self.cb_skeptic)
        row.addWidget(button(tr("Primijeni"), self._apply_models))
        row.addStretch(1)
        row.addWidget(button(tr("Deklariši GGUF…"), self._declare_gguf))
        row.addWidget(button(tr("Uvezi metodu…"), self._import_method, primary=True))
        v.addLayout(row)
        self.lb_models = small("")
        v.addWidget(self.lb_models)
        v.addWidget(hline())

        # 33d (rule 32): a tree by kind → mission / topic → item, with checkboxes
        v.addWidget(QLabel(tr("<b>Čeka tvoju odluku</b> — označi jednu, više ili cijelu grupu; "
                              "Doktorove mjere i nepovratne odluke idu jedna po jedna")))
        from PySide6.QtWidgets import QSplitter, QTreeWidget
        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self._tree_changed)
        self.tree.currentItemChanged.connect(self._show_item)
        split.addWidget(self.tree)
        self.view = MarkdownView()
        split.addWidget(self.view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        v.addWidget(split, 1)
        self.lb_sel = small("")
        v.addWidget(flow_row(button(tr("Odobri označene"), lambda: self._decide(True), kind="go"),
                             button(tr("Ne odobri označene"), lambda: self._decide(False), kind="no"),
                             button(tr("Označi sve"), lambda: self._check_all(True)),
                             button(tr("Odznači sve"), lambda: self._check_all(False)),
                             self.lb_sel))

        self._load_models()
        self.refresh()

    # -- models -------------------------------------------------------- #
    def _load_models(self):
        ids = [c["id"] for c in SEL.candidates()]
        self.cb_main.clear(); self.cb_skeptic.clear()
        self.cb_main.addItems(ids)
        self.cb_skeptic.addItems([tr("(nedostupan)")] + ids)
        main, sk = SEL.get_main(), SEL.get_skeptic()
        if main in ids:
            self.cb_main.setCurrentText(main)
        self.cb_skeptic.setCurrentText(sk if sk in ids else tr("(nedostupan)"))
        self._show_models()

    def _show_models(self):
        main, sk = SEL.get_main(), SEL.get_skeptic()
        avail = tr("dostupan") if SEL.skeptic_available() else tr("nedostupan (samo determinističke provjere)")
        self.lb_models.setText(tr("glavni: {0} · skeptik: {1} ({2})").format(main or '—', sk or '—', avail))

    def _apply_models(self):
        try:
            SEL.set_main(self.cb_main.currentText())
            sk = self.cb_skeptic.currentText()
            if sk and sk != tr("(nedostupan)"):
                SEL.set_skeptic(sk)
        except ValueError as e:
            QMessageBox.warning(self, tr("Izbor modela"), str(e))
        self._show_models()

    # -- declare a local model (master §8: the operator confirms the hash) -- #
    def _declare_gguf(self):
        from .. import config
        from ..llm import gguf as G
        path, _ = QFileDialog.getOpenFileName(self, tr("Deklariši lokalni model"),
                                              str(config.DIR_MODELS), "GGUF (*.gguf)")
        if not path:
            return
        pub = G.PUBLISHED.get(Path(path).name)
        self.lb_models.setText(tr("računam sha256…"))
        sha = G.sha256_of(Path(path))
        note = (tr("odgovara objavljenom hash-u (") + pub["source"] + ")"
                if pub and pub["sha256"] == sha else
                tr("NEMA objavljenog hash-a za ovaj fajl — deklarišeš ga na svoju odgovornost"))
        pid = G.propose_declaration(path, sha, note)
        QMessageBox.information(
            self, tr("Deklaracija modela"),
            f"sha256: {sha}\n{note}\n\n" +
            (tr("Prijedlog je u redu — potvrdi ga dolje (Odobri).") if pid else
             tr("Prijedlog za ovaj fajl već čeka u redu.")))
        self.refresh()

    # -- import a method pack through the door -------------------------- #
    def _import_method(self):
        if not OP.current():
            QMessageBox.warning(self, tr("Operater"), tr("Prvo se prijavi kao operater."))
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Uvezi paket metode"),
                                              "", "Paketi (*.json)")
        if not path:
            return
        try:
            out = DOOR.import_pack(path, proposer=f"operator:{OP.current()}",
                                   mission_id=MIS.FIRST_ID)
        except PK.PackError as e:
            QMessageBox.warning(self, tr("Paket metode"), tr("Neispravan paket: {0}").format(e))
            return
        if out["reproduced"]:
            QMessageBox.information(
                self, tr("Uvoz metode"),
                tr("Reprodukovano (B*={0:.12f}). Čeka tvoju potvrdu u redu.").format(out['result']['computed_B']))
        else:
            r = out["result"]
            QMessageBox.warning(
                self, tr("Uvoz metode — odbijeno na vratima"),
                tr("Paket NIJE reprodukovao broj iz rada: naš pipeline daje {0:.12f}, paket tvrdi {1:.12f} (razlika {2:.1e}). Nije ušao u red.").format(r['computed_B'], r['claimed_B'], r['error']))
        self.refresh()

    # -- the queue (33d) ------------------------------------------------ #
    def refresh(self):
        from PySide6.QtWidgets import QTreeWidgetItem
        from ..shared_lib import queue_groups as QG
        self._filling = True
        self.tree.clear()
        groups = QG.tree()
        if not groups:
            QTreeWidgetItem(self.tree, [tr("Red je prazan.")])
        for k in groups:
            n = sum(len(g["items"]) for g in k["groups"])
            top = QTreeWidgetItem(self.tree, [f"{tr(k['label'])} ({n})" +
                                              ("" if k["bulk"] else " · " + tr("jedna po jedna"))])
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable)
            top.setCheckState(0, Qt.Unchecked)
            for g in k["groups"]:
                parent = top
                if g["name"]:
                    parent = QTreeWidgetItem(top, [f"{g['name']} ({len(g['items'])})"])
                    parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable)
                    parent.setCheckState(0, Qt.Unchecked)
                for it in g["items"]:
                    leaf = QTreeWidgetItem(parent, [QG.title_of(it)])
                    leaf.setFlags(leaf.flags() | Qt.ItemIsUserCheckable)
                    leaf.setCheckState(0, Qt.Unchecked)
                    leaf.setData(0, Qt.UserRole, it["id"])
                    leaf.setData(0, Qt.UserRole + 1, k["bulk"])
            top.setExpanded(True)
        self.tree.expandAll()
        self._filling = False
        self.view.set_markdown(tr("_Klikni stavku da vidiš sve o njoj (i cijeli sažetak)._"))
        self._count()
        self._show_models()

    def _leaves(self, node=None):
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        out = []
        itr = QTreeWidgetItemIterator(self.tree)
        while itr.value():
            n = itr.value()
            if n.data(0, Qt.UserRole):
                out.append(n)
            itr += 1
        return out

    def _tree_changed(self, node, col):
        if getattr(self, "_filling", False):
            return
        self._filling = True
        st = node.checkState(0)

        def down(n):
            for i in range(n.childCount()):
                n.child(i).setCheckState(0, st)
                down(n.child(i))
        down(node)
        self._filling = False
        self._count()

    def _check_all(self, on: bool):
        self._filling = True
        for n in self._leaves():                    # one-by-one items are never ticked in bulk
            if on and not n.data(0, Qt.UserRole + 1):
                continue
            n.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._filling = False
        self._count()

    def _checked(self) -> list:
        return [n.data(0, Qt.UserRole) for n in self._leaves() if n.checkState(0) == Qt.Checked]

    def _count(self):
        self.lb_sel.setText(tr("označeno: {0}").format(len(self._checked())))

    def select(self, pid: str) -> bool:
        for n in self._leaves():
            if n.data(0, Qt.UserRole) == pid:
                n.setCheckState(0, Qt.Checked)
                self.tree.setCurrentItem(n)
                return True
        return False

    def _show_item(self, cur, _prev=None):
        from ..shared_lib import queue_groups as QG
        pid = cur.data(0, Qt.UserRole) if cur is not None else None
        if not pid:
            return
        it = store().get(pid)
        if it:
            self.view.set_markdown(QG.detail_md(it))

    def _decide(self, approve: bool, ask: bool = True):
        from ..shared_lib import queue_groups as QG
        if not OP.current():
            QMessageBox.warning(self, tr("Operater"), tr("Prvo se prijavi kao operater."))
            return
        ids = self._checked()
        if not ids:
            cur = self.tree.currentItem()
            pid = cur.data(0, Qt.UserRole) if cur is not None else None
            ids = [pid] if pid else []
        if not ids:
            return
        if ask and QMessageBox.question(
                self, tr("Odluka"),
                (tr("Odobravaš {0} stavki?") if approve else tr("Ne odobravaš {0} stavki?")).format(len(ids))) \
                != QMessageBox.Yes:
            return
        try:
            out = QG.decide_many(ids, approve)
        except ValueError as e:
            QMessageBox.warning(self, tr("Odluka"), str(e))
            return
        if out["failed"]:
            QMessageBox.warning(self, tr("Odluka"), "\n".join(f"{k}: {v}" for k, v in out["failed"].items()))
        self.decided.emit()
        self.refresh()
