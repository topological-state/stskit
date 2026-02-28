"""
dispoeditor-Modul

Das dispoeditor-Modul deklariert ein Qt-Tabellenmodell für das Dispositionsjournal.
Dadurch kann das Journal eingesehen (und in einer späteren Version) bearbeitet werden.
"""
from stskit.dispo.betrieb import Betrieb

import logging
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import QModelIndex, QAbstractTableModel, Qt
from PySide6.QtGui import QColor

from stskit.dispo.anlage import Anlage
from stskit.model.journal import Journal, JournalIDType, JournalEntryGroup, JournalEntry

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class DispoModell(QAbstractTableModel):
    """
    Datenmodell für Dispotabelle

    Listet die einzelnen Dispobefehle in einem benutzerfreundlichen Format.
    """

    def __init__(self, anlage: Anlage, betrieb: Betrieb):
        super().__init__()

        self._anlage = anlage
        self._betrieb = betrieb
        self._column_titles: dict[str, str] = {#'zid': 'ID',
                                               'zug': 'Zug',
                                               'gleis': 'Gleis',
                                               'typ': 'Befehl',
                                               #'rzid': 'Gegen-ID',
                                               'rzug': 'Gegenzug',
                                               'rgleis': 'Gegengleis',
                                               #'details': 'Details',
                                               }
        self._columns: list[str] = list(self._column_titles.keys())
        self._rows: list[JournalIDType] = []
        self._data: dict[JournalIDType, dict[str, str | int]] = {}

    def _get_zug_data(self, zid: int) -> dict[str, str | int]:
        try:
            zug = self._anlage.zuggraph.nodes[zid]
            result = dict(zid=zid, zug=zug.name)
        except (IndexError, KeyError):
            result = dict(zid=zid, zug=f"({zid})")
        return result

    def _get_journal_data(self,
                          zid: int,
                          entry: JournalEntry | JournalEntryGroup,
                          ) -> dict[str, str | int]:
        result = {}

        if isinstance(entry, JournalEntryGroup):
            for _entry in entry.entries:
                result.update(self._get_journal_data(zid, _entry))

        elif isinstance(entry, JournalEntry):
            if entry.target_node.zid == zid and entry.target_graph == 'ereignisgraph':
                node_data = self._betrieb.ereignisgraph.nodes[entry.target_node]
                result['gleis'] = node_data.gleis
                for edge, edge_data in entry.added_edges.items():
                    if edge[0].zid != zid and edge_data.get('typ') == 'A':
                        node_data = self._betrieb.ereignisgraph.nodes[edge[0]]
                        zug_data = self._get_zug_data(node_data.zid)
                        result['rzid'] = node_data.zid
                        result['rzug'] = zug_data.get('zug', '')
                        result['rgleis'] = node_data.gleis
                        break

        return result

    def update(self):
        self.beginResetModel()
        self._rows = sorted(self.dispo_journal().entries.keys())

        for jid in self._rows:
            entry = self.dispo_journal().entries[jid]
            data = {'typ': jid.typ,
                    'zid': jid.zid,
                    'gleis': jid.bst,
                    'zug': '',
                    'rzug': '',
                    'rzid': '',
                    'rgleis': '',
                    'details': '',
                    }
            data.update(self._get_zug_data(jid.zid))
            data.update(self._get_journal_data(jid.zid, entry))
            self._data[jid] = data

        self.endResetModel()

    def get_data(self,
                 row: int | None = None,
                 jid: JournalIDType | None = None,
                 ) -> dict[str, str | int]:
        if row is not None:
            jid = self._rows[row]
        return self._data[jid]

    def dispo_journal(self) -> Journal:
        return self._betrieb.journal

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
            _data = self._data[jid]
            _item = _data[col]
        except (IndexError, KeyError):
            return None

        if role == Qt.UserRole:
            return _item

        if role == Qt.DisplayRole:
            return str(_item)

        elif role == Qt.TextAlignmentRole:
            if col in {'typ', 'details'}:
                return Qt.AlignVCenter
            else:
                return Qt.AlignHCenter + Qt.AlignVCenter

        elif role == QtCore.Qt.ForegroundRole:
            zug = self._anlage.zuggraph.nodes[jid.zid]
            zugschema = self._anlage.zugschema
            if zug.sichtbar:
                rgb = zugschema.zugfarbe_rgb(zug)
                farbe = QColor(*rgb)
            elif zug.gleis:
                rgb = zugschema.zugfarbe_rgb(zug)
                farbe = QColor(*rgb)
            else:
                farbe = QColor("gray")
            return farbe

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
