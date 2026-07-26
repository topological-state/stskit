from collections.abc import Iterable, Sequence
import logging

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.plugin.stsobj import Knoten

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class SignalGraphNode(dict):
    enr = dict_property("enr", int, docstring="Elementnummer")
    name = dict_property("name", str, docstring="Elementname")
    typ = dict_property("typ", Knoten.Typ, docstring="Elementtyp")


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
        Signalgraph aus Knotenliste erstellen.

        Der Graph wird gelöscht und aus der Knotenliste neu aufgebaut.
        Die Knotenliste kommt von der Pluginschnittstelle.

        Args:
            wege: Iterable von `stsobj.Knoten` vom `PluginClient`.
        """
        self.clear()

        for knoten1 in wege:
            if knoten1.key:
                self.add_node(knoten1.key, typ=knoten1.typ, name=knoten1.name, enr=knoten1.enr)
                for knoten2 in knoten1.nachbarn.values():
                    self.add_edge(knoten1.key, knoten2.key, typ='verbindung', distanz=1)

        entfernen = set()
        for knoten1, data1 in self.nodes(data=True):
            if data1.typ == Knoten.Typ.UNDEFINIERT:
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
    Weichen durch Kanten ersetzen.

    Vereinfacht die Gleisanlage, indem Weichen durch direkte Kanten der Nachbarknoten ersetzt werden.

    Args:
        g: Ungerichteter Graph.

    Returns:
        Graph `g` mit ersetzten Weichen.
    """
    weichen = {n for n, _d in g.nodes.items()
               if _d.get('typ', None) in {Knoten.Typ.WEICHE_OBEN, Knoten.Typ.WEICHE_UNTEN}}
    for w in weichen:
        for v in g[w]:
            # w wird entfernt
            g = nx.contracted_nodes(g, v, w, self_loops=False, copy=False)
            break

    return g


def graph_anschluesse_pruefen(g: nx.Graph) -> nx.Graph:
    """
    Kanten von Anschlüssen prüfen und vereinfachen.

    Anschlüsse sollten wenn möglich mit Signalen verbunden sein.
    Direkte Verbindungen zu Bahnsteigen werden entfernt,
    außer es liegen keine Signale in der Nachbarschaft.

    Args:
        g: Ungerichteter Graph.

    Returns:
        Graph `g` mit geänderten Anschlüssen.
    """
    anschl = {n for n, _d in g.nodes.items()
              if _d.get('typ', None) in {Knoten.Typ.EINFAHRT, Knoten.Typ.AUSFAHRT}}
    for a in anschl:
        edges_to_remove = []
        signal_gefunden = False
        nbr = [n for n in g[a]]
        for n in nbr:
            if g.nodes[n]['typ'] == Knoten.Typ.SIGNAL:
                signal_gefunden = True
            else:
                edges_to_remove.append((a, n))
        if signal_gefunden:
            g.remove_edges_from(edges_to_remove)

    return g


def graph_bahnsteigsignale_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    Bahnsteig-Signal-Kombinationen durch Bahnsteige ersetzen.

    Vereinfacht die Gleisanlage, indem Signale in der Nachbarschaft von Bahnsteigen und Haltepunkten entfernt werden.
    Die von den betroffenen Signalen ausgehenden Kanten werden durch direkte Kanten der jeweiligen Partner ersetzt.

    Die Funktion hat zum Zweck, dass in der vereinfachten Gleisanlage Pfade nicht an den Bahnsteigen vorbeiführen.

    Args:
        g: Ungerichteter Graph.

    Returns:
        Graph `g` mit ersetzten Weichen.
    """
    bahnsteige = {n for n, _d in g.nodes.items() if _d.get('typ', None)
                  in {Knoten.Typ.BAHNSTEIG, Knoten.Typ.HALTEPUNKT}}
    for b in bahnsteige:
        nbr = [n for n in g[b]]
        for v in nbr:
            if g.nodes[v]['typ'] == Knoten.Typ.SIGNAL:
                g = nx.contracted_nodes(g, b, v, self_loops=False, copy=False)

    return g


def graph_signalpaare_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    Signalpaare kontrahieren.

    Signale, die mit einem anderen Signal verbunden sind, werden durch ein einzelnes ersetzt.

    Args:
        g: Ungerichteter Graph.

    Returns:
        Graph `g` mit ersetzten Signalpaaren.
    """
    while True:
        signale = {n for n, _d in g.nodes.items()
                   if _d.get('typ', None) == Knoten.Typ.SIGNAL}
        for s1 in signale:
            for s2 in g[s1]:
                if g.nodes[s2]['typ'] == Knoten.Typ.SIGNAL:
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
    Einzelne Signale zwischen Bahnsteigen durch Kanten ersetzen.

    Args:
        g: Ungerichteter Graph.

    Returns:
        Graph `g` mit entfernten Signalen.
    """
    signale = {n for n, _d in g.nodes.items()
               if _d.get('typ', None) == Knoten.Typ.SIGNAL}
    while signale:
        s1 = signale.pop()
        for s2 in g[s1]:
            if g.nodes[s2]['typ'] in {Knoten.Typ.BAHNSTEIG, Knoten.Typ.HALTEPUNKT}:
                g = nx.contracted_nodes(g, s2, s1, self_loops=False, copy=False)
                break

    return g


def graph_gleise_zuordnen(g: nx.Graph,
                          gleiszuordnung: dict[str, str],
                          ) -> nx.Graph:
    """
    Gleise in Graph zu Gruppen zusammenfassen.

    Args:
        g: Signalgraph, Gleisgraph oder ähnlicher Graph.
        gleiszuordnung: Mapping Gleisname zu Gruppenname.

    Returns:
        Graph g mit zugeordneten Gleisen.
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
            if g.nodes[n]['typ'] in {Knoten.Typ.EINFAHRT, Knoten.Typ.AUSFAHRT}:
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


def graph_mehrdeutige_strecken(g: nx.Graph,
                               max_knoten: int = 3,
                               ) -> list[set[str]]:
    """
    Findet mehrdeutige Streckenabschnitte.

    In mehrdeutigen Streckenabschnitten ist die Reihenfolge von Stationen aus dem Signalgraph unklar.
    Im Graphen erscheinen sie als Schleifen, meistens Dreiecke.

    Args:
        g: Signal-Graph, Gleis-Graph oder ähnlicher Graph.
        max_knoten: Filtert Abschnitte mit mehr als einer maximalen Knotenzahl heraus,
            wenn längere Schleifen nicht gemeldet werden sollen.

    Returns:
        Liste von mehrdeutigen Kanten.
    """
    cycles = nx.cycle_basis(g)
    cycles = [c for c in cycles if len(c) <= max_knoten]
    return cycles


def graph_mehrdeutige_strecke_abgleichen(g: nx.Graph,
                                         strecke: Sequence[str],
                                         routen: Sequence[Sequence[str]],
                                         ) -> nx.Graph:
    """
    Mehrdeutige Strecke mit Zugrouten abgleichen.

    Wenn die Reihenfolge der Stationen auf einer Strecke nicht eindeutig bestimmt werden kann,
    bleiben im Gleisgraphen Schleifen zurück.
    Diese Funktion versucht, die Reihenfolge anhand von bekannten Zugläufen zu bestimmen.
    Wenn ein Zug alle Stationen der Strecke anfährt, werden diese Kanten im Graphen belassen
    und alle unbedienten in der Nachbarschaft entfernt.

    Args:
        g: Gleisgraph oder ähnlich.
        strecke: Sequenz von Stationen, deren Reihenfolge abgeglichen werden soll.
        routen: Liste von Routen. Jede Route besteht aus einer Sequenz von Stationsnamen im Graphen g.

    Returns:
        Modifizierter Graph g.
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
