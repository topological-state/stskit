"""
datenstrukturen fuer anschlussmatrix


"""

import datetime
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung, AnkunftAbwarten
from slotgrafik import hour_minutes_formatter, ZugFarbschema
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung
from zentrale import DatenZentrale

from qt.ui_anschlussmatrix import Ui_AnschlussmatrixWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


ANSCHLUSS_KEIN = np.nan
ANSCHLUSS_OK = 0
ANSCHLUSS_SELBST = 14
ANSCHLUSS_ABWARTEN = 2
ANSCHLUSS_ERFOLGT = 4
ANSCHLUSS_KONFLIKT = 6
ANSCHLUSS_AUSWAHL_1 = 16
ANSCHLUSS_AUSWAHL_2 = 18


class Anschlussmatrix:
    """
    attribute
    ---------

    - anschlussplan: umsteigezeit in minuten nach fahrplan.
        ein anschluss besteht nur, wenn die umsteigezeit grösser als die minimale umsteigezeit des bahnhofs ist.
    - anschlussstatus: status des anschlusses.
        dies ist gleichzeitig auch der numerische wert für die grafische darstellung.
        der automatische status ist eine gerade zahl.
        wenn der status vom fdl quittiert worden ist, wird die nächsthöhere ungerade zahl eingetragen,
        was in der grafik die farbe ausbleicht.

        nan: kein anschluss
        0/1: anschluss erfüllt
        2/3: anschlusszug wartet
        4/5: wartezeit erreicht, zug kann fahren
        6/7: anschluss gebrochen
        8/9:
        10/11:
        12/13:
        14/15: selber zug
        16/17: auswahlfarbe 1
        18/19: auswahlfarbe 2

    - verspaetung: verspätung des ankommenden zuges in minuten

    """
    def __init__(self, anlage: Anlage):
        self.anlage: Anlage = anlage
        self.bahnhof: Optional[str] = None
        self.gleise: Set[str] = set([])
        self.zid_ankuenfte: List[int] = []
        self.zid_abfahrten: List[int] = []
        self.zuege: Dict[int, ZugDetailsPlanung] = {}
        self.ziele: Dict[int, ZugZielPlanung] = {}
        self.anschlussplan = np.zeros((0, 0), dtype=np.float)
        self.anschlussstatus = np.zeros((0, 0), dtype=np.float)
        self.verspaetung = np.zeros((0, 0), dtype=np.float)
        self.ankunft_labels: Dict[int, str] = {}
        self.abfahrt_labels: Dict[int, str] = {}
        self.farbschema: ZugFarbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

    def set_bahnhof(self, bahnhof: str):
        self.bahnhof = bahnhof
        self.gleise = self.anlage.bahnsteiggruppen[bahnhof]

    @staticmethod
    def format_label(name: str, richtung: str, zeit: datetime.time, verspaetung: int) -> str:
        label = [name, richtung.replace("Gleis ", "").split(" ")[0]]

        # try:
        #     zeit = time_to_minutes(zeit)
        # except AttributeError:
        #     pass
        # else:
        #     label.append(f"{int(zeit) // 60:02}:{int(zeit) % 60:02}")

        if verspaetung > 0:
            label.append(f"({int(verspaetung):+})")

        return " ".join(label)

    def update(self, planung: Planung):
        """
        daten für anschlussmatrix zusammentragen

        1. die listen der in frage kommenden züge werden zusammengestellt.
            dies sind züge, die innerhalb des zeitfensters ankommen oder abfahren,
            nicht durchfahren und nicht schon angekommen bzw. abgefahren sind.
            betriebliche vorgänge wie nummernwechsel erzeugen keine separaten einträge.

        2. ankunfts- und abfahrtstabellen werden nach zeit sortiert.

        3. umsteigezeiten und anschlussstatus werden für jede mögliche verbindung berechnet.

        :param planung:
        :return:
        """

        _zid_ankuenfte = set([])
        _zid_abfahrten = set([])
        self.zuege = {}
        self.ziele = {}

        startzeit = planung.simzeit_minuten
        endzeit = startzeit + 15
        min_umsteigezeit = 2

        for zid, zug in planung.zugliste.items():
            for ziel in zug.fahrplan:
                if ziel.gleis in self.gleise and not ziel.durchfahrt():
                    if not ziel.abgefahren \
                            and ziel.an is not None and time_to_minutes(ziel.an) < endzeit:
                        # keine ankunft, wenn zug aus nummernwechsel auf diesem gleis hervorgeht
                        for stamm_zid, ziel_zid, stamm_data in planung.zugbaum.in_edges(zid, data=True):
                            try:
                                stamm_zug = planung.zugbaum.nodes[stamm_zid]['obj']
                                stamm_ziel = stamm_zug.find_fahrplan_zielnr(stamm_data['zielnr'])
                                if stamm_data['flag'] == 'E' and stamm_ziel.ersatzzug.zid == zid:
                                    break
                                elif stamm_data['flag'] == 'F' and stamm_ziel.fluegelzug.zid == zid:
                                    break
                            except (AttributeError, KeyError, ValueError) as e:
                                logger.debug("kann stammzug nicht finden: " + str(e))
                        else:
                            _zid_ankuenfte.add(zid)
                            self.zuege[zid] = zug
                            self.ziele[zid] = ziel

                    if not ziel.abgefahren \
                            and ziel.ab is not None and time_to_minutes(ziel.ab) < endzeit + min_umsteigezeit:
                        # keine abfahrt, wenn zug ersetzt wird
                        if ziel.ersatzzug is None and ziel.kuppelzug is None:
                            _zid_abfahrten.add(zid)
                            self.zuege[zid] = zug
                            self.ziele[zid] = ziel

        self.zid_ankuenfte = sorted(_zid_ankuenfte, key=lambda z: self.ziele[z].an)
        self.zid_abfahrten = sorted(_zid_abfahrten, key=lambda z: self.ziele[z].ab)

        _labels = {ziel.zug.zid: self.format_label(ziel.zug.name, ziel.zug.von, ziel.an, ziel.verspaetung_an)
                   for ziel in self.ziele.values()}
        self.ankunft_labels = {zid: _labels[zid] for zid in self.zid_ankuenfte}
        _labels = {ziel.zug.zid: self.format_label(ziel.zug.name, ziel.zug.nach, ziel.ab, ziel.verspaetung_ab)
                   for ziel in self.ziele.values()}
        self.abfahrt_labels = {zid: _labels[zid] for zid in self.zid_abfahrten}

        n_an = len(self.zid_ankuenfte)
        n_ab = len(self.zid_abfahrten)
        self.anschlussplan = np.ones((n_ab, n_an), dtype=np.float) * np.nan
        self.anschlussstatus = np.ones((n_ab, n_an), dtype=np.float) * np.nan
        self.verspaetung = np.zeros((n_ab, n_an), dtype=np.float)

        for i_ab in range(n_ab):
            zid_ab = self.zid_abfahrten[i_ab]
            ziel_ab = self.ziele[zid_ab]
            zeit_ab = time_to_minutes(ziel_ab.ab)

            for i_an in range(n_an):
                zid_an = self.zid_ankuenfte[i_an]
                ziel_an = self.ziele[zid_an]
                zeit_an = time_to_minutes(ziel_an.an)

                umsteigezeit = zeit_ab - zeit_an
                verspaetung = -umsteigezeit
                verspaetung -= ziel_ab.verspaetung_ab
                verspaetung += ziel_an.verspaetung_an
                verspaetung += min_umsteigezeit

                try:
                    flag = planung.zugbaum.edges[zid_an, zid_ab]['flag']
                except KeyError:
                    flag = ""
                if zid_ab == zid_an or flag in {'E', 'K', 'F'}:
                    status = ANSCHLUSS_SELBST
                elif umsteigezeit >= min_umsteigezeit:
                    if verspaetung > 0:
                        status = ANSCHLUSS_KONFLIKT
                    elif isinstance(ziel_ab.fdl_korrektur, AnkunftAbwarten):
                        status = ANSCHLUSS_ABWARTEN
                    else:
                        status = ANSCHLUSS_OK
                else:
                    status = ANSCHLUSS_KEIN

                self.anschlussplan[i_ab, i_an] = umsteigezeit
                self.anschlussstatus[i_ab, i_an] = status
                self.verspaetung[i_ab, i_an] = verspaetung

    def plot(self, ax):
        kwargs = dict()
        # kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        # kwargs['width'] = 1.0
        kwargs['cmap'] = 'tab10'
        # kwargs['origin'] = 'lower'

        im = ax.imshow(self.anschlussstatus, **kwargs)
        im.set_clim((0., 19.))
        ax.set_ylabel('abfahrt')
        ax.set_xlabel('ankunft')
        try:
            x_labels = [self.ankunft_labels[zid] for zid in self.zid_ankuenfte]
            x_labels_colors = [self.farbschema.zugfarbe(self.zuege[zid]) for zid in self.zid_ankuenfte]
            x_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleise else 'normal' for zid in self.zid_ankuenfte]
            y_labels = [self.abfahrt_labels[zid] for zid in self.zid_abfahrten]
            y_labels_colors = [self.farbschema.zugfarbe(self.zuege[zid]) for zid in self.zid_abfahrten]
            y_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleise else 'normal' for zid in self.zid_abfahrten]
        except KeyError as e:
            logger.warning(e)
            return

        ax.set_xticks(np.arange(self.verspaetung.shape[1]), labels=x_labels, rotation=45, rotation_mode='anchor',
                      horizontalalignment='left', verticalalignment='bottom')
        ax.set_yticks(np.arange(self.verspaetung.shape[0]), labels=y_labels)
        ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

        for label, color, weight in zip(ax.get_xticklabels(), x_labels_colors, x_labels_weigths):
            label.set_color(color)
            label.set_fontweight(weight)
        for label, color, weight in zip(ax.get_yticklabels(), y_labels_colors, y_labels_weigths):
            label.set_color(color)
            label.set_fontweight(weight)

        ax.set_xticks(np.arange(self.verspaetung.shape[1] + 1) - .5, minor=True)
        ax.set_yticks(np.arange(self.verspaetung.shape[0] + 1) - .5, minor=True)
        ax.grid(which="minor", color=mpl.rcParams['axes.facecolor'], linestyle='-', linewidth=3)
        ax.tick_params(which="minor", bottom=False, left=False)

        for i in range(self.verspaetung.shape[0]):
            for j in range(self.verspaetung.shape[1]):
                v = self.verspaetung[i, j]
                if self.anschlussstatus[i, j] in {ANSCHLUSS_KONFLIKT, ANSCHLUSS_ABWARTEN} and not np.isnan(v) and v > 0:
                    text = ax.text(j, i, round(v),
                                   ha="center", va="center", color="w", fontsize="small")

        for item in (ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontsize('small')

        ax.figure.tight_layout()
        ax.figure.canvas.draw()


class AnschlussmatrixWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.anschlussmatrix: Optional[Anschlussmatrix] = None

        self.ui = Ui_AnschlussmatrixWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Anschlussmatrix")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        # self.ui.actionWarnungSetzen.triggered.connect(self.action_warnung_setzen)
        # self.ui.actionWarnungIgnorieren.triggered.connect(self.action_warnung_ignorieren)
        # self.ui.actionWarnungReset.triggered.connect(self.action_warnung_reset)
        # self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        # self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        # self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        # self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        # self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)
        self.ui.bahnhofBox.currentIndexChanged.connect(self.bahnhof_changed)

        self._axes = self.display_canvas.figure.subplots()
        # self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        # self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        # self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def planung(self) -> Planung:
        return self.zentrale.planung

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode)
        self.ui.actionBelegteGleise.setEnabled(display_mode)
        self.ui.actionWarnungSetzen.setEnabled(display_mode and False)  # not implemented
        self.ui.actionWarnungReset.setEnabled(display_mode and False)  # not implemented
        self.ui.actionWarnungIgnorieren.setEnabled(display_mode and False)  # not implemented
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and False)  # not implemented
        self.ui.actionPlusEins.setEnabled(display_mode and False)  # not implemented
        self.ui.actionMinusEins.setEnabled(display_mode and False)  # not implemented
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and False)  # not implemented
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and False)  # not implemented

    def update_combos(self):
        try:
            bahnhoefe = self.anlage.bahnsteiggruppen.keys()
            bahnhoefe_nach_namen = sorted(bahnhoefe)
            bahnhoefe_nach_groesse = sorted(bahnhoefe, key=lambda b: len(self.anlage.bahnsteiggruppen[b]))
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
        self.ui.bahnhofBox.addItems(bahnhoefe_nach_namen)
        self.ui.bahnhofBox.setCurrentText(bahnhof)

        if bahnhof:
            self.ui.bahnhofBox.setCurrentText(bahnhof)

    @pyqtSlot()
    def bahnhof_changed(self):
        try:
            self.anschlussmatrix.set_bahnhof(self.ui.bahnhofBox.currentText())
            self.setWindowTitle("Anschlussmatrix " + self.anschlussmatrix.bahnhof)
        except AttributeError:
            pass

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
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
        if self.anschlussmatrix is None and self.anlage is not None:
            self.anschlussmatrix = Anschlussmatrix(self.anlage)
            regionen_schweiz = {"Bern - Lötschberg", "Ostschweiz", "Tessin", "Westschweiz", "Zentralschweiz",
                                "Zürich und Umgebung"}
            if self.anlage.anlage.region in regionen_schweiz:
                self.anschlussmatrix.farbschema.init_schweiz()
            else:
                self.anschlussmatrix.farbschema.init_deutschland()
            self.update_combos()

        if self.anschlussmatrix:
            self.anschlussmatrix.update(self.planung)

    def grafik_update(self):
        try:
            self._axes.clear()
            self.anschlussmatrix.plot(self._axes)
        except AttributeError:
            pass

    def on_resize(self, event):
        self.grafik_update()
