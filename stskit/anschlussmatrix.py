"""
datenstrukturen und fenster für anschlussmatrix


"""
import itertools
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Type, Union

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.image import AxesImage
from matplotlib.text import Text
import numpy as np

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot

from stskit.anlage import Anlage
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung, \
    FesteVerspaetung, ZugAbwarten, AnkunftAbwarten, AbfahrtAbwarten, ZugNichtAbwarten, ZugZielNode
from stskit.stsobj import time_to_minutes
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_anschlussmatrix import Ui_AnschlussmatrixWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


ANSCHLUSS_KEIN = np.nan
ANSCHLUSS_OK = 0
ANSCHLUSS_ABWARTEN = 2
ANSCHLUSS_ERFOLGT = 4
ANSCHLUSS_WARNUNG = 6
ANSCHLUSS_AUFGEBEN = 8
ANSCHLUSS_FLAG = 12
ANSCHLUSS_SELBST = 14
ANSCHLUSS_AUSWAHL_1 = 16
ANSCHLUSS_AUSWAHL_2 = 18

ANSCHLUESSE_VERSPAETET = {ANSCHLUSS_WARNUNG, ANSCHLUSS_ABWARTEN, ANSCHLUSS_AUFGEBEN, ANSCHLUSS_FLAG}


class Anschlussmatrix:
    """
    attribute
    ---------

    - bahnhof: name des bahnhofs in anlage.bahnsteiggruppen.
    - umsteigezeit: minimal nötige umsteigezeit in minuten im bahnhof.
        dies bestimmt einerseits, ob ein zugspaar als anschluss erkannt wird,
        und andererseits um wie viel sich ein abganszug verspätet, wenn er den anschluss abwartet.
    - anschlusszeit: zeitfenster in minuten, in dem anschlüsse erkannt werden.
        definiert damit indirekt auch die länge der matrix.
    - anschlussplan (matrix): umsteigezeit in minuten nach fahrplan.
        ein anschluss besteht, wenn die umsteigezeit grösser als `min_umsteigezeit` und kleiner als `anschlusszeit` ist.
    - anschlussstatus (matrix): status des anschlusses.
        dies ist gleichzeitig auch der numerische wert für die grafische darstellung.
        der automatische status ist eine gerade zahl.
        wenn der status vom fdl quittiert worden ist, wird die nächsthöhere ungerade zahl eingetragen,
        was in der grafik die farbe ausbleicht.
        mögliche werte sind als ANSCHLUSS_XXXX konstanten deklariert.

        nan: kein anschluss
        0/1: anschluss erfüllt
        2/3: anschluss abwarten
        4/5: wartezeit erreicht, zug kann fahren
        6/7: anschlusswarnung
        8/9: anschluss aufgeben
        10/11:
        12/13: flag
        14/15: selber zug
        16/17: auswahlfarbe 1
        18/19: auswahlfarbe 2

    - verspaetung (matrix): geschätzte abgangsverspätung des abgängers in minuten
    - ankunft_label_muster, abfahrt_label_muster: liste von ZUG_SCHILDER,
        die den inhalt der zugbeschriftungen definieren.
    - gleise: set von gleisen, die zum bahnhof gehören (von anlage übernommen)
    - zid_ankuenfte_set, zid_abfahrten_set: zid von zügen, die in der matrix dargestellt sind.
    - zid_ankuenfte_index, zid_abfahrten_index: geordnete liste von zügen, die in der matrix dargestellt sind.
        diese listen definieren die achsen der matrix,
        abfahrten in dimension 0 (zeilen), ankünfte in dimension 1 (spalten).
    - zuege: ZugDetailsPlanung-objekte der in der matrix enthaltenen züge, indiziert nach zid.
    - ankunft_ziele, abfahrt_ziele: ZugZielPlanung-objekte der inder matrix enthaltenen anschlüsse, indiziert nach zid.
    - eff_ankunftszeiten: effektive ankunftszeiten der züge in der matrix, indiziert nach zid.
        die zeit wird in minuten ab mitternacht gemessen.
        dient zur freigabe von anschlüssen nach der min_umsteigezeit.
    - ankunft_labels, abfahrt_labels: zugbeschriftungen, indiziert nach zid.
    - ankunft_filter_kategorien: zugskategorien (s. Anlage.zugschema), die auf der ankunftsachse erscheinen
    - abfahrt_filter_kategorien: zugskategorien (s. Anlage.zugschema), die auf der abfahrtsachse erscheinen
    """

    ZUG_SCHILDER = ['gleis', 'name', 'richtung', 'zeit', 'verspaetung']

    def __init__(self, anlage: Anlage):
        self.anlage: Anlage = anlage
        self.bahnhof: Optional[str] = None
        self.anschlusszeit: int = 15
        self.umsteigezeit: int = 2
        self.ankunft_filter_kategorien: Set[str] = {'X', 'F', 'N', 'S'}
        self.abfahrt_filter_kategorien: Set[str] = {'X', 'F', 'N'}
        self.ankunft_label_muster: List[str] = ['name', 'richtung', 'verspaetung']
        self.abfahrt_label_muster: List[str] = ['name', 'richtung', 'verspaetung']
        self.ankuenfte_ausblenden: Set[int] = set([])
        self.abfahrten_ausblenden: Set[int] = set([])
        self.anschluss_auswahl: Set[Tuple[int, int]] = set([])
        self.anschluss_aufgabe: Set[Tuple[int, int]] = set([])

        self.gleise: Set[str] = set([])
        self.zid_ankuenfte_set: Set[int] = set([])
        self.zid_abfahrten_set: Set[int] = set([])
        self.zid_ankuenfte_index: List[int] = []
        self.zid_abfahrten_index: List[int] = []
        self.zuege: Dict[int, ZugDetailsPlanung] = {}
        self.ankunft_ziele: Dict[int, ZugZielPlanung] = {}
        self.abfahrt_ziele: Dict[int, ZugZielPlanung] = {}
        self.eff_ankunftszeiten: Dict[int, int] = {}
        self.anschlussstatus = np.zeros((0, 0), dtype=np.float)
        self.anschlussplan = np.zeros_like(self.anschlussstatus)
        self.verspaetung = np.zeros_like(self.anschlussstatus)
        self.anzeigematrix = np.zeros_like(self.anschlussstatus)
        self.ankunft_labels: Dict[int, str] = {}
        self.abfahrt_labels: Dict[int, str] = {}

    def set_bahnhof(self, bahnhof: str):
        """
        bahnhof auswählen

        :param bahnhof: muss ein schlüsselwort aus anlage.bahnsteiggruppen sein
        :return: None
        """
        if bahnhof != self.bahnhof:
            self.bahnhof = bahnhof
            self.gleise = self.anlage.bahnsteiggruppen[bahnhof]
            self.zid_ankuenfte_set = set([])
            self.zid_abfahrten_set = set([])

    def format_label(self, ziel: ZugZielPlanung, abfahrt: bool = False) -> str:
        """
        zugbeschriftung nach ankunfts- oder abfahrtsmuster formatieren

        :param ziel: zugziel
        :param abfahrt: abfahrt (True) oder ankunft (False)
        :return: str
        """

        args = {'name': ziel.zug.name, 'gleis': ziel.gleis + ':'}
        if abfahrt:
            muster = list(self.abfahrt_label_muster)
            richtung = ziel.zug.nach
            zeit = ziel.ab
            verspaetung = ziel.verspaetung_ab
        else:
            muster = list(self.ankunft_label_muster)
            richtung = ziel.zug.von
            zeit = ziel.an
            verspaetung = ziel.verspaetung_an

        args['richtung'] = richtung.replace("Gleis ", "").split(" ")[0]

        try:
            zeit = time_to_minutes(zeit)
        except AttributeError:
            try:
                muster.remove("zeit")
            except ValueError:
                pass
        else:
            args['zeit'] = f"{int(zeit) // 60:02}:{int(zeit) % 60:02}"

        if verspaetung > 0:
            args['verspaetung'] = f"({int(verspaetung):+})"
        else:
            try:
                muster.remove("verspaetung")
            except ValueError:
                pass

        beschriftung = " ".join((args[schild] for schild in muster))
        return beschriftung

    def _fahrplan_filter(self, fahrplan: Iterable[ZugZielPlanung], ankuenfte: bool = False, abfahrten: bool = False) \
            -> Iterable[ZugZielPlanung]:
        """
        ankunfts- und abfahrtseintrag aus fahrplan herausfiltern.

        filtert die zugziele für ankunft und abfahrt eines zuges im aktuellen bahnhof.
        in den meisten fällen ergibt das genau ein ziel pro zug.
        bei verknüpften zügen oder rangierfahrten, sind die einträge bei ankunft und abfahrt jedoch nicht die gleichen.

        :param fahrplan: iterable von ZugZielPlanung aus ZugDetailsPlanung.fahrplan
        :param ankuenfte: ankunft zurückgeben
        :param abfahrten: abfahrt zurückgeben
        :return: generator
        """

        letztes: Optional[ZugZielPlanung] = None
        for ziel in fahrplan:
            if not ziel.durchfahrt():
                if ziel.gleis in self.gleise:
                    if letztes is None and ankuenfte:
                        yield ziel
                    letztes = ziel
        if letztes is not None and abfahrten:
            yield letztes

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

        startzeit = planung.simzeit_minuten
        endzeit = startzeit + self.anschlusszeit
        min_umsteigezeit = self.umsteigezeit

        for zid, zug in planung.zugliste.items():
            kategorie = self.anlage.zugschema.kategorie(zug)
            # ankünfte
            if kategorie in self.ankunft_filter_kategorien:
                for ziel in self._fahrplan_filter(zug.fahrplan, True, False):
                    if not ziel.abgefahren and ziel.an is not None and time_to_minutes(ziel.an) < endzeit:
                        # keine ankunft, wenn zug aus nummernwechsel auf diesem gleis hervorgeht
                        zzid = ZugZielNode.neu(ziel=ziel)
                        for zzid1, zzid2, edge_data in planung.zielgraph.in_edges(zzid, data=True):
                            try:
                                if edge_data['typ'] in {'E', 'F'}:
                                    break
                            except KeyError:
                                pass
                        else:
                            self.zid_ankuenfte_set.add(zid)
                            self.zuege[zid] = zug
                            self.ankunft_ziele[zid] = ziel

            # abfahrten
            if kategorie in self.abfahrt_filter_kategorien:
                for ziel in self._fahrplan_filter(zug.fahrplan, False, True):
                    if not ziel.abgefahren and ziel.ab is not None and time_to_minutes(ziel.ab) < endzeit + min_umsteigezeit:
                        # keine abfahrt, wenn zug ersetzt wird
                        if ziel.ersatzzug is None and ziel.kuppelzug is None:
                            self.zid_abfahrten_set.add(zid)
                            self.zuege[zid] = zug
                            self.abfahrt_ziele[zid] = ziel
                        else:
                            self.zid_abfahrten_set.discard(zid)
                    else:
                        self.zid_abfahrten_set.discard(zid)

            if zug.amgleis and zug.gleis in self.gleise and zid not in self.eff_ankunftszeiten:
                try:
                    self.eff_ankunftszeiten[zid] = time_to_minutes(zug.find_fahrplanzeile(gleis=zug.gleis).angekommen)
                except AttributeError:
                    self.eff_ankunftszeiten[zid] = startzeit

        self.zid_ankuenfte_set.difference_update(self.ankuenfte_ausblenden)
        self.zid_abfahrten_set.difference_update(self.abfahrten_ausblenden)
        self.zid_ankuenfte_index = sorted(self.zid_ankuenfte_set, key=lambda z: self.ankunft_ziele[z].an)
        self.zid_abfahrten_index = sorted(self.zid_abfahrten_set, key=lambda z: self.abfahrt_ziele[z].ab)

        n_ab, n_an = len(self.zid_abfahrten_index), len(self.zid_ankuenfte_index)
        a_ab, a_an = n_ab, n_an
        self.anschlussplan = np.ones((a_ab, a_an), dtype=np.float) * np.nan
        self.anschlussstatus = np.ones((a_ab, a_an), dtype=np.float) * np.nan
        self.verspaetung = np.zeros((a_ab, a_an), dtype=np.float)

        for i_ab, zid_ab in enumerate(self.zid_abfahrten_index):
            ziel_ab = self.abfahrt_ziele[zid_ab]
            zeit_ab = time_to_minutes(ziel_ab.ab)

            for i_an, zid_an in enumerate(self.zid_ankuenfte_index):
                ziel_an = self.ankunft_ziele[zid_an]
                zeit_an = time_to_minutes(ziel_an.an)

                plan_umsteigezeit = zeit_ab - zeit_an
                eff_umsteigezeit = plan_umsteigezeit + ziel_ab.verspaetung_ab - ziel_an.verspaetung_an
                verspaetung = zeit_an + ziel_an.verspaetung_an + min_umsteigezeit - zeit_ab

                try:
                    flag = planung.zugbaum.edges[zid_an, zid_ab]['flag']
                except KeyError:
                    flag = ""
                if zid_ab == zid_an or flag in {'E', 'K', 'F'}:
                    if startzeit >= zeit_ab and ziel_an.angekommen:
                        status = ANSCHLUSS_ERFOLGT
                    elif flag == 'K':
                        status = ANSCHLUSS_FLAG
                        verspaetung -= min_umsteigezeit
                    else:
                        status = ANSCHLUSS_SELBST
                elif self.anschlusszeit >= plan_umsteigezeit >= min_umsteigezeit:
                    try:
                        freigabe = startzeit >= self.eff_ankunftszeiten[zid_an] + min_umsteigezeit
                    except KeyError:
                        freigabe = False
                    for korrektur in ziel_ab.fdl_korrektur.values():
                        if isinstance(korrektur, ZugAbwarten) and korrektur.ursprung.zid == zid_an:
                            abwarten = True
                            break
                    else:
                        abwarten = False
                    if freigabe:
                        status = ANSCHLUSS_ERFOLGT
                    elif abwarten:
                        status = ANSCHLUSS_ABWARTEN
                    elif eff_umsteigezeit < min_umsteigezeit:
                        status = ANSCHLUSS_WARNUNG
                    else:
                        status = ANSCHLUSS_OK
                else:
                    status = ANSCHLUSS_KEIN

                self.anschlussplan[i_ab, i_an] = plan_umsteigezeit
                self.anschlussstatus[i_ab, i_an] = status
                self.verspaetung[i_ab, i_an] = verspaetung

        spalten = np.any(~np.isnan(self.anschlussstatus), axis=0)
        self.zid_ankuenfte_index = list(np.asarray(self.zid_ankuenfte_index)[spalten])
        self.zid_ankuenfte_set = set(self.zid_ankuenfte_index)
        self.anschlussplan = self.anschlussplan[:, spalten]
        self.anschlussstatus = self.anschlussstatus[:, spalten]
        self.verspaetung = self.verspaetung[:, spalten]

        aufgabe_auswahl = self._make_auswahl_matrix(self.anschluss_aufgabe)
        aufgabe_maske = np.isin(self.anschlussstatus, [ANSCHLUSS_WARNUNG, ANSCHLUSS_AUFGEBEN, ANSCHLUSS_OK])
        aufgabe_auswahl = np.logical_and(aufgabe_auswahl, aufgabe_maske)
        self.anschlussstatus = np.where(aufgabe_auswahl, ANSCHLUSS_AUFGEBEN, self.anschlussstatus)

        self.ankunft_labels = {zid: self.format_label(self.ankunft_ziele[zid], False)
                               for zid in self.zid_ankuenfte_index}
        self.abfahrt_labels = {zid: self.format_label(self.abfahrt_ziele[zid], True)
                               for zid in self.zid_abfahrten_index}

        loeschen = set(self.zuege.keys()) - self.zid_ankuenfte_set - self.zid_abfahrten_set
        for zid in loeschen:
            del self.zuege[zid]
            try:
                del self.ankunft_ziele[zid]
            except KeyError:
                pass
            try:
                del self.abfahrt_ziele[zid]
            except KeyError:
                pass

    def plot(self, ax):
        """
        anschlussmatrix auf matplotlib-achsen zeichnen

        :param ax: matplotlib-Axes
        :return: None
        """

        kwargs = dict()
        kwargs['alpha'] = 0.5
        kwargs['cmap'] = 'tab20'
        kwargs['picker'] = True

        a_ab, a_an = self.anschlussstatus.shape
        n_ab, n_an = len(self.zid_abfahrten_index), len(self.zid_ankuenfte_index)
        self.anzeigematrix = self.anschlussstatus + self._make_auswahl_matrix(self.anschluss_auswahl)
        im = ax.imshow(self.anzeigematrix, **kwargs)
        im.set_clim((0., 19.))
        ax.set_ylabel('abfahrt')
        ax.set_xlabel('ankunft')
        try:
            x_labels = [self.ankunft_labels[zid] for zid in self.zid_ankuenfte_index] + [''] * (a_an - n_an)
            x_labels_colors = [self.anlage.zugschema.zugfarbe(self.zuege[zid])
                               for zid in self.zid_ankuenfte_index] + ['w'] * (a_an - n_an)
            x_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleise else 'normal'
                                for zid in self.zid_ankuenfte_index] + ['normal'] * (a_an - n_an)
            y_labels = [self.abfahrt_labels[zid] for zid in self.zid_abfahrten_index] + [''] * (a_ab - n_ab)
            y_labels_colors = [self.anlage.zugschema.zugfarbe(self.zuege[zid])
                               for zid in self.zid_abfahrten_index] + ['w'] * (a_ab - n_ab)
            y_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleise else 'normal'
                                for zid in self.zid_abfahrten_index] + ['normal'] * (a_ab - n_ab)
        except KeyError as e:
            logger.warning(e)
            return

        ax.set_xticks(np.arange(a_an), labels=x_labels, rotation=45, rotation_mode='anchor',
                      horizontalalignment='left', verticalalignment='bottom')
        ax.set_yticks(np.arange(a_ab), labels=y_labels)
        ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

        for zid, label, color, weight in zip(self.zid_ankuenfte_index, ax.get_xticklabels(), x_labels_colors,
                                             x_labels_weigths):
            label.set_color(color)
            label.set_fontweight(weight)
            label.set_picker(True)
            label.zids = (-1, zid)
        for zid, label, color, weight in zip(self.zid_abfahrten_index, ax.get_yticklabels(), y_labels_colors,
                                             y_labels_weigths):
            label.set_color(color)
            label.set_fontweight(weight)
            label.set_picker(True)
            label.zids = (zid, -1)

        ax.set_xticks(np.arange(a_an + 1) - .5, minor=True)
        ax.set_yticks(np.arange(a_ab + 1) - .5, minor=True)
        ax.grid(which="minor", color=mpl.rcParams['axes.facecolor'], linestyle='-', linewidth=3)
        ax.tick_params(which="minor", bottom=False, left=False)

        for i in range(n_ab):
            for j in range(n_an):
                v = self.verspaetung[i, j]
                if self.anschlussstatus[i, j] in ANSCHLUESSE_VERSPAETET and v > 0:
                    text = ax.text(j, i, round(v),
                                   ha="center", va="center", color="w", fontsize="small")

        for item in (ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontsize('small')

        ax.figure.tight_layout()
        ax.figure.canvas.draw()

    def _make_auswahl_matrix(self, auswahl: Iterable[Tuple[int, int]]):
        """
        erstellt eine auswahlmatrix aus einer liste von anschlüssen

        :param auswahl: iterable von (zid_ab, zid_an)-tupeln
            negative werte wählen eine ganze spalte bzw. zeile aus.
        :return: matrix mit der gleichen grösse wie self.anschlussstatus.
            die matrix enthält einsen an den ausgewählten anschlussrelationen und nullen in den übrigen elementen.
        """

        matrix = np.zeros_like(self.anschlussstatus)
        for zid_ab, zid_an in auswahl:
            try:
                if zid_ab >= 0:
                    i_ab = self.zid_abfahrten_index.index(zid_ab)
                else:
                    i_ab = -1
            except ValueError:
                continue

            try:
                if zid_an >= 0:
                    i_an = self.zid_ankuenfte_index.index(zid_an)
                else:
                    i_an = -1
            except ValueError:
                continue

            if i_an < 0:
                matrix[i_ab, :] = 1
            elif i_ab < 0:
                matrix[:, i_an] = 1
            elif i_an >= 0 and i_ab >= 0:
                matrix[i_ab, i_an] = 1
            else:
                matrix[:, :] = 0

        return matrix

    def auswahl_expandieren(self, auswahl: Iterable[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        result = set([])
        for zid_ab, zid_an in auswahl:
            if zid_ab >= 0:
                _zids_ab = [zid_ab]
            else:
                _zids_ab = self.zid_abfahrten_index
            if zid_an >= 0:
                _zids_an = [zid_an]
            else:
                _zids_an = self.zid_ankuenfte_index
            result.update(itertools.product(_zids_ab, _zids_an))
        return result

    def abfahrt_suchen(self, ankunft_zid: int) -> List[int]:
        """
        abfahrts-zid eines zuges suchen

        :param ankunft_zid: zid bei ankunft
        :return: zids bei abfahrt.
            die liste kann kein (zug endet oder fährt ausserhalb des anschlussfensters weiter),
            ein (zug fährt weiter) oder
            zwei (zug flügelt) elemente enthalten.
        """

        index = self.zid_ankuenfte_index.index(ankunft_zid)
        abfahrten = self.anschlussstatus[:, index]
        index_ab = np.nonzero(abfahrten == ANSCHLUSS_SELBST)[0]
        zid_ab = [self.zid_abfahrten_index[idx] for idx in index_ab]
        return zid_ab


class AnschlussmatrixWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.anschlussmatrix: Optional[Anschlussmatrix] = None
        self._pick_event: bool = False

        self.in_update = True
        self.ui = Ui_AnschlussmatrixWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Anschlussmatrix")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

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
        self.ui.zugbeschriftungTable.itemChanged.connect(self.beschriftung_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_actions()
        self.in_update = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def planung(self) -> Planung:
        return self.zentrale.planung

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

        self.ui.anschlusszeitSpin.setValue(self.anschlussmatrix.anschlusszeit)
        self.ui.umsteigezeitSpin.setValue(self.anschlussmatrix.umsteigezeit)
        self._update_beschriftung_spalte(0, self.anschlussmatrix.ankunft_label_muster)
        self._update_beschriftung_spalte(1, self.anschlussmatrix.abfahrt_label_muster)
        self.ui.zugbeschriftungTable.resizeColumnsToContents()
        self.ui.zugbeschriftungTable.resizeRowsToContents()

        self.in_update = False

    def _update_beschriftung_spalte(self, column: int, schilder: List[str]):
        for row in range(5):
            item = self.ui.zugbeschriftungTable.item(row, column)
            schild = self.anschlussmatrix.ZUG_SCHILDER[row]
            state = QtCore.Qt.Checked if schild in schilder else QtCore.Qt.Unchecked
            item.setCheckState(state)

    @pyqtSlot()
    def bahnhof_changed(self):
        try:
            self.anschlussmatrix.set_bahnhof(self.ui.bahnhofBox.currentText())
            self.setWindowTitle("Anschlussmatrix " + self.anschlussmatrix.bahnhof)
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
    def beschriftung_changed(self):
        if not self.in_update:
            self._beschriftung_spalte_changed(0, self.anschlussmatrix.ankunft_label_muster)
            self._beschriftung_spalte_changed(1, self.anschlussmatrix.abfahrt_label_muster)

    def _beschriftung_spalte_changed(self, column: int, schilder: List[str]):
        schilder.clear()
        for row in range(5):
            item = self.ui.zugbeschriftungTable.item(row, column)
            schild = self.anschlussmatrix.ZUG_SCHILDER[row]
            if item.checkState() == QtCore.Qt.Checked:
                schilder.append(schild)

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.update_widgets()

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
            self.update_widgets()

        if self.anschlussmatrix:
            self.anschlussmatrix.update(self.planung)

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

    @staticmethod
    def format_zuginfo(ziel: ZugZielPlanung, an: bool = False, ab: bool = False):
        """
        zuginfo formatieren

        :return: (str)
        """

        zug = ziel.zug
        name = zug.name

        if an:
            try:
                von = zug.fahrplan[0].gleis
                z1 = ziel.an.isoformat('minutes')
                v1 = f"{ziel.verspaetung_an:+}"
                zt = f"{z1}{v1}"
            except (AttributeError, IndexError):
                pass
            else:
                return f"{name} von {von} an {ziel.gleis} {zt}"
        elif ab:
            try:
                nach = zug.fahrplan[-1].gleis
                z2 = ziel.ab.isoformat('minutes')
                v2 = f"{ziel.verspaetung_ab:+}"
                zt = f"{z2}{v2}"
            except (AttributeError, IndexError):
                pass
            else:
                return f"{name} nach {nach} ab {ziel.gleis} {zt}"
        return ""

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
            info_an = self.format_zuginfo(ziel_an, True, False)
            info.append(info_an)
        except (IndexError, KeyError):
            pass
        try:
            ziel_ab = self.anschlussmatrix.abfahrt_ziele[zids[0]]
            info_ab = self.format_zuginfo(ziel_ab, False, True)
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
                        self.abhaengigkeit_definieren(AnkunftAbwarten,
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
                        self.abhaengigkeit_definieren(AbfahrtAbwarten,
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
                self.abhaengigkeit_definieren(ZugNichtAbwarten,
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
            self.planung.fdl_korrektur_loeschen(self.anschlussmatrix.abfahrt_ziele[zid_ab],
                                                self.anschlussmatrix.ankunft_ziele[zid_an])

        self.planung.verspaetungen_korrigieren()
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

    def verspaetung_aendern(self, ziel: ZugZielPlanung, verspaetung: int, relativ: bool = False):
        neu = True
        for korrektur in ziel.fdl_korrektur.values():
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
                korrektur.verspaetung = ziel.verspaetung_ab + verspaetung
            else:
                korrektur.verspaetung = verspaetung
            self.planung.fdl_korrektur_setzen(korrektur, ziel)

        self.planung.zugverspaetung_korrigieren(ziel.zug)

    def abhaengigkeit_definieren(self, klasse: Type[ZugAbwarten],
                                 ziel: ZugZielPlanung, referenz: ZugZielPlanung,
                                 wartezeit: Optional[int] = None):

        korrektur = klasse(self.planung)
        korrektur.node = ziel
        korrektur.ursprung = referenz
        if wartezeit is not None:
            korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, ziel)
        self.planung.zugverspaetung_korrigieren(ziel.zug)
