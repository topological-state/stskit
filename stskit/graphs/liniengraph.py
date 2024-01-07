import itertools
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.graphs.bahnhofgraph import BahnsteigGraphNode
from stskit.graphs.zielgraph import ZielGraphNode

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class LinienGraphNode(dict):
    typ = dict_property("typ", str,
                        docstring="Typ entsprechend BahnsteigGraphNode.typ, i.d.R. Bf oder Anst.")
    name = dict_property("name", str,
                         docstring="Benutzerfreundlicher Name des Knotens")
    fahrten = dict_property("fahrten", int,
                            docstring="Anzahl der ausgewerteten Fahrten über diesen Knoten")


class LinienGraphEdge(dict):
    fahrzeit_min = dict_property("fahrzeit_min", Union[int, float],
                                 docstring="Minimale Fahrzeit in Minuten")
    fahrzeit_max = dict_property("fahrzeit_max", Union[int, float],
                                 docstring="Maximale Fahrzeit in Minuten")
    fahrten = dict_property("fahrten", int,
                            docstring="Anzahl der ausgewerteten Fahrten")
    fahrzeit_summe = dict_property("fahrzeit_summe", Union[int, float],
                                   docstring="Summe aller ausgewerteten Fahrzeiten in Minuten")
    fahrzeit_schnitt = dict_property("fahrzeit_schnitt", float,
                                     docstring="Mittelwert aller ausgewerteten Fahrzeiten in Minuten")


class LinienGraph(nx.Graph):
    """
    Zugverbindungen zwischen Bahnhöfen.

    Dieser Graph zeigt bediente Verbindungen zwischen Bahnhöfen.
    Der Graph wird anhand der Zugfahrpläne erstellt.


    """
    node_attr_dict_factory = LinienGraphNode
    edge_attr_dict_factory = LinienGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)

        self._strecken_cache: Dict[Tuple[str, str], List[str]] = {}

    def to_undirected_class(self):
        return self.__class__

    @staticmethod
    def label(typ: str, name: str) -> Tuple[str, str]:
        """
        Das Label vom Liniengraph entspricht dem des BahnsteigGraph, i.d.R. auf Stufe Bf und Anst.
        """
        return typ, name

    def linie_eintragen(self,
                        ziel1: ZielGraphNode, bahnhof1: BahnsteigGraphNode,
                        ziel2: ZielGraphNode, bahnhof2: BahnsteigGraphNode):
        """
        Liniengraph erstellen

        Sollte nicht mehr als einmal pro Zug aufgerufen werden, da sonst die Statistik verfälscht werden kann.
        """

        MAX_FAHRZEIT = 24 * 60

        try:
            fahrzeit = ziel2.p_an - ziel1.p_ab
            # beschleunigungszeit von haltenden zuegen
            if ziel1.typ == 'D':
                fahrzeit += 1
        except AttributeError:
            fahrzeit = 2

        bft1 = (bahnhof1.typ, bahnhof1.name)
        bft2 = (bahnhof2.typ, bahnhof2.name)

        try:
            knoten1_daten = self.nodes[bft1]
        except KeyError:
            knoten1_daten = LinienGraphNode(typ=bahnhof1.typ, name=bahnhof1.name, fahrten=0)
        try:
            knoten2_daten = self.nodes[bft2]
        except KeyError:
            knoten2_daten = LinienGraphNode(typ=bahnhof2.typ, name=bahnhof2.name, fahrten=0)

        knoten1_daten.fahrten += 1
        knoten2_daten.fahrten += 1

        try:
            liniendaten = self[bft1][bft2]
        except KeyError:
            liniendaten = LinienGraphEdge(fahrzeit_min=MAX_FAHRZEIT, fahrzeit_max=0,
                                          fahrten=0, fahrzeit_summe=0., fahrzeit_schnitt=0.)

        liniendaten.fahrzeit_min = min(liniendaten.fahrzeit_min, fahrzeit)
        liniendaten.fahrzeit_max = max(liniendaten.fahrzeit_max, fahrzeit)
        liniendaten.fahrten += 1
        liniendaten.fahrzeit_summe += fahrzeit
        liniendaten.fahrzeit_schnitt = liniendaten.fahrzeit_summe / liniendaten.fahrten

        self.add_edge(bft1, bft2, **liniendaten)
        self.add_node(bft1, **knoten1_daten)
        self.add_node(bft2, **knoten2_daten)

    def schleifen_aufloesen(self):
        """
        Schleifen auflösen

        Weil Züge nicht alle Haltestellen bedienen,
        kann es im Liniengraph mehrere Verbindungen zwischen zwei Knoten geben,
        die im Graphen eine Schleife (cycle) bilden.
        Damit eine Strecke möglichst dem tatsächlichen Gleisverlauf folgt,
        löst diese Funktion solche Schleifen auf, indem sie die längste Kante jeder Schleife entfernt.
        Die Länge der Kante ist die minimale Fahrzeit zwischen den Knoten.

        Wenn die längste Kante nicht eindeutig bestimmt werden kann, wird die Schleife nicht aufgelöst.
        Dies kann z.B. der Fall sein, wenn die Fahrzeit zwischen allen Knoten gleich lang ist,
        weil der durchfahrende Zug die Zeit zum Anhalten und Beschleunigen einspart.
        Die Funktion versucht, solche Fälle aufzulösen,
        indem sie Verbindungen zwischen Knoten mit Grad > 2 künstlich verlängert.
        """

        entfernen = set()

        for schleife in nx.simple_cycles(self):
            kanten = zip(schleife, schleife[1:] + schleife[:1])
            laengste_fahrzeit = 0
            summe_fahrzeit = 0
            laengste_kante = None

            for kante in kanten:
                fahrzeit = max(1, self.edges[kante].get("fahrzeit_min", 0))
                fahrzeit += max(0, self.degree[kante[0]] - 2)
                fahrzeit += max(0, self.degree[kante[1]] - 2)
                if self.degree[kante[0]] > 2 and self.degree[kante[1]] > 2:
                    summe_fahrzeit += fahrzeit
                    if fahrzeit > laengste_fahrzeit:
                        laengste_fahrzeit = fahrzeit
                        laengste_kante = kante

            if laengste_kante is not None:
                if laengste_fahrzeit > summe_fahrzeit - laengste_fahrzeit - len(schleife):
                    entfernen.add(laengste_kante)
                else:
                    logger.debug(f"symmetrische schleife {schleife}")

        for u, v in entfernen:
            try:
                self.remove_edge(u, v)
            except nx.NetworkXError:
                pass

    def strecke(self, start: Tuple[str, str], ziel: Tuple[str, str]) -> List[Tuple[str, str]]:
        """
        Kürzeste Verbindung zwischen zwei Punkten bestimmen

        Start und Ziel sind die Labels zweier beliebiger Knoten im Liniengraph.
        Die berechnete Strecke ist eine geordnete Liste von Labels.

        Da die Streckenberechnung aufwändig sein kann, werden die Resultate im self._strecken_cache gespeichert.
        Der Cache muss gelöscht werden, wenn der Graph verändert wird.

        :param start: bahnhof- oder anschlussname
        :param ziel: bahnhof- oder anschlussname
        :return: liste von befahrenen gleisgruppen vom start zum ziel.
            die liste kann leer sein, wenn kein pfad gefunden wurde!
        """

        try:
            return self._strecken_cache[(start, ziel)]
        except KeyError:
            pass

        try:
            strecke = nx.shortest_path(self, start, ziel)
        except nx.NetworkXException:
            strecke = []

        self._strecken_cache[(start, ziel)] = strecke
        return strecke

    def strecken_vorschlagen(self, min_fahrten: int = 0, min_laenge: int = 2) -> List[List[Tuple[str, str]]]:
        """
        Strecken aus Liniengraph vorschlagen

        Diese Funktion bestimmt die kürzesten Strecken zwischen allen Kombinationen von Anschlüssen.
        Wenig frequentierte Anschlüsse können ausgeschlossen werden.

        Eine Strecke besteht aus einer Liste von Bahnhöfen inklusive Einfahrt am Anfang und Ausfahrt am Ende.
        Die Elemente sind Knotenlabels des Liniengraphen.

        :param: min_fahrten: Minimale Anzahl von Fahrten, die ein Anschluss aufweisen muss,
            um in die Auswahl aufgenommen zu werden.
            Per default (0), werden auch Strecken zwischen unbenutzten Anschlüssen erstellt.

        :param: min_laenge: Minimale Länge (Anzahl Wegpunkte) einer Strecke.
            Kürzere Strecken werden ignoriert.
            Die Defaultlänge 2 liefert auch direkte Strecken zwischen Einfahrt und Ausfahrt.

        :return: Liste von Listen von Liniengraphlabels
        """

        anschluesse = [x for x, d in self.nodes(data=True) if d.typ == 'Anst']
        strecken = []

        for ein, aus in itertools.permutations(anschluesse, 2):
            try:
                fahrten = min(self.nodes[ein]['fahrten'], self.nodes[aus]['fahrten'])
            except KeyError:
                fahrten = -1

            if ein != aus and fahrten >= min_fahrten:
                strecke = self.strecke(ein, aus)
                if len(strecke) >= min_laenge:
                    strecken.append(strecke)

        return strecken

    def strecken_zeitachse(self, strecke: List[Tuple[str, str]], parameter: str = 'fahrzeit_min') -> List[Union[int, float]]:
        """
        Distanzen entlang einer Strecke berechnen

        Kumulierte Distanzen der Haltepunkte ab dem ersten Punkt der strecke berechnen.
        Die Distanz wird als minimale Fahrzeit in Minuten angegeben.

        :param strecke: Liste von Linienpunkten
        :param parameter: Zu verwendender Zeitparameter, fahrzeit_min, fahrzeit_schnitt, fahrzeit_max.
        :return: distanz = Fahrzeit in Minuten.
            Die Liste enthält die gleiche Anzahl Elemente wie die Strecke.
            Das erste Element ist 0.
        """
        kanten = zip(strecke[:-1], strecke[1:])
        distanz = 0
        result = [distanz]
        for u, v in kanten:
            try:
                zeit = self[u][v][parameter]
                distanz += max(1, zeit)
            except KeyError:
                logger.warning(f"Verbindung {u}-{v} nicht im Liniengraph.")
                distanz += 1

            result.append(float(distanz))

        return result
