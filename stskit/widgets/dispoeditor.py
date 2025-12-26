from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PySide6 import QtCore
from PySide6.QtCore import Slot, QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QAbstractTableModel, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QAbstractItemView

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.journal import Journal, JournalIDType
from stskit.model.zuggraph import ZugGraphNode


class DispoModell(QAbstractTableModel):
    """
    Datenmodell für Dispotabelle
    """

    def __init__(self, anlage: Anlage):
        super().__init__()

        self._anlage = anlage
        self._columns: List[str] = ['typ', 'zid', 'gleis', 'zug', 'details']
        self._column_titles: Dict[str, str] = {'typ': 'Typ', 'zid': 'ID', 'gleis': 'Gleis', 'zug': 'Zug', 'details': 'Details'}
        self._rows: List[JournalIDType] = []
        self._summary: Dict[JournalIDType, Dict[Tuple[Hashable, Hashable], Set[str]]] = {}
        # self._zid: Dict[JournalIDType, Set[int]] = {}
        # self._zug: Dict[JournalIDType, Set[str]] = {}
        # self._bst: Dict[JournalIDType, Set[BahnhofElement]] = {}
        self._changes: Dict[JournalIDType, str] = {}

    def format_change(self, change: Dict[Tuple[Hashable, Hashable], Set[str]]) -> str:
        texts = []
        elements = [(*element, flags) for element, flags in change.items()]
        elements = sorted(elements, key=lambda x: (x[1].zid, x[1].zeit))
        for element in elements:
            graph, node, flags = element
            flags_text = "".join(sorted(flags, reverse=True))
            if graph == 'ereignisgraph':
                node_text = f"{node.zid} {node.typ} {node.zeit}"
            elif graph == 'zielgraph':
                node_text = f"{node.zid} {node.ort} {node.zeit}"
            else:
                continue

            text = f"({node_text}) {flags_text}"
            texts.append(text)

        return ", ".join(texts)

    def update(self):
        self.beginResetModel()
        self._rows = sorted(self.dispo_journal().entries.keys())
        self._summary = {jid: self.dispo_journal().entries[jid].summary() for jid in self._rows}
        for jid, change in self._summary.items():
            self._changes[jid] = self.format_change(change)
        self.endResetModel()

    def dispo_journal(self) -> Journal:
        return self._anlage.dispo_journal

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        """
        Daten pro Zelle ausgeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - UserRole gibt die originaldaten aus (zum sortieren benötigt).
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - CheckStateRole gibt an, ob ein zug am gleis steht.
            - ForegroundRole färbt die einträge ein.
            - TextAlignmentRole richtet den text aus.
        :return: verschiedene
        """

        if not index.isValid():
            return None

        try:
            jid = self._rows[index.row()]
            col = self._columns[index.column()]
        except (IndexError, KeyError):
            return None

        try:
            zug = self._anlage.zuggraph.nodes[jid.zid]
        except (IndexError, KeyError):
            zug = ZugGraphNode(zid=jid.zid, name="(?)")

        if role == Qt.UserRole:
            if col == 'typ':
                return jid.typ
            elif col == 'zid':
                return jid.zid
            elif col == 'gleis':
                return jid.bst
            elif col == 'zug':
                return zug.name
            elif col == 'details':
                return self._summary.get(jid)
            else:
                return None

        if role == Qt.DisplayRole:
            if col == 'typ':
                return jid.typ
            elif col == 'zid':
                return jid.zid
            elif col == 'gleis':
                return str(jid.bst)
            elif col == 'zug':
                return zug.name
            elif col == 'details':
                return str(self._changes.get(jid))
            else:
                return None

        elif role == Qt.TextAlignmentRole:
            if col == 'details':
                return Qt.AlignVCenter
            else:
                return Qt.AlignHCenter + Qt.AlignVCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile und -spalte aus.
        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den spaltentitel oder die zug-id aus.
        :return:
        """
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._column_titles[self._columns[section]]
            elif orientation == Qt.Vertical:
                return section

        return None
