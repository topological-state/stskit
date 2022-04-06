from dataclasses import dataclass, field
import itertools
import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets
import re
from typing import Any, Dict, List, Iterable, Mapping, Optional, Set, Union, Tuple

from auswertung import StsAuswertung
from database import StsConfig
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes

mpl.use('Qt5Agg')


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


def gleisname_sortkey(s: str) -> Tuple[str, int, str]:
    expr = r"([a-zA-Z]*)([0-9]*)([a-zA-Z]*)"
    mo = re.match(expr, s)
    try:
        return mo.group(1), int(mo.group(2)), mo.group(3)
    except ValueError:
        return mo.group(1), mo.group(2), mo.group(3)


# farben = {g: mpl.colors.TABLEAU_COLORS[i % len(mpl.colors.TABLEAU_COLORS)]
#           for i, g in enumerate(self.client.zuggattungen)}
# colors = [farben[b[5]] for b in bars]
farben = [k for k in mpl.colors.TABLEAU_COLORS]


# colors = [farben[i % len(farben)] for i in range(len(bars))]

# colors = [farben[slot['zug'].nummer // 10000] for slot in slots]


@dataclass
class Slot:
    zug: ZugDetails
    plan: FahrplanZeile
    gleis: str = ""
    zeit: int = 0
    dauer: int = 0
    kuppelzug: Optional[ZugDetails] = None
    konflikte: List['Slot'] = field(default_factory=list)

    def __eq__(self, other):
        return self.zug.name == other.zug.name and self.gleis == other.gleis and self.zeit == other.zeit

    @property
    def farbe(self) -> str:
        if self.zug.gattung in {'ICE', 'TGV'}:
            return 'tab:orange'
        elif self.zug.gattung in {'IC', 'EC', 'IR', 'IRE'}:
            return 'tab:green'
        elif self.zug.gattung in {'RE', 'RB'}:
            return 'tab:blue'
        elif self.zug.gattung in {'S'}:
            return 'tab:purple'
        elif self.zug.nummer < 2000:
            return 'tab:green'
        elif self.zug.nummer < 10000:
            return 'tab:blue'
        elif self.zug.nummer < 30000:
            return 'tab:purple'
        else:
            return 'tab:brown'

    @property
    def randfarbe(self) -> str:
        if self.konflikte:
            return 'r'
        elif self.kuppelzug:
            return 'g'
        else:
            return 'k'

    @property
    def titel(self) -> str:
        """
        "zugname (verspätung)"
        """
        if self.zug.verspaetung:
            return f"{self.zug.name} ({self.zug.verspaetung:+})"
        else:
            return f"{self.zug.name}"

    @property
    def style(self) -> str:
        return "italic" if self.plan.durchfahrt() else "normal"


class GleisbelegungWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.config: Optional[StsConfig] = None
        self.auswertung: Optional[StsAuswertung] = None

        self.setWindowTitle("gleisbelegung")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()
        self._balken = None
        self._labels = []

        self._belegte_gleise: List[str] = []
        self._slots: List[Slot] = []

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5

    def update(self):
        self._axes.clear()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        kwargs['width'] = 1.0

        self.belegung_berechnen()
        x_labels = self._belegte_gleise
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([self._belegte_gleise.index(slot.gleis) for slot in self._slots])
        y_bot = np.asarray([slot.zeit for slot in self._slots])
        y_hgt = np.asarray([slot.dauer for slot in self._slots])
        labels = [slot.titel for slot in self._slots]
        colors = [slot.farbe for slot in self._slots]
        style = [slot.style for slot in self._slots]
        edgecolors = [slot.randfarbe for slot in self._slots]
        linewidth = [w for w in map(lambda f: 1 if f == 'k' else 2, edgecolors)]

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(10))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        zeit = time_to_minutes(self.client.calc_simzeit())
        self._axes.set_ylim(bottom=zeit + self.zeitfenster_voraus, top=zeit - self.zeitfenster_zurueck, auto=False)

        self._balken = self._axes.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, edgecolor=edgecolors,
                                      linewidth=linewidth, **kwargs)
        self._labels = self._axes.bar_label(self._balken, labels=labels, label_type='center',
                                            fontsize='small', fontstretch='condensed')
        self._axes.axhline(y=0)

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def belegung_berechnen(self):
        gleise = set()
        slots = list()

        for zug in self.client.zugliste.values():
            for planzeile in zug.fahrplan:
                if planzeile.gleis:
                    gleise.add(planzeile.gleis)
                else:
                    continue

                slot = Slot(zug, planzeile, planzeile.gleis)
                slot.zeit = time_to_minutes(slot.plan.an) + zug.verspaetung
                try:
                    slot.dauer = max(1, time_to_minutes(slot.plan.ab) - time_to_minutes(slot.plan.an))
                except AttributeError:
                    slot.dauer = 1

                # ersatzzug anhängen
                if ersatzzug := planzeile.ersatzzug:
                    slot.dauer = max(1, time_to_minutes(ersatzzug.fahrplan[0].an) + zug.verspaetung - slot.zeit)
                elif kuppelzug := planzeile.kuppelzug:
                    slot.kuppelzug = kuppelzug
                    slot.dauer = max(1, time_to_minutes(kuppelzug.fahrplan[0].an) + kuppelzug.verspaetung - slot.zeit)
                elif fluegelzug := planzeile.fluegelzug:
                    slot.kuppelzug = fluegelzug

                if slot not in slots:
                    slots.append(slot)

        gleise = sorted(gleise, key=gleisname_sortkey)

        # konflikte erkennen
        for s1, s2 in itertools.permutations(slots, r=2):
            if s1.dauer >= 5:
                s1.dauer = max(5, s1.dauer - s1.zug.verspaetung)
            if s1.gleis == s2.gleis and s1.zeit <= s2.zeit < s1.zeit + s1.dauer:
                if s1.kuppelzug is not None and s1.kuppelzug == s2.zug:
                    s2.kuppelzug = s1.zug
                elif s2.kuppelzug is not None and s2.kuppelzug == s1.zug:
                    s1.kuppelzug = s2.zug
                else:
                    s1.konflikte.append(s2)
                    s2.konflikte.append(s1)

        self._slots = slots
        self._belegte_gleise = gleise
