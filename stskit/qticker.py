"""
ereignisticker (GUI)

dieses modul implementiert ein fenster mit einem ereignisticker für das STSdispo hauptprogramm (main-modul).

das fenster ist in der TickerWindow-klasse implementiert.
die EreignisTabelle-klasse bereitet die simulationsdaten für das tabellenwidget auf.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Set, Union

from PyQt5 import Qt, QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QModelIndex

from stskit.stsobj import Ereignis
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

EREIGNISART_QCOLOR_SVG = {
    "einfahrt": QtGui.QColor("orchid"),
    "ausfahrt": QtGui.QColor("dodgerblue"),
    "rothalt": QtGui.QColor("tomato"),
    "fahrt": QtGui.QColor("limegreen"),
    "ankunft": QtGui.QColor("skyblue"),
    "durchfahrt": QtGui.QColor("skyblue"),
    "bereit": QtGui.QColor("khaki"),
    "abfahrt": QtGui.QColor("limegreen"),
    "kuppeln": QtGui.QColor("coral"),
    "flügeln": QtGui.QColor("orange"),
    "default": QtGui.QColor("gray")
}


class EreignisTabelle(QtCore.QAbstractTableModel):

    def __init__(self):
        super().__init__()
        self.ereignis_limit: int = 1000
        self.ereignisse: List[Ereignis] = []
        self._columns: List[str] = ['ereignis', 'zug', 'von', 'nach', 'gleis', 'status']

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self.ereignisse)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        ereignis = self.ereignisse[index.row()]
        col = self._columns[index.column()]

        if role == QtCore.Qt.DisplayRole:
            if col == 'ereignis':
                return ereignis.art
            elif col == 'zug':
                return ereignis.name
            elif col == 'status':
                if ereignis.verspaetung:
                    return f"{ereignis.verspaetung:+}"
                else:
                    return ""
            elif col == 'von':
                return ereignis.von
            elif col == 'nach':
                return ereignis.nach
            elif col == 'gleis':
                if ereignis.gleis == ereignis.plangleis:
                    return ereignis.gleis
                else:
                    return f"{ereignis.gleis} /{ereignis.plangleis}/"

        elif role == QtCore.Qt.ForegroundRole:
            try:
                return EREIGNISART_QCOLOR_SVG[ereignis.art]
            except KeyError:
                return EREIGNISART_QCOLOR_SVG["default"]

        elif role == QtCore.Qt.CheckStateRole:
            if col == 'gleis' and ereignis.gleis:
                if ereignis.amgleis:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return str(self._columns[section])
            if orientation == QtCore.Qt.Vertical:
                return self.ereignisse[section].zeit.time().isoformat(timespec='seconds')

    def add_ereignis(self, ereignis: Ereignis):
        if ereignis.art == "abfahrt" and ereignis.amgleis:
            ereignis = copy.copy(ereignis)
            ereignis.art = "bereit"
        elif ereignis.art == "ankunft" and not ereignis.amgleis:
            ereignis = copy.copy(ereignis)
            ereignis.art = "durchfahrt"
        elif ereignis.art == "wurdegruen":
            ereignis = copy.copy(ereignis)
            ereignis.art = "fahrt"
        elif ereignis.art == "fluegeln":
            ereignis = copy.copy(ereignis)
            ereignis.art = "flügeln"

        if ereignis not in self.ereignisse:
            self.ereignisse.append(ereignis)
            self.ereignisse = self.ereignisse[-self.ereignis_limit:]


class TickerWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.plugin_ereignis.register(self.add_ereignis)

        self.setWindowTitle("ereignis-ticker")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        self.model = EreignisTabelle()
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionMode(Qt.QAbstractItemView.NoSelection)
        layout.addWidget(self.table)

    def add_ereignis(self, *args, ereignis: Ereignis, **kwargs):
        self.model.add_ereignis(ereignis)
        self.model.layoutChanged.emit()
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.table.scrollToBottom()
