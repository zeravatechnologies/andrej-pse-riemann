"""
The top bar (Svarog look): logo, title, and status pills you can read from
across the room — operator, balance θ, library, budget, Guardian, main AI,
skeptic, limiters, and how many things wait for your decision.

Every pill is computed from SHARED_LIB state on refresh; none is free text.
"""
from __future__ import annotations

from ..i18n import tr

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from .. import config
from .theme import pill_style


def _logo() -> QLabel:
    lb = QLabel()
    for p in (config.APP_ROOT / "packaging" / "pse-riemann.png",
              Path("/usr/share/icons/hicolor/256x256/apps/pse-riemann.png")):
        if p.exists():
            pm = QPixmap(str(p))
            if not pm.isNull():
                lb.setPixmap(pm.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                break
    lb.setStyleSheet("background:transparent;")
    return lb


class TopBar(QFrame):
    open_queue = Signal()
    toggle_online = Signal()
    toggle_lang = Signal()
    snapshot = Signal()
    open_results = Signal()

    def __init__(self, font_pt: float, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.font_pt = font_pt
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(8)
        h.addWidget(_logo())
        t = QLabel(tr("PSE Riemann"))
        t.setObjectName("title")
        h.addWidget(t)
        # screen fitting: pills and buttons wrap onto a second line on a narrow screen
        from .widgets import FlowLayout
        from PySide6.QtWidgets import QSizePolicy, QWidget
        box = QWidget()
        sp = box.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        sp.setHeightForWidth(True)
        box.setSizePolicy(sp)
        flow = FlowLayout(box, 8)
        h.addWidget(box, 1)
        h = flow                              # the rest goes into the wrapping row
        self.pills: dict[str, QLabel] = {}
        for key in ("mission", "op", "theta", "vault", "budget", "guard", "main", "skeptic",
                    "limits"):
            lb = QLabel("")
            lb.setTextFormat(Qt.PlainText)
            self.pills[key] = lb
            h.addWidget(lb)
        self.online_btn = QPushButton("")             # round 3, item 12 (also Ctrl+K)
        self.online_btn.setToolTip(tr("Prekidač za online AI (Ctrl+K): zatvara put prema "
                                   "cloud modelima, prekida pozive u toku, sklanja ključeve "
                                   "iz memorije. Uključuje ga samo operater."))
        self.online_btn.clicked.connect(self.toggle_online.emit)
        h.addWidget(self.online_btn)
        from ..i18n import lang
        self.lang_btn = QPushButton("SR | en" if lang() == "sr" else "sr | EN")
        self.lang_btn.setToolTip("Jezik interfejsa / interface language (SR/EN)")
        self.lang_btn.clicked.connect(self.toggle_lang.emit)
        h.addWidget(self.lang_btn)
        self.shot_btn = QPushButton("📷")                # round 3, item 29b (also F12)
        self.shot_btn.setToolTip(tr("Snimak ekrana (F12 = aktivni prozor, Shift+F12 = samo aktivni tab)"))
        self.shot_btn.clicked.connect(self.snapshot.emit)
        h.addWidget(self.shot_btn)
        self.results_btn = QPushButton("📂")
        self.results_btn.setToolTip(tr("Otvori folder sa rezultatima"))
        self.results_btn.clicked.connect(self.open_results.emit)
        h.addWidget(self.results_btn)
        self.queue_btn = QPushButton("")
        self.queue_btn.setProperty("kind", "primary")
        self.queue_btn.clicked.connect(self.open_queue.emit)
        h.addWidget(self.queue_btn)

    def _set(self, key: str, text: str, kind: str, tip: str = "") -> None:
        lb = self.pills[key]
        lb.setText(text)
        lb.setStyleSheet(pill_style(kind, self.font_pt))
        lb.setToolTip(tip)

    def refresh(self) -> None:
        from ..guardian.unit import guardian
        from ..llm.budget import budget
        from ..shared_lib import operator as OP
        from ..shared_lib.store import store
        from ..vault import store as VS

        try:                                            # item 28a: the active mission
            from ..shared_lib import missions as MIS
            am = MIS.get(MIS.active() or "")
            if am:
                short = am["title"] if len(am["title"]) <= 34 else am["title"][:33] + "…"
                parked = int(am.get("parked") or 0)
                self._set("mission", tr("misija: {0}").format(short) + (" ⏸" if parked else ""),
                          "warn" if parked else "info",
                          tr("aktivna misija — mijenjaš je u tabu Misije (Sljedeća misija ⟳)"))
            else:
                self._set("mission", tr("misija: —"), "plain")
        except Exception:                               # noqa: BLE001
            self._set("mission", tr("misija: ?"), "plain")
        op = OP.current()
        self._set("op", tr("operater: {0}").format(op or '—'), "plain" if op else "danger",
                  tr("registrovani operater ove sesije — glas SHARED_LIB-a govori samo njemu"))
        from ..shared_lib.pse_registry import pse
        sw = pse().swarm()
        kind = {"healthy": "ok", "sick": "warn", "measure": "warn",
                "frozen": "danger"}.get(sw["status"], "plain")
        txt = tr("roj {0} · θ {1:.1f}").format(sw["units"], sw["theta_mean"])
        if sw["frozen"]:
            txt += tr(" · ❄ {0}").format(len(sw["frozen"]))
        if sw["measures"]:
            txt += tr(" · Doktor {0}").format(sw["measures"])
        self._set("theta", txt, kind,
                  tr("PSE jedinice: {0} živih; obrasci {1}; zamrznute: {2}; "
                     "Doktorove mjere čekaju: {3}. Detalji u tabu Laboratorija.").format(
                         sw["units"], ", ".join(f"{a}={n}" for a, n in sw["attractors"].items()) or "—",
                         ", ".join(sw["frozen"]) or "—", sw["measures"]))
        st = VS.stats()
        self._set("vault", tr("kartice {0}/{1}").format(st.verified, st.total), "plain",
                  tr("provjerene / ukupno kartica"))
        self._set("budget", budget().status_line(), "plain", budget().tooltip())
        g = guardian().self_check()
        from ..guardian.ssh import unit as SSHU
        alarm = SSHU.pending_alarm()
        if alarm:
            self._set("guard", tr("⛔ OPASNOST"), "danger", alarm.get("text", ""))
        elif g["quarantined"]:
            self._set("guard", tr("Guardian: KARANTIN"), "danger", ", ".join(g["quarantined"]))
        elif g["problems"]:
            self._set("guard", tr("Guardian: provjeri"), "warn", "; ".join(map(str, g["problems"])))
        else:
            self._set("guard", tr("Guardian: ok"), "ok",
                      tr("{0} zahtjeva · {1} tier-1 · {2} tier-2").format(g['observations'], g['tier1'], g['tier2']))
        try:
            from ..llm import selection as SEL
            main = SEL.get_main()
            self._set("main", tr("glavni: {0}").format(main or tr('nema')), "info" if main else "warn",
                      tr("glavni AI radi sve uloge osim skeptika"))
            if SEL.skeptic_available():
                self._set("skeptic", tr("skeptik: {0}").format(SEL.get_skeptic()), "info",
                          tr("skeptik je uvijek drugi model; samo napada, nikad ne piše"))
            else:
                self._set("skeptic", tr("skeptik: nedostupan"), "warn",
                          tr("samo determinističke provjere (test reprodukcije, kapija, nivoi)"))
        except Exception:                                   # noqa: BLE001
            self._set("main", tr("glavni: ?"), "warn")
            self._set("skeptic", tr("skeptik: ?"), "warn")
        try:
            from ..llm import limits as L
            free = L.free_ram_gb()
            danger = L.Limits().must_unload()
            self._set("limits", tr("RAM {0:.1f} GB").format(free), "danger" if danger else "plain",
                      tr("limiteri: model se oslobađa kad slobodna memorija padne ispod praga"))
        except Exception:                                   # noqa: BLE001
            self._set("limits", tr("limiteri: ?"), "plain")
        from ..guardian import killswitch as KS
        off = KS.closed()
        self.online_btn.setText(tr("ONLINE AI: ISKLJUČEN") if off else tr("⏻ Online AI: uključen"))
        self.online_btn.setStyleSheet(
            ("QPushButton { background:#c62828; color:white; font-weight:700; "
             "border:1px solid #ff8a80; border-radius:11px; padding:3px 12px; }")
            if off else pill_style("ok", self.font_pt).replace("QLabel", "QPushButton"))
        n = len(store().open_items())
        self.queue_btn.setText(tr("Čeka tvoju odluku: {0}").format(n))
        self.queue_btn.setProperty("kind", "primary" if n else "")
        self.queue_btn.style().unpolish(self.queue_btn)
        self.queue_btn.style().polish(self.queue_btn)
