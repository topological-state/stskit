#!/env/python

"""
grafisches hauptprogramm

das charts programm ist ein starter für verschiedene grafische unterprogramme.
ausserdem unterhält es die kommunikation mit dem simulator und leitet ereignisse and die unterprogramme weiter.
"""

import argparse
import functools
import logging
import weakref
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import matplotlib.style
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSlot
import trio
import qtrio

from stsplugin import PluginClient, TaskDone
from zentrale import DatenZentrale
from bildfahrplan import BildFahrplanWindow
from gleisbelegung import GleisbelegungWindow
from gleisnetz import GleisnetzWindow
from qticker import TickerWindow
from fahrplan import FahrplanWindow

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
    logging.captureWarnings(enable)

    # special modules
    logging.getLogger('matplotlib').setLevel(max(numeric_level, logging.WARNING))
    logging.getLogger('PyQt5.uic.uiparser').setLevel(max(numeric_level, logging.WARNING))
    if not log_comm:
        logging.getLogger('stsplugin').setLevel(logging.WARNING)


class WindowManager:
    def __init__(self):
        self.windows: Dict[int, Any] = {}

    def add(self, window: Any):
        key = hash(window)
        self.windows[key] = window
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.destroyed.connect(functools.partial(self.on_window_destroyed, key))

    @pyqtSlot()
    def on_window_destroyed(self, key):
        try:
            del self.windows[key]
        except KeyError:
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.closed = trio.Event()

        self.config_path = Path.home() / r".stskit"
        self.config_path.mkdir(exist_ok=True)
        self.zentrale = DatenZentrale(config_path=self.config_path)

        try:
            p = Path(__file__).parent / r"mplstyle" / r"dark.mplstyle"
            matplotlib.style.use(p)
        except OSError:
            pass

        try:
            p = Path(__file__).parent / r"qt" / r"dark.css"
            ss = p.read_text(encoding="utf8")
            app = QtWidgets.QApplication.instance()
            app.setStyleSheet(ss)
        except OSError:
            pass

        self.windows = WindowManager()

        self.setWindowTitle("sts-charts")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        self.einfahrten_button = QtWidgets.QPushButton("einfahrten/ausfahrten", self)
        self.einfahrten_button.clicked.connect(self.einfahrten_clicked)
        layout.addWidget(self.einfahrten_button)

        self.gleisbelegung_button = QtWidgets.QPushButton("gleisbelegung", self)
        self.gleisbelegung_button.clicked.connect(self.gleisbelegung_clicked)
        layout.addWidget(self.gleisbelegung_button)

        self.bildfahrplan_button = QtWidgets.QPushButton("bildfahrplan", self)
        self.bildfahrplan_button.clicked.connect(self.bildfahrplan_clicked)
        layout.addWidget(self.bildfahrplan_button)
        self.bildfahrplan_button.setEnabled(True)

        self.fahrplan_button = QtWidgets.QPushButton("tabellenfahrplan", self)
        self.fahrplan_button.clicked.connect(self.fahrplan_clicked)
        layout.addWidget(self.fahrplan_button)
        self.fahrplan_button.setEnabled(True)

        self.netz_button = QtWidgets.QPushButton("gleisplan", self)
        self.netz_button.clicked.connect(self.netz_clicked)
        layout.addWidget(self.netz_button)
        self.netz_button.setEnabled(True)

        self.ticker_button = QtWidgets.QPushButton("ticker", self)
        self.ticker_button.clicked.connect(self.ticker_clicked)
        layout.addWidget(self.ticker_button)
        self.ticker_button.setEnabled(True)

        self.update_interval: int = 30  # seconds
        self.enable_update: bool = True

    def ticker_clicked(self):
        window = TickerWindow(self.zentrale)
        window.show()
        self.windows.add(window)

    def einfahrten_clicked(self):
        window = GleisbelegungWindow(self.zentrale)
        window.show_zufahrten = True
        window.show_bahnsteige = False
        window.setWindowTitle("Einfahrten/Ausfahrten")
        window.zeitfenster_voraus = 25
        window.planung_update()
        window.show()
        self.windows.add(window)

    def gleisbelegung_clicked(self):
        window = GleisbelegungWindow(self.zentrale)
        window.planung_update()
        window.show()
        self.windows.add(window)

    def netz_clicked(self):
        window = GleisnetzWindow(self.zentrale)
        window.anlage_update()
        window.show()
        self.windows.add(window)

    def fahrplan_clicked(self):
        window = FahrplanWindow(self.zentrale)
        window.planung_update()
        window.show()
        self.windows.add(window)

    def bildfahrplan_clicked(self):
        window = BildFahrplanWindow(self.zentrale)
        window.planung_update()
        window.show()
        self.windows.add(window)

    @pyqtSlot()
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close events and emit the ``closed`` signal."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.anlage.save_config(self.config_path)
            except (AttributeError, OSError):
                pass

            try:
                self.auswertung.fahrzeiten.report()
            except (AttributeError, OSError):
                pass

            self.enable_update = False
            self.closed.set()

    async def update_loop(self):
        await self.zentrale.client.registered.wait()
        while self.enable_update:
            try:
                await self.zentrale.update()
            except (trio.EndOfChannel, trio.BrokenResourceError, trio.ClosedResourceError):
                self.enable_update = False
                break
            except trio.BusyResourceError:
                pass

            await trio.sleep(self.update_interval)

    async def ereignis_loop(self):
        await self.zentrale.client.registered.wait()
        async for ereignis in self.zentrale.client._ereignis_channel_out:
            await self.zentrale.ereignis(ereignis)


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
    window.zentrale.client = client

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
