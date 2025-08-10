import logging
from typing import AbstractSet, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Type, Union

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Slot, QModelIndex

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BAHNHOFELEMENT_TYPEN
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
        self.zentrale.anlage_update.register(self.anlage_update)
        self.zentrale.plan_update.register(self.plan_update)
        self.zentrale.betrieb_update.register(self.plan_update)
        self.ansicht = ansicht
        self.collapsed_items = set()

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

    def closeEvent(self, event, /):
        self.zentrale.anlage_update.unregister(self)
        self.zentrale.plan_update.unregister(self)
        self.zentrale.betrieb_update.unregister(self)
        super().closeEvent(event)

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

    def save_expanded_state(self, level: int = 0, index: Optional[QModelIndex] = None):
        """
        Save expansion state of all tree view items.

        Adds Bahnhofelement label of collapsed items to collapsed_items attribute.
        At the top level, leave all optional arguments to their default values.
        Arguments are used in the internal recursion.
        """

        view = self.ui.gleisView
        model = view.model()

        if level == 0:
            index = QModelIndex()
            self.collapsed_items = set()
        elif level >= len(BAHNHOFELEMENT_TYPEN):
            return

        if index.isValid():
            element = index.data(QtCore.Qt.UserRole)
            if not view.isExpanded(index):
                self.collapsed_items.add(element)

        for row in range(model.rowCount(index)):
            self.save_expanded_state(level + 1, model.index(row, 0, index))

    def restore_expanded_state(self, level: int = 0, index: Optional[QModelIndex] = None):
        """
        Restore expansion state of all tree view items.

        Expands each item whose Bahnhofelement label is not present in the collapsed_items attribute.
        At the top level, leave all optional arguments to their default values.
        Arguments are used in the internal recursion.
        """

        view = self.ui.gleisView
        model = view.model()
        updates = False

        if level == 0:
            index = QModelIndex()
            view.setUpdatesEnabled(False)
            updates = True
        elif level >= len(BAHNHOFELEMENT_TYPEN):
            return

        if index.isValid():
            element = index.data(QtCore.Qt.UserRole)
            expanded = element not in self.collapsed_items
            view.setExpanded(index, expanded)

        for row in range(model.rowCount(index)):
            self.restore_expanded_state(level + 1, model.index(row, 0, index))

        if updates:
            view.setUpdatesEnabled(True)

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

    def anlage_update(self, *args, **kwargs):
        """
        Änderungen an der Anlage übernehmen
        """

        auswahl = self.gleisauswahl.get_auswahl()
        self.save_expanded_state()
        self.gleisauswahl.gleise_definieren(self.anlage,
                                            anschluesse=self.ansicht == "Agl", bahnsteige=self.ansicht != "Agl")
        self.restore_expanded_state()
        auswahl = auswahl & self.gleisauswahl.alle_gleise
        if not auswahl:
            auswahl = self.gleisauswahl.alle_gleise
        self.gleisauswahl.set_auswahl(auswahl)
        self.plot.belegung.gleise_auswaehlen(auswahl)

    def plan_update(self, *args, **kwargs):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """

        if not self.plot.belegung.gleise:
            self.anlage_update(*args, **kwargs)

        self.plot.belegung.update()
        self.plot.grafik_update()

    def plot_selection_changed(self, *args, **kwargs):
        text = "\n".join(self.plot.selection_text)
        self.ui.zuginfoLabel.setText(text)
        self.update_actions()

    @Slot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.gleisView.expandAll()
        self.ui.gleisView.resizeColumnToContents(0)
        self.gleisauswahl.set_auswahl(self.plot.belegung.gleise)
        self.update_widgets()

    @Slot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.plot.belegung.gleise_auswaehlen(self.gleisauswahl.get_auswahl())
        self.plot.grafik_update()

    @Slot()
    def page_changed(self):
        self.update_actions()

    @Slot()
    def action_belegte_gleise(self):
        self.plot.belegte_gleise_zeigen = not self.plot.belegte_gleise_zeigen
        self.plot.grafik_update()
        self.update_actions()

    @Slot()
    def action_plus_eins(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.wartezeit_aendern(ziel, 1, True)

    @Slot()
    def action_minus_eins(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.wartezeit_aendern(ziel, -1, True)

    @Slot()
    def action_loeschen(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.abfahrt_zuruecksetzen(ziel)

    @Slot()
    def action_abfahrt_abwarten(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
            referenz = self.plot._slot_auswahl[1].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.abfahrt_abwarten(ziel, referenz)

    @Slot()
    def action_ankunft_abwarten(self):
        try:
            ziel = self.plot._slot_auswahl[0].fid
            referenz = self.plot._slot_auswahl[1].fid
        except (IndexError, KeyError):
            return None

        self.zentrale.betrieb.ankunft_abwarten(ziel, referenz)

    @Slot()
    def action_warnung_ignorieren(self):
        pass

    @Slot()
    def action_warnung_setzen(self):
        pass

    @Slot()
    def action_warnung_reset(self):
        pass
