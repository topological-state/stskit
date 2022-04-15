#!/env/python

"""
grafisches hauptprogramm

das charts programm ist ein starter für verschiedene grafische unterprogramme.
ausserdem unterhält es die kommunikation mit dem simulator und leitet ereignisse and die unterprogramme weiter.
"""

import trio
import qtrio
from typing import Any, Dict, List, Optional, Set, Union

from PyQt5 import QtCore, QtWidgets, uic, QtGui

from stsplugin import PluginClient, TaskDone
from database import StsConfig
from auswertung import StsAuswertung
from stsobj import Ereignis
from einausfahrten import EinfahrtenWindow, AusfahrtenWindow
from gleisbelegung import GleisbelegungWindow
from gleisnetz import GleisnetzWindow
from qticker import TickerWindow


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.debug: bool = False
        self.closed = trio.Event()
        self.client: Optional[PluginClient] = None
        self.config: Optional[StsConfig] = None
        self.config_path = "charts.json"
        self.auswertung: Optional[StsAuswertung] = None

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

        self.enable_update = True

    def ticker_clicked(self):
        if not self.ticker_window:
            self.ticker_window = TickerWindow()
        self.ticker_window.show()

    def einfahrten_clicked(self):
        if self.einfahrten_window is None:
            self.einfahrten_window = EinfahrtenWindow()
        if self.einfahrten_window.client is None:
            self.einfahrten_window.client = self.client
        if self.einfahrten_window.config is None:
            self.einfahrten_window.config = self.config
        if self.einfahrten_window.auswertung is None:
            self.einfahrten_window.auswertung = self.auswertung

        self.einfahrten_window.update()
        self.einfahrten_window.show()

    def ausfahrten_clicked(self):
        if self.ausfahrten_window is None:
            self.ausfahrten_window = AusfahrtenWindow()
        if self.ausfahrten_window.client is None:
            self.ausfahrten_window.client = self.client
        if self.ausfahrten_window.config is None:
            self.ausfahrten_window.config = self.config
        if self.ausfahrten_window.auswertung is None:
            self.ausfahrten_window.auswertung = self.auswertung

        self.ausfahrten_window.update()
        self.ausfahrten_window.show()

    def gleisbelegung_clicked(self):
        if self.gleisbelegung_window is None:
            self.gleisbelegung_window = GleisbelegungWindow()
        if self.gleisbelegung_window.client is None:
            self.gleisbelegung_window.client = self.client
        if self.gleisbelegung_window.config is None:
            self.gleisbelegung_window.config = self.config
        if self.gleisbelegung_window.auswertung is None:
            self.gleisbelegung_window.auswertung = self.auswertung

        self.gleisbelegung_window.update()
        self.gleisbelegung_window.show()

    def netz_clicked(self):
        if not self.netz_window:
            self.netz_window = GleisnetzWindow()
        if self.netz_window.client is None:
            self.netz_window.client = self.client
        if self.netz_window.config is None:
            self.netz_window.config = self.config
        if self.netz_window.auswertung is None:
            self.netz_window.auswertung = self.auswertung

        self.netz_window.update()
        self.netz_window.show()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close events and emit the ``closed`` signal."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.config.save(self.config_path)
            except (AttributeError, OSError):
                pass

            self.auswertung.fahrzeiten.report()

            self.enable_update = False
            self.closed.set()

    async def update_loop(self):
        await self.client.registered.wait()
        while self.enable_update:
            await self.update()
            if self.einfahrten_window is not None:
                self.einfahrten_window.update()
            if self.ausfahrten_window is not None:
                self.ausfahrten_window.update()
            if self.gleisbelegung_window is not None:
                self.gleisbelegung_window.update()
            if self.netz_window is not None:
                self.netz_window.update()
            await trio.sleep(30)

    async def ereignis_loop(self):
        await self.client.registered.wait()
        async for ereignis in self.client._ereignis_channel_out:
            if self.debug:
                print(ereignis)
            if self.auswertung:
                self.auswertung.ereignis_uebernehmen(ereignis)
            if self.ticker_window is not None:
                self.ticker_window.add_ereignis(ereignis)

    async def update(self):
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


async def main():
    window = MainWindow()

    client = PluginClient(name='sts-charts', autor='bummler', version='0.5',
                          text='sts-charts: grafische fahrpläne und gleisbelegungen')
    await client.connect()
    window.client = client

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client._receiver)
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
