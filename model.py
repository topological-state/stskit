"""
datenmodell für plugin-client

dieses modul deklariert das datenmodell des plugin-klienten.
die gliederung entspricht dabei weitgehend der struktur der xml-daten von der schnittstelle.
für jedes tag gibt es eine klasse.
die attribute der klassen haben die gleichen namen wie die das entsprechende tag.
die daten werden in python-typen übersetzt.

einige der klassen haben noch zusätzliche attribute, die vom klienten ausgefüllt werden.
"""

import datetime
from typing import Dict, List, Optional, Union


class AnlagenInfo:
    """
    objektklasse für anlageninformationen.

    diese klasse entspricht dem xml-tag "anlageninfo".
    """

    # xml-tagname
    tag = 'anlageninfo'

    def __init__(self):
        self.aid = ""
        self.name = ""
        self.build = 0
        self.region = ""
        self.online = False

    def update(self, item: Dict) -> 'AnlagenInfo':
        """
        attributwerte vom xml-dokument übernehmen.

        :param item: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        self.aid = item['aid']
        self.name = item['name']
        self.build = item['simbuild']
        self.region = item['region']
        self.online = str(item['online']).lower() == 'true'
        return self


class BahnsteigInfo:
    """
    objektklasse für bahnsteiginformationen.

    diese klasse entspricht dem xml-tag "bahnsteiginfo" mit eigenen ergänzungen.

    bemerkungen:
    - in der liste 'zuege', führt der klient die züge, die den bahnsteig in ihrem fahrplan haben.
    - die genaue bedeutung der nachbarn habe ich noch nicht verstanden.
      die namen der nachbarn werden in der aktuellen version unverarbeitet übernommen.
    """

    # xml-tagname
    tag = 'bahnsteiginfo'

    def __init__(self):
        self.name = ""
        self.haltepunkt = False
        self.nachbarn = set()
        self.zuege = []

    def __str__(self) -> str:
        if self.haltepunkt:
            return f"Bahnsteig {self.name} (Haltepunkt)"
        else:
            return f"Bahnsteig {self.name}"

    def __repr__(self):
        return f"BahnsteigInfo {self.name}: haltepunkt={self.haltepunkt}"

    def update(self, item: Dict) -> 'BahnsteigInfo':
        """
        attributwerte vom xml-dokument übernehmen.

        :param item: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        self.name = item['name']
        self.haltepunkt = str(item['haltepunkt']).lower() == 'true'
        try:
            self.nachbarn = {n['name'] for n in item.n}
        except AttributeError:
            self.nachbarn = set()
        return self


class Knoten:
    """
    objektklasse für ein gleisbildelement ("knoten").

    diese klasse entspricht dem xml-tag "shape" mit eigenen ergänzungen.

    bemerkungen:
    - einige shape-tags haben nur enr-nummern, andere nur einen namen, einige beides.
      da wir alle elemente im gleichen dictionary speichern wollen,
      deklariert diese klasse noch einen 'key',
      der wo möglich aus der enr-nummer (in str-repräsentation) und sonst aus dem namen besteht.
    - der elementtyp wird numerisch gespeichert.
      er kann mittels der dicts TYP_NAME und TYP_NUMMER übersetzt werden.
    - in der liste 'zuege', führt der klient die züge, die über das gleiselement fahren
      (nur bei einfahrten, ausfahrten und bahnsteigen).
    """

    # xml-tagname
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

    def __eq__(self, other: 'Knoten') -> bool:
        return self.key.__eq__(other.key)

    def __hash__(self) -> int:
        return self.key.__hash__()

    def __str__(self) -> str:
        return f"Knoten {self.key}: {self.TYP_NAME[self.typ]} {self.name}"

    def __repr__(self) -> str:
        return f"Knoten('{self.key}': enr={self.enr}, typ={self.typ}, name='{self.name}')"

    def update(self, shape: Dict) -> 'Knoten':
        """
        attributwerte vom xml-dokument übernehmen.

        :param shape: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
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
    """
    objektklasse für zugdetails.

    die attribute entsprechen dem zugdetails-tag der plugin-schnittstelle.
    """

    # xml-tagname
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

    def __eq__(self, other: 'ZugDetails') -> bool:
        return self.zid.__eq__(other.zid)

    def __hash__(self) -> int:
        return self.zid.__hash__()

    def __str__(self) -> str:
        """
        einfach lesbare beschreibung

        zeigt den zugnamen, von/nach, das nächste gleis, die verspätung und unsichtbarkeit an.

        :return: (str)
        """
        if self.gleis:
            gleis = self.gleis
            if self.gleis != self.plangleis:
                gleis = gleis + '/' + self.plangleis + '/'
            if self.amgleis:
                gleis = '[' + gleis + ']'
        else:
            gleis = ''

        sichtbar = "" if self.sichtbar else " (unsichtbar)"

        return f"{self.name}: {self.von} - {gleis} - {self.nach} ({self.verspaetung:+}){sichtbar}"

    def __repr__(self) -> str:
        return f"ZugDetails({self.zid}, {self.name}, {self.von}, {self.nach}, {self.verspaetung:+}," \
               f"{self.sichtbar}, {self.gleis}/{self.plangleis}, {self.amgleis})"

    def update(self, zugdetails: Dict) -> 'ZugDetails':
        """
        attributwerte vom xml-dokument übernehmen.

        der fahrplan wird von dieser methode nicht berührt.

        :param zugdetails: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
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
        self.sichtbar = str(zugdetails['sichtbar']).lower() == 'true'
        self.amgleis = str(zugdetails['amgleis']).lower() == 'true'
        self.usertext = zugdetails['usertext']
        self.usertextsender = zugdetails['usertextsender']
        self.hinweistext = zugdetails['hinweistext']
        return self

    @property
    def gattung(self) -> Optional[str]:
        """
        zuggattung aus dem zugnamen.

        die zuggattung ist der alphabetische präfix aus dem zugnamen, z.b "ICE".
        für eine spätere version ist geplant, die gattung anhand der region und zugnummer zu bestimmen,
        wo der präfix fehlt.

        :return: (str) zuggattung. None, wenn keine gattung bestimmt werden kann.
        """
        try:
            l = self.name.split(" ")
            if len(l) > 1:
                return l[0]
            else:
                return None
        except ValueError:
            return None

    @property
    def nummer(self) -> Optional[int]:
        """
        zugnummer aus dem zugnamen.

        die nummer ist der hinterste numerische teil des zugnamens, z.b. 8376 in "S8 8376 RF"

        diese hat nichts mit der zug-id zu tun.

        :return: (int) zugnummer. None
        """
        for s in reversed(self.name.split(' ')):
            try:
                # falls es noetig ist, buchstaben zu entfernen:
                # s = "".join((c for c in s if c.isnumeric()))
                return int(s)
            except ValueError:
                pass
        return None

    def find_fahrplanzeile(self, gleis: str) -> Optional['FahrplanZeile']:
        """
        finde erste fahrplanzeile, in der gleis als aktuelles gleis vorkommt.

        :param gleis: (str)

        :return: FahrplanZeile objekt oder None.
        """
        for zeile in self.fahrplan:
            if gleis == zeile.gleis:
                return zeile
        return None


class Ereignis(ZugDetails):
    """
    objektklasse für ereignisse.

    ein ereignis-tag von der plugin-schnittstelle sieht z.b. so aus:

    ~~~~~~{.xml}
    <ereignis zid='1' art='einfahrt' name='RE 10' verspaetung='+2' gleis='1' plangleis='1'
    von='A-Stadt' nach='B-Hausen' sichtbar='true' amgleis='true' />
    ~~~~~~

    der tag enthält dieselben daten wie ein zugdetails-tag und zusätzlich die art des ereignisses.
    """

    # xml-tagname
    tag = 'ereignis'

    # ereginisarten, wie im xml-verwendet
    arten = {'einfahrt', 'ankunft', 'abfahrt', 'ausfahrt', 'rothalt', 'wurdegruen', 'kuppeln', 'fluegeln'}

    def __init__(self):
        super().__init__()
        self.art = ""

    def __str__(self) -> str:
        return self.art + " " + super().__str__()

    def __repr__(self) -> str:
        return f"Ereignis({self.zid}, {self.art}, {self.name}, {self.von}, {self.nach}, {self.verspaetung:+}," \
               f"{self.sichtbar}, {self.gleis}/{self.plangleis}, {self.amgleis})"

    def update(self, ereignis: Dict) -> 'Ereignis':
        """
        attributwerte vom xml-dokument übernehmen.

        :param ereignis: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        super().update(ereignis)
        self.art = ereignis['art']
        return self


class FahrplanZeile:
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
        return f"FahrplanZeile({self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

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
