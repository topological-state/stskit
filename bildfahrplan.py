import math
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets

from auswertung import Auswertung
from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung, FesteVerspaetung, AnkunftAbwarten, AbfahrtAbwarten
from slotgrafik import hour_minutes_formatter, ZugFarbschema
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung
from zentrale import DatenZentrale

from qt.ui_bildfahrplan import Ui_BildfahrplanWindow

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


def format_zuginfo(trasse: 'Trasse'):
    """
    zug-trasseninfo formatieren

    beispiel:
    ICE 573 A-D: B 2 ab 15:30 +3, C 3 an 15:40 +3

    :param trasse: ausgewaehlte trasse
    :return: (str)
    """

    z1 = trasse.start.ab.isoformat('minutes')
    z2 = trasse.ziel.an.isoformat('minutes')
    v1 = f"{trasse.start.verspaetung_ab:+}"
    v2 = f"{trasse.ziel.verspaetung_an:+}"
    name = trasse.zug.name
    von = trasse.zug.fahrplan[0].gleis
    nach = trasse.zug.fahrplan[-1].gleis

    return f"{name} ({von} - {nach}): {trasse.start.gleis} ab {z1}{v1}, {trasse.ziel.gleis} an {z2}{v2}"


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


class BildFahrplanWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self._strecken_name: str = ""
        self._strecke_von: str = ""
        self._strecke_via: str = ""
        self._strecke_nach: str = ""

        self._trasse_auswahl: List[Trasse] = []
        self._pick_event: bool = False

        # bahnhofname -> distanz [minuten]
        self._strecke: List[str] = []
        self._distanz: List[float] = []
        self._zuglaeufe: Dict[Tuple[int, int], List[Trasse]] = {}

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5
        self.farbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

        self.ui = Ui_BildfahrplanWindow()
        self.ui.setupUi(self)
        self.ui.display_button.setDefaultAction(self.ui.actionAnzeige)

        self.setWindowTitle("Bildfahrplan")

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

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    @property
    def planung(self) -> Planung:
        return self.zentrale.planung

    @property
    def auswertung(self) -> Auswertung:
        return self.zentrale.auswertung

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1
        trasse_auswahl = len(self._trasse_auswahl) >= 1
        trasse_paar = len(self._trasse_auswahl) >= 2

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self._strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionPlusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionMinusEins.setEnabled(display_mode and trasse_auswahl)
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and trasse_paar)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and trasse_paar)

    def update_combos(self):
        name = self._strecken_name
        von = self._strecke_von
        via = self._strecke_via
        nach = self._strecke_nach

        try:
            laengste_strecke = max(self.anlage.strecken.values(), key=len)
        except ValueError:
            laengste_strecke = []
        if not von and len(laengste_strecke) >= 2:
            von = laengste_strecke[0]
        if not nach and len(laengste_strecke) >= 2:
            nach = laengste_strecke[-1]

        gruppen_liste = sorted((gr for gr in self.anlage.gleisgruppen.keys()))
        self.ui.von_combo.clear()
        self.ui.von_combo.addItems(gruppen_liste)
        self.ui.via_combo.clear()
        self.ui.via_combo.addItems(["", *gruppen_liste])
        self.ui.nach_combo.clear()
        self.ui.nach_combo.addItems(gruppen_liste)
        self.ui.vordefiniert_combo.clear()
        self.ui.vordefiniert_combo.addItems([""])
        self.ui.vordefiniert_combo.addItems(self.anlage.strecken.keys())

        if von:
            self.ui.von_combo.setCurrentText(von)
        if via:
            self.ui.via_combo.setCurrentText(via)
        if nach:
            self.ui.nach_combo.setCurrentText(nach)
        if name:
            self.ui.vordefiniert_combo.setCurrentText(name)

    @pyqtSlot()
    def strecke_selection_changed(self):
        self._strecken_name = self.ui.vordefiniert_combo.currentText()
        self._strecke_von = self.ui.von_combo.currentText()
        self._strecke_via = self.ui.via_combo.currentText()
        self._strecke_nach = self.ui.nach_combo.currentText()
        self.update_strecke()

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        if self._strecke_von and self._strecke_nach:
            self.daten_update()
            self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    def planung_update(self, *args, **kwargs):
        if self.ui.von_combo.count() == 0:
            self.update_combos()
        if self._strecke_von and self._strecke_nach:
            self.update_strecke()
            self.daten_update()
            self.grafik_update()
            self.update_actions()

    def daten_update(self):
        self._zuglaeufe = {}
        for zug in self.planung.zugliste.values():
            self.update_zuglauf(zug)

    def update_strecke(self):
        if self._strecken_name in self.anlage.strecken:
            strecke = self.anlage.strecken[self._strecken_name]
        elif self._strecke_von and self._strecke_nach:
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

        self.ui.strecke_list.clear()
        self.ui.strecke_list.addItems(strecke)

        if len(strecke):
            sd = self.anlage.get_strecken_distanzen(strecke)
            self._strecke = strecke
            self._distanz = [v / 60 for v in sd]

        self.setWindowTitle(f"Bildfahrplan {self._strecke_von}-{self._strecke_nach}")
        self.update_actions()

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
        try:
            self._axes.set_xlim(left=x_labels_pos[0], right=x_labels_pos[-1])
        except IndexError:
            return

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

        label_unterdrueckt = False
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
                if ylim[0] < cy < ylim[1]:
                    if abs(pix[1][0] - pix[0][0]) > 30 or label_unterdrueckt:
                        label_unterdrueckt = False
                        try:
                            ang = math.degrees(math.atan(dy / dx))
                        except ZeroDivisionError:
                            pass
                        else:
                            titel = format_label(trasse.start, trasse.ziel)
                            self._axes.text(cx, cy, titel, rotation=ang, **label_args)
                    else:
                        label_unterdrueckt = True

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.zeitfenster_zurueck > 0:
            self._axes.axhline(y=zeit, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

        for tr, farbe in zip(self._trasse_auswahl, ['yellow', 'cyan']):
            self._trasse_markieren(tr, farbe)

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def _trasse_markieren(self, trasse: Trasse, farbe: str):
        """
        zeichnet die angegebene trasse als markierung in einer wählbaren farbe

        die trasse muss teil eines zuglaufs (self.zuglaeufe) sein.

        :param trasse: zu markierendes Trasse-objekt
        :param farbe: matplotlib-farbname
        :return: None
        """

        pos_x = [pos[0] for pos in trasse.koord]
        pos_y = [pos[1] for pos in trasse.koord]
        args = trasse.plot_args()
        args['color'] = farbe
        args['alpha'] = 0.5
        args['linewidth'] = 2
        self._axes.plot(pos_x, pos_y, **args)

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
            if self._trasse_auswahl:
                self._trasse_auswahl = []
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

        die auswahl wird in self._trasse_auswahl gespeichert.
        es können maximal zwei trassen gewählt sein.

        :param event:
        :return:
        """

        if event.mouseevent.inaxes == self._axes:
            auswahl = list(self._trasse_auswahl)
            self._pick_event = True
            if isinstance(event.artist, Line2D):
                try:
                    try:
                        auswahl.remove(event.artist.trasse)
                    except ValueError:
                        auswahl.append(event.artist.trasse)
                except AttributeError:
                    pass

            if len(auswahl) > 2:
                auswahl = auswahl[-2:]
            self._trasse_auswahl = auswahl
            l = [format_zuginfo(tr) for tr in self._trasse_auswahl]
            s = "\n".join(l)
            self.ui.zuginfoLabel.setText(s)

    @pyqtSlot()
    def action_plus_eins(self):
        try:
            self.verspaetung_aendern(self._trasse_auswahl[0], 1, True)
        except IndexError:
            pass

        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_minus_eins(self):
        try:
            self.verspaetung_aendern(self._trasse_auswahl[0], -1, True)
        except IndexError:
            pass

        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_loeschen(self):
        try:
            trasse = self._trasse_auswahl[0]
        except IndexError:
            pass
        else:
            self.planung.fdl_korrektur_setzen(None, trasse.start)
            self.planung.zugverspaetung_korrigieren(trasse.zug)
            self.update_zuglauf(trasse.zug)

        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        try:
            self.abhaengigkeit_definieren(self._trasse_auswahl[0], self._trasse_auswahl[1].start, 1, abfahrt=True)
        except IndexError:
            return

        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        try:
            self.abhaengigkeit_definieren(self._trasse_auswahl[0], self._trasse_auswahl[1].ziel, 1, abfahrt=False)
        except IndexError:
            return

        self.grafik_update()
        self.update_actions()

    def verspaetung_aendern(self, trasse: Trasse, verspaetung: int, relativ: bool = False):
        neu = True
        for korrektur in trasse.start.fdl_korrektur:
            if hasattr(korrektur, "wartezeit"):
                if relativ:
                    korrektur.wartezeit += verspaetung
                    neu = False
            elif hasattr(korrektur, "verspaetung"):
                neu = False
                if relativ:
                    korrektur.verspaetung += verspaetung
                else:
                    korrektur.verspaetung = verspaetung

        if neu:
            korrektur = FesteVerspaetung(self.planung)
            if relativ:
                korrektur.verspaetung = trasse.start.verspaetung_ab + verspaetung
            else:
                korrektur.verspaetung = verspaetung
            self.planung.fdl_korrektur_setzen(korrektur, trasse.start)

        self.planung.zugverspaetung_korrigieren(trasse.zug)
        self.update_zuglauf(trasse.zug)

    def abhaengigkeit_definieren(self, trasse: Trasse, referenz: ZugZielPlanung, wartezeit: int = 0,
                                 abfahrt: bool = False):
        if abfahrt:
            korrektur = AbfahrtAbwarten(self.planung)
        else:
            korrektur = AnkunftAbwarten(self.planung)
        korrektur.ursprung = referenz
        korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, trasse.start)
        self.planung.zugverspaetung_korrigieren(trasse.zug)
        self.update_zuglauf(trasse.zug)
