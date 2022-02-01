import datetime
import socket
import untangle
from xml.sax import SAXParseException

socket.setdefaulttimeout(10)


class AnlagenInfo:
    def __init__(self):
        self.aid = ""
        self.name = ""
        self.build = 0
        self.region = ""
        self.online = False

    def update(self, item):
        self.aid = item['aid']
        self.name = item['name']
        self.build = item['simbuild']
        self.region = item['region']
        self.online = bool(item['online'])
        return self


class BahnsteigInfo:
    def __init__(self):
        self.name = ""
        self.haltepunkt = False
        self.nachbarn = set()
        self.zuege = []

    def __str__(self):
        if self.haltepunkt:
            return f"Bahnsteig {self.name} (Haltepunkt)"
        else:
            return f"Bahnsteig {self.name}"

    def __repr__(self):
        return f"BahnsteigInfo {self.name}: haltepunkt={self.haltepunkt}"

    def update(self, item):
        self.name = item['name']
        self.haltepunkt = bool(item['haltepunkt'])
        try:
            self.nachbarn = {n['name'] for n in item.n}
        except AttributeError:
            self.nachbarn = set()
        return self


class Knoten:
    typen = {2: "Signal",
             3: "Weiche unten",
             4: "Weiche oben",
             5: "Bahnsteig",
             6: "Einfahrt",
             7: "Ausfahrt",
             12: "Haltepunkt"}

    def __init__(self):
        self.key = ""
        self.enr = 0
        self.name = ""
        self.typ = 0
        self.nachbarn = set()
        self.zuege = []

    def __eq__(self, other):
        return self.key.__eq__(other.key)

    def __hash__(self):
        return self.key.__hash__()

    def __str__(self):
        return f"Knoten {self.key}: {self.typen[self.typ]} {self.name}"

    def __repr__(self):
        return f"Knoten('{self.key}': enr={self.enr}, typ={self.typ}, name='{self.name}')"

    def update(self, shape):
        try:
            self.enr = int(shape['enr'])
        except TypeError:
            self.enr = None
        self.name = shape['name']
        if self.enr:
            self.key = str(self.enr)
        else:
            self.key = self.name
        try:
            self.typ = int(shape['type'])
        except TypeError:
            self.typ = 0
        return self


class ZugDetails:
    def __init__(self):
        self.zid = 0
        self.name = ""
        self.von = ""
        self.nach = ""
        self.verspaetung = 0
        self.sichtbar = False
        self.gleis = ""
        self.plangleis = ""
        self.amgleis = False
        self.hinweistext = ""
        self.usertext = ""
        self.usertextsender = ""
        self.fahrplan = []

    def __eq__(self, other):
        return self.zid.__eq__(other.zid)

    def __hash__(self):
        return self.zid.__hash__()

    def __str__(self):
        return f"Zug {self.name} von {self.von} nach {self.nach}"

    def __repr__(self):
        return f"ZugDetails({self.zid}, '{self.name}', '{self.von}', '{self.nach}')"

    def update(self, zugdetails):
        self.zid = zugdetails['zid']
        self.name = zugdetails['name']
        try:
            self.verspaetung = int(zugdetails['verspaetung'])
        except TypeError:
            pass
        self.gleis = zugdetails['gleis']
        self.plangleis = zugdetails['plangleis']
        self.von = zugdetails['von']
        self.nach = zugdetails['nach']
        self.sichtbar = bool(zugdetails['sichtbar'])
        self.amgleis = bool(zugdetails['amgleis'])
        self.usertext = zugdetails['usertextsender']
        self.usertextsender = zugdetails['usertextsender']
        self.hinweistext = zugdetails['hinweistext']
        return self

    def find_fahrplanzeile(self, gleis):
        """
        finde erste fahrplanzeile, in der gleis als aktuelles gleis vorkommt.
        :param gleis:
        :return:
        """
        for zeile in self.fahrplan:
            if gleis == zeile.gleis:
                return zeile
        return None


class ZugFahrplanZeile():
    def __init__(self, zug):
        self.zug = zug
        self.gleis = ""
        self.plan = ""
        self.an = datetime.time(hour=0, minute=0)
        self.ab = datetime.time(hour=0, minute=0)
        self.flags = ""
        self.hinweistext = ""

    def __str__(self):
        if self.gleis == self.plan:
            return f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"ZugFahrplanZeile('{self.gleis}', '{self.plan}', {self.an}, {self.ab}, '{self.flags}')"

    def update(self, item):
        self.gleis = item['name']
        self.plan = item['plan']
        try:
            self.an = datetime.time.fromisoformat(item['an'])
        except ValueError:
            self.an = None
        try:
            self.ab = datetime.time.fromisoformat(item['ab'])
        except ValueError:
            self.ab = None
        self.flags = item['flags']
        self.hinweistext = item['hinweistext']
        return self


class PluginClient:
    def __init__(self, name, autor, version, text):
        self._socket = None
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
        self._socket.close()
        self._socket = None
        self.closed()

    def closed(self):
        pass

    def connect(self):
        self._socket = socket.create_connection(('localhost', 3691))
        xml = self._socket.recv(4096).decode('utf-8')
        self.status = untangle.parse(xml)
        if int(self.status.status['code']) >= 400:
            raise ValueError(f"error {self.status.status['code']}: {self.status.status.cdata}")
        self.register()
        self.request_simzeit()
        self.connected()

    def connected(self):
        pass

    def _send_request(self, tag, **kwargs):
        args = [f"{k}='{v}'" for k, v in kwargs.items()]
        args = " ".join(args)
        req = f"<{tag} {args} />\n"
        self._socket.sendall(req.encode('utf-8'))
        rec = b""
        while True:
            rec = rec + self._socket.recv(4096)
            try:
                obj = untangle.parse(rec.decode('utf-8'))
                break
            except (SAXParseException, UnicodeDecodeError):
                pass
        return obj

    def get_sim_clock(self):
        return datetime.datetime.now() + self.time_offset

    def register(self):
        self.status = self._send_request("register", name=self.name, autor=self.autor, version=self.version,
                                         protokoll='1', text=self.text)
        self.check_status()

    def request_anlageninfo(self):
        response = self._send_request("anlageninfo")
        self.anlageninfo = AnlagenInfo()
        self.anlageninfo.update(response.anlageninfo)

    def request_bahnsteigliste(self):
        self.bahnsteigliste = {}
        response = self._send_request("bahnsteigliste")
        for bahnsteig in response.bahnsteigliste.bahnsteig:
            bi = BahnsteigInfo().update(bahnsteig)
            self.bahnsteigliste[bi.name] = bi

    def request_simzeit(self):
        self.client_datetime = datetime.datetime.now()
        simzeit = self._send_request("simzeit", sender=0)
        secs, msecs = divmod(int(simzeit.simzeit['zeit']), 1000)
        mins, secs = divmod(secs, 60)
        hrs, mins = divmod(mins, 60)
        t = datetime.time(hour=hrs, minute=mins, second=secs, microsecond=msecs * 1000)
        self.server_datetime = datetime.datetime.combine(self.client_datetime, t)
        self.time_offset = self.server_datetime - self.client_datetime

    def request_wege(self):
        response = self._send_request("wege")
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

    def request_zugdetails(self, zid=None):
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in zids:
            response = self._send_request("zugdetails", zid=zid)
            self.zugliste[zid].update(response.zugdetails)

    def request_zugfahrplan(self, zid=None):
        if zid is not None:
            zids = [zid]
        else:
            zids = self.zugliste.keys()
        for zid in zids:
            response = self._send_request("zugfahrplan", zid=zid)
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

    def request_zugliste(self):
        response = self._send_request("zugliste")
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
            knoten.zuege.sort(key=zugsortierschluessel(knoten.name, 'an', datetime.time()))


def zugsortierschluessel(gleis, attr, default):
    def caller(zugdetails):
        try:
            return getattr(zugdetails.find_fahrplanzeile(gleis), attr)
        except AttributeError:
            return default
    return caller


def test():
    client = PluginClient(name='test', autor='tester', version='0.0', text='testing the plugin client')
    client.connect()
    client.request_anlageninfo()
    client.request_bahnsteigliste()
    client.request_wege()
    client.request_zugliste()
    client.request_zugdetails()
    client.request_zugfahrplan()
    client.close()
    client.update_bahnsteig_zuege()
    client.update_wege_zuege()
    return client


if __name__ == '__main__':
    test()
