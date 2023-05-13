import itertools
import math
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Type, Union

import matplotlib as mpl
from PyQt5.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets

from stskit.auswertung import Auswertung
from stskit.anlage import Anlage
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung, FesteVerspaetung, \
    AnkunftAbwarten, AbfahrtAbwarten, ZugAbwarten, ZugNichtAbwarten
from stskit.slotgrafik import hour_minutes_formatter
from stskit.stsplugin import PluginClient
from stskit.stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung
from stskit.zentrale import DatenZentrale
from stskit.zugschema import Zugbeschriftung

from stskit.qt.ui_bildfahrplan import Ui_BildfahrplanWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


def format_label(zugbeschriftung: Zugbeschriftung, plan1: ZugZielPlanung, plan2: ZugZielPlanung):
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

    if "Name" in zugbeschriftung.elemente:
        name = plan1.zug.name
    elif "Nummer" in zugbeschriftung.elemente:
        name = plan1.zug.nummer
    else:
        name = ""

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
    koord: List[Tuple[float, float]]
    halt: bool = False
    color: str = "b"
    titel: str = ""
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

        for korr in self.start.fdl_korrektur.values():
            if isinstance(korr, AbfahrtAbwarten) or \
                    isinstance(korr, AnkunftAbwarten) or \
                    isinstance(korr, FesteVerspaetung):
                args['marker'] = 's'
                break
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
        self.zugbeschriftung = Zugbeschriftung(stil="Bildfahrplan")

        self._trasse_auswahl: List[Trasse] = []
        self._pick_event: bool = False

        # bahnhofname -> distanz [minuten]
        self._strecke: List[str] = []
        self._distanz: List[float] = []
        self._zuglaeufe: Dict[Tuple[int, int], List[Trasse]] = {}

        self.vorlaufzeit = 55
        self.nachlaufzeit = 5

        self.ui = Ui_BildfahrplanWindow()
        self.ui.setupUi(self)

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

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.default_strecke_waehlen()
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
        if trasse_paar:
            try:
                trasse_nachbar, _ = self.nachbartrasse_ziel(self._trasse_auswahl[0], self._trasse_auswahl[1])
            except ValueError:
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

        gruppen_liste = sorted((gr for gr in self.anlage.gleisgruppen.keys()))
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

        self._strecke_von = strecke[0]
        self._strecke_nach = strecke[-1]
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
            self._strecken_name = name
            self._strecke_von = von
            self._strecke_via = via
            self._strecke_nach = nach
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
        self._zuglaeufe = {}
        for zug in self.planung.zugliste.values():
            self.update_zuglauf(zug)

    def update_strecke(self):
        """
        streckenauswahl von einstellungen übernehmen.

        die einstellungen stehen in _strecken_name, _strecke_von, etc.
        wenn _strecken_name gesetzt ist, werden die anderen attribute nicht beachtet.

        die methode aktualisert die streckenliste auf der einstellungsseite und den fenstertitel,
        aktualisiert die werkzeugleiste,
        stösst aber keine neuberechnung der grafik an.

        :return: None
        """

        if self._strecken_name in self.anlage.strecken:
            strecke = self.anlage.strecken[self._strecken_name]
            titel = f"Bildfahrplan {self._strecken_name}"
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
            titel = f"Bildfahrplan {self._strecke_von}-{self._strecke_nach}"
        else:
            strecke = []
            titel = "Bildfahrplan (keine Strecke ausgewählt)"

        self.ui.strecke_list.clear()
        self.ui.strecke_list.addItems(strecke)

        if len(strecke):
            sd = self.anlage.get_strecken_distanzen(strecke)
            self._strecke = strecke
            self._distanz = [v / 60 for v in sd]

        self.setWindowTitle(titel)
        self.update_actions()

    def update_zuglauf(self, zug: ZugDetailsPlanung):
        self._update_zuglauf_richtung(zug, +1)
        self._update_zuglauf_richtung(zug, -1)

    def _update_zuglauf_richtung(self, zug: ZugDetailsPlanung, richtung: int):
        richtung = +1 if richtung >= 0 else -1
        color = self.anlage.zugschema.zugfarbe(zug)
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
            trasse.titel = format_label(self.zugbeschriftung, trasse.start, trasse.ziel)

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
        ylim = (zeit - self.nachlaufzeit, zeit + self.vorlaufzeit)
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
        wid_y = self.nachlaufzeit + self.vorlaufzeit
        off_x = 0
        off = self._axes.transData.inverted().transform([(0, 0), (0, -5)])
        off_y = (off[1] - off[0])[1]

        self._strecken_markieren(x_labels, x_labels_pos)

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
                            self._axes.text(cx, cy, trasse.titel, rotation=ang, **label_args)
                    else:
                        label_unterdrueckt = True

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.nachlaufzeit > 0:
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

    def _strecken_markieren(self, x_labels, x_labels_pos):
        """
        strecken mit einer schraffur markieren

        :param x_labels: liste von gleisnamen
        :param x_labels_pos: liste von x-koordinaten der gleise
        :param kwargs: kwargs-dict, der für die axes.bar-methode vorgesehen ist.
        :return: None
        """

        try:
            markierungen = self.anlage.streckenmarkierung
        except AttributeError:
            markierungen = {}

        ylim = self._axes.get_ylim()
        h = max(ylim) - min(ylim)
        for strecke, art in markierungen.items():
            try:
                x1 = x_labels_pos[x_labels.index(strecke[0])]
                x2 = x_labels_pos[x_labels.index(strecke[1])]
                xy = (x1, min(ylim))
                w = x2 - x1
            except ValueError:
                continue

            color = mpl.rcParams['grid.color']
            r = mpl.patches.Rectangle(xy, w, h, color=color, alpha=0.1, linewidth=None)
            self._axes.add_patch(r)

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
            ziel1 = self._trasse_auswahl[0].start
        except (IndexError, AttributeError, KeyError):
            pass
        else:
            try:
                _, ziel2 = self.nachbartrasse_ziel(self._trasse_auswahl[0], self._trasse_auswahl[1])
            except (IndexError, AttributeError, KeyError, ValueError):
                ziel2 = None

            self.planung.fdl_korrektur_loeschen(ziel1, ziel2, alle=len(self._trasse_auswahl) == 1)
            self.planung.zugverspaetung_korrigieren(ziel1.zug)
            self.grafik_update()
        self.update_actions()

    def nachbartrasse_ziel(self, trasse: Trasse, nachbar: Trasse) -> Tuple[int, ZugZielPlanung]:
        bf1 = self.anlage.gleiszuordnung[trasse.start.plan]
        bf2s = self.anlage.gleiszuordnung[nachbar.start.plan]
        bf2z = self.anlage.gleiszuordnung[nachbar.ziel.plan]
        if bf1 == bf2s:
            return 0, nachbar.start
        elif bf1 == bf2z:
            return 1, nachbar.ziel
        else:
            raise ValueError("Trassen sind nicht benachbart")

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        try:
            i, z = self.nachbartrasse_ziel(self._trasse_auswahl[0], self._trasse_auswahl[1])
            if i == 0:
                self.abhaengigkeit_definieren(AbfahrtAbwarten, self._trasse_auswahl[0], z)
        except (IndexError, ValueError):
            pass
        else:
            self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        try:
            i, z = self.nachbartrasse_ziel(self._trasse_auswahl[0], self._trasse_auswahl[1])
            if i == 1:
                self.abhaengigkeit_definieren(AnkunftAbwarten, self._trasse_auswahl[0], z)
        except (IndexError, ValueError):
            pass
        else:
            self.grafik_update()
        self.update_actions()

    def verspaetung_aendern(self, trasse: Trasse, verspaetung: int, relativ: bool = False):
        neu = True
        for korrektur in trasse.start.fdl_korrektur.values():
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

    def abhaengigkeit_definieren(self, klasse: Type[ZugAbwarten],
                                 trasse: Trasse, referenz: ZugZielPlanung,
                                 wartezeit: Optional[int] = None):

        korrektur = klasse(self.planung)
        korrektur.node = trasse.start
        korrektur.ursprung = referenz
        if wartezeit is not None:
            korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, trasse.start)
        self.planung.zugverspaetung_korrigieren(trasse.zug)
        self.update_zuglauf(trasse.zug)
