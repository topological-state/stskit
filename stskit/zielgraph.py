"""
werkzeug zur darstellung von zugläufen aus einem zielgraphen

die darstellung des zielgraphen ist momentan nur als library verfügbar.
möglicherweise wird sie später in das hauptprogramm integriert.

anwendungsbeispiel
------------------

~~~~~~
import stskit.zielgraph as zielgraph
import networkx as nx
import matplotlib as mpl
mpl.use("QtAgg")  # nicht nötig, wenn die IDE matplotlib-figuren unterstützt, z.b. pycharm professional
g = zielgraph.load("/home/matthias/.stskit/696.zielgraph.json")
zg = zielgraph.zug_subgraph(g, 101106)
zielgraph.plot_zielgraph(zg)
~~~~~~

"""

import json
import logging
import os
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Type, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def ziel_zeit_layout(graph: nx.Graph) -> Dict:
    sorted_nodes = list(nx.topological_sort(graph))

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
            zeit[zid] = min(zeit[zid] - 1, -graph.nodes[node]['p_ab'])
        except KeyError:
            zeit[zid] -= 1

        pos[node] = np.array((zug_pos[zid], zeit[zid]))

    return pos


def ziel_topo_layout(graph: nx.Graph) -> Dict:
    def _linear_edge(n1, n2):
        return graph[n1][n2].get("typ", "P") in {"P", "E"}

    komponenten_index = {}
    einfache_ketten = nx.subgraph_view(graph, filter_edge=_linear_edge)
    for komponente, kette in enumerate(nx.weakly_connected_components(einfache_ketten)):
        for zzn in kette:
            komponenten_index[zzn[0]] = komponente

    sorted_nodes = list(nx.topological_sort(graph))

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

    return pos


def format_zeit(minuten: int, verspaetung: int) -> str:
    if verspaetung:
        return f"{int(minuten) // 60:02}:{int(minuten) % 60:02}{verspaetung:+}"
    else:
        return f"{int(minuten) // 60:02}:{int(minuten) % 60:02}"


def format_node_label_name(data: Dict[str, Any]) -> str:
    # typ, zid, plan, p_an, p_ab, v_an, v_ab
    label = []
    try:
        zug_name = data['obj'].zug.name
    except KeyError:
        zug_name = "?"
    label.append(f"{zug_name} {data.get('typ', '?')} {data.get('plan', '?')}")
    try:
        label.append(format_zeit(data['p_an'], data['v_an']) + " / " + format_zeit(data['p_ab'], data['v_ab']))
    except KeyError:
        pass
    return "\n".join(label)


def format_node_label_zid(data: Dict[str, Any]) -> str:
    # typ, zid, plan, p_an, p_ab, v_an, v_ab
    label = []
    label.append(f"{data['zid']} {data['typ']} {data['plan']}")
    label.append(format_zeit(data['p_an'], data['v_an']) + " / " + format_zeit(data['p_ab'], data['v_ab']))
    return "\n".join(label)


def draw_zielgraph(graph: nx.Graph, node_format=format_node_label_zid, node_color=None, ax=None):
    pos = ziel_topo_layout(graph)

    edge_labels = {(e1, e2): d.get('typ', '?') for e1, e2, d in graph.edges(data=True)}
    edge_color_map = {'P': 'w', 'E': 'b', 'F': 'g', 'K': 'm', '?': 'r', 'A': 'darkorange'}
    edge_colors = [edge_color_map[d.get('typ', '?')] for e1, e2, d in graph.edges(data=True)]

    for node, data in graph.nodes(data=True):
        label = node_format(data)
        try:
            farbe = node_color(data)
        except (AttributeError, KeyError, TypeError) as e:
            farbe = mpl.rcParams['text.color']

        label_options = {"ec": farbe, "fc": mpl.rcParams['axes.facecolor'], "alpha": 1.0, "pad": 2}
        nx.draw_networkx_labels(graph, pos, labels={node: label},
                                font_size="x-small", font_color=farbe,
                                bbox=label_options, ax=ax)

    # args: edge_color, alpha
    nx.draw_networkx_edges(graph, pos, edge_color=edge_colors, ax=ax)

    label_options = {"ec": mpl.rcParams['axes.facecolor'], "fc": mpl.rcParams['axes.facecolor'], "alpha": 1.0, "pad": 2}
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels,
                                 font_size='x-small', font_color=mpl.rcParams['text.color'],
                                 bbox=label_options, ax=ax)


def plot_zielgraph(graph: nx.Graph):
    plt.rcParams["figure.figsize"] = [15, 10]
    # plt.rcParams["figure.dpi"] = 300
    plt.rcParams["figure.autolayout"] = True
    draw_zielgraph(graph)
    plt.show()


def zug_subgraph(graph: nx.DiGraph, zid: int) -> Optional[nx.Graph]:
    g = graph.to_undirected(as_view=True)
    for node, data in g.nodes.items():
        try:
            if data['zid'] == zid:
                nodes = nx.node_connected_component(g, node)
                break
        except KeyError:
            pass
    else:
        return None

    return nx.subgraph(graph, nodes)


def verarbeitete_stammzuege_entfernen(zielgraph: nx.Graph, zuggraph: nx.Graph, zid: int):

    try:
        zug = zuggraph.nodes[zid]['obj']
    except KeyError:
        logger.warning(f"kein zugobjekt zu zid {zid} im zugbaum")
        return

    verarbeitete_zuege = {
        _zid for _zid, _zug in zuggraph.nodes(data='obj', default=zug)
        if _zug.ausgefahren and _zug.ausfahrtszeit < zug.einfahrtszeit
    }

    entfernen = [
        _zzid for _zzid, _zid in zielgraph.nodes(data='zid', default=None)
        if _zid in verarbeitete_zuege
    ]

    for _zzid in entfernen:
        zielgraph.remove_node(_zzid)


def load(path: os.PathLike):
    with open(path, encoding='utf-8') as f:
        graph_dict = json.load(f)
    graph = nx.node_link_graph(graph_dict)
    return graph

# largest_cc = max(nx.weakly_connected_components(g), key=len)