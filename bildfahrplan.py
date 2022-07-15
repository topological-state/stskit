import math
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets, uic

import planung
from auswertung import Auswertung
from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from slotgrafik import hour_minutes_formatter, ZugFarbschema
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


def format_label(plan1: ZugZielPlanung, plan2: ZugZielPlanung):
    """
    zuglabel formatieren mit verspätungsangabe

    das label besteht aus zugname und verspätungsangabe (falls nicht null).
    die verspätungsangabe besteht aus einem teil wenn sie am anfang und ende der linie gleich ist,
    sonst aus der verspätung am anfang und ende.

    :param plan1: anfangspunkt der linie. zug.name und verspaetung_ab werden benutzt.
    :param plan2: endpunkt der linie. verspaetung_an wird benutzt.
    :return: (str)
    """
    v1 = plan1.verspaetung_ab
    v2 = plan2.verspaetung_an
    name = plan1.zug.name

    if v1 == v2:
        if v1 == 0:
            v = ""
        else:
            v = format_verspaetung(v1)
    else:
        v = "|".join((format_verspaetung(v1), format_verspaetung(v2)))

    if v:
        return f"{name} ({v})"
    else:
        return f"{name}"


@dataclass(init=False)
class Trasse:
    zug: ZugDetailsPlanung
    richtung: int
    start: ZugZielPlanung
    ziel: ZugZielPlanung
    koord: List[Tuple[float]]
    halt: bool = False
    color: str = "b"
    fontstyle: str = "normal"
    linestyle: str = "-"
    linewidth: int = 1
    marker: str = "."

    def __str__(self):
        return f"{self.zug.name}: {self.start.plan}-{self.ziel.plan}"

    def __hash__(self) -> int:
        return hash(self.key)

    def key(self) -> Tuple[int, int, str, str]:
        return self.zug.zid, self.richtung, self.start.plan, self.ziel.plan

    def plot_args(self):
        args = {'color': self.color,
                'linewidth': self.linewidth,
                'linestyle': self.linestyle,
                'marker': self.marker}

        if self.start.fdl_korrektur:
            args['marker'] = 's'
        try:
            args['markevery'] = [not self.start.durchfahrt(), not self.ziel.durchfahrt()]
        except AttributeError:
            args['marker'] = ""

        return args


class BildFahrplanWindow(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.planung: Optional[Planung] = None
        self.auswertung: Optional[Auswertung] = None

        self._strecken_name: str = ""
        self._strecke_von: str = ""
        self._strecke_via: str = ""
        self._strecke_nach: str = ""

        self._trasse_auswahl: Optional[Trasse] = None
        self._pick_event: bool = False

        # bahnhofname -> distanz [minuten]
        self._strecke: List[str] = []
        self._distanz: List[float] = []
        self._zuglaeufe: Dict[Tuple[int, int], List[Trasse]] = {}

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5
        self.farbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

        self.setWindowTitle("Bildfahrplan")
        ss = f"background-color: {mpl.rcParams['axes.facecolor']};" \
             f"color: {mpl.rcParams['text.color']};"
        # further possible entries:
        # "selection-color: yellow;"
        # "selection-background-color: blue;"
        self.setStyleSheet(ss)

        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.stackedWidget = QtWidgets.QStackedWidget(self)
        self.settings_page = QtWidgets.QWidget()
        self.splitter = QtWidgets.QSplitter(self.settings_page)
        self.settings_splitter = QtWidgets.QSplitter(self.settings_page)
        self.settings_splitter.setGeometry(QtCore.QRect(10, 10, 300, 400))
        self.settings_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.settings_widget = QtWidgets.QWidget(self.settings_splitter)
        self.settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_page.setLayout(self.settings_layout)

        self.von_label = QtWidgets.QLabel("&Von", self.settings_widget)
        self.settings_layout.addWidget(self.von_label)
        self.von_combo = QtWidgets.QComboBox(self.settings_widget)
        self.settings_layout.addWidget(self.von_combo)
        self.von_label.setBuddy(self.von_combo)
        self.via_label = QtWidgets.QLabel("V&ia (optional)", self.settings_widget)
        self.settings_layout.addWidget(self.via_label)
        self.via_combo = QtWidgets.QComboBox(self.settings_widget)
        self.settings_layout.addWidget(self.via_combo)
        self.via_label.setBuddy(self.via_combo)
        self.nach_label = QtWidgets.QLabel("&Nach", self.settings_widget)
        self.settings_layout.addWidget(self.nach_label)
        self.nach_combo = QtWidgets.QComboBox(self.settings_widget)
        self.settings_layout.addWidget(self.nach_combo)
        self.nach_label.setBuddy(self.nach_combo)
        self.strecke_label = QtWidgets.QLabel("Strecke", self.settings_widget)
        self.settings_layout.addWidget(self.strecke_label)
        self.strecke_list = QtWidgets.QListWidget(self.settings_widget)
        self.settings_layout.addWidget(self.strecke_list)
        self.hidden_widget = QtWidgets.QWidget(self.splitter)

        self.stackedWidget.addWidget(self.settings_page)

        self.display_page = QtWidgets.QWidget()
        self.stackedWidget.addWidget(self.display_page)
        self.verticalLayout.addWidget(self.stackedWidget)

        self.display_layout = QtWidgets.QVBoxLayout(self.display_page)
        self.display_page.setLayout(self.display_layout)
        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.display_layout.addWidget(self.display_canvas)

        self.settings_button = QtWidgets.QPushButton("&Strecke", self.display_canvas)
        self.display_button = QtWidgets.QPushButton("&Anzeigen")
        self.settings_layout.addWidget(self.display_button)

        self.stackedWidget.setCurrentIndex(0)

        self.von_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.via_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.nach_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.settings_button.clicked.connect(self.settings_button_clicked)
        self.display_button.clicked.connect(self.display_button_clicked)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("key_press_event", self.on_key_press)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

    def set_strecke(self, streckenname: str):
        if streckenname != self._strecken_name:
            self._strecken_name = streckenname
            self._strecke = []

    def update_combos(self):
        von = self._strecke_von
        via = self._strecke_via
        nach = self._strecke_nach

        laengste_strecke = max(self.anlage.strecken.values(), key=len)
        if not von and len(laengste_strecke) >= 2:
            von = laengste_strecke[0]
        if not nach and len(laengste_strecke) >= 2:
            nach = laengste_strecke[-1]

        gruppen_liste = sorted((gr for gr in self.anlage.gleisgruppen.keys()))
        self.von_combo.clear()
        self.von_combo.addItems(gruppen_liste)
        self.via_combo.clear()
        self.via_combo.addItems(["", *gruppen_liste])
        self.nach_combo.clear()
        self.nach_combo.addItems(gruppen_liste)

        if von:
            self.von_combo.setCurrentText(von)
        if via:
            self.via_combo.setCurrentText(via)
        if nach:
            self.nach_combo.setCurrentText(nach)

    @pyqtSlot()
    def strecke_selection_changed(self):
        self._strecke_von = self.von_combo.currentText()
        self._strecke_via = self.via_combo.currentText()
        self._strecke_nach = self.nach_combo.currentText()
        self.update_strecke()

    @pyqtSlot()
    def settings_button_clicked(self):
        self.stackedWidget.setCurrentIndex(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.stackedWidget.setCurrentIndex(1)
        if self._strecke_von and self._strecke_nach:
            self.daten_update()
            self.grafik_update()

    def update(self):
        if self.von_combo.count() == 0:
            self.update_combos()
        if self._strecke_von and self._strecke_nach:
            self.update_strecke()
            self.daten_update()
            self.grafik_update()

    def daten_update(self):
        self._zuglaeufe = {}
        for zug in self.planung.zugliste.values():
            self.update_zuglauf(zug)

    def update_strecke(self):
        if self._strecke_von and self._strecke_nach:
            if self._strecke_via:
                von_gleis = self._strecke_von
                nach_gleis = self._strecke_via
                strecke1 = self.anlage.verbindungsstrecke(von_gleis, nach_gleis)
                von_gleis = self._strecke_via
                nach_gleis = self._strecke_nach
                strecke2 = self.anlage.verbindungsstrecke(von_gleis, nach_gleis)
                strecke = [*strecke1[:-1], *strecke2]
            else:
                von_gleis = self._strecke_von
                nach_gleis = self._strecke_nach
                strecke = self.anlage.verbindungsstrecke(von_gleis, nach_gleis)
        else:
            strecke = []

        self.strecke_list.clear()
        self.strecke_list.addItems(strecke)

        if len(strecke):
            sd = self.anlage.get_strecken_distanzen(strecke)
            self._strecke = strecke
            self._distanz = [v / 60 for v in sd]

        self.setWindowTitle(f"Bildfahrplan {self._strecke_von}-{self._strecke_nach}")

    def update_zuglauf(self, zug: ZugDetailsPlanung):
        self._update_zuglauf_richtung(zug, +1)
        self._update_zuglauf_richtung(zug, -1)

    def _update_zuglauf_richtung(self, zug: ZugDetailsPlanung, richtung: int):
        richtung = +1 if richtung >= 0 else -1
        color = self.farbschema.zugfarbe(zug)
        zuglauf = []
        strecke = self._strecke
        distanz = self._distanz

        plan1 = zug.fahrplan[0]
        i_gruppe1 = 0 if richtung > 0 else -1
        i_gruppe2 = 0
        an_vorher = 0
        for plan2 in zug.fahrplan[1:]:
            trasse = Trasse()
            trasse.zug = zug
            trasse.richtung = richtung
            trasse.color = color
            trasse.start = plan1
            trasse.ziel = plan2

            try:
                gruppe1 = self.anlage.gleiszuordnung[plan1.gleis]
            except KeyError:
                logger.warning(f"gleis {plan1.gleis} ({zug.name}) kann keinem bahnhof zugeordnet werden.")
                gruppe1 = ""
            try:
                while strecke[i_gruppe1] != gruppe1:
                    i_gruppe1 += richtung
            except IndexError:
                # startbahnhof nicht in strecke (bzw. nicht in fahrtrichtung)
                # mit nächstem fahrplanziel nochmals versuchen
                i_gruppe1 = i_gruppe2
                plan1 = plan2
                continue

            try:
                gruppe2 = self.anlage.gleiszuordnung[plan2.gleis]
            except KeyError:
                logger.warning(f"gleis {plan2.gleis} ({zug.name}) kann keinem bahnhof zugeordnet werden.")
                gruppe2 = ""
            try:
                i_gruppe2 = i_gruppe1
                while strecke[i_gruppe2] != gruppe2:
                    i_gruppe2 += richtung
            except IndexError:
                # zielbahnhof nicht in strecke (bzw. nicht in fahrtrichtung)
                # richtungswechsel versuchen
                try:
                    i_gruppe2 = i_gruppe1
                    while strecke[i_gruppe2] != gruppe2:
                        i_gruppe2 -= richtung
                    richtung *= -1
                except IndexError:
                    continue

            try:
                ab = time_to_minutes(plan1.ab) + plan1.verspaetung_ab
                an = time_to_minutes(plan2.an) + plan2.verspaetung_an
                trasse.koord = [(distanz[i_gruppe1], max(ab, an_vorher)),
                                (distanz[i_gruppe2], an)]
                an_vorher = an
            except AttributeError:
                pass
            else:
                zuglauf.append(trasse)

            # haltelinie
            try:
                an = time_to_minutes(plan2.an) + plan2.verspaetung_an
                ab = time_to_minutes(plan2.ab) + plan2.verspaetung_ab
            except AttributeError:
                pass
            else:
                if ab > an:
                    trasse = Trasse()
                    trasse.zug = zug
                    trasse.richtung = richtung
                    trasse.color = color
                    trasse.start = plan2
                    trasse.ziel = plan2
                    trasse.halt = True
                    trasse.linestyle = '--'
                    trasse.koord = [(distanz[i_gruppe2], an), (distanz[i_gruppe2], ab)]
                    zuglauf.append(trasse)

            plan1 = plan2

        if zuglauf:
            self._zuglaeufe[(zug.zid, richtung)] = zuglauf
        else:
            try:
                del self._zuglaeufe[(zug.zid, richtung)]
            except KeyError:
                pass

    def grafik_update(self):
        self._axes.clear()

        x_labels = self._strecke
        x_labels_pos = self._distanz

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(5))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        zeit = time_to_minutes(self.client.calc_simzeit())
        ylim = (zeit - self.zeitfenster_zurueck, zeit + self.zeitfenster_voraus)
        self._axes.set_ylim(top=ylim[0], bottom=ylim[1])
        self._axes.set_xlim(left=x_labels_pos[0], right=x_labels_pos[-1])

        try:
            idx = self._strecke.index(self._strecke_via)
        except ValueError:
            pass
        else:
            self._axes.axvline(x=self._distanz[idx], color=mpl.rcParams['grid.color'],
                               linewidth=mpl.rcParams['axes.linewidth'])

        wid_x = x_labels_pos[-1] - x_labels_pos[0]
        wid_y = self.zeitfenster_zurueck + self.zeitfenster_voraus
        off_x = 0
        off = self._axes.transData.inverted().transform([(0, 0), (0, -5)])
        off_y = (off[1] - off[0])[1]

        label_args = {'ha': 'center',
                      'va': 'center',
                      'fontsize': 'small',
                      'fontstretch': 'condensed',
                      'rotation_mode': 'anchor',
                      'transform_rotates_text': True}

        for zuglauf in self._zuglaeufe.values():
            for trasse in zuglauf:
                pos_x = [pos[0] for pos in trasse.koord]
                pos_y = [pos[1] for pos in trasse.koord]
                mpl_lines = self._axes.plot(pos_x, pos_y, picker=True, pickradius=5, **trasse.plot_args())
                mpl_lines[0].trasse = trasse
                seg = trasse.koord
                pix = self._axes.transData.transform(seg)
                cx = (seg[0][0] + seg[1][0]) / 2 + off_x
                cy = (seg[0][1] + seg[1][1]) / 2 + off_y
                dx = (seg[1][0] - seg[0][0])
                dy = (seg[1][1] - seg[0][1])
                if ylim[0] < cy < ylim[1] and abs(pix[1][0] - pix[0][0]) > 30:
                    ang = math.degrees(math.atan(dy / dx))
                    titel = format_label(trasse.start, trasse.ziel)
                    self._axes.text(cx, cy, titel, rotation=ang, **label_args)

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.zeitfenster_zurueck > 0:
            self._axes.axhline(y=zeit, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

        if self._trasse_auswahl:
            try:
                zuglauf = self._zuglaeufe[(self._trasse_auswahl.zug.zid, self._trasse_auswahl.richtung)]
            except KeyError:
                zuglauf = []

            for trasse in zuglauf:
                if trasse.start == self._trasse_auswahl.start and trasse.ziel == self._trasse_auswahl.ziel:
                    pos_x = [pos[0] for pos in trasse.koord]
                    pos_y = [pos[1] for pos in trasse.koord]
                    args = trasse.plot_args()
                    args['color'] = 'yellow'
                    args['alpha'] = 0.5
                    args['linewidth'] = 2
                    self._axes.plot(pos_x, pos_y, **args)
                    break

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def on_resize(self, event):
        self.grafik_update()

    def on_button_press(self, event):
        if self._trasse_auswahl and not self._pick_event:
            self._trasse_auswahl = None
            self.grafik_update()

        self._pick_event = False

    def on_button_release(self, event):
        pass

    def on_pick(self, event):
        auswahl_vorher = self._trasse_auswahl
        self._trasse_auswahl = None
        if event.mouseevent.inaxes == self._axes:
            if isinstance(event.artist, Line2D):
                try:
                    self._trasse_auswahl = event.artist.trasse
                    self._pick_event = True
                except AttributeError:
                    pass
        if self._trasse_auswahl != auswahl_vorher:
            self.grafik_update()

    def on_key_press(self, event):
        if event.key == "+":
            if self._trasse_auswahl:
                self.verspaetung_aendern(self._trasse_auswahl, 1, True)
                self.grafik_update()
        elif event.key == "-":
            if self._trasse_auswahl:
                self.verspaetung_aendern(self._trasse_auswahl, -1, True)
                self.grafik_update()
        elif event.key == "0":
            if self._trasse_auswahl:
                self.verspaetung_aendern(self._trasse_auswahl, 0, False)
                self.grafik_update()

    def verspaetung_aendern(self, trasse: Trasse, verspaetung: int, relativ: bool = False):
        korrektur = trasse.start.fdl_korrektur
        if not isinstance(korrektur, planung.FesteVerspaetung):
            korrektur = planung.FesteVerspaetung(self.planung)
            korrektur.verspaetung = trasse.start.verspaetung_ab

        if relativ:
            korrektur.verspaetung += verspaetung
        else:
            korrektur.verspaetung = verspaetung
        if korrektur.verspaetung == 0:
            korrektur = None

        self.planung.fdl_korrektur_setzen(korrektur, trasse.start)
        self.planung.zugverspaetung_korrigieren(trasse.zug)
        self.update_zuglauf(trasse.zug)

    def abhaengigkeit_definieren(self, trasse: Trasse, referenz: ZugZielPlanung, abfahrt: bool = False,
                                 wartezeit: int = 0):
        if abfahrt:
            korrektur = planung.AbfahrtAbwarten(self.planung)
        else:
            korrektur = planung.AnkunftAbwarten(self.planung)
        korrektur.ursprung = referenz
        korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, trasse.start)
        self.planung.zugverspaetung_korrigieren(trasse.zug)
        self.update_zuglauf(trasse.zug)
