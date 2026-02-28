import logging
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Type, Union

import matplotlib as mpl
import networkx as nx
import numpy as np

from stskit.dispo.anlage import Anlage
from stskit.dispo.betrieb import Betrieb
from stskit.model.zielgraph import ZielGraph, ZielGraphNode
from stskit.model.zuggraph import ZugGraph, ZugGraphNode

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def format_zeit(minuten: int, verspaetung: int) -> str:
    if verspaetung:
        return f"{int(minuten) // 60:02}:{int(minuten) % 60:02}{int(verspaetung):+}"
    else:
        return f"{int(minuten) // 60:02}:{int(minuten) % 60:02}"


class ZielPlot:
    def __init__(self, anlage: Anlage, betrieb: Betrieb) -> None:
        self.anlage = anlage
        self.betrieb = betrieb
        self.zugzielgraph = ZielGraph()
        self.zid: Optional[int] = None
        self.positionen = {}

    @property
    def zuggraph(self) -> ZugGraph:
        return self.anlage.zuggraph

    @property
    def zielgraph(self) -> ZielGraph:
        return self.betrieb.zielgraph

    def select_zug(self, zid: int):
        """
        Zug auswählen

        :param zid: Zug
        """

        self.zid = zid

    def _update_zugzielgraph(self):
        """
        Zugzielgraph aktualisieren

        Der Zugzielgraph enthält alle mit dem gewählten Zug verbundenen Züge, die noch nicht ausgefahren sind.
        Der zugzielgraph ist ein View von zielgraph.
        """

        g = self.zielgraph.to_undirected(as_view=True)
        node = self.zielgraph.zuganfaenge.get(self.zid)
        if node is not None:
            nodes = nx.node_connected_component(g, node)
            nodes = [node for node in nodes if not self.zuggraph.nodes[node[0]]['ausgefahren']]
            self.zugzielgraph = nx.subgraph(self.zielgraph, nodes)
        else:
            self.zugzielgraph = nx.DiGraph()

    def draw(self, axes):
        axes.clear()
        self._update_zugzielgraph()

        self.draw_zielgraph(ax=axes)

        axes.figure.tight_layout()
        axes.figure.canvas.draw()

    def draw_zielgraph(self, ax=None):
        self.topo_layout()

        edge_labels = {(e1, e2): d.get('typ', '?') for e1, e2, d in self.zugzielgraph.edges(data=True)}
        edge_color_map = {'P': 'w', 'E': 'b', 'F': 'g', 'K': 'm', '?': 'r', 'A': 'darkorange'}
        edge_colors = [edge_color_map[d.get('typ', '?')] for e1, e2, d in self.zugzielgraph.edges(data=True)]

        node_format = self.format_node_label_name
        node_color = self.node_color

        for node, data in self.zugzielgraph.nodes(data=True):
            label = node_format(data)
            try:
                farbe = node_color(data)
            except (AttributeError, KeyError, TypeError) as e:
                farbe = mpl.rcParams['text.color']

            label_options = {"ec": farbe, "fc": mpl.rcParams['axes.facecolor'], "alpha": 1.0, "pad": 2}
            if data.zid != self.zid:
                label_options["ls"] = "--"
            nx.draw_networkx_labels(self.zugzielgraph, self.positionen, labels={node: label},
                                    font_size="x-small", font_color=farbe,
                                    bbox=label_options, ax=ax)

        # args: edge_color, alpha
        nx.draw_networkx_edges(self.zugzielgraph, self.positionen, edge_color=edge_colors, node_size=500, min_source_margin=20, min_target_margin=20, ax=ax)

        label_options = {"ec": mpl.rcParams['axes.facecolor'], "fc": mpl.rcParams['axes.facecolor'], "alpha": 1.0, "pad": 2}
        nx.draw_networkx_edge_labels(self.zugzielgraph, self.positionen, edge_labels=edge_labels,
                                     font_size='x-small', font_color=mpl.rcParams['text.color'],
                                     bbox=label_options, ax=ax)

    def zeit_layout(self):
        sorted_nodes = list(nx.topological_sort(self.zugzielgraph))

        zuege = set([])
        zugliste = []
        for node in sorted_nodes:
            try:
                zid = node.zid
            except AttributeError:
                zid = node[0]

            if zid not in zuege:
                zugliste.append(zid)
            zuege.add(zid)

        zug_pos = {zid: idx for idx, zid in enumerate(zugliste)}

        pos = {}
        zeit = {zid: 0 for zid in zuege}
        for node in sorted_nodes:
            try:
                zid = node.zid
            except AttributeError:
                zid = node[0]

            try:
                zeit[zid] = min(zeit[zid] - 1, -self.zugzielgraph.nodes[node]['p_ab'])
            except KeyError:
                zeit[zid] -= 1

            pos[node] = np.array((zug_pos[zid], zeit[zid]))

        self.positionen = pos

    def topo_layout(self):
        def _linear_edge(n1, n2):
            return self.zugzielgraph[n1][n2].get("typ", "P") in {"P", "E"}

        komponenten_index = {}
        einfache_ketten = nx.subgraph_view(self.zugzielgraph, filter_edge=_linear_edge)
        for komponente, kette in enumerate(nx.weakly_connected_components(einfache_ketten)):
            for zzn in kette:
                komponenten_index[zzn[0]] = komponente

        sorted_nodes = list(nx.topological_sort(self.zugzielgraph))

        pos = {}
        zeit = 0
        letzte_spalte = -1
        komponenten_spalte = {}

        for node in sorted_nodes:
            try:
                zid = node.zid
            except AttributeError:
                zid = node[0]

            try:
                spalte = komponenten_spalte[komponenten_index[zid]]
            except KeyError:
                spalte = letzte_spalte = letzte_spalte + 1
                komponenten_spalte[komponenten_index[zid]] = letzte_spalte

            zeit -= 1
            pos[node] = np.array((spalte, zeit))

        self.positionen = pos

    def format_node_label_name(self, data: ZielGraphNode) -> str:
        label = []

        if data.fid == self.zielgraph.zuganfaenge[data.zid]:
            try:
                zug_name = self.zuggraph.nodes[data.zid]['name']
            except KeyError:
                zug_name = "?"
            label.append(zug_name)

        try:
            label.append(data.plan)
        except AttributeError:
            label.append('Gleis?')

        try:
            ankunft = format_zeit(data['p_an'], 0)
        except KeyError:
            ankunft = ""
        try:
            abfahrt = format_zeit(data['p_ab'], 0)
        except KeyError:
            abfahrt = ""
        label.append(" - ".join((ankunft, abfahrt)))

        return "\n".join(label)

    def format_node_label_zid(self, data: ZielGraphNode) -> str:
        label = []
        label.append(f"{data['zid']} {data['typ']} {data['plan']}")
        label.append(format_zeit(data.get('p_an', 0), data.get('v_an', 0)) + " / " + format_zeit(data.get('p_ab'), data.get('v_ab', 0)))
        return "\n".join(label)

    def node_color(self, data: ZielGraphNode):
        if 'W' in data.flags or 'L' in data.flags:
            farbe = 'tab:brown'
        else:
            farbe = mpl.rcParams['text.color']

        try:
            zug: ZugGraphNode = self.zuggraph.nodes[data.zid]
        except KeyError:
            pass
        else:
            if zug.sichtbar:
                if data.status == "ab":
                    farbe = "darkcyan"
                elif data.status == "an" or data.gleis == zug.gleis:
                    farbe = "cyan"
                elif data.typ == "B":
                    farbe = "orange"
            elif not zug.gleis:
                farbe = "darkcyan"
            elif data.typ == "B":
                farbe = "orange"

        return farbe
