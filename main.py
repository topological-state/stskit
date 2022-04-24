#!/env/python

"""
grafisches hauptprogramm

das charts programm ist ein starter für verschiedene grafische unterprogramme.
ausserdem unterhält es die kommunikation mit dem simulator und leitet ereignisse and die unterprogramme weiter.
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PyQt5 import QtCore, QtWidgets, uic, QtGui
import trio
import qtrio

from stsplugin import PluginClient, TaskDone
from anlage import Anlage
from auswertung import StsAuswertung
from stsobj import Ereignis
from einausfahrten import EinfahrtenWindow, AusfahrtenWindow
from gleisbelegung import GleisbelegungWindow
from gleisnetz import GleisnetzWindow
from qticker import TickerWindow

logger = logging.getLogger(__name__)


def setup_logging(filename: Optional[str] = "", level: Optional[str] = "ERROR", log_comm: bool = False):
    """
    configure the logger. direct the logs either to a file or the null handler.

    this function must be called before the first logging command.
    to disable logging, call this function with empty filename (default).

    modules create their own loggers, by calling `logger = logging.getLogger(__name__)` at the top of the module code.
    messages are passed first to that logger by calls like `logger.debug(message)`.

    :param filename: (Path-like) path and name of the log file.
        if the filename is empty, logging is disabled.
    :param level: (string) principal log level.
        must be one of "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".
        if empty, logging is disabled.
        if not a valid level, defaults to "WARNING".
    :param log_comm: (bool) log all communications.
        normally, communications are not logged even at DEBUG level because it produces a lot of messages.
        level must be "DEBUG" for this parameter to have an effect.
    :return None
    """
    enable = bool(filename) and bool(level)
    if enable:
        numeric_level = getattr(logging, level.upper(), logging.WARNING)
    else:
        numeric_level = logging.ERROR

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    if enable:
        log_format = '%(asctime)s (%(name)s) %(levelname)s: %(message)s'
        formatter = logging.Formatter(log_format)

        handler = logging.FileHandler(filename, mode="w", delay=True)
        handler.setLevel(numeric_level)
        handler.setFormatter(formatter)
    else:
        handler = logging.NullHandler()

    root_logger.addHandler(handler)

    # special modules
    logging.getLogger('matplotlib').setLevel(max(numeric_level, logging.WARNING))
    if not log_comm:
        logging.getLogger('stsplugin').setLevel(logging.WARNING)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.closed = trio.Event()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.auswertung: Optional[StsAuswertung] = None

        self.config_path = Path.home() / r".stskit"
        self.config_path.mkdir(exist_ok=True)

        self.setWindowTitle("sts-charts")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        self.einfahrten_button = QtWidgets.QPushButton("einfahrten", self)
        self.einfahrten_button.clicked.connect(self.einfahrten_clicked)
        layout.addWidget(self.einfahrten_button)
        self.einfahrten_window: Optional[EinfahrtenWindow] = None

        self.ausfahrten_button = QtWidgets.QPushButton("ausfahrten", self)
        self.ausfahrten_button.clicked.connect(self.ausfahrten_clicked)
        layout.addWidget(self.ausfahrten_button)
        self.ausfahrten_window: Optional[AusfahrtenWindow] = None

        self.gleisbelegung_button = QtWidgets.QPushButton("gleisbelegung", self)
        self.gleisbelegung_button.clicked.connect(self.gleisbelegung_clicked)
        layout.addWidget(self.gleisbelegung_button)
        self.gleisbelegung_window: Optional[GleisbelegungWindow] = None

        self.ticker_button = QtWidgets.QPushButton("ticker", self)
        self.ticker_button.clicked.connect(self.ticker_clicked)
        layout.addWidget(self.ticker_button)
        self.ticker_window: Optional[QtWidgets.QWidget] = None
        self.ticker_button.setEnabled(True)

        self.netz_button = QtWidgets.QPushButton("gleisplan", self)
        self.netz_button.clicked.connect(self.netz_clicked)
        layout.addWidget(self.netz_button)
        self.netz_window: Optional[QtWidgets.QWidget] = None
        self.netz_button.setEnabled(True)

        self.update_interval: int = 30  # seconds
        self.enable_update: bool = True

    def ticker_clicked(self):
        if not self.ticker_window:
            self.ticker_window = TickerWindow()
        self.ticker_window.show()

    def einfahrten_clicked(self):
        if self.einfahrten_window is None:
            self.einfahrten_window = EinfahrtenWindow()
        if self.einfahrten_window.client is None:
            self.einfahrten_window.client = self.client
        if self.einfahrten_window.anlage is None:
            self.einfahrten_window.anlage = self.anlage
        if self.einfahrten_window.auswertung is None:
            self.einfahrten_window.auswertung = self.auswertung

        self.einfahrten_window.update()
        self.einfahrten_window.show()

    def ausfahrten_clicked(self):
        if self.ausfahrten_window is None:
            self.ausfahrten_window = AusfahrtenWindow()
        if self.ausfahrten_window.client is None:
            self.ausfahrten_window.client = self.client
        if self.ausfahrten_window.anlage is None:
            self.ausfahrten_window.anlage = self.anlage
        if self.ausfahrten_window.auswertung is None:
            self.ausfahrten_window.auswertung = self.auswertung

        self.ausfahrten_window.update()
        self.ausfahrten_window.show()

    def gleisbelegung_clicked(self):
        if self.gleisbelegung_window is None:
            self.gleisbelegung_window = GleisbelegungWindow()
        if self.gleisbelegung_window.client is None:
            self.gleisbelegung_window.client = self.client
        if self.gleisbelegung_window.anlage is None:
            self.gleisbelegung_window.anlage = self.anlage
        if self.gleisbelegung_window.auswertung is None:
            self.gleisbelegung_window.auswertung = self.auswertung

        self.gleisbelegung_window.update()
        self.gleisbelegung_window.show()

    def netz_clicked(self):
        if not self.netz_window:
            self.netz_window = GleisnetzWindow()
        if self.netz_window.client is None:
            self.netz_window.client = self.client
        if self.netz_window.anlage is None:
            self.netz_window.anlage = self.anlage
        if self.netz_window.auswertung is None:
            self.netz_window.auswertung = self.auswertung

        self.netz_window.update()
        self.netz_window.show()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close events and emit the ``closed`` signal."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.anlage.save_config(self.config_path)
            except (AttributeError, OSError):
                pass

            self.auswertung.fahrzeiten.report()

            self.enable_update = False
            self.closed.set()

    async def update_loop(self):
        await self.client.registered.wait()
        while self.enable_update:
            try:
                await self.update()
            except (trio.EndOfChannel, trio.BrokenResourceError, trio.ClosedResourceError):
                self.enable_update = False
                break
            except trio.BusyResourceError:
                pass
            else:
                if self.einfahrten_window is not None:
                    self.einfahrten_window.update()
                if self.ausfahrten_window is not None:
                    self.ausfahrten_window.update()
                if self.gleisbelegung_window is not None:
                    self.gleisbelegung_window.update()
                if self.netz_window is not None:
                    self.netz_window.update()

            await trio.sleep(self.update_interval)

    async def ereignis_loop(self):
        await self.client.registered.wait()
        async for ereignis in self.client._ereignis_channel_out:
            if self.auswertung:
                self.auswertung.ereignis_uebernehmen(ereignis)
            if self.ticker_window is not None:
                self.ticker_window.add_ereignis(ereignis)

    async def update(self):
        await self.get_sts_data()
        for art in Ereignis.arten:
            await self.client.request_ereignis(art, self.client.zugliste.keys())

        if not self.anlage:
            self.anlage = Anlage(self.client.anlageninfo)
        self.anlage.update(self.client, self.config_path)

        if self.auswertung:
            self.auswertung.zuege_uebernehmen(self.client.zugliste.values())
        else:
            self.auswertung = StsAuswertung(self.anlage)

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
        await self.client.resolve_zugflags()

        self.client.update_bahnsteig_zuege()
        self.client.update_wege_zuege()


def parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""
            charts plugin for stellwerksim (https://www.stellwerksim.de).
        """
    )

    # parser.add_argument("-d", "--data-dir")
    # parser.add_argument("-h", "--host")
    # parser.add_argument("-p", "--port")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="ERROR",
                        help="minimale stufe für protokoll-meldungen.")
    parser.add_argument("--log-file", default="stskit.log",
                        help="protokolldatei.")
    parser.add_argument("--log-comm", action="store_true",
                        help="ganze kommunikation mit server protokollieren. "
                             "log-level DEBUG muss dafür ausgewählt sein.")

    return parser.parse_args(arguments)


async def main():
    arguments = parse_args(QtWidgets.QApplication.instance().arguments())
    setup_logging(filename=arguments.log_file, level=arguments.log_level, log_comm=arguments.log_comm)

    window = MainWindow()

    client = PluginClient(name='sts-charts', autor='bummler', version='0.6',
                          text='sts-charts: grafische fahrpläne und gleisbelegungen')

    await client.connect()
    window.client = client

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                nursery.start_soon(window.update_loop)
                nursery.start_soon(window.ereignis_loop)
                window.show()
                await window.closed.wait()
                raise TaskDone()

    except KeyboardInterrupt:
        pass
    except TaskDone:
        pass


if __name__ == "__main__":
    qtrio.run(main)
