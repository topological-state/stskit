import asyncio
import datetime
import untangle
from xml.sax import SAXParseException
from xml.parsers.expat import ExpatError

from model import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, ZugFahrplanZeile


class PluginClient:
    def __init__(self, name, autor, version, text):
        self._reader = None
        self._writer = None
        self.name = name
        self.autor = autor
        self.version = version
        self.text = text
        self.status = None
        self.anlageninfo = None
        # dict {BahnsteigInfo.name: Bahnsteiginfo}
        self.bahnsteigliste = {}
        # dict {Knoten.key: Knoten}
        self.wege = {}
        # dict {Knoten.name: set of Knoten}
        self.wege_nach_namen = {}
        # dict {Knoten.typ: set of Knoten}
        self.wege_nach_typ = {}
        self.zugliste = {}
        self.client_datetime = datetime.datetime.now()
        self.server_datetime = datetime.datetime.now()
        self.time_offset = self.server_datetime - self.client_datetime

    def check_status(self):
        if int(self.status.status['code']) >= 300:
            raise ValueError(f"error {self.status.status['code']}: {self.status.status.cdata}")

    def close(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None

    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection('127.0.0.1', 3691)
        data = await self._reader.readuntil(separator=b'>')
        data += await self._reader.readuntil(separator=b'>')
        xml = data.decode()
        self.status = untangle.parse(xml)
        if int(self.status.status['code']) >= 400:
            raise ValueError(f"error {self.status.status['code']}: {self.status.status.cdata}")
        await self.register()
        await self.request_simzeit()

    def is_connected(self):
        return self._writer is not None

    async def _send_request(self, tag, **kwargs):
        """

        :param tag:
        :param kwargs:
        :return:
        :raise: asyncio.TimeoutError
        """
        args = [f"{k}='{v}'" for k, v in kwargs.items()]
        args = " ".join(args)
        req = f"<{tag} {args} />\n"
        data = req.encode()
        self._writer.write(data)
        await self._writer.drain()

        rec = b""
        obj = None
        while True:
            rec = rec + await asyncio.wait_for(self._reader.readuntil(separator=b'>'), timeout=10)
            try:
                obj = untangle.parse(rec.decode())
                break
            except ExpatError:
                pass
            except SAXParseException:
                pass
            except UnicodeDecodeError:
                break
        return obj

    def get_sim_clock(self):
        return datetime.datetime.now() + self.time_offset

    async def register(self):
        self.status = await self._send_request("register", name=self.name, autor=self.autor, version=self.version,
                                         protokoll='1', text=self.text)
        self.check_status()

    async def request_anlageninfo(self):
        response = await self._send_request("anlageninfo")
        self.anlageninfo = AnlagenInfo()
        self.anlageninfo.update(response.anlageninfo)

    async def request_bahnsteigliste(self):
        self.bahnsteigliste = {}
        response = await self._send_request("bahnsteigliste")
        for bahnsteig in response.bahnsteigliste.bahnsteig:
            bi = BahnsteigInfo().update(bahnsteig)
            self.bahnsteigliste[bi.name] = bi

    async def request_simzeit(self):
        self.client_datetime = datetime.datetime.now()
        simzeit = await self._send_request("simzeit", sender=0)
        secs, msecs = divmod(int(simzeit.simzeit['zeit']), 1000)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        t = datetime.time(hour=hrs, minute=mins, second=secs, microsecond=msecs * 1000)
        self.server_datetime = datetime.datetime.combine(self.client_datetime, t)
        self.time_offset = self.server_datetime - self.client_datetime

    async def request_wege(self):
        response = await self._send_request("wege")
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
            response = await self._send_request("zugdetails", zid=zid)
            self.zugliste[zid].update(response.zugdetails)

    async def request_zugfahrplan(self, zid=None):
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in zids:
            response = await self._send_request("zugfahrplan", zid=zid)
            zug = self.zugliste[zid]
            zug.fahrplan = []
            try:
                for gleis in response.zugfahrplan.gleis:
                    zeile = ZugFahrplanZeile(zug)
                    zeile.update(gleis)
                    zug.fahrplan.append(zeile)
            except AttributeError:
                pass
            zug.fahrplan.sort(key=lambda zfz: zfz.an)

    async def request_zugliste(self):
        response = await self._send_request("zugliste")
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

    # for zid, zug in client.zugliste.items():
    #     print(zid, zug)

    for knoten in client.wege_nach_typ[6]:
        print(knoten)
        for zug in knoten.zuege:
            try:
                print(zug.name, zug.fahrplan[0].an, zug.verspaetung)
            except (AttributeError, IndexError):
                pass
        print()

    return client


if __name__ == '__main__':
    asyncio.run(test())
