"""
Nachrichtenzentrale

Die Nachrichtenzentrale hält die Anlage- und Betriebsobjekte
und stellt die Schnittstelle zu den Benutzermodulen bereit.
Änderungen an den Betriebsdaten werden über Observer gemeldet.
"""

import logging
import os
from typing import Optional

from stskit.utils.observer import Observable
from stskit.plugin.stsobj import Ereignis, time_to_minutes
from stskit.plugin.stsgraph import GraphClient
from stskit.dispo.anlage import Anlage
from stskit.dispo.betrieb import Betrieb
from stskit.dispo.auswertung import Auswertung

logger = logging.getLogger(__name__)


class DatenZentrale:
    """
    Zentrale Datenschnittstelle zum Simulator

    Die Datenzentrale ist unterteilt in:
    - Die Plugin-Schnittstelle hält die Daten vom Simulator bereit, s. Modul stsgraph.
      Die Benutzermodule dürfen nicht direkt auf diese Objekte zugreifen.
    - Die Anlage beschreibt das Stellwerk und die aktuellen Fahrplandaten, s. Modul dispo.anlage.
    - Der Betrieb verwaltet die Änderungen des Benutzers, s. Modul dispo.betrieb.
      Alle Anlagen- und Fahrplanänderungen müssen über diese Schnittstelle beantragt werden.
    - Die Auswertung wertet erfolgte Zugbewegungen aus, s. Modul auswertung.

    Die Klasse implementiert asynchrone Methoden, die die Plugin-Schnittstelle abfragen
    und Ereignisse vom Simulator weiterleiten.
    Die Kommunikationsschleifen müssen jedoch vom Besitzer unterhalten werden.

    Für die Benutzermodule stellt die Klasse Observer-Schnittstellen bereit.
    Benutzermodule registrieren sich bei den passenden Beobachtern und
    werden über die periodische Aktualisierung benachrichtigt.
    Folgende Observer stehen zur Verfügung:

    - anlage_update: Änderungen an der Anlage, die für das Anlagemodul interessant sind.
    - betrieb_update: Änderungen am Fahrplan, die für das Betriebsmodul interessant sind.
    - auswertung_update: Änderungen am Fahrplan, die für das Auswertungsmodul interessant sind.
    - planung_update: obsolet, wird in einer der nächsten Versionen entfernt.
    - plugin_ereignis: Ereignismeldung vom Simulator.
    """

    def __init__(self, config_path: Optional[os.PathLike] = None):
        self.simzeit_minuten: int = 0
        self.config_path: os.PathLike = config_path
        self.client: Optional[GraphClient] = None
        self.anlage: Optional[Anlage] = None
        self.betrieb: Optional[Betrieb] = None
        self.auswertung: Optional[Auswertung] = None
        self.planung_update = Observable(self)
        self.anlage_update = Observable(self)
        self.betrieb_update = Observable(self)
        self.auswertung_update = Observable(self)
        self.plugin_ereignis = Observable(self)

    async def update(self):
        """
        Aktuelle Daten von der Plugin-Schnittstelle abfragen.

        Die eigenen Objekte werden aktualisiert und die Observer aufgerufen.

        :return: None
        """

        await self._get_sts_data()
        for art in Ereignis.arten:
            await self.client.request_ereignis(art, self.client.zugliste.keys())

        self.simzeit_minuten = time_to_minutes(self.client.calc_simzeit())

        if not self.anlage:
            self.anlage = Anlage()
        self.anlage.update(self.client, self.config_path)
        self.anlage_update.trigger()

        if not self.betrieb:
            self.betrieb = Betrieb()
        self.betrieb.update(self.anlage, self.config_path)
        self.betrieb_update.trigger()
        self.planung_update.trigger()

        if not self.auswertung:
            self.auswertung = Auswertung(self.anlage)
        self.auswertung.zuege_uebernehmen(self.client.zugliste.values())
        self.auswertung_update.trigger()

    async def notify(self):
        if self.anlage_update.triggered:
            self.anlage_update.notify()
        if self.betrieb_update.triggered:
            self.betrieb_update.notify()
        if self.planung_update.triggered:
            self.planung_update.notify()
        if self.auswertung_update.triggered:
            self.auswertung_update.notify()

    async def _get_sts_data(self, alles=False):
        """
        Aktuelle Daten von der Plugin-Schnittstelle abfragen (Unterprozedur von update).

        Ruft den Pluginclient auf, um die Daten abzufragen.
        Die Anlageninformation inkl. Bahnsteige und Signalgraph werden standardmässig nur beim ersten Mal angefragt.

        :param alles: Bei False (default) wird die Anlageninformation nur angefragt,
            wenn die entsprechenden Objekte wie zu Beginn leer sind.
            Bei True wird die Anlageninformation unbedingt angefragt.
        :return: None
        """

        await self.client.request_simzeit()

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

    async def ereignis(self, ereignis):
        """
        Ereignisdaten übernehmen.

        :param ereignis:
        :return:
        """

        if self.anlage:
            self.anlage.sim_ereignis_uebernehmen(ereignis)
        if self.auswertung:
            self.auswertung.ereignis_uebernehmen(ereignis)

        self.plugin_ereignis.notify(ereignis=ereignis)

    def select_zugschema(self, zugschema_name: str):
        self.anlage.zugschema.load_config(zugschema_name, self.anlage.anlageninfo.region)
        self.anlage_update.trigger()
        self.planung_update.trigger()
