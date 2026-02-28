"""
Nachrichtenzentrale

Die Nachrichtenzentrale hält die Anlage- und Betriebsobjekte
und stellt die Schnittstelle zu den Benutzermodulen bereit.
Änderungen an den Betriebsdaten werden über Observer gemeldet.
"""

import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

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

    - anlage_update: Änderungen an der Anlagenkonfiguration, insbesondere an den Datenstrukturen
        signalgraph, bahnsteiggraph, bahnhofgraph, liniengraph,
        strecken, hauptstrecke, streckenmarkierung, gleissperrungen und zugschema.
        Benutzermodule müssen möglicherweise ihre Strukturen (Layout) neu aufbauen.
        Der Observer triggert beim ersten Einlesen der Simulatordaten,
        beim Laden und Bearbeiten der Konfiguration durch den Benutzer.

        Die Benachrichtigung wird in jedem Fall von einem plan_update gefolgt.
        Benutzermodule können also auch nur auf plan_update reagieren.
    - plan_update: Änderungen am Fahrplan durch den Simulator, insbesondere an den Datenstrukturen
        zuggraph, zielgraph, ereignisgraph.
        Benutzermodule müssen möglicherweise ihre Daten (Inhalt) aktualisieren.
        Der Observer triggert beim regelmässigen Einlesen der Simulatordaten.
    - betrieb_update: Änderungen am Betriebsablauf durch den Fdl, insbesondere an den Datenstrukturen
        zielgraph, ereignisgraph und fdl_korrekturen.
        Die Züge können geänderte Betriebshalte oder andere Verspätungen haben.
        Benutzermodule müssen möglicherweise ihre Daten (Inhalt) aktualisieren.
        Die meisten Benutzermodule reagieren auf plan_update und betrieb_update auf die gleiche Weise.
    - auswertung_update: Änderungen am Fahrplan, die für das Auswertungsmodul interessant sind.
        Das Auswertungsmodul wird möglicherweise in einer folgenden Version überarbeitet.
        Der Observer sollte in neuen Modulen nicht verwendet werden.
    - plugin_ereignis: Ereignismeldung vom Simulator.
        Für Benutzermodule, die zeitnah auf Ereignisse vom Simulator reagieren müssen.
        Der Observer triggert bei jedem Ereignis vom Simulator,
        was bei gewissen Ereignisarten mehrmals pro Sekunde sein kann.
        Die Verarbeitung darf daher keine lange Zeit in Anspruch nehmen,
        insbesondere sollten komplexe Grafikaktualisierungen vermieden werden.
        Diese sollten z.B. an die Qt-Mainloop oder an betrieb_update delegiert werden.
    """

    def __init__(self, config_path: Optional[os.PathLike] = None):
        self.simzeit_minuten: int = 0
        self.config_path: os.PathLike = config_path
        self.client: Optional[GraphClient] = None
        self.anlage: Optional[Anlage] = None
        self.betrieb: Optional[Betrieb] = None
        self.auswertung: Optional[Auswertung] = None
        self.plan_update = Observable(self)
        self.anlage_update = Observable(self)
        self._betrieb_update = Observable(self)
        self.auswertung_update = Observable(self)
        self.plugin_ereignis = Observable(self)

    @property
    def betrieb_update(self) -> Observable:
        if self.betrieb is not None:
            return self.betrieb.on_change
        else:
            return self._betrieb_update

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
        aenderungen = self.anlage.update(self.client, self.config_path)
        aenderungen -= {'zuggraph', 'zielgraph'}
        if aenderungen:
            self.anlage_update.trigger()

        if not self.betrieb:
            self.betrieb = Betrieb()
        self.betrieb.update(self.anlage, self.config_path)
        self.betrieb_update.trigger()
        self.plan_update.trigger()

        if not self.auswertung:
            self.auswertung = Auswertung(self.anlage)
        self.auswertung.zuege_uebernehmen(self.client.zugliste.values())
        self.auswertung_update.trigger()

    async def notify(self):
        if self.anlage_update.triggered:
            self.anlage_update.notify()
            self.plan_update.trigger()
        if self.plan_update.triggered:
            self.plan_update.notify()
        if self.betrieb_update.triggered:
            self.betrieb_update.notify()
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
        if self.betrieb:
            self.betrieb.sim_ereignis_uebernehmen(ereignis)
        if self.auswertung:
            self.auswertung.ereignis_uebernehmen(ereignis)

        self.plugin_ereignis.notify(ereignis=ereignis)

    def notify_anlage(self, aenderungen: Set[str]):
        self.anlage.aenderungen.update(aenderungen)
        self.anlage_update.trigger()
