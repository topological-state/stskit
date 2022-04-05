import matplotlib as mpl
import numpy as np
from typing import Any, Dict, List, Optional, Set, Union

from PyQt5 import QtCore, QtWidgets, uic, QtGui

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from stsplugin import PluginClient
from database import StsConfig
from auswertung import StsAuswertung
from stsobj import time_to_minutes, Ereignis

mpl.use('Qt5Agg')


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


class EinfahrtenWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.config: Optional[StsConfig] = None
        self.auswertung: Optional[StsAuswertung] = None

        self.setWindowTitle("einfahrten-chart")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()
        self._balken = None
        self._labels = []

    @staticmethod
    def zugtitel(zug) -> str:
        """
        "zugname (verspätung)"

        :return: (str)
        """

        if zug.verspaetung:
            return f"{zug.nummer} ({zug.verspaetung:+})"
        else:
            return f"{zug.nummer}"

    def update(self):
        if self._balken is not None:
            self._balken.remove()
        for label in self._labels:
            label.remove()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        # kwargs['color'] = 'red'
        kwargs['edgecolor'] = 'black'
        kwargs['linewidth'] = 1
        kwargs['width'] = 1.0

        try:
            x_labels_pos, x_labels, x_pos, y_bot, y_hgt, bar_labels, colors = self.build_bars(
                self.client.wege_nach_typ[6])
        except KeyError:
            return None

        self._axes.set_title('einfahrten')
        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')

        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(10))
        self._axes.yaxis.grid(True, which='major')
        # ymin = min(y_bot)
        ymin = time_to_minutes(self.client.calc_simzeit())
        self._axes.set_ylim(bottom=ymin + 30, top=ymin, auto=False)

        self._balken = self._axes.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, **kwargs)
        self._labels = self._axes.bar_label(self._balken, labels=bar_labels, label_type='center',
                                            fontsize='small', fontstretch='condensed')

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def build_bars(self, knoten_liste):
        x_labels = set()
        slots = list()

        for knoten in knoten_liste:
            gruppenname = knoten.name
            # gruppenname = self.config.suche_gleisgruppe(knoten.name, self.config.einfahrtsgruppen)
            if not gruppenname:
                continue

            for zug in knoten.zuege:
                if not zug.sichtbar:
                    try:
                        zeile = zug.fahrplan[0]
                        ankunft = time_to_minutes(zeile.an) + zug.verspaetung
                        korrektur = self.auswertung.fahrzeiten.get_fahrzeit(zug.von, zeile.gleis) / 60
                        if not np.isnan(korrektur):
                            ankunft -= round(korrektur)
                        aufenthalt = 1
                        slot = {'zug': zug, 'gruppe': gruppenname, 'zeit': ankunft, 'dauer': aufenthalt}
                    except (AttributeError, IndexError):
                        pass
                    else:
                        x_labels.add(gruppenname)
                        slots.append(slot)

        x_labels = sorted(x_labels)
        x_labels_pos = list(range(len(x_labels)))

        # konfliktbehandlung
        slots.sort(key=lambda s: s['zeit'])
        frei = {gruppe: 0 for gruppe in x_labels}
        letzter_slot = {gruppe: None for gruppe in x_labels}
        for slot in slots:
            slot['konflikt'] = frei[slot['gruppe']] > slot['zeit']
            if slot['konflikt'] and letzter_slot[slot['gruppe']] is not None:
                letzter_slot[slot['gruppe']]['konflikt'] = True
            slot['zeit'] = max(frei[slot['gruppe']], slot['zeit'])
            frei[slot['gruppe']] = slot['zeit'] + slot['dauer']
            letzter_slot[slot['gruppe']] = slot

        x_pos = np.asarray([x_labels.index(slot['gruppe']) for slot in slots])
        y_bot = np.asarray([slot['zeit'] for slot in slots])
        y_hgt = np.asarray([slot['dauer'] for slot in slots])
        labels = [f"{self.zugtitel(slot['zug'])}" for slot in slots]

        # farben = {g: mpl.colors.TABLEAU_COLORS[i % len(mpl.colors.TABLEAU_COLORS)]
        #           for i, g in enumerate(self.client.zuggattungen)}
        # colors = [farben[b[5]] for b in bars]
        farben = [k for k in mpl.colors.TABLEAU_COLORS]

        # colors = [farben[i % len(farben)] for i in range(len(bars))]

        # colors = [farben[slot['zug'].nummer // 10000] for slot in slots]
        def farbe(sl):
            if sl['konflikt']:
                return 'r'
            else:
                return farben[sl['zug'].nummer // 10000]

        colors = [farbe(slot) for slot in slots]

        return x_labels_pos, x_labels, x_pos, y_bot, y_hgt, labels, colors
