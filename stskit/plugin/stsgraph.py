import datetime

import trio
import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.plugin.stsobj import Knoten
from stskit.plugin.stsplugin import PluginClient, TaskDone
from stskit.model.signalgraph import SignalGraph
from stskit.model.bahnhofgraph import BahnsteigGraph
from stskit.model.zuggraph import ZugGraph
from stskit.model.zielgraph import ZielGraph

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GraphClient(PluginClient):
    """
    Erweiterter PluginClient mit Graphdarstellung der Basisdaten vom Simulator.

    Die Klasse unterhält folgende Graphen:

    Signalgraph
    ===========

    Der _Signalgraph_ enthält das Gleisbild aus der Wegeliste der Plugin-Schnittstelle mit sämtlichen Knoten und Kanten.
    Das 'typ'-Attribut wird auf den sts-Knotentyp (int) gesetzt.
    Kanten werden entsprechend der Nachbarrelationen aus der Wegeliste ('typ'-attribut 'gleis') gesetzt.
    Der Graph ist gerichtet, da die nachbarbeziehung i.a. nicht reziprok ist.
    Die Kante zeigt auf die Knoten, die als Nachbarn aufgeführt sind.
    Meist werden von der Schnittstelle jedoch Kanten in beide Richtungen angegeben,
    weshalb z.B. nicht herausgefunden werden kann, für welche Richtung ein Signal gilt.

    Der Graph sollte nicht verändert werden.
    Es wird nicht erwartet, dass sich der Graph im Laufe eines Spiels ändert.

    Die Signaldistanz wird am Anfang auf 1 gesetzt.

    Bahnsteiggraph
    ==============

    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.
    Kanten werden entsprechend der Nachbarrelationen gesetzt.
    Der Graph ist ungerichtet, da die Nachbarbeziehung als reziprok aufgefasst wird.

    Der Graph sollte nicht verändert werden.
    Es wird nicht erwartet, dass sich der Graph im Laufe eines Spiels ändert.

    Zuggraph
    ========

    Der _Zuggraph_ enthält alle Züge aus der Zugliste der Plugin-Schnittstelle als Knoten.
    Kanten werden aus den Ersatz-, Kuppeln- und Flügeln-Flags gebildet.

    Der Zuggraph verändert sich im Laufe eines Spiels.
    Neue Züge werden hinzugefügt.
    Ausgefahrene und ersetzte Züge werden beibehalten und als "ausgefahren" markiert.

    Zielgraph
    =========

    Der Zielgraph enthält die Zielpunkte aller Züge.
    Die Punkte sind gemäss Anordnung im Fahrplan
    sowie planmässigen Abhängigkeiten (Ersatz, Kuppeln, Flügeln) verbunden.

    Bei Ein- und Ausfahrten wird die Ankunfts- und Abfahrtszeit auf 1 Minute vor bzw. nach dem Halt geschätzt.

    Weitere Instanzattribute
    ========================

    bahnhofteile: Ordnet jedem Gleis einen Bahnhofteil zu.
        Der Bahnhofteil entspricht dem alphabetisch ersten Gleis in der Nachbarschaft.
        Der Dictionary wird durch _bahnhofteile_gruppieren gefüllt.
    """

    def __init__(self, name: str, autor: str, version: str, text: str):
        super().__init__(name, autor, version, text)

        self.signalgraph = SignalGraph()
        self.bahnsteiggraph = BahnsteigGraph()
        self.zuggraph = ZugGraph()
        self.zielgraph = ZielGraph()
        self.bahnhofteile: Dict[str, str] = {}
        self.anschlussgruppen: Dict[int, str] = {}

    async def request_bahnsteigliste(self):
        await super().request_bahnsteigliste()
        self._bahnsteiggraph_erstellen()
        self._bahnhofteile_gruppieren()

    async def request_wege(self):
        await super().request_wege()
        self._signalgraph_erstellen()
        self._anschluesse_gruppieren()

    async def request_zugliste(self):
        await super().request_zugliste()
        self._zuggraph_erstellen()

    async def request_zugdetails_einzeln(self, zid: int):
        result = await super().request_zugdetails_einzeln(zid)
        if result:
            self.zuggraph.zug_details_importieren(self.zugliste[zid])
        return result

    async def request_zugfahrplan_einzeln(self, zid: int) -> bool:
        result = await super().request_zugfahrplan_einzeln(zid)
        if result:
            self._zielgraph_update_zug(self.zugliste[zid])

        return result

    def _signalgraph_erstellen(self):
        """
        Signalgraph erstellen.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        :return: None
        """

        self.signalgraph.wege_importieren(self.wege.values())

    def _bahnsteiggraph_erstellen(self):
        """
        Bahnsteiggraph erstellen.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        :return: None
        """

        self.bahnsteiggraph.bahnsteige_importieren(self.bahnsteigliste.values())

    def _bahnhofteile_gruppieren(self):
        """
        Bahnhofteile nach Nachbarschaftsbeziehung gruppieren

        Diese Funktion erstellt das bahnhofteile Dictionary.
        """

        self.bahnhofteile = {}

        for comp in nx.connected_components(self.bahnsteiggraph.to_undirected(as_view=False)):
            hauptgleis = sorted(comp)[0]
            for gleis in comp:
                self.bahnhofteile[gleis] = hauptgleis

    def _anschluesse_gruppieren(self):
        for anschluss, data in self.signalgraph.nodes(data=True):
            if data['typ'] in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                self.anschlussgruppen[anschluss] = data['name']

    def _zuggraph_erstellen(self, clean=False):
        """
        Zuggraph erstellen bzw. aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Per Voreinstellung (clean=False),
        fügt diese Methode neue Knoten und ihre Kanten zum Graphen hinzu.
        Bestehende Knoten werden nicht verändert.
        Um den Graphen neu aufzubauen, sollte clean=True übergeben werden.

        Diese Methode markiert auch ausgefahrene Züge.

        :return: None
        """

        if clean:
            self.zuggraph.clear()

        self.zuggraph.reset_aenderungen()

        bisherige_zuege = {zid for zid, data in self.zuggraph.nodes(data=True) if not data.get('ausgefahren', True)}
        aktuelle_zuege = set(self.zugliste.keys())
        ausgefahrene_zuege = bisherige_zuege.difference(aktuelle_zuege)
        for zug in ausgefahrene_zuege:
            self.zuggraph.zug_ausfahren(zug)

        for zug in self.zugliste.values():
            self.zuggraph.zug_details_importieren(zug)

    def _zielgraph_erstellen(self, clean=False):
        """
        Ziel- und Zuggraphen erstellen bzw. aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Per Voreinstellung (clean=False),
        fügt diese Methode neue Knoten und ihre Kanten zum Graphen hinzu.
        Bestehende Knoten werden nicht verändert.
        Um den Graphen neu aufzubauen, sollte clean=True übergeben werden.

        :return: None
        """

        if clean:
            self.zielgraph.clear()

        for zug in self.zugliste.values():
            self._zielgraph_update_zug(zug)

    def _zielgraph_update_zug(self, zug):
        einfahrt = self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Einfahrt']].get(zug.von, None) or \
                   self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Ausfahrt']].get(zug.von, None)
        ausfahrt = self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Ausfahrt']].get(zug.nach, None) or \
                   self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Einfahrt']].get(zug.nach, None)
        links = self.zielgraph.zug_details_importieren(zug, einfahrt, ausfahrt, None)
        for link in links:
            self.zuggraph.zuege_verknuepfen(link[0], link[1], link[2])


async def test() -> GraphClient:
    """
    Testprogramm

    Das testprogramm fragt alle Daten einmalig vom Simulator ab.

    Der GraphClient bleibt bestehen, damit weitere Details aus den statischen Attributen ausgelesen werden können.
    Die Kommunikation mit dem Simulator wird jedoch geschlossen.

    :return: GraphClient-instanz
    """

    client = GraphClient(name='test', autor='tester', version='0.0', text='testing the graph client')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                await client.request_bahnsteigliste()
                await client.request_wege()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
                await client.resolve_zugflags()
                raise TaskDone()
    except TaskDone:
        pass

    return client


if __name__ == '__main__':
    trio.run(test)
