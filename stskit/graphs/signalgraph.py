import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.interface.stsobj import Knoten

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class SignalGraphNode(dict):
    enr = dict_property("enr", int, docstring="Elementnummer")
    name = dict_property("name", str, docstring="Elementname")
    typ = dict_property("typ", int, docstring="Elementtyp, s. stsobj.Knoten.TYP_NUMMER")


class SignalGraphEdge(dict):
    typ = dict_property("typ", str, docstring="""
        'gleis' zwischen knoten mit namen, sonst 'verbindung' (z.b. weichen).
        """)
    distanz = dict_property("distanz", int, docstring="""
        Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten.
        Wird auf 1 gesetzt.
        """)


class SignalGraph(nx.DiGraph):
    """
    Signale, Weichen, Gleise und ihre Verbindungen.

    Der Signalgraph enthält das Gleisbild aus der Wegeliste der Plugin-Schnittstelle mit sämtlichen Knoten und Kanten.
    Das 'typ'-Attribut wird auf den sts-Knotentyp (int) gesetzt.
    Kanten werden entsprechend der Nachbarrelationen aus der Wegeliste ('typ'-attribut 'gleis') gesetzt.
    Der Graph ist gerichtet, da die Nachbarbeziehung i.a. nicht reziprok ist.
    Die Kante zeigt auf die Knoten, die als Nachbarn aufgeführt sind.
    Meist werden von der Schnittstelle jedoch Kanten in beide Richtungen angegeben,
    weshalb z.B. nicht herausgefunden werden kann, für welche Richtung ein Signal gilt.

    Die Signaldistanz wird am Anfang auf 1 gesetzt.
    """
    node_attr_dict_factory = SignalGraphNode
    edge_attr_dict_factory = SignalGraphEdge

    def to_undirected_class(self):
        return SignalGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def wege_importieren(self, wege: Iterable[Knoten]):
        """
        Signalgraph aus Knoten-Liste erstellen.

        Der Graph wird gelöscht und aus der Knotenliste neu aufgebaut.
        Die Knotenliste kommt von der Pluginschnittstelle.

        :param wege: Iterable von stsobj.Knoten vom PluginClient
        :return: None
        """

        self.clear()

        for knoten1 in wege:
            if knoten1.key:
                self.add_node(knoten1.key, typ=knoten1.typ, name=knoten1.name, enr=knoten1.enr)
                for knoten2 in knoten1.nachbarn:
                    self.add_edge(knoten1.key, knoten2.key, typ='verbindung', distanz=1)

        for knoten1, typ in self.nodes(data='typ', default='kein'):
            if typ == 'kein':
                print(f"_signalgraph_erstellen: Knoten {knoten1} hat keinen Typ.")
                self.remove_node(knoten1)

        self.remove_edges_from(nx.selfloop_edges(self))


class SignalGraphUngerichtet(nx.Graph):
    """
    Ungerichtete Variante von SignalGraph

    Der ursprüngliche SignalGraph ist gerichtet.
    Für Algorithmen die nur auf ungerichteten Graphen arbeiten,
    kann er in die ungerichtete Variante SignalGraphUngerichtet verwandelt werden.
    """
    node_attr_dict_factory = SignalGraphNode
    edge_attr_dict_factory = SignalGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return SignalGraph
