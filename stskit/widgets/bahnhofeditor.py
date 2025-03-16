import logging
from typing import AbstractSet, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Type, Union


from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PyQt5 import Qt, QtCore
from PyQt5.QtCore import pyqtSlot, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QStringListModel
from PyQt5.QtWidgets import QWidget, QTableView, QVBoxLayout

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement, BahnsteigGraphNode, BahnsteigGraphEdge
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


class BahnhofEditor:
    def __init__(self, anlage: Anlage, ui: Ui_EinstellungenWindow):
        super().__init__()
        self.anlage = anlage
        self.bahnhofgraph = anlage.bahnhofgraph.copy(as_view=False)
        self.ui = ui

        self.gl_table_model = BahnhofEditorModel(self.bahnhofgraph)
        self.ui.gl_table_view.setModel(self.gl_table_model)
        self.ui.gl_table_view.setSelectionMode(Qt.QAbstractItemView.MultiSelection)
        self.ui.gl_table_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)

        self.gl_model = QStringListModel()
        self.ui.gl_combo.setModel(self.gl_model)

        self.bs_model = QStringListModel()
        self.ui.bs_combo.setModel(self.bs_model)

        self.bft_model = QStringListModel()
        self.ui.bft_combo.setModel(self.bft_model)

        self.bf_model = QStringListModel()
        self.ui.bf_combo.setModel(self.bf_model)

    def update_widgets(self):
        # Update the widgets based on the current state of the anlage
        self.gl_table_model.update()
        self.ui.gl_table_view.resizeColumnsToContents()
        self.ui.gl_table_view.resizeRowsToContents()

        self.gl_model.setStringList(sorted((gl.name for gl in self.bahnhofgraph.list_by_type({'Gl'}))))
        self.bs_model.setStringList(sorted((bs.name for bs in self.bahnhofgraph.list_by_type({'Bs'}))))
        self.bft_model.setStringList(sorted((bft.name for bft in self.bahnhofgraph.list_by_type({'Bft'}))))
        self.bf_model.setStringList(sorted((bf.name for bf in self.bahnhofgraph.list_by_type({'Bf'}))))
