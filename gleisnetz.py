from typing import Any, Dict, List, Optional, Set, Union

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import itertools
import json
import networkx as nx

from stsplugin import PluginClient
from database import StsConfig
from auswertung import StsAuswertung
from stsobj import Knoten


def strip_signals(g: nx.Graph) -> nx.Graph:
    # h = nx.subgraph_view(g, lambda n: g.nodes[n]['typ'] in {5, 6, 7, 12})
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


def gruppieren(g: nx.Graph, gruppen: Dict[str, Set[str]]) -> nx.Graph:
    for gr_name, gr_set in gruppen.items():
        lst = sorted(list(gr_set))
        print(gr_name, lst)

        if gr_name not in g.nodes:
            g.add_node(gr_name, typ=Knoten.TYP_NUMMER["Bahnsteig"])
            g.add_edge(gr_name, lst[0])

        lst = [gr_name, *lst]
        for name1, name2 in itertools.permutations(lst, r=2):
            print(name1, name2)
            try:
                g = nx.contracted_edge(g, (name1, name2), self_loops=False, copy=False)
            except (KeyError, ValueError):
                print("Error")

    return g


def gruppen_union(*gr: Dict[str, Set[str]]):
    d = dict()
    for g in gr:
        for k, v in g.items():
            if k in d:
                d[k] = d[k].union(v)
            else:
                d[k] = v
    return d


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.config: Optional[StsConfig] = None
        self.auswertung: Optional[StsAuswertung] = None

        self.setWindowTitle("gleisplan")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()
        self._graph: nx.Graph = nx.Graph()

    def update1(self):
        try:
            self._graph.clear()

            von_liste = [o for o in self.auswertung.fahrzeiten.zeiten.columns]
            nach_list = [o for o in self.auswertung.fahrzeiten.zeiten.index]

            for von, nach in itertools.product(von_liste, nach_list):
                try:
                    z = self.auswertung.fahrzeiten.zeiten.at[nach, von]
                    if not np.isnan(z):
                        self._graph.add_edge(von, nach, zeit=z)
                except KeyError:
                    pass

            self._axes.clear()
            nx.draw_networkx(self._graph, ax=self._axes)
            self._axes.figure.canvas.draw()
        except AttributeError:
            pass

    def update(self):
        knoten_auswahl = {Knoten.TYP_NUMMER["Signal"],
                          Knoten.TYP_NUMMER["Bahnsteig"],
                          Knoten.TYP_NUMMER["Einfahrt"],
                          Knoten.TYP_NUMMER["Ausfahrt"],
                          Knoten.TYP_NUMMER["Haltepunkt"]}

        try:
            self._graph.clear()
            for knoten1 in self.client.wege.values():
                if knoten1.name and knoten1.typ in knoten_auswahl:
                    self._graph.add_node(knoten1.name)
                    self._graph.nodes[knoten1.name]['typ'] = knoten1.typ
                    for knoten2 in knoten1.nachbarn:
                        if knoten2.name and knoten2.typ in knoten_auswahl:
                            self._graph.add_edge(knoten1.name, knoten2.name)

            self._graph = strip_signals(self._graph)
            # gruppen = gruppen_union(self.config.bahnsteigsgruppen, self.config.einfahrtsgruppen,
            #                         self.config.ausfahrtsgruppen)
            # self._graph = nx.quotient_graph(self._graph, gruppen)
            self._axes.clear()
            nx.draw_networkx(self._graph, ax=self._axes, node_size=100)
            self._axes.figure.canvas.draw()
        except AttributeError:
            pass

    def update3(self):
        if self.auswertung.fahrzeiten is not None:
            df = self.auswertung.fahrzeiten.fahrten
            self._graph.add_edges_from(zip(df['von'], df['nach']))
            nx.draw_networkx(self._graph, ax=self._axes)
            self._axes.figure.canvas.draw()

        #    h.add_nodes_from((n for n in g.nodes if 'typ' in g.nodes[n] and g.nodes[n]['typ'] in {2, 5, 6, 7, 12}))
        #    h.add_edges_from(((n1, n2) for n1, n2 in itertools.product(h.nodes, h.nodes) if n1 < n2))

    def dump(self):
        data1 = nx.readwrite.json_graph.node_link_data(self._graph)
        path = f"{self.client.anlageninfo.name}.netz.json"
        with open(path, "w") as fp:
            json.dump(data1, fp, sort_keys=True, indent=4)

doc = """
    pos : dictionary, optional
        A dictionary with nodes as keys and positions as values.
        If not specified a spring layout positioning will be computed.
        See :py:mod:`networkx.drawing.layout` for functions that
        compute node positions.

    nodelist : list (default=list(G))
        Draw only specified nodes

    edgelist : list (default=list(G.edges()))
        Draw only specified edges

    node_size : scalar or array (default=300)
        Size of nodes.  If an array is specified it must be the
        same length as nodelist.

    node_color : color or array of colors (default='#1f78b4')
        Node color. Can be a single color or a sequence of colors with the same
        length as nodelist. Color can be string or rgb (or rgba) tuple of
        floats from 0-1. If numeric values are specified they will be
        mapped to colors using the cmap and vmin,vmax parameters. See
        matplotlib.scatter for more details.

    node_shape :  string (default='o')
        The shape of the node.  Specification is as matplotlib.scatter
        marker, one of 'so^>v<dph8'.

    alpha : float or None (default=None)
        The node and edge transparency

    cmap : Matplotlib colormap, optional
        Colormap for mapping intensities of nodes

    vmin,vmax : float, optional
        Minimum and maximum for node colormap scaling

    linewidths : scalar or sequence (default=1.0)
        Line width of symbol border

    width : float or array of floats (default=1.0)
        Line width of edges

    edge_color : color or array of colors (default='k')
        Edge color. Can be a single color or a sequence of colors with the same
        length as edgelist. Color can be string or rgb (or rgba) tuple of
        floats from 0-1. If numeric values are specified they will be
        mapped to colors using the edge_cmap and edge_vmin,edge_vmax parameters.

    edge_cmap : Matplotlib colormap, optional
        Colormap for mapping intensities of edges

    edge_vmin,edge_vmax : floats, optional
        Minimum and maximum for edge colormap scaling

    style : string (default=solid line)
        Edge line style e.g.: '-', '--', '-.', ':'
        or words like 'solid' or 'dashed'.
        (See `matplotlib.patches.FancyArrowPatch`: `linestyle`)

    labels : dictionary (default=None)
        Node labels in a dictionary of text labels keyed by node
"""