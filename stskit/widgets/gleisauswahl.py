"""
Modell für Gleisauswahl in Qt5-Treeview-Widget

Das Modul deklariert eine GleisauswahlModell-Klasse,
mit der in einem Qt5-Treeview-Widget Gleise asugewählt werden können.
"""

import logging
from typing import AbstractSet, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Type, Union

import networkx as nx

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QModelIndex

from stskit.dispo.anlage import Anlage
from stskit.graphs.bahnhofgraph import Zielort

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisauswahlItem:
    """
    Repräsentation eines Gleises bzw. der zugeordneten Betriebselemente.

    Wird intern von GleisauswahlModell verwendet.
    """

    TYPEN = {"root", "Kat", "Anst", "Agl", "Bf", "Bft", "Bs", "Gl"}

    def __init__(self, modell: 'GleisauswahlModell', typ: str, name: str):
        super().__init__()
        assert typ in self.TYPEN, f"Unbekannter GleisauswahlItem-Typ {typ}"
        self.modell = modell
        self.typ = typ
        self.name = name
        self.sperrung: bool = False
        self._column_count = 2 if self.typ == "Gleis" else 1
        self._parent = None
        self._children = []
        self._row = 0
        self._check_state: bool = False

    def columnCount(self) -> int:
        return self._column_count

    def childCount(self) -> int:
        return len(self._children)

    def child(self, row: int) -> Optional['GleisauswahlItem']:
        try:
            return self._children[row]
        except IndexError:
            return None

    def children(self) -> Iterable['GleisauswahlItem']:
        for child in self._children:
            yield child

    def parent(self):
        return self._parent

    def row(self):
        return self._row

    def addChild(self, child: 'GleisauswahlItem'):
        child._parent = self
        child._row = len(self._children)
        self._children.append(child)
        self._column_count = max(child.columnCount(), self._column_count)

    def checkState(self) -> QtCore.Qt.CheckState:
        if len(self._children):
            checked = 0
            unchecked = 0
            undefined = 0
            for item in self._children:
                state = item.checkState()
                if state == QtCore.Qt.Checked:
                    checked += 1
                elif state == QtCore.Qt.Unchecked:
                    unchecked += 1
                else:
                    undefined += 1

            if checked == len(self._children):
                return QtCore.Qt.Checked
            elif unchecked == len(self._children):
                return QtCore.Qt.Unchecked
            else:
                return QtCore.Qt.PartiallyChecked
        else:
            return QtCore.Qt.Checked if self._check_state else QtCore.Qt.Unchecked

    def setCheckState(self, check_state: QtCore.Qt.CheckState):
        if len(self._children) == 0:
            self._check_state = check_state == QtCore.Qt.Checked

    def flags(self):
        flags = QtCore.Qt.ItemIsEnabled

        if self.name:
            flags = flags | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable
        if self.typ == "Gl":
            flags = flags | QtCore.Qt.ItemNeverHasChildren
        else:
            flags = flags | QtCore.Qt.ItemIsAutoTristate

        return flags

    def data(self, column, role):
        if role == QtCore.Qt.DisplayRole:
            if column == 0:
                return self.name
            if column == 1:
                return ""

        elif role == QtCore.Qt.CheckStateRole:
            if column == 0:
                return self.checkState()
            elif column == 1 and self.typ == "Gl":
                return QtCore.Qt.Checked if self.sperrung else QtCore.Qt.Unchecked

        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        column = index.column()
        if role == QtCore.Qt.EditRole:
            return False
        elif role == QtCore.Qt.CheckStateRole:
            if column == 0:
                self.setCheckState(value)
                if len(self._children):
                    for child in self._children:
                        child_index = self.modell.index(child._row, column, index)
                        child.setData(child_index, value, role)
                self.modell.dataChanged.emit(index, index)
                return True
            elif column == 1 and self.typ == "Gl":
                self.sperrung = value != QtCore.Qt.Unchecked
                self.modell.dataChanged.emit(index, index)
                return True

        return False


class GleisauswahlModell(QtCore.QAbstractItemModel):
    """
    Modell für Gleisauswahl.

    Um in einem Treeview eine Gleisauswahl anzubieten,
    wird dem Treeview eine Instanz dieser Klasse zugeordnet.

    Die Daten werden über die Methoden
    gleise_definieren, set_auswahl, get_auswahl, set_sperrungen, get_sperrungen ein- und ausgelesen.
    """

    def __init__(self, parent: Optional[QtCore.QObject]):
        super(GleisauswahlModell, self).__init__(parent)
        self._root = GleisauswahlItem(self, "root", "")

        self.alle_gleise: Set[Zielort] = set()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = ...) -> int:
        if parent.isValid():
            return parent.internalPointer().childCount()
        else:
            return self._root.childCount()

    def index(self, row: int, column: int, _parent: QModelIndex = ...) -> QModelIndex:
        if not _parent or not _parent.isValid():
            parent = self._root
        else:
            parent = _parent.internalPointer()

        if not QtCore.QAbstractItemModel.hasIndex(self, row, column, _parent):
            return QtCore.QModelIndex()

        child = parent.child(row)
        if child:
            return QtCore.QAbstractItemModel.createIndex(self, row, column, child)
        else:
            return QtCore.QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        if child.isValid():
            p = child.internalPointer().parent()
            if p and p is not self._root:
                return QtCore.QAbstractItemModel.createIndex(self, p.row(), 0, p)
        return QtCore.QModelIndex()

    def addChild(self, node: GleisauswahlItem, _parent: QModelIndex) -> None:
        if not _parent or not _parent.isValid():
            parent = self._root
        else:
            parent = _parent.internalPointer()
        parent.addChild(node)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                if section == 0:
                    return "Gleis"
                elif section == 1:
                    return "Sperrung"

        return None

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled

        node: GleisauswahlItem = index.internalPointer()
        return node.flags()

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        node: GleisauswahlItem = index.internalPointer()
        return node.data(index.column(), role)

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if not index.isValid():
            return False

        node: GleisauswahlItem = index.internalPointer()

        if role == QtCore.Qt.CheckStateRole:
            node.setData(index, value, role)

            parent_index = index
            while True:
                parent_index = self.parent(parent_index)
                if parent_index.isValid():
                    self.dataChanged.emit(parent_index, parent_index)
                else:
                    break

            return True

        return False

    def gleise_definieren(self, anlage: Anlage, bahnsteige=True, anschluesse=False) -> None:
        """
        Gleisliste aus Anlagendefinition übernehmen.

        Bahnsteiggleise und Anschlüsse können gefiltert werden.

        :param anlage: Anlagendefinition
        :param bahnsteige: Bahnsteige inkludieren?
        :param anschluesse: Einfahrten inkludieren?
        :return: kein
        """

        self.beginResetModel()

        self._root = GleisauswahlItem(self, "root", "")

        self.alle_gleise = set()

        items: Dict[Tuple[str, str], GleisauswahlItem] = {}

        if anschluesse:
            alle_agl = (node for node in anlage.bahnhofgraph.nodes if node[0] == 'Agl')
            self.alle_gleise.update(alle_agl)

            anschluesse_item = GleisauswahlItem(self, "Kat", "Anschlüsse")
            self._root.addChild(anschluesse_item)

            for anst in anlage.bahnhofgraph.anschlussstellen():
                anst_item = GleisauswahlItem(self, "Anst", anst)
                anschluesse_item.addChild(anst_item)
                for agl in sorted(anlage.bahnhofgraph.anschlussgleise(anst)):
                    agl_item = GleisauswahlItem(self, "Agl", agl)
                    anst_item.addChild(agl_item)

        if bahnsteige:
            alle_gl = (node for node in anlage.bahnhofgraph.nodes if node[0] == 'Gl')
            self.alle_gleise.update(alle_gl)

            bahnsteige_item = GleisauswahlItem(self, "Kat", "Bahnsteige")
            self._root.addChild(bahnsteige_item)
            items[('Bst', 'Bf')] = bahnsteige_item

            for node1, node2 in nx.dfs_edges(anlage.bahnhofgraph, source=('Bst', 'Bf')):
                item = GleisauswahlItem(self, node2[0], node2[1])
                items[node2] = item
                items[node1].addChild(item)

        self.endResetModel()

    def gleis_items(self, parent: Optional[GleisauswahlItem] = None, level: int = 0) -> Iterable[GleisauswahlItem]:
        """
        Zu einem Parent gehörende Gleiselemente auflisten.

        :param parent:
        :param level:
        :return: Generator
        """

        if parent is None:
            parent = self._root
        for i in range(parent.childCount()):
            item = parent.child(i)
            if item.childCount() > 0:
                yield from self.gleis_items(parent=item, level=level+1)
            else:
                yield item

    def set_auswahl(self, gleise: Union[AbstractSet[Zielort], Iterable[Zielort]]) -> None:
        """
        Auswahlstatus aller Gleise auf einmal setzen.

        :param gleise: Set von Gleisnamen. Nicht gelistete Gleise werden abgewählt.
        :return: kein
        """

        gleise = set(gleise)
        for item in self.gleis_items():
            state = QtCore.Qt.Checked if item.name in gleise else QtCore.Qt.Unchecked
            item.setCheckState(state)

        self.dataChanged.emit(self.index(0, 0, QModelIndex()),
                              self.index(self._root.columnCount() - 1, self._root.childCount() - 1, QModelIndex()))

    def get_auswahl(self) -> Set[Zielort]:
        """
        Auswahlstatus aller Gleise auf einmal auslesen.

        :return: Set von Gleisnamen
        """

        gleise = set()
        for item in self.gleis_items():
            element = Zielort(item.typ, item.name)
            state = item.checkState()
            if element in self.alle_gleise and state == QtCore.Qt.Checked:
                gleise.add(element)

        return gleise

    def set_sperrungen(self, gleissperrungen: AbstractSet[Zielort]) -> None:
        """
        Sperrungsstatus aller Gleise auf einmal setzen.

        :param gleissperrungen: Set von (Gleistyp, Gleisnamen)-Tupeln.
            Gelistete Gleise werden gesperrt, nicht gelistete entsperrt.
        :return:
        """

        for item in self.gleis_items():
            item.sperrung = Zielort(item.typ, item.name) in gleissperrungen

    def get_sperrungen(self) -> Set[Zielort]:
        """
        Sperrungsstatus aller Gleise auf einmal auslesen..

        :param gleissperrungen: Set von (Gleistyp, Gleisnamen)-Tupeln.
            Gelistete Gleise werden gesperrt, nicht gelistete entsperrt.
        :return:
        """

        sperrungen = (Zielort(item.typ, item.name) for item in self.gleis_items() if item.sperrung and item.typ == "Gl")
        return set(sperrungen)
