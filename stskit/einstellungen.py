"""
datenstrukturen und fenster für anschlussmatrix


"""

import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Type, Union

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot

from stskit.zugschema import Zugschema, ZugkategorienModell
from stskit.anlage import Anlage
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class EinstellungenWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale

        self.in_update = True
        self.ui = Ui_EinstellungenWindow()
        self.ui.setupUi(self)

        self.setWindowTitle(f"Einstellungen {self.anlage.anlage.name}")

        self.zugschema = Zugschema()
        self.zugschema.load_config(self.anlage.zugschema.name)
        self.zugschema_modell = ZugkategorienModell(None, zugschema=self.zugschema)
        self.ui.zugschema_details_table.setModel(self.zugschema_modell)
        self.ui.zugschema_name_combo.currentIndexChanged.connect(self.zugschema_changed)

        self.update_widgets()
        self.in_update = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    def update_widgets(self):
        self.in_update = True

        schemas = sorted(Zugschema.schemas.keys())
        self.ui.zugschema_name_combo.clear()
        self.ui.zugschema_name_combo.addItems(schemas)
        self.ui.zugschema_name_combo.setCurrentText(self.anlage.zugschema.name)

        self.in_update = False

        self.ui.zugschema_details_table.resizeColumnsToContents()
        self.ui.zugschema_details_table.resizeRowsToContents()

    @pyqtSlot()
    def zugschema_changed(self):
        zugschema = self.ui.zugschema_name_combo.currentText()

        changed = zugschema != self.anlage.zugschema.name

        if changed:
            self.zugschema.load_config(zugschema)
            self.zugschema_modell.update()

    @pyqtSlot()
    def accept(self):
        self.anlage.zugschema.load_config(self.zugschema.name)
        self.close()

    @pyqtSlot()
    def reject(self):
        self.close()
