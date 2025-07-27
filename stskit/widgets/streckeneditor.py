import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QStringListModel, QObject
from PySide6.QtWidgets import QWidget, QAbstractItemView

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BahnsteigGraphNode, BahnsteigGraphEdge
from stskit.model.journal import GraphJournal
from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class StreckenEditor(QObject):
    # todo : drag drop uebernehmen

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
        self.akt_auswahl: List[BahnhofElement] = []
        self.akt_abwahl: List[BahnhofElement] = []
        self.akt_name: str = ""
        
        self.auswahl_model = QStringListModel()
        self.ui.strecken_auswahl_list.setModel(self.auswahl_model)
        self.abwahl_model = QStringListModel()
        self.ui.strecken_abwahl_list.setModel(self.abwahl_model)
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
        self.abwahl_model.rowsInserted.connect(self.abwahl_rows_inserted)
        self.auswahl_model.rowsMoved.connect(self.auswahl_rows_moved)
        self.abwahl_model.rowsMoved.connect(self.abwahl_rows_moved)
        self.auswahl_model.rowsRemoved.connect(self.auswahl_rows_removed)
        self.abwahl_model.rowsRemoved.connect(self.abwahl_rows_removed)
        self.auswahl_model.dataChanged.connect(self.auswahl_data_changed)
        self.abwahl_model.dataChanged.connect(self.abwahl_data_changed)

        self.init_from_anlage()
        self.update_widgets()

    def init_from_anlage(self):
        """
        Streckendefinition von Anlage initialisieren

        Alle Änderungen werden gelöscht!
        """

        self.anlage_strecken = {k: self.anlage.strecken.strecken[k] for k in self.anlage.strecken.strecken}
        self.auto_strecken = {k for k in self.anlage.strecken.strecken if self.anlage.strecken.auto.get(k, True)}
        self.alle_strecken = self.anlage_strecken.copy()
        self.edited_strecken = set()
        self.anlage_bst = sorted(self.anlage.bahnhofgraph.list_by_type({'Bf', 'Anst'}))

        if self.akt_name not in self.alle_strecken:
            for name in self.alle_strecken:
                self.select_strecke(name)
                break

    def save_to_anlage(self):
        for idx, strecke in enumerate(self.alle_strecken.items()):
            name, stationen = strecke
            if name not in self.auto_strecken:
                if len(stationen) >= 2:
                    self.anlage.strecken.add_strecke(name, stationen, idx + 1, False)
                else:
                    self.anlage.strecken.remove_strecke(name)

    def strecke_edited(self):
        pass

    def update_widgets(self):
        """
        Update the widgets based on the current state of the anlage
        """

        # todo : auswahl beibehalten

        def strecken_key(name: str) -> Any:
            return name in self.auto_strecken, name

        self.in_update = True

        self.akt_abwahl = [bst for bst in self.anlage_bst if bst not in self.akt_auswahl]

        strecken_liste = sorted((name for name, strecke in self.alle_strecken.items()), key=strecken_key)
        self.strecken_model.setStringList(strecken_liste)
        self.auswahl_model.setStringList([str(bst) for bst in self.akt_auswahl])
        self.abwahl_model.setStringList([str(bst) for bst in self.akt_abwahl])

        try:
            self.ui.strecken_name_combo.setCurrentIndex(strecken_liste.index(self.akt_name))
        except ValueError:
            pass

        self.in_update = False

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
        if name not in self.alle_strecken:
            return
        self.akt_name = name
        self.akt_auswahl = self.alle_strecken.get(self.akt_name)

    def change_strecke(self, name: str, stationen: Sequence[BahnhofElement]):
        self.akt_auswahl = list(stationen)
        self.alle_strecken[name] = list(stationen)
        self.edited_strecken.add(name)

    @Slot()
    def strecken_name_combo_index_changed(self):
        if self.in_update:
            return

        idx = self.ui.strecken_name_combo.currentIndex()
        index = self.strecken_model.index(idx)
        if index.isValid():
            self.akt_name = self.strecken_model.data(index)
            self.akt_auswahl = self.alle_strecken.get(self.akt_name)
        self.update_widgets()

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
                self.auto_strecken.discard(index_name)
                self.edited_strecken.add(new_name)
                self.strecken_model.setData(index, new_name)
                self.akt_name = new_name

    @Slot()
    def strecken_auswahl_button_clicked(self):
        try:
            src_indexes = self.ui.strecken_abwahl_list.selectedIndexes()
            move_items = [self.akt_abwahl[index.row()] for index in src_indexes]
        except IndexError:
            return
        try:
            dst_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            index = dst_indexes[0].row()
        except IndexError:
            index = len(self.akt_auswahl)

        before = self.akt_auswahl[0:index]
        after = self.akt_auswahl[index:]
        self.change_strecke(self.akt_name, [*before, *move_items, *after])
        self.update_widgets()

    @Slot()
    def strecken_abwahl_button_clicked(self):
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            move_items = [self.akt_auswahl[index.row()] for index in src_indexes]
        except IndexError:
            return
        self.change_strecke(self.akt_name, [station for station in self.akt_auswahl if station not in move_items])
        self.update_widgets()

    @Slot()
    def strecken_hoch_button_clicked(self):
        # todo : funktioniert nicht (keine wirkung, keine fehlermeldung)
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            move_items = [self.akt_auswahl[index.row()] for index in src_indexes]
            index = src_indexes[0].row()
        except IndexError:
            return
        before = self.akt_auswahl[0:index]
        after = [station for station in self.akt_auswahl[index:] if station not in move_items]
        self.change_strecke(self.akt_name, [*before, *move_items, *after])
        self.update_widgets()

    @Slot()
    def strecken_runter_button_clicked(self):
        # todo : funktioniert nicht (keine wirkung, keine fehlermeldung)
        try:
            src_indexes = self.ui.strecken_auswahl_list.selectedIndexes()
            move_items = [self.akt_auswahl[index.row()] for index in src_indexes]
            index = src_indexes[-1].row()
        except IndexError:
            return
        before = [station for station in self.akt_auswahl[0:index] if station not in move_items]
        after = self.akt_auswahl[index+1:]
        self.change_strecke(self.akt_name, [*before, *move_items, *after])
        self.update_widgets()

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

    @Slot()
    def strecken_loeschen_button_clicked(self):
        self.change_strecke(self.akt_name, [])
        self.update_widgets()

    @Slot()
    def strecken_erstellen_button_clicked(self):
        name = "Unbenannt"
        i = 1
        while name in self.alle_strecken:
            i += 1
            name = "Unbenannt " + str(i)

        self.change_strecke(name, [])
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
            start = self.akt_auswahl[0]
        except IndexError:
            return
        try:
            signal_start = _bst_to_signal(start)
        except KeyError:
            return

        distanzen = {}
        d = 0.
        for station in self.akt_auswahl:
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

        self.change_strecke(self.akt_name, sorted(self.akt_auswahl, key=lambda _item: distanzen[_item]))
        self.select_strecke("")
        self.update_widgets()
