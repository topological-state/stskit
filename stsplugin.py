"""
stellwerksim plugin-client

dieses modul stellt eine PluginClient-klasse zur verfügung, die die kommunikation mit dem simulator übernimmt.
der client speichert auch alle anlagen- und fahrplandaten zwischen und verarbeitet ereignisse.

asynchrone kommunikation:

die kommunikationsmethoden des PluginClient sind als async-methoden deklariert,
die in await statements verwendet werden können.
diese architektur bedingt, dass die applikation eine ereignisschleife unterhält.
in textbasierten programmen, wird diese implizit vom asyncio-modul bereitgestellt
(siehe test-routine unten oder das ticker-programm).
bei GUI-programmen muss eine kompatible ereignisschleife wie z.b. von qasync für Qt verwendet werden.

vorsicht ist bei der verwendung von parallelen tasks geboten,
damit sich zwei serveranfragen nicht überschneiden können.
am besten werden alle anfragen im gleichen asyncio-task gestellt.
parallel dazu kann ein einem eigenen task, die ereignis-queue abgefragt werden, siehe ticker-programm.
"""

import asyncio
from contextlib import asynccontextmanager
import datetime
from typing import Any, Dict, List, Optional, Set, Union
import untangle

from xml.sax import make_parser

from model import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis


class PluginClient:
    def __init__(self, name: str, autor: str, version: str, text: str):
        self._reader = None
        self._writer = None
        self._parser = None
        self._handler = None
        self._rec_task = None

        self.debug: bool = False
        self.name: str = name
        self.autor: str = autor
        self.version: str = version
        self.text: str = text
        self.status: Optional[untangle.Element] = None

        self.anlageninfo: Optional[AnlagenInfo] = None
        self.bahnsteigliste: Dict[str, BahnsteigInfo] = {}
        self.wege: Dict[str, Knoten] = {}
        self.wege_nach_namen: Dict[str, Set[Knoten]] = {}
        self.wege_nach_typ: Dict[int, Set[Knoten]] = {}
        self.zugliste: Dict[int, ZugDetails] = {}
        self.zuggattungen: Set[str] = set()

        self.antworten = asyncio.Queue()
        self.ereignisse = asyncio.Queue()
        self.registrierte_ereignisse: Dict[str, Set[int]] = {art: set() for art in Ereignis.arten}

        self.client_datetime: datetime.datetime = datetime.datetime.now()
        self.server_datetime: datetime.datetime = datetime.datetime.now()
        self.time_offset: datetime.timedelta = self.server_datetime - self.client_datetime

    def check_status(self):
        if int(self.status.status['code']) >= 300:
            raise ValueError(f"error {self.status.status['code']}: {self.status.status.cdata}")

    def close(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None
        if self._rec_task is not None:
            self._rec_task.cancel()
            self._rec_task = None

    async def connect(self, host='localhost', port=3691):
        if self._writer is None:
            self._reader, self._writer = await asyncio.open_connection(host, port)
            self._parser = make_parser()
            self._handler = untangle.Handler()
            self._parser.setContentHandler(self._handler)

            data = await self._reader.readuntil(separator=b'>')
            data += await self._reader.readuntil(separator=b'>')
            xml = data.decode()
            self.status = untangle.parse(xml)
            if int(self.status.status['code']) >= 400:
                raise ValueError(f"error {self.status.status['code']}: {self.status.status.cdata}")

            self._rec_task = asyncio.create_task(self._receive_data())

            await self.register()
            await self.request_simzeit()

    @asynccontextmanager
    async def get_connection(self):
        """
        experimental

        :return:
        """
        await self.connect()
        try:
            yield self
        finally:
            self.close()

    def is_connected(self) -> bool:
        """
        ist der klient mit dem server verbunden?

        :return: (bool)
        """
        return self._writer is not None

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
        self._writer.write(data)
        await self._writer.drain()

    async def _receive_data(self):
        """
        empfangsschleife: antworten empfangen und verteilen

        alle antworten ausser ereignisse werden in untangle.Element objekte gepackt und
        an die self.antworten-queue übergeben.
        ereignisse werden als model.Ereignis-objekte an die self.ereignisse-queue übergeben.

        diese coroutine läuft im self._rec_task, solange die verbindung offen ist.
        """
        while True:
            bs = await self._reader.readline()
            s = bs.decode().replace('\n', '')
            if self.debug:
                print(s)
            if s:
                self._parser.feed(s)

            # xml tag complete?
            if len(self._handler.elements) == 0:
                element = self._handler.root
                self._parser.close()
                self._handler.root = untangle.Element(None, None)
                self._handler.root.is_root = True

                try:
                    tag = dir(element)[0]
                except IndexError:
                    # leeres element
                    continue
                else:
                    if tag == "ereignis":
                        obj = Ereignis().update(getattr(element, tag))
                        obj.zeit = self.calc_simzeit()
                        self.ereignisse.put_nowait(obj)
                    else:
                        self.antworten.put_nowait(element)

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

    async def register(self) -> None:
        """
        klient beim simulator registrieren.

        :return: None
        """
        await self._send_request("register", name=self.name, autor=self.autor, version=self.version,
                                 protokoll='1', text=self.text)
        self.status = await self.antworten.get()
        self.check_status()

    async def request_anlageninfo(self):
        """
        anlageninfo anfordern.

        die antwort wird im anlageninfo attribut gespeichert.

        :return: None
        """
        await self._send_request(AnlagenInfo.tag)
        response = await self.antworten.get()
        self.anlageninfo = AnlagenInfo().update(response.anlageninfo)

    async def request_bahnsteigliste(self):
        """
        bahnsteigliste anfordern.

        die liste wird im bahnsteigliste-attribut gespeichert.

        :return: None
        """
        self.bahnsteigliste = {}
        await self._send_request("bahnsteigliste")
        response = await self.antworten.get()
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
        simzeit = await self.antworten.get()
        secs, msecs = divmod(int(simzeit.simzeit['zeit']), 1000)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        t = datetime.time(hour=hrs, minute=mins, second=secs, microsecond=msecs * 1000)
        self.server_datetime = datetime.datetime.combine(self.client_datetime, t)
        self.time_offset = (self.server_datetime - self.client_datetime)
        return self.server_datetime

    async def request_wege(self):
        await self._send_request("wege")
        response = await self.antworten.get()
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
            response = await self.antworten.get()
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
            response = await self.antworten.get()
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
        response = await self.antworten.get()
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


async def test():
    client = PluginClient(name='test', autor='tester', version='0.0', text='testing the plugin client')
    await client.connect()
    await client.request_anlageninfo()
    await client.request_bahnsteigliste()
    await client.request_wege()
    await client.request_zugliste()
    await client.request_zugdetails()
    await client.request_zugfahrplan()
    client.close()
    client.update_bahnsteig_zuege()
    client.update_wege_zuege()

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
    asyncio.run(test())
