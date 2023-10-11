"""
dieses Qt-fenster stellt den fahrplan (zugliste und detailfahrplan eines zuges) tabellarisch dar.
"""

import logging
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5 import Qt, QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from stskit.zentrale import DatenZentrale
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stskit.stsobj import ZugDetails, time_to_minutes, format_verspaetung
from stskit.qt.ui_fahrplan import Ui_FahrplanWidget
from stskit.zielgraph import draw_zielgraph, zug_subgraph, format_node_label_name

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def zug_status(zug: ZugDetailsPlanung) -> str:
    if zug.sichtbar:
        return "S"
    elif zug.gleis:
        return "E"
    else:
        return "A"


class ZuglisteModell(QtCore.QAbstractTableModel):
    """
    tabellenmodell für die zugliste

    die tabelle enthält die spalten 'Einfahrt', 'Zug', 'Von', 'Nach', 'Gleis', 'Verspätung'.
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
        self._columns: List[str] = ['Status', 'Einfahrt', 'Zug', 'Von', 'Nach', 'Gleis', 'Verspätung']
        self.zugschema = None

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
                try:
                    return time_to_minutes(zug.einfahrtszeit) + zug.verspaetung
                except AttributeError:
                    return None
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
            elif col == 'Status':
                return zug_status(zug)
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
            elif col == 'Status':
                return zug_status(zug)
            else:
                return None

        elif role == QtCore.Qt.CheckStateRole:
            if col == 'Gleis' and zug.gleis:
                if zug.amgleis:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked
            elif col == 'Status':
                if zug.sichtbar:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.ForegroundRole:
            if zug.sichtbar:
                rgb = self.zugschema.zugfarbe_rgb(zug)
                farbe = QtGui.QColor(*rgb)
            elif zug.gleis:
                rgb = self.zugschema.zugfarbe_rgb(zug)
                farbe = QtGui.QColor(*rgb)
            else:
                farbe = QtGui.QColor("gray")
            return farbe

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

    die spalten sind 'Gleis', 'An', 'VAn', 'Ab', 'VAb', 'Flags', 'Vorgang', 'Vermerke'.
    jede zeile entspricht einem fahrplanziel.

    der anzuzeigende zug wird durch set_zug gesetzt.
    """
    def __init__(self):
        super().__init__()

        self.zug: Optional[ZugDetails] = None
        self._columns: List[str] = ['Gleis', 'An', 'VAn', 'Ab', 'VAb', 'Flags', 'Vorgang', 'Vermerke']

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
            elif col == 'Vorgang':
                if zeile.auto_korrektur:
                    return str(zeile.auto_korrektur)
                else:
                    return None
            elif col == 'Vermerke':
                abh = []
                for korrektur in zeile.fdl_korrektur.values():
                    abh.append(str(korrektur))
                return ", ".join(abh)
            else:
                return None

        elif role == QtCore.Qt.ForegroundRole:
            if self.zug.sichtbar:
                if zeile.abgefahren:
                    return QtGui.QColor("darkCyan")
                elif zeile.angekommen or zeile.gleis == self.zug.gleis:
                    return QtGui.QColor("cyan")
                else:
                    return None
            elif self.zug.gleis:
                return None
            else:
                return QtGui.QColor("darkCyan")

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
    def __init__(self, zentrale: DatenZentrale, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.ui = Ui_FahrplanWidget()
        self.ui.setupUi(self)

        self.setWindowTitle("Zugfahrplan")

        self.display_canvas = FigureCanvas(Figure(figsize=(3, 5)))
        self._axes = self.display_canvas.figure.subplots()

        self.ui.display_layout = QtWidgets.QHBoxLayout(self.ui.grafik_widget)
        self.ui.display_layout.setObjectName("display_layout")
        self.ui.display_layout.addWidget(self.display_canvas)

        self.zugliste_modell = ZuglisteModell()
        self.zugliste_modell.zugschema = self.zentrale.anlage.zugschema
        self.zugliste_sort_filter = QSortFilterProxyModel(self)
        self.zugliste_sort_filter.setSourceModel(self.zugliste_modell)
        self.zugliste_sort_filter.setSortRole(QtCore.Qt.UserRole)
        self.ui.zugliste_view.setModel(self.zugliste_sort_filter)
        self.ui.zugliste_view.selectionModel().selectionChanged.connect(
            self.zugliste_selection_changed)
        self.ui.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.zugliste_view.sortByColumn(0, 0)
        self.ui.zugliste_view.setSortingEnabled(True)

        self.fahrplan_modell = FahrplanModell()
        self.ui.fahrplan_view.setModel(self.fahrplan_modell)
        self.ui.fahrplan_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.fahrplan_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.fahrplan_view.verticalHeader().setVisible(False)

        self.folgezug_modell = FahrplanModell()
        self.ui.folgezug_view.setModel(self.folgezug_modell)
        self.ui.folgezug_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.folgezug_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.folgezug_view.verticalHeader().setVisible(False)

    def planung_update(self, *args, **kwargs) -> None:
        """
        fahrplan mit neuen daten aktualisieren.

        wird vom hauptprogramm aufgerufen, wenn der fahrplan aktualisiert wurde.

        :return: None
        """
        try:
            view_index = self.ui.zugliste_view.selectedIndexes()[0]
            model_index = self.zugliste_sort_filter.mapToSource(view_index)
        except IndexError:
            model_index = None

        self.zugliste_modell.set_zugliste(self.zentrale.planung.zugliste)

        if model_index:
            view_index = self.zugliste_sort_filter.mapFromSource(model_index)
            self.ui.zugliste_view.selectionModel().select(view_index, QItemSelectionModel.SelectionFlag.Select |
                                                       QItemSelectionModel.SelectionFlag.Rows)

        self.ui.zugliste_view.resizeColumnsToContents()
        self.ui.zugliste_view.resizeRowsToContents()

    @QtCore.pyqtSlot('QItemSelection', 'QItemSelection')
    def zugliste_selection_changed(self, selected, deselected):
        """
        fahrplan eines angewählten zuges darstellen.

        :param selected: nicht verwendet (die auswahl wird aus dem widget ausgelesen).
        :param deselected: nicht verwendet
        :return: None
        """
        try:
            index = self.ui.zugliste_view.selectedIndexes()[0]
            index = self.zugliste_sort_filter.mapToSource(index)
            row = index.row()
            zug = self.zugliste_modell.get_zug(row)
            self.ui.fahrplan_label.setText(f"Stammzug {zug.name}")
            self.fahrplan_modell.set_zug(zug)
        except IndexError:
            pass
        else:
            self.ui.fahrplan_view.resizeColumnsToContents()
            self.ui.fahrplan_view.resizeRowsToContents()
        self.update_folgezug()
        self.grafik_update()

    def update_folgezug(self):
        if self.fahrplan_modell.zug:
            for fpz in self.fahrplan_modell.zug.fahrplan:
                folgezug = fpz.ersatzzug or fpz.fluegelzug or fpz.kuppelzug
                if folgezug:
                    self.folgezug_modell.set_zug(folgezug)
                    self.ui.folgezug_label.setText(f"Folgezug {folgezug.name}")
                    self.ui.folgezug_view.resizeColumnsToContents()
                    self.ui.folgezug_view.resizeRowsToContents()
                    break
            else:
                self.folgezug_modell.set_zug(None)
                self.ui.folgezug_label.setText(f"Kein Folgezug")
        else:
            self.folgezug_modell.set_zug(None)
            self.ui.folgezug_label.setText(f"Kein Folgezug")

    def grafik_update(self):
        def node_color(data):
            farbe = mpl.rcParams['text.color']
            try:
                obj: ZugZielPlanung = data['obj']
                zug = obj.zug
            except (AttributeError, KeyError):
                pass
            else:
                if zug.sichtbar:
                    if obj.abgefahren:
                        farbe = "darkcyan"
                    elif obj.angekommen or obj.gleis == zug.gleis:
                        farbe = "cyan"
                elif not zug.gleis:
                    farbe = "darkcyan"

            return farbe

        self._axes.clear()

        try:
            zg = zug_subgraph(self.zentrale.planung.zielgraph, self.fahrplan_modell.zug.zid)
        except AttributeError:
            logger.exception("exception in grafik_update")
            return

        if len(zg):
            logger.debug(f"draw_zielgraph")
            draw_zielgraph(zg, node_format=format_node_label_name, node_color=node_color, ax=self._axes)
        else:
            logger.warning(f"leerer zielgraph")

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def on_resize(self, event):
        """
        matplotlib resize-event

        zeichnet die grafik neu.

        :param event:
        :return:
        """

        self.grafik_update()
