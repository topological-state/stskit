import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.interface.stsobj import BahnsteigInfo

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BahnsteigGraphNode(dict):
    """
    Klasse der Knotenattribute von BahnsteigGraph und BahnhofGraph
    """
    name = dict_property("name", str, docstring="Name")
    enr = dict_property("enr", int, docstring="Elementnummer bei Anschlussgleisen. Nur für Agl definiert.")
    typ = dict_property("typ", str, docstring="""
        'Gl': Gleis(sektor)bezeichnung, wie sie in den Fahrplänen vorkommt. Vom Sim deklariert. 
        'Bs': Bahnsteigbezeichnung, fasst Gleissektoren zusammen.
        'Bft': Bahnhofteil, fasst Bahnsteige zusammen, auf die ein Zug umdisponiert werden kann.
        'Bf': Bahnhof für grafische Darstellung und Fahrzeitauswertung.
        'Agl': Anschluss- oder Übergabegleis. Vom Sim deklariert.
        'Anst': Anschluss- oder Übergabestelle, fasst Anschlussgleise zusammen auf die ein Zug umdisponiert werden kann. 
        """)
    auto = dict_property("auto", bool, docstring="True bei automatischer, False bei manueller Konfiguration.")
    einfahrt = dict_property("einfahrt", bool, docstring="True, wenn das Gleis eine Einfahrt ist. Nur für Agl definiert.")
    ausfahrt = dict_property("ausfahrt", bool, docstring="True, wenn das Gleis eine Ausfahrt ist. Nur für Agl definiert.")
    sperrung = dict_property("sperrung", bool, docstring="Gleissperrung")


class BahnsteigGraphEdge(dict):
    """
    Klasse der Kantenattribute von BahnsteigGraph und BahnhofGraph
    """
    typ = dict_property("typ", str, docstring="""
        'Nachbar': Nachbarbeziehung gemäss Simulator.
        'Hierarchie': Von StsDispo definierte Hierarchiebeziehung.
        """)
    distanz = dict_property("distanz", int, docstring="""
        Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten.
        """)


class BahnsteigGraph(nx.Graph):
    """
    Bahnsteige

    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.
    Kanten werden entsprechend der Nachbarrelationen gesetzt.
    Der Graph ist ungerichtet, da die Nachbarbeziehung als reziprok aufgefasst wird.

    Vom Simulator werden nur die Gleisbezeichnungen der untersten Hierarchie sowie ihre Nachbarbeziehungen angegeben.
    Die Gruppierung in Bahnhofteile, Bahnhöfe und Anschlussstellen wird von der Klasse unterstützt,
    muss aber vom Besitzer gemacht werden.
    """
    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return BahnhofGraph

    def bahnsteige_importieren(self, bahnsteige: Iterable[BahnsteigInfo]):
        """
        Bahnsteiggraph aus Plugindaten erstellen.

        :param bahnsteige: Iterable von stsobj.BahnsteigInfo vom PluginClient
        :return: None
        """

        self.clear()

        for bs1 in bahnsteige:
            self.add_node(bs1.name, name=bs1.name, typ='Gl')
            for bs2 in bs1.nachbarn:
                self.add_edge(bs1.name, bs2.name, typ='Nachbar', distanz=0)


class BahnhofGraph(nx.DiGraph):
    """
    Bahnhöfe und ihre Gleishierarchie

    Der _Bahnhofgraph_ stellt die Gleishierarchie der Bahnhöfe dar
    und ordnet Bahnhöfe, Bahnhofteile, Bahnsteige und Gleise einander zu.

    Die Attribute der Knoten haben die Klasse BahnsteigGraphNode, die Kanten BahnsteigGraphEdge.

    Der Graph ist gerichtet, die Kanten zeigen von Bahnhöfen zu Gleisen.
    Die ungerichtete Variante ist der BahnsteigGraph.
    """

    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def to_directed_class(self):
        return self.__class__

    def to_undirected_class(self):
        return BahnsteigGraph

    @staticmethod
    def label(typ: str, name: str) -> Tuple[str, str]:
        """
        Das Label Besteht aus Typ und Name des BahnsteigGraphNode.
        """
        return typ, name

    def find_parent_name(self, child_typ: str, child_name: str, parent_typ: str) -> str:
        """
        Übergeordnetes Element finden
        """
        for node in nx.ancestors(self, (child_typ, child_name)):
            if node[0] == parent_typ:
                return node[1]
        else:
            raise KeyError(f"{child_typ} {child_name} ist keinem {parent_typ} zugeordnet")

    def find_root(self, label: Tuple[str, str]) -> Tuple[str, str]:
        """
        Stammelement suchen

        Das Stammelement hat die höchste Hierarchiestufe im Baum.
        :param label: Ausgangselement
        :return:
        """
        for node in self.predecessors(label):
            return self.find_root(node)
        else:
            return label

    def gleis_bahnsteig(self, gleis: str) -> str:
        """
        Zugeordneten Bahnsteig nachschlagen
        """
        return self.find_parent_name('Gl', gleis, 'Bs')

    def gleis_bahnhofteil(self, gleis: str) -> str:
        """
        Zugeordneten Bahnhofteil nachschlagen
        """
        return self.find_parent_name('Gl', gleis, 'Bft')

    def gleis_bahnhof(self, gleis: str) -> str:
        """
        Zugeordneten Bahnhof nachschlagen
        """
        return self.find_parent_name('Gl', gleis, 'Bf')

    def anschlussstelle(self, gleis: str) -> str:
        """
        Zugeordnete Anschlussstelle nachschlagen
        """
        return self.find_parent_name('Agl', gleis, 'Anst')

    def bahnhofgleise(self, bahnhof: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhof gehörenden Gleise auf.
        """
        for parent, child in nx.dfs_edges(self, ('Bf', bahnhof)):
            if child[0] == 'Gl':
                yield child[1]

    def bahnhofteilgleise(self, bahnhofteil: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhofteil gehörenden Gleise auf.
        """
        for parent, child in nx.dfs_edges(self, ('Bft', bahnhofteil)):
            if child[0] == 'Gl':
                yield child[1]

    def anschlussgleise(self, anst: str) -> Iterable[str]:
        """
        Listet die zu einer Anschlussstelle gehörenden Gleise auf.
        """
        for parent, child in nx.dfs_edges(self, ('Anst', anst)):
            if child[0] == 'Agl':
                yield child[1]

    def gruppengleise(self, gruppe: Tuple[str, str]) -> Iterable[str]:
        """
        Listet die zu einem Gruppenelement gehörenden Gleise auf.
        """
        for parent, child in nx.dfs_edges(self, gruppe):
            if child[0] in {'Agl', 'Gl'}:
                yield child[1]

    def bahnhoefe(self) -> Iterable[str]:
        """
        Listet alle Bahnhöfe auf.
        """
        for node in self.nodes:
            if node[0] == 'Bf':
                yield node[1]

    def anschlussstellen(self) -> Iterable[str]:
        """
        Listet alle Bahnhöfe auf.
        """
        for node in self.nodes:
            if node[0] == 'Anst':
                yield node[1]


