import itertools
import logging
from typing import Optional, Tuple

from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtWidgets

from stskit.dispo.anlage import Anlage
from stskit.model.ereignisgraph import EreignisGraphNode, EreignisGraphEdge
from stskit.plugin.stsobj import time_to_minutes
from stskit.plugin.stsplugin import PluginClient
from stskit.plots.bildfahrplan import BildfahrplanPlot
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_bildfahrplan import Ui_BildfahrplanWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BildFahrplanWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

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

        self.plot = BildfahrplanPlot(zentrale, self.display_canvas)
        self.plot.selection_changed.register(self.plot_selection_changed)

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
        trasse_auswahl = len(self.plot._selected_edges) >= 1
        trasse_nachbar = None

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self.plot.strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionPlusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionMinusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and self.kann_abfahrt_abwarten() is not None)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and self.kann_ankunft_abwarten() is not None)

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
        self.plot.zeit = time_to_minutes(self.client.calc_simzeit())
        self.plot.draw_graph()

    def plot_selection_changed(self, *args, **kwargs):
        text = "\n".join(self.plot.selection_text)
        self.ui.zuginfoLabel.setText(text)
        self.update_actions()

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
        """
        Abfahrt des zweiten Zuges abwarten (Anschluss/Kreuzung)

        Bedingungen
        - Zwei Kanten selektiert.
        - Beide Kanten gehen vom gleichen Bahnhof ab.
        """

        nodes = self.kann_abfahrt_abwarten()
        if nodes is None:
            return
        else:
            ziel, referenz = nodes

        edge = EreignisGraphEdge(typ="A", zid=ziel.zid, dt_min=0)
        eg = self.zentrale.anlage.ereignisgraph
        if eg.has_node(referenz.node_id) and eg.has_node(ziel.node_id):
            eg.add_edge(referenz.node_id, ziel.node_id, **edge)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_abfahrt_abwarten(self) -> Optional[Tuple[EreignisGraphNode, EreignisGraphNode]]:
        """
        Prüfen ob "Abfahrt abwarten" für aktuelle Auswahl möglich ist

        Bedingungen
        - Zwei Kanten selektiert.
        - Beide Kanten gehen vom gleichen Bahnhof ab.

        :return: Zielereignis und Referenzereignis wenn Befehl mäglich ist, sonst None
        """

        try:
            ziel = self.plot.bildgraph.nodes[self.plot._selected_edges[0][0]]
            referenz = self.plot.bildgraph.nodes[self.plot._selected_edges[1][0]]
        except (IndexError, KeyError):
            return None

        if ziel.bst != referenz.bst:
            return None

        return ziel, referenz

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        """
        Ankunft des zweiten Zuges abwarten (Anschluss/Kreuzung)

        Bedingungen
        - Zwei Kanten selektiert.
        - Zweite Kante endet im Bahnhof, wo die erste Kante abgeht.
        """

        nodes = self.kann_ankunft_abwarten()
        if nodes is None:
            return
        else:
            ziel, referenz = nodes

        edge = EreignisGraphEdge(typ="A", zid=ziel.zid, dt_min=0)
        eg = self.zentrale.anlage.ereignisgraph
        if eg.has_node(referenz.node_id) and eg.has_node(ziel.node_id):
            eg.add_edge(referenz.node_id, ziel.node_id, **edge)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_ankunft_abwarten(self) -> Optional[Tuple[EreignisGraphNode, EreignisGraphNode]]:
        """
        Prüfen ob "Ankunft abwarten" für aktuelle Auswahl möglich ist

        Bedingungen
        - Zwei Kanten selektiert.
        - Zweite Kante endet im Bahnhof, wo die erste Kante abgeht.

        :return: Zielereignis und Referenzereignis wenn Befehl mäglich ist, sonst None
        """

        try:
            ziel = self.plot.bildgraph.nodes[self.plot._selected_edges[0][0]]
            referenz = self.plot.bildgraph.nodes[self.plot._selected_edges[1][1]]
        except (IndexError, KeyError):
            return

        if ziel.bst != referenz.bst:
            return

        return ziel, referenz

