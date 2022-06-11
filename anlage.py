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

from stsobj import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, time_to_seconds
from stsplugin import PluginClient


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
    def __init__(self, anlage: AnlagenInfo):
        self.anlage = anlage
        self.config_loaded = False
        self.auto = True

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
        self.bahnsteig_graph: nx.Graph = nx.DiGraph()
        self.bahnhof_graph: nx.Graph = nx.Graph()

        # strecken-name -> gruppen-namen
        self.strecken: Dict[str, Tuple[str]] = {}

    def update(self, client: PluginClient, config_path: os.PathLike):
        if not self.anlage:
            self.anlage = client.anlageninfo

        if len(self.signal_graph) == 0:
            self.original_graphen_erstellen(client)
            self.auto_gruppen()

        if not self.config_loaded:
            try:
                self.load_config(config_path)
            except (OSError, ValueError):
                logger.warning("fehler beim laden der anlagenkonfiguration")
            self.config_loaded = True

        if len(self.bahnhof_graph) == 0:
            self.bahnhof_graph_aus_fahrplan(client.zugliste.values())

        if not self.strecken:
            self.strecken_aus_fahrplan(client.zugliste.values())

    def original_graphen_erstellen(self, client: PluginClient):
        """
        erstellt die signal- und bahnsteig-graphen nach anlageninformationen vom simulator.

        der signal-graph enthält alle signale, bahnsteige, einfahrten, ausfahrten und haltepunkte aus der wege-liste
        der plugin-schnittstelle als knoten.
        das 'typ'-attribut wird auf den sts-knotentyp (int) gesetzt.
        kanten werden entsprechend der nachbarn-relationen aus der wegeliste ('typ'-attribut 'gleis') gesetzt.
        der graph ist gerichtet, da die nachbarbeziehung nicht reziprok ist.
        die kante zeigt auf die knoten, die als nachbarn aufgeführt sind.
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
        knoten_auswahl = {Knoten.TYP_NUMMER["Signal"],
                          Knoten.TYP_NUMMER["Bahnsteig"],
                          Knoten.TYP_NUMMER["Einfahrt"],
                          Knoten.TYP_NUMMER["Ausfahrt"],
                          Knoten.TYP_NUMMER["Haltepunkt"]}

        self.signal_graph.clear()
        for knoten1 in client.wege.values():
            if knoten1.name and knoten1.typ in knoten_auswahl:
                self.signal_graph.add_node(knoten1.name, typ=knoten1.typ)
                for knoten2 in knoten1.nachbarn:
                    if knoten2.name and knoten2.typ in knoten_auswahl:
                        self.signal_graph.add_edge(knoten1.name, knoten2.name, typ='gleis', distanz=1)

        pat = re.compile(r'[^\d\W]*')
        for bs1 in client.bahnsteigliste.values():
            self.bahnsteig_graph.add_node(bs1.name)
            pre1 = re.match(pat, bs1.name).group(0)
            for bs2 in bs1.nachbarn:
                pre2 = re.match(pat, bs2.name).group(0)
                if pre1 == pre2:
                    self.bahnsteig_graph.add_edge(bs1.name, bs2.name, typ='bahnhof', distanz=0)
                else:
                    self.bahnsteig_graph.add_edge(bs1.name, bs2.name, typ='nachbar', distanz=0)

    def bahnhof_graph_erstellen(self):
        """
        bahnhof-graph aus signal-graph ableiten

        der bahnhofgraph enthält die bahnhöfe (self.bahnhofnamen) als knoten und verbindungen als kanten.

        self.bahnsteiggruppen und self.anschlussgruppen müssen bereits definiert sein.

        :return:
        """
        bahnsteig_typen = {Knoten.TYP_NUMMER["Bahnsteig"], Knoten.TYP_NUMMER["Haltepunkt"]}
        graph = nx.Graph()

        for n, s in self.bahnsteiggruppen.items():
            graph.add_node(n, typ='bahnhof', elemente=s, name=n)
        for n, s in self.anschlussgruppen.items():
            graph.add_node(n, typ='anschluss', elemente=s, name=n)

        alle_gruppen = dict_union(self.bahnsteiggruppen, self.anschlussgruppen)
        alle_gleise = set().union(*alle_gruppen.values())

        gleis_graph = self.signal_graph.to_undirected()
        for u, d in gleis_graph.nodes(data=True):
            d['bahnhof'] = d['typ'] in bahnsteig_typen
            for v in gleis_graph[u]:
                if gleis_graph.nodes[v]['typ'] in bahnsteig_typen:
                    d['bahnhof'] = True
                    break

        for u, v in itertools.combinations(alle_gleise, 2):
            try:
                p = nx.shortest_path(gleis_graph, u, v)
                for n in p[2:-2]:
                    if gleis_graph.nodes[n]['bahnhof']:
                        break
                else:
                    ug = find_set_item_in_dict(u, alle_gruppen)
                    vg = find_set_item_in_dict(v, alle_gruppen)
                    if ug != vg:
                        graph.add_edge(ug, vg, distanz=len(p))
            except (nx.NetworkXException, ValueError):
                continue

        edges_to_remove = set([])
        for u, nbrs in graph.adj.items():
            ns = set(nbrs) - {u}
            for v, w in itertools.combinations(ns, 2):
                try:
                    luv = graph[u][v]['distanz']
                    lvw = graph[v][w]['distanz']
                    luw = graph[u][w]['distanz']
                    if luv < lvw and luw < lvw:
                        edges_to_remove.add((v, w))
                except KeyError:
                    pass

        graph.remove_edges_from(edges_to_remove)

        self.bahnhof_graph = graph

    def bahnhof_graph_aus_fahrplan(self, zugliste: Iterable[ZugDetails]):
        """
        bahnhof-graph aus fahrplan erstellen.

        der bahnhofgraph enthält die bahnhöfe (self.bahnhofnamen) als knoten und verbindungen als kanten.

        self.bahnsteiggruppen, self.anschlussgruppen definieren die knoten und müssen daher schon konfiguriert sein.

        :return:
        """
        bahnsteig_typen = {Knoten.TYP_NUMMER["Bahnsteig"], Knoten.TYP_NUMMER["Haltepunkt"]}
        graph = self.bahnhof_graph

        for n, s in self.bahnsteiggruppen.items():
            graph.add_node(n, typ='bahnhof', elemente=s, name=n)
        for n, s in self.anschlussgruppen.items():
            graph.add_node(n, typ='anschluss', elemente=s, name=n)

        gleis_graph = self.signal_graph.copy()
        for u, d in gleis_graph.nodes(data=True):
            d['bahnhof'] = d['typ'] in bahnsteig_typen
            for v in gleis_graph[u]:
                if gleis_graph.nodes[v]['typ'] in bahnsteig_typen:
                    d['bahnhof'] = True
                    break

        for zug in zugliste:
            if zug.sichtbar:
                # der fahrplan von sichtbaren zügen kann unvollständig sein
                continue

            try:
                start = self.gleiszuordnung[zug.von]
                startzeit = np.nan
            except (IndexError, KeyError):
                continue

            for zeile in zug.fahrplan:
                try:
                    ziel = self.gleiszuordnung[zeile.plan]
                    zielzeit = time_to_seconds(zeile.an)
                except (AttributeError, KeyError):
                    break

                zeit = zielzeit - startzeit
                if start != ziel:
                    try:
                        d = graph[start][ziel]
                        d['fahrzeit_sum'] = d['fahrzeit_sum'] + zeit
                        d['fahrzeit_min'] = min(d['fahrzeit_min'], zeit) if not np.isnan(d['fahrzeit_min']) else zeit
                        d['fahrzeit_max'] = max(d['fahrzeit_max'], zeit) if not np.isnan(d['fahrzeit_max']) else zeit
                        d['zuege'] = d['zuege'] + 1
                    except KeyError:
                        graph.add_edge(start, ziel, fahrzeit_sum=zeit, fahrzeit_min=zeit, fahrzeit_max=zeit, zuege=1)
                        logger.debug(f"edge {start}-{ziel} ({zeit})")

                start = ziel
                try:
                    startzeit = time_to_seconds(zeile.ab)
                except AttributeError:
                    break

            try:
                ziel = self.gleiszuordnung[zug.nach]
                if start != ziel:
                    graph.add_edge(start, ziel, fahrzeit_sum=0., fahrzeit_min=np.nan, fahrzeit_max=np.nan, zuege=0)
                    logger.debug(f"edge {start}-{ziel}")
            except (AttributeError, KeyError):
                pass

        edges_to_remove = set([])
        for u, nbrs in graph.adj.items():
            ns = set(nbrs) - {u}
            for v, w in itertools.combinations(ns, 2):
                try:
                    luv = graph[u][v]['fahrzeit_min']
                    lvw = graph[v][w]['fahrzeit_min']
                    luw = graph[u][w]['fahrzeit_min']
                    if luv < lvw and luw < lvw:
                        edges_to_remove.add((v, w))
                except KeyError:
                    pass

        # graph.remove_edges_from(edges_to_remove)

        nodes_to_remove = [node for node, degree in graph.degree() if degree < 1]
        graph.remove_nodes_from(nodes_to_remove)

        self.bahnhof_graph = graph

    def generalisieren(self, metrik):
        graph = self.bahnhof_graph

        edges_to_remove = set([])
        for u, nbrs in graph.adj.items():
            ns = set(nbrs) - {u}
            for v, w in itertools.combinations(ns, 2):
                try:
                    luv = graph[u][v][metrik]
                    lvw = graph[v][w][metrik]
                    luw = graph[u][w][metrik]
                    if luv < lvw and luw < lvw:
                        edges_to_remove.add((v, w))
                        logger.debug(f"remove {v}-{w} from triangle ({u},{v},{w}) distance ({lvw},{luw},{luv})")
                except KeyError:
                    pass

        graph.remove_edges_from(edges_to_remove)

    def auto_gruppen(self):
        """
        gruppiert bahnsteige zu bahnhöfen und ein-/ausfahrten zu anschlüssen.

        einfahrten und ausfahrten werden nach dem ersten namensteil gruppiert.
        der erste namensteil wird zum anschlussnamen.
        dieser algorithmus fasst in einigen stellwerken zu viele einfahrten zu einer gruppe zusammen.
        diese müssen manuell über die konfiguration aufgeteilt werden,
        da es keine einfache möglichkeit gibt, solche fälle anhand der plugin-schnittstelle zu erkennen.

        bahnsteige werden nach nachbarn gemäss anlageninfo gruppiert.
        der gruppenname wird aus dem längsten gemeinsamen namensteil gebildet.

        :return: None
        """
        anschlusstypen = {Knoten.TYP_NUMMER["Einfahrt"], Knoten.TYP_NUMMER["Ausfahrt"]}
        bahnsteigtypen = {Knoten.TYP_NUMMER["Bahnsteig"], Knoten.TYP_NUMMER["Haltepunkt"]}

        self.anschlussgruppen = {}
        nodes = [n for n, t in self.signal_graph.nodes(data='typ') if t in anschlusstypen]
        gr1 = set([n.split(" ")[0] for n in nodes])
        gruppen = []
        for k in gr1:
            gruppen.append(set([n for n in nodes if n.split(" ")[0] == k]))
        for g in gruppen:
            name = sorted(g)[0]
            self.anschlussgruppen[name] = g

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

        self.bahnsteiggruppen = {}
        subgraph = nx.subgraph_view(self.bahnsteig_graph, filter_node=filter_node, filter_edge=filter_edge)
        subgraph = subgraph.to_undirected()
        gruppen = list(nx.connected_components(subgraph))
        for g in gruppen:
            name = sorted(g)[0]
            self.bahnsteiggruppen[name] = g

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

    def strecken_aus_fahrplan(self, zugliste: Iterable[ZugDetails]):
        """
        streckenliste aus fahrplan erstellen.

        :return:
        """

        strecken = set([])

        for zug in zugliste:
            if zug.sichtbar:
                # der fahrplan von sichtbaren zügen kann unvollständig sein
                continue

            try:
                strecke = tuple((self.gleiszuordnung[wp] for wp in zug.route(plan=True)))
                if len(strecke) >= 3:
                    strecken.add(strecke)
            except KeyError:
                logger.warning(f"wegpunkte von zug {zug.name} können nicht auf bahnhöfe abgebildet werden.")

        vereinigte_strecken = set([])
        for strecke1, strecke2 in itertools.permutations(strecken, 2):
            # strecken aneinanderreihen
            if strecke1[-1] == strecke2[0]:
                strecke3 = list(strecke1[:-1])
                strecke3.extend(strecke2)
                strecke3 = tuple(strecke3)
                vereinigte_strecken.add(strecke3)
            # laengere strecke
            if set(strecke1).issuperset(set(strecke2)):
                vereinigte_strecken.add(strecke1)

        self.strecken = {f"{s[0]}-{s[-1]}": s for s in strecken}

    def get_strecken_distanzen(self, streckenname: str) -> Dict[str, float]:
        """

        :param streckenname:
        :return: distanz = minimale fahrzeit in sekunden
        """
        strecke = self.strecken[streckenname]
        kanten = zip(strecke[:-1], strecke[1:])
        distanz = 0.
        result = {strecke[0]: distanz}
        for u, v in kanten:
            try:
                zeit = self.bahnhof_graph[u][v]['fahrzeit_min']
                if not np.isnan(zeit):
                    distanz += zeit
                else:
                    distanz += 60.
            except KeyError:
                logger.warning(f"strecke {streckenname}: verbindung {u}{v} nicht im netzplan.")
                distanz += 60.

            result[v] = float(distanz)

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
        d = {'_aid': self.anlage.aid,
             '_region': self.anlage.region,
             '_name': self.anlage.name,
             '_build': self.anlage.build,
             '_version': 2,
             'bahnsteiggruppen': self.bahnsteiggruppen,
             'anschlussgruppen': self.anschlussgruppen,
             'anschlusslage': self.anschlusslage,
             'strecken': self.strecken}

        p = Path(path) / f"{self.anlage.aid}.json"
        with open(p, "w") as fp:
            json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

        if logger.isEnabledFor(logging.DEBUG):
            if self.signal_graph:
                d['signal_graph'] = dict(nx.node_link_data(self.signal_graph))
            if self.bahnsteig_graph:
                d['bahnsteig_graph'] = dict(nx.node_link_data(self.bahnsteig_graph))
            if self.bahnhof_graph:
                d['bahnhof_graph'] = dict(nx.node_link_data(self.bahnhof_graph))

            p = Path(path) / f"{self.anlage.aid}diag.json"
            with open(p, "w") as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)


def main():
    pass


if __name__ == "__main__":
    main()
