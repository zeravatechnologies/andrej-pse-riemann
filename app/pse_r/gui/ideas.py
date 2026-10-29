"""
The "Ideje" tab (round 3, item 28): this week's INSPIRACIJE, each already attacked
by the skeptic, and the operator's four choices — zadrži · odbaci · pretvori u
otvoreno pitanje · odgodi. No pop-ups: the tab title carries a small badge.
"""
from __future__ import annotations

from ..i18n import tr

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from ..shared_lib import ideas as IDEAS
from ..shared_lib import missions as MIS
from .widgets import MarkdownView, button, flow_row, hline


def idea_md(r: dict) -> str:
    mt = (MIS.get(r["mission_id"] or "") or {}).get("title", r["mission_id"] or "—")
    out = [f"### {r['title']}", "",
           tr("**Oznaka:** INSPIRACIJA — ideja, ne tvrdnja; ne ulazi u vault kao činjenica."), "",
           r["idea"], "",
           tr("**Misija:** {0}").format(mt), "",
           tr("**Zašto:** {0}").format(r["why"]), "",
           tr("**Da postane provjerljiva metoda:** {0}").format(r["method_hint"]), "",
           tr("**Izvor:** `{0}` — {1}").format(r["source_ref"], r.get("source_title") or ""), "",
           tr("**Skeptik ({0}):**").format(r.get("skeptic_state") or "—")]
    objs = r.get("skeptic") or []
    if not objs:
        out.append(tr("- _(nema prigovora)_") if r.get("skeptic_state") == "napao"
                   else tr("- _skeptik nedostupan — samo determinističke provjere_"))
    for o in objs:
        out.append(f"- **[{o.get('ozbiljnost', '')}]** {o.get('prigovor', '')} — {o.get('razlog', '')}")
    return "\n".join(out)


class IdeasTab(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        self.sp_cap = QSpinBox()
        self.sp_cap.setRange(0, 20)
        v.addWidget(flow_row(QLabel(tr("<b>Ideje</b> — INSPIRACIJE, ne tvrdnje")),
                             QLabel(tr("Najviše sedmično:")), self.sp_cap,
                             button(tr("Primijeni"), self._apply_cap),
                             button(tr("Pročitaj izvore sada"), self._round_now),
                             button(tr("Sedmični pregled"), self._review),
                             button(tr("Osvježi"), self.refresh)))
        v.addWidget(hline())
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show)
        split.addWidget(self.list)
        self.view = MarkdownView()
        split.addWidget(self.view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setSizes([380, 760])
        self.list.setMinimumWidth(120)
        self.list.setWordWrap(True)
        v.addWidget(split, 1)
        v.addWidget(flow_row(*[button(label, lambda _=False, k=key: self._decide(k))
                               for key, label in (("keep", tr("Zadrži")), ("drop", tr("Odbaci")),
                                                  ("question", tr("Pretvori u otvoreno pitanje")),
                                                  ("snooze", tr("Odgodi (sedmica)")))]))
        self.refresh()

    def _apply_cap(self):
        try:
            IDEAS.set_cap(self.sp_cap.value())
        except Exception as e:                          # noqa: BLE001 — shown, nothing changed
            QMessageBox.warning(self, tr("Ideje"), str(e))
        self.refresh()

    def _round_now(self):
        r = IDEAS.ideas_round(force=True)
        self.view.set_markdown(tr("_Čitam izvore u pozadini (kroz Guardian egress); ideje stižu kad skeptik završi. Osvježi za koji minut._")
                               if not r.get("skipped") else "")

    def _review(self):
        self.view.set_markdown(IDEAS.weekly_review())

    def _show(self, cur, _prev=None):
        if cur is None:
            return
        r = IDEAS.get(cur.data(Qt.UserRole))
        if r:
            self.view.set_markdown(idea_md(r))

    def _decide(self, action: str):
        cur = self.list.currentItem()
        if cur is None:
            return
        try:
            IDEAS.decide(cur.data(Qt.UserRole), action)
        except Exception as e:                          # noqa: BLE001
            QMessageBox.warning(self, tr("Ideje"), str(e))
            return
        self.refresh()
        self.changed.emit()

    def refresh(self):
        self.sp_cap.setValue(IDEAS.cap())
        cur = self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        self.list.clear()
        rows = IDEAS.shown()
        for r in rows:
            it = QListWidgetItem(r["title"].replace("INSPIRACIJA: ", "💡 ", 1))
            it.setToolTip(r["title"])
            it.setData(Qt.UserRole, r["id"])
            self.list.addItem(it)
            if r["id"] == cur:
                self.list.setCurrentItem(it)
        if rows and self.list.currentItem() is None:
            self.list.setCurrentRow(0)
        if not rows:
            self.view.set_markdown(tr("_Nema ideja na odluci. Najviše {0} sedmično; kandidati čekaju slobodno mjesto._").format(IDEAS.cap())
                                   + "\n\n" + IDEAS.weekly_review())
