import math
from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets

from auswertung import Auswertung
from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from slotgrafik import hour_minutes_formatter, ZugFarbschema
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


@dataclass
class Trasse():
    zug: ZugDetails
    color: str = "b"
    fontstyle: str = "normal"
    linestyle: str = "-"
    linewidth: int = 1


class BildFahrplanWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.planung: Optional[Planung] = None
        self.auswertung: Optional[Auswertung] = None

        self.setWindowTitle("bildfahrplan")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()

        # bahnhofname -> distanz [minuten]
        self._strecke: Dict[str, float] = {}
        self._trassen: List[Trasse] = []

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5
        self.farbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

    def set_strecke(self, streckenname: str):
        sd = self.anlage.get_strecken_distanzen(streckenname)
        for k, v in sd.items():
            sd[k] = v / 60
        self.update()

    def update(self):
        if not self._strecke:
            try:
                self.set_strecke(list(self.anlage.strecken.keys())[0])
            except IndexError:
                logger.warning("bildfahrplan: keine strecken definiert.")
                return

        self.daten_update()
        self.grafik_update()

    def daten_update(self):
        for zug in self.client.zugliste.values():
            trasse = Trasse()
            koord = []
            plan1 = zug.fahrplan[0]
            for plan2 in zug.fahrplan[1:]:
                gruppe1 = self.anlage.bahnsteige[plan1.gleis]
                gruppe2 = self.anlage.bahnsteige[plan2.gleis]
                if gruppe1 in self._strecke and gruppe2 in self._strecke:
                    koord.append((self.distanz[gruppe1], time_to_minutes(plan1.ab)))
                    koord.append((self.distanz[gruppe2], time_to_minutes(plan2.an)))
            trasse.koord = koord
            trasse.color = self.farbschema.zugfarbe(zug)
            self._trassen.append(trasse)

    def grafik_update(self):
        self._axes.clear()

        x_labels = list(self._strecke.keys())
        x_labels_pos = list(self._strecke.values())

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(5))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        zeit = time_to_minutes(self.client.calc_simzeit())
        self._axes.set_ylim(bottom=zeit + self.zeitfenster_voraus, top=zeit - self.zeitfenster_zurueck, auto=False)

        wid_x = x_labels_pos[-1] - x_labels_pos[0]
        wid_y = self.zeitfenster_zurueck + self.zeitfenster_voraus
        off_x = 0
        off_y = 1  # todo : von pixel umrechnen

        for trasse in self._trassen:
            lines = self._axes.plot(trasse.koord, color=trasse.color, lw=trasse.linewidth, ls=trasse.linestyle)
            labels = []
            for seg in zip(trasse.koord[:-1], trasse.koord[1:]):
                cx = (seg[0][0] + seg[1][0]) / 2 + off_x
                cy = (seg[0][1] + seg[1][1]) / 2 + off_y
                dx = (seg[1][0] - seg[0][0])
                dy = (seg[1][1] - seg[0][1])
                if abs(dx) > wid_x / 10:
                    # todo : koordinaten in pixel umrechnen
                    ang = math.degrees(math.atan2(dy, dx))
                    titel = trasse.zug.name
                    label = self._axes.text(cx, cy, titel, fontsize='small', fontstretch='condensed', rotation=ang)
                    labels.append(label)

            trasse.lines = lines
            trasse.labels = labels

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.zeitfenster_zurueck > 0:
            self._axes.axhline(y=zeit, color='k', lw=1)

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()
