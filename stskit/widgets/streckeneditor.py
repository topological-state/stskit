import bisect
import logging
import pickle
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import (Slot, Signal, QAbstractListModel, QModelIndex, QItemSelectionModel,
                            QStringListModel, QObject, QMimeData, QByteArray)
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

    drop_completed = Signal(str)

    def __init__(self, anlage: Anlage, parent=None):
        super().__init__(parent)
        self.anlage: Anlage = anlage
        self.columns: List[str] = ["Stationen"]
        self.rows: List[BahnhofElement] = []
        self.sorted = False
        self._drag_data = {}

    def update(self, strecke: Sequence[BahnhofElement]) -> None:
        self.beginResetModel()
        if self.sorted:
            strecke = sorted(strecke)
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
            Wenn die Liste sortiert ist, hat row keinen Einfluss.
        :param bst: Einzufügendes BahnhofElement.
        :return: True bei Erfolg, False bei Indexfehler.
        """

        if self.sorted:
            row = bisect.bisect_left(self.rows, bst)

        self.beginInsertRows(QModelIndex(), row, row)
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

        self.beginRemoveRows(QModelIndex(), row, row)
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

        Parameters:
        data (QDropEvent): The event containing the dropped data.
        action (int): The action to be performed with the dropped data, e.g., Qt.MoveAction or Qt.CopyAction.
        row (int): The row where the data should be inserted.
        column (int): The column where the data should be inserted.
        parent (QModelIndex): The parent index of the item being dropped.

        Returns:
        bool: True if the data was successfully dropped, False otherwise.

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

        Summary
        -------
        This method processes a completed drop event by parsing the provided data,
        creating `BahnhofElement` instances, and removing them from the current context.

        Parameters
        ----------
        dada (Dict) : The data received from the drop event.
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
        self.changes: GraphJournal = GraphJournal()
        self.parent = parent
        self.ui = ui
        self.in_update = True

        self.anlage_bst: List[BahnhofElement] = []
        self.anlage_strecken: Dict[str, List[BahnhofElement]] = {}
        self.alle_strecken: Dict[str, List[BahnhofElement]] = {}
        self.ordnung: Dict[str, Union[int, float]] = {}
        self.auto_strecken: Set[str] = set()
        self.edited_strecken: Set[str] = set()
        self.deleted_strecken: Set[str] = set()
        self.strecken_name: str = ""
        
        self.auswahl_model = StreckenEditorModel(anlage, parent)
        self.ui.strecken_auswahl_list.setModel(self.auswahl_model)
        self.ui.strecken_auswahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.strecken_auswahl_list.setAcceptDrops(True)
        self.abwahl_model = StreckenEditorModel(anlage, parent)
        self.abwahl_model.sorted = True
        self.ui.strecken_abwahl_list.setModel(self.abwahl_model)
        self.ui.strecken_abwahl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.strecken_abwahl_list.setAcceptDrops(True)
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

        self.auswahl_model.rowsInserted.connect(self.auswahl_rows_inserted)
        self.auswahl_model.rowsMoved.connect(self.auswahl_rows_moved)
        self.auswahl_model.rowsRemoved.connect(self.auswahl_rows_removed)
        self.auswahl_model.dataChanged.connect(self.auswahl_data_changed)

        self.auswahl_model.drop_completed.connect(self.abwahl_model.on_drop_completed)
        self.abwahl_model.drop_completed.connect(self.auswahl_model.on_drop_completed)

        self.init_from_anlage()
        self._streckenliste_changed()
        self._select_strecke(self.strecken_name)

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
        self._streckenliste_changed()

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
            self._select_strecke(self.strecken_name)

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
        self.ordnung = self.anlage.strecken.ordnung.copy()
        self.edited_strecken = set()
        self.deleted_strecken = set()

        try:
            self.strecken_name = min(self.ordnung, key=self.ordnung.get)
        except ValueError:
            try:
                self.strecken_name = list(self.alle_strecken)[0]
            except IndexError:
                pass

    def save_to_anlage(self):
        for idx, name in enumerate(self.edited_strecken):
            stationen = self.alle_strecken[name]
            self.anlage.strecken.add_strecke(name, stationen, idx + 1, False)
            self.auto_strecken.discard(name)
        for name in self.deleted_strecken:
            self.anlage.strecken.remove_strecke(name)
            self.auto_strecken.discard(name)

        self.edited_strecken = set()
        self.deleted_strecken = set()

    def _streckenliste_changed(self):
        """
        Streckenlisten-Modell aktualisieren
        """

        def strecken_key(name: str) -> Any:
            return name in self.auto_strecken, name

        strecken_liste = sorted((name for name, strecke in self.alle_strecken.items()), key=strecken_key)
        self.strecken_model.setStringList(strecken_liste)
        try:
            index = strecken_liste.index(self.strecken_name)
        except ValueError:
            pass
        else:
            self.ui.strecken_name_combo.setCurrentIndex(index)

    def _select_strecke(self, name: str):
        """
        Strecke auswählen und Stationslisten aktualisieren

        Die Modelle der Stationslisten werden aus alle_strecken aktualisiert (überschrieben!).

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

    def _strecke_edited(self):
        """
        Geänderte Strecke vom List-Modell übernehmen

        Aktualisiert alle_strecken,
        fügt die Strecke zu edited_strecken hinzu und
        entfernt sie aus deleted_strecken.
        """

        self.alle_strecken[self.strecken_name] = list(self.auswahl_model.rows)
        self.edited_strecken.add(self.strecken_name)
        self.deleted_strecken.discard(self.strecken_name)

    @Slot()
    def strecken_name_combo_index_changed(self):
        if self.in_update:
            return

        idx = self.ui.strecken_name_combo.currentIndex()
        index = self.strecken_model.index(idx)
        if index.isValid():
            strecken_name = self.strecken_model.data(index)
            if strecken_name != self.strecken_name:
                self.strecken_name = strecken_name
                self._select_strecke(self.strecken_name)

    @Slot()
    def strecken_name_combo_text_changed(self):
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
                self.auto_strecken.discard(new_name)
                self.deleted_strecken.discard(new_name)
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

        #self._strecke_edited()
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
            self.abwahl_model.insert(0, bst)

        #self._strecke_edited()
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

        #self._strecke_edited()

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

        #self._strecke_edited()

    @Slot()
    def strecken_loeschen_button_clicked(self):
        try:
            del self.alle_strecken[self.strecken_name]
        except KeyError:
            pass
        self.edited_strecken.discard(self.strecken_name)
        self.deleted_strecken.add(self.strecken_name)
        self._streckenliste_changed()

    @Slot()
    def strecken_erstellen_button_clicked(self):
        name = "Unbenannt"
        i = 1
        while name in self.alle_strecken:
            i += 1
            name = "Unbenannt " + str(i)

        self.alle_strecken[name] = []
        self.edited_strecken.add(self.strecken_name)
        self._select_strecke(name)
        self._streckenliste_changed()

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
        self._select_strecke(self.strecken_name)

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
