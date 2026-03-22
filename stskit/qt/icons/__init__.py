from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import (
    QIcon,
    QIconEngine,
    QPainter,
    QPalette,
    QPixmap, QAction,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget


class SvgIconEngine(QIconEngine):
    """
    From: https://gist.github.com/kaofelix/493845261a0bd7d8b3997d5f25895039
    """
    def __init__(self, svg_content):
        super().__init__()
        self.svg_content = svg_content
        self.svg_renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))

    def pixmap(self, size, mode, state) -> QPixmap:
        px = QPixmap(size)
        px.fill(Qt.GlobalColor.transparent)
        self.paint(QPainter(px), px.rect(), mode, state)
        return px

    def paint(self, painter, rect, mode, state):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        svg_painter = QPainter(pixmap)
        self.svg_renderer.render(svg_painter)

        # We need this hacky workaround to print in the correct color,
        # since Qt won't pass in an external color to the `currentColor`
        svg_painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        svg_painter.fillRect(pixmap.rect(), self.color_for(mode))
        svg_painter.end()

        painter.drawPixmap(rect, pixmap)

    def clone(self):
        return SvgIconEngine(self.svg_content)

    def actualSize(self, size, mode, state):
        return self.svg_renderer.defaultSize()

    def color_for(self, mode):
        if mode == QIcon.Mode.Normal:
            return QApplication.palette().color(QPalette.ColorRole.WindowText)
        elif mode == QIcon.Mode.Disabled:
            return QApplication.palette().color(
                QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
            )
        elif mode == QIcon.Mode.Active:
            return QApplication.palette().color(
                QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText
            )
        elif mode == QIcon.Mode.Selected:
            return QApplication.palette().color(QPalette.ColorRole.HighlightedText)
        else:
            return QApplication.palette().color(QPalette.ColorRole.WindowText)


@cache
def get_icon(action: str) -> QIcon:
    path = (Path(__file__).parent / action).with_suffix(".svg")
    if path.is_file():
        icon = QIcon(SvgIconEngine(path.read_text()))
    else:
        icon = QIcon.fromTheme(QIcon.ThemeIcon.DialogError)

    return icon


def set_action_icons(ui: object):
    for name, obj in vars(ui).items():
        if isinstance(obj, QAction):
            obj.setIcon(get_icon(name))
