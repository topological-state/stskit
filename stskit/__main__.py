#!/env/python

"""
STSdispo hauptprogramm

das hauptprogramm ist ein starter für die verschiedenen STSdispo-module.
es unterhält die kommunikation mit dem simulator und leitet ereignisse and die module weiter.
"""

import argparse
import functools
import logging
import os
import weakref
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import matplotlib.style
from PyQt5 import QtCore, QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSlot
import trio
import qtrio

from stskit.stsplugin import PluginClient, TaskDone, DEFAULT_HOST, DEFAULT_PORT
from stskit.zentrale import DatenZentrale
from stskit.anschlussmatrix import AnschlussmatrixWindow
from stskit.bildfahrplan import BildFahrplanWindow
from stskit.einstellungen import EinstellungenWindow
from stskit.gleisbelegung import GleisbelegungWindow
from stskit.gleisnetz import GleisnetzWindow
from stskit.qticker import TickerWindow
from stskit.fahrplan import FahrplanWindow

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
        logging.getLogger('stskit.stsplugin').setLevel(logging.WARNING)


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
    def __init__(self, config_path: Optional[os.PathLike] = None):
        super().__init__()
        self.closed = trio.Event()

        try:
            p = Path(config_path)
            if not p.is_dir():
                p = None
        except TypeError:
            p = None

        if p:
            self.config_path = p
        else:
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

        self.setWindowTitle("STSdispo")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        self.einfahrten_button = QtWidgets.QPushButton("Einfahrten/Ausfahrten", self)
        self.einfahrten_button.setEnabled(False)
        self.einfahrten_button.clicked.connect(self.einfahrten_clicked)
        layout.addWidget(self.einfahrten_button)

        self.gleisbelegung_button = QtWidgets.QPushButton("Gleisbelegung", self)
        self.gleisbelegung_button.setEnabled(False)
        self.gleisbelegung_button.clicked.connect(self.gleisbelegung_clicked)
        layout.addWidget(self.gleisbelegung_button)

        self.bildfahrplan_button = QtWidgets.QPushButton("Bildfahrplan", self)
        self.bildfahrplan_button.setEnabled(False)
        self.bildfahrplan_button.clicked.connect(self.bildfahrplan_clicked)
        layout.addWidget(self.bildfahrplan_button)

        self.matrix_button = QtWidgets.QPushButton("Anschlussmatrix", self)
        self.matrix_button.setEnabled(False)
        self.matrix_button.clicked.connect(self.matrix_clicked)
        layout.addWidget(self.matrix_button)

        self.fahrplan_button = QtWidgets.QPushButton("Tabellenfahrplan", self)
        self.fahrplan_button.setEnabled(False)
        self.fahrplan_button.clicked.connect(self.fahrplan_clicked)
        layout.addWidget(self.fahrplan_button)

        self.netz_button = QtWidgets.QPushButton("Gleisplan", self)
        self.netz_button.setEnabled(False)
        self.netz_button.clicked.connect(self.netz_clicked)
        layout.addWidget(self.netz_button)

        self.ticker_button = QtWidgets.QPushButton("Ticker", self)
        self.ticker_button.setEnabled(False)
        self.ticker_button.clicked.connect(self.ticker_clicked)
        layout.addWidget(self.ticker_button)

        self.einstellungen_button = QtWidgets.QPushButton("Einstellungen", self)
        self.einstellungen_button.setEnabled(False)
        self.einstellungen_button.clicked.connect(self.einstellungen_clicked)
        layout.addWidget(self.einstellungen_button)

        self.statusfeld = QtWidgets.QLineEdit("Initialisierung...")
        self.statusfeld.setReadOnly(True)
        layout.addWidget(self.statusfeld)

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
        window.vorlaufzeit = 25
        window.planung_update()
        window.show()
        self.windows.add(window)

    def gleisbelegung_clicked(self):
        window = GleisbelegungWindow(self.zentrale)
        window.planung_update()
        window.show()
        self.windows.add(window)

    def matrix_clicked(self):
        window = AnschlussmatrixWindow(self.zentrale)
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

    def einstellungen_clicked(self):
        window = EinstellungenWindow(self.zentrale)
        window.update()
        window.show()
        self.windows.add(window)

    @pyqtSlot()
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close events and emit the ``closed`` signal."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.zentrale.anlage.save_config(self.config_path)
                if logger.isEnabledFor(logging.DEBUG):
                    p = Path(self.config_path) / f"{self.zentrale.anlage.anlage.aid}.zielgraph.json"
                    self.zentrale.planung.zielgraph_speichern(p)
            except (AttributeError, OSError) as e:
                logger.error(e)

            try:
                self.auswertung.fahrzeiten.report()
            except (AttributeError, OSError) as e:
                logger.error(e)

            self.enable_update = False
            self.closed.set()

    async def update_loop(self):
        await self.zentrale.client.registered.wait()
        while self.enable_update:
            try:
                self.statusfeld.setText("Datenübertragung...")
                await self.zentrale.update()
            except (trio.EndOfChannel, trio.BrokenResourceError, trio.ClosedResourceError):
                self.enable_update = False
                break
            except trio.BusyResourceError:
                pass
            else:
                self.einfahrten_button.setEnabled(self.enable_update)
                self.gleisbelegung_button.setEnabled(self.enable_update)
                self.bildfahrplan_button.setEnabled(self.enable_update)
                self.matrix_button.setEnabled(self.enable_update)
                self.fahrplan_button.setEnabled(self.enable_update)
                self.netz_button.setEnabled(self.enable_update)
                self.ticker_button.setEnabled(self.enable_update)
                self.einstellungen_button.setEnabled(self.enable_update)

            self.statusfeld.setText("")
            await trio.sleep(self.update_interval)

        self.statusfeld.setText("Keine Verbindung")

    async def ereignis_loop(self):
        await self.zentrale.client.registered.wait()
        async for ereignis in self.zentrale.client._ereignis_channel_out:
            await self.zentrale.ereignis(ereignis)


def parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""
            STSdispo plugin for Stellwerksim (https://www.stellwerksim.de).
        """
    )

    default_config_path = Path.home() / r".stskit"

    parser.add_argument("--data-dir",
                        help=f"Daten- und Konfigurationsverzeichnis. Default: {default_config_path}")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Hostname oder IP-Adresse des Stellwerksim-Simulators. Default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Netzwerkport des Stellwerksim-Simulators. Default: {DEFAULT_PORT}")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="ERROR",
                        help="Minimale Stufe für Protokollmeldungen. Default: ERROR")
    parser.add_argument("--log-file", default="stskit.log",
                        help="Protokolldatei. Default: stskit.log im Arbeitsverzeichnis")
    parser.add_argument("--log-comm", action="store_true",
                        help="Ganze Kommunikation mit Server protokollieren. "
                             "log-level DEBUG muss dafür ausgewählt sein. default: aus")

    return parser.parse_args(arguments)


async def main_window():
    arguments = parse_args(QtWidgets.QApplication.instance().arguments())
    setup_logging(filename=arguments.log_file, level=arguments.log_level, log_comm=arguments.log_comm)

    window = MainWindow(arguments.data_dir)

    client = PluginClient(name='STSdispo', autor='bummler', version='0.8',
                          text='STSdispo: grafische fahrpläne, disposition und auswertung')

    await client.connect(host=arguments.host, port=arguments.port)
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


def main():
    qtrio.run(main_window)


if __name__ == "__main__":
    main()
