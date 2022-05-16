import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union
from PyQt5 import Qt, QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QModelIndex

from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stsplugin import PluginClient
from stsobj import ZugDetails

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZuglisteModell(QtCore.QAbstractTableModel):
    def __init__(self):
        super().__init__()

        self.zugliste: Optional[List[ZugDetails]] = None
        self._columns: List[str] = ['zug', 'von', 'nach', 'gleis', 'verspätung', 'hinweistext']

    def set_zugliste(self, zugliste: List[ZugDetails]) -> None:
        self.zugliste = zugliste
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self.zugliste) if self.zugliste else 0

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        try:
            zug: ZugDetailsPlanung = self.zugliste[index.row()]
            col = self._columns[index.column()]
        except IndexError:
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 'zug':
                return str(zug.name)
            elif col == 'verspätung':
                return f"{zug.verspaetung:+}"
            elif col == 'von':
                return str(zug.von)
            elif col == 'nach':
                return str(zug.nach)
            elif col == 'gleis' and zug.gleis:
                if zug.gleis == zug.plangleis:
                    return str(zug.gleis)
                else:
                    return f"{zug.gleis} /{zug.plangleis}/"
            elif col == 'hinweistext' and zug.hinweistext:
                return str(zug.hinweistext)
            else:
                return None

        elif role == QtCore.Qt.CheckStateRole:
            if col == 'gleis' and zug.gleis:
                if zug.amgleis:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked
            elif col == 'zug':
                if zug.sichtbar:
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
                return str(self.zugliste[section].zid)


class FahrplanModell(QtCore.QAbstractTableModel):
    def __init__(self):
        super().__init__()

        self.zug: Optional[ZugDetails] = None
        self._columns: List[str] = ['gleis', 'an', 'ab', 'verspätung', 'flags', 'folgezug', 'hinweistext']

    def set_zug(self, zug: ZugDetails):
        self.zug = zug
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self.zug.fahrplan) if self.zug else 0

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        try:
            zeile: ZugZielPlanung = self.zug.fahrplan[index.row()]
            col = self._columns[index.column()]
        except IndexError:
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 'gleis' and zeile.gleis:
                if zeile.gleis == zeile.plan:
                    return zeile.gleis
                else:
                    return f"{zeile.gleis} /{zeile.plan}/"
            elif col == 'an' and zeile.an:
                return zeile.an.isoformat(timespec='minutes')
            elif col == 'ab' and zeile.ab:
                return zeile.ab.isoformat(timespec='minutes')
            elif col == 'verspätung' and hasattr(zeile, 'verspaetung'):
                return f"{zeile.verspaetung:+}"
            elif col == 'flags':
                return str(zeile.flags)
            elif col == 'folgezug':
                if zeile.ersatzzug:
                    return zeile.ersatzzug.name
                elif zeile.kuppelzug:
                    return zeile.kuppelzug.name
                elif zeile.fluegelzug:
                    return zeile.fluegelzug.name
                else:
                    return None
            elif col == 'hinweistext' and zeile.hinweistext:
                return str(zeile.hinweistext)
            else:
                return None

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return str(self._columns[section])


class FahrplanWindow(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi('qt/fahrplan.ui', self)

        self.client: Optional[PluginClient] = None
        self.planung: Optional[Planung] = None

        self.setWindowTitle("fahrplan")

        self.zugliste = ZuglisteModell()
        self.fahrplan = FahrplanModell()

        self.zugliste_view.setModel(self.zugliste)
        self.fahrplan_view.setModel(self.fahrplan)

        self.zugliste_view.selectionModel().selectionChanged.connect(
            self.zugliste_selection_changed)

        self.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.fahrplan_view.setSelectionMode(Qt.QAbstractItemView.NoSelection)

    def update(self) -> None:
        self.zugliste.set_zugliste(sorted(self.planung.zugliste.values(), key=lambda x: x.zid))
        self.zugliste_view.resizeColumnsToContents()
        self.zugliste_view.resizeRowsToContents()

    @QtCore.pyqtSlot('QItemSelection', 'QItemSelection')
    def zugliste_selection_changed(self, selected, deselected):
        try:
            row = selected.indexes()[0].row()
            self.fahrplan.set_zug(self.zugliste.zugliste[row])
        except IndexError:
            pass
        else:
            self.fahrplan_view.resizeColumnsToContents()
            self.fahrplan_view.resizeRowsToContents()
