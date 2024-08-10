import math
import itertools
import logging
from typing import Dict, List, Optional, Tuple, Type

import matplotlib as mpl
from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PyQt5 import QtWidgets

from stskit.dispo.anlage import Anlage
from stskit.graphs.ereignisgraph import EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.graphs.zuggraph import ZugGraphNode
from stskit.interface.stsobj import time_to_minutes
from stskit.interface.stsplugin import PluginClient
from stskit.plots.bildfahrplan import BildfahrplanPlot
from stskit.interface.stsobj import format_minutes, format_verspaetung
from stskit.zentrale import DatenZentrale

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
        self._selected_edges: List[Tuple[EreignisLabelType, ...]] = []

        self.ui = Ui_BildfahrplanWindow()
        self.ui.setupUi(self)
        self.update_anlage()

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

        self.plot.default_strecke_waehlen()
        self.update_widgets()
        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1
        trasse_auswahl = False
        trasse_nachbar = None

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self.plot.strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionPlusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionMinusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and trasse_nachbar == 0)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and trasse_nachbar == 1)

    def update_anlage(self):
        """
        Widget-Inhalte nach Anlagenupdate aktualisieren.


        """

        gruppen_liste = sorted((gr for gr in itertools.chain(self.anlage.bahnhofgraph.bahnhoefe(),
                                                             self.anlage.bahnhofgraph.anschlussstellen())))

        strecken_liste = sorted(self.anlage.strecken.keys())

        self.ui.von_combo.clear()
        self.ui.von_combo.addItems(["", *gruppen_liste])
        self.ui.via_combo.clear()
        self.ui.via_combo.addItems(["", *gruppen_liste])
        self.ui.nach_combo.clear()
        self.ui.nach_combo.addItems(["", *gruppen_liste])
        self.ui.vordefiniert_combo.clear()
        self.ui.vordefiniert_combo.addItems(["", *strecken_liste])

    def update_widgets(self):
        """
        Widget-Zustände gemäss Plotattributen aktualisieren.
        """

        name = self.plot.strecken_name
        von = self.plot.strecke_von
        via = self.plot.strecke_via
        nach = self.plot.strecke_nach

        self.ui.vordefiniert_combo.setCurrentText(name)
        self.ui.von_combo.setCurrentText(von)
        self.ui.via_combo.setCurrentText(via)
        self.ui.nach_combo.setCurrentText(nach)

        enable_detailwahl = not bool(name)
        self.ui.von_combo.setEnabled(enable_detailwahl)
        self.ui.via_combo.setEnabled(enable_detailwahl)
        self.ui.nach_combo.setEnabled(enable_detailwahl)

        self.ui.strecke_list.clear()
        self.ui.strecke_list.addItems((p[1] for p in self.plot.strecke))

        if self.plot.strecken_name:
            titel = f"Bildfahrplan {self.plot.strecken_name}"
        elif self.plot.strecke_von and self.plot.strecke_nach:
            titel = f"Bildfahrplan {self.plot.strecke_von}-{self.plot.strecke_nach}"
        else:
            titel = "Bildfahrplan (keine Strecke ausgewählt)"
        self.setWindowTitle(titel)

        self.ui.vorlaufzeit_spin.setValue(self.plot.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.plot.nachlaufzeit)
        if "Name" in self.plot.zugbeschriftung.elemente:
            self.ui.name_button.setChecked(True)
        else:
            self.ui.nummer_button.setChecked(True)

    @pyqtSlot()
    def strecke_selection_changed(self):
        """
        Neue Streckenwahl von Widgets übernehmen.
        """

        name = self.ui.vordefiniert_combo.currentText()
        von = self.ui.von_combo.currentText()
        via = self.ui.via_combo.currentText()
        nach = self.ui.nach_combo.currentText()

        changed = name != self.plot.strecken_name
        if not name:
            changed = changed or \
                      von != self.plot.strecke_von or \
                      nach != self.plot.strecke_nach or \
                      via != self.plot.strecke_via

        if changed:
            self.plot.strecken_name = name
            if not name:
                self.plot.strecke_von = von
                self.plot.strecke_nach = nach
                self.plot.strecke_via = via

            self.plot.update_strecke()
            self.update_widgets()
            self.update_actions()

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        if self.ui.name_button.isChecked():
            self.plot.zugbeschriftung.elemente = ["Name", "Verspätung"]
        else:
            self.plot.zugbeschriftung.elemente = ["Nummer", "Verspätung"]
        if self.plot.strecke_von and self.plot.strecke_nach:
            self.daten_update()
            self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    @pyqtSlot()
    def vorlaufzeit_changed(self):
        try:
            self.plot.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def nachlaufzeit_changed(self):
        try:
            self.plot.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    def planung_update(self, *args, **kwargs):
        if self.ui.von_combo.count() == 0:
            self.update_widgets()
        if self.plot.strecke_von and self.plot.strecke_nach:
            self.plot.update_strecke()
            self.daten_update()
            self.grafik_update()
            self.update_actions()

    def daten_update(self):
        self.plot.zeit = time_to_minutes(self.client.calc_simzeit())
        self.plot.update_ereignisgraph()

    def grafik_update(self):
        self._axes.clear()
        self.plot.zeit = time_to_minutes(self.client.calc_simzeit())
        self.plot.draw_graph()

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

        if self._pick_event:
            self.grafik_update()
            self.update_actions()
        else:
            while self._selected_edges:
                edge = self._selected_edges[-1]
                self.select_edge(edge[0], edge[1], False)

            self.ui.zuginfoLabel.setText("")
            self.grafik_update()
            self.update_actions()

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

        die auswahl wird in _selected_edges gespeichert.
        es können maximal zwei trassen gewählt sein.

        :param event:
        :return:
        """

        if event.mouseevent.inaxes == self._axes:
            self._pick_event = True
            if isinstance(event.artist, Line2D):
                try:
                    edge = event.artist.edge
                except AttributeError:
                    return
                else:
                    self.select_edge(edge[0], edge[1], True)

            l = [self.format_zuginfo(*tr) for tr in self._selected_edges]
            s = "\n".join(l)
            self.ui.zuginfoLabel.setText(s)

    def select_edge(self, u: EreignisLabelType, v: EreignisLabelType, sel: bool):
        if not sel:
            try:
                self._selected_edges.remove((u, v))
            except ValueError:
                pass

        edge_data = self.plot.bildgraph.get_edge_data(u, v)
        if edge_data is not None:
            if sel:
                self._selected_edges.append((u, v))
                idx = min(2, len(self._selected_edges))
                edge_data.auswahl = idx
            else:
                edge_data.auswahl = 0

        if len(self._selected_edges) > 2:
            edge = self._selected_edges[1]
            self.select_edge(edge[0], edge[1], False)

    def format_zuginfo(self, u: EreignisLabelType, v: EreignisLabelType):
        """
        zug-trasseninfo formatieren

        beispiel:
        ICE 573 A-D: B 2 ab 15:30 +3, C 3 an 15:40 +3

        :param trasse: ausgewaehlte trasse
        :return: (str)
        """

        abfahrt = self.plot.bildgraph.nodes[u]
        ankunft = self.plot.bildgraph.nodes[v]
        zug = self.zentrale.betrieb.zuggraph.nodes[abfahrt.zid]

        z1 = format_minutes(abfahrt.t_eff)
        z2 = format_minutes(ankunft.t_eff)
        v1 = format_verspaetung(round(abfahrt.t_eff - abfahrt.t_plan))
        v2 = format_verspaetung(round(ankunft.t_eff - ankunft.t_plan))
        name = zug.name
        von = zug.von
        nach = zug.nach

        return f"{name} ({von} - {nach}): {abfahrt.gleis} ab {z1}{v1}, {ankunft.gleis} an {z2}{v2}"

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
