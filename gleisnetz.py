"""
schematischer netzplan (experimentell)

dieses modul ist in entwicklung.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union

import numpy as np
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import networkx as nx

from stsplugin import PluginClient
from anlage import Anlage
from auswertung import StsAuswertung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisnetzWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.auswertung: Optional[StsAuswertung] = None

        self.setWindowTitle("gleisplan")
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
                nx.draw_networkx(self.anlage.bahnhof_graph, ax=self._axes, node_size=100)
            self._axes.figure.canvas.draw()
        except AttributeError:
            pass
