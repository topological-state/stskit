"""
Ereignisticker (GUI-Version)

Dieses Modul implementiert ein Fenster mit einem Ereignisticker für das STSdispo Hauptprogramm.

Das Fenster ist in der TickerWindow-klasse implementiert.
Die EreignisTabelleModell-Klasse sammelt die Ereignisse und stellt über die Modellschnittstelle zur Verfügung.
"""

import copy
import logging
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore
from PySide6.QtCore import Slot, QModelIndex, QSortFilterProxyModel, QAbstractTableModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QAbstractItemView

from stskit.plugin.stsobj import Ereignis, time_to_minutes, time_to_seconds
from stskit.zentrale import DatenZentrale
from stskit.qt.ui_ticker import Ui_EreignisTickerWidget

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

EREIGNISART_QCOLOR_SVG = {
    "einfahrt": QColor("orchid"),
    "ausfahrt": QColor("dodgerblue"),
    "ersatz": QColor("dodgerblue"),
    "rothalt": QColor("tomato"),
    "fahrt": QColor("limegreen"),
    "ankunft": QColor("skyblue"),
    "durchfahrt": QColor("skyblue"),
    "bereit": QColor("khaki"),
    "abfahrt": QColor("limegreen"),
    "kuppeln": QColor("coral"),
    "flügeln": QColor("orange"),
    "default": QColor("gray")
}

class EreignisTabelleModell(QAbstractTableModel):
    MAX_EREIGNISSE = 1000
    
    def __init__(self):
        super().__init__()
        self.ereignis_limit: int = self.MAX_EREIGNISSE
        self.ereignisse: list[Ereignis] = []
        self.min_zeit: int = 0
        self._columns: list[str] = ['zeit', 'ereignis', 'zug', 'von', 'nach', 'gleis', 'status']
        self._column_titles: dict[str, str] = {
            'zeit': 'Zeit',
            'ereignis': 'Ereignis', 
            'zug': 'Zug', 
            'von': 'Von', 
            'nach': 'Nach', 
            'gleis': 'Gleis', 
            'status': 'Status',
        }
        self._data_methods: dict[int, Callable[[Ereignis, str], Any]] = {
            QtCore.Qt.ItemDataRole.DisplayRole: self._data_display,
            QtCore.Qt.ItemDataRole.UserRole: self._data_user,
            QtCore.Qt.ItemDataRole.ForegroundRole: self._data_foreground,
            QtCore.Qt.ItemDataRole.CheckStateRole: self._data_check_state,
            QtCore.Qt.ItemDataRole.TextAlignmentRole: self._data_text_alignment,
        }

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self.ereignisse)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        ereignis = self.ereignisse[index.row()]
        col = self._columns[index.column()]
        try:
            return self._data_methods[role](ereignis, col)
        except KeyError:
            return None

    def _data_display(self, ereignis: Ereignis, col: str, ) -> Any:
        match col:
            case 'zeit':
                return ereignis.zeit.time().isoformat(timespec='seconds')
            case 'ereignis':
                return ereignis.art.title()
            case 'zug':
                return ereignis.name
            case 'status':
                if ereignis.verspaetung:
                    return f"{ereignis.verspaetung:+}"
                else:
                    return ""
            case 'von':
                return ereignis.von
            case 'nach':
                return ereignis.nach
            case 'gleis':
                if ereignis.gleis == ereignis.plangleis:
                    return ereignis.gleis or ""
                else:
                    return f"{ereignis.gleis} /{ereignis.plangleis}/"
            case _:
                return ""

    def _data_user(self, ereignis: Ereignis, col: str, ) -> Any:
        match col:
            case 'zeit':
                return time_to_seconds(ereignis.zeit)
            case 'ereignis':
                return ereignis.art
            case 'zug':
                return ereignis.nummer
            case 'status':
                return ereignis.verspaetung or 0
            case 'von':
                return ereignis.von or ""
            case 'nach':
                return ereignis.nach or ""
            case 'gleis':
                return ereignis.gleis or ""
            case _:
                return ""

    def _data_foreground(self, ereignis: Ereignis, col: str, ) -> Any:
        try:
            return EREIGNISART_QCOLOR_SVG[ereignis.art]
        except KeyError:
            return EREIGNISART_QCOLOR_SVG["default"]

    def _data_check_state(self, ereignis: Ereignis, col: str, ) -> Any:
        match col:
            case 'gleis':
                if ereignis.amgleis:
                    return QtCore.Qt.CheckState.Checked
                else:
                    return QtCore.Qt.CheckState.Unchecked
            case _:
                return None

    def _data_text_alignment(self, ereignis: Ereignis, col: str, ) -> Any:
        return QtCore.Qt.AlignmentFlag.AlignHCenter + QtCore.Qt.AlignmentFlag.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self._column_titles[self._columns[section]])
            if orientation == QtCore.Qt.Orientation.Vertical:
                return section

        return None

    def add_ereignis(self, ereignis: Ereignis):
        if ereignis.art == "abfahrt" and ereignis.amgleis:
            ereignis = copy.copy(ereignis)
            ereignis.art = "bereit"
        elif ereignis.art == "ankunft" and not ereignis.amgleis:
            ereignis = copy.copy(ereignis)
            ereignis.art = "durchfahrt"
        elif ereignis.art == "wurdegruen":
            ereignis = copy.copy(ereignis)
            ereignis.art = "fahrt"
        elif ereignis.art == "fluegeln":
            ereignis = copy.copy(ereignis)
            ereignis.art = "flügeln"

        if ereignis not in self.ereignisse:
            self.beginResetModel()
            self.ereignisse.append(ereignis)
            if len(self.ereignisse) > self.ereignis_limit:
                self.ereignisse = self.ereignisse[-self.ereignis_limit:]
            self.endResetModel()


class EreignisTabelleFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent=...):
        super().__init__(parent)
        self._simzeit: int = 0
        self._zug_filter: str = ""
        self._nachlaufzeit: int = 120

    @property
    def simzeit(self) -> int:
        return self._simzeit

    @simzeit.setter
    def simzeit(self, minuten: int):
        self._simzeit = minuten

    @property
    def nachlaufzeit(self) -> int:
        return self._nachlaufzeit

    @nachlaufzeit.setter
    def nachlaufzeit(self, minuten: int):
        self._nachlaufzeit = minuten
    
    @property
    def zug_filter(self) -> str:
        return self._zug_filter
    
    @zug_filter.setter
    def zug_filter(self, value: str):
        self._zug_filter = value.casefold()

    def filterAcceptsRow(self, source_row, source_parent):
        model: EreignisTabelleModell | None = None
        while model is None:
            source = self.sourceModel()
            if isinstance(source, EreignisTabelleModell):
                model = source
                break

        try:
            ereignis: Ereignis = model.ereignisse[source_row]
        except (IndexError, KeyError):
            return False

        if self._zug_filter and self._zug_filter not in ereignis.name.casefold():
            return False
        
        if self.simzeit - time_to_minutes(ereignis.zeit)  > self._nachlaufzeit > 0:
            return False

        return True


class TickerWindow(QWidget):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.plugin_ereignis.register(self.add_ereignis)
        
        self.ui = Ui_EreignisTickerWidget()
        self.ui.setupUi(self)
        self.setWindowTitle("Ereignisticker")

        self.model = EreignisTabelleModell()
        self.filter = EreignisTabelleFilterProxy(self)
        self.filter.setSourceModel(self.model)
        self.filter.setSortRole(Qt.ItemDataRole.UserRole)
        self.filter.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filter.setDynamicSortFilter(True)

        self.ui.ticker_view.setModel(self.filter)
        self.ui.ticker_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ui.ticker_view.setSortingEnabled(True)
        self.ui.ticker_view.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)

        self.ui.auto_scroll_checkbox.setCheckState(Qt.CheckState.Checked)
        self.ui.nachlaufzeit_spin.setValue(self.filter.nachlaufzeit)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)
        self.ui.filter_zug_edit.textEdited.connect(self.filter_zug_changed)
        self.ui.filter_loeschen_button.clicked.connect(self.filter_loeschen_clicked)

    def closeEvent(self, event, /):
        self.zentrale.plugin_ereignis.unregister(self)
        super().closeEvent(event)

    def add_ereignis(self, *args, ereignis: Ereignis, **kwargs):
        self.filter.simzeit = self.zentrale.simzeit_minuten
        self.model.add_ereignis(ereignis)
        self.ui.ticker_view.resizeColumnsToContents()
        self.ui.ticker_view.resizeRowsToContents()
        if self.ui.auto_scroll_checkbox.checkState() == Qt.CheckState.Checked:
            self.ui.ticker_view.scrollToBottom()

    @Slot()
    def nachlaufzeit_changed(self):
        try:
            self.filter.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    @Slot()
    def filter_zug_changed(self):
        self.filter.zug_filter = self.ui.filter_zug_edit.text()
        self.model.layoutChanged.emit()

    @Slot()
    def filter_loeschen_clicked(self):
        self.ui.filter_zug_edit.clear()
        self.filter.zug_filter = ""
        self.model.layoutChanged.emit()

    @Slot()
    def autoscroll_checkbox_clicked(self):
        if self.ui.auto_scroll_checkbox.checkState() == Qt.CheckState.Checked:
            self.ui.ticker_view.scrollToBottom()
