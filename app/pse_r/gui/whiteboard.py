"""
The whiteboard — draw mathematics by hand, keep it forever, transcribe it when
the network is there.

The design decision that matters: **the strokes are always saved as SVG and
embedded into a markdown note, whether or not transcription happens.** Vector
strokes never fail, never need a model, never need a network, and never
hallucinate an exponent. Transcription is an optional layer on top: the image
goes to a vision model, the LaTeX comes back as a *proposal* shown next to your
drawing, and you accept or fix it.

That ordering is deliberate. A whiteboard that only produces LaTeX loses your
work whenever the transcription is wrong or the WiFi is down — which, on this
trip, is the normal case rather than the exception.
"""
from __future__ import annotations

from ..i18n import tr

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QComboBox, QGraphicsPathItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QLabel, QPlainTextEdit,
                               QSpinBox, QSplitter, QVBoxLayout, QWidget)

from .. import config
from ..core import journal as J
from ..pse import measure as PM
from ..pse import path as PATH
from ..llm import backend as B
from ..llm.budget import BudgetExceeded
from ..llm.router import NoProvider
from .widgets import MarkdownView, button, small


class Board(QGraphicsView):
    """QGraphicsScene strokes — vector, cheap, undoable. Not a bitmap canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_ = QGraphicsScene(0, 0, 2400, 1400)
        self.setScene(self.scene_)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#101010"))
        self.setDragMode(QGraphicsView.NoDrag)
        self.pen = QPen(QColor("#f0f0f0"), 2.4)
        self.pen.setCapStyle(Qt.RoundCap)
        self.pen.setJoinStyle(Qt.RoundJoin)
        self._path = None
        self._item = None
        self.strokes: list = []
        self.erasing = False

    def set_width(self, w: int):
        self.pen.setWidthF(float(w))

    def set_color(self, name: str):
        self.pen.setColor(QColor(name))

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        p = self.mapToScene(e.position().toPoint())
        if self.erasing:
            for it in self.items(e.position().toPoint()):
                if isinstance(it, QGraphicsPathItem):
                    self.scene_.removeItem(it)
                    if it in self.strokes:
                        self.strokes.remove(it)
                    break
            return
        self._path = QPainterPath(p)
        self._item = self.scene_.addPath(self._path, QPen(self.pen))
        self.strokes.append(self._item)

    def mouseMoveEvent(self, e):
        if self._path is None:
            return super().mouseMoveEvent(e)
        self._path.lineTo(self.mapToScene(e.position().toPoint()))
        self._item.setPath(self._path)

    def mouseReleaseEvent(self, e):
        self._path = None
        self._item = None

    def undo(self):
        if self.strokes:
            it = self.strokes.pop()
            self.scene_.removeItem(it)

    def clear(self):
        for it in list(self.strokes):
            self.scene_.removeItem(it)
        self.strokes.clear()

    def content_rect(self) -> QRectF:
        r = self.scene_.itemsBoundingRect()
        return r.adjusted(-24, -24, 24, 24) if not r.isEmpty() \
            else QRectF(0, 0, 400, 200)

    def to_png(self, scale: float = 1.0) -> bytes:
        from PySide6.QtCore import QBuffer, QByteArray
        r = self.content_rect()
        img = QImage(int(r.width() * scale), int(r.height() * scale),
                     QImage.Format_RGB32)
        img.fill(QColor("#101010"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        self.scene_.render(p, target=QRectF(img.rect()), source=r)
        p.end()
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.WriteOnly)
        img.save(buf, "PNG")
        return bytes(ba)

    def to_svg(self, path: Path) -> Path:
        from PySide6.QtSvg import QSvgGenerator
        r = self.content_rect()
        gen = QSvgGenerator()
        gen.setFileName(str(path))
        gen.setSize(r.size().toSize())
        gen.setViewBox(QRectF(0, 0, r.width(), r.height()))
        gen.setTitle("PSE Riemann whiteboard")
        p = QPainter(gen)
        p.setRenderHint(QPainter.Antialiasing)
        self.scene_.render(p, target=QRectF(0, 0, r.width(), r.height()),
                           source=r)
        p.end()
        return path


class _Transcribe(QObject):
    done = Signal(str, str)

    def __init__(self, png: bytes):
        super().__init__()
        self.png = png

    def run(self):
        try:
            r = PATH.ask("whiteboard", [B.Msg(
                "user",
                "Prepiši matematiku sa ove table u LaTeX. Vrati SAMO LaTeX.",
                image_png=self.png)], entity=("operater", "human"))
            self.done.emit(r.text, "")
        except (NoProvider, BudgetExceeded, PATH.Refused) as e:
            self.done.emit("", str(e))
        except Exception as e:                          # noqa: BLE001
            self.done.emit("", f"{type(e).__name__}: {e}")


class WhiteboardTab(QWidget):
    card_written = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        bar = QHBoxLayout()
        self.board = Board()
        bar.addWidget(button(tr("↶ Undo"), self.board.undo))
        bar.addWidget(button(tr("Obriši sve"), self.board.clear))
        self.b_erase = button(tr("Guma"), self._toggle_erase)
        bar.addWidget(self.b_erase)
        w = QSpinBox()
        w.setRange(1, 12)
        w.setValue(2)
        w.valueChanged.connect(self.board.set_width)
        bar.addWidget(QLabel(tr("debljina")))
        bar.addWidget(w)
        col = QComboBox()
        col.addItems(["#f0f0f0", "#ffd54f", "#81c784", "#ef5350", "#4fc3f7"])
        col.currentTextChanged.connect(self.board.set_color)
        bar.addWidget(col)
        bar.addStretch(1)
        bar.addWidget(button(tr("Transkribuj (vision)"), self._transcribe))
        bar.addWidget(button(tr("💾 Snimi u bilješku"), self._save, primary=True))
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("board")
        split.setChildrenCollapsible(False)
        split.addWidget(self.board)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel(tr("<b>LaTeX</b> — prijedlog modela, ti ispravljaš")))
        self.latex = QPlainTextEdit()
        from .widgets import _BASE_PT
        self.latex.setStyleSheet(
            f"font-family:monospace;font-size:{_BASE_PT[0]*0.95:.1f}pt;")
        self.latex.setPlaceholderText(
            tr("Ovdje stiže transkripcija. Možeš i sam pisati — snima se i bez "
            "modela.\nNepročitani simboli dolaze kao \\text{???} umjesto "
            "pogađanja."))
        self.latex.textChanged.connect(self._preview)
        rv.addWidget(self.latex, 1)
        rv.addWidget(QLabel(tr("<b>Pregled</b>")))
        self.preview = MarkdownView()
        rv.addWidget(self.preview, 1)
        self.state = small("")
        rv.addWidget(self.state)
        split.addWidget(right)
        split.setSizes([640, 380])
        root.addWidget(split, 1)
        self._thr = None

    def _toggle_erase(self):
        self.board.erasing = not self.board.erasing
        self.b_erase.setText(tr("Guma ✓") if self.board.erasing else tr("Guma"))

    def _preview(self):
        t = self.latex.toPlainText().strip()
        self.preview.set_markdown(f"$$\n{t}\n$$" if t else "")

    def _transcribe(self):
        if not self.board.strokes:
            self.state.setText(tr("tabla je prazna"))
            return
        if self._thr is not None:
            return
        self.state.setText(tr("šaljem sliku vision modelu…"))
        png = self.board.to_png(1.0)
        self._thr = QThread()
        self._w = _Transcribe(png)
        self._w.moveToThread(self._thr)
        self._thr.started.connect(self._w.run)
        self._w.done.connect(self._got)
        self._thr.start()

    def _got(self, text: str, err: str):
        if self._thr:
            self._thr.quit()
            self._thr.wait(3000)
            self._thr = None
        if err:
            self.state.setText("⛔ " + err[:200] +
                               tr("  — potezi su i dalje sigurni, snimi ih."))
            return
        clean = (text or "").strip()
        for fence in ("```latex", "```LaTeX", "```"):
            clean = clean.replace(fence, "")
        self.latex.setPlainText(clean.strip())
        self.state.setText(tr("✅ prijedlog stigao — provjeri prije snimanja "
                           "(\\text{???} znači da model nije bio siguran)"))

    def _save(self):
        if not self.board.strokes and not self.latex.toPlainText().strip():
            self.state.setText(tr("nema šta da se snimi"))
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        config.DIR_MEDIA.mkdir(parents=True, exist_ok=True)
        svg = config.DIR_MEDIA / f"tabla-{stamp}.svg"
        png = config.DIR_MEDIA / f"tabla-{stamp}.png"
        try:
            self.board.to_svg(svg)
        except Exception as e:                          # noqa: BLE001
            self.state.setText(tr("SVG nije uspio ({0}) — snimam PNG").format(e))
            svg = None
        png.write_bytes(self.board.to_png(1.0))

        tex = self.latex.toPlainText().strip()
        note = config.DIR_NOTES / f"tabla-{stamp}.md"
        body = [f"---", "id: tabla-{0}".format(stamp),
                "title: Tabla {0}".format(stamp), "type: note", "status: FOLKLORE",
                "author: user", "tags:", tr("  - tabla"), "---", "",
                tr("# Tabla {0}").format(stamp), "",
                "![tabla](media/{0})".format(png.name), ""]
        if svg:
            body += [tr("_vektor: `media/{0}`_").format(svg.name), ""]
        if tex:
            body += [tr("## Prepisano"), "", "$$", tex, "$$", "",
                     tr("> Transkripcija je prijedlog modela koji si ti potvrdio. "
                     "Originalni potezi su iznad i oni su izvor istine."), ""]
        note.write_text("\n".join(body), encoding="utf-8")
        PATH.work("whiteboard", [PM.Action("snima tablu operatera", "o", checked=True)],
                  entity=("operater", "human"), note=note.name)
        J.log(J.GATE, "user", {"note": str(note), "svg": str(svg) if svg else "",
                               "transcribed": bool(tex)},
              subject=note.stem, verdict="whiteboard")
        self.state.setText(tr("✅ snimljeno: {0}").format(note.name))
        self.card_written.emit()
