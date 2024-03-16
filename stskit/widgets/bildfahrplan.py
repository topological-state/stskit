import math
import itertools
import logging
from typing import Dict, List, Optional, Tuple, Type

import matplotlib as mpl
from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import networkx as nx
from PyQt5 import QtWidgets

from stskit.auswertung import Auswertung
from stskit.dispo.anlage import Anlage
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung, FesteVerspaetung, \
    AnkunftAbwarten, AbfahrtAbwarten, ZugAbwarten
from stskit.slotgrafik import hour_minutes_formatter
from stskit.interface.stsplugin import PluginClient
from stskit.interface.stsobj import time_to_minutes, format_verspaetung
from stskit.plots.bildfahrplan import BildfahrplanPlot
from stskit.zentrale import DatenZentrale
from stskit.zugschema import Zugbeschriftung

from stskit.qt.ui_bildfahrplan import Ui_BildfahrplanWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


class BildFahrplanWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self._pick_event: bool = False

        self.ui = Ui_BildfahrplanWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Streckenfahrplan")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)
        self.ui.vordefiniert_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.ui.von_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.ui.via_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.ui.nach_combo.currentIndexChanged.connect(self.strecke_selection_changed)

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.plot = BildfahrplanPlot(zentrale, self._axes)

        self.default_strecke_waehlen()
        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1
        trasse_auswahl = len(self._trasse_auswahl) >= 1
        trasse_paar = len(self._trasse_auswahl) >= 2
        if trasse_paar:
            try:
                trasse_nachbar, _ = self.nachbartrasse_ziel(self._trasse_auswahl[0], self._trasse_auswahl[1])
            except (KeyError, ValueError):
                trasse_nachbar = -1
        else:
            trasse_nachbar = -1

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self._strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionPlusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionMinusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and trasse_nachbar == 0)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and trasse_nachbar == 1)

    def update_widgets(self):
        name = self._strecken_name
        von = self._strecke_von
        via = self._strecke_via
        nach = self._strecke_nach

        gruppen_liste = sorted((gr for gr in itertools.chain(self.anlage.bahnhofgraph.bahnhoefe(),
                                                             self.anlage.bahnhofgraph.anschlussstellen())))
        strecken_liste = sorted(self.anlage.strecken.keys())

        self.ui.von_combo.clear()
        self.ui.von_combo.addItems(gruppen_liste)
        self.ui.via_combo.clear()
        self.ui.via_combo.addItems(["", *gruppen_liste])
        self.ui.nach_combo.clear()
        self.ui.nach_combo.addItems(gruppen_liste)
        self.ui.vordefiniert_combo.clear()
        self.ui.vordefiniert_combo.addItems([""])
        self.ui.vordefiniert_combo.addItems(strecken_liste)

        if von:
            self.ui.von_combo.setCurrentText(von)
        if via:
            self.ui.via_combo.setCurrentText(via)
        if nach:
            self.ui.nach_combo.setCurrentText(nach)
        if name:
            self.ui.vordefiniert_combo.setCurrentText(name)

        self.ui.vorlaufzeit_spin.setValue(self.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.nachlaufzeit)
        if "Name" in self.zugbeschriftung.elemente:
            self.ui.name_button.setChecked(True)
        else:
            self.ui.nummer_button.setChecked(True)

    def default_strecke_waehlen(self):
        strecken = [(name, len(strecke)) for name, strecke in self.anlage.strecken.items()]
        try:
            laengste_strecke = max(strecken, key=lambda x: x[1])
            laengste_strecke = laengste_strecke[0]
        except (ValueError, IndexError):
            laengste_strecke = ""

        try:
            self._strecken_name = self.anlage.hauptstrecke
            strecke = self.anlage.strecken[self.anlage.hauptstrecke]
        except KeyError:
            self._strecken_name = ""
            try:
                strecke = self.anlage.strecken[laengste_strecke]
            except KeyError:
                strecke = []

        try:
            self._strecke_von = strecke[0][1]
            self._strecke_nach = strecke[-1][1]
            self._strecke_via = ""
        except IndexError:
            self._strecke_von = ""
            self._strecke_nach = ""
            self._strecke_via = ""

        self.update_widgets()

    @pyqtSlot()
    def strecke_selection_changed(self):
        name = self.ui.vordefiniert_combo.currentText()
        von = self.ui.von_combo.currentText()
        via = self.ui.via_combo.currentText()
        nach = self.ui.nach_combo.currentText()

        changed = name != self._strecken_name or \
            von != self._strecke_von or \
            nach != self._strecke_nach or \
            via != self._strecke_via

        if changed:
            # todo
            self.update_strecke()

            enable_detailwahl = not bool(name)
            self.ui.von_combo.setEnabled(enable_detailwahl)
            self.ui.via_combo.setEnabled(enable_detailwahl)
            self.ui.nach_combo.setEnabled(enable_detailwahl)

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        if self.ui.name_button.isChecked():
            self.zugbeschriftung.elemente = ["Name", "Verspätung"]
        else:
            self.zugbeschriftung.elemente = ["Nummer", "Verspätung"]
        if self._strecke_von and self._strecke_nach:
            self.daten_update()
            self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    @pyqtSlot()
    def vorlaufzeit_changed(self):
        try:
            self.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def nachlaufzeit_changed(self):
        try:
            self.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    def planung_update(self, *args, **kwargs):
        if self.ui.von_combo.count() == 0:
            self.update_widgets()
        if self._strecke_von and self._strecke_nach:
            self.update_strecke()
            self.daten_update()
            self.grafik_update()
            self.update_actions()

    def daten_update(self):
        pass

    def grafik_update(self):
        self._axes.clear()


        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def on_resize(self, event):
        """
        matplotlib resize-event

        zeichnet die grafik neu.

        :param event:
        :return:
        """

        self.grafik_update()

    def on_button_press(self, event):
        """
        matplotlib button-press event

        aktualisiert die grafik, wenn zuvor ein pick-event stattgefunden hat.
        wenn kein pick-event stattgefunden hat, wird die aktuelle trassenauswahl gelöscht.

        :param event:
        :return:
        """

        self._pick_event = False

    def on_button_release(self, event):
        """
        matplotlib button-release event

        hat im moment keine wirkung.

        :param event:
        :return:
        """

        pass

    def on_pick(self, event):
        """
        matplotlib pick-event wählt liniensegmente (trassen) aus oder ab

        die auswahl wird in self._trasse_auswahl gespeichert.
        es können maximal zwei trassen gewählt sein.

        :param event:
        :return:
        """

        pass

    @pyqtSlot()
    def action_plus_eins(self):
        pass

    @pyqtSlot()
    def action_minus_eins(self):
        pass

    @pyqtSlot()
    def action_loeschen(self):
        pass

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        pass

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        pass
