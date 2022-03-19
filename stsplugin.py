"""
stellwerksim plugin-client

dieses modul stellt eine PluginClient-klasse zur verfügung, die die kommunikation mit dem simulator übernimmt.
der client speichert auch alle anlagen- und fahrplandaten zwischen und verarbeitet ereignisse.

asynchrone kommunikation:

die kommunikationsmethoden des PluginClient sind als asynchron und werden von der trio-bibliothek verwaltet.

vorsicht ist bei der verwendung von parallelen tasks geboten,
damit sich zwei serveranfragen nicht überschneiden können.
am besten werden alle anfragen im gleichen asyncio-task gestellt.
parallel dazu kann in einem eigenen task, die ereignis-queue abgefragt werden, siehe ticker-programm.
"""

import trio
import datetime
from typing import Any, Dict, List, Optional, Set, Union
import untangle

from xml.sax import make_parser

from model import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis


def check_status(status: untangle.Element):
    if int(status.status['code']) >= 400:
        raise ValueError(f"error {status.status['code']}: {status.status.cdata}")


class PluginClient:
    def __init__(self, name: str, autor: str, version: str, text: str):
        self._stream: Optional[trio.abc.Stream] = None
        self.connected = trio.Event()

        self.debug: bool = False
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
        req = f"<{tag} {args} />\n"
        data = req.encode()
        await self._stream.send_all(data)

    async def _receiver(self, *, task_status=trio.TASK_STATUS_IGNORED):
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
                        if self.debug:
                            print(s)
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

    async def request_zugdetails(self, zid=None):
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in zids:
            await self._send_request("zugdetails", zid=zid)
            response = await self._antwort_channel_out.receive()
            self.zugliste[zid].update(response.zugdetails)
            self.zuggattungen.add(self.zugliste[zid].gattung)

    async def request_ereignis(self, art, zids):
        """
        ereignismeldung anfordern

        :param art: art des ereignisses, cf. model.Ereignis.arten
        :param zids: menge oder sequenz von zug-id-nummern
        :return: None
        """
        zids = set(zids).difference(self.registrierte_ereignisse[art])
        for zid in zids:
            await self._send_request("ereignis", art=art, zid=zid)
            self.registrierte_ereignisse[art].update(zids)

    async def request_zugfahrplan(self, zid=None):
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in zids:
            await self._send_request("zugfahrplan", zid=zid)
            response = await self._antwort_channel_out.receive()
            zug = self.zugliste[zid]
            zug.fahrplan = []
            try:
                for gleis in response.zugfahrplan.gleis:
                    zeile = FahrplanZeile(zug)
                    zeile.update(gleis)
                    zug.fahrplan.append(zeile)
            except AttributeError:
                pass
            zug.fahrplan.sort(key=lambda zfz: zfz.an)

    async def request_zugliste(self):
        await self._send_request("zugliste")
        response = await self._antwort_channel_out.receive()
        try:
            self.zugliste = {zug['zid']: ZugDetails().update(zug) for zug in response.zugliste.zug}
        except AttributeError:
            self.zugliste = {}

    def update_bahnsteig_zuege(self):
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
            bahnsteig.zuege.sort(key=zugsortierschluessel(bahnsteig.name, 'an', datetime.time()))

    def update_wege_zuege(self):
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
                knoten.zuege.sort(key=zugsortierschluessel(knoten.name, 'an', datetime.time()))
            elif knoten.typ == 6:
                knoten.zuege.sort(key=einfahrt_sortierschluessel('an', datetime.time()))
            elif knoten.typ == 7:
                knoten.zuege.sort(key=ausfahrt_sortierschluessel('an', datetime.time()))


def zugsortierschluessel(gleis, attr, default):
    def caller(zugdetails):
        try:
            return getattr(zugdetails.find_fahrplanzeile(gleis), attr)
        except AttributeError:
            return default
    return caller


def einfahrt_sortierschluessel(attr, default):
    def caller(zugdetails):
        try:
            return getattr(zugdetails.fahrplan[0], attr)
        except (AttributeError, IndexError):
            return default
    return caller


def ausfahrt_sortierschluessel(attr, default):
    def caller(zugdetails):
        try:
            return getattr(zugdetails.fahrplan[-1], attr)
        except (AttributeError, IndexError):
            return default

    return caller


class TaskDone(Exception):
    pass


async def test():
    client = PluginClient(name='test', autor='tester', version='0.0', text='testing the plugin client')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client._receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                await client.request_bahnsteigliste()
                await client.request_wege()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
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
        print("  nachbarn: ", ", ".join(sorted(bi.nachbarn)))

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
