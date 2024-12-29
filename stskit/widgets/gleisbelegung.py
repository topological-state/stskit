import logging

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.plugin.stsplugin import PluginClient
from stskit.plots.gleisbelegung import GleisbelegungPlot
from stskit.qt.ui_gleisbelegung import Ui_GleisbelegungWindow
from stskit.widgets.gleisauswahl import GleisauswahlModell
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisbelegungWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale, ansicht: str = "Gl"):
        """
        :param zentrale: DatenZentrale
        :param ansicht: "Gl" für Gleisbelegung von Bahnhöfen oder "Agl" für Ein- und Ausfahrten
        """

        super().__init__()

        self.zentrale = zentrale
        self.zentrale.plan_update.register(self.plan_update)
        self.zentrale.betrieb_update.register(self.plan_update)
        self.ansicht = ansicht

        self._pick_event = False

        self.ui = Ui_GleisbelegungWindow()
        self.ui.setupUi(self)
        self.gleisauswahl = GleisauswahlModell(None)
        self.ui.gleisView.setModel(self.gleisauswahl)

        self.setWindowTitle("Gleisbelegung")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))

        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionBelegteGleise.triggered.connect(self.action_belegte_gleise)
        self.ui.actionWarnungSetzen.triggered.connect(self.action_warnung_setzen)
        self.ui.actionWarnungIgnorieren.triggered.connect(self.action_warnung_ignorieren)
        self.ui.actionWarnungReset.triggered.connect(self.action_warnung_reset)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self.plot = GleisbelegungPlot(self.zentrale, self.display_canvas)
        self.plot.selection_changed.register(self.plot_selection_changed)
        if ansicht == "Agl":
            self.plot.vorlaufzeit = 15

        self.update_widgets()
        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode)
        self.ui.actionBelegteGleise.setEnabled(display_mode)
        self.ui.actionBelegteGleise.setChecked(self.plot.belegte_gleise_zeigen)
        self.ui.actionWarnungSetzen.setEnabled(display_mode and len(self.plot._slot_auswahl))
        self.ui.actionWarnungReset.setEnabled(display_mode and len(self.plot._warnung_auswahl))
        self.ui.actionWarnungIgnorieren.setEnabled(display_mode and len(self.plot._warnung_auswahl))
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and len(self.plot._slot_auswahl))
        self.ui.actionPlusEins.setEnabled(display_mode and len(self.plot._slot_auswahl))
        self.ui.actionMinusEins.setEnabled(display_mode and len(self.plot._slot_auswahl))
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and len(self.plot._slot_auswahl) == 2)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and len(self.plot._slot_auswahl) == 2)

    def update_widgets(self):
        self.ui.vorlaufzeit_spin.setValue(self.plot.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.plot.nachlaufzeit)
        try:
            if "Name" in self.belegung.zugbeschriftung.elemente:
                self.ui.name_button.setChecked(True)
            else:
                self.ui.nummer_button.setChecked(True)
        except AttributeError:
            pass

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

    def plan_update(self, *args, **kwargs):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """

        self.daten_update()
        self.grafik_update()

    def daten_update(self):
        if not self.plot.belegung.gleise:
            self.gleisauswahl.gleise_definieren(self.anlage,
                                                anschluesse=self.ansicht == "Agl", bahnsteige=self.ansicht != "Agl")
            self.gleisauswahl.set_auswahl(self.gleisauswahl.alle_gleise)
            self.plot.belegung.gleise_auswaehlen(self.gleisauswahl.alle_gleise)
            sperrungen = {BahnhofElement(gleis[0], gleis[1]) for gleis in self.anlage.gleissperrungen}
            self.gleisauswahl.set_sperrungen(sperrungen)

        self.plot.belegung.update()

    def grafik_update(self):
        self.plot.grafik_update()

    def plot_selection_changed(self, *args, **kwargs):
        text = "\n".join(self.plot.selection_text)
        self.ui.zuginfoLabel.setText(text)
        self.update_actions()

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.gleisView.expandAll()
        self.ui.gleisView.resizeColumnToContents(0)
        self.gleisauswahl.set_auswahl(self.plot.belegung.gleise)
        self.update_widgets()

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.plot.belegung.gleise_auswaehlen(self.gleisauswahl.get_auswahl())
        self.anlage.gleissperrungen = self.gleisauswahl.get_sperrungen()
        if self.ui.name_button.isChecked():
            self.plot.belegung.zugbeschriftung.elemente = ["Name"]
        else:
            self.plot.belegung.zugbeschriftung.elemente = ["Nummer"]
        self.daten_update()
        self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    @pyqtSlot()
    def action_belegte_gleise(self):
        self.plot.belegte_gleise_zeigen = not self.plot.belegte_gleise_zeigen
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_plus_eins(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.wartezeit_aendern(ziel, 1, True)

    @pyqtSlot()
    def action_minus_eins(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.wartezeit_aendern(ziel, -1, True)

    @pyqtSlot()
    def action_loeschen(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.abfahrt_zuruecksetzen(ziel)

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
            referenz = self.plot._slot_auswahl[1].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.abfahrt_abwarten(ziel, referenz)

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
            referenz = self.plot._slot_auswahl[1].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.ankunft_abwarten(ziel, referenz)

    @pyqtSlot()
    def action_warnung_ignorieren(self):
        pass

    @pyqtSlot()
    def action_warnung_setzen(self):
        pass

    @pyqtSlot()
    def action_warnung_reset(self):
        pass
