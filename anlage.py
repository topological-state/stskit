from collections.abc import Set
import json
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx

from stsobj import AnlagenInfo, BahnsteigInfo, Knoten
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


def strip_signals(g: nx.Graph) -> nx.Graph:
    """
    signale aus graph entfernen

    alle signalknoten werden entfernt, ihre nachbarknoten direkt miteinander verbunden.

    :param g: ursprünglicher graph
    :return: neuer graph
    """
    h = g
    n2 = len(g)
    n1 = n2 + 1
    while n2 < n1:
        n1 = n2
        h = g.copy(as_view=False)
        for edge in g.edges:
            if g.nodes[edge[0]]['typ'] != 2 and g.nodes[edge[1]]['typ'] == 2:
                try:
                    nx.contracted_edge(h, edge, self_loops=False, copy=False)
                except ValueError:
                    pass

        n2 = len(nx.subgraph_view(h, lambda n: h.nodes[n]['typ'] == 2))
        g = h

    return h


def gruppen_union(*gr: Dict[str, Set[str]]):
    d = dict()
    for g in gr:
        for k, v in g.items():
            if k in d:
                d[k] = d[k].union(v)
            else:
                d[k] = v
    return d


def get_gruppen_name(g):
    return ''.join(common_prefix(g))


class Anlage:
    def __init__(self, anlage: AnlagenInfo):
        self.anlage = anlage
        self.auto = True
        self._data = {'einfahrtsgruppen': dict(),
                      'ausfahrtsgruppen': dict(),
                      'bahnsteigsgruppen': dict()}
        self.original_graph: Optional[nx.Graph] = None
        self.bahnhof_graph: Optional[nx.Graph] = None

    @property
    def einfahrtsgruppen(self) -> Dict[str, Set[str]]:
        """
        gruppierung von einfahrten

        mehrere einfahrten können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen auf sets von knotennamen ab.

        :return: dictionary gruppenname -> set of (knotenname)
        """
        return self._data['einfahrtsgruppen']

    @property
    def ausfahrtsgruppen(self) -> Dict[str, Set[str]]:
        """
        gruppierung von ausfahrten

        mehrere ausfahrten können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen auf sets von knotennamen ab.

        :return: dictionary gruppenname -> set of (knotenname)
        """
        return self._data['ausfahrtsgruppen']

    @property
    def bahnsteigsgruppen(self) -> Dict[str, Set[str]]:
        """
        gruppierung von bahnsteigen

        mehrere bahnsteige (typischerweise alle zu einem bahnhof gehörigen)
        können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen (bahnhofnamen) auf sets von bahnsteignamen ab.

        :return: dictionary gruppenname -> set of (bahnsteigname)
        """
        return self._data['bahnsteigsgruppen']

    def suche_gleisgruppe(self, gleis: str, gruppen: Dict) -> Optional[str]:
        """
        suche gleis in bahnsteig- oder knotengruppe.

        :param gleis: gleisname
        :param gruppen: dict entsprechend einfahrtsgruppen, ausfahrtsgruppen oder bahnsteigsgruppen.
        :return: gruppenname
        """
        for name, gruppe in gruppen.items():
            if gleis in gruppe:
                return name
        return None

    def auto_config(self, client: PluginClient):
        """
        bestimmt die gruppen basierend auf anlageninfo und üblicher schreibweise der gleisnamen.

        einfahrten und ausfahrten werden nach dem ersten namensteil gruppiert.
        der erste namensteil wird zum gruppennamen.

        bahnsteige werden nach nachbarn gemäss anlageninfo gruppiert.
        der gruppenname wird aus dem längsten gemeinsamen namensteil gebildet.

        :param client:
        :return: None
        """
        self.anlage = client.anlageninfo
        expr = r"([a-zA-Z]*)([ 0-9]*).*"

        for k in client.wege_nach_typ[Knoten.TYP_NUMMER['Einfahrt']]:
            try:
                mo = re.match(expr, k.name)
                gr = mo.group(1)
            except IndexError:
                pass
            else:
                try:
                    self.einfahrtsgruppen[gr].add(k.name)
                except KeyError:
                    self.einfahrtsgruppen[gr] = {k.name}
                try:
                    self.ausfahrtsgruppen[gr].add(k.name)
                except KeyError:
                    self.ausfahrtsgruppen[gr] = {k.name}

        for k in client.wege_nach_typ[Knoten.TYP_NUMMER['Ausfahrt']]:
            try:
                mo = re.match(expr, k.name)
                gr = mo.group(1)
            except IndexError:
                pass
            else:
                try:
                    self.einfahrtsgruppen[gr].add(k.name)
                except KeyError:
                    self.einfahrtsgruppen[gr] = {k.name}
                try:
                    self.ausfahrtsgruppen[gr].add(k.name)
                except KeyError:
                    self.ausfahrtsgruppen[gr] = {k.name}

        bsl: List[BahnsteigInfo] = [bi for bi in client.bahnsteigliste.values()]
        while bsl:
            bs = bsl.pop(0)
            gruppe = {bs}.union(bs.nachbarn)

            # gruppenname
            namen = [bn.name for bn in gruppe]
            name = ''.join(common_prefix(namen))
            if not name:
                name = bs.name
            try:
                self.bahnsteigsgruppen[name].update(namen)
            except KeyError:
                self.bahnsteigsgruppen[name] = set(namen)

            # jeder bahnsteig in max. einer gruppe
            for bn in bs.nachbarn:
                try:
                    bsl.remove(bn)
                except ValueError:
                    pass

            # konsistenz mit wegnetz pruefen
            for n in namen:
                if n not in client.wege:
                    print(f"bahnsteig {n} ist im gleisnetz nicht vorhanden")

        self.original_graph_erstellen(client)

    def load_config(self, path):
        """

        :param path:
        :return:
        :raise: OSError, JSONDecodeError(ValueError)
        """
        with open(path) as fp:
            d = json.load(fp, object_hook=json_object_hook)
        try:
            self._data = d[str(self.anlage.aid)]
        except KeyError:
            pass
        else:
            self.auto = False

    def save_config(self, path):
        try:
            with open(path) as fp:
                d = json.load(fp, object_hook=json_object_hook)
        except (OSError, json.decoder.JSONDecodeError):
            d = dict()

        if self._data:
            aid = str(self.anlage.aid)
            d[aid] = self._data
            d[aid]['_region'] = self.anlage.region
            d[aid]['_name'] = self.anlage.name
            d[aid]['_build'] = self.anlage.build

            with open(path, "w") as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

    def original_graph_erstellen(self, client: PluginClient):
        knoten_auswahl = {Knoten.TYP_NUMMER["Signal"],
                          Knoten.TYP_NUMMER["Bahnsteig"],
                          Knoten.TYP_NUMMER["Einfahrt"],
                          Knoten.TYP_NUMMER["Ausfahrt"],
                          Knoten.TYP_NUMMER["Haltepunkt"]}

        self.original_graph = nx.Graph()
        for knoten1 in client.wege.values():
            if knoten1.name and knoten1.typ in knoten_auswahl:
                self.original_graph.add_node(knoten1.name)
                self.original_graph.nodes[knoten1.name]['typ'] = knoten1.typ
                for knoten2 in knoten1.nachbarn:
                    if knoten2.name and knoten2.typ in knoten_auswahl:
                        self.original_graph.add_edge(knoten1.name, knoten2.name)

    def bahnsteige_pruefen(self):
        pass

    def einfahrten_pruefen(self):
        pass

    def ausfahrten_pruefen(self):
        pass

    def validate(self):
        """
        wir muessen pruefen, dass
        - jede gruppe genau einmal vorkommt
        - jeder bahnsteig genau einmal vorkommt und einer gruppe zugewiesen ist

        :return:
        """
        self.einfahrten_pruefen()
        self.ausfahrten_pruefen()
        self.bahnsteige_pruefen()
        self.bahnhof_graph_erstellen()

    def bahnhof_graph_erstellen(self):
        try:
            self.bahnhof_graph = strip_signals(self.original_graph)

            gruppen = gruppen_union(self.bahnsteigsgruppen,
                                    self.einfahrtsgruppen, self.ausfahrtsgruppen)

            gruppen2 = {}
            for g, s in gruppen.items():
                t = s.intersection(self.bahnhof_graph.nodes)
                if len(t):
                    gruppen2[g] = t
            gruppen = gruppen2

            all_nodes = set().union(*gruppen.values())
            all_nodes = sorted(all_nodes)

            nodes = {n for c in gruppen.values() for n in c if n in self.bahnhof_graph.nodes}
            nodes = sorted(nodes)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("--- bahnhof_graph_erstellen debug info")
                logger.debug(str(all_nodes))
                logger.debug(str(nodes))
                logger.debug(str(sorted(self.bahnhof_graph.nodes)))
                logger.debug(f"{len(self.bahnhof_graph)}, {len(nodes)}, {sum(len(c) for c in gruppen)}")
                for k, c in gruppen.items():
                    logger.debug(f"{k}, {sorted(c)}")
                logger.debug("---")

            self.bahnhof_graph = nx.quotient_graph(self.bahnhof_graph, gruppen)
            self.bahnhof_graph = nx.relabel_nodes(self.bahnhof_graph, get_gruppen_name)

        except AttributeError:
            pass

    def dump(self):
        data1 = nx.readwrite.json_graph.node_link_data(self.original_graph)
        path = f"{self.anlage.name}.netz.json"
        with open(path, "w") as fp:
            json.dump(data1, fp, sort_keys=True, indent=4)

    def testing(self):
        path = "Rotkreuz.netz.json"
        with open(path, "r") as fp:
            data = json.load(fp)

        self.original_graph = nx.readwrite.node_link_graph(data)
        self.bahnhof_graph = strip_signals(self.original_graph)


def main():
    pass


if __name__ == "__main__":
    main()
