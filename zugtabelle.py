import asyncio
import matplotlib as mpl
import numpy as np
import sys
import time

from PyQt5 import QtCore, QtWidgets, uic
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from stsplugin import PluginClient

mpl.use('Qt5Agg')


def minutes(dt):
    try:
        return dt.hour * 60 + dt.minute
    except AttributeError:
        return dt.seconds % 60


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        einfahrten_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(einfahrten_canvas)
        self._einfahrten_ax = einfahrten_canvas.figure.subplots()

        ausfahrten_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(ausfahrten_canvas)
        self._ausfahrten_ax = ausfahrten_canvas.figure.subplots()

        # self._timer = ausfahrten_canvas.new_timer(10000)
        # self._timer.add_callback(self._update_plots)
        # self._timer.start()

        self._bars_ein = None
        self.client = PluginClient(name='test', autor='tester', version='0.0', text='einfahrtstabelle')
        self.query_sts()
        self._update_plots()

    def _update_plots(self):

        if self._bars_ein is not None:
            self._bars_ein.remove()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        kwargs['color'] = 'red'
        kwargs['edgecolor'] = 'black'
        kwargs['linewidth'] = 1

        x_labels_pos, x_labels, x_pos, y_bot, y_hgt, bar_labels = self.build_bars(self.client.wege_nach_typ[6])

        self._einfahrten_ax.set_title('ankuenfte')
        self._einfahrten_ax.set_xticks(x_labels_pos, x_labels)

        yfmt = lambda x, pos: "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
        self._einfahrten_ax.yaxis.set_major_formatter(yfmt)
        self._einfahrten_ax.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._einfahrten_ax.yaxis.set_major_locator(mpl.ticker.MultipleLocator(10))
        self._einfahrten_ax.yaxis.grid(True, which='major')
        ymin = min(y_bot)
        self._einfahrten_ax.set_ylim(bottom=ymin+60, top=ymin, auto=False)

        self._bars_ein = self._einfahrten_ax.bar(x_pos, y_hgt, width=0.8, bottom=y_bot, data=None, **kwargs)
        self._einfahrten_ax.bar_label(self._bars_ein, labels=bar_labels, label_type='center')

        # Trigger the canvas to update and redraw.
        self._einfahrten_ax.figure.canvas.draw()

    def build_bars(self, knoten_liste):
        x_labels = list()
        x_labels_pos = list()
        bars = list()

        for i_knoten, knoten in enumerate(knoten_liste):
            x_labels.append(knoten.name)
            x_labels_pos.append(i_knoten)
            for zug in knoten.zuege:
                try:
                    zeile = zug.fahrplan[0]
                    ankunft = minutes(zeile.an) + zug.verspaetung
                    aufenthalt = 1 # minutes(zeile.ab) - minutes(zeile.an)
                    bar = (zug.name, i_knoten, ankunft, aufenthalt)
                    bars.append(bar)
                except (AttributeError, IndexError):
                    pass

        x_pos = np.asarray([b[1] for b in bars])
        y_bot = np.asarray([b[2] for b in bars])
        y_hgt = np.asarray([b[3] for b in bars])
        bar_labels = [b[0] for b in bars]

        return x_labels_pos, x_labels, x_pos, y_bot, y_hgt, bar_labels

    async def get_sts_data(self):
        await self.client.connect()
        await self.client.request_anlageninfo()
        await self.client.request_bahnsteigliste()
        await self.client.request_wege()
        await self.client.request_zugliste()
        await self.client.request_zugdetails()
        await self.client.request_zugfahrplan()
        self.client.close()
        self.client.update_bahnsteig_zuege()
        self.client.update_wege_zuege()

        for knoten in self.client.wege_nach_typ[6]:
            print(knoten)
            for zug in knoten.zuege:
                try:
                    print(zug.name, zug.fahrplan[0].an, zug.verspaetung)
                except (AttributeError, IndexError):
                    pass
            print()
        for zug in self.client.zugliste:
            print(zug)
        print()

    def query_sts(self):
        asyncio.run(self.get_sts_data())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
