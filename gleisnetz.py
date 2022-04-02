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


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


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

    def update(self):
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

            # self._graph = nx.Graph()
            # for name, knoten1 in self.client.wege.items():
            #     if knoten1.typ in {Knoten.TYP_NUMMER["Bahnsteig"],
            #                        Knoten.TYP_NUMMER["Einfahrt"],
            #                        Knoten.TYP_NUMMER["Ausfahrt"],
            #                        Knoten.TYP_NUMMER["Haltepunkt"]}:
            #         self._graph.add_node(name)
            #         self._graph.nodes[name]['typ'] = knoten1.typ
            #         # for knoten2 in knoten1.nachbarn:
            #         #    g.add_edge(knoten1.name, knoten2.name)

        # if self.auswertung.fahrzeiten is not None:
        #     df = self.auswertung.fahrzeiten.fahrten
        #     self._graph.add_edges_from(zip(df['von'], df['nach']))
        #     nx.draw_networkx(self._graph, ax=self._axes)
        #     self._axes.figure.canvas.draw()

        #    h.add_nodes_from((n for n in g.nodes if 'typ' in g.nodes[n] and g.nodes[n]['typ'] in {2, 5, 6, 7, 12}))
        #    h.add_edges_from(((n1, n2) for n1, n2 in itertools.product(h.nodes, h.nodes) if n1 < n2))

    def debug(self):
        # with open("netz.txt", "wt") as f:
        #     for name, knoten1 in self.client.wege.items():
        #         for knoten2 in knoten1.nachbarn:
        #             f.write(f"{knoten1.name}, {knoten2.name}, {knoten1.typ}, {knoten2.typ}\n")

        g = nx.Graph()
        for name, knoten1 in self.client.wege.items():
            g.add_node(name)
            g.nodes[name]['typ'] = knoten1.typ
            for knoten2 in knoten1.nachbarn:
                g.add_edge(knoten1.name, knoten2.name)

        data1 = nx.readwrite.json_graph.node_link_data(g)
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