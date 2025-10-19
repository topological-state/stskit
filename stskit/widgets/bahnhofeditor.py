from collections import Counter
import logging
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import networkx as nx
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QStringListModel, QObject
from PySide6.QtWidgets import QWidget, QAbstractItemView

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BahnsteigGraphNode, BahnsteigGraphEdge, \
    BAHNHOFELEMENT_TYPEN
from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class AbstractBahnhofEditorModel(QAbstractTableModel):
    """
    Abstract TableModel for editing BahnhofElements.

    The inheriting class must set the `_columns` and `_gleistyp` attributes in its constructor.

    Attributes
    ==========

    - _gleistyp : 'Gl' or 'Agl', depending on which tree is edited.
    - _columns : Column names displayed in the header row.
        Supported column names are:
        'Gl', 'Bs´, 'Bft', 'Bf', 'Agl', 'Anst', 'Sperrung', 'Stil', 'Sichtbar', 'N'
    - bahnhofgraph : BahnhofGraph instance to be edited.
    - rows: List of Gl or Agl elements to be displayed in rows.
        This is a sorted list of the dictionary keys of row_data.
    - row_data: Element data to be displayed in rows.
        The dictionary keys correspond to `rows`, without order.
        Each value contains a dictionary where the key corresponds to the column name
        and value the data to be displayed in the cell.
    - changed: Indicates whether data have changed.
    """

    def __init__(self, bahnhofgraph: BahnhofGraph, parent=None):
        super().__init__(parent)

        self._columns: List[str] = []
        self._gleistyp: str = ''
        self.bahnhofgraph: BahnhofGraph = bahnhofgraph
        self.row_data: Dict[BahnhofElement, Any] = {}
        self.row_index: Dict[BahnhofElement, Tuple[Union[int, str], ...]] = {}
        self.rows: List[BahnhofElement] = []
        self.changed = False

    def update(self):
        """
        Update the row data and rows based on the current state of the bahnhofgraph.

        The method iterates through all elements of a specific type in the graph,
        and fills the `row_data` and `rows` attributes according to the description in the class header..

        This function also signals a reset to associated views.
        """

        self.beginResetModel()
        self._update()
        self.endResetModel()

    def _update(self):
        """
        (Internal) Update the row data and rows based on the current state of the bahnhofgraph.

        The method iterates through all elements of a specific type in the graph,
        and fills the `row_data` and `rows` attributes according to the description in the class header.

        This function is internal.
        It does not signal the change to associated views.
        Use `update` unless you take care to signal the views.
        """

        elemente = {}

        for gleis in self.bahnhofgraph.list_by_type({self._gleistyp}):
            pfad = {t: n for t, n in self.bahnhofgraph.list_parents(gleis)}
            pfad[self._gleistyp] = gleis.name
            data = self.bahnhofgraph.nodes[gleis]
            pfad['Sperrung'] = data.get('sperrung', False)
            pfad['Stil'] = data.get('stil', ':')
            pfad['Sichtbar'] = data.get('sichtbar', False)
            pfad['N'] = data.get('gleise', 1)
            elemente[gleis] = pfad

        self.row_data = elemente
        self.row_index = self.bahnhofgraph.hierarchical_index(elemente.keys())
        self.rows = list(elemente.keys())

    def _get_index(self, element: BahnhofElement) -> Tuple[QModelIndex, QModelIndex]:
        """
        Returns the QModelIndex of the first and last rows corresponding to a given element.

        If element is a Gl (or Agl), the first and last rows are the same.
        If element is a higher level, the indexes can span a range of rows.

        Args:
            element (BahnhofElement): The element for which to find the indexes.

        Returns:
            Tuple[QModelIndex, QModelIndex]: A tuple containing the QModelIndex of the first and last rows.
            The first index points to column 0, the second index to the last column.

        Raises:
            KeyError: If element is not in bahnhofgraph.
            ValueError: If the element is not in the table. (Should not happen if the table is up to date.)
        """

        gleise = self.bahnhofgraph.list_children(element, {self._gleistyp})
        rows = [self.rows.index(gl) for gl in gleise]
        index1 = self.index(min(rows), 0, QModelIndex())
        index2 = self.index(max(rows), len(self._columns) - 1, QModelIndex())
        return index1, index2

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

        elif role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            try:
                if col == 'Sperrung':
                    return None
                else:
                    return str(data[col])
            except KeyError:
                return None

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

        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return False

        row = index.row()
        col = self._columns[index.column()]
        label = self.rows[row]
        data = self.row_data[label]

        if role == QtCore.Qt.EditRole:
            if col in {'Bs', 'Bft', 'Bf', 'Anst'}:
                element = self.bahnhofgraph.find_superior(label, {col})
                self.rename_element(col, element.name, value)
                return True

        elif role == QtCore.Qt.CheckStateRole:
            value = QtCore.Qt.CheckState(value)
            if col in {'Sperrung', 'Sichtbar'}:
                data[col] = value == QtCore.Qt.Checked
                self.bahnhofgraph.nodes[label][col.lower()] = data[col]
                self.dataChanged.emit(index, index)
                return True

        return False

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        col = self._columns[index.column()]

        result = QtCore.Qt.ItemIsEnabled
        if col in {'Gl', 'Agl'}:
            result |= QtCore.Qt.ItemIsSelectable
        elif col in {'Sperrung', 'Sichtbar'}:
            result |= QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable
        elif col in {'Bs', 'Bft', 'Bf', 'Anst', 'Stil', 'N'}:
            result |= QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsSelectable
        else:
            result = QtCore.Qt.NoItemFlags

        return result

    def group_elements(self,
                       gleise: Set[BahnhofElement],
                       level: str,
                       element: Optional[str] = None) -> Set[BahnhofElement]:
        """
        Groups elements based on the given criteria.

        :param gleise: Set of BahnhofElement objects to be grouped.
        :type gleise: Set[BahnhofElement]
        :param level: Level at which to perform the grouping.
        :type level: str
        :param element: Optional parameter specifying the specific element to group by; if None, the most common element is used.
        :type element: Optional[str]

        :return: Set of BahnhofElement objects (Gl or Agl) that were replaced or inserted.
        :rtype: Set[BahnhofElement]
        """

        if element is None:
            elements = (self.row_data[sel].get(level) for sel in gleise)
            elements = sorted((bf for bf in elements if bf is not None))
            if not elements:
                return set()
            element, _ = Counter(elements).most_common(1)[0]

        new_element = BahnhofElement(level, element)
        replacements = {gl: new_element for gl in gleise}
        self._replace_parents(replacements)

        return set(replacements.keys())

    def ungroup_elements(self, elements: Set[BahnhofElement],
                        level: str) -> Set[BahnhofElement]:
        """
        Ungroups elements based on a given level.

        This method creates new BahnhofElement objects with the specified level and name of each child element
        if the corresponding parent does not exist in the bahnhofgraph.

        Parameters:
            elements (Set[BahnhofElement]): A set of BahnhofElement objects to be ungrouped.
            level (str): The level at which to create new BahnhofElement objects.

        Returns:
            Set[BahnhofElement]: A set containing the new BahnhofElement objects that were created and added to the bahnhofgraph.

        This method modifies the bahnhofgraph by replacing parent-child relationships as necessary. If no replacements are made, an empty set is returned.
        """

        replacements = {}
        for child in elements:
            if not self.bahnhofgraph.has_node(child):
                continue  # Gleis existiert nicht
            parent = BahnhofElement(level, child.name)
            if self.bahnhofgraph.has_node(parent):
                continue  # Bahnsteig existiert bereits
            replacements[child] = parent
        if not replacements:
            return set()

        self._replace_parents(replacements)

        return set(replacements.keys())

    def _replace_parents(self, replacements: Mapping[BahnhofElement, BahnhofElement]):
        self.beginResetModel()
        try:
            for child, parent in replacements.items():
                try:
                    self.bahnhofgraph.replace_parent(child, parent)
                    self.changed = True
                except ValueError:
                    pass
            self.bahnhofgraph.leere_gruppen_entfernen()
        finally:
            self._update()
            self.endResetModel()

    def rename_element(self, level: str, old: str, new: str) -> bool:
        """
        Renames an element in the graph and updates the model accordingly.

        This is the public method that also signals the change to associated views.
        """

        old = BahnhofElement(level, old)
        new = BahnhofElement(level, new)

        if old == new:
            return False   # Alter und neuer Name sind identisch
        if old not in self.bahnhofgraph.nodes():
            return  False  # Element existiert nicht
        if new in self.bahnhofgraph.nodes():
            return  False  # Neuer Name existiert bereits

        old_index_1, old_index_2 = self._get_index(old)
        self._rename_element(old, new)
        new_index_1, new_index_2 = self._get_index(new)

        index_1 = self.index(min(old_index_1.row(), new_index_1.row()), old_index_1.column(), QModelIndex())
        index_2 = self.index(min(old_index_2.row(), new_index_2.row()), old_index_2.column(), QModelIndex())
        self.dataChanged.emit(index_1, index_2)

        return True

    def _rename_element(self, old: BahnhofElement, new: BahnhofElement):
        """
        (Internal) Renames an element in the graph and updates the model accordingly.

        This is method does not notify associated views.
        """

        nx.relabel_nodes(self.bahnhofgraph, {old: new}, copy=False)
        self.bahnhofgraph.nodes[new]['auto'] = False
        self.bahnhofgraph.nodes[new]['name'] = new.name
        self.changed = True
        self._update()


class AnschlussEditorModel(AbstractBahnhofEditorModel):
    """
    Tabellenmodell für den Anschlusseditor

    Diese Klasse stellt den Anschlussast des Bahnhofgraphs dar.

    """

    ALL_COLUMNS = ['Agl', 'Anst', 'Sperrung', 'Stil', 'Sichtbar', 'N']

    def __init__(self, bahnhofgraph: BahnhofGraph, parent=None):
        super().__init__(bahnhofgraph, parent)

        self._columns: List[str] = ['Agl', 'Anst', 'Sperrung']
        self._gleistyp: str = 'Agl'


class BahnhofEditorModel(AbstractBahnhofEditorModel):
    """
    Tabellenmodell für den Bahnhofeditor

    Diese Klasse stellt den Bahnhofast des Bahnhofgraphs dar.

    """

    ALL_COLUMNS = ['Gl', 'Bs', 'Bft', 'Bf', 'Sperrung', 'Stil', 'Sichtbar', 'N']

    def __init__(self, bahnhofgraph: BahnhofGraph, parent=None):
        super().__init__(bahnhofgraph, parent)

        self._columns: List[str] = ['Gl', 'Bs', 'Bft', 'Bf', 'Sperrung']
        self._gleistyp: str = 'Gl'


class BahnhofEditorFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent):
        super().__init__(parent)
        self.filter_text: Optional[str] = None

    def _get_source_model(self):
        model = self.sourceModel()
        while not isinstance(model, AbstractBahnhofEditorModel):
            try:
                model = model.sourceModel()
            except AttributeError:
                pass
        return model

    def filterAcceptsRow(self, source_row, source_parent):
        if not self.filter_text:
            return True

        model = self._get_source_model()
        try:
            element = model.rows[source_row]
        except (AttributeError, IndexError, KeyError):
            return True

        return self.filter_text in element.name.casefold()

    def lessThan(self, source_left, source_right, /):
        model = self._get_source_model()
        key_left = model.row_index[model.rows[source_left.row()]]
        key_right = model.row_index[model.rows[source_right.row()]]
        return key_left < key_right

class BahnhofEditor(QObject):
    def __init__(self, anlage: Anlage, parent: QObject, ui: Ui_EinstellungenWindow):
        super().__init__()
        self.anlage = anlage
        self.bahnhofgraph = anlage.bahnhofgraph.copy(as_view=False)
        self.parent = parent
        self.ui = ui
        self.in_update = True

        self.gl_table_model = BahnhofEditorModel(self.bahnhofgraph)
        self.gl_table_filter = BahnhofEditorFilterProxy(parent)
        self.gl_table_filter.setSourceModel(self.gl_table_model)
        self.ui.gl_table_view.setModel(self.gl_table_filter)
        self.ui.gl_table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.gl_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.gl_table_view.sortByColumn(self.gl_table_model._columns.index('Gl'), QtCore.Qt.AscendingOrder)
        self.ui.gl_table_view.setSortingEnabled(True)
        self.gl_last_selection = set()

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
        self.ui.bft_group_button.clicked.connect(self.bft_group_button_clicked)
        self.ui.bft_ungroup_button.clicked.connect(self.bft_ungroup_button_clicked)
        self.ui.bft_rename_button.clicked.connect(self.bft_rename_button_clicked)
        self.ui.bs_group_button.clicked.connect(self.bs_group_button_clicked)
        self.ui.bs_ungroup_button.clicked.connect(self.bs_ungroup_button_clicked)
        self.ui.bs_rename_button.clicked.connect(self.bs_rename_button_clicked)
        self.ui.bf_combo.currentIndexChanged.connect(self.bf_combo_index_changed)
        self.ui.bf_combo.editTextChanged.connect(self.bf_combo_text_changed)
        self.ui.bft_combo.currentIndexChanged.connect(self.bft_combo_index_changed)
        self.ui.bft_combo.editTextChanged.connect(self.bft_combo_text_changed)
        self.ui.bs_combo.currentIndexChanged.connect(self.bs_combo_index_changed)
        self.ui.bs_combo.editTextChanged.connect(self.bs_combo_text_changed)
        self.ui.gl_combo.editTextChanged.connect(self.gl_combo_text_changed)
        self.ui.gl_table_view.selectionModel().selectionChanged.connect(
            self.gl_selection_changed)
        self.gl_table_model.dataChanged.connect(self.gl_table_model_changed)

        self.agl_table_model = AnschlussEditorModel(self.bahnhofgraph)
        self.agl_table_filter = BahnhofEditorFilterProxy(parent)
        self.agl_table_filter.setSourceModel(self.agl_table_model)
        self.ui.agl_table_view.setModel(self.agl_table_filter)
        self.ui.agl_table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.agl_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.agl_table_view.sortByColumn(self.agl_table_model._columns.index('Agl'), QtCore.Qt.AscendingOrder)
        self.ui.agl_table_view.setSortingEnabled(True)
        self.agl_last_selection = set()

        self.agl_model = QStringListModel()
        self.ui.agl_combo.setModel(self.agl_model)
        self.anst_model = QStringListModel()
        self.ui.anst_combo.setModel(self.anst_model)

        self.ui.anst_group_button.clicked.connect(self.anst_group_button_clicked)
        self.ui.anst_ungroup_button.clicked.connect(self.anst_ungroup_button_clicked)
        self.ui.anst_rename_button.clicked.connect(self.anst_rename_button_clicked)
        self.ui.anst_combo.currentIndexChanged.connect(self.anst_combo_index_changed)
        self.ui.anst_combo.editTextChanged.connect(self.anst_combo_text_changed)
        self.ui.agl_combo.currentIndexChanged.connect(self.agl_combo_index_changed)
        self.ui.agl_combo.editTextChanged.connect(self.agl_combo_text_changed)
        self.ui.agl_table_view.selectionModel().selectionChanged.connect(
            self.agl_selection_changed)
        self.agl_table_model.dataChanged.connect(self.agl_table_model_changed)

        self.in_update = False

    def update_widgets(self):
        """
        Fully update the widgets based on the current state of self.bahnhofgraph.
        """

        self.in_update = True
        self.gl_table_model.update()
        self.agl_table_model.update()

        self.update_lists()
        self.update_gl_widget_states()
        self.update_agl_widget_states()
        self.adjust_geometry()
        self.in_update = False

    def update_lists_and_states(self, levels: Optional[Set[str]] = None):
        """
        Fully update the widgets based on the current state of self.bahnhofgraph.
        """
        if levels is None:
            levels = set(BAHNHOFELEMENT_TYPEN)

        self.in_update = True
        self.update_lists(levels=levels)
        if levels.intersection(['Gl', 'Bs', 'Bft', 'Bf']):
            self.update_gl_combo_index()
            self.update_gl_widget_states()
        if levels.intersection(['Agl', 'Anst']):
            self.update_agl_combo_index()
            self.update_agl_widget_states()
        self.adjust_geometry()
        self.in_update = False

    @staticmethod
    def _make_filter_list(gl_list: Iterable[BahnhofElement]) -> Iterable[str]:
        result = {''}
        for gl in gl_list:
            mo = re.match(r'^[a-zA-Z]*', gl.name)
            if mo:
                result.add(mo[0])
        return result

    def update_lists(self, levels: Optional[Set[str]] = None) -> None:
        """
        Update the listes of the combo boxes according to the current selection..

        Parameters
        ----------
        levels : Optional[Set[str]], optional
            A set of levels of combo boxes to update. Defaults to all BAHNHOFELEMENT_TYPEN.

        """

        if levels is None:
            levels = set(BAHNHOFELEMENT_TYPEN)

        if 'Gl' in levels:
            gl_filter = sorted(self._make_filter_list(self.bahnhofgraph.list_by_type({'Gl'})))
            self.gl_model.setStringList(gl_filter)

        if 'Agl' in levels:
            agl_filter = sorted(self._make_filter_list(self.bahnhofgraph.list_by_type({'Agl'})))
            self.agl_model.setStringList(agl_filter)

        if levels.intersection(['Bs', 'Bft', 'Bf', 'Anst']):
            gl_sel = self.get_gl_selection()
            parents = {typ: set() for typ in BAHNHOFELEMENT_TYPEN}
            uncles = {typ: set() for typ in BAHNHOFELEMENT_TYPEN}
            for gl in gl_sel:
                for be in self.bahnhofgraph.list_parents(gl):
                    parents[be.typ].add(be)
            agl_sel = self.get_agl_selection()
            for agl in agl_sel:
                for be in self.bahnhofgraph.list_parents(agl):
                    parents[be.typ].add(be)

            for typ in ['Bs', 'Bft', 'Bf', 'Anst']:
                for parent in parents[typ]:
                    uncles[typ].update(self.bahnhofgraph.list_siblings(parent))

            if 'Bs' in levels:
                self.bs_model.setStringList(sorted((uncle.name for uncle in uncles['Bs'])))
            if 'Bft' in levels:
                self.bft_model.setStringList(sorted((uncle.name for uncle in uncles['Bft'])))
            if 'Bf' in levels:
                self.bf_model.setStringList(sorted((uncle.name for uncle in uncles['Bf'])))
            if 'Anst' in levels:
                self.anst_model.setStringList(sorted((uncle.name for uncle in uncles['Anst'])))

    def adjust_geometry(self):
        """
        Adjust the geometry of the widgets based on their current content.
        """

        self.ui.gl_table_view.resizeColumnsToContents()
        self.ui.gl_table_view.resizeRowsToContents()
        self.ui.agl_table_view.resizeColumnsToContents()
        self.ui.agl_table_view.resizeRowsToContents()

    @property
    def changed(self) -> bool:
        return self.gl_table_model.changed or self.agl_table_model.changed

    def apply(self):
        """
        Apply changes to anlage based on the current state of the widgets
        """

        self.anlage.bahnhofgraph.clear()
        self.anlage.bahnhofgraph.update(self.bahnhofgraph)
        self.anlage.liniengraph_konfigurieren()
        self.gl_table_model.changed = False
        self.agl_table_model.changed = False

    def reset(self):
        """
        Reset models and widgets to anlage
        """

        self.bahnhofgraph.clear()
        self.bahnhofgraph.update(self.anlage.bahnhofgraph)
        self.update_widgets()
        self.gl_table_model.changed = False
        self.agl_table_model.changed = False

    def get_gl_selection(self) -> Set[BahnhofElement]:
        """
        Gibt die aktuell ausgewählten Gleise zurück.

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

    def get_agl_selection(self) -> Set[BahnhofElement]:
        """
        Gibt die aktuell ausgewählten Anschlussgleise zurück.

        :return: Ein Set von Anschlussgleisen (Bahnhofelemente vom Typ `Agl`), die aktuell ausgewählt sind.
        """

        selection = set()
        for index in self.ui.agl_table_view.selectedIndexes():
            try:
                index = self.agl_table_filter.mapToSource(index)
                row = index.row()
                selection.add(self.agl_table_model.rows[row])
            except (IndexError, KeyError):
                pass

        return selection

    def get_combo_element(self, level: str, combo: QtWidgets.QComboBox):
        """
        Bahnhofelement aus Combobox auslesen.

        Der Name des Elements wird aus dem Editierfeld ausgelesen.
        Das Modell wird nicht beachtet.

        :param level: Der Level des Elements.
        :param combo: Die QComboBox, das den Namen des Elements enthält.
        :return: Ein BahnhofElement vom Typ level, oder None, wenn das Element nicht existiert.
        """

        txt = combo.currentText()
        element = BahnhofElement(level, txt)
        if self.bahnhofgraph.has_node(element):
            return element
        else:
            return None

    @Slot('QItemSelection', 'QItemSelection')
    def gl_selection_changed(self, selected, deselected):
        """
        Handles selection changes in the GL view and updates corresponding UI elements.

        Parameters
        ----------
        selected : QItemSelection
            The new items selected in the GL view.
        deselected : QItemSelection
            The items that have been deselected in the GL view.

        Returns
        -------
        None

        Details
        ------
        This method is triggered when the user selects or deselects items in the GL view.

        1. Updates the lists of combo boxes.
        2. Tries to select the corresponding element of the combo boxes.
        3. Updates the widget states.
        """

        self.update_lists(levels={'Bs', 'Bft', 'Bf'})
        self.update_gl_combo_index()
        self.update_gl_widget_states()

    def update_gl_combo_index(self):
        selection = self.get_gl_selection()
        new = selection - self.gl_last_selection or selection
        self.gl_last_selection = selection

        try:
            new = list(new)[0]
            new_data = self.gl_table_model.row_data[new]
        except (IndexError, KeyError):
            pass
        else:
            try:
                self.ui.bf_combo.setCurrentIndex(self.bf_model.stringList().index(new_data['Bf']))
            except (KeyError, ValueError):
                pass
            try:
                self.ui.bft_combo.setCurrentIndex(self.bft_model.stringList().index(new_data['Bft']))
            except (KeyError, ValueError):
                pass
            try:
                self.ui.bs_combo.setCurrentIndex(self.bs_model.stringList().index(new_data['Bs']))
            except (KeyError, ValueError):
                pass

    @Slot('QItemSelection', 'QItemSelection')
    def agl_selection_changed(self, selected, deselected):
        """
        Handles selection changes in the AGL view and updates corresponding UI elements.

        Parameters
        ----------
        selected : QItemSelection
            The new items selected in the GL view.
        deselected : QItemSelection
            The items that have been deselected in the GL view.

        Returns
        -------
        None

        Details
        ------
        This method is triggered when the user selects or deselects items in the AGL view.

        1. Updates the lists of combo boxes.
        2. Tries to select the corresponding element of the combo boxes.
        3. Updates the widget states.
        """

        self.update_lists(levels={'Anst'})
        self.update_agl_combo_index()
        self.update_agl_widget_states()

    def update_agl_combo_index(self):
        selection = self.get_agl_selection()
        new = selection - self.agl_last_selection
        self.agl_last_selection = selection

        try:
            new = list(new)[0]
            new_data = self.agl_table_model.row_data[new]
        except (IndexError, KeyError):
            pass
        else:
            try:
                self.ui.anst_combo.setCurrentIndex(self.bf_model.stringList().index(new_data['Anst']))
            except (KeyError, ValueError):
                pass

    def update_gl_widget_states(self):
        """
        Enables or disables buttons according to the current selection in the GL view.
        """

        selection = self.get_gl_selection()
        bs_sel = {self.gl_table_model.row_data[gl]['Bs'] for gl in selection if 'Bs' in self.gl_table_model.row_data[gl]}
        bft_sel = {self.gl_table_model.row_data[gl]['Bft'] for gl in selection if 'Bft' in self.gl_table_model.row_data[gl]}
        bf_sel = {self.gl_table_model.row_data[gl]['Bf'] for gl in selection if 'Bf' in self.gl_table_model.row_data[gl]}

        # gleiswahl >= 1 , combo-text vorhanden und noch nicht vergeben
        # en = bool(selection)
        # if en:
        #     tx = self.ui.bf_combo.currentText()
        #     be = BahnhofElement('Bf', tx)
        #     en = bool(tx) and be in self.bahnhofgraph
        en = len(bft_sel) == 1 and bool(tx := self.ui.bf_combo.currentText()) and (BahnhofElement('Bf', tx) in self.bahnhofgraph)
        self.ui.bf_group_button.setEnabled(en)

        # gleiswahl >= 1 , combo-text vorhanden und noch nicht vergeben
        en = len(bft_sel) == 1 and bool(tx := self.ui.bft_combo.currentText()) and (BahnhofElement('Bft', tx) in self.bahnhofgraph)
        self.ui.bft_group_button.setEnabled(en)

        # gleiswahl >= 1 vom gleichen bft, combo-text vorhanden und noch nicht vergeben
        en = len(bft_sel) == 1 and bool(tx := self.ui.bs_combo.currentText()) and (BahnhofElement('Bs', tx) in self.bahnhofgraph)
        self.ui.bs_group_button.setEnabled(en)

        # einzelner bf gewählt
        en = len(bf_sel) == 1
        self.ui.bf_ungroup_button.setEnabled(en)

        # einzelner bft gewählt
        en = len(bft_sel) == 1
        self.ui.bft_ungroup_button.setEnabled(en)

        # einzelner bs gewählt
        en = len(bs_sel) == 1
        self.ui.bs_ungroup_button.setEnabled(en)

        # einzelner bf gewählt, combo-text vorhanden und noch nicht vergeben
        en = len(bf_sel) == 1 and bool(tx := self.ui.bf_combo.currentText()) and (BahnhofElement('Bf', tx) not in self.bahnhofgraph)
        self.ui.bf_rename_button.setEnabled(en)

        # einzelner bft gewählt, combo-text vorhanden und noch nicht vergeben
        en = len(bft_sel) == 1 and bool(tx := self.ui.bft_combo.currentText()) and (BahnhofElement('Bft', tx) not in self.bahnhofgraph)
        self.ui.bft_rename_button.setEnabled(en)

        # einzelner bs gewählt, combo-text vorhanden und noch nicht vergeben
        en = len(bs_sel) == 1 and bool(tx := self.ui.bs_combo.currentText()) and (BahnhofElement('Bs', tx) not in self.bahnhofgraph)
        self.ui.bs_rename_button.setEnabled(en)

    def update_agl_widget_states(self):
        """
        Enables or disables buttons according to the current selection in the AGL view.
        """

        selection = self.get_agl_selection()
        anst_sel = {self.agl_table_model.row_data[gl]['Anst'] for gl in selection}

        # gleiswahl >= 1 , combo-text vorhanden und noch nicht vergeben
        en = len(selection) >= 1 and bool(tx := self.ui.anst_combo.currentText()) and (BahnhofElement('Anst', tx) in self.bahnhofgraph)
        self.ui.anst_group_button.setEnabled(en)

        # einzelne anst gewählt
        en = len(anst_sel) == 1
        self.ui.anst_ungroup_button.setEnabled(en)

        # einzelner anst gewählt, combo-text vorhanden und noch nicht vergeben
        en = len(anst_sel) == 1 and bool(tx := self.ui.anst_combo.currentText()) and (BahnhofElement('Anst', tx) not in self.bahnhofgraph)
        self.ui.anst_rename_button.setEnabled(en)

    def group_elements(self, level: str, element: Optional[str] = None):
        """
        Gruppiert die ausgewählten Elemente zu einer übergeordneten Gruppe.
        """

        if level == 'Anst':
            gleise = self.get_agl_selection()
            table_model = self.agl_table_model
        elif level in {'Bf', 'Bft', 'Bs'}:
            gleise = self.get_gl_selection()
            table_model = self.gl_table_model
        else:
            raise ValueError(f'Invalid level {level}')

        if table_model.group_elements(gleise, level, element):
            pass
            # self.update_widgets()

    def ungroup_element(self, level: str):
        if level == 'Anst':
            sel = self.get_agl_selection()
            table_model = self.agl_table_model
        elif level in {'Bf', 'Bft', 'Bs'}:
            sel = self.get_gl_selection()
            table_model = self.gl_table_model
        else:
            raise ValueError(f'Invalid level {level}')

        table_model.ungroup_elements(sel, level)

    def rename_element(self, level: str, combo: QtWidgets.QComboBox):
        """
        Renames an element in the graph and updates the model accordingly.
        """

        if level == 'Anst':
            sel = self.get_agl_selection()
            table_model = self.agl_table_model
        elif level in {'Bf', 'Bft', 'Bs'}:
            sel = self.get_gl_selection()
            table_model = self.gl_table_model
        else:
            raise ValueError(f'Invalid level {level}')

        sel = {table_model.row_data[gl][level] for gl in sel}
        if len(sel) != 1:
            return

        old = sel.pop()
        new = combo.currentText()

        table_model.rename_element(level, old, new)

    @Slot()
    def gl_table_model_changed(self):
        if self.in_update:
            return
        self.update_lists_and_states(levels={'Bf', 'Bft', 'Bs', 'Gl'})

    @Slot()
    def agl_table_model_changed(self):
        if self.in_update:
            return
        self.update_lists_and_states(levels={'Anst', 'Agl'})

    @Slot()
    def bf_group_button_clicked(self):
        self.group_elements('Bf', self.ui.bf_combo.currentText())

    @Slot()
    def bft_group_button_clicked(self):
        self.group_elements('Bft', self.ui.bft_combo.currentText())

    @Slot()
    def bs_group_button_clicked(self):
        self.group_elements('Bs', self.ui.bs_combo.currentText())

    @Slot()
    def bf_ungroup_button_clicked(self):
        self.ungroup_element('Bf')

    @Slot()
    def bft_ungroup_button_clicked(self):
        self.ungroup_element('Bft')

    @Slot()
    def bs_ungroup_button_clicked(self):
        self.ungroup_element('Bs')

    @Slot()
    def bf_rename_button_clicked(self):
        self.rename_element('Bf', self.ui.bf_combo)

    @Slot()
    def bft_rename_button_clicked(self):
        self.rename_element('Bft', self.ui.bft_combo)

    @Slot()
    def bs_rename_button_clicked(self):
        self.rename_element('Bs', self.ui.bs_combo)

    @Slot()
    def bf_combo_index_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def bft_combo_index_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def bs_combo_index_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def gl_combo_index_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def bf_combo_text_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def bft_combo_text_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def bs_combo_text_changed(self):
        self.update_gl_widget_states()

    @Slot()
    def gl_combo_text_changed(self):
        self.gl_table_filter.beginResetModel()
        try:
            self.gl_table_filter.filter_text = self.ui.gl_combo.currentText().casefold()
        finally:
            self.gl_table_filter.endResetModel()
        self.adjust_geometry()

    @Slot()
    def anst_group_button_clicked(self):
        self.group_elements('Anst', self.ui.anst_combo.currentText())

    @Slot()
    def anst_ungroup_button_clicked(self):
        self.ungroup_element('Anst')

    @Slot()
    def anst_rename_button_clicked(self):
        self.rename_element('Anst', self.ui.anst_combo)

    @Slot()
    def anst_combo_index_changed(self):
        self.update_agl_widget_states()

    @Slot()
    def agl_combo_index_changed(self):
        self.update_agl_widget_states()

    @Slot()
    def anst_combo_text_changed(self):
        self.update_agl_widget_states()

    @Slot()
    def agl_combo_text_changed(self):
        self.agl_table_filter.beginResetModel()
        try:
            self.agl_table_filter.filter_text = self.ui.agl_combo.currentText().casefold()
        finally:
            self.agl_table_filter.endResetModel()
        self.adjust_geometry()
