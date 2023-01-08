"""
schematischer netzplan (experimentell)

dieses modul ist in entwicklung.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSlot
import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import networkx as nx

from stskit.stsplugin import PluginClient
from stskit.anlage import Anlage
from stskit.auswertung import Auswertung
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.anlage_update.register(self.anlage_update)

        self.layout_seed: int = 0

        self.setWindowTitle("gleisplan")
        ss = f"background-color: {mpl.rcParams['axes.facecolor']};" \
             f"color: {mpl.rcParams['text.color']};"
        self.setStyleSheet(ss)
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()

        self.layout_spinbox = QtWidgets.QSpinBox(canvas)
        self.layout_spinbox.setMinimum(0)
        self.layout_spinbox.valueChanged.connect(self.layout_spinbox_changed)

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    @pyqtSlot(int)
    def layout_spinbox_changed(self, v):
        self.layout_seed = max(0, int(v))
        self.update()

    def anlage_update(self, *args, **kwargs):
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
