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

import outcome
from pathlib import Path
import signal
import sys
import traceback
from typing import Any, Dict, Optional, Sequence

import matplotlib.style
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt, QEvent, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMainWindow
import trio

from stskit.plugin.stsplugin import DEFAULT_HOST, DEFAULT_PORT
from stskit.plugin.stsgraph import GraphClient
from stskit.zentrale import DatenZentrale
from stskit.utils.observer import Observable
from stskit.widgets.anschlussmatrix import AnschlussmatrixWindow
from stskit.widgets.einstellungen import EinstellungenWindow
from stskit.widgets.gleisbelegung import GleisbelegungWindow
from stskit.widgets.gleisnetz import GleisnetzWindow
from stskit.widgets.qticker import TickerWindow
from stskit.widgets.fahrplan import FahrplanWindow
from stskit.widgets.rangierplan import RangierplanWindow
from stskit.widgets.bildfahrplan import BildFahrplanWindow

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
    logging.getLogger('PySide6.uic.uiparser').setLevel(max(numeric_level, logging.WARNING))
    if not log_comm:
        logging.getLogger('stskit.plugin.stsplugin').setLevel(logging.WARNING)


class StsDispoRunner(QObject):
    def __init__(self, arguments: argparse.Namespace, config_path: Optional[os.PathLike] = None):
        super().__init__()
        self.arguments = arguments
        self.config_path = config_path

        self.update_interval: int = 30  # seconds
        self.enable_update: bool = True
        self.notify_interval: int = 1
        self.enable_notify: bool = True
        self.status: str = ""
        self.status_update = Observable(self)

        self.client = GraphClient(name='STSdispo', autor='Matthias Muntwiler', version='2.0',
                                  text='STSdispo: Grafische Fahrpläne, Disposition und Auswertung')

        self.zentrale = DatenZentrale(config_path=self.config_path)
        self.zentrale.client = self.client

        self.coroutines = []
        self.done = False
        self.nursery = None

    async def start(self):
        await self.client.connect(host=self.arguments.host, port=self.arguments.port)

        async with self.client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(self.client.receiver)
                await self.client.register()
                await self.client.request_simzeit()
                await self.client.request_anlageninfo()
                nursery.start_soon(self.update_loop)
                nursery.start_soon(self.ereignis_loop)
                nursery.start_soon(self.notify_loop)

                self.done = True

    async def update_loop(self):
        await self.zentrale.client.registered.wait()
        while self.enable_update:
            try:
                self.status = "Datenübertragung..."
                self.status_update.trigger()
                self.status_update.notify()
                await self.zentrale.update()
            except (trio.EndOfChannel, trio.BrokenResourceError, trio.ClosedResourceError):
                self.enable_update = False
                break
            except trio.BusyResourceError:
                pass

            self.status = ""
            self.status_update.trigger()
            self.status_update.notify()
            await trio.sleep(self.update_interval)

        self.status = "Keine Verbindung"
        self.status_update.trigger()
        self.status_update.notify()

    async def ereignis_loop(self):
        await self.zentrale.client.registered.wait()
        async for ereignis in self.zentrale.client._ereignis_channel_out:
            await self.zentrale.ereignis(ereignis)

    async def notify_loop(self):
        await self.zentrale.client.registered.wait()
        while self.enable_notify:
            await self.zentrale.notify()
            await trio.sleep(self.notify_interval)


class WindowManager:
    def __init__(self):
        self.windows: Dict[int, Any] = {}

    def add(self, window: Any):
        key = hash(window)
        self.windows[key] = window
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.destroyed.connect(functools.partial(self.on_window_destroyed, key))

    @Slot()
    def on_window_destroyed(self, key):
        try:
            del self.windows[key]
        except KeyError:
            pass


class MainWindow(QMainWindow):
    def __init__(self, arguments: argparse.Namespace, config_path: Optional[os.PathLike] = None):
        super().__init__()

        self.arguments = arguments
        self.config_path = config_path
        self.runner: Optional[StsDispoRunner] = None
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

        self.bildfahrplan_button = QtWidgets.QPushButton("Streckenfahrplan", self)
        self.bildfahrplan_button.setEnabled(False)
        self.bildfahrplan_button.clicked.connect(self.bildfahrplan_clicked)
        layout.addWidget(self.bildfahrplan_button)

        self.matrix_button = QtWidgets.QPushButton("Anschlussmatrix", self)
        self.matrix_button.setEnabled(False)
        self.matrix_button.clicked.connect(self.matrix_clicked)
        layout.addWidget(self.matrix_button)

        self.fahrplan_button = QtWidgets.QPushButton("Zugfahrplan", self)
        self.fahrplan_button.setEnabled(False)
        self.fahrplan_button.clicked.connect(self.fahrplan_clicked)
        layout.addWidget(self.fahrplan_button)

        self.rangierplan_button = QtWidgets.QPushButton("Rangierplan", self)
        self.rangierplan_button.setEnabled(False)
        self.rangierplan_button.clicked.connect(self.rangierplan_clicked)
        layout.addWidget(self.rangierplan_button)

        self.netz_button = QtWidgets.QPushButton("Gleisplan (Geduld!)", self)
        self.netz_button.setEnabled(False)
        self.netz_button.clicked.connect(self.netz_clicked)
        layout.addWidget(self.netz_button)
        self.netz_button.setVisible(bool(self.arguments.netgraph))

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

    async def start_runner(self):
        self.runner = StsDispoRunner(self.arguments, self.config_path)
        self.runner.status_update.register(self.update_status)
        await self.runner.start()

    def update_status(self, *args, **kwargs):
        if self.runner is not None:
            self.statusfeld.setText(self.runner.status)
            enable = self.runner.enable_update
        else:
            self.statusfeld.setText("Keine Verbindung")
            enable = False

        self.einfahrten_button.setEnabled(enable)
        self.gleisbelegung_button.setEnabled(enable)
        self.bildfahrplan_button.setEnabled(enable)
        self.matrix_button.setEnabled(enable)
        self.fahrplan_button.setEnabled(enable)
        self.rangierplan_button.setEnabled(enable)
        self.netz_button.setEnabled(enable)
        self.ticker_button.setEnabled(enable)
        self.einstellungen_button.setEnabled(enable)

    # todo : window-initialisierungen in entsprechende module verschieben

    def ticker_clicked(self):
        window = TickerWindow(self.runner.zentrale)
        window.show()
        self.windows.add(window)

    def einfahrten_clicked(self):
        window = GleisbelegungWindow(self.runner.zentrale, "Agl")
        window.setWindowTitle("Einfahrten/Ausfahrten")
        window.vorlaufzeit = 25
        window.plan_update()
        window.show()
        self.windows.add(window)

    def gleisbelegung_clicked(self):
        window = GleisbelegungWindow(self.runner.zentrale, "Gl")
        window.plan_update()
        window.show()
        self.windows.add(window)

    def matrix_clicked(self):
        window = AnschlussmatrixWindow(self.runner.zentrale)
        window.plan_update()
        window.show()
        self.windows.add(window)

    def netz_clicked(self):
        window = GleisnetzWindow(self.runner.zentrale)
        window.anlage_update()
        window.show()
        self.windows.add(window)

    def fahrplan_clicked(self):
        window = FahrplanWindow(self.runner.zentrale)
        window.plan_update()
        window.show()
        self.windows.add(window)

    def rangierplan_clicked(self):
        window = RangierplanWindow(self.runner.zentrale)
        window.plan_update()
        window.show()
        self.windows.add(window)

    def bildfahrplan_clicked(self):
        window = BildFahrplanWindow(self.runner.zentrale)
        window.plan_update()
        window.show()
        self.windows.add(window)

    def einstellungen_clicked(self):
        window = EinstellungenWindow(self.runner.zentrale)
        window.update()
        window.show()
        self.windows.add(window)

    @Slot()
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close event and save configuration before closing."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.runner.zentrale.anlage.save_config(self.config_path)
            except (AttributeError, OSError) as e:
                logger.error(e)

            try:
                self.runner.zentrale.auswertung.fahrzeiten.report()
            except (AttributeError, OSError) as e:
                logger.error(e)

        QApplication.quit()


class AsyncHelper(QObject):
    """
    from https://doc.qt.io/qtforpython-6/examples/example_async_eratosthenes.html

    This is application-agnostic boilerplate.
    """

    class ReenterQtObject(QObject):
        """ This is a QObject to which an event will be posted, allowing
            Trio to resume when the event is handled. event.fn() is the
            next entry point of the Trio event loop. """
        def event(self, event):
            if event.type() == QEvent.Type.User + 1:
                event.fn()
                return True
            return False

    class ReenterQtEvent(QEvent):
        """ This is the QEvent that will be handled by the ReenterQtObject.
            self.fn is the next entry point of the Trio event loop. """
        def __init__(self, fn):
            super().__init__(QEvent.Type(QEvent.Type.User + 1))
            self.fn = fn

    def __init__(self, worker, entry):
        """
        Helper class to run the Trio event loop inside the Qt event loop.

        Parameters
        ----------

        `worker`: A QObject class that implements the trio event loop.
            If the worker has a `start_signal` attribute of type `Signal`,
            it will trigger a `launch_guest_run` when signalled.
        `entry`: A method of `worker` that calls the trio event loop.
        """

        super().__init__()
        self.reenter_qt = self.ReenterQtObject()
        self.entry = entry

        self.worker = worker
        if hasattr(self.worker, "start_signal") and isinstance(self.worker.start_signal, Signal):
            self.worker.start_signal.connect(self.launch_guest_run)

    @Slot()
    def launch_guest_run(self):
        """ To use Trio and Qt together, one must run the Trio event
            loop as a "guest" inside the Qt "host" event loop. """
        if not self.entry:
            raise Exception("No entry point for the Trio guest run was set.")
        trio.lowlevel.start_guest_run(
            self.entry,
            run_sync_soon_threadsafe=self.next_guest_run_schedule,
            done_callback=self.trio_done_callback,
        )

    def next_guest_run_schedule(self, fn):
        """ This function serves to re-schedule the guest (Trio) event
            loop inside the host (Qt) event loop. It is called by Trio
            at the end of an event loop run in order to relinquish back
            to Qt's event loop. By posting an event on the Qt event loop
            that contains Trio's next entry point, it ensures that Trio's
            event loop will be scheduled again by Qt. """
        QApplication.postEvent(self.reenter_qt, self.ReenterQtEvent(fn))

    def trio_done_callback(self, outcome_):
        """ This function is called by Trio when its event loop has
            finished. """
        if isinstance(outcome_, outcome.Error):
            error = outcome_.error
            traceback.print_exception(type(error), error, error.__traceback__)


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
    parser.add_argument("--netgraph", action="store_true",
                        help="Gleisnetzmodul anbieten. Das Gleisnetzmodul ist in Entwicklung und standardmässig verborgen.")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="ERROR",
                        help="Minimale Stufe für Protokollmeldungen. Default: ERROR")
    parser.add_argument("--log-file", default="stskit.log",
                        help="Protokolldatei. Default: stskit.log im Arbeitsverzeichnis")
    parser.add_argument("--log-comm", action="store_true",
                        help="Ganze Kommunikation mit Server protokollieren. "
                             "log-level DEBUG muss dafür ausgewählt sein. default: aus")

    return parser.parse_args(arguments)


def main():
    app = QApplication(sys.argv)
    arguments = parse_args(sys.argv[1:])
    setup_logging(filename=arguments.log_file, level=arguments.log_level, log_comm=arguments.log_comm)

    config_path = arguments.data_dir
    try:
        p = Path(config_path)
        if not p.is_dir():
            p = None
    except TypeError:
        p = None

    if p:
        config_path = p
    else:
        config_path = Path.home() / r".stskit"
        config_path.mkdir(exist_ok=True)

    try:
        p = Path(__file__).parent / r"mplstyle" / r"dark.mplstyle"
        matplotlib.style.use(p)
    except OSError:
        pass

    app.setStyle('Fusion')
    try:
        p = Path(__file__).parent / r"qt" / r"dark.css"
        ss = p.read_text(encoding="utf8")
        app.setStyleSheet(ss)
    except (AttributeError, OSError):
        pass

    main_window = MainWindow(arguments, config_path)
    async_helper = AsyncHelper(main_window, main_window.start_runner)
    QTimer.singleShot(0, async_helper.launch_guest_run)
    main_window.show()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.exec()


if __name__ == "__main__":
    main()
