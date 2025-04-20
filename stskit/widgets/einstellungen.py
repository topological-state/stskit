"""
Einstellungsfenster

- Auswahl des Zugschemas

"""

import logging
import os
from pathlib import Path

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot

from stskit.model.zugschema import Zugschema, ZugschemaBearbeitungModell
from stskit.dispo.anlage import Anlage
from stskit.zentrale import DatenZentrale
from stskit.widgets.bahnhofeditor import BahnhofEditor

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

        p = Path(__file__).with_suffix('.md')
        try:
            with open(p) as f:
                hilfe = f.read()
        except OSError as e:
            self.ui.hilfe_text.setText(str(e))
        else:
            self.ui.hilfe_text.setMarkdown(hilfe)

        try:
            self.setWindowTitle(f"Einstellungen {self.anlage.anlageninfo.name}")
        except AttributeError:
            self.setWindowTitle(f"Einstellungen")

        self.bahnhof_editor = BahnhofEditor(zentrale.anlage, parent=self, ui=self.ui)

        self.zugschema = Zugschema()
        self.zugschema.load_config(self.anlage.zugschema.name)
        self.zugschema_namen_nach_titel = {titel: name for name, titel in Zugschema.schematitel.items()}
        self.zugschema_modell = ZugschemaBearbeitungModell(None, zugschema=self.zugschema)
        self.ui.zugschema_details_table.setModel(self.zugschema_modell)
        self.ui.zugschema_name_combo.currentIndexChanged.connect(self.zugschema_changed)

        self.update_widgets()
        self.in_update = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    def update_widgets(self):
        self.in_update = True

        self.bahnhof_editor.update_widgets()

        schemas = sorted(self.zugschema_namen_nach_titel.keys())
        self.ui.zugschema_name_combo.clear()
        self.ui.zugschema_name_combo.addItems(schemas)
        self.ui.zugschema_name_combo.setCurrentText(self.zugschema.titel)

        self.in_update = False

        self.ui.zugschema_details_table.resizeColumnsToContents()
        self.ui.zugschema_details_table.resizeRowsToContents()

    @pyqtSlot()
    def zugschema_changed(self):
        if self.in_update:
            return

        titel = self.ui.zugschema_name_combo.currentText()
        try:
            name = self.zugschema_namen_nach_titel[titel]
        except KeyError:
            return

        changed = name != self.zugschema.name

        if changed:
            self.zugschema.load_config(name)
            self.zugschema_modell.update()
            self.ui.zugschema_details_table.resizeColumnsToContents()
            self.ui.zugschema_details_table.resizeRowsToContents()

    @pyqtSlot()
    def apply(self):
        self.bahnhof_editor.apply()
        self.anlage.zugschema.load_config(self.zugschema.name, self.anlage.anlageninfo.region)
        self.zentrale.notify_anlage({'zugschema', 'bahnhofgraph'})

    @pyqtSlot()
    def accept(self):
        self.apply()
        self.close()

    @pyqtSlot()
    def reset(self):
        self.bahnhof_editor.reset()
        self.zugschema.load_config(self.anlage.zugschema.name)
        self.zugschema_modell.update()

    @pyqtSlot()
    def reject(self):
        self.reset()
        self.close()
