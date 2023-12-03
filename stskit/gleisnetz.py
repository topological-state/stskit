"""
schematischer netzplan (experimentell)

dieses modul ist in entwicklung.
"""

import logging

import numpy as np
from PyQt5 import QtCore, QtWidgets
import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import networkx as nx
from netgraph import InteractiveGraph

from stskit.interface.stsplugin import PluginClient
from stskit.anlage import Anlage
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.anlage_update.register(self.anlage_update)

        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure())
        canvas.setParent(self._main)
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()

        self.setWindowTitle("Gleisnetz")

        canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        canvas.setFocus()

        self._graph = None

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    def anlage_update(self, *args, **kwargs):
        if self._graph:
            return

        try:
            self._axes.clear()
            if self.anlage.bahnhof_graph:
                self.draw_graph()

            self._axes.figure.tight_layout()
            self._axes.figure.canvas.draw()
        except AttributeError:
            self._graph = None

    def draw_graph(self):
        graph = self.anlage.bahnhof_graph

        colormap = {'bahnhof': 'tab:blue', 'anschluss': 'tab:orange'}
        node_colors = {key: colormap.get(typ, "r") for key, typ in graph.nodes(data='typ', default='kein')}

        edge_labels = {(e1, e2): str(round(zeit / 60))
                       for e1, e2, zeit in graph.edges(data='fahrzeit_min', default=0)
                       if zeit >= 30}

        # node_size=3
        # node_edge_width
        node_label_fontdict = {"size": 10}
        edge_label_fontdict = {"size": 10, "bbox": {"boxstyle": "circle",
                                                    "fc": mpl.rcParams["axes.facecolor"],
                                                    "ec": mpl.rcParams["axes.facecolor"]}}
        self._graph = InteractiveGraph(self.anlage.bahnhof_graph, ax=self._axes,
                                       node_color=node_colors,
                                       node_edge_width=0.0,
                                       node_labels=True,
                                       node_label_fontdict=node_label_fontdict,
                                       node_size=2,
                                       edge_color=mpl.rcParams['text.color'],
                                       edge_labels=edge_labels,
                                       edge_label_fontdict=edge_label_fontdict,
                                       edge_width=0.5,
                                       prettify=False)

        self._axes.set_xticks([])
        self._axes.set_yticks([])
        self._axes.set_aspect('equal')

    def anlage_update_alt(self, *args, **kwargs):
        try:
            self._axes.clear()
            if self.anlage.bahnhof_graph:
                for e1, e2, d in self.anlage.bahnhof_graph.edges(data=True):
                    d['spring_weight'] = 1 / np.sqrt(d['fahrzeit_min']) if d['fahrzeit_min'] > 0 else 1
                    d['spectral_weight'] = 1

                pos = nx.spring_layout(self.anlage.bahnhof_graph, weight='spring_weight', seed=self.layout_seed)
                # pos = nx.circular_layout(self.anlage.bahnhof_graph)
                # pos = nx.spectral_layout(self.anlage.bahnhof_graph, weight='spectral_weight')
                # pos = nx.shell_layout(self.anlage.bahnhof_graph, seed=self.layout_seed)
                # pos = nx.multipartite_layout(self.anlage.bahnhof_graph)

                colormap = {'bahnhof': 'tab:blue', 'anschluss': 'tab:orange'}
                node_colors = [colormap.get(self.anlage.bahnhof_graph.nodes[key]['typ'], "r") for key in pos.keys()]

                edge_labels = {}
                edge_values = []
                edge_vmin = 0
                edge_vmax = 0
                for e1, e2, d in self.anlage.bahnhof_graph.edges(data=True):
                    try:
                        count = d['fahrzeit_count']
                    except KeyError:
                        count = 0
                    edge_vmax = max(edge_vmax, count)
                    edge_values.append(count)

                    try:
                        zeit = d['fahrzeit_min']
                    except KeyError:
                        zeit = np.nan

                    # try:
                    #     df = self.auswertung.fahrzeiten.zeiten
                    #     assert df.columns.name == 'von'
                    #     assert df.index.name == 'nach'
                    #     sel_von = list(self.anlage.gleisgruppen[e1].intersection(set(df.columns)))
                    #     sel_nach = list(self.anlage.gleisgruppen[e2].intersection(set(df.index)))
                    #     # loc[zeile, spalte] !!!
                    #     zeiten: pd.DataFrame = self.auswertung.fahrzeiten.zeiten.loc[sel_nach, sel_von]
                    #     s = zeiten.sum().sum()
                    #     n = zeiten.count().sum()
                    #     if n > 0:
                    #         zeit = s / n
                    # except AttributeError:
                    #     break
                    # except KeyError:
                    #     continue
                    # except TypeError:
                    #     break
                    # except ZeroDivisionError:
                    #     continue

                    if not np.isnan(zeit):
                        edge_labels[(e1, e2)] = round(zeit / 60)

                nx.draw_networkx_nodes(self.anlage.bahnhof_graph, pos, node_size=100,
                                       node_color=node_colors, ax=self._axes)

                cmax = mpl.colors.to_rgb(mpl.rcParams['text.color'])[0]
                cmin = mpl.colors.to_rgb(mpl.rcParams['axes.facecolor'])[0]
                cmin = (cmax + cmin) / 2
                if edge_vmax > edge_vmin:
                    cscale = (cmax - cmin) / (edge_vmax - edge_vmin)
                    edge_colors = [(v, v, v) for v in map(lambda x: (x - edge_vmin) * cscale + cmin, edge_values)]
                else:
                    edge_colors = [(cmax, cmax, cmax) for v in edge_values]
                nx.draw_networkx_edges(self.anlage.bahnhof_graph, pos, ax=self._axes, edge_color=edge_colors)

                nx.draw_networkx_labels(self.anlage.bahnhof_graph, pos, ax=self._axes,
                                        font_color=mpl.rcParams['text.color'])

                bbox = dict(boxstyle="round", ec=mpl.rcParams['axes.facecolor'], fc=mpl.rcParams['axes.facecolor'])
                nx.draw_networkx_edge_labels(self.anlage.bahnhof_graph, pos, edge_labels=edge_labels,
                                             font_size='small', font_color=mpl.rcParams['text.color'],
                                             bbox=bbox, ax=self._axes)

            self._axes.figure.tight_layout()
            self._axes.figure.canvas.draw()
        except AttributeError:
            pass
