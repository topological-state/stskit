import collections
import itertools
import os
import re
from collections.abc import Set
import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx
import numpy as np
import trio

from stsobj import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, time_to_seconds
from stsplugin import PluginClient, TaskDone


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class JSONEncoder(json.JSONEncoder):
    """
    translate non-standard objects to JSON objects.

    currently implemented: Set.

    ~~~~~~{.py}
    encoded = json.dumps(data, cls=JSONEncoder)
    decoded = json.loads(encoded, object_hook=json_object_hook)
    ~~~~~~
    """

    def default(self, obj):
        if isinstance(obj, Set):
            return dict(__class__='Set', data=list(obj))
        if isinstance(obj, frozenset):
            return dict(__class__='frozenset', data=list(obj))
        if isinstance(obj, nx.Graph):
            return "networkx.Graph"
        else:
            return super().default(obj)


def json_object_hook(d):
    if '__class__' in d and d['__class__'] == 'Set':
        return set(d['data'])
    else:
        return d


def common_prefix(lst: Iterable) -> Generator[str, None, None]:
    for s in zip(*lst):
        if len(set(s)) == 1:
            yield s[0]
        else:
            return


def gemeinsamer_name(g: Iterable) -> str:
    return ''.join(common_prefix(g)).strip()


ALPHA_PREFIX_PATTERN = re.compile(r'[^\d\W]*')
NON_DIGIT_PREFIX_PATTERN = re.compile(r'\D*')
EINZEL_ANSCHLUESSE = ['Anschluss', 'Feld', 'Gruppe', 'Gleis', 'Gr.', 'Anschl.', 'Gl.', 'Industrie', 'Depot', 'Abstellung']


def alpha_prefix(name: str) -> str:
    """
    alphabetischen anfang eines namens extrahieren.

    anfang des namens bis zum ersten nicht-alphabetischen zeichen (ziffer, leerzeichen, sonderzeichen).
    umlaute etc. werden als alphabetisch betrachtet.
    leerer string, wenn keine alphabetischen zeichen gefunden wurden.

    :param name: z.b. gleisname
    :return: resultat

    """
    return re.match(ALPHA_PREFIX_PATTERN, name).group(0)


def default_bahnhofname(gleis: str) -> str:
    """
    bahnhofnamen aus gleisnamen ableiten.

    es wird angenommen, dass der bahnhofname aus den alphabetischen zeichen am anfang des gleisnamens besteht.
    wenn der gleisname keine alphabetischen zeichen enthält, wird per default "HBf" zurückgegeben.

    :param gleis: gleis- bzw. bahnsteigname
    :return: bahnhofname
    """

    name = alpha_prefix(gleis)
    if name:
        return name
    else:
        return "HBf"


def ist_einzel_anschluss(gleis: str) -> bool:
    """
    prüft anhand von schlüsselwörtern, ob das gleis ein einfacher anschluss ist.

    zeigt True, wenn eine zeichenfolge aus EINZEL_ANSCHLUESSE im gleisnamen vorkommt.

    :param gleis: name des anschlussgleises
    :return:
    """
    for ea in EINZEL_ANSCHLUESSE:
        if gleis.find(ea) >= 0:
            return True

    return False


def default_anschlussname(gleis: str) -> str:
    """
    anschlussname aus gleisnamen ableiten.

    es wird angenommen, dass der bahnhofname aus den alphabetischen zeichen am anfang des gleisnamens besteht.
    wenn der gleisname keine alphabetischen zeichen enthält, wird ein leerer string zurückgegeben.

    wenn eine zeichenfolge aus EINZEL_ANSCHLUESSE im gleisnamen vorkommt, wird der gleisname unverändert zurückgegeben.

    :param gleis: gleisname
    :return: anschlussname
    """

    if ist_einzel_anschluss(gleis):
        return gleis
    else:
        return re.match(ALPHA_PREFIX_PATTERN, gleis).group(0).strip()


def dict_union(*gr: Dict[str, Set[Any]]) -> Dict[str, Set[Any]]:
    """
    merge dictionaries of sets.

    the given dictionaries are merged.
    if two dictionaries contain the same key, the union of their values is stored.

    :param gr: any number of dictionaries containing sets as values
    :return: merged dictionary
    """
    d = dict()
    for g in gr:
        for k, v in g.items():
            if k in d:
                d[k] = d[k].union(v)
            else:
                d[k] = v
    return d


def find_set_item_in_dict(item: Any, mapping: Mapping[Any, Set[Any]]) -> Any:
    """
    look up a set member in a key->set mapping.

    :param item: item to find in one of the sets in the dictonary.
    :param mapping: mapping->set
    :return: key
    :raise ValueError if not found
    """
    for k, s in mapping.items():
        if item in s:
            return k
    else:
        raise ValueError(f"item {item} not found in dictionary.")


anschluss_name_funktionen = {}
    # "Bern - Lötschberg": alpha_prefix,
    # "Ostschweiz": alpha_prefix,
    # "Tessin": alpha_prefix,
    # "Westschweiz": alpha_prefix,
    # "Zentralschweiz": alpha_prefix,
    # "Zürich und Umgebung": alpha_prefix}

bahnhof_name_funktionen = {}


def graph_weichen_ersetzen(g: nx.Graph) -> nx.Graph:
    """
    weichen durch kanten ersetzen

    vereinfacht die gleisanlage, indem weichen durch direkte kanten der nachbarknoten ersetzt werden.

    :param g: ungerichteter graph
    :return: graph g mit ersetzten weichen
    """
    weichen = {n for n, _d in g.nodes.items() if _d['typ'] in {3, 4}}
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
    anschl = {n for n, _d in g.nodes.items() if _d['typ'] in {6, 7}}
    for a in anschl:
        edges_to_remove = []
        signal_gefunden = False
        nbr = [n for n in g[a]]
        for n in nbr:
            if g.nodes[n]['typ'] == 2:
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
    bahnsteige = {n for n, _d in g.nodes.items() if _d['typ'] in {5, 12}}
    for b in bahnsteige:
        nbr = [n for n in g[b]]
        for v in nbr:
            if g.nodes[v]['typ'] == 2:
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
        signale = {n for n, _d in g.nodes.items() if _d['typ'] == 2}
        for s1 in signale:
            for s2 in g[s1]:
                if g.nodes[s2]['typ'] == 2:
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
    signale = {n for n, _d in g.nodes.items() if _d['typ'] == 2}
    while signale:
        s1 = signale.pop()
        for s2 in g[s1]:
            if g.nodes[s2]['typ'] in {5, 12}:
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
            if g.nodes[n]['typ'] in {6, 7}:
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


class Anlage:
    """
    netzwerk-darstellungen der bahnanlage

    diese klasse verwaltet folgende graphen als darstellung der bahnanlage:

    :var self.signal_graph original "wege"-graph vom simulator
        mit bahnsteigen, haltepunkten, signalen, einfahrten und ausfahrten.
        dieser graph dient als basis und wird nicht speziell bearbeitet.
        der graph ist ungerichtet, weil die richtung vom simulator nicht konsistent angegeben wird:
        entgegengesetzte signale sind verbunden, einfahrten sind mit ausfahrsignalen verbunden.

    :var self.bahnsteig_graph graph mit den bahnsteigen von der "bahnsteigliste".
        vom simulator als nachbarn bezeichnete bahnsteige sind durch kanten verbunden.
        der bahnsteig-graph zerfällt dadurch in bahnhof-teile.
        es ist für den gebrauch in den charts in einigen fällen wünschbar,
        dass bahnhof-teile zu einem ganzen bahnhof zusammengefasst werden,
        z.b. bahnsteige und abstellgleise.
        die zuordnung kann jedoch nicht aus dem graphen selber abgelesen werden
        und muss separat (user, konfiguration, empirische auswertung) gemacht werden.

        vorsicht: bahnsteige aus der bahnsteigliste sind teilweise im wege-graph nicht enthalten!

    :var self.bahnhof_graph netz-graph mit bahnsteiggruppen, einfahrtgruppen und ausfahrtgruppen.
        vom bahnsteig-graph abgeleiteter graph, der die ganzen zugeordneten gruppen enthält.


    :var self.anschlussgruppen gruppierung von einfahrten und ausfahrten

        mehrere ein- und ausfahrten können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen auf sets von knotennamen ab.

    :var self.bahnsteiggruppen gruppierung von bahnsteigen

        mehrere bahnsteige (typischerweise alle zu einem bahnhof gehörigen)
        können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen (bahnhofnamen) auf sets von bahnsteignamen ab.
    """

    BAHNHOF_GRAPH_INIT_EDGE = {
        "fahrzeit_sum": 0,
        "fahrzeit_min": np.nan,
        "fahrzeit_max": np.nan,
        "fahrzeit_count": 0
    }

    BAHNHOF_GRAPH_INIT_NODE = {
        "zug_count": 0
    }

    def __init__(self, anlage: AnlagenInfo):
        self.anlage = anlage
        self.config_loaded = False
        self.auto = True

        self.f_anschlussname = default_anschlussname
        self.f_bahnhofname = default_bahnhofname

        # gruppenname -> {gleisnamen}
        self.anschlussgruppen: Dict[str, Set[str]] = {}
        self.bahnsteiggruppen: Dict[str, Set[str]] = {}
        self.gleisgruppen: Dict[str, Set[str]] = {}

        # gleisname -> gruppenname
        self.anschlusszuordnung: Dict[str, str] = {}
        self.bahnsteigzuordnung: Dict[str, str] = {}
        self.gleiszuordnung: Dict[str, str] = {}

        # lage des anschlusses auf dem gleisbild
        # gruppenname -> "links", "mitte", "rechts", "oben", "unten"
        self.anschlusslage: Dict[str, str] = {}

        self.signal_graph: nx.Graph = nx.DiGraph()
        self.gleis_graph: nx.Graph = nx.Graph()
        self.bahnsteig_graph: nx.Graph = nx.DiGraph()
        self.bahnhof_graph: nx.Graph = nx.Graph()
        self.gleis_graph_probleme: List[Any] = []

        # strecken-name -> gruppen-namen
        self.strecken: Dict[str, Tuple[str]] = {}

        self._verbindungsstrecke_cache: Dict[Tuple[str, str], List[str]] = {}

    def update(self, client: PluginClient, config_path: os.PathLike):
        if not self.anlage:
            self.anlage = client.anlageninfo

            try:
                self.f_anschlussname = anschluss_name_funktionen[self.anlage.region]
            except KeyError:
                pass
            try:
                self.f_bahnhofname = bahnhof_name_funktionen[self.anlage.region]
            except KeyError:
                pass

        if len(self.signal_graph) == 0:
            self.original_graphen_erstellen(client)
            self.gleise_gruppieren()

        if not self.config_loaded:
            try:
                self.load_config(config_path)
            except OSError:
                logger.exception("fehler beim laden der anlagenkonfiguration")
            except ValueError as e:
                logger.exception("fehlerhafte anlagenkonfiguration")
            self.config_loaded = True

        if len(self.gleis_graph) == 0 or len(self.bahnhof_graph) == 0 or len(self.gleis_graph_probleme) > 0:
            self.gleis_graph_erstellen(client.zugliste.values())
            self.gleis_graph_probleme = graph_mehrdeutige_strecken(self.gleis_graph)
            self.bahnhof_graph_erstellen()

        if len(self.strecken) == 0:
            self.strecken_aus_bahnhofgraph()

        self.bahnhof_graph_zugupdate(client.zugliste.values())

    def original_graphen_erstellen(self, client: PluginClient):
        """
        erstellt die signal- und bahnsteig-graphen nach anlageninformationen vom simulator.

        der signal-graph enthält das gleisbild aus der wege-liste der plugin-schnittstelle mit sämtlichen knoten und kanten.
        das 'typ'-attribut wird auf den sts-knotentyp (int) gesetzt.
        kanten werden entsprechend der nachbarn-relationen aus der wegeliste ('typ'-attribut 'gleis') gesetzt.
        der graph ist gerichtet, da die nachbarbeziehung nicht reziprok ist.
        die kante zeigt auf die knoten, die als nachbarn aufgeführt sind.
        meist werden von der schnittstelle jedoch kanten in beide richtung angegeben,
        weshalb z.b. nicht herausgefunden werden kann, für welche richtung ein signal gilt.
        der graph wird in self.signal_graph abgelegt.
        dieser graph sollte nicht verändert werden.

        der bahnsteig-graph enthält alle bahnsteige aus der bahnsteigliste der plugin-schnittstelle als knoten.
        kanten werden entsprechend der nachbar-relationen gesetzt.
        der graph ist gerichtet, da die nachbarbeziehung nicht reziprok ist.
        die kante zeigt auf die knoten, die als nachbarn aufgeführt sind.

        signal-attribute
        ----------------
        knoten 'typ': (int) stsobj.Knoten.TYP_NUMMER
        kanten 'typ': (str) 'gleis'
        kanten 'distanz': (int) länge (anzahl knoten) des kürzesten pfades zwischen den knoten. wird auf 1 gesetzt.

        bahnsteig-attribute
        -------------------
        kanten 'typ': (str) 'bahnhof', wenn die bahnsteignamen mit der gleichen buchstabenfolge
                      (oder direkt mit der gleisnummer) beginnen und damit zum gleichen bahnhof gehören,
                      sonst 'nachbar'.
        kanten 'distanz': (int) länge (anzahl knoten) des kürzesten pfades zwischen den knoten. wird auf 0 gesetzt.

        :param client: PluginClient-artiges objekt mit aktuellen bahnsteigliste und wege attributen.
        :return: None.
        """

        self.signal_graph.clear()
        self.gleis_graph.clear()
        self._verbindungsstrecke_cache = {}

        for knoten1 in client.wege.values():
            if knoten1.name:
                self.signal_graph.add_node(knoten1.name, typ=knoten1.typ)
                for knoten2 in knoten1.nachbarn:
                    if knoten2.name:
                        self.signal_graph.add_edge(knoten1.name, knoten2.name, typ='gleis', distanz=1)

        for bs1 in client.bahnsteigliste.values():
            self.bahnsteig_graph.add_node(bs1.name)
            pre1 = alpha_prefix(bs1.name)
            for bs2 in bs1.nachbarn:
                pre2 = alpha_prefix(bs2.name)
                if pre1 == pre2:
                    self.bahnsteig_graph.add_edge(bs1.name, bs2.name, typ='bahnhof', distanz=0)
                else:
                    self.bahnsteig_graph.add_edge(bs1.name, bs2.name, typ='nachbar', distanz=0)

    def gleis_graph_erstellen(self, zugliste: Iterable[ZugDetails]):
        """
        gleis-graph erstellen

        der gleisgraph dient als grundlage zur streckenberechnung zwischen start- und zielpunkten.

        für die erstellung des gleis-graphen sind der signal-graph, die gleiszuordnung sowie eine zugliste nötig.

        :return: None. der graph wird im gleis_graph-attribut gespeichert.
        """
        self._verbindungsstrecke_cache = {}
        g = self.signal_graph.to_undirected()
        g = graph_weichen_ersetzen(g)
        g = graph_anschluesse_pruefen(g)
        g = graph_bahnsteigsignale_ersetzen(g)
        g = graph_signalpaare_ersetzen(g)
        g = graph_gleise_zuordnen(g, self.gleiszuordnung)
        g = graph_schleifen_aufloesen(g)
        g = graph_zwischensignale_entfernen(g)
        g = graph_schleifen_aufloesen(g)
        mehrdeutige_strecken = graph_mehrdeutige_strecken(g)
        if mehrdeutige_strecken:
            routen = set([])
            for zug in zugliste:
                try:
                    routen.add(tuple([self.gleiszuordnung[n] for n in zug.route()]))
                except KeyError:
                    continue
            for kante in mehrdeutige_strecken:
                g = graph_mehrdeutige_strecke_abgleichen(g, kante, routen)

        self.gleis_graph = g

    def gleise_gruppieren(self):
        """
        gruppiert bahnsteige zu bahnhöfen und ein-/ausfahrten zu anschlüssen.

        bahnsteige werden nach nachbarn gemäss anlageninfo gruppiert.
        der gruppenname wird aus gemäss der regionsabhängigen f_bahnhofname-funktion gebildet
        (per default die alphabetischen zeichen bis zum ersten nicht-alphabetischen zeichen).
        falls dieses verfahren jedoch zu mehrdeutigen bezeichnungen führen würde,
        wird der alphabetisch erste gleisnamen übernommen.

        einfahrten und ausfahrten werden nach dem namen gruppiert,
        der durch die regionsabhängige f_anschlussname gebildet wird.
        falls ein anschlussname mit einem bahnhofsnamen kollidiert, wird ein pluszeichen nachgestellt.

        da es keine allgemeine konvention für gleis- und anschlussnamen gibt,
        kann der algorithmus abhängig vom stellwerk zu viele oder zu wenige gleise zusammenfassen.
        in diesen fällen muss die zuordnung in der konfigurationsdatei manuell korrigiert werden.

        :return: None
        """
        anschlusstypen = {Knoten.TYP_NUMMER["Einfahrt"], Knoten.TYP_NUMMER["Ausfahrt"]}
        bahnsteigtypen = {Knoten.TYP_NUMMER["Bahnsteig"], Knoten.TYP_NUMMER["Haltepunkt"]}

        def filter_node(n1):
            try:
                return self.signal_graph.nodes[n1]["typ"] in bahnsteigtypen
            except KeyError:
                return False

        def filter_edge(n1, n2):
            try:
                return self.bahnsteig_graph[n1][n2]["typ"] == "bahnhof"
            except KeyError:
                return False

        # durch nachbarbeziehung verbundene bahnsteige bilden einen bahnhof
        subgraph = nx.subgraph_view(self.bahnsteig_graph, filter_node=filter_node, filter_edge=filter_edge)
        subgraph = subgraph.to_undirected()
        gruppen = {sorted(g)[0]: g for g in nx.connected_components(subgraph)}
        # gleisbezeichnung abtrennen
        nice_names = {k: self.f_bahnhofname(k) for k in gruppen}
        # mehrdeutige bahnhofsnamen identifizieren und durch gleichbezeichnung ersetzen
        counts_nice = collections.Counter(nice_names.values())
        counts_safe = {sn: counts_nice[nice_names[sn]] for sn in gruppen.keys()}
        self.bahnsteiggruppen = {nice_names[sn] if counts_safe[sn] == 1 else sn: g for sn, g in gruppen.items()}

        # ein- und ausfahrten, die auf den gleichen anschlussnamen abbilden, bilden einen anschluss
        nodes = [n for n, t in self.signal_graph.nodes(data='typ') if t in anschlusstypen]
        nice_names = {k: self.f_anschlussname(k) for k in nodes}
        # anschlüsse, die den gleichen namen wie ein bahnhof haben, umbenennen
        nice_names = {k: v if v not in self.bahnsteiggruppen else v + "+" for k, v in nice_names.items()}
        unique_names = set(nice_names.values())
        self.anschlussgruppen = {k: set([n for n in nodes if self.f_anschlussname(n) == k]) for k in unique_names}

        self.auto = True
        self._update_gruppen_dict()

    def _update_gruppen_dict(self):
        """
        gruppen-dictionaries aktualisieren.

        die ursprungsdaten stehen in den bahnsteiggruppen- und anschlussgruppen-dictionaries.
        von ihnen werden die zuordnungen, gleisgruppen und gleiszuordnung abgeleitet.

        :return: None
        """

        self.anschlusszuordnung = {}
        for name, gruppe in self.anschlussgruppen.items():
            for gleis in gruppe:
                self.anschlusszuordnung[gleis] = name

        self.bahnsteigzuordnung = {}
        for name, gruppe in self.bahnsteiggruppen.items():
            for gleis in gruppe:
                self.bahnsteigzuordnung[gleis] = name

        self.gleisgruppen = dict_union(self.bahnsteiggruppen, self.anschlussgruppen)
        self.gleiszuordnung = {**self.bahnsteigzuordnung, **self.anschlusszuordnung}

        self._verbindungsstrecke_cache = {}

    def bahnhof_graph_erstellen(self):
        """
        bahnhofgraph aus signalgraph und gruppenkonfiguration neu erstellen.

        der bahnhofgraph wird aus den kürzesten verbindungsstrecken aller möglichen kombinationen von ein- und
        ausfahrten gebildet. er enthält die von ihnen berührten bahnhöfe und anschlüsse als knoten.

        die self.anschlussgruppen und self.bahnsteiggruppen müssen bereits konfiguriert sein.

        :return: kein
        """
        self.bahnhof_graph = self.gleis_graph.copy()
        for n in self.bahnhof_graph.nodes:
            self.bahnhof_graph.nodes[n].update(Anlage.BAHNHOF_GRAPH_INIT_NODE)
            self.bahnhof_graph.nodes[n]['typ'] = "bahnhof" if n in self.bahnsteiggruppen else "anschluss"
        for e in self.bahnhof_graph.edges:
            self.bahnhof_graph.edges[e].update(Anlage.BAHNHOF_GRAPH_INIT_EDGE)

    def bahnhof_graph_zugupdate(self, zugliste: Iterable[ZugDetails]):
        """
        bahnhof-graph aus fahrplan aktualisieren.

        der bahnhofgraph wird von der bahnhof_graph_erstellen-methode erstellt.
        diese methode aktualisiert die fahrzeiten-attribute der kanten anhand des fahrplans.
        fahrzeit_sum, fahrzeit_min, fahrzeit_max und fahrzeit_count werden aktualisiert.
        die fahrzeiten sind in sekunden.
        fahrzeit_count ist die anzahl betrachteter zugverbindungen.

        :return: kein
        """

        for zug in zugliste:
            start = None
            startzeit = 0
            for zeile in zug.fahrplan:
                try:
                    ziel = self.gleiszuordnung[zeile.plan]
                    zielzeit = time_to_seconds(zeile.an)
                except (AttributeError, KeyError):
                    break
                else:
                    try:
                        d = self.bahnhof_graph.nodes[ziel]
                        d['zug_count'] = d['zug_count'] + 1
                    except KeyError:
                        logger.error(f"KeyError {ziel} (zug {zug.name}) nicht im bahnhofgraph")
                        break

                if start and start != ziel:
                    zeit = zielzeit - startzeit
                    self.fahrzeit_update(start, ziel, zeit)

                start = ziel
                try:
                    startzeit = time_to_seconds(zeile.ab)
                except AttributeError:
                    break

    def fahrzeit_update(self, start, ziel, zeit, recursive=True):
        try:
            d = self.bahnhof_graph[start][ziel]
        except KeyError:
            if recursive:
                strecke = self.verbindungsstrecke(start, ziel)
                for s, z in zip(strecke[:-1], strecke[1:]):
                    self.fahrzeit_update(s, z, round(zeit / (len(strecke) - 1)), recursive=False)
        else:
            d['fahrzeit_sum'] = d['fahrzeit_sum'] + zeit
            d['fahrzeit_min'] = min(d['fahrzeit_min'], zeit) if not np.isnan(d['fahrzeit_min']) else zeit
            d['fahrzeit_max'] = max(d['fahrzeit_max'], zeit) if not np.isnan(d['fahrzeit_max']) else zeit
            d['fahrzeit_count'] = d['fahrzeit_count'] + 1

    def strecken_aus_bahnhofgraph(self):
        """
        strecken aus bahnhofgraph ableiten

        diese funktion bestimmt die kürzesten strecken zwischen allen anschlusskombinationen.
        die strecken werden in self.strecken abgelegt.

        eine strecke besteht aus einer liste von bahnhöfen inklusive einfahrt am anfang und ausfahrt am ende.
        die namen der elemente sind gruppennamen, d.h. die schlüssel aus self.gleisgruppen.
        der streckenname (schlüssel von self.strecken) wird aus dem ersten und letzten wegpunkt gebildet,
        die mit einem bindestrich aneinandergefügt werden.

        :return: das result wird in self.strecken abgelegt.
        """
        anschlussgleise = list(self.anschlussgruppen.keys())
        strecken = []
        for ein, aus in itertools.combinations(anschlussgleise, 2):
            strecke = self.verbindungsstrecke(ein, aus)
            if len(strecke) >= 1:
                strecken.append(strecke)

        self.strecken = {f"{s[0]}-{s[-1]}": s for s in strecken}

    def verbindungsstrecke(self, start_gleis: str, ziel_gleis: str) -> List[str]:
        """
        kürzeste verbindung zwischen zwei gleisen bestimmen

        die kürzeste verbindung wird aus dem bahnhofgraphen bestimmt.
        start und ziel müssen knoten im bahnhofgraphen sein, also gruppennamen (bahnhöfe oder anschlüsse).
        die berechnete strecke ist eine geordnete liste von gruppennamen.

        da die streckenberechnung aufwändig sein kann, werden die resultate im self._verbindungsstrecke_cache
        gespeichert. der cache muss gelöscht werden, wenn sich der bahnhofgraph oder die bahnsteigzuordnung ändert.

        :param start_gleis: bahnhof- oder anschlussname
        :param ziel_gleis: bahnhof- oder anschlussname
        :return: liste von befahrenen gleisgruppen vom start zum ziel.
            die liste kann leer sein, wenn kein pfad gefunden wurde!
        """

        try:
            return self._verbindungsstrecke_cache[(start_gleis, ziel_gleis)]
        except KeyError:
            pass

        try:
            strecke = nx.shortest_path(self.bahnhof_graph, start_gleis, ziel_gleis)
        except nx.NetworkXException:
            return []

        self._verbindungsstrecke_cache[(start_gleis, ziel_gleis)] = strecke
        return strecke

    def get_strecken_distanzen(self, strecke: List[str]) -> List[float]:
        """
        distanzen (minimale fahrzeit) entlang einer strecke berechnen

        distanzen der bahnhöfe zum ersten punkt der strecke berechnen.
        die distanz wird als minimale fahrzeit in sekunden angegeben.

        :param strecke: liste von gleisgruppen-namen
        :return: distanz = minimale fahrzeit in sekunden.
            die liste enthält die gleiche anzahl elemente wie die strecke.
            das erste element ist 0.
        """
        kanten = zip(strecke[:-1], strecke[1:])
        distanz = 0.
        result = [distanz]
        for u, v in kanten:
            try:
                zeit = self.bahnhof_graph[u][v]['fahrzeit_min']
                if not np.isnan(zeit):
                    distanz += zeit
                else:
                    distanz += 60.
            except KeyError:
                logger.warning(f"verbindung {u}-{v} nicht im netzplan.")
                distanz += 60.

            result.append(float(distanz))

        return result

    def load_config(self, path: os.PathLike, load_graphs=False, ignore_version=False):
        """

        :param path: verzeichnis mit den konfigurationsdaten.
            der dateiname wird aus der anlagen-id gebildet.
        :param load_graphs: die graphen werden normalerweise vom simulator abgefragt und erstellt.
            für offline-auswertung können sie auch aus dem konfigurationsfile geladen werden.
        :return: None
        :raise: OSError, JSONDecodeError(ValueError)
        """
        if load_graphs:
            p = Path(path) / f"{self.anlage.aid}diag.json"
        else:
            p = Path(path) / f"{self.anlage.aid}.json"

        with open(p) as fp:
            d = json.load(fp, object_hook=json_object_hook)

        if not ignore_version:
            assert d['_aid'] == self.anlage.aid
            if self.anlage.build != d['_build']:
                logger.warning(f"unterschiedliche build-nummern (file: {d['_build']}, sim: {self.anlage.build})")

            if '_version' not in d:
                d['_version'] = 1
                logger.warning(f"konfigurationsdatei ohne versionsangabe. nehme 1 an.")
            if d['_version'] < 2:
                logger.error(f"inkompatible konfigurationsdatei - auto-konfiguration")
                return

        try:
            self.bahnsteiggruppen = d['bahnsteiggruppen']
            self.auto = False
        except KeyError:
            logger.info("fehlende bahnsteiggruppen-konfiguration - auto-konfiguration")
        try:
            self.anschlussgruppen = d['anschlussgruppen']
        except KeyError:
            logger.info("fehlende anschlussgruppen-konfiguration - auto-konfiguration")
        try:
            self.anschlusslage = d['anschlusslage']
        except KeyError:
            self.anschlusslage = {k: "mitte" for k in self.anschlussgruppen.keys()}

        try:
            self.strecken = d['strecken']
        except KeyError:
            logger.info("fehlende streckenkonfiguration")

        self._update_gruppen_dict()
        self.config_loaded = True

        if load_graphs:
            try:
                self.signal_graph = nx.node_link_graph(d['signal_graph'])
            except KeyError:
                pass
            try:
                self.bahnsteig_graph = nx.node_link_graph(d['bahnsteig_graph'])
            except KeyError:
                pass
            try:
                self.bahnhof_graph = nx.node_link_graph(d['bahnhof_graph'])
            except KeyError:
                pass

    def save_config(self, path: os.PathLike):
        d = self.get_config(graphs=False)
        p = Path(path) / f"{self.anlage.aid}.json"
        with open(p, "w") as fp:
            json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

        if logger.isEnabledFor(logging.DEBUG):
            d = self.get_config(graphs=True)
            p = Path(path) / f"{self.anlage.aid}diag.json"
            with open(p, "w") as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

    def get_config(self, graphs=False) -> Dict:
        """
        aktuelle konfiguration im dict-format auslesen

        das dictionary kann dann im json-format abgespeichert und als konfigurationsdatei verwendet werden.

        :param graphs: gibt an, ob die graphen (im networkx node-link format mitgeliefert werden sollen.
        :return: dictionary mit konfiguration- und diagnostik-daten.
        """

        d = {'_aid': self.anlage.aid,
             '_region': self.anlage.region,
             '_name': self.anlage.name,
             '_build': self.anlage.build,
             '_version': 2,
             'bahnsteiggruppen': self.bahnsteiggruppen,
             'anschlussgruppen': self.anschlussgruppen,
             'anschlusslage': self.anschlusslage,
             'strecken': self.strecken}

        if graphs:
            if self.signal_graph:
                d['signal_graph'] = dict(nx.node_link_data(self.signal_graph))
            if self.bahnsteig_graph:
                d['bahnsteig_graph'] = dict(nx.node_link_data(self.bahnsteig_graph))
            # bahnhofgraph kann im moment wegen kontraktionen nicht codiert werden
            # if self.bahnhof_graph:
            #     d['bahnhof_graph'] = dict(nx.node_link_data(self.bahnhof_graph))

        return d


async def main():
    """
    anlagenkonfiguration ausgeben

    diese funktion dient der inspektion der anlage.
    die anlage inkl. wege, bahnsteige und zuege wird vom sim abgefragt und automatisch konfiguriert.
    die konfiguration wird dann im json-format an stdout ausgegeben.

    :return: None
    """
    client = PluginClient(name='anlageinfo', autor='tester', version='0.0', text='anlagekonfiguration auslesen')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                await client.request_bahnsteigliste()
                await client.request_wege()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
                await client.resolve_zugflags()
                client.update_bahnsteig_zuege()
                client.update_wege_zuege()

                anlage = Anlage(client.anlageninfo)
                anlage.update(client, "")
                d = anlage.get_config(graphs=True)
                s = json.dumps(d, sort_keys=True, indent=4, cls=JSONEncoder)
                print(s)
                raise TaskDone()
    except TaskDone:
        pass

if __name__ == "__main__":
    trio.run(main)
