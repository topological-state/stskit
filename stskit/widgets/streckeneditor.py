import copy

from dataclasses import dataclass
from stskit.model.liniengraph import LinienGraphEdge, LinienGraph, LinienGraphNode
import bisect
import logging
import pickle
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import (Slot, Signal, QAbstractListModel, QAbstractTableModel, QModelIndex, QItemSelectionModel,
                            QStringListModel, QObject, QMimeData, QByteArray)
from PySide6.QtWidgets import QWidget, QAbstractItemView, QStyledItemDelegate, QComboBox
from PySide6.QtGui import QFont, QTextCharFormat, QColor

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BAHNHOFELEMENT_BESCHREIBUNG
from stskit.model.journal import JournalEntry, Journal, JournalEntryGroup
from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


ROLE_ITALIC = QtCore.Qt.UserRole + 1
ROLE_STRIKETHROUGH = QtCore.Qt.UserRole + 2


class StyledTextDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if self.parent().model().data(index, ROLE_ITALIC):
            option.font.setItalic(True)
        if self.parent().model().data(index, ROLE_STRIKETHROUGH):
            format = QTextCharFormat()
            # format.setForeground(QColor("gray"))
            format.setFontStrikeOut(True)
            option.textCursor.mergeCharFormat(format)


class StreckenListModel(QAbstractListModel):
    """
    ListModel für die Streckenliste

    """

    CHECK_STATE = {False: QtCore.Qt.Unchecked, True: QtCore.Qt.Checked}

    def __init__(self, anlage: Anlage, parent=None):
        super().__init__(parent)
        self.anlage: Anlage = anlage
        self._namen: List[str] = []
        self._checked: Set[str] = set()
        self._edited: Set[str] = set()
        self._auto: Set[str] = set()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._namen)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return "Strecke"
            elif orientation == QtCore.Qt.Vertical:
                return self._namen[section]

        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        name = self._namen[row]

        if role == QtCore.Qt.UserRole:
            return name

        elif role == QtCore.Qt.DisplayRole:
            return name

        elif role == QtCore.Qt.CheckStateRole:
            return self.CHECK_STATE[name in self._checked]

        elif role == ROLE_ITALIC:
            return self.get_auto(name)

        elif role == QtCore.Qt.ToolTipRole:
            tt = f"Strecke {name}"
            if self.get_auto(name):
                tt = f"{tt} (automatisch erstellt)"
            elif self.get_edited(name):
                tt = f"{tt} (geändert)"
            return tt

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        result = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable

        return result

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return False

        if role == QtCore.Qt.CheckStateRole:
            value = QtCore.Qt.CheckState(value)
            checked = value in (QtCore.Qt.Checked, QtCore.Qt.PartiallyChecked)
            name = self._namen[index.row()]
            self.set_checked(name, checked)
            self.dataChanged.emit(index, value)
            return True

        # nicht editierbar
        return False

    def add(self, name: str, auto=False, checked=False, edited=False):
        if name not in self._namen:
            self.beginResetModel()
            self._namen = sorted(self._namen + [name])
            if auto:
                self._auto.add(name)
            else:
                self._auto.discard(name)
            if checked:
                self._checked = {name}
            else:
                self._checked.discard(name)
            if edited:
                self._edited.add(name)
            else:
                self._edited.discard(name)
            self.endResetModel()

    def remove(self, name: str):
        if name in self._namen:
            self.beginResetModel()
            try:
                self._auto.discard(name)
                self._checked.discard(name)
                self._edited.discard(name)
                self._namen.remove(name)
            except (ValueError, KeyError):
                pass
            self.endResetModel()

    def update(self, strecken: List[str],
               auto: Optional[Iterable[str]] = None,
               checked: Optional[Iterable[str]] = None,
               edited: Optional[Iterable[str]] = None):
        self.beginResetModel()
        self._namen = sorted(strecken)
        self._auto = set(auto)
        try:
            _checked = list(checked)[0:1]
        except TypeError:
            _checked = set()
        self._checked = set(_checked)
        self._edited = set(edited)
        self.endResetModel()
        
    def get_auto(self, name: str) -> bool:
        return name in self._auto

    def get_checked(self, name: str) -> bool:
        return name in self._checked

    def get_edited(self, name: str) -> bool:
        return name in self._edited

    def set_auto(self, name: str, value: bool):
        if value != self.get_auto(name):
            self.beginResetModel()
            if value:
                self._auto.add(name)
            else:
                self._auto.discard(name)
            self.endResetModel()

    def set_checked(self, name: str, value: bool):
        """
        Checked-Status setzen

        Nur eine Strecke kann Checked sein.
        """

        if value != self.get_checked(name):
            self.beginResetModel()
            if value:
                self._checked = {name}
            else:
                self._checked.discard(name)
            self.endResetModel()

    def set_edited(self, name: str, value: bool):
        if value != self.get_edited(name):
            self.beginResetModel()
            if value:
                self._edited.add(name)
            else:
                self._edited.discard(name)
            self.endResetModel()


@dataclass
class StreckenSegment:
    """
    Streckensegment (Zeile) im Streckeneditor
    """

    station1: BahnhofElement
    station2: BahnhofElement | None = None
    markierung: str | None = None
    fahrzeit: int | float | None = None
    fahrzeit_manuell: bool = False

    def reset(self):
        self.station2 = None
        self.markierung = None
        self.fahrzeit = None
        self.fahrzeit_manuell = False


class StreckenItemDelegate(StyledTextDelegate):
    def __init__(self, /, parent=...):
        super().__init__(parent)

    def createEditor(self, parent, option, index, /):
        model = self.parent().model()
        col = index.column()
        col_key = model.headerData(col, QtCore.Qt.Horizontal)

        match col_key:
            case 'Markierung':
                editor = QComboBox(parent)
                editor.setFrame(False)
                editor.addItems(list(model.MARKIERUNGEN.values()))
            case 'Fahrzeit':
                editor = super().createEditor(parent, option, index)
            case _:
                editor = None

        return editor

    def setEditorData(self, editor, index, /):
        model = self.parent().model()
        col = index.column()
        col_key = model.headerData(col, QtCore.Qt.Horizontal)

        match col_key:
            case 'Markierung':
                value = model.data(QtCore.Qt.EditRole)
                if isinstance(editor, QComboBox):
                    editor.setCurrentText(value)
            case _:
                super().setEditorData(editor, index)

    def setModelData(self, editor, model, index, /):
        col = index.column()
        col_key = model.headerData(col, QtCore.Qt.Horizontal)

        match col_key:
            case 'Markierung':
                if isinstance(editor, QComboBox):
                    value = editor.currentText()
                    model.setData(index, value, QtCore.Qt.EditRole)
            case _:
                super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index, /):
        model = self.parent().model()
        col = index.column()
        col_key = model.headerData(col, QtCore.Qt.Horizontal)

        match col_key:
            case 'Markierung':
                editor.setGeometry(option.rect)
            case _:
                super().updateEditorGeometry(editor, option, index)


class StreckenEditorModel(QAbstractTableModel):
    """
    ListModel für den Streckeneditor

    Attributes:
        mit_liniendaten: Gibt an, ob Liniendaten angezeigt und bearbeitet werden können.
        columns: Liste von Spaltenüberschriften.
            Hängt davon ab, ob Liniendaten angezeigt werden.
        sorted: Alphanumerische Sortierung der Einträge.
            Nur für die Abwahlliste sinnvoll.
            Schliesst Liniendaten aus.
        rows: Liste von Bahnhöfen
        segments: Liste von Streckensegmenten (Kantendaten) zu den Bahnhöfen in rows.
            Rows und segments müssen immer synchron sein,
            d.h. `rows[i] == segments[i].station1` für alle i.
            Zu jeder Aenderung an rows muss das entsprechende Element von segments erstellt werden.
            Es reicht jedoch, station1 zu setzen, den Rest erledigt die _update-Methode.
            Wenn keine Liniendaten bearbeitet werden, werden die Einträge nicht unterhalten.
        anlage: Anlage-Objekt mit Streckendaten und Liniengraph.
        liniengraph: Liniengraph-Objekt enthält eine bearbeitete Version des Liniengraphen.
            Ohne Aenderungen ist es ein View von anlage.liniengraph.
            Mit Aenderungen ist es eine tiefe Kopie von anlage.liniengraph mit angewendetem Journal.
        journal: Liste von Aenderungen am Liniengraph.
            Die Aenderungen betreffen die Kantenattribute markierung und fahrzeit_manuell.
    """

    MARKIERUNGEN = {"": "", "H": "Gefahrgut", "G": "Gleis", "O": "Profil", "E": "Traktion"}
    FLAGS = {"": "", "Gefahrgut": "H", "Gleis": "G", "Profil": "O", "Traktion": "E"}

    drop_completed = Signal(str)

    def __init__(self, anlage: Anlage, mit_liniendaten: bool, sortierung: bool, parent=None):
        super().__init__(parent)
        self.anlage: Anlage = anlage
        self.liniengraph: LinienGraph = anlage.liniengraph.copy(as_view=True)
        self.journal: Journal = Journal()
        self.mit_liniendaten = mit_liniendaten
        self.sorted = sortierung and not mit_liniendaten
        if self.mit_liniendaten:
            self.columns: List[str] = ["Station", "Markierung", "Fahrzeit"]
        else:
            self.columns: List[str] = ["Station"]
        self.rows: List[BahnhofElement] = []
        self.segments: List[StreckenSegment] = []
        self._drag_data = {}

    def update(self, strecke: Sequence[BahnhofElement]) -> None:
        self.beginResetModel()
        if self.sorted:
            self.rows = sorted(strecke)
        else:
            self.rows = list(strecke)
        self.segments = [StreckenSegment(station1=station1) for station1 in self.rows]
        self._update()
        self.endResetModel()

    def _update(self):
        """
        segments-Attribut aktualisieren

        Führt die Attribute der Streckensegmente (segments) nach.
        Die Segmente müssen bereits existieren und station1 muss korrekt gesetzt sein.
        Die Segmentdaten werden self.liniengraph entnommen.

        Wenn keine Liniendaten bearbeitet werden, macht die Methode nichts.
        """

        if not self.mit_liniendaten:
            return
        
        for segment1, segment2 in zip(self.segments, self.segments[1:]):
            if segment1.station2 != segment2.station1:
                segment1.reset()
                segment1.station2 = segment2.station1

            try:
                liniendata: LinienGraphEdge = self.liniengraph.edges[segment1.station1, segment1.station2]
            except KeyError:
                continue

            segment1.markierung = liniendata.get('markierung')
            fahrzeit_manuell = liniendata.get('fahrzeit_manuell')
            segment1.fahrzeit = fahrzeit_manuell or liniendata.get('fahrzeit_schnitt')
            segment1.fahrzeit_manuell = bool(fahrzeit_manuell)

        # letzte zeile ist nur endpunkt
        try:
            segment = self.segments[-1]
        except IndexError:
            pass
        else:
            segment.reset()
        
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.columns)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.columns[section]
            elif orientation == QtCore.Qt.Vertical:
                return self.rows[section]

        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        station = self.rows[row]
        segment = self.segments[row]
        col = index.column()
        col_key = self.columns[col]

        if role == QtCore.Qt.UserRole:
            match col_key:
                case 'Station':
                    return station
                case 'Markierung':
                    return segment.markierung
                case 'Fahrzeit':
                    return segment.fahrzeit

        elif role == QtCore.Qt.DisplayRole:
            match col_key:
                case 'Station':
                    return str(station)
                case 'Markierung':
                    return self.MARKIERUNGEN[segment.markierung]
                case 'Fahrzeit':
                    if segment.station2 is not None and segment.fahrzeit is not None:
                        return f"{segment.fahrzeit:.1f}"

        elif role == QtCore.Qt.ToolTipRole:
            match col_key:
                case 'Station':
                    return f"{BAHNHOFELEMENT_BESCHREIBUNG[station.typ]} {station.name}"

        elif role == QtCore.Qt.WhatsThisRole:
            match col_key:
                case 'Station':
                    return f"{BAHNHOFELEMENT_BESCHREIBUNG[station.typ]} {station.name}"

        elif role == QtCore.Qt.EditRole:
            match col_key:
                case 'Station':
                    return str(station)
                case 'Markierung':
                    if segment.station2 is not None:
                        return self.MARKIERUNGEN[segment.markierung]
                case 'Fahrzeit':
                    if segment.station2 is not None and segment.fahrzeit is not None:
                        return f"{segment.fahrzeit:.1f}"

        elif role == ROLE_ITALIC:
            match col_key:
                case 'Fahrzeit':
                    if segment.station2 is not None:
                        return not segment.fahrzeit_manuell

        elif role == QtCore.Qt.TextAlignmentRole:
            if col_key in {'Markierung', 'Fahrzeit'}:
                return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter
            else:
                return QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        row = index.row()
        segment = self.segments[row]
        col = index.column()
        col_key = self.columns[col]

        result = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled
        if segment.station2 is not None and col_key in {'Markierung', 'Fahrzeit'}:
            result |= QtCore.Qt.ItemIsEditable

        return result

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return None

        row = index.row()
        segment = self.segments[row]
        col = index.column()
        col_key = self.columns[col]

        if role == QtCore.Qt.EditRole and segment.station2 is not None:
            match col_key:
                case 'Markierung':
                    try:
                        value = self.FLAGS[value]
                    except KeyError:
                        value = ""
                    if self.set_markierung(segment, value):
                        self.dataChanged.emit(index, index)
                        return True
                case 'Fahrzeit':
                    if self.set_fahrzeit(segment, value):
                        self.dataChanged.emit(index, index)
                        return True

    def set_markierung(self, segment: StreckenSegment, value: str) -> bool:
        try:
            value = str(value)
        except ValueError:
            return False

        return self._set_segment_property(segment, 'markierung', value)
    
    def set_fahrzeit(self, segment: StreckenSegment, value: float) -> bool:
        try:
            value = float(value)
        except ValueError:
            return False

        return self._set_segment_property(segment, 'fahrzeit_manuell', value)

    def _set_segment_property(self, segment: StreckenSegment, name: str, value: Any) -> bool:
        if segment.station2 is None:
            return False

        entry = JournalEntry("liniengraph", segment.station1)
        data = {name: value}

        if not self.liniengraph.has_node(segment.station1):
            node_data = LinienGraphNode(typ=segment.station1.typ, name=segment.station1.name, fahrten=0)
            entry.add_node(segment.station1, **node_data)

        if not self.liniengraph.has_node(segment.station2):
            node_data = LinienGraphNode(typ=segment.station2.typ, name=segment.station2.name, fahrten=0)
            entry.add_node(segment.station1, **node_data)

        if not self.liniengraph.has_edge(segment.station1, segment.station2):
            edge_data = LinienGraphEdge(
                fahrzeit_min=LinienGraph.MAX_FAHRZEIT,
                fahrzeit_max=0,
                fahrten=0,
                fahrzeit_summe=0.0,
                fahrzeit_schnitt=0.0,
            )
            entry.add_edge(segment.station1, segment.station2, **edge_data)

        entry.change_edge(segment.station1, segment.station2, **data)

        self.journal.add_entry((name, segment.station1), entry)
        self._apply_journal()
        self._update()

        return True

    def _apply_journal(self):
        """
        Journal auf Liniengraph anwenden.

        Kopiert den Liniengraph von der Anlage und spielt das Journal darauf ab.
        """

        self.liniengraph = copy.deepcopy(self.anlage.liniengraph)
        self.journal.replay({"liniengraph": self.liniengraph})

    def insert(self, row: int, bst: BahnhofElement):
        """
        Station einfügen

        Args:
            row: Zielindex.
                Hat keinen Einfluss, wenn die Liste sortiert ist.
            bst: Einzufügendes BahnhofElement.
            
        Returns:
            True bei Erfolg, False bei falschem Index.
        """

        if self.sorted:
            row = bisect.bisect_left(self.rows, bst)

        self.beginInsertRows(QModelIndex(), row, row)
        try:
            self.rows.insert(row, bst)
            self.segments.insert(row, StreckenSegment(bst))
            result = True
        except IndexError:
            result = False
        else:
            self._update()
            
        self.endInsertRows()
        return result

    def remove(self, bst: BahnhofElement):
        """
        Station entfernen

        Args:
            bst: Zu entfernendes BahnhofElement.

        Returns:
            True bei Erfolg, False bei falschem Index.
        """

        try:
            row = self.rows.index(bst)
        except ValueError:
            return False

        self.beginRemoveRows(QModelIndex(), row, row)
        try:
            del self.rows[row]
            del self.segments[row]
            result = True
        except IndexError:
            result = False
        else:
            self._update()

        self.endRemoveRows()
        return result

    def move(self, row: int, bst: BahnhofElement) -> bool:
        """
        Station verschieben

        Args:
            row: Zielindex.
                Bezieht sich auf die ursprüngliche Liste!
                Ist also ev. grösser als der Index in der Ergebnisliste.
            bst: Zu verschiebendes BahnhofElement.

        Returns:
            True bei Erfolg, False bei falschem Index.
        """

        try:
            old_row = self.rows.index(bst)
        except ValueError:
            return False

        self.beginMoveRows(QModelIndex(), old_row, old_row, QModelIndex(), row)
        try:
            del self.rows[old_row]
            del self.segments[old_row]
            if old_row <= row:
                row -= 1
            self.rows.insert(row, bst)
            self.segments.insert(row, StreckenSegment(bst))
            result = True
        except IndexError:
            result = False
        else:
            self._update()

        self.endMoveRows()
        return result

    def supportedDragActions(self, /):
        return QtCore.Qt.MoveAction

    def supportedDropActions(self, /):
        return QtCore.Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-bahnhofelement"]

    def mimeData(self, items):
        src_rows = [index.row() for index in items]
        bst_list = [self.rows[row] for row in src_rows]
        drag_id = id(bst_list)
        dada = {"drag_id": drag_id, "sender": id(self), "bst_list": bst_list}
        self._drag_data[drag_id] = dada
        data = QMimeData()
        data.setData("application/x-bahnhofelement", pickle.dumps(dada))
        return data

    def dropMimeData(self, data, action, row, column, parent, /):
        """
        Verarbeitet einen Drop von Bst

        Args:
            data (QDropEvent): The event containing the dropped data.
            action (int): The action to be performed with the dropped data, e.g., Qt.MoveAction or Qt.CopyAction.
            row (int): The row where the data should be inserted.
            column (int): The column where the data should be inserted.
            parent (QModelIndex): The parent index of the item being dropped.

        Returns:
            True if the data was successfully dropped, False otherwise.

        """

        try:
            dada = pickle.loads(data.data("application/x-bahnhofelement"))
        except pickle.PickleError:
            return False

        if parent.isValid():
            row = parent.row()
        
        try:
            if dada["sender"] == id(self):
                for bst in reversed(dada["bst_list"]):
                    self.move(row, bst)
            else:
                for bst in reversed(dada["bst_list"]):
                    self.insert(row, bst)
        except KeyError:
            return False

        self.drop_completed.emit(str(dada.get("drag_id", 0)))
        return True

    def on_drop_completed(self, drag_id):
        """
        Schliesst einen Drag-Event ab.

        This method processes a completed drop event by parsing the provided data,
        creating `BahnhofElement` instances, and removing them from the current context.

        Args:
            drag_id: key of the drop envent to look up in self._drag_data.
        """

        drag_id = int(drag_id)
        try:
            dada = self._drag_data[drag_id]
        except (KeyError, ValueError):
            return

        if dada["sender"] == id(self):
            for bst in dada["bst_list"]:
                self.remove(bst)

        del self._drag_data[drag_id]


class StreckenEditor(QObject):
    def __init__(self, anlage: Anlage, parent: QObject, ui: Ui_EinstellungenWindow):
        super().__init__()
        self.anlage = anlage
        self.bahnhofgraph = anlage.bahnhofgraph.copy(as_view=False)
        self.changes: JournalEntry = JournalEntry()
        self.parent = parent
        self.ui = ui
        self.in_update = True

        self.anlage_bst: List[BahnhofElement] = []
        self.anlage_strecken: Dict[str, List[BahnhofElement]] = {}
        self.alle_strecken: Dict[str, List[BahnhofElement]] = {}
        self.auto_strecken: Set[str] = set()
        self.edited_strecken: Set[str] = set()
        self.deleted_strecken: Set[str] = set()
        self.strecken_liste: List[str] = []
        self.strecken_name: str = ""
        self.hauptstrecken_name: Optional[str] = None
        
        self.auswahl_model = StreckenEditorModel(anlage, True, False, parent)
        self.ui.strecken_auswahl_list.setModel(self.auswahl_model)
        self.ui.strecken_auswahl_list.setItemDelegate(StreckenItemDelegate(parent=self.ui.strecken_auswahl_list))
        self.ui.strecken_auswahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.strecken_auswahl_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        #self.ui.strecken_auswahl_list.selectionModel().selectionChanged.connect(
        #    self.zugliste_selection_changed)
        self.ui.strecken_auswahl_list.setAcceptDrops(True)

        self.abwahl_model = StreckenEditorModel(anlage, False, True, parent)
        self.ui.strecken_abwahl_list.setModel(self.abwahl_model)
        self.ui.strecken_abwahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.strecken_abwahl_list.setAcceptDrops(True)

        self.strecken_model = StreckenListModel(anlage, parent)
        self.ui.strecken_liste.setModel(self.strecken_model)
        self.ui.strecken_liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.strecken_liste.setItemDelegate(StyledTextDelegate(parent=self.ui.strecken_liste))
        self.strecken_model.dataChanged.connect(self.strecken_model_data_changed)

        self.ui.strecken_auswahl_button.clicked.connect(self.strecken_auswahl_button_clicked)
        self.ui.strecken_abwahl_button.clicked.connect(self.strecken_abwahl_button_clicked)
        self.ui.strecken_hoch_button.clicked.connect(self.strecken_hoch_button_clicked)
        self.ui.strecken_runter_button.clicked.connect(self.strecken_runter_button_clicked)
        self.ui.strecken_ordnen_button.clicked.connect(self.strecken_ordnen_button_clicked)
        self.ui.strecken_erstellen_button.clicked.connect(self.strecken_erstellen_button_clicked)
        self.ui.strecken_umbenennen_button.clicked.connect(self.strecken_umbenennen_button_clicked)
        self.ui.strecken_loeschen_button.clicked.connect(self.strecken_loeschen_button_clicked)
        self.ui.strecken_interpolieren_button.clicked.connect(self.strecken_interpolieren_button_clicked)

        self.ui.strecken_liste.selectionModel().selectionChanged.connect(self.streckenliste_auswahl_changed)
        self.ui.strecken_auswahl_list.selectionModel().selectionChanged.connect(self.update_widget_states)
        self.ui.strecken_abwahl_list.selectionModel().selectionChanged.connect(self.update_widget_states)
        self.ui.strecken_name_edit.textChanged.connect(self.strecken_name_edit_changed)
        self.ui.strecken_name_edit.returnPressed.connect(self.strecken_umbenennen_button_clicked)

        self.auswahl_model.rowsInserted.connect(self.auswahl_rows_inserted)
        self.auswahl_model.rowsMoved.connect(self.auswahl_rows_moved)
        self.auswahl_model.rowsRemoved.connect(self.auswahl_rows_removed)
        self.auswahl_model.dataChanged.connect(self.auswahl_data_changed)
        self.auswahl_model.drop_completed.connect(self.abwahl_model.on_drop_completed)
        self.abwahl_model.drop_completed.connect(self.auswahl_model.on_drop_completed)

        self.in_update = False
        self.init_from_anlage()
        self.strecken_name = self._default_strecke()
        self._streckenliste_changed()
        self._strecke_changed()

    def apply(self):
        """
        Apply changes to the anlage based on the current state of the widgets
        
        Called by owner when the user clicks the Apply or OK button.
        """

        self.save_to_anlage()

    def reset(self):
        """
        Reset all widgets to Anlage
        
        Called by owner when the user clicks the Reset button.
        """

        self.init_from_anlage()
        if self.strecken_name not in self.alle_strecken:
            self.strecken_name = self._default_strecke()
        self._streckenliste_changed()
        self._strecke_changed()
        self.auswahl_model.journal.clear()

    def update_widgets(self):
        """
        Update changes of Anlage.

        Called by owner after changes to the anlage.
        Update anlage_bst and validate alle_strecken.
        """

        self.anlage_bst = sorted(self.anlage.bahnhofgraph.list_by_type({'Bf', 'Anst'}))

        neue_strecken = {}
        changed = False
        for name, strecke in self.alle_strecken.items():
            neue_strecke = [station for station in strecke if station in self.anlage_bst]
            neue_strecken[name] = neue_strecke
            if neue_strecke != strecke:
                changed = True

        if changed:
            self.alle_strecken = neue_strecken
            self._strecke_changed()
            self.adjust_geometry()

    def update_widget_states(self):
        en = len(self.ui.strecken_abwahl_list.selectedIndexes()) >= 1
        self.ui.strecken_auswahl_button.setEnabled(en)
        en = len(self.ui.strecken_auswahl_list.selectedIndexes()) >= 1
        self.ui.strecken_abwahl_button.setEnabled(en)
        self.ui.strecken_hoch_button.setEnabled(en)
        self.ui.strecken_runter_button.setEnabled(en)

        self.ui.strecken_erstellen_button.setEnabled(True)
        strecken_auswahl = self.ui.strecken_liste.selectedIndexes()
        strecken_edit = self.ui.strecken_name_edit.text()
        en = len(strecken_auswahl) >= 1
        self.ui.strecken_loeschen_button.setEnabled(en)
        en = len(strecken_auswahl) == 1 and len(strecken_edit) >= 1 and strecken_edit not in self.alle_strecken
        self.ui.strecken_umbenennen_button.setEnabled(en)

        en = bool(self.strecken_name) and len(self.auswahl_model.rows) >= 2
        self.ui.strecken_interpolieren_button.setEnabled(en)
        self.ui.strecken_ordnen_button.setEnabled(en)

    def adjust_geometry(self):
        """
        Adjust the geometry of the widgets based on their current content.
        """

        self.ui.strecken_auswahl_list.resizeColumnsToContents()
        self.ui.strecken_auswahl_list.resizeRowsToContents()
        self.ui.strecken_abwahl_list.resizeColumnsToContents()
        self.ui.strecken_abwahl_list.resizeRowsToContents()

    def init_from_anlage(self):
        """
        Streckendefinition von Anlage initialisieren

        Alle Änderungen werden gelöscht!
        Aktualisiert nur die eigenen Attribute, nicht die Views!
        Wählt auch eine Strecke aus.
        """

        self.anlage_bst = sorted(self.anlage.bahnhofgraph.list_by_type({'Bf', 'Anst'}))
        self.anlage_strecken = {k: self.anlage.strecken.strecken[k] for k in self.anlage.strecken.strecken}
        self.auto_strecken = {k for k in self.anlage.strecken.strecken if self.anlage.strecken.auto.get(k, False)}
        self.alle_strecken = self.anlage_strecken.copy()
        self.hauptstrecken_name = self.anlage.strecken.hauptstrecke
        self.edited_strecken = set()
        self.deleted_strecken = set()

    def _default_strecke(self) -> Optional[str]:
        if self.hauptstrecken_name in self.alle_strecken:
            return self.hauptstrecken_name
        try:
            return list(self.alle_strecken)[0]
        except IndexError:
            return None

    def save_to_anlage(self):
        auto_idx_0 = max(len(self.alle_strecken) + 1, 100)
        for idx, name in enumerate(self.alle_strecken):
            ordnung = idx + 1 if name not in self.auto_strecken else auto_idx_0 + idx
            if name in self.edited_strecken:
                self.anlage.strecken.add_strecke(name, self.alle_strecken[name], ordnung, auto=False)
                self.auto_strecken.discard(name)
            elif name in self.anlage.strecken.ordnung:
                self.anlage.strecken.ordnung[name] = ordnung
        self.anlage.strecken.hauptstrecke = self.hauptstrecken_name
        for name in self.deleted_strecken:
            self.anlage.strecken.remove_strecke(name)
            self.auto_strecken.discard(name)

        self.edited_strecken = set()
        self.deleted_strecken = set()

        self.auswahl_model.journal.replay({"liniengraph": self.anlage.liniengraph})
        self.auswahl_model.journal.clear()

    def _streckenliste_changed(self):
        """
        Streckenlisten-Modell aktualisieren
        """

        def strecken_key(name: str) -> Any:
            return name in self.auto_strecken, name

        self.strecken_liste = sorted((name for name, strecke in self.alle_strecken.items()), key=strecken_key)
        self.strecken_model.update(self.strecken_liste, auto=self.auto_strecken, edited=self.edited_strecken,
                                   checked={self.hauptstrecken_name})

        try:
            index = self.strecken_model.index(self.strecken_liste.index(self.strecken_name))
        except ValueError:
            pass
        else:
            self.ui.strecken_liste.setCurrentIndex(index)
        self.update_widget_states()

    def select_strecke(self, name: str):
        """
        Strecke auswählen und Stationslisten aktualisieren

        Wählt eine Strecke im UI und Modell aus.
        Die Modelle der Stationslisten werden aus alle_strecken aktualisiert (überschrieben!).
        Die Stationslisten werden in jedem Fall neu aufgebaut, auch wenn der Name der Strecke sich nicht ändert.

        Args:
            name: Name der Strecke. Muss existieren, sonst schlägt die Methode fehl.

        Returns:
            True, wenn der Vorgang erfolgreich war.
        """

        if name not in self.alle_strecken:
            return False

        try:
            index = self.strecken_model.index(self.strecken_liste.index(self.strecken_name))
        except ValueError:
            return False

        # dies triggert die aktualisierung
        self.ui.strecken_liste.setCurrentIndex(index)
        return True

    def _strecke_changed(self):
        """
        Stationslisten gem. gewählter Strecke aktualisieren

        Die Modelle der Stationslisten werden aus alle_strecken aktualisiert (überschrieben!).
        Die gewählte Strecke steht in `self.strecken_name`.
        """

        self.in_update = True
        stationen = self.alle_strecken.get(self.strecken_name, [])
        self.auswahl_model.update(stationen)
        uebrige = [bst for bst in self.anlage_bst if bst not in stationen]
        self.abwahl_model.update(uebrige)
        self.in_update = False
        self.adjust_geometry()
        self.update_widget_states()

    def _strecke_edited(self):
        """
        Geänderte Strecke vom List-Modell übernehmen

        Aktualisiert alle_strecken,
        fügt die Strecke zu edited_strecken hinzu und
        entfernt sie aus deleted_strecken.
        """

        self.alle_strecken[self.strecken_name] = list(self.auswahl_model.rows)
        self.edited_strecken.add(self.strecken_name)
        self.auto_strecken.discard(self.strecken_name)
        self.deleted_strecken.discard(self.strecken_name)
        self.strecken_model.set_edited(self.strecken_name, True)
        self.adjust_geometry()
        self.update_widget_states()

    @Slot()
    def streckenliste_auswahl_changed(self):
        if self.in_update:
            return

        indexes = self.ui.strecken_liste.selectedIndexes()
        if len(indexes) == 1:
            name = self.strecken_model.data(indexes[0])
        else:
            name = ""

        if name != self.strecken_name:
            self.strecken_name = name
            self._strecke_changed()
            self.ui.strecken_name_edit.setText(self.strecken_name)

    @Slot()
    def strecken_auswahl_button_clicked(self):
        # todo : selection in auswahlview behalten
        try:
            src_indexes = self.ui.strecken_abwahl_list.selectedIndexes()
            src_rows = [index.row() for index in src_indexes]
            move_items = [self.abwahl_model.rows[row] for row in src_rows]
        except IndexError:
            return
        try:
            dst_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            index = dst_indexes[0].row()
        except IndexError:
            index = self.auswahl_model.rowCount()

        for bst in reversed(move_items):
            self.abwahl_model.remove(bst)
            self.auswahl_model.insert(index, bst)

        self.ui.strecken_auswahl_list.clearSelection()
        self.ui.strecken_abwahl_list.clearSelection()

    @Slot()
    def strecken_abwahl_button_clicked(self):
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            src_rows = [index.row() for index in src_indexes]
            move_items = [self.auswahl_model.rows[row] for row in src_rows]
        except IndexError:
            return

        for bst in move_items:
            self.auswahl_model.remove(bst)
            if self.bahnhofgraph.has_node(bst):
                self.abwahl_model.insert(0, bst)

        self.ui.strecken_auswahl_list.clearSelection()
        self.ui.strecken_abwahl_list.clearSelection()

    @Slot()
    def strecken_hoch_button_clicked(self):
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            src_rows = sorted((index.row() for index in src_indexes))
            move_items = [self.auswahl_model.rows[row] for row in src_rows]
            dst_row = min(src_rows) - 1
            if dst_row < 0:
                return
        except (IndexError, ValueError):
            return
        for bst in move_items:
            self.auswahl_model.move(dst_row, bst)
            dst_row += 1

    @Slot()
    def strecken_runter_button_clicked(self):
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            src_rows = sorted((index.row() for index in src_indexes), reverse=True)
            move_items = [self.auswahl_model.rows[row] for row in src_rows]
            dst_row = max(src_rows) + 2
            if dst_row > self.auswahl_model.rowCount():
                return
        except (IndexError, ValueError):
            return
        for bst in move_items:
            self.auswahl_model.move(dst_row, bst)
            dst_row -= 1

    @Slot()
    def strecken_loeschen_button_clicked(self):
        indexes = self.ui.strecken_liste.selectedIndexes()
        for index in indexes:
            name = self.strecken_model.data(index)
            try:
                del self.alle_strecken[name]
            except KeyError:
                pass
            self.edited_strecken.discard(name)
            self.deleted_strecken.add(name)
        self._streckenliste_changed()

    @Slot()
    def strecken_erstellen_button_clicked(self):
        basis = name = self.ui.strecken_name_edit.text() or "Strecke"
        i = 1
        while name in self.alle_strecken:
            i += 1
            name = f"{basis} {str(i)}"

        self.alle_strecken[name] = []
        self.edited_strecken.add(name)
        self.strecken_name = name
        self._streckenliste_changed()
        self._strecke_changed()

    @Slot()
    def strecken_umbenennen_button_clicked(self):
        if self.in_update:
            return
        if not self.strecken_name:
            self.strecken_erstellen_button_clicked()
            return

        old_name = self.strecken_name
        new_name = self.ui.strecken_name_edit.text()
        if new_name != old_name:
            self.alle_strecken[new_name] = self.alle_strecken[old_name]
            try:
                del self.alle_strecken[old_name]
            except KeyError:
                pass
            self.edited_strecken.discard(old_name)
            self.auto_strecken.discard(new_name)
            self.deleted_strecken.discard(new_name)
            self.deleted_strecken.add(old_name)
            self.edited_strecken.add(new_name)
            self.strecken_name = new_name
            if self.hauptstrecken_name == old_name:
                self.hauptstrecken_name = new_name
            self._streckenliste_changed()
            self._strecke_changed()

    @Slot()
    def strecken_model_data_changed(self):
        for name in self.alle_strecken:
            if self.strecken_model.get_checked(name):
                self.hauptstrecken_name = name
                break
        else:
            self.hauptstrecken_name = None

    def get_hauptstrecke(self) -> Optional[str]:
        for name in self.alle_strecken:
            if self.strecken_model.get_checked(name):
                return name
        return None

    @Slot()
    def strecken_name_edit_changed(self):
        self.update_widget_states()

    @Slot()
    def strecken_auto_loeschen_button_clicked(self):
        namen = list(self.alle_strecken.keys())
        changed = False
        for name in namen:
            if name in self.auto_strecken:
                del self.alle_strecken[name]
                self.edited_strecken.discard(name)
                self.deleted_strecken.add(name)
                changed = True

        if changed:
            self._streckenliste_changed()
            if self.strecken_name in self.deleted_strecken:
                self.strecken_name = ""
            self._strecke_changed()

    @Slot()
    def strecken_interpolieren_button_clicked(self):
        if not self.strecken_name:
            return
        try:
            start = self.auswahl_model.rows[0]
        except IndexError:
            return
        try:
            ziel = self.auswahl_model.rows[-1]
        except IndexError:
            return

        start_anlage = self.anlage.bahnhofgraph.map_from_other_graph(start, self.bahnhofgraph)
        ziel_anlage =  self.anlage.bahnhofgraph.map_from_other_graph(ziel, self.bahnhofgraph)
        strecke_anlage = self.anlage.liniengraph.strecke(start_anlage, ziel_anlage)
        strecke = [self.bahnhofgraph.map_from_other_graph(bst, self.anlage.bahnhofgraph) for bst in strecke_anlage]
        strecke = [bst for bst in strecke if bst is not None]

        if strecke:
            self.alle_strecken[self.strecken_name] = strecke
            self.edited_strecken.add(self.strecken_name)
            self.deleted_strecken.discard(self.strecken_name)
            self._strecke_changed()

    @Slot()
    def strecken_ordnen_button_clicked(self):
        def _bst_to_signal(bst: BahnhofElement):
            for gl in self.anlage.bahnhofgraph.list_children(bst, {"Gl", "Agl"}):
                gl_node = self.anlage.bahnhofgraph.nodes[gl]
                break
            else:
                return None

            if gl_node.typ == "Agl":
                return gl_node.enr
            elif gl_node.typ == "Gl":
                return gl_node.name
            else:
                return None

        try:
            start = self.auswahl_model.rows[0]
        except IndexError:
            return
        try:
            signal_start = _bst_to_signal(start)
        except KeyError:
            return
        if signal_start is None:
            return

        distanzen = {}
        for i, station in enumerate(self.auswahl_model.rows):
            signal_ziel = _bst_to_signal(station)
            if station == start:
                distanzen[station] = 0
            elif signal_ziel is not None:
                try:
                    pfad = nx.shortest_path(self.anlage.signalgraph, signal_start, signal_ziel)
                except (KeyError, nx.exception.NetworkXError, nx.exception.NodeNotFound):
                    d = i
                else:
                    d = len(pfad)
                distanzen[station] = d
            else:
                distanzen[station] = i

        self.alle_strecken[self.strecken_name] = sorted(distanzen.keys(), key=lambda _item: distanzen[_item])
        self.edited_strecken.add(self.strecken_name)
        self._strecke_changed()

    @Slot()
    def auswahl_rows_inserted(self):
        self._strecke_edited()

    @Slot()
    def auswahl_rows_moved(self):
        self._strecke_edited()

    @Slot()
    def auswahl_rows_removed(self):
        self._strecke_edited()

    @Slot()
    def auswahl_data_changed(self):
        self._strecke_edited()
