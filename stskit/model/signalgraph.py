import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.plugin.stsobj import Knoten

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

        entfernen = set()
        for knoten1, typ in self.nodes(data='typ', default='kein'):
            if typ == 'kein':
                logger.error(f"_signalgraph_erstellen: Knoten {knoten1} hat keinen Typ.")
                entfernen.add(knoten1)
        for knoten1 in entfernen:
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


# verschiedene funktionen zur signalgraphbearbeitung

def graph_weichen_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    weichen durch kanten ersetzen

    vereinfacht die gleisanlage, indem weichen durch direkte kanten der nachbarknoten ersetzt werden.

    :param g: ungerichteter graph
    :return: graph g mit ersetzten weichen
    """
    weichen = {n for n, _d in g.nodes.items()
               if _d.get('typ', None) in {Knoten.TYP_NUMMER['Weiche unten'], Knoten.TYP_NUMMER['Weiche oben']}}
    for w in weichen:
        for v in g[w]:
            # w wird entfernt
            g = nx.contracted_nodes(g, v, w, self_loops=False, copy=False)
            break

    return g


def graph_anschluesse_pruefen(g: nx.Graph) -> nx.Graph:
    """
    kanten von anschlüssen prüfen und vereinfachen

    anschlüsse sollten wenn möglich mit signalen verbunden sein.
    direkte verbindungen zu bahnsteigen werden entfernt,
    ausser es liegen keine signale in der nachbarschaft.

    :param g: ungerichteter graph
    :return: graph g mit geänderten anschlüssen
    """
    anschl = {n for n, _d in g.nodes.items()
              if _d.get('typ', None) in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}}
    for a in anschl:
        edges_to_remove = []
        signal_gefunden = False
        nbr = [n for n in g[a]]
        for n in nbr:
            if g.nodes[n]['typ'] == Knoten.TYP_NUMMER['Signal']:
                signal_gefunden = True
            else:
                edges_to_remove.append((a, n))
        if signal_gefunden:
            g.remove_edges_from(edges_to_remove)

    return g


def graph_bahnsteigsignale_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    bahnsteig-signal-kombinationen durch bahnsteige ersetzen

    vereinfacht die gleisanlage, indem signale in der nachbarschaft von bahnsteigen und haltepunkten entfernt werden.
    die von den betroffenen signalen ausgehenden kanten werden durch direkte kanten der jeweiligen partner ersetzt.

    die funktion hat zum zweck, dass in der vereinfachten gleisanlage pfade nicht an den bahnsteigen vorbeiführen.

    :param g: ungerichteter graph
    :return: graph g mit ersetzten weichen
    """
    bahnsteige = {n for n, _d in g.nodes.items() if _d.get('typ', None)
                  in {Knoten.TYP_NUMMER['Bahnsteig'], Knoten.TYP_NUMMER['Haltepunkt']}}
    for b in bahnsteige:
        nbr = [n for n in g[b]]
        for v in nbr:
            if g.nodes[v]['typ'] == Knoten.TYP_NUMMER['Signal']:
                g = nx.contracted_nodes(g, b, v, self_loops=False, copy=False)

    return g


def graph_signalpaare_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    signalpaare kontrahieren

    signale, die mit einem anderen signal verbunden sind, werden durch ein einzelnes ersetzt.

    :param g: ungerichteter graph
    :return: graph g mit ersetzten signalpaaren
    """
    while True:
        signale = {n for n, _d in g.nodes.items()
                   if _d.get('typ', None) == Knoten.TYP_NUMMER['Signal']}
        for s1 in signale:
            for s2 in g[s1]:
                if g.nodes[s2]['typ'] == Knoten.TYP_NUMMER['Signal']:
                    g = nx.contracted_nodes(g, s1, s2, self_loops=False, copy=False)
                    signale.remove(s2)
                    break
            else:
                continue
            break
        else:
            break

    return g


def graph_zwischensignale_entfernen(g: nx.Graph) -> nx.Graph:
    """
    einzelne signale zwischen bahnsteigen durch kanten ersetzen

    :param g: ungerichteter graph
    :return: graph g mit entfernten signalen
    """
    signale = {n for n, _d in g.nodes.items()
               if _d.get('typ', None) == Knoten.TYP_NUMMER['Signal']}
    while signale:
        s1 = signale.pop()
        for s2 in g[s1]:
            if g.nodes[s2]['typ'] in {Knoten.TYP_NUMMER['Bahnsteig'], Knoten.TYP_NUMMER['Haltepunkt']}:
                g = nx.contracted_nodes(g, s2, s1, self_loops=False, copy=False)
                break

    return g


def graph_gleise_zuordnen(g: nx.Graph, gleiszuordnung: Dict[str, str]) -> nx.Graph:
    """
    gleise in graph zu gruppen zusammenfassen

    :param g: signal-graph, gleis-graph oder ähnlicher graph.
    :param gleiszuordnung: mapping gleisname -> gruppenname
    :return: graph g mit zugeordneten gleisen
    """
    g = nx.relabel_nodes(g, gleiszuordnung, copy=False)
    g.remove_edges_from(nx.selfloop_edges(g))
    return g


def graph_schleifen_aufloesen(g: nx.Graph) -> nx.Graph:
    cycles = nx.cycle_basis(g)
    degrees = g.degree()
    edges_to_remove = []
    for c in cycles:
        ds = []
        dmin = len(c)
        nmin = None
        for n in c:
            if g.nodes[n]['typ'] in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                d = len(c)
            else:
                d = degrees[n]
            ds.append(d)
            if d < dmin:
                nmin = n
                dmin = d

        # nur dreiecke bearbeiten
        if len(ds) == 3 and dmin == 2:
            c.remove(nmin)
            edges_to_remove.append((c[0], c[1]))

    g.remove_edges_from(edges_to_remove)

    return g


def graph_mehrdeutige_strecken(g: nx.Graph, max_knoten: int = 3) -> List[Set[str]]:
    """
    findet mehrdeutige streckenabschnitte

    in mehrdeutigen streckenabschnitten ist die reihenfolge von stationen aus dem signalgraph unklar.
    im graphen erscheinen sie als schleifen, meistens dreiecke.

    :param g: signal-graph, gleis-graph oder ähnlicher graph.
    :param max_knoten: filtert abschnitte mit mehr als einer maximalen knotenzahl heraus,
        wenn längere schleifen nicht gemeldet werden sollen.
    :return: liste von mehrdeutigen kanten
    """
    cycles = nx.cycle_basis(g)
    cycles = [c for c in cycles if len(c) <= max_knoten]
    return cycles


def graph_mehrdeutige_strecke_abgleichen(g: nx.Graph, strecke: Iterable[str], routen: Iterable[Iterable[str]]):
    """
    mehrdeutige strecke mit zugrouten abgleichen

    wenn die reihenfolge der stationen auf einer strecke nicht eindeutig bestimmt werden kann,
    bleiben im gleis-graphen schleifen zurück.
    diese funktion versucht die reihenfolge anhand von bekannten zugläufen zu bestimmen.
    wenn ein zug alle stationen der strecke anfährt, werden diese kanten im graphen belassen
    und alle unbedienten in der nachbarschaft entfernt.

    :param g: gleis-graph oder ähnlich
    :param strecke: sequenz von stationen, deren reihenfolge abgeglichen werden soll
    :param routen: liste von routen. jede route besteht aus einer sequenz von stationsnamen im graphen g.
    :return: modifizierter graph g
    """
    nachbarschaft = set([])
    for k in strecke:
        nachbarschaft.update(g.adj[k])

    edges_to_remove = set([])
    for route in routen:
        match_index = [i for i, n in enumerate(route) if n in nachbarschaft]
        if len(match_index) >= len(nachbarschaft):
            pfad = route[min(match_index):max(match_index)+1]
            rg = nx.Graph(zip(pfad[:-1], pfad[1:]))
            for n in strecke:
                for e in g.edges(n):
                    if e not in rg.edges:
                        edges_to_remove.add(e)
            break

    g.remove_edges_from(edges_to_remove)
    return g
