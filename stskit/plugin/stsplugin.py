"""
Stellwerksim Plugin-Client

Dieses Modul stellt eine PluginClient-Klasse zur Verfügung, die die Kommunikation mit dem Simulator übernimmt.
Der Client speichert auch alle Anlagen- und Fahrplandaten zwischen und verarbeitet Ereignisse.
Der PluginClient übersetzt Anfragen in xml und sendet sie an den Simulator.
Die xml-Antworten übersetzt er in Python-Objekte.

Asynchrone Kommunikation:

Die Kommunikation verläuft asynchron und ist nach der trio-Bibliothek modelliert.
Es gibt einen Socket-Stream für die xml-Kommunikation mit dem Simulator.
Die request-Methoden senden Anfragen via diesen Stream.
Antworten werden innerhalb der Receiver-Methode, die in einem eigenen trio-Task gestartet wird, verarbeitet
und als Python-Objekte in die Antworten- oder Ereignis-Queues gestellt.
Die request-Methoden holen die Antworten dort ab.
Für Ereignisse kann das Hauptprogramm einen separaten Task starten und die Queue auslesen.

Vorsicht ist bei der Verwendung von parallelen Tasks geboten,
damit sich zwei Serveranfragen nicht überschneiden können.
Am besten werden alle Anfragen im gleichen trio-Task gestellt.
In einem separaten Task wird die Ereignis-Queue abgefragt.

Beispiele für die Implementation zeigen das Testprogramm unten, oder weitere im Paket enthaltene Programme.

Logging:

stsplugin nutzt einen eigenen Logger mit dem namen "stsplugin" aus dem logging-Modul der Standardbibliothek.

tip:
    Auf Stufe DEBUG wird die gesamte Kommunikation mit dem Simulator ausgegeben!
    Wenn dies nicht gewünscht wird, der Rest des Programms aber auf DEBUG bleiben soll,
    kann die Stufe dieses Moduls individuell angepasst werden durch
    `logging.getLogger('stskit.interface.stsplugin').setLevel(logging.WARNING)`.
"""
import sys

from collections.abc import Iterable
import trio
import datetime
import html.entities
import logging
import re
from typing import Any, Callable
import untangle
import xml.sax

from stskit.plugin.stsobj import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 3691


def check_status(status: untangle.Element):
    if int(status.status['code']) >= 400:
        raise ValueError(f"error {status.status['code']}: {status.status.cdata}")


def log_status_warning(request: str, response: untangle.Element):
    if hasattr(response, 'status'):
        logger.warning(f"{request}: {response.status}")


class MyEntityResolver(untangle.Handler, xml.sax.handler.EntityResolver):
    def skippedEntity(self, name):
        print(f"skipped entity: {name}")

    def resolveEntity(self, publicId, systemId):
        print(f"resolve entity: {publicId}, {systemId}")
        return "test.dtd"


class PluginClient:
    """
    PluginClient - der Kern der Plugin-Schnittstelle

    Attrs:

        name: Name des Plugins. Wird beim Start im Sim angezeigt.
        autor: Autor des Plugins. Wird beim Start im Sim angezeigt.
        version: Version des Plugins. Wird beim Start im Sim angezeigt.
        text: Beschreibung des Plugins. Wird beim Start im Sim angezeigt.

        anlageninfo: AnlagenInfo vom Simulator. Wird durch request_anlageninfo abgefragt.

        bahnsteigliste: Liste von BahnsteigInfo-Objekten. Wird durch request_bahnsteigliste abgefragt.

        zugliste: List von ZugDetails-Objekten mit den Informationen zu den Zügen.
            Wird durch request_zugliste und request_zugdetails abgefragt.

        wege: Dict von Knoten-objekten repräsentiert den Wege-Graph.
            Der Dict ist nach Knoten.key aufgeschlüsselt.
            Dies ist für die meisten Element die enr.
            Für Bahnsteige und Haltepunkte ist es der Name.
            Vorsicht: Bahnsteige und Einfahrten/Ausfahrten können den gleichen Namen haben.
        wege_nach_enr: Wege-Graph nach enr-Nummern aufgeschlüsselt.
            Der Dict enthält die Knoten-Objekte, die eine enr-Nummer deklariert haben:
            Signale, Weichen, Einfahrten und Ausfahrten.
        wege_nach_namen: Wege-Graph nach knoten-Namen aufgeschlüsselt.
            Der Dict enthält die Knoten-Objekte, die einen Namen deklariert haben.
            Weil der Name nicht eindeutig ist
            (Anschlüsse und Bahnsteige haben z.B. in einigen Stellwerken den gleichen Namen),
            sind die Werte des Dicts Sets.
        wege_nach_typ: Wege-Graph nach Typnummer aufgeschlüsselt.
            Der Dict enthält Sets von Knoten-objekten.
        wege_verbindungen: Set von Zweiertuples Knoten.key mit den Verbindungen zwischen Knoten.
            Kann als Kantenliste für den Aufbau von Graphen verwendet werden.
            Achtung: Es kann Kanten geben, deren Endpunkt in `wege` keinen Knoten haben, s. `fehlende_wege_knoten`.

        fehlende_wege_knoten: Set von Wegeknoten, die in einer `wege_verbindungen` vorkommen,
            aber in `wege` nicht erfasst sind.
            Gewisse Rangiersignale aus Einfahrten (Beispiele S210, S289, S308, S218 in Bozen) haben keinen Knoten,
            d.h. wir können ihren Typ und Namen nicht ermitteln.
            Diese Signale fehlen dann auch im Signalgraph.
            Aktuell sollte dies aber kein Problem darstellen.
        fehlende_wege_kanten: Set von Verbindungen analog `wege_verbindungen`,
            von denen mindestens ein Endpunkt in `wege` nicht erfasst ist.
            Der entsprechende Endpunkt ist in `fehlende_wege_knoten` eingetragen.
            Die nicht aufgelösten Kanten sind trotzdem in `wege_verbindungen` enthalten.

    Usage:
        Siehe Beispielcode am Ende des Moduls (test-Funktion).
    """

    def __init__(self, name: str, autor: str, version: str, text: str):
        self._stream: trio.abc.Stream | None = None
        self._antwort_channel_in: trio.MemorySendChannel[untangle.Element] | None = None
        self._antwort_channel_out: trio.MemoryReceiveChannel[untangle.Element] | None = None
        self._ereignis_channel_in: trio.MemorySendChannel[Ereignis] | None = None
        self._ereignis_channel_out: trio.MemoryReceiveChannel[Ereignis] | None = None

        self.connected = trio.Event()
        self.registered = trio.Event()

        self.name: str = name
        self.autor: str = autor
        self.version: str = version
        self.text: str = text

        self.anlageninfo: AnlagenInfo | None = None
        self.bahnsteigliste: dict[str, BahnsteigInfo] = {}
        self.wege: dict[int | str, Knoten] = {}
        self.wege_nach_enr: dict[int, Knoten] = {}
        self.wege_nach_namen: dict[str, set[Knoten]] = {}
        self.wege_nach_typ: dict[int, set[Knoten]] = {}
        self.wege_nach_typ_namen: dict[int, dict[str, Knoten]] = {}
        self.wege_verbindungen: set[tuple[int | str, int | str]] = set()
        self.fehlende_wege_knoten: set[int | str] = set()
        self.fehlende_wege_kanten: set[tuple[int | str, int | str]] = set()
        self.zugliste: dict[int, ZugDetails] = {}
        self.zuggattungen: set[str] = set()

        self.registrierte_ereignisse: dict[str, set[int]] = {art: set() for art in Ereignis.arten}

        self.client_datetime: datetime.datetime = datetime.datetime.now()
        self.server_datetime: datetime.datetime = datetime.datetime.now()
        self.time_offset: datetime.timedelta = self.server_datetime - self.client_datetime

    @property
    def stream(self) -> trio.abc.Stream:
        """
        Asynchroner Kommunikationsstream zum Simulator
        """
        assert self._stream is not None
        return self._stream

    @property
    def antwort_channel_in(self) -> trio.abc.SendChannel[untangle.Element]:
        """
        Eingang asynchrone Warteschlange für Antworten vom Simulator

        Antworten vom Simulator werden während des Parsens als Element-Objekte an diese Warteschlange übergeben.
        """
        assert self._antwort_channel_in is not None
        return self._antwort_channel_in

    @property
    def antwort_channel_out(self) -> trio.abc.ReceiveChannel[untangle.Element]:
        """
        Ausgang asynchrone Warteschlange für Antworten vom Simulator

        Antworten vom Simulator können asynchron als Element-Objekte aus dieser Warteschlange entnommen und verarbeitet werden.
        """
        assert self._antwort_channel_out is not None
        return self._antwort_channel_out

    @property
    def ereignis_channel_in(self) -> trio.abc.SendChannel[Ereignis]:
        """
        Eingang asynchrone Warteschlange für Ereignismeldungen vom Simulator

        Ereignismeldungen vom Simulator werden während des Parsens als Ereignis-Objekte an diese Warteschlange übergeben.
        """
        assert self._ereignis_channel_in is not None
        return self._ereignis_channel_in

    @property
    def ereignis_channel_out(self) -> trio.abc.ReceiveChannel[Ereignis]:
        """
        Ausgang asynchrone Warteschlange für Ereignismeldungen vom Simulator

        Ereignismeldungen vom Simulator können asynchron als Ereignis-Objekte aus dieser Warteschlange entnommen und verarbeitet werden.
        """
        assert self._ereignis_channel_out is not None
        return self._ereignis_channel_out

    async def connect(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self._stream = await trio.open_tcp_stream(host, port)
        self.connected.set()

    async def close(self):
        await self.stream.aclose()
        self.connected = trio.Event()
        self.registered = trio.Event()

    async def _send_request(self,
                            tag: str,
                            **kwargs: str | int,
                            ) -> None:
        """
        Anfrage senden.

        Diese coroutine wartet ggf., bis der Sendepuffer wieder bereit ist.

        Args:
            tag: Name des xml-Tags
            kwargs: Attribute des xml-Tags
        """
        args = [f"{k}='{v}'" for k, v in kwargs.items()]
        args = " ".join(args)
        req = f"<{tag} {args} />"
        logger.debug("senden: " + req)
        req += "\n"
        data = req.encode()
        await self.stream.send_all(data)

    async def receiver(self, *, task_status=trio.TASK_STATUS_IGNORED):
        """
        Empfangsschleife: Antworten empfangen und verteilen

        Alle Antworten ausser Ereignisse werden in untangle.Element-Objekte gepackt
        und an die Antworten-Queue übergeben.
        Ereignisse werden als stskit.model.Ereignis-Objekte an die Ereignisse-Queue übergeben.

        Diese Coroutine muss explizit in einer trio.nursery gestartet werden
        und läuft, bis die Verbindung unterbrochen wird.
        """

        parser: Any = xml.sax.make_parser()
        handler = untangle.Handler()
        parser.setContentHandler(handler)
        ro = re.compile(r"&[a-z]+;")

        def resolve_char_ref(match) -> str:
            try:
                cp = html.entities.name2codepoint[match.group(0)[1:-1]]
                return f"&#{cp};"
            except (KeyError, IndexError):
                return "?"

        self._antwort_channel_in, self._antwort_channel_out = trio.open_memory_channel(0)
        self._ereignis_channel_in, self._ereignis_channel_out = trio.open_memory_channel(0)
        task_status.started()

        async with self.antwort_channel_in:
            async with self.ereignis_channel_in:
                async for bs in self.stream:
                    for s in bs.decode().split('\n'):
                        logger.debug("empfang: " + s)
                        if not s:
                            continue

                        s = re.sub(ro, resolve_char_ref, s)
                        try:
                            parser.feed(s)
                        except xml.sax.SAXException:
                            logger.exception("error parsing xml: " + s)

                        # xml tag complete?
                        if len(handler.elements) == 0:
                            element = handler.root
                            try:
                                parser.close()
                            except xml.sax.SAXParseException as e:
                                # rare parse exception: unclosed element
                                logger.exception(e)
                                logger.error(f"offending string: {s}")
                                print(e.getMessage(), file=sys.stderr)
                                continue

                            handler.root = untangle.Element(None, None)
                            handler.root.is_root = True

                            try:
                                tag = dir(element)[0]
                            except IndexError:
                                # leeres element
                                continue
                            else:
                                if tag == "ereignis":
                                    ereignis = Ereignis().update(getattr(element, tag))
                                    ereignis.zeit = self.calc_simzeit()
                                    await self.ereignis_channel_in.send(ereignis)
                                else:
                                    await self.antwort_channel_in.send(element)

    async def register(self) -> None:
        """
        Klient beim Simulator registrieren.

        Diese Funktion muss als erste nach dem Verbinden aufgerufen werden,
        da sie auch die Statusantwort nach der Verbindungsaufnahme auswertet.
        """
        status = await self.antwort_channel_out.receive()
        check_status(status)

        await self._send_request("register", name=self.name, autor=self.autor, version=self.version,
                                 protokoll='1', text=self.text)
        status = await self.antwort_channel_out.receive()
        check_status(status)
        self.registered.set()

    async def request_anlageninfo(self) -> None:
        """
        Anlageninfo anfordern.

        Die antwort wird im anlageninfo-Attribut gespeichert.
        """
        await self._send_request(AnlagenInfo.tag)
        response = await self.antwort_channel_out.receive()
        self.anlageninfo = AnlagenInfo().update(response.anlageninfo)

    async def request_bahnsteigliste(self) -> None:
        """
        Bahnsteigliste anfordern.

        Die Liste wird im Attribut `bahnsteigliste` gespeichert.
        Die Methode löst auch die `nachbarn` der Bahnsteige auf.
        """

        self.bahnsteigliste = {}
        await self._send_request("bahnsteigliste")
        response = await self.antwort_channel_out.receive()
        for bahnsteig in response.bahnsteigliste.bahnsteig:
            bi = BahnsteigInfo().update(bahnsteig)
            self.bahnsteigliste[bi.name] = bi

        for bahnsteig in self.bahnsteigliste.values():
            for name in bahnsteig.nachbarn_namen:
                try:
                    bahnsteig.nachbarn[name] = self.bahnsteigliste[name]
                except KeyError:
                    logger.warning(f"Nachbarbahnsteig {name} zu {bahnsteig.name} nicht in der Bahnsteigliste.")

    async def request_simzeit(self) -> datetime.datetime:
        """
        Simulatorzeit anfragen.

        Die funktion fragt die aktuelle Simulatorzeit an und liefert sie in einem `datetime.time`-Objekt.

        Basierend auf der antwort setzt sie ausserdem `client_datetime`, `server_datetime` und `time_offset`.
        Diese attribute können benutzt werden, um die Simulatorzeit zu berechnen (`calc_simzeit`-Funktion),
        ohne dass eine erneute Anfrage geschickt werden muss.

        Info:
            `client_datetime` und `server_datetime` enthalten das aktuelle Datum.
            Das ist nötig, um den `time_offset` als `timedelta` zu berechnen.
            Da der Simulator kein Datum kennt, sollten die Datumsfelder nicht beachtet werden.
            Die `datetime.datetime.time`-Methode ist ein schneller Weg, ein `datetime.time`-Objekt zu erhalten.

        Returns:
            Aktuelle Simulatorzeit
        """
        self.client_datetime = datetime.datetime.now()
        await self._send_request("simzeit", sender=0)
        simzeit = await self.antwort_channel_out.receive()
        secs, msecs = divmod(int(simzeit.simzeit['zeit']), 1000)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        t = datetime.time(hour=hrs, minute=mins, second=secs, microsecond=msecs * 1000)
        self.server_datetime = datetime.datetime.combine(self.client_datetime, t)
        self.time_offset = (self.server_datetime - self.client_datetime)
        return self.server_datetime

    def calc_simzeit(self) -> datetime.datetime:
        """
        Simulatorzeit ohne Serverabfrage abschätzen.

        Der `time_offset` muss vorher einmal mittels `request_simzeit` kalibriert worden sein.

        Der Rückgabewert enthält das aktuelle (Client-)Datum.
        Das ist nötig, damit mit der Uhrzeit gerechnet werden kann.
        Da der Simulator kein Datum kennt, sollten die Datumsfelder nach der Rechnung nicht beachtet werden.
        Der Fahrplan (in `FahrplanZeile`) enthält lediglich `datetime.time`-Objekte.
        Ein `datetime.time`-Objekt kann einfach über die `time`-Methode extrahiert werden.

        Returns:
            Extrapolierte Simulatorzeit
        """
        return datetime.datetime.now() + self.time_offset

    async def request_wege(self) -> None:
        """
        Wege-Graph anfragen

        Der Wege-Graph enthält die Elemente des Gleisbilds und ihre Verbindungen.
        Im PluginClient wird er als Dict von Knoten-Objekten dargestellt,
        die über ihre Nachbarn-attribute verlinkt sind.
        Für eine Darstellung mittels networkx-Graphen, siehe stsgraph.GraphClient.

        Da der Simulator für die Elemente zwei verschiedene Schlüssel (enr und name) verwendet,
        ist der Schlüssel des Wege-Dict zweiteilig und enthält den Elementtyp und
        - je nach Typ - entweder die enr oder den Namen.

        Die Methode aktualisiert folgende Attribute:
        wege, wege_nach_enr, wege_nach_namen, wege_nach_typ, wege_verbindungen,
        fehlende_wege_knoten, fehlende_wege_kanten.

        Teilweise fehlen wichtige Gleisverbindungen in dem Graphen, z.B. von Anschlüssen ans Gleisnetz.

        Rangiersignale aus Einfahrten (Beispiele S210, S289, S308, S218 in Bozen) haben keinen Knoten,
        werden aber in Kanten referenziert.
        Wir geben in diesem Fall eine Info-Meldung 'Nicht auflösbare Elementreferenz' ins Log
        und schreiben die Verbindung und Referenz in die fehlende_wege_knoten- und fehlende_wege_kanten-Listen.
        """

        await self._send_request("wege")
        response = await self.antwort_channel_out.receive()
        self.wege = {}
        self.wege_nach_enr = {}
        self.wege_nach_namen = {}
        self.wege_nach_typ = {typ: set([]) for typ in Knoten.TYP_NAME}
        self.wege_nach_typ_namen = {typ: {} for typ in Knoten.TYP_NAME}
        self.fehlende_wege_knoten = set()
        self.fehlende_wege_kanten = set()

        for shape in response.wege.shape:
            knoten = Knoten().update(shape)
            if knoten.key:
                self.wege[knoten.key] = knoten
            if knoten.enr:
                self.wege_nach_enr[knoten.enr] = knoten
            if knoten.name:
                try:
                    self.wege_nach_namen[knoten.name].add(knoten)
                except KeyError:
                    self.wege_nach_namen[knoten.name] = {knoten}
            if knoten.typ:
                try:
                    self.wege_nach_typ[knoten.typ].add(knoten)
                except KeyError:
                    self.wege_nach_typ[knoten.typ] = {knoten}
                try:
                    self.wege_nach_typ_namen[knoten.typ][knoten.name] = knoten
                except KeyError:
                    pass

        for connector in response.wege.connector:
            try:
                key1 = int(connector['enr1'])
            except (KeyError, TypeError):
                try:
                    key1 = str(connector['name1']).strip()
                except KeyError:
                    logger.warning(f"Fehlerhafte Elementreferenz zu Knoten 1 von {connector}")
                    continue

            try:
                key2 = int(connector['enr2'])
            except (KeyError, TypeError):
                try:
                    key2 = str(connector['name2']).strip()
                except KeyError:
                    logger.warning(f"Fehlerhafte Elementreferenz zu Knoten 2 von {connector}")
                    continue

            try:
                knoten1 = self.wege[key1]
            except KeyError:
                logger.info(f"Nicht auflösbare Elementreferenz zu Knoten 1 von {connector}")
                self.fehlende_wege_knoten.add(key1)
                self.fehlende_wege_kanten.add((key1, key2))
                knoten1 = None

            try:
                knoten2 = self.wege[key2]
            except KeyError:
                logger.info(f"Nicht auflösbare Elementreferenz zu Knoten 2 von {connector}")
                self.fehlende_wege_knoten.add(key2)
                self.fehlende_wege_kanten.add((key1, key2))
                knoten2 = None

            if key1 and key2:
                self.wege_verbindungen.add((key1, key2))

            if knoten1 is not None and knoten2 is not None:
                knoten1.nachbarn[knoten2.key] = knoten2
                knoten2.nachbarn[knoten1.key] = knoten1

        logger.info(f"Wege: Fehlende Knoten {self.fehlende_wege_knoten}")
        logger.info(f"Wege: Fehlende Kanten {self.fehlende_wege_kanten}")

    async def request_zugdetails(self, zid: int | Iterable[int] | None = None) -> None:
        """
        ZugDetails eines, mehrerer oder aller Züge anfragen.

        Wenn ein ZugDetails-Objekt mit der zid bereits in der Zugliste angelegt ist,
        wird es aktualisiert, andernfalls neu angelegt.
        Wenn ein Fehler auftritt (weil z.B. der Zug nicht mehr im Stellwerk ist),
        wird der Zug aus der Zugliste gelöscht.

        Args:
            zid: Einzelne Zug-ID, Iterable von Zug-IDs, oder None (alle in der Zugliste).
        """

        if zid is not None:
            if isinstance(zid, Iterable):
                zids = list(iter(zid))
            else:
                zids = [int(zid)]
        else:
            zids = list(self.zugliste.keys())

        for zid in sorted(map(int, zids)):
            await self.request_zugdetails_einzeln(zid)

    async def request_zugdetails_einzeln(self, zid: int) -> bool:
        """
        ZugDetails eines einzelnen Zuges anfragen.

        Wenn ein ZugDetails-Objekt mit der angegebenen zid bereits in der Zugliste angelegt ist,
        wird es aktualisiert, andernfalls neu angelegt.
        Wenn ein Fehler auftritt (weil z.B. der Zug nicht mehr im Stellwerk ist),
        wird der Zug aus der Zugliste gelöscht.

        Args:
            zid: einzelne zug-id.

        Returns:
            True (Erfolg) oder False (Fehler, Zug entfernt)
        """

        await self._send_request("zugdetails", zid=zid)
        response = await self.antwort_channel_out.receive()

        try:
            zug = self.zugliste[zid]
        except KeyError:
            zug = ZugDetails()
            zug.zid = zid
            self.zugliste[zid] = zug

        try:
            zug.update(response.zugdetails)
            logger.debug(f"request_zugdetails: {zug}")
        except AttributeError:
            del self.zugliste[zid]
            log_status_warning("request_zugdetails", response)
            return False
        else:
            self.zuggattungen.add(zug.gattung)

        return True

    async def request_ereignis(self, art: str, zids: Iterable[int]) -> None:
        """
        Ereignismeldung anfordern

        Nach Nummernwechsel muss man Ereignismeldungen neu anfordern.
        Ausser für "Einfahrt" schicken wir daher Anforderungen nur, wenn der Zug sichtbar ist.

        Anforderungen werden in `registrierte_ereignisse` notiert,
        damit sie nicht wiederholt gesendet werden.

        Args:
            art: art des ereignisses, cf. model.Ereignis.arten
            zids: menge oder sequenz von zug-id-nummern
        """
        zids = set(zids).difference(self.registrierte_ereignisse[art])
        for zid in zids:
            if zid in self.zugliste and (art == "einfahrt" or self.zugliste[zid].sichtbar):
                await self._send_request("ereignis", art=art, zid=zid)
                self.registrierte_ereignisse[art].add(zid)

    async def request_zugfahrplan(self, zid: int | Iterable[int] | None = None):
        """
        Fahrplan eines, mehrerer oder aller Züge anfragen.

        Das ZugDetails-Objekt muss in der Zugliste bereits existieren.

        Abgefahrene Wegpunkte sind im Fahrplan nicht mehr vorhanden.

        Args:
            zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        """

        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in sorted(map(int, zids)):
            if zid in self.zugliste:
                await self.request_zugfahrplan_einzeln(zid)

    async def request_zugfahrplan_einzeln(self, zid: int) -> bool:
        """
        Fahrplan eines Zuges anfragen.

        Das ZugDetails-Objekt muss in der Zugliste bereits existieren.
        Der Fahrplan wird bei der ersten Anfrage komplett übernommen.
        Bei den folgenden Anfragen, wird nur die aktuelle Gleisänderung übernommen,
        die anderen Attribute bleiben unverändert (s. Bemerkung unten).

        Die Methode aktualisiert auch den `ziel_index` des Zuges.

        Abgefahrene Wegpunkte (ausser dem letzten) sind in der Antwort vom Simulator nicht mehr vorhanden.
        Wir behalten jedoch den Fahrplan im ZugDetails bei, so wie er bei der ersten Aufruf zurückgegeben wurde.
        Lediglich die Gleisänderung wird aktualisiert.

        Der Fahrplan vom Simulator enthält den letzten Wegpunkt auch, nachdem er passiert wurde.
        Der Eintrag kann dann aber fehlerhafte Werte enthalten (Dezember 2024).
        Z.B. kann das Flags-Attribut Fall leer sein, wenn es vorher eine Durchfahrt angezeigt hat.

        Ersatzloks haben im XML keine Plangleis- und Gleisangabe.
        Wir übernehmen beim ersten Auftreten den ersten Fahrplaneintrag.

        Args:
            zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).

        Returns:
            True (Erfolg) oder False (Fehler)
        """

        zug = self.zugliste[zid]
        akt_ziel_index = None

        await self._send_request("zugfahrplan", zid=zid)
        response = await self.antwort_channel_out.receive()

        try:
            neuer_fahrplan = []
            for gleis in response.zugfahrplan.gleis:
                zeile = FahrplanZeile(zug).update(gleis)
                neuer_fahrplan.append(zeile)
                if zug.plangleis == zeile.plan:
                    akt_ziel_index = len(neuer_fahrplan) - 1
                logger.debug(f"request_zugfahrplan: {zeile}")
        except AttributeError:
            log_status_warning("request_zugfahrplan", response)
            return False

        if zid < 0 and not zug.plangleis:
            # ersatzlok
            try:
                zug.plangleis = neuer_fahrplan[0].plan
                zug.gleis = neuer_fahrplan[0].gleis
                akt_ziel_index = 0
            except IndexError:
                pass

        if not zug.fahrplan:
            zug.fahrplan = neuer_fahrplan
            zug.ziel_index = akt_ziel_index
            return True

        for zeile_alt, zeile_neu in zip(reversed(zug.fahrplan), reversed(neuer_fahrplan)):
            if zeile_neu.plan == zeile_alt.plan:
                zeile_alt.gleis = zeile_neu.gleis
            else:
                logger.warning(f"ersetze fahrplan von {zug}, weil {zeile_alt.plan} ungleich {zeile_neu.plan}")
                zug.fahrplan = neuer_fahrplan
                zug.ziel_index = akt_ziel_index
                break
        else:
            if akt_ziel_index is not None:
                zug.ziel_index = akt_ziel_index + len(zug.fahrplan) - len(neuer_fahrplan)
            else:
                zug.ziel_index = None

        return True

    async def request_zugliste(self):
        """
        Zugliste anfragen.

        Die Zugliste wird angefragt und aktualisiert.

        Die vom Simulator gelieferte Zugliste enthält nicht alle Folgezüge.

        Ausgefahrene Züge werden von der Liste entfernt.
        Für ersetzte Züge wird ein ersatz-Ereignis erzeugt.

        Die Zugobjekte sind nach dieser Abfrage schon ziemlich komplett.
        Es fehlen die aktuelle Verspätung (request_zugdetails)
        und Gleisänderungen im Fahrplan (request_zugfahrplan).

        Die Objektinstanzen werden bei Aktualisierung beibehalten.

        Ersatzloks haben eine negative ID.
        """

        alte_zugliste = set(self.zugliste.keys())
        aktuelle_zugliste = set()
        zeit = self.calc_simzeit()

        await self._send_request("zugliste")
        response = await self.antwort_channel_out.receive()

        try:
            for zug in response.zugliste.zug:
                try:
                    zid = int(zug['zid'])
                    if zid in self.zugliste:
                        self.zugliste[zid].update(zug)
                    else:
                        self.zugliste[zid] = ZugDetails().update(zug)
                    aktuelle_zugliste.add(zid)
                except (KeyError, ValueError):
                    logger.error(f"request_zugliste: fehlerhafter zug-eintrag: {zug}")
        except AttributeError:
            log_status_warning("request_zugliste", response)

        # ausgefahrene und ersetzte züge
        for zid in alte_zugliste - aktuelle_zugliste:
            zug = self.zugliste[zid]
            try:
                letztes_ziel = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if 'E' in letztes_ziel.flags:
                    attr = dict(zug.__dict__)
                    attr['art'] = "ersatz"
                    ereignis = Ereignis().update(attr)
                    ereignis.zeit = zeit
                    ereignis.sichtbar = False
                    await self.ereignis_channel_in.send(ereignis)
            try:
                del self.zugliste[zid]
            except KeyError:
                pass

    async def request_zug(self, zid: int) -> ZugDetails | None:
        """
        Einzelnen Zug und Fahrplan anfragen.

        Der Zug wird in die Zugliste eingetragen bzw. aktualisiert und als `ZugDetails`-Objekt zurückgegeben.

        Args:
            zid: einzelne zug-id

        Returns:
            `ZugDetails` inkl. Fahrplan.
            None, wenn der Zug nicht verzeichnet ist.
        """
        zid = int(zid)
        if zid:
            await self.request_zugdetails(zid)
            await self.request_zugfahrplan(zid)
        else:
            return None

        try:
            zug = self.zugliste[zid]
            return zug
        except KeyError:
            return None

    async def resolve_zugflags(self, zid: int | Iterable[int] | None = None) -> None:
        """
        Folgezüge aus den Zugflags auflösen.

        Da `request_zugliste` die Folgezüge (Ersatz-, Flügel- und Kuppelzüge) nicht automatisch erhält,
        lesen wir diese aus den Zugflags aus und fragen ihre Details und Fahrpläne explizit an.
        Die Funktion arbeitet iterativ, bis alle Folgezüge aufgelöst sind.
        Die Züge werden in die Zugliste eingetragen und im Stammzug referenziert.

        Info:
            zids sind nicht geordnet. Ersatzzüge können eine tiefere zid als der Stammzug haben.

        Args:
            zid: Einzelne Zug-ID, Iterable von Zug-IDs, oder None (alle in der Liste).
        """
        if zid is not None:
            zids = [int(zid)]
        else:
            zids = list(self.zugliste.keys())

        erledigte_zids = []
        while zids:
            zid = zids.pop(0)
            if zid in erledigte_zids:
                continue  # unendliche rekursion verhindern
            else:
                erledigte_zids.append(zid)

            try:
                zug = self.zugliste[zid]
            except KeyError:
                continue

            for planzeile in zug.fahrplan:
                if zid2 := planzeile.ersatz_zid():
                    logger.info(f"zid {zid2} als ersatz für {zid} anfragen")
                    zug2 = await self.request_zug(zid2)
                    if zug2 is not None:
                        planzeile.ersatzzug = zug2
                        zug2.stamm_zids.add(zug.zid)
                        zug2.verspaetung = zug.verspaetung
                        zids.append(zid2)
                    else:
                        logger.warning(f"keine antwort für zug {zid2}")
                if zid2 := planzeile.fluegel_zid():
                    logger.info(f"zid {zid2} als flügel für {zid} anfragen")
                    zug2 = await self.request_zug(zid2)
                    if zug2 is not None:
                        planzeile.fluegelzug = zug2
                        zug2.stamm_zids.add(zug.zid)
                        zug2.verspaetung = zug.verspaetung
                        zids.append(zid2)
                    else:
                        logger.warning(f"keine antwort für zug {zid2}")
                if zid2 := planzeile.kuppel_zid():
                    logger.info(f"zid {zid2} als kuppel für {zid} anfragen")
                    zug2 = await self.request_zug(zid2)
                    if zug2 is not None:
                        planzeile.kuppelzug = zug2
                        zug2.stamm_zids.add(zug.zid)
                        zids.append(zid2)
                    else:
                        logger.warning(f"keine antwort für zug {zid2}")

    def update_bahnsteig_zuege(self):
        """
        Züge in Bahnsteigliste eintragen.

        Im `zuege`-attribut der Bahnsteige werden die an den Bahnsteig disponierten Züge aufgelistet.
        `zuege` ist ein Dictionary und bildet zid auf ZugDetails ab.
        Die ZugDetails sind weak References.
        """

        for bahnsteig in self.bahnsteigliste.values():
            bahnsteig.zuege.clear()

        for zid in self.zugliste.keys():
            zug = self.zugliste[zid]
            for fahrplanzeile in zug.fahrplan:
                try:
                    bahnsteig = self.bahnsteigliste[fahrplanzeile.gleis]
                except KeyError:
                    pass
                else:
                    bahnsteig.zuege[zid] = zug

    def update_wege_zuege(self):
        """
        Züge in Wegelisten eintragen.

        Im Züge-Attribut der Wege und Knoten (Einfahrten, Ausfahrten, Haltepunkte)
        werden die fahrplanmässig daran vorbei kommenden Züge aufgelistet.
        """
        for knoten in self.wege.values():
            knoten.zuege.clear()

        einfahrten = {knoten.name: knoten for knoten in self.wege_nach_typ[6]}
        ausfahrten = {knoten.name: knoten for knoten in self.wege_nach_typ[7]}
        bahnsteige = {knoten.name: knoten for knoten in self.wege_nach_typ[5]}
        haltepunkte = {knoten.name: knoten for knoten in self.wege_nach_typ[12]}
        haltepunkte.update(bahnsteige)

        for zid in self.zugliste.keys():
            zug = self.zugliste[zid]

            try:
                einfahrten[zug.von].zuege[zid] = zug
            except KeyError:
                pass
            try:
                ausfahrten[zug.nach].zuege[zid] = zug
            except KeyError:
                pass
            for fahrplanzeile in zug.fahrplan:
                try:
                    haltepunkte[fahrplanzeile.gleis].zuege[zid] = zug
                except KeyError:
                    pass


def zugsortierschluessel(gleis: str, attr: str, default: datetime.time) -> Callable:
    """
    Sortierschlüssel-Funktion für Züge an einem Gleis erzeugen.

    Der Sortierschlüssel ist die Ankunfts- oder Abfahrtszeit am angegebenen Gleis im Fahrplan
    oder der default-Wert, wenn die Fahrplanzeile oder Zeitangabe fehlt.

    Args:
        gleis: Name des Gleises oder Bahnsteigs.
        attr: Name des Zeitattributs, entweder `an` oder `ab`.
        default: Defaultwert, falls das Attribut fehlt.

    Returns:
        sortierschlüssel-funktion für sorted().
    """

    def caller(zugdetails):
        try:
            return getattr(zugdetails.find_fahrplanzeile(gleis), attr)
        except AttributeError:
            return default
    return caller


def einfahrt_sortierschluessel(attr: str, default: datetime.time) -> Callable:
    """
    Sortierschlüssel-Funktion für Zugeinfahrten erzeugen.

    Der Sortierschlüssel ist die Ankunfts- oder Abfahrtszeit des ersten Fahrplanziels
    oder der Defaultwert, wenn der Fahrplan leer ist oder die Zeitangabe fehlt.

    Args:
        attr: Name des Zeitattributs, entweder `an` oder `ab`.
        default: Defaultwert, falls das Attribut fehlt.

    Returns:
        Sortierschlüssel-Funktion für sorted().
    """

    def caller(zugdetails):
        try:
            return getattr(zugdetails.fahrplan[0], attr)
        except (AttributeError, IndexError):
            return default
    return caller


def ausfahrt_sortierschluessel(attr: str, default: datetime.time) -> Callable:
    """
    sortierschlüssel-funktion für zugeinfahrten erzeugen.

    der sortierschlüssel ist die ankunfts- oder abfahrtszeit des letzten fahrplanziels
    oder der default-wert, wenn der fahrplan leer ist oder die zeitangabe fehlt.

    Args:
        attr: Name des Zeitattributs, entweder `an` oder `ab`.
        default: Defaultwert, falls das Attribut fehlt.

    Returns:
        Sortierschlüssel-Funktion für sorted().
    """

    def caller(zugdetails):
        try:
            return getattr(zugdetails.fahrplan[-1], attr)
        except (AttributeError, IndexError):
            return default

    return caller


class TaskDone(Exception):
    """
    Task erfolgreich erledigt

    Die exception signalisiert, dass die Aufgaben erfolgreich abgearbeitet worden sind.

    Die Exception kann vom Hauptprogramm ausgelöst werden, um einen trio-nursery-Kontext zu verlassen,
    der ansonsten unbestimmt auf andere Tasks warten würde.
    Die Exception muss ausserhalb des Kontexts abgefangen werden.
    """
    pass


async def test(*args, **kwargs) -> PluginClient:
    """
    Testprogramm

    Das Testprogramm fragt alle Daten einmalig vom Simulator ab und gibt sie an stdout aus.

    Der PluginClient bleibt bestehen, damit weitere Details aus den statischen Attributen ausgelesen werden können.
    Die Kommunikation mit dem Simulator wird jedoch geschlossen.

    Returns:
        `PluginClient`-Instanz
    """
    client = PluginClient(name='test', autor='tester', version='0.0', text='testing the plugin client')
    await client.connect()

    try:
        async with client.stream:
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
                client.update_bahnsteig_zuege()
                client.update_wege_zuege()
                raise TaskDone()
    except TaskDone:
        pass

    print("\nanlageninfo\n")
    print(client.anlageninfo)

    print("\nbahnsteige\n")
    for bi in client.bahnsteigliste.values():
        print(bi)
        print("  nachbarn: ", ", ".join(sorted(bi.nachbarn_namen)))

    print("\neinfahrten\n")
    for knoten in client.wege_nach_typ[6]:
        print(knoten)
        print("  nachbarn: ", ", ".join(sorted((n.key for n in knoten.nachbarn.values()))))

    print("\nausfahrten\n")
    for knoten in client.wege_nach_typ[7]:
        print(knoten)
        print("  nachbarn: ", ", ".join(sorted((n.key for n in knoten.nachbarn.values()))))

    print("\nzüge\n")
    for zid, zug in client.zugliste.items():
        print(zid, zug)

    return client


if __name__ == '__main__':
    trio.run(test)
