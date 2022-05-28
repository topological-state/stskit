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
"logging.getLogger('stsplugin').setLevel(logging.WARNING)".
"""

import trio
import datetime
import logging
from typing import Any, Callable, Dict, List, Iterable, Mapping, Optional, Set, Union
import untangle

from xml.sax import make_parser

from stsobj import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def check_status(status: untangle.Element):
    if int(status.status['code']) >= 400:
        raise ValueError(f"error {status.status['code']}: {status.status.cdata}")


def log_status_warning(request: str, response: untangle.Element):
    if hasattr(response, 'status'):
        logger.warning(f"{request}: {response.status}")


class PluginClient:
    """
    PluginClient - der kern der plugin-schnittstelle
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
        self.wege: Dict[str, Knoten] = {}
        self.wege_nach_namen: Dict[str, Set[Knoten]] = {}
        self.wege_nach_typ: Dict[int, Set[Knoten]] = {}
        self.zugliste: Dict[int, ZugDetails] = {}
        self.zuggattungen: Set[str] = set()

        self.registrierte_ereignisse: Dict[str, Set[int]] = {art: set() for art in Ereignis.arten}

        self.client_datetime: datetime.datetime = datetime.datetime.now()
        self.server_datetime: datetime.datetime = datetime.datetime.now()
        self.time_offset: datetime.timedelta = self.server_datetime - self.client_datetime

    async def connect(self, host='localhost', port=3691):
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

        parser: Any = make_parser()
        handler = untangle.Handler()
        parser.setContentHandler(handler)

        self._antwort_channel_in, self._antwort_channel_out = trio.open_memory_channel(0)
        self._ereignis_channel_in, self._ereignis_channel_out = trio.open_memory_channel(0)
        task_status.started()

        async with self._antwort_channel_in:
            async with self._ereignis_channel_in:
                async for bs in self._stream:
                    for s in bs.decode().split('\n'):
                        logger.debug("empfang: " + s)
                        if s:
                            parser.feed(s)

                        # xml tag complete?
                        if len(handler.elements) == 0:
                            element = handler.root
                            parser.close()
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
        await self._send_request("wege")
        response = await self._antwort_channel_out.receive()
        self.wege = {}
        self.wege_nach_namen = {}
        self.wege_nach_typ = {}

        for shape in response.wege.shape:
            knoten = Knoten().update(shape)
            # assert knoten.key not in self.wege, f"name/enr {knoten.key} kommt mehrfach vor"
            if knoten.key:
                self.wege[knoten.key] = knoten
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

        for connector in response.wege.connector:
            try:
                if connector['enr1']:
                    knoten1 = self.wege[connector['enr1']]
                else:
                    knoten1 = self.wege[connector['name1']]
            except KeyError:
                knoten1 = None

            try:
                if connector['enr2']:
                    knoten2 = self.wege[connector['enr2']]
                else:
                    knoten2 = self.wege[connector['name2']]
            except KeyError:
                knoten2 = None

            if knoten1 is not None and knoten2 is not None:
                knoten1.nachbarn.add(knoten2)
                knoten2.nachbarn.add(knoten1)

    async def request_zugdetails(self, zid: Optional[Union[int, Iterable[int]]] = None):
        """
        fahrplan eines zuges, mehrerer oder aller züge anfragen.

        wenn ein ZugDetails-objekt mit der zid muss bereits in der zugliste angelegt ist,
        wird es aktualisiert, andernfalls neu angelegt.
        wenn ein fehler auftritt (weil z.b. der zug nicht mehr im stellwerk ist),
        wird der zug aus der zugliste gelöscht.

        :param zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        :return: None
        """
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in map(int, zids):
            if zid > 0:
                await self._send_request("zugdetails", zid=zid)
                response = await self._antwort_channel_out.receive()
            else:
                logger.warning(f"request_zugdetails: anfrage mit zid={zid} ignoriert.")
                continue

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
            else:
                self.zuggattungen.add(zug.gattung)

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
        fahrplan eines zuges, mehrerer oder aller züge anfragen.

        das ZugDetails-objekt muss in der zugliste bereits existieren.

        bemerkung: abgefahrene wegpunkte sind im fahrplan nicht mehr vorhanden.

        :param zid: einzelne zug-id, iterable von zug-ids, oder None (alle in der liste).
        :return: None
        """
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in map(int, zids):
            try:
                zug = self.zugliste[zid]
                zug.fahrplan = []
            except KeyError:
                continue

            await self._send_request("zugfahrplan", zid=zid)
            response = await self._antwort_channel_out.receive()

            try:
                for gleis in response.zugfahrplan.gleis:
                    zeile = FahrplanZeile(zug).update(gleis)
                    zug.fahrplan.append(zeile)
                    if zug.gleis == zeile.gleis:
                        zug.fahrplanzeile = zeile
                    logger.debug(f"request_zugfahrplan: {zeile}")
                zug.fahrplan.sort(key=lambda zfz: zfz.an)
            except AttributeError:
                log_status_warning("request_zugfahrplan", response)

    async def request_zugliste(self):
        """
        zugliste anfragen.

        die zugliste wird angefragt und neu aufgebaut.

        bemerkung: folgezüge sind möglicherweise nicht enthalten.

        :return: None
        """
        self.zugliste = {}

        await self._send_request("zugliste")
        response = await self._antwort_channel_out.receive()

        try:
            for zug in response.zugliste.zug:
                try:
                    zid = int(zug['zid'])
                    if zid > 0:
                        self.zugliste[zid] = ZugDetails().update(zug)
                except (KeyError, ValueError):
                    logger.error(f"request_zugliste: fehlerhafter zug-eintrag: {zug}")
        except AttributeError:
            log_status_warning("request_zugliste", response)

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

        while zids:
            zid = zids.pop(0)
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
                        if zug2.stammzug and zug2.stammzug.zid != zug.zid:
                            logger.warning(f"mehrfacher stamm, zug {zug2}")
                        zug2.stammzug = zug
                        zug2.verspaetung = zug.verspaetung
                        zids.append(zid2)
                    else:
                        logger.warning(f"keine antwort für zug {zid2}")
                if zid2 := planzeile.fluegel_zid():
                    logger.info(f"zid {zid2} als flügel für {zid} anfragen")
                    zug2 = await self.request_zug(zid2)
                    if zug2 is not None:
                        planzeile.fluegelzug = zug2
                        if zug2.stammzug and zug2.stammzug.zid != zug.zid:
                            logger.warning(f"mehrfacher stamm, zug {zug2}")
                        zug2.stammzug = zug
                        zug2.verspaetung = zug.verspaetung
                        zids.append(zid2)
                    else:
                        logger.warning(f"keine antwort für zug {zid2}")
                if zid2 := planzeile.kuppel_zid():
                    logger.info(f"zid {zid2} als kuppel für {zid} anfragen")
                    zug2 = await self.request_zug(zid2)
                    if zug2 is not None:
                        planzeile.kuppelzug = zug2
                        if zug2.stammzug and zug2.stammzug.zid != zug.zid:
                            logger.warning(f"mehrfacher stamm, zug {zug2}")
                        zug2.stammzug = zug
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

        for zid in self.zugliste.keys():
            zug = self.zugliste[zid]

            try:
                einfahrten = self.wege_nach_namen[zug.von].intersection(self.wege_nach_typ[6])
                for einfahrt in einfahrten:
                    einfahrt.zuege.append(zug)
            except KeyError:
                pass
            try:
                ausfahrten = self.wege_nach_namen[zug.nach].intersection(self.wege_nach_typ[7])
                for ausfahrt in ausfahrten:
                    ausfahrt.zuege.append(zug)
            except KeyError:
                pass
            for fahrplanzeile in zug.fahrplan:
                try:
                    gleise = self.wege_nach_namen[fahrplanzeile.gleis]
                except KeyError:
                    pass
                else:
                    for gleis in gleise:
                        gleis.zuege.append(zug)

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
