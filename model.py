import datetime


class AnlagenInfo:
    tag = 'anlageninfo'

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
    tag = 'bahnsteiginfo'

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
    tag = 'shape'

    TYP_NAME = {2: "Signal",
                3: "Weiche unten",
                4: "Weiche oben",
                5: "Bahnsteig",
                6: "Einfahrt",
                7: "Ausfahrt",
                12: "Haltepunkt"}

    TYP_NUMMER = {"Signal": 2,
                  "Weiche unten": 3,
                  "Weiche oben": 4,
                  "Bahnsteig": 5,
                  "Einfahrt": 6,
                  "Ausfahrt": 7,
                  "Haltepunkt": 12}

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
        return f"Knoten {self.key}: {self.TYP_NAME[self.typ]} {self.name}"

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
    tag = 'zugdetails'

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
        return f"Zug {self.name} von {self.von} nach {self.nach} ({self.verspaetung})"

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

    @property
    def gattung(self):
        try:
            l = self.name.split(" ")
            if len(l) > 1:
                return l[0]
            else:
                return ""
        except ValueError:
            return ""

    @property
    def nummer(self):
        try:
            return int(self.name.split(' ')[-1])
        except ValueError:
            return 0

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


class Ereignis(ZugDetails):
    """
    <ereignis zid='1' art='einfahrt' name='RE 10' verspaetung='+2' gleis='1' plangleis='1' von='A-Stadt' nach='B-Hausen' sichtbar='true' amgleis='true' />
    """
    tag = 'ereignis'

    arten = {'einfahrt', 'ankunft', 'abfahrt', 'ausfahrt', 'rothalt', 'wurdegruen', 'kuppeln', 'fluegeln'}

    def __init__(self):
        super().__init__()
        self.art = ""

    def __str__(self):
        if self.amgleis:
            return f"{self.art} gleis {self.gleis}: {self.name} von {self.von} nach {self.nach} ({self.verspaetung})"
        else:
            return f"{self.art}: {self.name} von {self.von} nach {self.nach} ({self.verspaetung})"

    def __repr__(self):
        return f"Ereignis({self.zid}, '{self.art}', '{self.name}', '{self.von}', '{self.nach}')"

    def update(self, ereignis):
        super().update(ereignis)
        self.art = ereignis['art']
        return self


class ZugFahrplanZeile:
    tag = 'gleis'

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
