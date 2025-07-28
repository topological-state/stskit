import bisect
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot, QAbstractListModel, QModelIndex, QItemSelectionModel, QStringListModel, QObject, \
    QMimeData, QByteArray
from PySide6.QtWidgets import QWidget, QAbstractItemView

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BAHNHOFELEMENT_BESCHREIBUNG
from stskit.model.journal import GraphJournal
from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class StreckenEditorModel(QAbstractListModel):
    """
    ListModel für den Streckeneditor

    Attribute
    =========

    - anlage : Anlage
      The Anlage object containing the BahnhofElements.
    - rows : list of BahnhofElement
      List of BahnhofElements sorted by some criterion (not specified in the code).
    """

    def __init__(self, anlage: Anlage, parent=None):
        super().__init__(parent)

        self.anlage: Anlage = anlage
        self.columns: List[str] = ["Stationen"]
        self.rows: List[BahnhofElement] = []

    def update(self, strecke: Sequence[BahnhofElement]) -> None:
        self.beginResetModel()
        self.rows = list(strecke)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.rows)

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
        key = self.rows[row]

        if role == QtCore.Qt.UserRole:
            try:
                return key
            except KeyError:
                return None

        elif role == QtCore.Qt.DisplayRole:
            try:
                return str(key)
            except KeyError:
                return '???'

        elif role == QtCore.Qt.ToolTipRole:
            try:
                return f"{BAHNHOFELEMENT_BESCHREIBUNG[key.typ]} {key.name}"
            except KeyError:
                return '???'

        elif role == QtCore.Qt.WhatsThisRole:
            try:
                return f"{BAHNHOFELEMENT_BESCHREIBUNG[key.typ]} {key.name}"
            except KeyError:
                return '???'

        elif role == QtCore.Qt.EditRole:
            try:
                return str(key)
            except KeyError:
                return '???'

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        result = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled

        return result

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        # for editable models
        return False

    def insert(self, row: int, bst: BahnhofElement):
        """
        Station einfügen

        :param row: Zielindex
        :param bst: Einzufügendes BahnhofElement.
        :return: True bei Erfolg, False bei Indexfehler.
        """

        self.beginInsertRows(QModelIndex(), row, 1)
        try:
            self.rows.insert(row, bst)
            result = True
        except IndexError:
            result = False
        self.endInsertRows()
        return result

    def remove(self, bst: BahnhofElement):
        """
        Station entfernen

        :param bst: Zu entfernendes BahnhofElement.
        :return: True bei Erfolg, False bei Indexfehler.
        """

        try:
            row = self.rows.index(bst)
        except ValueError:
            return False

        self.beginRemoveRows(QModelIndex(), row, 1)
        try:
            del self.rows[row]
            result = True
        except IndexError:
            result = False
        self.endRemoveRows()
        return result

    def move(self, row: int, bst: BahnhofElement) -> bool:
        """
        Station verschieben

        :param row: Zielindex.
            Bezieht sich auf die ursprüngliche Liste!
            Ist also ev. grösser als der Index in der Ergebnisliste.
        :param bst: Zu verschiebendes BahnhofElement.
        :return: True bei Erfolg, False bei Indexfehler.
        """

        try:
            old_row = self.rows.index(bst)
        except ValueError:
            return False

        self.beginMoveRows(QModelIndex(), old_row, old_row, QModelIndex(), row)
        try:
            del self.rows[old_row]
            if old_row <= row:
                row -= 1
            self.rows.insert(row, bst)
            result = True
        except IndexError:
            result = False

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
        move_items = [str(self.rows[row]) for row in src_rows]
        move_str = ";".join(move_items)
        dada = QByteArray.fromStdString(move_str)
        data = QMimeData()
        data.setData("application/x-bahnhofelement", dada)
        return data

    def dropMimeData(self, data, action, row, column, parent, /):
        dada = data.data("application/x-bahnhofelement").toStdString()
        print("--- dropMimeData", dada)
        return True


class StreckenEditor(QObject):
    def __init__(self, anlage: Anlage, parent: QObject, ui: Ui_EinstellungenWindow):
        super().__init__()
        self.anlage = anlage
        self.bahnhofgraph = anlage.bahnhofgraph.copy(as_view=False)
        self.changes: GraphJournal = GraphJournal()
        self.parent = parent
        self.ui = ui
        self.in_update = True

        self.anlage_bst: List[BahnhofElement] = []
        self.anlage_strecken: Dict[str, List[BahnhofElement]] = {}
        self.alle_strecken: Dict[str, List[BahnhofElement]] = {}
        self.auto_strecken: Set[str] = set()
        self.edited_strecken: Set[str] = set()
        self.deleted_strecken: Set[str] = set()
        self.strecken_name: str = ""
        
        self.auswahl_model = StreckenEditorModel(anlage, parent)
        self.ui.strecken_auswahl_list.setModel(self.auswahl_model)
        self.ui.strecken_auswahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.abwahl_model = StreckenEditorModel(anlage, parent)
        self.ui.strecken_abwahl_list.setModel(self.abwahl_model)
        self.ui.strecken_abwahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.strecken_model = QStringListModel()
        self.ui.strecken_name_combo.setModel(self.strecken_model)

        self.ui.strecken_auswahl_button.clicked.connect(self.strecken_auswahl_button_clicked)
        self.ui.strecken_abwahl_button.clicked.connect(self.strecken_abwahl_button_clicked)
        self.ui.strecken_hoch_button.clicked.connect(self.strecken_hoch_button_clicked)
        self.ui.strecken_runter_button.clicked.connect(self.strecken_runter_button_clicked)
        self.ui.strecken_ordnen_button.clicked.connect(self.strecken_ordnen_button_clicked)
        self.ui.strecken_erstellen_button.clicked.connect(self.strecken_erstellen_button_clicked)
        self.ui.strecken_loeschen_button.clicked.connect(self.strecken_loeschen_button_clicked)

        self.ui.strecken_name_combo.currentIndexChanged.connect(self.strecken_name_combo_index_changed)
        self.ui.strecken_name_combo.editTextChanged.connect(self.strecken_name_combo_text_changed)

        # self.auswahl_model.rowsInserted.connect(self.auswahl_rows_inserted)
        # self.abwahl_model.rowsInserted.connect(self.abwahl_rows_inserted)
        # self.auswahl_model.rowsMoved.connect(self.auswahl_rows_moved)
        # self.abwahl_model.rowsMoved.connect(self.abwahl_rows_moved)
        # self.auswahl_model.rowsRemoved.connect(self.auswahl_rows_removed)
        # self.abwahl_model.rowsRemoved.connect(self.abwahl_rows_removed)
        # self.auswahl_model.dataChanged.connect(self.auswahl_data_changed)
        # self.abwahl_model.dataChanged.connect(self.abwahl_data_changed)

        self.init_from_anlage()
        self.update_widgets()
        try:
            self.strecken_name = list(self.alle_strecken)[0]
            self.select_strecke(self.strecken_name)
            self.ui.strecken_name_combo.setCurrentIndex(0)
        except IndexError:
            pass

    def init_from_anlage(self):
        """
        Streckendefinition von Anlage initialisieren

        Alle Änderungen werden gelöscht!
        """

        self.anlage_strecken = {k: self.anlage.strecken.strecken[k] for k in self.anlage.strecken.strecken}
        self.auto_strecken = {k for k in self.anlage.strecken.strecken if self.anlage.strecken.auto.get(k, True)}
        self.alle_strecken = self.anlage_strecken.copy()
        self.edited_strecken = set()
        self.deleted_strecken = set()
        self.anlage_bst = sorted(self.anlage.bahnhofgraph.list_by_type({'Bf', 'Anst'}))

    def save_to_anlage(self):
        self.auto_strecken = self.auto_strecken - self.edited_strecken - self.deleted_strecken
        for idx, strecke in enumerate(self.alle_strecken.items()):
            name, stationen = strecke
            if name not in self.auto_strecken:
                if name not in self.deleted_strecken and len(stationen) >= 2:
                    self.anlage.strecken.add_strecke(name, stationen, idx + 1, False)
                else:
                    self.anlage.strecken.remove_strecke(name)

        self.edited_strecken = set()
        self.deleted_strecken = set()

    def update_widgets(self):
        """
        Update the widgets based on the current state of the anlage
        """

        def strecken_key(name: str) -> Any:
            return name in self.auto_strecken, name

        #self.in_update = True
        strecken_liste = sorted((name for name, strecke in self.alle_strecken.items()), key=strecken_key)
        self.strecken_model.setStringList(strecken_liste)
        #self.in_update = False

        try:
            index = strecken_liste.index(self.strecken_name)
        except ValueError:
            pass
        else:
            self.ui.strecken_name_combo.setCurrentIndex(index)

    def apply(self):
        """
        Apply changes to the anlage based on the current state of the widgets
        """

        self.save_to_anlage()

    def reset(self):
        """
        Reset all widgets to Anlage
        """

        self.init_from_anlage()
        self.update_widgets()

    def select_strecke(self, name: str):
        """
        Strecke auswählen und Stationslisten aktualisieren

        :param name: Name der Strecke.

        :return True, wenn der Vorgang erfolgreich war.
        """

        self.in_update = True
        self.strecken_name = name
        stationen = self.alle_strecken.get(name, [])
        self.auswahl_model.update(stationen)
        uebrige = [bst for bst in self.anlage_bst if bst not in stationen]
        self.abwahl_model.update(uebrige)
        self.in_update = False

    def change_strecke(self, name: str, stationen: Sequence[BahnhofElement]):
        self.alle_strecken[name] = list(self.auswahl_model.rows)
        self.edited_strecken.add(name)

    @Slot()
    def strecken_name_combo_index_changed(self):
        print(f"strecken_name_combo_index_changed: {self.strecken_name}, {self.in_update}")
        if self.in_update:
            return

        idx = self.ui.strecken_name_combo.currentIndex()
        index = self.strecken_model.index(idx)
        if index.isValid():
            strecken_name = self.strecken_model.data(index)
            if strecken_name != self.strecken_name:
                self.strecken_name = strecken_name
                self.select_strecke(self.strecken_name)

    @Slot()
    def strecken_name_combo_text_changed(self):
        print(f"strecken_name_combo_text_changed: {self.strecken_name}, {self.in_update}")
        if self.in_update:
            return

        idx = self.ui.strecken_name_combo.currentIndex()
        index = self.strecken_model.index(idx)
        if index.isValid():
            index_name = self.strecken_model.data(index)
            new_name = self.ui.strecken_name_combo.currentText()
            if new_name != index_name:
                self.alle_strecken[new_name] = self.alle_strecken[index_name]
                try:
                    del self.alle_strecken[index_name]
                except KeyError:
                    pass
                self.edited_strecken.discard(index_name)
                self.auto_strecken.discard(index_name)
                self.edited_strecken.add(new_name)
                self.strecken_model.setData(index, new_name)
                self.strecken_name = new_name

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

        self.edited_strecken.add(self.strecken_name)
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
            index = bisect.bisect_left(self.abwahl_model.rows, bst)
            self.abwahl_model.insert(index, bst)

        self.edited_strecken.add(self.strecken_name)
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

        self.edited_strecken.add(self.strecken_name)

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

        self.edited_strecken.add(self.strecken_name)

    @Slot()
    def strecken_loeschen_button_clicked(self):
        del self.alle_strecken[self.strecken_name]
        self.deleted_strecken.add(self.strecken_name)
        self.update_widgets()

    @Slot()
    def strecken_erstellen_button_clicked(self):
        name = "Unbenannt"
        i = 1
        while name in self.alle_strecken:
            i += 1
            name = "Unbenannt " + str(i)

        self.alle_strecken[name] = []
        self.edited_strecken.add(self.strecken_name)
        self.select_strecke(name)
        self.update_widgets()

    @Slot()
    def strecken_ordnen_button_clicked(self):
        def _bst_to_signal(bst: BahnhofElement):
            for gl in self.anlage.bahnhofgraph.list_children(bst, {"Gl", "Agl"}):
                gl_node = self.anlage.bahnhofgraph.nodes[gl]
                break
            else:
                return None

            if bst.typ == "Anst":
                return gl_node.enr
            elif bst.typ == "Gl":
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

        distanzen = {}
        d = 0.
        for station in self.auswahl_model.rows:
            signal_ziel = _bst_to_signal(station)
            if station == start:
                distanzen[station] = 0.
            else:
                try:
                    pfad = nx.shortest_path(self.anlage.signalgraph, signal_start, signal_ziel)
                except (KeyError, nx.exception.NetworkXError):
                    d += 0.001
                else:
                    d = len(pfad) + 0.
                distanzen[station] = d

        self.alle_strecken[self.strecken_name] = sorted(distanzen.keys(), key=lambda _item: distanzen[_item])
        self.edited_strecken.add(self.strecken_name)
        self.select_strecke(self.strecken_name)

    @Slot()
    def auswahl_rows_inserted(self):
        print("auswahl_rows_inserted")

    @Slot()
    def abwahl_rows_inserted(self):
        print("abwahl_rows_inserted")

    @Slot()
    def auswahl_rows_moved(self):
        print("auswahl_rows_moved")

    @Slot()
    def abwahl_rows_moved(self):
        print("abwahl_rows_moved")

    @Slot()
    def auswahl_rows_removed(self):
        print("auswahl_rows_removed")

    @Slot()
    def abwahl_rows_removed(self):
        print("abwahl_rows_removed")

    @Slot()
    def auswahl_data_changed(self):
        print("auswahl_data_changed")

    @Slot()
    def abwahl_data_changed(self):
        print("abwahl_data_changed")

