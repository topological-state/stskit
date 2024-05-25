"""
stellwerksim plugin-client

dieses modul stellt eine PluginClient-klasse zur verfügung, die die kommunikation mit dem simulator übernimmt.
der client speichert auch alle anlagen- und fahrplandaten zwischen und verarbeitet ereignisse.
der PluginClient übersetzt anfragen in xml und sendet sie an den simulator.
die xml-antworten übersetzt er in python-objekte.

asynchrone kommunikation:

die kommunikation verläuft asynchron und ist nach der trio-bibliothek modelliert.
es gibt einen socket-stream für die xml-kommunikation mit dem simulator.
die request-methoden senden anfragen via diesen stream.
antworten werden innerhalb der receiver-methode, die in einem eigenen task gestartet wird, verarbeitet
und als python-objekte in die antworten- oder ereignis-queues gestellt.
die request-methoden holen die antworten dort ab.
für ereignisse kann das hauptprogramm einen separaten task starten und die queue auslesen.

vorsicht ist bei der verwendung von parallelen tasks geboten,
damit sich zwei serveranfragen nicht überschneiden können.
am besten werden alle anfragen im gleichen task gestellt.
in einem separaten task wird die ereignis-queue abgefragt.

beispiele für die implementation zeigen das testprogramm unten, oder weitere im paket enthaltenen programme.

logging:

stsplugin nutzt einen eigenen logger mit dem namen "stsplugin" aus dem logging modul der standardbibliothek.
vorsicht: auf stufe DEBUG wird die gesamte kommunikation mit dem simulator ausgegeben!
wenn dies nicht gewünscht wird, der rest des programms aber auf DEBUG bleiben soll,
kann die stufe dieses moduls individuell angepasst werden durch
"logging.getLogger('stskit.interface.stsplugin').setLevel(logging.WARNING)".
"""
import sys

import trio
import datetime
import html.entities
import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union
import untangle
import xml.sax

from stskit.interface.stsobj import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis


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

    Attribute
    ---------

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

    Verwendung
    ----------

    Siehe Beispielcode am Ende des Moduls (test-Funktion).
    """

    def __init__(self, name: str, autor: str, version: str, text: str):
        self._stream: Optional[trio.abc.Stream] = None
        self._antwort_channel_in: Optional[trio.MemorySendChannel] = None
        self._antwort_channel_out: Optional[trio.MemoryReceiveChannel] = None
        self._ereignis_channel_in: Optional[trio.MemorySendChannel] = None
        self._ereignis_channel_out: Optional[trio.MemoryReceiveChannel] = None

        self.connected = trio.Event()
        self.registered = trio.Event()

        self.name: str = name
        self.autor: str = autor
        self.version: str = version
        self.text: str = text

        self.anlageninfo: Optional[AnlagenInfo] = None
        self.bahnsteigliste: Dict[str, BahnsteigInfo] = {}
        self.wege: Dict[Union[int, str], Knoten] = {}
        self.wege_nach_enr: Dict[int, Knoten] = {}
        self.wege_nach_namen: Dict[str, Set[Knoten]] = {}
        self.wege_nach_typ: Dict[int, Set[Knoten]] = {}
        self.wege_nach_typ_namen: Dict[int, Dict[str, Knoten]] = {}
        self.wege_verbindungen: Set[Tuple[Union[int, str], Union[int, str]]] = set([])
        self.zugliste: Dict[int, ZugDetails] = {}
        self.zuggattungen: Set[str] = set()

        self.registrierte_ereignisse: Dict[str, Set[int]] = {art: set() for art in Ereignis.arten}

        self.client_datetime: datetime.datetime = datetime.datetime.now()
        self.server_datetime: datetime.datetime = datetime.datetime.now()
        self.time_offset: datetime.timedelta = self.server_datetime - self.client_datetime

    async def connect(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self._stream = await trio.open_tcp_stream(host, port)
        self.connected.set()

    async def close(self):
        await self._stream.aclose()
        self.connected = trio.Event()
        self.registered = trio.Event()

    async def _send_request(self, tag, **kwargs):
        """
        anfrage senden.

        diese coroutine wartet ggf., bis der sendepuffer wieder bereit ist.

        :param tag: name des xml-tags
        :param kwargs: (dict) attribute des xml-tags
        :return: None
        """
        args = [f"{k}='{v}'" for k, v in kwargs.items()]
        args = " ".join(args)
        req = f"<{tag} {args} />"
        logger.debug("senden: " + req)
        req += "\n"
        data = req.encode()
        await self._stream.send_all(data)

    async def receiver(self, *, task_status=trio.TASK_STATUS_IGNORED):
        """
        empfangsschleife: antworten empfangen und verteilen

        alle antworten ausser ereignisse werden in untangle.Element objekte gepackt
        und and den antworten-channel übergeben.
        ereignisse werden als model.Ereignis-objekte an den ereignisse-channel übergeben.

        diese coroutine muss explizit in einer trio.nursery gestartet werden
        und läuft, bis die verbindung unterbrochen wird.
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

        async with self._antwort_channel_in:
            async with self._ereignis_channel_in:
                async for bs in self._stream:
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
                                    await self._ereignis_channel_in.send(ereignis)
                                else:
                                    await self._antwort_channel_in.send(element)

    async def register(self) -> None:
        """
        klient beim simulator registrieren.

        die funktion muss als erste nach dem connect aufgerufen werden,
        da sie auch die statusantwort nach der verbindungsaufnahme auswertet.

        :return: None
        """
        status = await self._antwort_channel_out.receive()
        check_status(status)

        await self._send_request("register", name=self.name, autor=self.autor, version=self.version,
                                 protokoll='1', text=self.text)
        status = await self._antwort_channel_out.receive()
        check_status(status)
        self.registered.set()

    async def request_anlageninfo(self):
        """
        anlageninfo anfordern.

        die antwort wird im anlageninfo attribut gespeichert.

        :return: None
        """
        await self._send_request(AnlagenInfo.tag)
        response = await self._antwort_channel_out.receive()
        self.anlageninfo = AnlagenInfo().update(response.anlageninfo)

    async def request_bahnsteigliste(self):
        """
        bahnsteigliste anfordern.

        die liste wird im bahnsteigliste-attribut gespeichert.

        :return: None
        """
        self.bahnsteigliste = {}
        await self._send_request("bahnsteigliste")
        response = await self._antwort_channel_out.receive()
        for bahnsteig in response.bahnsteigliste.bahnsteig:
            bi = BahnsteigInfo().update(bahnsteig)
            self.bahnsteigliste[bi.name] = bi

        for bahnsteig in self.bahnsteigliste.values():
            bahnsteig.nachbarn = [self.bahnsteigliste[name] for name in bahnsteig.nachbarn_namen]
            bahnsteig.nachbarn.sort(key=lambda b: b.name)

    async def request_simzeit(self) -> datetime.datetime:
        """
        simulatorzeit anfragen.

        die funktion fragt die aktuelle simulatorzeit an und liefert sie in einem datetime.time objekt.

        basierend auf der antwort setzt sie ausserdem client_datetime, server_datetime und time_offset.
        diese attribute können benutzt werden, um die simulatorzeit zu berechnen (calc_simzeit funktion),
        ohne dass eine erneute anfrage geschickt werden muss.

        bemerkung: client_datetime und server_datetime enthalten das aktuelle datum.
        das ist nötig, um den time_offset als timedelta zu berechnen.
        da der simulator kein datum kennt, sollten die datumsfelder nicht beachtet werden.
        die datetime.datetime.time-methode ist ein schneller weg, ein datetime.time-objekt zu erhalten.

        :return: (datetime.datetime)
        """
        self.client_datetime = datetime.datetime.now()
        await self._send_request("simzeit", sender=0)
        simzeit = await self._antwort_channel_out.receive()
        secs, msecs = divmod(int(simzeit.simzeit['zeit']), 1000)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        t = datetime.time(hour=hrs, minute=mins, second=secs, microsecond=msecs * 1000)
        self.server_datetime = datetime.datetime.combine(self.client_datetime, t)
        self.time_offset = (self.server_datetime - self.client_datetime)
        return self.server_datetime

    def calc_simzeit(self) -> datetime.datetime:
        """
        simulatorzeit ohne serverabfrage abschätzen.

        der time_offset muss vorher einmal mittels request_simzeit kalibriert worden sein.

        der rückgabewert enthält das aktuelle (client-)datum.
        das ist nötig, damit mit der uhrzeit gerechnet werden kann.
        da der simulator kein datum kennt, sollten die datumsfelder nach der rechnung nicht beachtet werden.
        der fahrplan (in FahrplanZeile) enthält lediglich datetime.time objekte.
        ein datetime.time-objekt kann einfach über die time-methode extrahiert werden.

        :return: (datetime.datetime)
        """
        return datetime.datetime.now() + self.time_offset

    async def request_wege(self):
        """
        Wege-Graph anfragen

        Der Wege-Graph enthält die Elemente des Gleisbilds und ihre Verbindungen.
        Im PluginClient wird er als Dict von Knoten-Objekten dargestellt,
        die über ihre Nachbarn-attribute verlinkt sind.
        Für eine Darstellung mittels networkx-Graphen, siehe stsgraph.GraphClient.

        Da der Simulator für die Elemente zwei verschiedene Schlüssel (enr und name) verwendet,
        ist der Schlüssel des Wege-Dict zweiteilig und enthält den Elementtyp und
        - je nach Typ - entweder die enr oder den Namen.

        Die methode aktualisiert folgende Attribute:
        wege, wege_nach_enr, wege_nach_namen, wege_nach_typ, wege_verbindungen.

        Bemerkungen
        -----------

        - Teilweise fehlen wichtige Gleisverbindungen in dem Graphen, z.B. von Anschlüssen ans Gleisnetz.

        :return: None
        """

        await self._send_request("wege")
        response = await self._antwort_channel_out.receive()
        self.wege = {}
        self.wege_nach_enr = {}
        self.wege_nach_namen = {}
        self.wege_nach_typ = {typ: set([]) for typ in Knoten.TYP_NAME}
        self.wege_nach_typ_namen = {typ: {} for typ in Knoten.TYP_NAME}

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
                    key1 = connector['name1']
                except KeyError:
                    logger.warning(f"Fehlerhafte Elementreferenz zu Knoten 1 von {connector}")
                    continue

            try:
                knoten1 = self.wege[key1]
            except KeyError:
                logger.warning(f"Nicht auflösbare Elementreferenz zu Knoten 1 von {connector}")
                knoten1 = None

            try:
                key2 = int(connector['enr2'])
            except (KeyError, TypeError):
                try:
                    key2 = connector['name2']
                except KeyError:
                    logger.warning(f"Fehlerhafte Elementreferenz zu Knoten 2 von {connector}")
                    continue

            try:
                knoten2 = self.wege[key2]
            except KeyError:
                logger.warning(f"Nicht auflösbare Elementreferenz zu Knoten 2 von {connector}")
                knoten2 = None

            if key1 and key2:
                self.wege_verbindungen.add((key1, key2))

            if knoten1 is not None and knoten2 is not None:
                knoten1.nachbarn.add(knoten2)
                knoten2.nachbarn.add(knoten1)

    async def request_zugdetails(self, zid: Optional[Union[int, Iterable[int]]] = None):
        """
        ZugDetails eines, mehrerer oder aller Züge anfragen.

        Wenn ein ZugDetails-Objekt mit der zid bereits in der Zugliste angelegt ist,
        wird es aktualisiert, andernfalls neu angelegt.
        Wenn ein Fehler auftritt (weil z.B. der Zug nicht mehr im Stellwerk ist),
        wird der Zug aus der Zugliste gelöscht.

        :param zid: Einzelne Zug-ID, Iterable von Zug-IDs, oder None (alle in der Zugliste).
        :return: None
        """

        if zid is not None:
            try:
                zids = list(iter(zid))
            except TypeError:
                zids = [int(zid)]
        else:
            zids = list(self.zugliste.keys())

        for zid in sorted(map(int, zids)):
            if zid > 0:
                await self.request_zugdetails_einzeln(zid)
            else:
                logger.warning(f"request_zugdetails: anfrage mit zid={zid} ignoriert.")

    async def request_zugdetails_einzeln(self, zid: int) -> bool:
        """
        ZugDetails eines einzelnen Zuges anfragen.

        Wenn ein ZugDetails-Objekt mit der angegebenen zid bereits in der Zugliste angelegt ist,
        wird es aktualisiert, andernfalls neu angelegt.
        Wenn ein Fehler auftritt (weil z.B. der Zug nicht mehr im Stellwerk ist),
        wird der Zug aus der Zugliste gelöscht.

        :param zid: einzelne zug-id.
        :return: True (Erfolg) oder False (Fehler, Zug entfernt)
        """

        await self._send_request("zugdetails", zid=zid)
        response = await self._antwort_channel_out.receive()

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

    async def request_ereignis(self, art, zids: Iterable[int]):
        """
        ereignismeldung anfordern

        bemerkung: nach namenswechsel muss man ereignismeldungen neu anfordern.
        ausser für "einfahrt" schicken wir daher anforderungen nur, wenn der zug sichtbar ist.

        anforderungen werden in registrierte_ereignisse notiert,
        damit sie nicht wiederholt gesendet werden.

        :param art: art des ereignisses, cf. model.Ereignis.arten
        :param zids: menge oder sequenz von zug-id-nummern
        :return: None
        """
        zids = set(zids).difference(self.registrierte_ereignisse[art])
        for zid in zids:
            if zid in self.zugliste and (art == "einfahrt" or self.zugliste[zid].sichtbar):
                await self._send_request("ereignis", art=art, zid=zid)
                self.registrierte_ereignisse[art].add(zid)

    async def request_zugfahrplan(self, zid: Optional[Union[int, Iterable[int]]] = None):
        """
        Fahrplan eines, mehrerer oder aller Züge anfragen.

        Das ZugDetails-Objekt muss in der Zugliste bereits existieren.

        Bemerkungen
        -----------

        - Abgefahrene Wegpunkte sind im Fahrplan nicht mehr vorhanden.

        :param zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        :return: None
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

        Bemerkungen
        -----------

        - Abgefahrene Wegpunkte sind im Fahrplan nicht mehr vorhanden.

        :param zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        :return: True (Erfolg) oder False (Fehler)
        """

        zug = self.zugliste[zid]
        akt_ziel_index = None

        await self._send_request("zugfahrplan", zid=zid)
        response = await self._antwort_channel_out.receive()

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

        if not zug.fahrplan:
            zug.fahrplan = neuer_fahrplan
            zug.ziel_index = akt_ziel_index
            return True

        for zeile_alt, zeile_neu in zip(reversed(zug.fahrplan), reversed(neuer_fahrplan)):
            if zeile_neu.plan == zeile_alt.plan:
                zeile_alt.update(zeile_neu.__dict__)
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

        Bemerkungen
        -----------

        - Die vom Simulator gelieferte Zugliste enthält nicht alle Folgezüge.
        - Ausgefahrene Züge werden von der Liste entfernt.
          Für ersetzte Züge wird ein ersatz-Ereignis erzeugt.
        - Die Zugobjekte sind nach dieser Abfrage schon ziemlich komplett.
          Es fehlen die aktuelle Verspätung fehlt (request_zugdetails)
          und Gleisänderungen im Fahrplan (request_zugfahrplan).
        - Die Objektinstanzen werden bei Aktualisierung beibehalten.
        - Züge mit negativer ID (Ersatzloks) werden ignoriert.

        :return: None
        """

        alte_zugliste = set(self.zugliste.keys())
        aktuelle_zugliste = set()
        zeit = self.calc_simzeit()

        await self._send_request("zugliste")
        response = await self._antwort_channel_out.receive()

        try:
            for zug in response.zugliste.zug:
                try:
                    zid = int(zug['zid'])
                    if zid <= 0:
                        # Ersatzlok
                        continue
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
                    await self._ereignis_channel_in.send(ereignis)
            try:
                del self.zugliste[zid]
            except KeyError:
                pass

    async def request_zug(self, zid: int) -> Optional[ZugDetails]:
        """
        einzelnen zug und fahrplan anfragen.

        der zug wird in die zugliste eingetragen bzw. aktualisiert und als ZugDetails-objekt zurückgegeben.

        :param zid: einzelne zug-id
        :return: ZugDetails inkl. fahrplan
        """
        zid = int(zid)
        if zid > 0:
            await self.request_zugdetails(zid)
            await self.request_zugfahrplan(zid)
        else:
            return None

        try:
            zug = self.zugliste[zid]
            return zug
        except KeyError:
            return None

    async def resolve_zugflags(self, zid: Optional[Union[int, Iterable[int]]] = None):
        """
        folgezüge aus den zugflags auflösen.

        da request_zugliste die folgezüge (ersatz-, flügel- und kuppelzüge) nicht automatisch erhält,
        lesen wir diese aus den zugflags aus und fragen ihre details und fahrpläne an.
        die funktion arbeitet iterativ, bis alle folgezüge aufgelöst sind.
        die züge werden in die zugliste eingetragen und im stammzug referenziert.

        anmerkung: zids sind nicht chronologisch. ersatzzüge können eine tiefere zid als der stammzug haben.

        :param zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        :return: None
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
        züge in bahnsteigliste eintragen.

        im züge-attribut der bahnsteige werden die fahrplanmässig an dem bahnsteig vorbei kommenden züge aufgelistet.

        :return: None
        """
        for bahnsteig in self.bahnsteigliste.values():
            bahnsteig.zuege = []

        for zid in self.zugliste.keys():
            zug = self.zugliste[zid]
            for fahrplanzeile in zug.fahrplan:
                try:
                    bahnsteig = self.bahnsteigliste[fahrplanzeile.gleis]
                except KeyError:
                    pass
                else:
                    bahnsteig.zuege.append(zug)

        for bahnsteig in self.bahnsteigliste.values():
            bahnsteig.zuege = sorted(set(bahnsteig.zuege),
                                     key=zugsortierschluessel(bahnsteig.name, 'an', datetime.time()))

    def update_wege_zuege(self):
        """
        züge in wegelisten eintragen.

        im züge-attribut der wege und knoten (einfahrten, ausfahrten, haltepunkte)
        werden die fahrplanmässig daran vorbei kommenden züge aufgelistet.

        :return: None
        """
        for knoten in self.wege.values():
            knoten.zuege = []

        einfahrten = {knoten.name: knoten for knoten in self.wege_nach_typ[6]}
        ausfahrten = {knoten.name: knoten for knoten in self.wege_nach_typ[7]}
        bahnsteige = {knoten.name: knoten for knoten in self.wege_nach_typ[5]}
        haltepunkte = {knoten.name: knoten for knoten in self.wege_nach_typ[12]}
        haltepunkte.update(bahnsteige)

        for zid in self.zugliste.keys():
            zug = self.zugliste[zid]

            try:
                einfahrten[zug.von].zuege.append(zug)
            except KeyError:
                pass
            try:
                ausfahrten[zug.nach].zuege.append(zug)
            except KeyError:
                pass
            for fahrplanzeile in zug.fahrplan:
                try:
                    haltepunkte[fahrplanzeile.gleis].zuege.append(fahrplanzeile.gleis)
                except KeyError:
                    pass

        for knoten in self.wege.values():
            if knoten.typ == 5 or knoten.typ == 12:
                knoten.zuege = sorted(set(knoten.zuege), key=zugsortierschluessel(knoten.name, 'an', datetime.time()))
            elif knoten.typ == 6:
                knoten.zuege = sorted(set(knoten.zuege), key=einfahrt_sortierschluessel('an', datetime.time()))
            elif knoten.typ == 7:
                knoten.zuege = sorted(set(knoten.zuege), key=ausfahrt_sortierschluessel('an', datetime.time()))


def zugsortierschluessel(gleis: str, attr: str, default: datetime.time) -> Callable:
    """
    sortierschlüssel-funktion für züge an einem gleis erzeugen.

    der sortierschlüssel ist die ankunfts- oder abfahrtszeit am angegebenen gleis im fahrplan
    oder der default-wert, wenn die fahrplanzeile oder zeitangabe fehlt.

    :param gleis: name des gleises oder bahnsteigs.
    :param attr: name des zeit-attributs, entweder 'an' oder 'ab'.
    :param default: default-zeit, falls das attribut fehlt.
    :return: sortierschlüssel-funktion für sorted().
    """

    def caller(zugdetails):
        try:
            return getattr(zugdetails.find_fahrplanzeile(gleis), attr)
        except AttributeError:
            return default
    return caller


def einfahrt_sortierschluessel(attr: str, default: datetime.time) -> Callable:
    """
    sortierschlüssel-funktion für zugeinfahrten erzeugen.

    der sortierschlüssel ist die ankunfts- oder abfahrtszeit des ersten fahrplanziels
    oder der default-wert, wenn der fahrplan leer ist oder die zeitangabe fehlt.

    :param attr: name des zeit-attributs, entweder 'an' oder 'ab'.
    :param default: default-zeit, falls das attribut fehlt.
    :return: sortierschlüssel-funktion für sorted().
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

    :param attr: name des zeit-attributs, entweder 'an' oder 'ab'.
    :param default: default-zeit, falls das attribut fehlt.
    :return: sortierschlüssel-funktion für sorted().
    """

    def caller(zugdetails):
        try:
            return getattr(zugdetails.fahrplan[-1], attr)
        except (AttributeError, IndexError):
            return default

    return caller


class TaskDone(Exception):
    """
    task erfolgreich erledigt

    die exception signalisiert, dass die aufgaben erfolgreich abgearbeitet worden sind.

    die exception kann vom hauptprogramm ausgelöst werden, um einen trio-nursery-kontext zu verlassen,
    der ansonsten unbestimmt auf andere tasks warten würde.
    die exception muss ausserhalb des kontexts abgefangen werden.
    """
    pass


async def test() -> PluginClient:
    """
    testprogramm

    das testprogramm fragt alle daten einmalig vom simulator ab und gibt sie an stdout aus.

    der PluginClient bleibt bestehen, damit weitere details aus den statischen attributen ausgelesen werden können.
    die kommunikation mit dem simulator wird jedoch geschlossen.

    :return: PluginClient-instanz
    """
    client = PluginClient(name='test', autor='tester', version='0.0', text='testing the plugin client')
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
        print("  nachbarn: ", ", ".join(sorted((n.key for n in knoten.nachbarn))))

    print("\nausfahrten\n")
    for knoten in client.wege_nach_typ[7]:
        print(knoten)
        print("  nachbarn: ", ", ".join(sorted((n.key for n in knoten.nachbarn))))

    print("\nzüge\n")
    for zid, zug in client.zugliste.items():
        print(zid, zug)

    return client


if __name__ == '__main__':
    trio.run(test)
