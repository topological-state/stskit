import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

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
