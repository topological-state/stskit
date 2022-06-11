"""
schematischer netzplan (experimentell)

dieses modul ist in entwicklung.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union

import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import networkx as nx

from stsplugin import PluginClient
from anlage import Anlage
from auswertung import Auswertung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.auswertung: Optional[Auswertung] = None

        self.setWindowTitle("gleisplan (experimentell)")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()

    def update(self):
        try:
            self._axes.clear()
            if self.anlage.bahnhof_graph:
                self.anlage.generalisieren('fahrzeit_min')

                for e1, e2, d in self.anlage.bahnhof_graph.edges(data=True):
                    d['spring_weight'] = 1 / np.sqrt(d['fahrzeit_min']) if d['fahrzeit_min'] > 0 else 1
                    d['spectral_weight'] = 1

                pos = nx.spring_layout(self.anlage.bahnhof_graph, weight='spring_weight', seed=0)
                # pos = nx.circular_layout(self.anlage.bahnhof_graph)
                # pos = nx.spectral_layout(self.anlage.bahnhof_graph, weight='spectral_weight')
                # pos = nx.shell_layout(self.anlage.bahnhof_graph, seed=0)
                # pos = nx.multipartite_layout(self.anlage.bahnhof_graph)

                colormap = {'bahnhof': 'tab:blue', 'anschluss': 'tab:orange'}
                colors = [colormap[self.anlage.bahnhof_graph.nodes[key]['typ']] for key in pos.keys()]
                labels = {key: name for key, name in self.anlage.bahnhof_graph.nodes(data='name')}

                edge_labels = {}
                for e1, e2, zeit in self.anlage.bahnhof_graph.edges(data='fahrzeit_min'):
                    try:
                        df = self.auswertung.fahrzeiten.zeiten
                        assert df.columns.name == 'von'
                        assert df.index.name == 'nach'
                        sel_von = list(self.anlage.gleisgruppen[e1].intersection(set(df.columns)))
                        sel_nach = list(self.anlage.gleisgruppen[e2].intersection(set(df.index)))
                        # loc[zeile, spalte] !!!
                        zeiten: pd.DataFrame = self.auswertung.fahrzeiten.zeiten.loc[sel_nach, sel_von]
                        s = zeiten.sum().sum()
                        n = zeiten.count().sum()
                        if n > 0:
                            zeit = s / n
                    except AttributeError:
                        break
                    except KeyError:
                        continue
                    except TypeError:
                        break
                    except ZeroDivisionError:
                        continue
                    if not np.isnan(zeit):
                        edge_labels[(e1, e2)] = round(zeit / 60)

                nx.draw_networkx_nodes(self.anlage.bahnhof_graph, pos, node_size=100,
                                       node_color=colors, ax=self._axes)
                nx.draw_networkx_edges(self.anlage.bahnhof_graph, pos, ax=self._axes)
                nx.draw_networkx_labels(self.anlage.bahnhof_graph, pos, labels=labels, ax=self._axes)
                nx.draw_networkx_edge_labels(self.anlage.bahnhof_graph, pos, edge_labels=edge_labels,
                                             font_size='small', ax=self._axes)

            self._axes.figure.tight_layout()
            self._axes.figure.canvas.draw()
        except AttributeError:
            pass
