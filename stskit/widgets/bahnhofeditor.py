from collections import Counter
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PyQt5 import Qt, QtCore
from PyQt5.QtCore import pyqtSlot, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QStringListModel, QObject

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BahnsteigGraphNode, BahnsteigGraphEdge
from stskit.model.journal import GraphJournal
from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BahnhofEditorModel(QAbstractTableModel):
    """
    TableModel for editing BahnhofElements.

    Attribute
    =========

    - columns : list of str
      List of column names.
    - anlage : Anlage
      The Anlage object containing the BahnhofElements.
    - elemente : dict of BahnhofElement to any
      Dictionary mapping BahnhofElements to their data.
    - index : list of BahnhofElement
      List of BahnhofElements sorted by some criterion (not specified in the code).
    """

    ALL_COLUMNS = ['Gl', 'Bs', 'Bft', 'Bf', 'Sperrung', 'Stil', 'Sichtbar', 'N']

    def __init__(self, bahnhofgraph: BahnhofGraph, parent=None):
        super().__init__(parent)

        self._columns: List[str] = ['Gl', 'Bs', 'Bft', 'Bf', 'Sperrung', 'Stil']
        self.bahnhofgraph: BahnhofGraph = bahnhofgraph
        self.row_data: Dict[BahnhofElement, Any] = {}
        self.rows: List[BahnhofElement] = []

    def update(self):
        self.beginResetModel()
        elemente = {}

        for gleis in self.bahnhofgraph.list_by_type({'Gl'}):
            pfad = {t: n for t, n in self.bahnhofgraph.list_parents(gleis)}
            pfad['Gl'] = gleis.name
            data = self.bahnhofgraph.nodes[gleis]
            pfad['Sperrung'] = data.get('sperrung', False)
            pfad['Stil'] = data.get('stil', ':')
            pfad['Sichtbar'] = data.get('sichtbar', False)
            pfad['N'] = data.get('gleise', 1)
            elemente[gleis] = pfad

        self.row_data = elemente
        self.rows = sorted(self.row_data.keys())
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._columns)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = self._columns[index.column()]

        label = self.rows[row]
        data = self.row_data[label]

        if role == QtCore.Qt.UserRole:
            try:
                return data[col]
            except KeyError:
                return None

        elif role == QtCore.Qt.DisplayRole:
            try:
                if col == 'Sperrung':
                    return None
                else:
                    return str(data[col])
            except KeyError:
                return '???'

        elif role == QtCore.Qt.EditRole:
            try:
                if col == 'Sperrung':
                    return None
                else:
                    return str(data[col])
            except KeyError:
                return '???'

        elif role == QtCore.Qt.CheckStateRole:
            if col == 'Sperrung':
                if data[col]:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._columns[section]
            elif orientation == QtCore.Qt.Vertical:
                return self.rows[section]

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid() or role != QtCore.Qt.EditRole:
            return False
        return False

        # todo
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return super().flags(index) | QtCore.Qt.ItemIsEditable


class BahnhofEditorFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent):
        super().__init__(parent)

    def filterAcceptsRow(self, source_row, source_parent):
        return True


class BahnhofEditor(QObject):
    def __init__(self, anlage: Anlage, parent: QObject, ui: Ui_EinstellungenWindow):
        super().__init__()
        self.anlage = anlage
        self.bahnhofgraph = anlage.bahnhofgraph.copy(as_view=False)
        self.changes: GraphJournal = GraphJournal()
        self.parent = parent
        self.ui = ui

        self.gl_table_model = BahnhofEditorModel(self.bahnhofgraph)
        self.gl_table_filter = BahnhofEditorFilterProxy(parent)
        self.gl_table_filter.setSourceModel(self.gl_table_model)
        self.gl_table_filter.setSortRole(QtCore.Qt.UserRole)
        self.ui.gl_table_view.setModel(self.gl_table_filter)
        self.ui.gl_table_view.setSelectionMode(Qt.QAbstractItemView.MultiSelection)
        self.ui.gl_table_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.gl_table_view.sortByColumn(self.gl_table_model._columns.index('Gl'), 0)
        self.ui.gl_table_view.setSortingEnabled(True)
        self.last_selection = set()

        self.gl_model = QStringListModel()
        self.ui.gl_combo.setModel(self.gl_model)

        self.bs_model = QStringListModel()
        self.ui.bs_combo.setModel(self.bs_model)

        self.bft_model = QStringListModel()
        self.ui.bft_combo.setModel(self.bft_model)

        self.bf_model = QStringListModel()
        self.ui.bf_combo.setModel(self.bf_model)

        self.ui.bf_group_button.clicked.connect(self.bf_group_button_clicked)
        self.ui.bf_ungroup_button.clicked.connect(self.bf_ungroup_button_clicked)
        self.ui.bf_rename_button.clicked.connect(self.bf_rename_button_clicked)
        self.ui.bft_rename_button.clicked.connect(self.bft_rename_button_clicked)
        self.ui.bs_group_button.clicked.connect(self.bs_group_button_clicked)
        self.ui.bs_ungroup_button.clicked.connect(self.bs_ungroup_button_clicked)
        self.ui.bs_rename_button.clicked.connect(self.bs_rename_button_clicked)
        self.ui.gl_filter_button.clicked.connect(self.gl_filter_button_clicked)
        self.ui.bf_combo.currentIndexChanged.connect(self.bf_combo_index_changed)
        self.ui.bf_combo.editTextChanged.connect(self.bf_combo_text_changed)
        self.ui.bft_combo.currentIndexChanged.connect(self.bft_combo_index_changed)
        self.ui.bft_combo.editTextChanged.connect(self.bft_combo_text_changed)
        self.ui.bs_combo.currentIndexChanged.connect(self.bs_combo_index_changed)
        self.ui.bs_combo.editTextChanged.connect(self.bs_combo_text_changed)
        self.ui.gl_combo.currentIndexChanged.connect(self.gl_combo_index_changed)
        self.ui.gl_combo.editTextChanged.connect(self.gl_combo_text_changed)
        self.ui.gl_table_view.selectionModel().selectionChanged.connect(
            self.gl_selection_changed)

    def update_widgets(self):
        # Update the widgets based on the current state of the anlage
        self.gl_table_model.update()
        self.ui.gl_table_view.resizeColumnsToContents()
        self.ui.gl_table_view.resizeRowsToContents()

        self.gl_model.setStringList(sorted((gl.name for gl in self.bahnhofgraph.list_by_type({'Gl'}))))
        self.bs_model.setStringList(sorted((bs.name for bs in self.bahnhofgraph.list_by_type({'Bs'}))))
        self.bft_model.setStringList(sorted((bft.name for bft in self.bahnhofgraph.list_by_type({'Bft'}))))
        self.bf_model.setStringList(sorted((bf.name for bf in self.bahnhofgraph.list_by_type({'Bf'}))))

    def get_selection(self) -> Set[BahnhofElement]:
        """
        Gibt die aktuell ausgewählten Elemente zurück.

        :return: Ein Set von Gleisen (Bahnhofelemente vom Typ `Gl`), die aktuell ausgewählt sind.
        """

        selection = set()
        for index in self.ui.gl_table_view.selectedIndexes():
            try:
                index = self.gl_table_filter.mapToSource(index)
                row = index.row()
                selection.add(self.gl_table_model.rows[row])
            except (IndexError, KeyError):
                pass

        return selection

    @pyqtSlot('QItemSelection', 'QItemSelection')
    def gl_selection_changed(self, selected, deselected):
        selection = self.get_selection()
        new = selection - self.last_selection
        self.last_selection = selection

        try:
            new = list(new)[0]
            new_data = self.gl_table_model.row_data[new]
        except (IndexError, KeyError):
            return

        try:
            self.ui.bf_combo.setCurrentIndex(self.bf_model.stringList().index(new_data['Bf']))
        except ValueError:
            pass
        try:
            self.ui.bft_combo.setCurrentIndex(self.bft_model.stringList().index(new_data['Bft']))
        except ValueError:
            pass
        try:
            self.ui.bs_combo.setCurrentIndex(self.bs_model.stringList().index(new_data['Bs']))
        except ValueError:
            pass
        try:
            self.ui.gl_combo.setCurrentIndex(self.gl_model.stringList().index(new_data['Gl']))
        except ValueError:
            pass

    @pyqtSlot()
    def bf_group_button_clicked(self):
        """
        Gruppiert die ausgewählten Bahnhofteile zu einem Bahnhof.

        Die einzelnen Schritte sind:
        1. Zielbahnhof auswählen, z.B. unter den gewählten Elementen den Bahnhof mit den meisten Gleisen.
        2. Andere Bahnhöfe löschen.
        3. Hinzufügen der ausgewählten Bahnhofteile zum Zielbahnhof durch Erstellen von Kanten.
        4. Aktualisieren des Modells und der Ansicht.
        """

        self.group_elements('Bf', self.ui.bf_combo.currentText())

    @pyqtSlot()
    def bs_group_button_clicked(self):
        """
        Gruppiert die ausgewählten Gleise zu einem Bahnsteig.

        Die einzelnen Schritte sind:
        1. Zielbahnsteig auswählen, z.B. unter den gewählten Elementen den Bahnsteig mit den meisten Gleisen.
        2. Andere Bahnsteige löschen.
        3. Hinzufügen der ausgewählten Gleise zum Bahnsteig durch Erstellen von Kanten.
        4. Aktualisieren des Modells und der Ansicht.
        """

        self.group_elements('Bs', self.ui.bs_combo.currentText())

    @pyqtSlot()
    def bf_ungroup_button_clicked(self):
        """
        Entfernt die Gruppierung der ausgewählten Bahnhofteile und ordnet sie wieder unabhängigen Bahnhöfen zu.

        Die einzelnen Schritte sind:
        1. Bahnhof löschen.
        2. Zu jedem Bahnhofteil einen Bahnhof gleichen Namens erstellen und mit einer Kante verbinden.
        3. Aktualisieren des Modells und der Ansicht.
        """

        gleise = {gl for gl in self.get_selection()}

        self.gl_table_model.beginResetModel()
        try:
            for gl in gleise:
                bft = self.bahnhofgraph.find_superior(gl, {'Bft'})
                self.bahnhofgraph.replace_parent(gl, BahnhofElement('Bf', bft.name), del_old_parent=True)
        finally:
            self.gl_table_model.endResetModel()

    def group_elements(self, level: str, element: Optional[str] = None):
        gleise = {gl for gl in self.get_selection()}

        if element is None:
            elements = (self.gl_table_model.row_data[sel].get(level) for sel in gleise)
            elements = sorted((bf for bf in elements if bf is not None))
            if not elements:
                return {}, {}
            element, _ = Counter(elements).most_common(1)[0]

        new_element = BahnhofElement(level, element)
        replace = {}
        insert = {}
        for gl in gleise:
            try:
                sup = self.bahnhofgraph.find_superior(gl, level)
            except KeyError:
                insert[gl] = new_element
            else:
                if sup != new_element:
                    replace[sup] = new_element

        self.gl_table_model.beginResetModel()
        try:
            # todo: test!
            nx.relabel_nodes(self.bahnhofgraph, replace, copy=False)
        finally:
            self.gl_table_model.endResetModel()

    @pyqtSlot()
    def bs_ungroup_button_clicked(self):
        """
        Entfernt die Gruppierung der ausgewählten Gleise und ordnet sie wieder unabhängigen Bahnsteigen zu.

        Die einzelnen Schritte sind:
        1. Bahnsteig löschen.
        2. Zu jedem Gleis einen Bahnsteig gleichen Namens erstellen und mit einer Kante verbinden.
        3. Aktualisieren des Modells und der Ansicht.
        """

        gleise = {gl for gl in self.get_selection()}

        self.gl_table_model.beginResetModel()
        try:
            for gl in gleise:
                bs = self.bahnhofgraph.find_superior(gl, {'Bs'})
                self.bahnhofgraph.replace_parent(gl, BahnhofElement('Bs', bs.name), del_old_parent=True)
        finally:
            self.gl_table_model.endResetModel()

    @pyqtSlot()
    def bf_rename_button_clicked(self):
        pass

    @pyqtSlot()
    def bft_rename_button_clicked(self):
        pass

    @pyqtSlot()
    def bs_rename_button_clicked(self):
        pass

    @pyqtSlot()
    def bf_combo_index_changed(self):
        pass

    @pyqtSlot()
    def bft_combo_index_changed(self):
        pass

    @pyqtSlot()
    def bs_combo_index_changed(self):
        pass

    @pyqtSlot()
    def gl_combo_index_changed(self):
        pass

    @pyqtSlot()
    def bf_combo_text_changed(self):
        pass

    @pyqtSlot()
    def bft_combo_text_changed(self):
        pass

    @pyqtSlot()
    def bs_combo_text_changed(self):
        pass

    @pyqtSlot()
    def gl_combo_text_changed(self):
        pass

    @pyqtSlot()
    def gl_filter_button_clicked(self):
        pass
