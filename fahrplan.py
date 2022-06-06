"""
dieses Qt-fenster stellt den fahrplan (zugliste und detailfahrplan eines zuges) tabellarisch dar.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union
from PyQt5 import Qt, QtCore, QtGui, QtWidgets, uic
from PyQt5.QtWidgets import QTableView, QLabel
from PyQt5.QtCore import QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stsplugin import PluginClient
from stsobj import ZugDetails, time_to_minutes, format_verspaetung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZuglisteModell(QtCore.QAbstractTableModel):
    """
    tabellenmodell für die zugliste

    die tabelle enthält die spalten 'Einfahrt', 'Zug', 'Von', 'Nach', 'Gleis', 'Verspätung', 'Hinweis'.
    jeder zug wird in einer zeile dargestellt.

    implementiert die methoden von QAbstractTableModel.
    die zugdaten werden per set_zugliste() bzw. get_zug() kommuniziert.

    die tabelle unterhält nur eine referenz auf die originalliste.
    es wird davon ausgegangen, dass die zugliste nicht häufing verändert wird
    und dass änderungen sofort über set_zugliste angezeigt werden.
    """
    def __init__(self):
        super().__init__()

        self._zugliste: Dict[int, ZugDetailsPlanung] = {}
        self._reihenfolge: List[int] = []
        self._columns: List[str] = ['Einfahrt', 'Zug', 'Von', 'Nach', 'Gleis', 'Verspätung', 'Hinweis']

    def set_zugliste(self, zugliste: Dict[int, ZugDetailsPlanung]) -> None:
        """
        zugliste setzen.

        die zugliste darf nur als ganzes über diese methode gesetzt werden.
        der direkte zugriff auf _zugliste kann einen absturz verursachen!

        :param zugliste: dies muss die zugliste aus dem planungsmodul sein.
        :return: None
        """
        self.beginResetModel()
        self._zugliste = zugliste
        self._reihenfolge = sorted(self._zugliste.keys())
        self.endResetModel()

    def get_zug(self, row) -> Optional[ZugDetailsPlanung]:
        """
        zug einer gewählten zeile auslesen.

        :param row: tabellenzeile
        :return: zugdetails aus der zugliste. None, wenn kein entsprechender zug gefunden wird.
        """
        try:
            return self._zugliste[self._reihenfolge[row]]
        except (KeyError, IndexError):
            return None

    def columnCount(self, parent: QModelIndex = ...) -> int:
        """
        anzahl spalten in der tabelle

        :param parent: nicht verwendet
        :return: die spaltenzahl ist fix.
        """
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        """
        anzahl zeilen (züge)

        :param parent: nicht verwendet
        :return: anzahl dargestellte züge.
        """
        return len(self._reihenfolge)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        """
        daten pro zelle ausgeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - UserRole gibt die originaldaten aus (zum sortieren benötigt).
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - CheckStateRole gibt an, ob ein zug am gleis steht.
            - ForegroundRole färbt die eingefahrenen, ausgefahrenen und noch unsichtbaren züge unterschiedlich ein.
            - TextAlignmentRole richtet den text aus.
        :return: verschiedene
        """
        if not index.isValid():
            return None

        try:
            row = index.row()
            zug = self._zugliste[self._reihenfolge[row]]
            col = self._columns[index.column()]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.UserRole:
            if col == 'ID':
                return zug.zid
            elif col == 'Einfahrt':
                return time_to_minutes(zug.einfahrtszeit) + zug.verspaetung
            elif col == 'Zug':
                return zug.nummer
            elif col == 'Verspätung':
                return zug.verspaetung
            elif col == 'Von':
                return zug.von
            elif col == 'Nach':
                return zug.nach
            elif col == 'Gleis':
                return zug.gleis
            elif col == 'Hinweis':
                return zug.hinweistext
            else:
                return None
        
        if role == QtCore.Qt.DisplayRole:
            if col == 'ID':
                return zug.zid
            elif col == 'Einfahrt':
                try:
                    return zug.einfahrtszeit.isoformat(timespec='minutes')
                except AttributeError:
                    return ""
            elif col == 'Zug':
                return zug.name
            elif col == 'Verspätung':
                try:
                    return format_verspaetung(zug.verspaetung)
                except AttributeError:
                    return ""
            elif col == 'Von':
                return zug.von
            elif col == 'Nach':
                return zug.nach
            elif col == 'Gleis' and zug.gleis:
                if zug.gleis == zug.plangleis:
                    return zug.gleis
                else:
                    return f"{zug.gleis} /{zug.plangleis}/"
            elif col == 'Hinweis' and zug.hinweistext:
                return zug.hinweistext
            else:
                return None

        elif role == QtCore.Qt.CheckStateRole:
            if col == 'Gleis' and zug.gleis:
                if zug.amgleis:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.ForegroundRole:
            if zug.sichtbar:
                return QtGui.QColor("darkRed")
            elif zug.gleis:
                return QtGui.QColor("darkBlue")
            else:
                return QtGui.QColor("gray")

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile und -spalte aus.
        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den spaltentitel oder die zug-id aus.
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._columns[section]
            elif orientation == QtCore.Qt.Vertical:
                return self._zugliste[self._reihenfolge[section]].zid


class FahrplanModell(QtCore.QAbstractTableModel):
    """
    tabellenmodell für den zugfahrplan

    die spalten sind 'Gleis', 'An', 'Ab', 'Verspätung', 'Flags', 'Folgezug', 'Hinweis'.
    jede zeile entspricht einem fahrplanziel.

    der anzuzeigende zug wird durch set_zug gesetzt.
    """
    def __init__(self):
        super().__init__()

        self.zug: Optional[ZugDetails] = None
        self._columns: List[str] = ['Gleis', 'An', 'VAn', 'Ab', 'VAb', 'Flags', 'Folgezug', 'Hinweis']

    def set_zug(self, zug: Optional[ZugDetails]):
        """
        anzuzeigenden zug setzen.

        :param zug: ZugDetails oder ZugDetailsPlanung. None = leerer fahrplan.
        :return: None
        """
        self.zug = zug
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        """
        spaltenzahl

        :param parent: nicht verwendet.
        :return: die spaltenzahl ist fix.
        """
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        """
        zeilenzahl (anzahl fahrplanziele)

        :param parent: nicht verwendet
        :return:
        """
        return len(self.zug.fahrplan) if self.zug else 0

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        """
        daten pro zelle ausgeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - TextAlignmentRole richtet den text aus.
        :return: verschiedene
        """
        if not index.isValid():
            return None

        try:
            zeile: ZugZielPlanung = self.zug.fahrplan[index.row()]
            col = self._columns[index.column()]
        except IndexError:
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 'Gleis' and zeile.gleis:
                if zeile.gleis == zeile.plan:
                    return zeile.gleis
                else:
                    return f"{zeile.gleis} /{zeile.plan}/"
            elif col == 'An' and zeile.an:
                return zeile.an.isoformat(timespec='minutes')
            elif col == 'Ab' and zeile.ab:
                return zeile.ab.isoformat(timespec='minutes')
            elif col == 'VAn':
                try:
                    return format_verspaetung(zeile.verspaetung_an)
                except AttributeError:
                    return ""
            elif col == 'VAb':
                try:
                    return format_verspaetung(zeile.verspaetung_ab)
                except AttributeError:
                    return ""
            elif col == 'Flags':
                return str(zeile.flags)
            elif col == 'Folgezug':
                if zeile.ersatzzug:
                    return zeile.ersatzzug.name
                elif zeile.kuppelzug:
                    return zeile.kuppelzug.name
                elif zeile.fluegelzug:
                    return zeile.fluegelzug.name
                else:
                    return None
            elif col == 'Hinweis' and zeile.hinweistext:
                return str(zeile.hinweistext)
            else:
                return None

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile aus.

        die fahrplantabelle hat keine kopfspalte.

        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den spaltentitel aus.
        :return: spaltentitel
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._columns[section]


class FahrplanWindow(QtWidgets.QWidget):
    """
    fensterklasse für den tabllenfahrplan

    das fenster enthält eine liste aller züge sowie den fahrplan eines gewählten zuges.
    der zug kann in der zugliste durch anklicken ausgewählt werden.
    die zugliste kann durch klicken auf die kopfzeile sortiert werden.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.zugliste_view: Optional[QTableView] = None
        self.fahrplan_view: Optional[QTableView] = None
        self.fahrplan_label: Optional[QLabel] = None
        self.folgezug_view: Optional[QTableView] = None
        self.folgezug_label: Optional[QLabel] = None

        py_path = Path(__file__).parent
        ui_path = Path(py_path, 'qt', 'fahrplan.ui')
        uic.loadUi(ui_path, self)

        self.client: Optional[PluginClient] = None
        self.planung: Optional[Planung] = None

        self.setWindowTitle("Tabellarischer Fahrplan")

        self.zugliste_modell = ZuglisteModell()
        self.zugliste_sort_filter = QSortFilterProxyModel(self)
        self.zugliste_sort_filter.setSourceModel(self.zugliste_modell)
        self.zugliste_sort_filter.setSortRole(QtCore.Qt.UserRole)
        self.zugliste_view.setModel(self.zugliste_sort_filter)
        self.zugliste_view.selectionModel().selectionChanged.connect(
            self.zugliste_selection_changed)
        self.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.zugliste_view.sortByColumn(0, 0)
        self.zugliste_view.setSortingEnabled(True)

        self.fahrplan_modell = FahrplanModell()
        self.fahrplan_view.setModel(self.fahrplan_modell)
        self.fahrplan_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.fahrplan_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.fahrplan_view.verticalHeader().setVisible(False)

        self.folgezug_modell = FahrplanModell()
        self.folgezug_view.setModel(self.folgezug_modell)
        self.folgezug_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.folgezug_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.folgezug_view.verticalHeader().setVisible(False)

    def update(self) -> None:
        """
        fahrplan mit neuen daten aktualisieren.

        wird vom hauptprogramm aufgerufen, wenn der fahrplan aktualisiert wurde.

        :return: None
        """
        try:
            view_index = self.zugliste_view.selectedIndexes()[0]
            model_index = self.zugliste_sort_filter.mapToSource(view_index)
        except IndexError:
            model_index = None

        self.zugliste_modell.set_zugliste(self.planung.zugliste)

        if model_index:
            view_index = self.zugliste_sort_filter.mapFromSource(model_index)
            self.zugliste_view.selectionModel().select(view_index, QItemSelectionModel.SelectionFlag.Select |
                                                       QItemSelectionModel.SelectionFlag.Rows)

        self.zugliste_view.resizeColumnsToContents()
        self.zugliste_view.resizeRowsToContents()

    @QtCore.pyqtSlot('QItemSelection', 'QItemSelection')
    def zugliste_selection_changed(self, selected, deselected):
        """
        fahrplan eines angewählten zuges darstellen.

        :param selected: nicht verwendet (die auswahl wird aus dem widget ausgelesen).
        :param deselected: nicht verwendet
        :return: None
        """
        try:
            index = self.zugliste_view.selectedIndexes()[0]
            index = self.zugliste_sort_filter.mapToSource(index)
            row = index.row()
            zug = self.zugliste_modell.get_zug(row)
            self.fahrplan_label.setText(f"Fahrplan {zug.name}")
            self.fahrplan_modell.set_zug(zug)
        except IndexError:
            pass
        else:
            self.fahrplan_view.resizeColumnsToContents()
            self.fahrplan_view.resizeRowsToContents()
        self.update_folgezug()

    def update_folgezug(self):
        if self.fahrplan_modell.zug:
            for fpz in self.fahrplan_modell.zug.fahrplan:
                folgezug = fpz.ersatzzug or fpz.fluegelzug or fpz.kuppelzug
                if folgezug:
                    self.folgezug_modell.set_zug(folgezug)
                    self.folgezug_label.setText(f"Fahrplan {folgezug.name}")
                    self.folgezug_view.resizeColumnsToContents()
                    self.folgezug_view.resizeRowsToContents()
                    break
            else:
                self.folgezug_modell.set_zug(None)
                self.folgezug_label.setText(f"Fahrplan Folgezug")
        else:
            self.folgezug_modell.set_zug(None)
            self.folgezug_label.setText(f"Fahrplan Folgezug")
