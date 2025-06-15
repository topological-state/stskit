"""
schematischer netzplan (experimentell)

dieses modul ist in entwicklung.
"""

import logging
import math
import sys
from typing import Callable, Iterable, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import networkx as nx
import netgraph
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofGraph
from stskit.model.liniengraph import LinienGraph
from stskit.model.signalgraph import (graph_weichen_ersetzen, graph_anschluesse_pruefen,
                                      graph_bahnsteigsignale_ersetzen, graph_signalpaare_ersetzen,
                                      graph_schleifen_aufloesen, graph_zwischensignale_entfernen)

from stskit.zentrale import DatenZentrale
from stskit.qt.ui_gleisnetz import Ui_GleisnetzWindow


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def graph_nachbarbahnsteige_vereinen(g: nx.DiGraph) -> nx.DiGraph:
    while True:
        for u, v, t in g.edges(data="typ", default="unkannt"):
            if t == "nachbar":
                g = nx.contracted_nodes(g, u, v, self_loops=False, copy=False)
                break
        else:
            break

    g.remove_edges_from(nx.selfloop_edges(g))

    return g


BAHNHOF_COLORMAP = {'Bf': "tab:red",
                    'Bft': "tab:orange",
                    'Bs': "tab:blue",
                    'Gl': "tab:cyan",
                    'Anst': "tab:purple",
                    'Agl': "tab:pink"
                    }

SIGNAL_COLORMAP = {2: "tab:blue",  # Signal
                   3: "tab:gray",  # Weiche unten
                   4: "tab:gray",  # Weiche oben
                   5: "tab:red",  # Bahnsteig
                   6: "tab:pink",  # Einfahrt
                   7: "tab:purple",  # Ausfahrt
                   12: "tab:orange"}  # Haltepunkt


class SignalDiagramm:
    """
    Stellt einen SignalGraph grafisch dar.
    """
    def __init__(self):
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.canvas.figure.subplots()
        self.colormap = SIGNAL_COLORMAP
        self.netgraph = None

    def draw_graph(self, graph: nx.Graph, bahnsteig_graph: nx.Graph, filters: Optional[Iterable[Callable]] = None):
        self.axes.clear()

        graph = graph.to_undirected()
        graph.add_edges_from(bahnsteig_graph.edges, typ="nachbar")
        if filters is None:
            filters = []
        for filt in filters:
            graph = filt(graph)

        def fino(node):
            typ = graph.nodes[node]["typ"]
            return typ in {6, 7}

        sub_nodes = sorted([x for x, y in graph.nodes(data=True) if y.get('typ', -1) in {6, 7}])
        sub_graph = nx.subgraph(graph, sub_nodes).copy()
        # for x, y in zip(sub_nodes, sub_nodes[1:] + [sub_nodes[0]]):
        #     sub_graph.add_edge(x, y, typ='hilfslinie', distanz=1)
        sub_edges = list(zip(sub_nodes, sub_nodes[1:] + [sub_nodes[0]]))
        layout = netgraph.get_circular_layout(sub_edges)

        node_colors = {key: self.colormap.get(typ, "r")
                       for key, typ in graph.nodes(data='typ', default='kein')}

        node_labels = {key: data["name"] for key, data in graph.nodes(data=True) if data.get('typ', -1) in {5, 6, 7, 12}}

        edge_labels = {(e1, e2): distanz
                       for e1, e2, distanz in graph.edges(data='distanz', default=0)
                       if distanz > 0}
        edge_length = {(e1, e2): max(1/100, zeit / 100)
                       for e1, e2, zeit in graph.edges(data='distanz', default=0)}

        # node_size=3
        # node_edge_width
        node_label_fontdict = {"size": 10}
        edge_label_fontdict = {"size": 10, "bbox": {"boxstyle": "circle",
                                                    "fc": mpl.rcParams["axes.facecolor"],
                                                    "ec": mpl.rcParams["axes.facecolor"]}}
        self.netgraph = netgraph.InteractiveGraph(graph, ax=self.axes,
                                      node_layout="spring",
                                      # node_layout_kwargs=dict(node_positions=layout),
                                      node_color=node_colors,
                                      node_edge_width=0.0,
                                      node_labels=node_labels,
                                      node_label_fontdict=node_label_fontdict,
                                      node_size=0.5,
                                      edge_color=mpl.rcParams['text.color'],
                                      # edge_labels=edge_labels,
                                      # edge_label_fontdict=edge_label_fontdict,
                                      edge_width=0.2,
                                      prettify=False)

        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.set_aspect('equal')
        self.axes.figure.tight_layout()
        self.axes.figure.canvas.draw()


class SignalBahnhofDiagramm:
    """
    Reduziert einen SignalGraph auf die Bahnsteige und stellt ihre Beziehungen grafisch dar.
    """
    def __init__(self):
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.canvas.figure.subplots()
        self.colormap = SIGNAL_COLORMAP
        self.netgraph = None
        self.vereinfachter_graph = None

    def graph_vereinfachen(self, graph):
        g = graph.to_undirected()
        g = graph_weichen_ersetzen(g)
        g = graph_anschluesse_pruefen(g)
        g = graph_bahnsteigsignale_ersetzen(g)
        g = graph_signalpaare_ersetzen(g)
        g = graph_schleifen_aufloesen(g)
        g = graph_zwischensignale_entfernen(g)
        g = graph_schleifen_aufloesen(g)
        self.vereinfachter_graph = g

    def draw_graph(self, graph: nx.Graph, bahnsteig_graph: nx.Graph, filters: Optional[Iterable[Callable]] = None):
        self.axes.clear()

        if self.vereinfachter_graph is None:
            self.graph_vereinfachen(graph)

        node_colors = {key: self.colormap.get(typ, "r")
                       for key, typ in self.vereinfachter_graph.nodes(data='typ', default='kein')}

        node_labels = {key: name
                       for key, name in self.vereinfachter_graph.nodes(data='name', default='?')}

        edge_labels = {(e1, e2): distanz
                       for e1, e2, distanz in self.vereinfachter_graph.edges(data='distanz', default=0)
                       if distanz > 0}
        edge_length = {(e1, e2): 0.01
                       for e1, e2, zeit in self.vereinfachter_graph.edges(data='distanz', default=0)}

        # node_size=3
        # node_edge_width
        node_label_fontdict = {"size": 10}
        edge_label_fontdict = {"size": 10, "bbox": {"boxstyle": "circle",
                                                    "fc": mpl.rcParams["axes.facecolor"],
                                                    "ec": mpl.rcParams["axes.facecolor"]}}
        self.netgraph = netgraph.InteractiveGraph(self.vereinfachter_graph, ax=self.axes,
                                      node_layout="geometric",
                                      node_layout_kwargs=dict(edge_length=edge_length),
                                      node_color=node_colors,
                                      node_edge_width=0.0,
                                      node_labels=node_labels,
                                      node_label_fontdict=node_label_fontdict,
                                      node_size=1,
                                      edge_color=mpl.rcParams['text.color'],
                                      # edge_labels=edge_labels,
                                      # edge_label_fontdict=edge_label_fontdict,
                                      edge_width=0.2,
                                      prettify=False)

        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.set_aspect('equal')
        self.axes.figure.tight_layout()
        self.axes.figure.canvas.draw()


class BahnhofDiagramm:
    """
    Stellt einen BahnhofGraph grafisch dar.
    """
    def __init__(self):
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.canvas.figure.subplots()
        self.colormap = BAHNHOF_COLORMAP
        self.netgraph = None

    def draw_graph(self, graph: BahnhofGraph):
        self.axes.clear()

        edges_gen = nx.bfs_edges(graph, graph.root(), sort_neighbors=sorted)

        y_pos = {'Bf': 0.8,
                 'Bft': 0.7,
                 'Bs': 0.6,
                 'Gl': 0.5,
                 'Anst': 0.3,
                 'Agl': 0.2}

        graph = nx.subgraph_view(graph, filter_node=lambda node: node[0] in y_pos)

        node_colors = {}
        node_labels = {}
        node_positions = {}
        partitions_dict = {}

        for node, data in graph.nodes(data=True):
            if node[0] in y_pos:
                key = node
                node_labels[key] = data.name
                node_colors[key] = self.colormap.get(data.typ, "tab:gray")
                node_positions[key] = (0, y_pos[node[0]])

                try:
                    partitions_dict[data.typ].add(key)
                except KeyError:
                    partitions_dict[data.typ] = {key}

        partitions = {
            'Bf': sorted(partitions_dict['Bf']),
            'Bft': sorted(partitions_dict['Bft']),
            'Bs': sorted(partitions_dict['Bs']),
            'Gl': sorted(partitions_dict['Gl']),
            'Anst': sorted(partitions_dict['Anst']),
            'Agl': sorted(partitions_dict['Agl'])
        }

        x_delta = {k: 1 / (len(partition) + 1) for k, partition in partitions.items()}
        x_pos = {k: 0. for k in partitions.keys()}
        y_dither = {k: 0. for k in partitions.keys()}

        for e in edges_gen:
            node = e[1]
            typ = node[0]
            if typ in y_pos:
                x_pos[typ] = x = x_pos[typ] + x_delta[typ]
                dither = 0.02 * math.sin(y_dither[typ])
                y_dither[typ] += math.pi / 2
                node_positions[node] = (x, y_pos[typ] + dither)

        node_label_fontdict = {"size": 10}
        edge_label_fontdict = {"size": 10, "bbox": {"boxstyle": "circle",
                                                    "fc": mpl.rcParams["axes.facecolor"],
                                                    "ec": mpl.rcParams["axes.facecolor"]}}

        self.netgraph = netgraph.InteractiveGraph(graph,
                                                  ax=self.axes,
                                                  node_layout=node_positions,
                                                  node_color=node_colors,
                                                  node_edge_width=0.0,
                                                  node_labels=node_labels,
                                                  node_label_fontdict=node_label_fontdict,
                                                  node_size=1,
                                                  edge_color=mpl.rcParams['text.color'],
                                                  edge_width=0.2,
                                                  prettify=False
                                                  )

        node_proxy_artists = []
        for typ in y_pos:
            proxy = plt.Line2D(
                [], [],
                linestyle='None',
                color=self.colormap.get(typ, "tab:gray"),
                marker='o',
                markersize=2,
                label=typ
            )
            node_proxy_artists.append(proxy)

        node_legend = self.axes.legend(handles=node_proxy_artists, loc='upper left')
        self.axes.add_artist(node_legend)

        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.set_aspect('equal')
        self.axes.figure.tight_layout()
        self.axes.figure.canvas.draw()


def liniengraph_schleifen_aufloesen(g: nx.Graph):
    entfernen = set()

    for schleife in nx.simple_cycles(g):
        kanten = zip(schleife, schleife[1:] + schleife[:1])
        laengste_fahrzeit = 0
        summe_fahrzeit = 0
        laengste_kante = None
        for kante in kanten:
            fahrzeit = g.edges[kante].get("fahrzeit_min", 0)
            summe_fahrzeit += fahrzeit
            if fahrzeit > laengste_fahrzeit:
                laengste_fahrzeit = fahrzeit
                laengste_kante = kante

        if laengste_kante is not None:
            if laengste_fahrzeit > summe_fahrzeit - laengste_fahrzeit - len(schleife):
                entfernen.add(laengste_kante)
            else:
                print("symmetrische schleife", schleife)

    for u, v in entfernen:
        try:
            g.remove_edge(u, v)
        except nx.NetworkXError:
            pass

    return g


class LinienDiagramm:
    """
    Stellt einen LinienGraph grafisch dar.
    """
    def __init__(self):
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.canvas.figure.subplots()
        self.colormap = BAHNHOF_COLORMAP
        self.netgraph = None

    def draw_graph(self, graph: LinienGraph, filters: Optional[Iterable[Callable]] = None):
        self.axes.clear()

        if filters is None:
            filters = []
        for filt in filters:
            graph = filt(graph)

        node_colors = {key: self.colormap.get(typ, "tab:gray")
                       for key, typ in graph.nodes(data='typ', default='?')}
        node_labels = {key: name
                       for key, name in graph.nodes(data='name', default='?')}

        edge_labels = {(e1, e2): str(round(zeit))
                       for e1, e2, zeit in graph.edges(data='fahrzeit_schnitt', default=0)
                       if zeit > 0}
        edge_length = {(e1, e2): max(1/1000, zeit * 60 / 1000)
                       for e1, e2, zeit in graph.edges(data='fahrzeit_schnitt', default=0)}
        edge_width = {(e1, e2): min(1., max(1 / 100, fahrten / 10))
                      for e1, e2, fahrten in graph.edges(data='fahrten', default=0)}

        # node_size=3
        # node_edge_width
        node_label_fontdict = {"size": 10}
        edge_label_fontdict = {"size": 10, "bbox": {"boxstyle": "circle",
                                                    "fc": mpl.rcParams["axes.facecolor"],
                                                    "ec": mpl.rcParams["axes.facecolor"]}}

        self.netgraph = netgraph.InteractiveGraph(graph,
                                                  ax=self.axes,
                                                  node_layout="geometric",
                                                  node_layout_kwargs=dict(edge_length=edge_length),
                                                  node_color=node_colors,
                                                  node_edge_width=0.0,
                                                  node_labels=node_labels,
                                                  node_label_fontdict=node_label_fontdict,
                                                  node_size=1,
                                                  edge_color=mpl.rcParams['text.color'],
                                                  edge_labels=edge_labels,
                                                  edge_label_fontdict=edge_label_fontdict,
                                                  edge_width=edge_width,
                                                  # scale=(10., 10.),
                                                  prettify=False)

        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.axes.set_aspect('equal')
        self.axes.figure.tight_layout()
        self.axes.figure.canvas.draw()


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.anlage_update.register(self.anlage_update)

        self.ui = Ui_GleisnetzWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Netzplan")

        self.signal_diagramm = SignalDiagramm()
        self.signal_diagramm.canvas.setParent(self.ui.signal_graph_area)
        self.ui.signal_layout = QtWidgets.QHBoxLayout(self.ui.signal_graph_area)
        self.ui.signal_layout.setObjectName("signal_layout")
        self.ui.signal_layout.addWidget(self.signal_diagramm.canvas)
        self.signal_diagramm.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.bahnhof_diagramm = BahnhofDiagramm()
        self.bahnhof_diagramm.canvas.setParent(self.ui.bahnhof_graph_area)
        self.ui.bahnhof_layout = QtWidgets.QHBoxLayout(self.ui.bahnhof_graph_area)
        self.ui.bahnhof_layout.setObjectName("bahnhof_layout")
        self.ui.bahnhof_layout.addWidget(self.bahnhof_diagramm.canvas)
        self.bahnhof_diagramm.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.linien_diagramm = LinienDiagramm()
        self.linien_diagramm.canvas.setParent(self.ui.linien_graph_area)
        self.ui.linien_layout = QtWidgets.QHBoxLayout(self.ui.linien_graph_area)
        self.ui.linien_layout.setObjectName("linien_layout")
        self.ui.linien_layout.addWidget(self.linien_diagramm.canvas)
        self.linien_diagramm.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.ui.signal_aktualisieren_button.clicked.connect(self.on_signal_aktualisieren_button_clicked)
        self.ui.linien_aktualisieren_button.clicked.connect(self.on_linie_aktualisieren_button_clicked)

        self.signal_diagramm.canvas.setFocus()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    def anlage_update(self, *args, **kwargs):
        try:
            # if self.anlage.signalgraph and not self.signal_diagramm.netgraph:
            #     self.signal_diagramm.draw_graph(self.anlage.signalgraph, self.anlage.bahnsteiggraph)

            if self.anlage.bahnhofgraph:
                self.bahnhof_diagramm.draw_graph(self.anlage.bahnhofgraph)

            if self.anlage.liniengraph:
                self.linien_diagramm.draw_graph(self.anlage.liniengraph)
        except AttributeError as e:
            print("Fehler in Gleisnetz.anlage_update:", e, file=sys.stderr)

    @Slot()
    def on_signal_aktualisieren_button_clicked(self):
        filters = []

        if self.ui.signal_weichen_check.isChecked():
            filters.append(graph_weichen_ersetzen)
        if self.ui.signal_anschluss_check.isChecked():
            filters.append(graph_anschluesse_pruefen)
        if self.ui.signal_nachbarn_check.isChecked():
            filters.append(graph_nachbarbahnsteige_vereinen)
        if self.ui.signal_bahnsteig_check.isChecked():
            filters.append(graph_bahnsteigsignale_ersetzen)
        if self.ui.signal_paar_check.isChecked():
            filters.append(graph_signalpaare_ersetzen)
        if self.ui.signal_schleifen_check.isChecked():
            filters.append(graph_schleifen_aufloesen)
        if self.ui.signal_zwischen_check.isChecked():
            filters.append(graph_zwischensignale_entfernen)

        self.signal_diagramm.draw_graph(self.anlage.signalgraph, self.anlage.bahnsteiggraph, filters=filters)

    @Slot()
    def on_linie_aktualisieren_button_clicked(self):
        filters = []

        if self.ui.linien_schleifen_check.isChecked():
            filters.append(liniengraph_schleifen_aufloesen)
        self.linien_diagramm.draw_graph(self.anlage.liniengraph, filters=filters)
