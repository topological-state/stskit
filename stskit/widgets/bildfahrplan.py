import itertools
import logging
from typing import Optional, Tuple

from PySide6.QtCore import Slot, QStringListModel
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6 import QtWidgets

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement
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
        self.zentrale.anlage_update.register(self.anlage_update)
        self.zentrale.plan_update.register(self.plan_update)
        self.zentrale.betrieb_update.register(self.plan_update)
        self.updating = True

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
        self.ui.actionBetriebshaltEinfuegen.triggered.connect(self.action_betriebshalt_einfuegen)
        self.ui.actionActionBetriebshaltLoeschen.triggered.connect(self.action_betriebshalt_loeschen)

        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self.vordefiniert_model = QStringListModel()
        self.ui.vordefiniert_combo.setModel(self.vordefiniert_model)
        self.ui.vordefiniert_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.von_model = QStringListModel()
        self.ui.von_combo.setModel(self.von_model)
        self.ui.von_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.via_model = QStringListModel()
        self.ui.via_combo.setModel(self.via_model)
        self.ui.via_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.nach_model = QStringListModel()
        self.ui.nach_combo.setModel(self.nach_model)
        self.ui.nach_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.strecke_model = QStringListModel()
        self.ui.strecke_list.setModel(self.strecke_model)

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self.plot = BildfahrplanPlot(zentrale, self.display_canvas)
        self.plot.auswahl_geaendert.register(self.plot_selection_changed)

        self.plot.default_strecke_waehlen()
        self.anlage_update()
        self.plan_update()
        self.updating = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    def closeEvent(self, event, /):
        self.zentrale.anlage_update.unregister(self)
        self.zentrale.plan_update.unregister(self)
        self.zentrale.betrieb_update.unregister(self)
        super().closeEvent(event)

    def anlage_update(self, *args, **kwargs):
        """
        Anlagenupdate

        Bei einem Anlagenupdate können geändert werden:
        - Bahnhofmodell und Streckendefinition
        - Zugschema
        """

        self.plot.update_strecke()
        self.update_widgets()

    def plan_update(self, *args, **kwargs):
        self.daten_update()
        self.grafik_update()
        self.update_actions()

    def daten_update(self):
        self.plot.zeit = time_to_minutes(self.client.calc_simzeit())
        self.plot.update_ereignisgraph()

    def grafik_update(self):
        self.plot.draw_graph()

    def update_widgets(self):
        """
        Widget-Zustände gemäss Plotattributen aktualisieren.
        """

        self.updating = True

        bg = self.anlage.bahnhofgraph
        bst_liste = sorted(bg.list_children(bg.root(), {'Bf', 'Anst'}))
        bst_liste = ["", *map(str, bst_liste)]
        strecken_liste = sorted(self.anlage.strecken.strecken.keys(), key=self.anlage.strecken.ordnung.get)

        self.von_model.setStringList(bst_liste)
        self.via_model.setStringList(bst_liste)
        self.nach_model.setStringList(bst_liste)
        self.vordefiniert_model.setStringList(["", *strecken_liste])

        name = self.plot.strecken_name
        von = self.plot.strecke_von
        via = self.plot.strecke_via
        nach = self.plot.strecke_nach

        try:
            self.ui.vordefiniert_combo.setCurrentIndex(self.vordefiniert_model.stringList().index(name))
        except ValueError:
            pass
        try:
            self.ui.von_combo.setCurrentIndex(self.von_model.stringList().index(str(von)))
        except ValueError:
            pass
        try:
            self.ui.via_combo.setCurrentIndex(self.via_model.stringList().index(str(via)))
        except ValueError:
            pass
        try:
            self.ui.nach_combo.setCurrentIndex(self.nach_model.stringList().index(str(nach)))
        except ValueError:
            pass

        enable_detailwahl = not bool(name)
        self.ui.von_combo.setEnabled(enable_detailwahl)
        self.ui.via_combo.setEnabled(enable_detailwahl)
        self.ui.nach_combo.setEnabled(enable_detailwahl)

        self.strecke_model.setStringList(map(str, self.plot.strecke))

        if self.plot.strecken_name:
            titel = f"Streckenfahrplan {self.plot.strecken_name}"
        elif self.plot.strecke_von and self.plot.strecke_nach:
            titel = f"Streckenfahrplan {self.plot.strecke_von.name}-{self.plot.strecke_nach.name}"
        else:
            titel = "Streckenfahrplan (keine Strecke ausgewählt)"
        self.setWindowTitle(titel)

        self.ui.vorlaufzeit_spin.setValue(self.plot.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.plot.nachlaufzeit)

        self.updating = False

    def update_actions(self):
        self.updating = True

        display_mode = self.ui.stackedWidget.currentIndex() == 1
        trasse_auswahl = len(self.plot.auswahl_kanten) >= 1
        trasse_nachbar = None

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self.plot.strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionPlusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionMinusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and self.kann_abfahrt_abwarten() is not None)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and self.kann_ankunft_abwarten() is not None)

        self.updating = False

    @Slot()
    def strecke_selection_changed(self):
        """
        Neue Streckenwahl von Widgets übernehmen.
        """
        if self.updating:
            return

        name = self.ui.vordefiniert_combo.currentText()
        try:
            von = BahnhofElement(*self.ui.von_combo.currentText().split(" ", 1))
        except TypeError:
            von = None
        try:
            via = BahnhofElement(*self.ui.via_combo.currentText().split(" ", 1))
        except TypeError:
            via = None
        try:
            nach = BahnhofElement(*self.ui.nach_combo.currentText().split(" ", 1))
        except TypeError:
            nach = None

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

    @Slot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @Slot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        if self.plot.strecke_von and self.plot.strecke_nach:
            self.daten_update()
            self.grafik_update()

    @Slot()
    def page_changed(self):
        self.update_actions()

    @Slot()
    def vorlaufzeit_changed(self):
        try:
            self.plot.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @Slot()
    def nachlaufzeit_changed(self):
        try:
            self.plot.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    def plot_selection_changed(self, *args, **kwargs):
        text = "\n".join(self.plot.auswahl_text)
        self.ui.zuginfoLabel.setText(text)
        self.update_actions()

    @Slot()
    def action_plus_eins(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
        except (IndexError, KeyError):
            return None
        else:
            self.zentrale.betrieb.wartezeit_aendern(ziel, 1, True)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    @Slot()
    def action_minus_eins(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
        except (IndexError, KeyError):
            return None
        else:
            self.zentrale.betrieb.wartezeit_aendern(ziel, -1, True)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    @Slot()
    def action_loeschen(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
        except (IndexError, KeyError):
            return None
        else:
            self.zentrale.betrieb.abfahrt_zuruecksetzen(ziel)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    @Slot()
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
            self.zentrale.betrieb.abfahrt_abwarten(ziel, referenz)

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
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
            referenz = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[1][0]]
        except (IndexError, KeyError):
            return None

        if ziel.bst != referenz.bst:
            return None

        return ziel, referenz

    @Slot()
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
            self.zentrale.betrieb.ankunft_abwarten(ziel, referenz)

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
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
            referenz = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[1][1]]
        except (IndexError, KeyError):
            return

        if ziel.bst != referenz.bst:
            return

        return ziel, referenz

    @Slot()
    def action_betriebshalt_einfuegen(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
        except (IndexError, KeyError):
            return

        self.zentrale.betrieb.betriebshalt_einfuegen(ziel, self.plot.auswahl_bahnhoefe[0], wartezeit=1)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    @Slot()
    def action_betriebshalt_loeschen(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_kanten[0][0]]
        except (IndexError, KeyError):
            return

        self.zentrale.betrieb.betriebshalt_loeschen(ziel)

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()
