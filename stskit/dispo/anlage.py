import logging
import os
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple

import networkx as nx

from stskit.interface.stsgraph import GraphClient
from stskit.interface.stsobj import Knoten
from stskit.graphs.signalgraph import SignalGraph
from stskit.graphs.bahnhofgraph import BahnhofGraph, BahnsteigGraph
from stskit.graphs.liniengraph import LinienGraph
from stskit.utils.gleisnamen import default_anschlussname, default_bahnhofname, default_bahnsteigname
from stskit.zugschema import Zugschema


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def bahnhofgraph_konfig_umdrehen(gleis_konfig, anschluss_konfig):
    """
    Konfiguration invertieren

    bahnhofgraph_konfigurien benoetigt eine bottom-up Struktur,
    waehrend die Konfigurationsdatei eine top-down Struktur hat.
    diese Methode wandelt top-down in bottom-up um.
    """

    result = {}

    for bf, bf_dict in gleis_konfig.items():
        for bft, bft_dict in bf_dict.items():
            for bs, bs_set in bft_dict.items():
                for gl in bs_set:
                    result[('Gl', gl)] = (bf, bft, bs)

    for anst, anst_set in anschluss_konfig.items():
        for agl in anst_set:
            result[('Agl', agl)] = (anst,)

    return result


class Anlage:
    def __init__(self):
        self.signalgraph = SignalGraph()
        self.bahnsteiggraph = BahnsteigGraph()
        self.bahnhofgraph = BahnhofGraph()
        self.liniengraph = LinienGraph()

        # todo : zugschema
        # todo : strecken
        # todo : streckenmarkierung

        self.strecken: Dict[str, Tuple[str]] = {}
        self.hauptstrecke: str = ""
        self.streckenmarkierung: Dict[Tuple[str, str], str] = {}
        self.gleissperrungen: Set[str] = set([])

        self.zugschema = Zugschema()

    def update(self, client: GraphClient, config_path: os.PathLike):
        # todo : update-frequenz
        # todo : konfiguration
        self.graphen_uebernehmen(client.signalgraph, client.bahnsteiggraph)

    def graphen_uebernehmen(self,
                            signalgraph: SignalGraph,
                            bahnsteiggraph: BahnsteigGraph):

        self.signalgraph = signalgraph.copy(as_view=False)
        self.bahnsteiggraph = bahnsteiggraph.copy(as_view=False)
        # todo : bahnhofteile anpassen

        self.bahnhofgraph_erstellen()
        self.liniengraph_konfigurieren()

    def bahnhofgraph_erstellen(self):
        """
        Initialisiert den Bahnhofgraphen aus dem Bahnsteiggraphen

        """
        self.bahnhofgraph.clear()
        
        for comp in nx.connected_components(self.bahnsteiggraph):
            bft = default_bahnsteigname(sorted(comp)[0])
            bf = default_bahnhofname(bft)
            self.bahnhofgraph.add_node(('Bf', bf), name=bf, typ='Bf', auto=True)
            self.bahnhofgraph.add_node(('Bft', bft), name=bft, typ='Bft', auto=True)
            self.bahnhofgraph.add_edge(('Bf', bf), ('Bft', bft), typ='Bf', auto=True)
            
            for gleis in comp:
                bs = default_bahnsteigname(gleis)
                self.bahnhofgraph.add_node(('Bs', bs), name=bs, typ='Bs', auto=True)
                self.bahnhofgraph.add_node(('Gl', gleis), name=gleis, typ='Gl', auto=True)
                self.bahnhofgraph.add_edge(('Bft', bft), ('Bs', bs), typ='Bft', auto=True)
                self.bahnhofgraph.add_edge(('Bs', bs), ('Gl', gleis), typ='Bs', auto=True)

        for anschluss, data in self.signalgraph.nodes(data=True):
            if data['typ'] in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                agl = data['name']
                agl_data = dict(name=agl, typ='Agl', auto=True)
                if data['typ'] == Knoten.TYP_NUMMER['Einfahrt']:
                    agl_data['einfahrt'] = True
                if data['typ'] == Knoten.TYP_NUMMER['Ausfahrt']:
                    agl_data['ausfahrt'] = True

                anst = default_anschlussname(agl)
                self.bahnhofgraph.add_node(('Agl', agl), **agl_data)
                self.bahnhofgraph.add_node(('Anst', anst), name=anst, typ='Anst', auto=True)
                self.bahnhofgraph.add_edge(('Agl', agl), ('Anst', anst), typ='Anst', auto=True)

    def bahnhofgraph_konfigurieren(self, config: Dict[Tuple[str, str], Tuple[str, ...]]) -> None:
        """
        Modifiziert den Bahnhofgraphen anhand von Konfigurationsdaten

        :param config: Mapping von STS-Gleisnamen zu Tupel (Bahnsteig, Bahnhofteil, Bahnhof) bzw. (Anschlussstelle)
        """

        relabeling = {}

        def bahnhof_ast(graph: nx.Graph, gl: Tuple[str, str]) -> Optional[List[Tuple[str, str]]]:
            """
            Finde den Bf bzw. Anst-Knoten und gib den Pfad zum Gleisknoten zurück.
            :param graph: Bahnhofgraph
            :param gl: Gleislabel (typ, name)
            :return: Liste von Bahnhofgraphlabels von Bf zu Gl, bzw. Anst zu Agl
            """

            try:
                pfade = nx.shortest_path(graph, target=gl)
            except nx.NodeNotFound:
                return None

            for key, pfad in pfade.items():
                if key[0] in {'Bf', 'Anst'}:
                    return pfad

        for gleis, bf_bft_bs in config.items():
            ast = bahnhof_ast(self.bahnhofgraph, gleis)
            if ast:
                for label_alt, name_neu in zip(ast, bf_bft_bs):
                    typ, name_alt = label_alt
                    if name_neu != name_alt:
                        relabeling[label_alt] = (typ, name_neu)

        nx.relabel_nodes(self.bahnhofgraph, relabeling, copy=False)

        for node, data in self.bahnhofgraph.nodes(data=True):
            if data['name'] != node[1]:
                data['name'] = node[1]
                data['auto'] = False

    def liniengraph_konfigurieren(self):
        pass