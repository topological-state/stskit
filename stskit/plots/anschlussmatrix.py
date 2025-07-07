"""
Datenstrukturen für Anschlussmatrix


"""

from enum import IntFlag
import itertools
import logging
from typing import Dict, Iterable, List, Optional, Set, Tuple

import matplotlib as mpl
import numpy as np

from stskit.zentrale import DatenZentrale
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.ereignisgraph import EreignisGraphNode, EreignisLabelType
from stskit.model.zuggraph import ZugGraphNode
from stskit.plugin.stsobj import format_minutes, format_verspaetung
from stskit.model.zugschema import Zugbeschriftung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
    Attribute
    ---------

    Die folgenden Attribute dienen zur Konfiguration:

    - bahnhof: Typ und Name des Bahnhofs.
    - umsteigezeit: Minimal nötige Umsteigezeit in Minuten.
        Diese bestimmt einerseits, ob ein Zugspaar als Anschluss erkannt wird,
        und andererseits um wie viel sich ein Abganszug verspätet, wenn er den Anschluss abwartet.
    - anschlusszeit: Zeitfenster in minuten, in dem anschlüsse erkannt werden.
        Definiert damit indirekt auch die Länge der Matrix.
    - ankunft_filter_kategorien: Zugskategorien (s. Anlage.zugschema), die auf der Ankunftsachse erscheinen
    - abfahrt_filter_kategorien: Zugskategorien (s. Anlage.zugschema), die auf der Abfahrtsachse erscheinen

    Die folgenden Attribute werden von der Anlage abgeleitet:

    - gleisnamen: Set von Gleisen, die zum Bahnhof gehören (von anlage übernommen)
    - zuege: ZugGraphNode-Objekte der in der Matrix enthaltenen Züge, indiziert nach zid.
    - zid_ankuenfte_set, zid_abfahrten_set: zid von Zügen, die in der Matrix dargestellt sind.
    - zid_ankuenfte_index, zid_abfahrten_index: Geordnete Liste von Zügen, die in der Matrix dargestellt sind.
        Diese Listen definieren die Achsen der Matrix,
        Abfahrten in Dimension 0 (Zeilen), Ankünfte in Dimension 1 (Spalten).
    - ankunft_ereignisse, abfahrt_ereignisse: Ereignisobjekte der in der Matrix enthaltenen Anschlüsse, indiziert nach zid.

    Die folgenden Attribute werden in der grafischen Darstellung verwendet:

    - anschlussplan (matrix): Umsteigezeit in Minuten nach Fahrplan.
        Ein Anschluss besteht, wenn die planmässige verfügbare Zeit zwischen Ankunft und Abfahrt der Züge
        grösser als `min_umsteigezeit` und kleiner als `anschlusszeit` ist.
    - anschlussstatus (matrix): Status des Anschlusses.
        Dies ist gleichzeitig auch der numerische Wert für die grafische Darstellung.
        Der automatische Status ist eine gerade Zahl.
        wenn der Status vom Fdl quittiert worden ist, wird die nächsthöhere ungerade Zahl eingetragen,
        was in der Grafik die Farbe ausbleicht.
        Mögliche Werte sind als ANSCHLUSS_XXXX-Konstanten deklariert.

        nan: kein Anschluss
        0/1: Anschluss erfüllt
        2/3: Anschluss abwarten
        4/5: Wartezeit erreicht, Zug kann fahren
        6/7: Anschlusswarnung
        8/9: Anschluss aufgeben
        10/11:
        12/13: Flag-gesteuerter Anschluss
        14/15: gleicher Zug
        16/17: Auswahlfarbe 1
        18/19: Auswahlfarbe 2

    - verspaetung (matrix): Geschätzte Abgangsverspätung in Minuten
    - ankunft_labels, abfahrt_labels: Achsenbeschriftungen, indiziert nach zid.
    - ankunft_insets, abfahrt_insets: Inset-Zugbeschriftungen, indiziert nach zid.
    """

    def __init__(self, zentrale: DatenZentrale):
        self.zentrale = zentrale
        self.bahnhof: Optional[BahnhofElement] = None
        self.anschlusszeit: int = 15
        self.umsteigezeit: int = 2
        self.ankunft_filter_kategorien: Set[str] = {'X', 'F', 'N', 'S'}
        self.abfahrt_filter_kategorien: Set[str] = {'X', 'F', 'N'}
        self.beschriftung = Zugbeschriftung(self.zentrale.anlage)
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
        self.ankunft_ereignisse: Dict[int, EreignisGraphNode] = {}
        self.abfahrt_ereignisse: Dict[int, EreignisGraphNode] = {}
        self.anschlussstatus = np.zeros((0, 0), dtype=float)
        self.anschlussplan = np.zeros_like(self.anschlussstatus)
        self.verspaetung = np.zeros_like(self.anschlussstatus)
        self.anzeigematrix = np.zeros_like(self.anschlussstatus)
        self.ankunft_labels: Dict[int, str] = {}
        self.abfahrt_labels: Dict[int, str] = {}
        self.ankunft_insets: Dict[int, str] = {}
        self.abfahrt_insets: Dict[int, str] = {}

    def set_bahnhof(self, bahnhof: BahnhofElement):
        """
        Bahnhof auswählen

        :param bahnhof: Muss im Bahnhofgraph definiert sein.
        :return: None
        """
        if bahnhof != self.bahnhof:
            self.bahnhof = bahnhof
            try:
                self.gleisnamen = {name for typ, name in self.zentrale.anlage.bahnhofgraph.list_children(bahnhof, {'Gl'})}
            except KeyError:
                self.gleisnamen = set()
            self.zid_ankuenfte_set = set()
            self.zid_abfahrten_set = set()

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
        zuggraph = self.zentrale.anlage.zuggraph.vollstaendige_zuege()
        ereignisgraph = self.zentrale.anlage.ereignisgraph
        zielgraph = self.zentrale.anlage.zielgraph

        def _zug_haelt(_label: EreignisLabelType):
            for _u, _v, _data in ereignisgraph.out_edges(_label, data=True):
                if _data.get('typ') in {'H', 'B', 'E', 'F', 'K'}:
                    return True
            return False

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
                              and data.t_plan < endzeit
                              and _zug_haelt(label)}
        abfahrtsereignisse = {label: data for label, data in ereignisse.items()
                              if data.typ == "Ab"
                              and data.zid in zids_ab
                              and data.t_plan < endzeit + min_umsteigezeit}
        zids_abgefahren = {data.zid for label, data in ereignisgraph.nodes(data=True)
                           if data.typ == "Ab"
                           and data.zid in zids_ab
                           and data.plan in self.gleisnamen
                           and data.get('t_mess', startzeit) < startzeit - 1}
        zids_ausgefahren = {zid for zid, zug in zuggraph.nodes(data=True)
                            if zug.ausgefahren}

        self.zid_ankuenfte_set.update((label.zid for label in ankunftsereignisse.keys()))
        self.zid_ankuenfte_set.difference_update(zids_ausgefahren)
        self.zid_abfahrten_set.update((label.zid for label in abfahrtsereignisse.keys()))
        self.zid_abfahrten_set.difference_update(zids_abgefahren)
        self.zid_abfahrten_set.difference_update(zids_ausgefahren)

        for label, data in ankunftsereignisse.items():
            self.zuege[label.zid] = zuggraph.nodes[label.zid]
            self.ankunft_ereignisse[label.zid] = data

        for label, data in abfahrtsereignisse.items():
            self.zuege[label.zid] = zuggraph.nodes[label.zid]
            self.abfahrt_ereignisse[label.zid] = data

        self.zid_ankuenfte_set.difference_update(self.ankuenfte_ausblenden)
        self.zid_abfahrten_set.difference_update(self.abfahrten_ausblenden)

        def _sortierung(ereignis_dict: Dict[int, EreignisGraphNode]):
            def _key(zid) -> Tuple[int, int]:
                ereignis = ereignis_dict[zid]
                zug = self.zuege[zid]
                return ereignis.t_plan, zug.nummer
            return _key

        self.zid_ankuenfte_index = sorted(self.zid_ankuenfte_set, key=_sortierung(self.ankunft_ereignisse))
        self.zid_abfahrten_index = sorted(self.zid_abfahrten_set, key=_sortierung(self.abfahrt_ereignisse), reverse=True)

        n_ab, n_an = len(self.zid_abfahrten_index), len(self.zid_ankuenfte_index)
        a_ab, a_an = n_ab, n_an
        self.anschlussplan = np.ones((a_ab, a_an), dtype=float) * np.nan
        self.anschlussstatus = np.ones((a_ab, a_an), dtype=float) * np.nan
        self.verspaetung = np.zeros((a_ab, a_an), dtype=float)

        for i_ab, zid_ab in enumerate(self.zid_abfahrten_index):
            ereignis_ab = self.abfahrt_ereignisse[zid_ab]
            zeit_ab = ereignis_ab.t_plan
            verspaetung_ab = ereignis_ab.t_prog - ereignis_ab.t_plan

            for i_an, zid_an in enumerate(self.zid_ankuenfte_index):
                ereignis_an = self.ankunft_ereignisse[zid_an]
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
                        verspaetung -= min_umsteigezeit
                elif self.anschlusszeit >= plan_umsteigezeit >= min_umsteigezeit:
                    try:
                        freigabe = startzeit >= ereignis_an.get('t_mess', startzeit) + min_umsteigezeit
                    except AttributeError:
                        freigabe = False

                    abwarten = self.zentrale.anlage.ereignisgraph.has_successor(ereignis_an.node_id, ereignis_ab.node_id)

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
        self.zid_ankuenfte_index = [int(i) for i in np.asarray(self.zid_ankuenfte_index)[spalten]]
        self.zid_ankuenfte_set = set(self.zid_ankuenfte_index)
        self.anschlussplan = self.anschlussplan[:, spalten]
        self.anschlussstatus = self.anschlussstatus[:, spalten]
        self.verspaetung = self.verspaetung[:, spalten]

        aufgabe_auswahl = self._make_auswahl_matrix(self.anschluss_aufgabe)
        aufgabe_maske = np.isin(self.anschlussstatus, [ANSCHLUSS_WARNUNG, ANSCHLUSS_AUFGEBEN, ANSCHLUSS_OK])
        aufgabe_auswahl = np.logical_and(aufgabe_auswahl, aufgabe_maske)
        self.anschlussstatus = np.where(aufgabe_auswahl, ANSCHLUSS_AUFGEBEN, self.anschlussstatus)

        self.ankunft_labels = {zid: self.beschriftung.format_anschluss_label(self.zuege[zid], ankunft=self.ankunft_ereignisse[zid])
                               for zid in self.zid_ankuenfte_index}
        self.abfahrt_labels = {zid: self.beschriftung.format_anschluss_label(self.zuege[zid], abfahrt=self.abfahrt_ereignisse[zid])
                               for zid in self.zid_abfahrten_index}
        self.ankunft_insets = {zid: self.beschriftung.format_anschluss_inset(self.zuege[zid], ankunft=self.ankunft_ereignisse[zid])
                               for zid in self.zid_ankuenfte_index}
        self.abfahrt_insets = {zid: self.beschriftung.format_anschluss_inset(self.zuege[zid], abfahrt=self.abfahrt_ereignisse[zid])
                               for zid in self.zid_abfahrten_index}

        loeschen = set(self.zuege.keys()) - self.zid_ankuenfte_set - self.zid_abfahrten_set
        for zid in loeschen:
            del self.zuege[zid]
            try:
                del self.ankunft_ereignisse[zid]
            except KeyError:
                pass
            try:
                del self.abfahrt_ereignisse[zid]
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
        extent = (-0.5, a_an - 0.5, a_ab - 0.5, -0.5)
        im = ax.imshow(self.anzeigematrix, extent=extent, **kwargs)
        im.set_clim((0., 19.))
        ax.set_ylabel('Abfahrt')
        ax.set_xlabel('Ankunft')
        try:
            x_labels = [self.ankunft_labels[zid] for zid in self.zid_ankuenfte_index] + [''] * (a_an - n_an)
            y_labels = [self.abfahrt_labels[zid] for zid in self.zid_abfahrten_index] + [''] * (a_ab - n_ab)
        except KeyError as e:
            logger.warning(e)
            return

        ax.set_xticks(np.arange(a_an), labels=x_labels, rotation=45, rotation_mode='anchor',
                      horizontalalignment='left', verticalalignment='bottom')
        ax.set_yticks(np.arange(a_ab), labels=y_labels)
        ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

        for zid, label in zip(self.zid_ankuenfte_index, ax.get_xticklabels()):
            label.set_picker(True)
            label.zids = (-1, zid)
        for zid, label in zip(self.zid_abfahrten_index, ax.get_yticklabels()):
            label.set_picker(True)
            label.zids = (zid, -1)

        ax.set_xticks(np.arange(a_an + 1) - .5, minor=True)
        ax.set_yticks(np.arange(a_ab + 1) - .5, minor=True)
        ax.grid(which="minor", color=mpl.rcParams['axes.facecolor'], linestyle='-', linewidth=3)
        ax.tick_params(which="minor", bottom=False, left=False)

        for i in range(n_ab):
            for j in range(n_an):
                v = self.verspaetung[i, j]
                if self.anschlussstatus[i, j] in ANSCHLUESSE_VERSPAETET | {ANSCHLUSS_SELBST} and v > 0:
                    text = ax.text(j, i, round(v),
                                   ha="center", va="center", color="w", fontsize="small")

        for item in (ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontsize('small')

        self._plot_zugleisten(ax)

        ax.figure.tight_layout()
        ax.figure.canvas.draw()

    def _plot_zugleisten(self, ax):
        """
        Zugleisten entlang den Ankunfts- und Abfahrtsachsen zeichnen.

        :param ax: matplotlib-Axes
        :return: None
        """

        zugschema = self.zentrale.anlage.zugschema

        image_args = {'alpha': 0.5,
                      'cmap': zugschema.farbtabelle,
                      'vmin': 0.,
                      'vmax': 1.,
                      'picker': True}

        label_args = {'ha': 'center',
                      'va': 'center',
                      'fontsize': 'small',
                      'fontstretch': 'condensed',
                      'color': 'w',
                      'rotation_mode': 'anchor',
                      'transform_rotates_text': True}

        ankunft_matrix = np.atleast_2d(np.asarray([zugschema.zug_farbwert(self.zuege[zid])
                                                   for zid in self.zid_ankuenfte_index]))   # shape (1, n)
        abfahrt_matrix = np.atleast_2d(np.asarray([zugschema.zug_farbwert(self.zuege[zid])
                                                   for zid in self.zid_abfahrten_index])).T   # shape (n, 1)

        n_an, n_ab = ankunft_matrix.shape[1], abfahrt_matrix.shape[0]

        # main_extent = (-0.5, n_an - 0.5, n_ab - 0.5, -0.5)  # left, right, bottom, top
        ankunft_extent = (-0.5, n_an - 0.5, n_ab + 1.0, n_ab - 0.5)
        abfahrt_extent = (-2.0, -0.5, n_ab - 0.5, -0.5)
        # total_extent = (-2.0, n_an - 0.5, n_ab + 1.0, -1.0)

        ax.imshow(ankunft_matrix, extent=ankunft_extent, **image_args)
        ax.imshow(abfahrt_matrix, extent=abfahrt_extent, **image_args)
        ax.set_xlim(-2.0, n_an - 0.5)
        ax.set_ylim(-0.5, n_ab + 1.0)

        for j, zid in enumerate(self.zid_ankuenfte_index):
            ax.text(j, n_ab + 0.25, self.ankunft_insets[zid], **label_args)
        for j, zid in enumerate(self.zid_abfahrten_index):
            ax.text(-1.25, j, self.abfahrt_insets[zid], rotation=90, **label_args)

        ax.axhline(y=n_ab - 0.5, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])
        ax.axvline(x=-0.5, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

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
