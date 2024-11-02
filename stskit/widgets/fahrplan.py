"""
dieses Qt-fenster stellt den fahrplan (zugliste und detailfahrplan eines zuges) tabellarisch dar.
"""

import logging
from typing import Any, Dict, List, Optional

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5 import Qt, QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from stskit.dispo.anlage import Anlage
from stskit.zentrale import DatenZentrale
from stskit.plugin.stsobj import format_verspaetung, format_minutes
from stskit.qt.ui_fahrplan import Ui_FahrplanWidget
from stskit.model.zielgraph import ZielGraph, ZielGraphNode, ZielLabelType
from stskit.model.zuggraph import ZugGraph, ZugGraphNode
from stskit.plots.zielplot import ZielPlot

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
    def __init__(self, anlage: Anlage):
        super().__init__()

        self.anlage = anlage
        self.zid_liste: List[int] = []
        self._columns: List[str] = ['Zug', 'Status', 'Von', 'Nach', 'Einfahrt', 'Ausfahrt', 'Gleis', 'Verspätung']
        self.zugschema = None

    @property
    def zuggraph(self) -> ZugGraph:
        return self.anlage.zuggraph

    @property
    def zielgraph(self) -> ZielGraph:
        return self.anlage.zielgraph

    def update(self):
        """
        Zugdaten aktualisieren

        :param zuggraph:
        :return: None
        """
        self.beginResetModel()
        self.zid_liste = sorted(self.zuggraph.nodes())
        self.endResetModel()

    def get_zug(self, row: int) -> Optional[ZugGraphNode]:
        """
        Zug einer gewählten Tabellenzeile auslesen.

        :param row: Index der Tabellenzeile
        :return: Zugdaten aus dem Originalgraph. None, wenn kein entsprechender Zug gefunden wird.
        """
        try:
            return self.zuggraph.nodes[self.zid_liste[row]]
        except (KeyError, IndexError):
            return None

    @staticmethod
    def zug_status(zug: ZugGraphNode) -> str:
        if zug.sichtbar:
            return "S"
        elif zug.ausgefahren:
            return "A"
        elif zug.gleis:
            return "E"
        else:
            return "?"

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
        return len(self.zid_liste)

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
            zug = self.zuggraph.nodes[self.zid_liste[row]]
            col = self._columns[index.column()]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.UserRole:
            if col == 'ID':
                return zug.zid
            elif col == 'Einfahrt':
                try:
                    fid = self.zielgraph.zuganfaenge[zug.zid]
                    ziel = self.zielgraph.nodes[fid]
                    return ziel.p_an
                except (AttributeError, KeyError):
                    return None
            elif col == 'Ausfahrt':
                try:
                    fid = self.zielgraph.zugenden[zug.zid]
                    ziel = self.zielgraph.nodes[fid]
                    return ziel.p_ab
                except (AttributeError, KeyError):
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
                return self.zug_status(zug)
            else:
                return None
        
        if role == QtCore.Qt.DisplayRole:
            if col == 'ID':
                return zug.zid
            elif col == 'Einfahrt':
                try:
                    fid = self.zielgraph.zuganfaenge[zug.zid]
                    ziel = self.zielgraph.nodes[fid]
                    return format_minutes(ziel.p_an)
                except (AttributeError, KeyError, TypeError):
                    return None
            elif col == 'Ausfahrt':
                try:
                    fid = self.zielgraph.zugenden[zug.zid]
                    ziel = self.zielgraph.nodes[fid]
                    return format_minutes(ziel.p_ab)
                except (AttributeError, KeyError, TypeError):
                    return None
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
                return self.zug_status(zug)
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
                return self.zid_liste[section]


class ZuglisteFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent=...):
        super().__init__(parent)
        self._simzeit: int = 0
        self._vorlaufzeit: int = 0
        self._nachlaufzeit: int = 15
        self._zugliste_model: ZuglisteModell = None

    @property
    def zuggraph(self) -> ZugGraph:
        return self.anlage.zuggraph

    @property
    def zielgraph(self) -> ZielGraph:
        return self.anlage.zielgraph

    @property
    def simzeit(self) -> int:
        return self._simzeit

    @simzeit.setter
    def simzeit(self, minuten: int):
        self._simzeit = minuten

    @property
    def vorlaufzeit(self) -> int:
        return self._vorlaufzeit

    @vorlaufzeit.setter
    def vorlaufzeit(self, minuten: int):
        self._vorlaufzeit = minuten

    @property
    def nachlaufzeit(self) -> int:
        return self._nachlaufzeit

    @nachlaufzeit.setter
    def nachlaufzeit(self, minuten: int):
        self._nachlaufzeit = minuten

    def filterAcceptsRow(self, source_row, source_parent):
        if self.simzeit <= 0:
            return True

        zugliste_modell: Optional[ZuglisteModell] = None
        while zugliste_modell is None:
            source = self.sourceModel()
            if isinstance(source, ZuglisteModell):
                zugliste_modell = source
                break

        try:
            zug = zugliste_modell.get_zug(source_row)
        except AttributeError:
            return True
        try:
            if zug is None or zug.sichtbar:
                return True
        except AttributeError:
            return False

        if zug.gleis or zug.zid < 0:
            if self._vorlaufzeit <= 0:
                return True

            try:
                anfang_id = zugliste_modell.zielgraph.zuganfaenge[zug.zid]
                anfang = zugliste_modell.zielgraph.nodes[anfang_id]
            except KeyError:
                pass
            else:
                try:
                    if anfang.p_an + min(0, anfang.v_an) > self.simzeit + self._vorlaufzeit:
                        return False
                except AttributeError:
                    pass

        else:
            if self._nachlaufzeit <= 0:
                return True

            try:
                ende_id = zugliste_modell.zielgraph.zugenden[zug.zid]
                ende = zugliste_modell.zielgraph.nodes[ende_id]
            except KeyError:
                return False
            else:
                try:
                    if ende.p_ab + ende.v_ab < self.simzeit - self._nachlaufzeit:
                        return False
                except AttributeError:
                    pass

        return True


class FahrplanModell(QtCore.QAbstractTableModel):
    """
    tabellenmodell für den zugfahrplan

    die spalten sind 'Gleis', 'An', 'VAn', 'Ab', 'VAb', 'Flags', 'Vorgang', 'Vermerke'.
    jede zeile entspricht einem fahrplanziel.

    der anzuzeigende zug wird durch set_zug gesetzt.
    """
    def __init__(self, anlage: Anlage):
        super().__init__()

        self.anlage = anlage
        self.zid: int = 0
        self.zug: Optional[ZugGraphNode] = None
        self.zugpfad: List[ZielLabelType] = []
        self.zweige: Dict[ZielLabelType, ZielLabelType] = {}
        self._columns: List[str] = ['Gleis', 'An', 'VAn', 'Ab', 'VAb', 'Flags', 'Vorgang', 'Vermerke']

    @property
    def zuggraph(self) -> ZugGraph:
        return self.anlage.zuggraph

    @property
    def zielgraph(self) -> ZielGraph:
        return self.anlage.zielgraph

    def set_zug(self, zid: int):
        """
        Anzuzeigenden Zug setzen.

        :param zid: Zug-ID. 0 = leerer Fahrplan.
        :return: None
        """
        self.beginResetModel()
        self.zid = zid
        self.update()
        self.endResetModel()

    def update(self):
        self.beginResetModel()
        if self.zid:
            self.zug = self.zuggraph.nodes[self.zid]
            self.zugpfad = list(self.zielgraph.zugpfad(self.zid))
        else:
            self.zug = None
            self.zugpfad = []
        self._update_zweige()
        self.endResetModel()

    def _update_zweige(self):
        self.zweige = {}

        for fid in self.zugpfad:
            for u, v, d in self.zielgraph.out_edges(fid, data=True):
                if d.typ in {"E", "K", "F"}:
                    self.zweige[fid] = v

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
        return len(self.zugpfad)

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
            ziel: ZielGraphNode = self.zielgraph.nodes[self.zugpfad[index.row()]]
            col = self._columns[index.column()]
        except IndexError:
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 'Gleis' and ziel.gleis:
                if ziel.gleis == ziel.plan:
                    return ziel.gleis
                else:
                    return f"{ziel.gleis} /{ziel.plan}/"
            elif col == 'An':
                try:
                    return format_minutes(ziel.p_an)
                except AttributeError:
                    return None
            elif col == 'Ab':
                try:
                    return format_minutes(ziel.p_ab)
                except AttributeError:
                    return None
            elif col == 'VAn':
                try:
                    return format_verspaetung(ziel.v_an)
                except AttributeError:
                    return ""
            elif col == 'VAb':
                try:
                    return format_verspaetung(ziel.v_ab)
                except AttributeError:
                    return ""
            elif col == 'Flags':
                return str(ziel.flags)
            elif col == 'Vorgang':
                return self.format_vorgang(ziel)
            elif col == 'Vermerke':
                # todo
                return None
            else:
                return None

        elif role == QtCore.Qt.ForegroundRole:
            if self.zug.sichtbar:
                if ziel.status == "ab":
                    return QtGui.QColor("darkCyan")
                elif ziel.status == "an" or ziel.gleis == self.zug.gleis:
                    return QtGui.QColor("cyan")
                else:
                    return None
            elif self.zug.ausgefahren:
                return QtGui.QColor("darkCyan")
            elif self.zug.gleis:
                return None
            else:
                return QtGui.QColor("red")

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def format_vorgang(self, ziel: ZielGraphNode) -> str:
        operations = []

        for u, v, d in self.zielgraph.in_edges(ziel.fid, data=True):
            if d.typ in {"E", "K", "F"}:
                try:
                    ursprung = self.zuggraph.nodes[u[0]]
                    ursprung_name = ursprung.name
                except KeyError:
                    ursprung_name = "?"

                operations.append(f"{d.typ} ← {ursprung_name}")

        for u, v, d in self.zielgraph.out_edges(ziel.fid, data=True):
            if d.typ in {"E", "K", "F"}:
                try:
                    folge = self.zuggraph.nodes[v[0]]
                    folge_name = folge.name
                except KeyError:
                    folge_name = "?"

                operations.append(f"{d.typ} → {folge_name}")

        return ", ".join(operations)

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

        self.zugliste_modell = ZuglisteModell(zentrale.anlage)

        self.zugliste_modell.zugschema = self.zentrale.anlage.zugschema
        self.zugliste_sort_filter = ZuglisteFilterProxy(self)
        self.zugliste_sort_filter.setSourceModel(self.zugliste_modell)
        self.zugliste_sort_filter.setSortRole(QtCore.Qt.UserRole)
        self.ui.zugliste_view.setModel(self.zugliste_sort_filter)
        self.ui.zugliste_view.selectionModel().selectionChanged.connect(
            self.zugliste_selection_changed)
        self.ui.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.zugliste_view.sortByColumn(0, 0)
        self.ui.zugliste_view.setSortingEnabled(True)

        self.ui.vorlaufzeit_spin.setValue(self.zugliste_sort_filter.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.zugliste_sort_filter.nachlaufzeit)
        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self.ui.suche_zug_edit.textEdited.connect(self.suche_zug_changed)
        self.ui.suche_loeschen_button.clicked.connect(self.suche_loeschen_clicked)

        self.fahrplan_modell = FahrplanModell(zentrale.anlage)
        self.ui.fahrplan_view.setModel(self.fahrplan_modell)
        self.ui.fahrplan_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.fahrplan_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.fahrplan_view.verticalHeader().setVisible(False)

        self.folgezug_modell = FahrplanModell(zentrale.anlage)
        self.ui.folgezug_view.setModel(self.folgezug_modell)
        self.ui.folgezug_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.folgezug_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.folgezug_view.verticalHeader().setVisible(False)

        self.zielplot = ZielPlot(zentrale.anlage)

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

        self.zugliste_sort_filter.simzeit = self.zentrale.simzeit_minuten
        self.zugliste_modell.update()
        self.fahrplan_modell.update()
        self.folgezug_modell.update()

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
            self.fahrplan_modell.set_zug(zug.zid)
            self.zielplot.select_zug(zug.zid)
        except IndexError:
            pass
        else:
            self.ui.fahrplan_view.resizeColumnsToContents()
            self.ui.fahrplan_view.resizeRowsToContents()
        self.update_folgezug()
        self.grafik_update()

    def update_folgezug(self):
        if self.fahrplan_modell.zid:
            for fid1 in self.fahrplan_modell.zugpfad:
                try:
                    fid2 = self.fahrplan_modell.zweige[fid1]
                    ziel2 = self.fahrplan_modell.zielgraph.nodes[fid2]
                    zug2 = self.fahrplan_modell.zuggraph.nodes[ziel2.zid]
                except KeyError:
                    continue
                else:
                    self.folgezug_modell.set_zug(ziel2.zid)
                    self.ui.folgezug_label.setText(f"Folgezug {zug2.name}")
                    self.ui.folgezug_view.resizeColumnsToContents()
                    self.ui.folgezug_view.resizeRowsToContents()
                    break
            else:
                self.folgezug_modell.set_zug(0)
                self.ui.folgezug_label.setText(f"Kein Folgezug")
        else:
            self.folgezug_modell.set_zug(0)
            self.ui.folgezug_label.setText(f"Kein Folgezug")

    def grafik_update(self):
        self.zielplot.draw(self._axes)

    def on_resize(self, event):
        """
        matplotlib resize-event

        zeichnet die grafik neu.

        :param event:
        :return:
        """

        self.grafik_update()

    @pyqtSlot()
    def vorlaufzeit_changed(self):
        try:
            self.zugliste_sort_filter.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def nachlaufzeit_changed(self):
        try:
            self.zugliste_sort_filter.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def suche_zug_changed(self):
        text = self.ui.suche_zug_edit.text()
        if not text:
            return

        column = self.zugliste_modell._columns.index("Zug")
        start = self.zugliste_sort_filter.index(0, column)
        matches = self.zugliste_sort_filter.match(start, QtCore.Qt.DisplayRole, text, 1, QtCore.Qt.MatchContains)

        for index in matches:
            if index.column() == column:
                self.ui.zugliste_view.selectionModel().clear()
                self.ui.zugliste_view.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Select |
                                                              QItemSelectionModel.SelectionFlag.Rows)
                break
        else:
            self.ui.zugliste_view.selectionModel().clear()

    @pyqtSlot()
    def suche_loeschen_clicked(self):
        self.ui.suche_zug_edit.clear()
