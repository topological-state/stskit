"""
datenstrukturen und fenster für anschlussmatrix


"""
import itertools
import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Type

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.image import AxesImage
from matplotlib.text import Text
import numpy as np

from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot

from stskit.plots.anschlussmatrix import Anschlussmatrix, \
    ANSCHLUSS_KEIN, ANSCHLUSS_OK, ANSCHLUSS_ABWARTEN, ANSCHLUSS_ERFOLGT, ANSCHLUSS_WARNUNG, ANSCHLUSS_AUFGEBEN, \
    ANSCHLUSS_FLAG, ANSCHLUSS_SELBST, ANSCHLUSS_AUSWAHL_1, ANSCHLUSS_AUSWAHL_2, \
    ANSCHLUESSE_VERSPAETET
from stskit.zugschema import Zugbeschriftung, ZugbeschriftungAuswahlModell, ZugschemaAuswahlModell

from stskit.qt.ui_anschlussmatrix import Ui_AnschlussmatrixWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class AnschlussmatrixWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: 'DatenZentrale'):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.betrieb_update.register(self.planung_update)

        self.anschlussmatrix: Anschlussmatrix = Anschlussmatrix(zentrale)
        self._pick_event: bool = False

        self.in_update = True
        self.ui = Ui_AnschlussmatrixWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Anschlussmatrix")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ankunft_filter_modell = ZugschemaAuswahlModell(None, zugschema=self.zentrale.anlage.zugschema)
        self.ui.ankunft_filter_view.setModel(self.ankunft_filter_modell)

        self.abfahrt_filter_modell = ZugschemaAuswahlModell(None, zugschema=self.zentrale.anlage.zugschema)
        self.ui.abfahrt_filter_view.setModel(self.abfahrt_filter_modell)

        self.ankunft_beschriftung_modell = ZugbeschriftungAuswahlModell(None,
            beschriftung=self.anschlussmatrix.ankunft_beschriftung)
        self.ui.ankunft_beschriftung_view.setModel(self.ankunft_beschriftung_modell)

        self.abfahrt_beschriftung_modell = ZugbeschriftungAuswahlModell(None,
            beschriftung=self.anschlussmatrix.abfahrt_beschriftung)
        self.ui.abfahrt_beschriftung_view.setModel(self.abfahrt_beschriftung_modell)

        self.zugbeschriftung = Zugbeschriftung(stil='Anschlussmatrix')

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_anschluss_reset)
        self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.actionAnschlussAufgeben.triggered.connect(self.action_anschluss_aufgeben)
        self.ui.actionZugAusblenden.triggered.connect(self.action_zug_ausblenden)
        self.ui.actionZugEinblenden.triggered.connect(self.action_zug_einblenden)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self.ui.bahnhofBox.currentIndexChanged.connect(self.bahnhof_changed)
        self.ui.umsteigezeitSpin.valueChanged.connect(self.umsteigezeit_changed)
        self.ui.anschlusszeitSpin.valueChanged.connect(self.anschlusszeit_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_widgets()
        self.update_actions()
        self.in_update = False

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1

        if self.anschlussmatrix is not None:
            auswahl_matrix = self.anschlussmatrix._make_auswahl_matrix(self.anschlussmatrix.anschluss_auswahl)
            auswahl_matrix[auswahl_matrix == 0] = np.nan
            status_auswahl = self.anschlussmatrix.anschlussstatus * auswahl_matrix
            auswahl = display_mode and ~np.all(np.isnan(status_auswahl))
        else:
            auswahl = False

        loeschen_enabled = auswahl and np.any(np.isin(status_auswahl, [ANSCHLUSS_ABWARTEN, ANSCHLUSS_AUFGEBEN]))
        minus_enabled = auswahl and np.any(np.isin(status_auswahl, [ANSCHLUSS_ABWARTEN]))
        plus_enabled = auswahl and np.any(np.isin(status_auswahl, [ANSCHLUSS_ABWARTEN, ANSCHLUSS_WARNUNG, ANSCHLUSS_OK]))
        abwarten_enabled = auswahl and np.any(np.isin(status_auswahl, [ANSCHLUSS_WARNUNG, ANSCHLUSS_OK]))
        einblenden_enabled = display_mode and self.anschlussmatrix is not None and \
                             (len(self.anschlussmatrix.abfahrten_ausblenden) or
                            len(self.anschlussmatrix.ankuenfte_ausblenden))

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode)
        self.ui.actionWarnungSetzen.setEnabled(display_mode and False)  # not implemented
        self.ui.actionWarnungReset.setEnabled(display_mode and False)  # not implemented
        self.ui.actionWarnungIgnorieren.setEnabled(display_mode and False)  # not implemented
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(loeschen_enabled)
        self.ui.actionPlusEins.setEnabled(plus_enabled)
        self.ui.actionMinusEins.setEnabled(minus_enabled)
        self.ui.actionAbfahrtAbwarten.setEnabled(abwarten_enabled)
        self.ui.actionAnkunftAbwarten.setEnabled(abwarten_enabled)
        self.ui.actionAnschlussAufgeben.setEnabled(abwarten_enabled)
        self.ui.actionZugEinblenden.setEnabled(einblenden_enabled)
        self.ui.actionZugAusblenden.setEnabled(auswahl)

    def update_widgets(self):
        self.in_update = True

        bahnhofgraph = self.zentrale.anlage.bahnhofgraph
        try:
            bahnhoefe = list(bahnhofgraph.list_children(bahnhofgraph.root(), {"Bf"}))
            bahnhoefe_nach_namen = sorted(bahnhoefe, key=lambda b: b.name)
            bahnhoefe_nach_groesse = sorted(bahnhoefe, key=lambda b:
                                            len(list(bahnhofgraph.list_children(b, {'Gl'}))))
        except AttributeError:
            return

        try:
            bahnhof = self.anschlussmatrix.bahnhof
        except AttributeError:
            return
        else:
            if not bahnhof:
                bahnhof = bahnhoefe_nach_groesse[-1]

        self.ui.bahnhofBox.clear()
        self.ui.bahnhofBox.addItems([b.name for b in bahnhoefe_nach_namen])
        if bahnhof:
            self.ui.bahnhofBox.setCurrentText(bahnhof.name)

        self.ui.anschlusszeitSpin.setValue(self.anschlussmatrix.anschlusszeit)
        self.ui.umsteigezeitSpin.setValue(self.anschlussmatrix.umsteigezeit)

        self.ankunft_filter_modell.auswahl = self.anschlussmatrix.ankunft_filter_kategorien
        self.abfahrt_filter_modell.auswahl = self.anschlussmatrix.abfahrt_filter_kategorien
        self.ankunft_beschriftung_modell.auswahl = self.anschlussmatrix.ankunft_beschriftung.elemente
        self.abfahrt_beschriftung_modell.auswahl = self.anschlussmatrix.abfahrt_beschriftung.elemente

        self.ui.ankunft_beschriftung_view.resizeColumnsToContents()
        self.ui.ankunft_beschriftung_view.resizeRowsToContents()
        self.ui.abfahrt_beschriftung_view.resizeColumnsToContents()
        self.ui.abfahrt_beschriftung_view.resizeRowsToContents()
        self.ui.ankunft_filter_view.resizeColumnsToContents()
        self.ui.ankunft_filter_view.resizeRowsToContents()
        self.ui.abfahrt_filter_view.resizeColumnsToContents()
        self.ui.abfahrt_filter_view.resizeRowsToContents()

        self.in_update = False

    @pyqtSlot()
    def bahnhof_changed(self):
        try:
            self.anschlussmatrix.set_bahnhof(self.zentrale.anlage.bahnhofgraph.find_name(self.ui.bahnhofBox.currentText()))
            self.setWindowTitle("Anschlussmatrix " + self.anschlussmatrix.bahnhof.name)
        except (AttributeError, KeyError):
            pass

    @pyqtSlot()
    def umsteigezeit_changed(self):
        try:
            self.anschlussmatrix.umsteigezeit = self.ui.umsteigezeitSpin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def anschlusszeit_changed(self):
        try:
            self.anschlussmatrix.anschlusszeit = self.ui.anschlusszeitSpin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.update_widgets()

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.anschlussmatrix.ankunft_filter_kategorien = self.ankunft_filter_modell.auswahl
        self.anschlussmatrix.abfahrt_filter_kategorien = self.abfahrt_filter_modell.auswahl
        self.anschlussmatrix.ankunft_beschriftung.elemente = self.ankunft_beschriftung_modell.auswahl
        self.anschlussmatrix.abfahrt_beschriftung.elemente = self.abfahrt_beschriftung_modell.auswahl
        if self.anschlussmatrix.bahnhof:
            self.daten_update()
            self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    def planung_update(self, *args, **kwargs):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """

        self.daten_update()
        self.grafik_update()

    def daten_update(self):
        if self.anschlussmatrix:
            self.anschlussmatrix.update()

    def grafik_update(self):
        self._axes.clear()
        if self.anschlussmatrix is None:
            return

        self.anschlussmatrix.plot(self._axes)

    def on_resize(self, event):
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
            self.ui.zuginfoLabel.setText("")

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
        matplotlib pick-event

        :param event:
        :return:
        """

        self._pick_event = True
        if isinstance(event.artist, AxesImage):
            try:
                i_an = round(event.mouseevent.xdata)
                i_ab = round(event.mouseevent.ydata)
            except AttributeError:
                return
            try:
                zid_an = self.anschlussmatrix.zid_ankuenfte_index[i_an]
                zid_ab = self.anschlussmatrix.zid_abfahrten_index[i_ab]
            except IndexError:
                return
            zids = (zid_ab, zid_an)
            self.anschlussmatrix.anschluss_auswahl = {zids}
        elif isinstance(event.artist, Text):
            try:
                zids = event.artist.zids
                self.anschlussmatrix.anschluss_auswahl = {zids}
            except AttributeError:
                return
        else:
            self.anschlussmatrix.anschluss_auswahl.clear()
            zids = (-1, -1)

        info = []
        try:
            ziel_an = self.anschlussmatrix.ankunft_ziele[zids[1]]
            zug_data = self.zentrale.betrieb.zuggraph.nodes[ziel_an.zid]
            info_an = self.zugbeschriftung.format(zug_data, ziel_an, "Ankunft")
            info.append(info_an)
        except (IndexError, KeyError):
            pass
        try:
            ziel_ab = self.anschlussmatrix.abfahrt_ziele[zids[0]]
            zug_data = self.zentrale.betrieb.zuggraph.nodes[ziel_ab.zid]
            info_ab = self.zugbeschriftung.format(zug_data, ziel_ab, "Abfahrt")
            info.append(info_ab)
        except (IndexError, KeyError):
            pass
        s = "\n".join(info)
        self.ui.zuginfoLabel.setText(s)

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        for zid_ab, zid_an in self.anschlussmatrix.anschluss_auswahl:
            if zid_an < 0:
                # todo : mehrfache eingehende anschlüsse werden zur zeit nicht unterstützt
                return
            if zid_ab >= 0:
                _zids_ab = {zid_ab}
            else:
                _zids_ab = self.anschlussmatrix.zid_abfahrten_set
            for _zid_ab in _zids_ab:
                try:
                    i_ab = self.anschlussmatrix.zid_abfahrten_index.index(_zid_ab)
                    i_an = self.anschlussmatrix.zid_ankuenfte_index.index(zid_an)
                except ValueError:
                    continue
                else:
                    if self.anschlussmatrix.anschlussstatus[i_ab, i_an] in\
                            {ANSCHLUSS_WARNUNG, ANSCHLUSS_AUFGEBEN, ANSCHLUSS_OK}:
                        self.abhaengigkeit_definieren(None,
                                                      self.anschlussmatrix.abfahrt_ziele[_zid_ab],
                                                      self.anschlussmatrix.ankunft_ziele[zid_an],
                                                      self.anschlussmatrix.umsteigezeit)

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        for zid_ab, zid_an in self.anschlussmatrix.anschluss_auswahl:
            if zid_an < 0:
                # mehrfache eingehende anschlüsse werden zur zeit nicht unterstützt
                return

            # abfahrt des zubringers suchen
            try:
                _zid_an = self.anschlussmatrix.abfahrt_suchen(zid_an)
                _zid_an = _zid_an[-1]
                i_an = self.anschlussmatrix.zid_ankuenfte_index.index(_zid_an)
            except (IndexError, ValueError):
                continue

            if zid_ab >= 0:
                _zids_ab = {zid_ab}
            else:
                _zids_ab = self.anschlussmatrix.zid_abfahrten_set

            for _zid_ab in _zids_ab:
                try:
                    i_ab = self.anschlussmatrix.zid_abfahrten_index.index(_zid_ab)
                except ValueError:
                    continue
                else:
                    if self.anschlussmatrix.anschlussstatus[i_ab, i_an] in \
                            {ANSCHLUSS_WARNUNG, ANSCHLUSS_AUFGEBEN, ANSCHLUSS_OK}:
                        self.abhaengigkeit_definieren(None,
                                                      self.anschlussmatrix.abfahrt_ziele[_zid_ab],
                                                      self.anschlussmatrix.abfahrt_ziele[_zid_an])

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_anschluss_aufgeben(self):
        auswahl = self.anschlussmatrix.auswahl_expandieren(self.anschlussmatrix.anschluss_auswahl)
        self.anschlussmatrix.anschluss_aufgabe.update(auswahl)
        for zid_ab, zid_an in auswahl:
            i_ab = self.anschlussmatrix.zid_abfahrten_index.index(zid_ab)
            i_an = self.anschlussmatrix.zid_ankuenfte_index.index(zid_an)
            if self.anschlussmatrix.anschlussstatus[i_ab, i_an] in {ANSCHLUSS_ABWARTEN}:
                self.abhaengigkeit_definieren(None,
                                              self.anschlussmatrix.abfahrt_ziele[zid_ab],
                                              self.anschlussmatrix.ankunft_ziele[zid_an])

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_anschluss_reset(self):
        auswahl = self.anschlussmatrix.auswahl_expandieren(self.anschlussmatrix.anschluss_auswahl)
        self.anschlussmatrix.anschluss_aufgabe.difference_update(auswahl)
        for zid_ab, zid_an in auswahl:
            pass

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_plus_eins(self):
        auswahl = self.anschlussmatrix.auswahl_expandieren(self.anschlussmatrix.anschluss_auswahl)
        for zid_ab, zid_an in auswahl:
            self.verspaetung_aendern(self.anschlussmatrix.abfahrt_ziele[zid_ab], 1, True)

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_minus_eins(self):
        auswahl = self.anschlussmatrix.auswahl_expandieren(self.anschlussmatrix.anschluss_auswahl)
        for zid_ab, zid_an in auswahl:
            self.verspaetung_aendern(self.anschlussmatrix.abfahrt_ziele[zid_ab], -1, True)

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_zug_ausblenden(self):
        for zid_ab, zid_an in self.anschlussmatrix.anschluss_auswahl:
            if zid_ab:
                self.anschlussmatrix.abfahrten_ausblenden.add(zid_ab)
            if zid_an:
                self.anschlussmatrix.ankuenfte_ausblenden.add(zid_an)

        self.anschlussmatrix.anschluss_auswahl.clear()
        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_zug_einblenden(self):
        self.anschlussmatrix.ankuenfte_ausblenden.clear()
        self.anschlussmatrix.abfahrten_ausblenden.clear()
        self.anschlussmatrix.anschluss_auswahl.clear()
        self.daten_update()
        self.grafik_update()
        self.update_actions()

    def verspaetung_aendern(self, ziel: Any, verspaetung: int, relativ: bool = False):
        pass

    def abhaengigkeit_definieren(self, klasse: Any,
                                 ziel: Any,
                                 referenz: Any,
                                 wartezeit: Optional[int] = None):
        pass