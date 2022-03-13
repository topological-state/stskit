import asyncio
import datetime
import matplotlib as mpl
import numpy as np
import sys
from typing import Any, Dict, List, Optional, Set, Union

from PyQt5 import QtCore, QtWidgets, uic, QtGui
import qasync

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from stsplugin import PluginClient
from database import StsConfig
from auswertung import StsAuswertung
from model import time_to_minutes, Ereignis

mpl.use('Qt5Agg')


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client = sts_client
        self.config: Optional[StsConfig] = None
        self.config_path = "zugtabelle.json"

        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        einfahrten_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(einfahrten_canvas)
        self._einfahrten_ax = einfahrten_canvas.figure.subplots()
        self._bars_ein = None
        self._labels_ein = []

        self.auswertung: Optional[StsAuswertung] = None

        self.enable_update = True
        self.update_task = asyncio.create_task(self.update_loop())

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        try:
            self.config.save(self.config_path)
        except (AttributeError, OSError):
            pass
        super().closeEvent(a0)

    async def update_loop(self):
        while self.enable_update:
            await self.update()
            await asyncio.sleep(15)

    async def update(self):
        # todo : ueberlappende zuege stapeln
        # todo : farben nach zug-gattungen
        if not self.client.is_connected():
            await self.client.connect()
        await self.get_sts_data()
        for art in Ereignis.arten:
            await self.client.request_ereignis(art, self.client.zugliste.keys())

        if not self.config:
            self.config = StsConfig(self.client.anlageninfo)
            try:
                self.config.load(self.config_path)
            except (OSError, ValueError):
                pass
            if self.config.auto:
                self.config.auto_config(self.client)

        if self.auswertung:
            self.auswertung.zuege_uebernehmen(self.client.zugliste.values())
        else:
            self.auswertung = StsAuswertung(self.config)

        if self._bars_ein is not None:
            self._bars_ein.remove()
        for label in self._labels_ein:
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

        self._einfahrten_ax.set_title('einfahrten')
        self._einfahrten_ax.set_xticks(x_labels_pos, x_labels)

        self._einfahrten_ax.yaxis.set_major_formatter(hour_minutes_formatter)
        self._einfahrten_ax.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._einfahrten_ax.yaxis.set_major_locator(mpl.ticker.MultipleLocator(10))
        self._einfahrten_ax.yaxis.grid(True, which='major')
        # ymin = min(y_bot)
        ymin = time_to_minutes(self.client.calc_simzeit())
        self._einfahrten_ax.set_ylim(bottom=ymin + 30, top=ymin, auto=False)

        self._bars_ein = self._einfahrten_ax.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, **kwargs)
        self._labels_ein = self._einfahrten_ax.bar_label(self._bars_ein, labels=bar_labels, label_type='center')

        # Trigger the canvas to update and redraw.
        self._einfahrten_ax.figure.canvas.draw()

    def build_bars(self, knoten_liste):
        x_labels = list(self.config.einfahrtsgruppen.keys())
        x_labels_pos = list(range(len(x_labels)))
        bars = list()

        for knoten in knoten_liste:
            if gruppenname := self.config.suche_gleisgruppe(knoten.name, self.config.einfahrtsgruppen):
                x_pos = x_labels.index(gruppenname)
            else:
                continue

            for zug in knoten.zuege:
                if not zug.sichtbar:
                    try:
                        zeile = zug.fahrplan[0]
                        ankunft = time_to_minutes(zeile.an) + zug.verspaetung
                        aufenthalt = 1
                        bar = (zug, x_pos, ankunft, aufenthalt)
                        bars.append(bar)
                    except (AttributeError, IndexError):
                        pass

        x_pos = np.asarray([b[1] for b in bars])
        y_bot = np.asarray([b[2] for b in bars])
        y_hgt = np.asarray([b[3] for b in bars])
        bar_labels = [b[0].name for b in bars]

        # farben = {g: mpl.colors.TABLEAU_COLORS[i % len(mpl.colors.TABLEAU_COLORS)]
        #           for i, g in enumerate(self.client.zuggattungen)}
        # colors = [farben[b[5]] for b in bars]
        farben = [k for k in mpl.colors.TABLEAU_COLORS]
        # colors = [farben[i % len(farben)] for i in range(len(bars))]
        colors = [farben[b[0].nummer // 10000] for b in bars]

        return x_labels_pos, x_labels, x_pos, y_bot, y_hgt, bar_labels, colors

    async def get_sts_data(self, alles=False):
        if alles or not self.client.anlageninfo:
            await self.client.request_anlageninfo()
        if alles or not self.client.bahnsteigliste:
            await self.client.request_bahnsteigliste()
        if alles or not self.client.wege:
            await self.client.request_wege()

        await self.client.request_zugliste()
        await self.client.request_zugdetails()
        await self.client.request_zugfahrplan()

        self.client.update_bahnsteig_zuege()
        self.client.update_wege_zuege()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        sts_client = PluginClient(name='zugtabelle', autor='bummler', version='0.1', text='zugtabellen')
        window = MainWindow()
        window.show()
        loop.run_forever()
        sts_client.close()
