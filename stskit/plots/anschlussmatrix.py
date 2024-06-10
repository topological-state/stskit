"""
Datenstrukturen für Anschlussmatrix


"""

from enum import IntFlag
import itertools
import logging
from typing import Dict, Iterable, List, Optional, Set, Tuple, Type

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.image import AxesImage
from matplotlib.text import Text
import numpy as np

from stskit.zentrale import DatenZentrale
from stskit.graphs.bahnhofgraph import BahnhofElement
from stskit.graphs.ereignisgraph import EreignisGraphNode
from stskit.graphs.zuggraph import ZugGraphNode
from stskit.zugschema import Zugbeschriftung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


class Anschluss(IntFlag):
    OK = 0
    ABWARTEN = 2
    ERFOLGT = 4
    WARNUNG = 6
    AUFGEBEN = 8
    FLAG = 12
    SELBST = 14
    AUSWAHL1 = 16
    AUSWAHL2 = 18


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
    - zuege: ZugGraphNode-objekte der in der matrix enthaltenen züge, indiziert nach zid.
    - ankunft_ziele, abfahrt_ziele: ZugZielPlanung-objekte der inder matrix enthaltenen anschlüsse, indiziert nach zid.
    - eff_ankunftszeiten: effektive ankunftszeiten der züge in der matrix, indiziert nach zid.
        die zeit wird in minuten ab mitternacht gemessen.
        dient zur freigabe von anschlüssen nach der min_umsteigezeit.
    - ankunft_labels, abfahrt_labels: zugbeschriftungen, indiziert nach zid.
    - ankunft_filter_kategorien: zugskategorien (s. Anlage.zugschema), die auf der ankunftsachse erscheinen
    - abfahrt_filter_kategorien: zugskategorien (s. Anlage.zugschema), die auf der abfahrtsachse erscheinen
    """

    def __init__(self, zentrale: DatenZentrale):
        self.zentrale = zentrale
        self.bahnhof: Optional[BahnhofElement] = None
        self.anschlusszeit: int = 15
        self.umsteigezeit: int = 2
        self.ankunft_filter_kategorien: Set[str] = {'X', 'F', 'N', 'S'}
        self.abfahrt_filter_kategorien: Set[str] = {'X', 'F', 'N'}
        self.ankunft_beschriftung = Zugbeschriftung(stil='Anschlussmatrix')
        self.abfahrt_beschriftung = Zugbeschriftung(stil='Anschlussmatrix')
        self.ankuenfte_ausblenden: Set[int] = set([])
        self.abfahrten_ausblenden: Set[int] = set([])
        self.anschluss_auswahl: Set[Tuple[int, int]] = set([])
        self.anschluss_aufgabe: Set[Tuple[int, int]] = set([])

        self.gleisnamen: Set[str] = set([])
        self.zid_ankuenfte_set: Set[int] = set([])
        self.zid_abfahrten_set: Set[int] = set([])
        self.zid_ankuenfte_index: List[int] = []
        self.zid_abfahrten_index: List[int] = []
        self.zuege: Dict[int, ZugGraphNode] = {}
        self.ankunft_ziele: Dict[int, EreignisGraphNode] = {}
        self.abfahrt_ziele: Dict[int, EreignisGraphNode] = {}
        self.anschlussstatus = np.zeros((0, 0), dtype=float)
        self.anschlussplan = np.zeros_like(self.anschlussstatus)
        self.verspaetung = np.zeros_like(self.anschlussstatus)
        self.anzeigematrix = np.zeros_like(self.anschlussstatus)
        self.ankunft_labels: Dict[int, str] = {}
        self.abfahrt_labels: Dict[int, str] = {}

    def set_bahnhof(self, bahnhof: BahnhofElement):
        """
        Bahnhof auswählen

        :param bahnhof: Muss im Bahnhofgraph definiert sein.
        :return: None
        """
        if bahnhof != self.bahnhof:
            self.bahnhof = bahnhof
            self.gleisnamen = {name for typ, name in self.zentrale.anlage.bahnhofgraph.list_children(bahnhof, {'Gl'})}
            self.zid_ankuenfte_set = set([])
            self.zid_abfahrten_set = set([])

    def update(self):
        """
        Daten für Anschlussmatrix zusammentragen

        1. Die Listen der in Frage kommenden Züge werden zusammengestellt.
            Dies sind Züge, die innerhalb des Zeitfensters ankommen oder abfahren,
            nicht durchfahren und nicht schon angekommen bzw. abgefahren sind.
            Betriebliche Vorgänge wie Nummernwechsel erzeugen keine separaten Einträge.

        2. Ankunfts- und Abfahrtstabellen werden nach Zeit sortiert.

        3. Umsteigezeiten und Anschlussstatus werden für jede mögliche Verbindung berechnet.

        :return:
        """

        startzeit = self.zentrale.simzeit_minuten
        endzeit = startzeit + self.anschlusszeit
        min_umsteigezeit = self.umsteigezeit
        zuggraph = self.zentrale.betrieb.zuggraph
        ereignisgraph = self.zentrale.betrieb.ereignisgraph
        zielgraph = self.zentrale.betrieb.zielgraph

        kats = {zid: self.zentrale.anlage.zugschema.kategorie(zug)
                for zid, zug in zuggraph.nodes(data=True)
                if not zug.ausgefahren}

        zids_an = {zid for zid, kat in kats.items()
                   if kat in self.ankunft_filter_kategorien}
        zids_ab = {zid for zid, kat in kats.items()
                   if kat in self.abfahrt_filter_kategorien}

        ereignisse = {label: data for label, data in ereignisgraph.nodes(data=True)
                      if data.get('t_mess', None) is None
                      and data.t_plan is not None
                      and data.plan in self.gleisnamen}

        ankunftsereignisse = {label: data for label, data in ereignisse.items()
                              if data.typ == "An"
                              and data.zid in zids_an
                              and data.t_plan < endzeit}
        abfahrtsereignisse = {label: data for label, data in ereignisse.items()
                              if data.typ == "Ab"
                              and data.zid in zids_ab
                              and data.t_plan < endzeit + min_umsteigezeit}
        zids_abgefahren = {data.zid for label, data in ereignisgraph.nodes(data=True)
                           if data.typ == "Ab"
                           and data.zid in zids_ab
                           and data.get('t_mess', startzeit) < startzeit - 1}

        self.zid_ankuenfte_set.update((label.zid for label in ankunftsereignisse.keys()))
        self.zid_abfahrten_set.update((label.zid for label in abfahrtsereignisse.keys()))
        self.zid_abfahrten_set.difference_update(zids_abgefahren)

        for label, data in ankunftsereignisse.items():
            self.zuege[label.zid] = zuggraph.nodes[label.zid]
            self.ankunft_ziele[label.zid] = data

        for label, data in abfahrtsereignisse.items():
            self.zuege[label.zid] = zuggraph.nodes[label.zid]
            self.abfahrt_ziele[label.zid] = data

        self.zid_ankuenfte_set.difference_update(self.ankuenfte_ausblenden)
        self.zid_abfahrten_set.difference_update(self.abfahrten_ausblenden)
        self.zid_ankuenfte_index = sorted(self.zid_ankuenfte_set, key=lambda z: self.ankunft_ziele[z].t_plan)
        self.zid_abfahrten_index = sorted(self.zid_abfahrten_set, key=lambda z: self.abfahrt_ziele[z].t_plan)

        n_ab, n_an = len(self.zid_abfahrten_index), len(self.zid_ankuenfte_index)
        a_ab, a_an = n_ab, n_an
        self.anschlussplan = np.ones((a_ab, a_an), dtype=float) * np.nan
        self.anschlussstatus = np.ones((a_ab, a_an), dtype=float) * np.nan
        self.verspaetung = np.zeros((a_ab, a_an), dtype=float)

        for i_ab, zid_ab in enumerate(self.zid_abfahrten_index):
            ereignis_ab = self.abfahrt_ziele[zid_ab]
            zeit_ab = ereignis_ab.t_plan
            verspaetung_ab = ereignis_ab.t_prog - ereignis_ab.t_plan

            for i_an, zid_an in enumerate(self.zid_ankuenfte_index):
                ereignis_an = self.ankunft_ziele[zid_an]
                zeit_an = ereignis_an.t_plan
                verspaetung_an = ereignis_an.t_prog - ereignis_an.t_plan

                plan_umsteigezeit = zeit_ab - zeit_an
                eff_umsteigezeit = (plan_umsteigezeit + verspaetung_ab - verspaetung_an)
                verspaetung = zeit_an + verspaetung_an + min_umsteigezeit - zeit_ab

                try:
                    edge_data = zielgraph.get_edge_data(ereignis_an.fid, ereignis_ab.fid)
                    flag = edge_data.typ
                except AttributeError:
                    flag = ""

                if zid_ab == zid_an or flag in {'E', 'K', 'F'}:
                    if startzeit >= zeit_ab and ereignis_an.get('t_mess', None) is not None:
                        status = ANSCHLUSS_ERFOLGT
                    elif flag == 'K':
                        status = ANSCHLUSS_FLAG
                        verspaetung -= min_umsteigezeit
                    else:
                        status = ANSCHLUSS_SELBST
                elif self.anschlusszeit >= plan_umsteigezeit >= min_umsteigezeit:
                    try:
                        freigabe = startzeit >= ereignis_an.get('t_mess', startzeit) + min_umsteigezeit
                    except AttributeError:
                        freigabe = False

                    # todo : fdl-korrektur
                    # abwarten = True
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

        self.ankunft_labels = {zid: self.ankunft_beschriftung.format(self.zuege[zid], self.ankunft_ziele[zid], 'Ankunft')
                               for zid in self.zid_ankuenfte_index}
        self.abfahrt_labels = {zid: self.abfahrt_beschriftung.format(self.zuege[zid], self.abfahrt_ziele[zid], 'Abfahrt')
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
        ax.set_ylabel('Abfahrt')
        ax.set_xlabel('Ankunft')
        try:
            x_labels = [self.ankunft_labels[zid] for zid in self.zid_ankuenfte_index] + [''] * (a_an - n_an)
            x_labels_colors = [self.zentrale.anlage.zugschema.zugfarbe(self.zuege[zid])
                               for zid in self.zid_ankuenfte_index] + ['w'] * (a_an - n_an)
            x_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleisnamen else 'normal'
                                for zid in self.zid_ankuenfte_index] + ['normal'] * (a_an - n_an)
            y_labels = [self.abfahrt_labels[zid] for zid in self.zid_abfahrten_index] + [''] * (a_ab - n_ab)
            y_labels_colors = [self.zentrale.anlage.zugschema.zugfarbe(self.zuege[zid])
                               for zid in self.zid_abfahrten_index] + ['w'] * (a_ab - n_ab)
            y_labels_weigths = ['bold' if self.zuege[zid].amgleis and self.zuege[zid].gleis in self.gleisnamen else 'normal'
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
