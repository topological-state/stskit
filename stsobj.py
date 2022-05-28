"""
objektklassen für die stellwerksim plugin-schnittstelle

dieses modul deklariert das datenmodell des plugin-klienten (stsplugin-modul).
die gliederung entspricht weitgehend der struktur der xml-daten von der schnittstelle.
für jedes tag gibt es eine klasse mit den tag-attributen.
die tag- und attributnamen sind ähnlich wie im xml-protokoll, es gibt aber abweichungen.
die daten werden in python-typen übersetzt.
einige der klassen haben noch zusätzliche attribute, die vom klienten ausgefüllt werden.

alle objekte werden leer konstruiert und über die update-methode mit daten gefüllt.
die update-methoden erwarten geparste xml-daten in untangle.Element objekten.
"""

import datetime
import logging
import networkx as nx
import numpy as np
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
import untangle

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def time_to_minutes(dt: Union[datetime.datetime, datetime.time, datetime.timedelta]) -> int:
    """
    uhrzeit in minuten seit mitternacht umrechnen.

    :param dt: datetime, time oder timedelta objekt. das datum wird ignoriert.
    :return: minuten, ganzzahlig
    :raise AttributeError wenn der typ nicht kompatibel oder None ist
    """
    try:
        # datetime, time
        return dt.hour * 60 + dt.minute + round(dt.second / 60)
    except AttributeError:
        # timedelta
        return round(dt.seconds / 60)


def time_to_seconds(dt: Union[datetime.datetime, datetime.time, datetime.timedelta]) -> int:
    """
    uhrzeit in sekunden seit mitternacht umrechnen.

    :param dt: datetime, time oder timedelta objekt. das datum wird ignoriert.
    :return: sekunden, ganzzahlig
    :raise AttributeError wenn der typ nicht kompatibel oder None ist
    """
    try:
        # datetime, time
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    except AttributeError:
        # timedelta
        return dt.seconds


def minutes_to_time(minutes: float) -> datetime.time:
    """
    minuten seit mitternacht in uhrzeit umrechnen.

    :param minutes: minuten seit mitternacht. dezimalstellen geben sekunden an.
    :return datetime.time objekt. auf ganze sekunden gerundet.
    """
    return seconds_to_time(minutes * 60)


def seconds_to_time(seconds: float) -> datetime.time:
    """
    sekunden seit mitternacht in uhrzeit umrechnen.

    :param seconds: sekunden seit mitternacht. dezimalstellen werden auf ganze sekunden gerundet.
    :return datetime.time objekt.
    """
    s = round(seconds)
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    return datetime.time(hour=h, minute=m, second=s)


def format_verspaetung(verspaetung: Optional[int]) -> str:
    if verspaetung is not None:
        if verspaetung:
            return f"{verspaetung:+}"
        else:
            return "0"
    else:
        return ""


class AnlagenInfo:
    """
    objektklasse für anlageninformationen.

    diese klasse entspricht dem xml-tag "anlageninfo".
    """

    # xml-tagname
    tag = 'anlageninfo'

    def __init__(self):
        super().__init__()
        self.aid: int = 0
        self.name: str = ""
        self.build: int = 0
        self.region: str = ""
        self.online: bool = False

    def __str__(self) -> str:
        network = "online" if self.online else "offline"
        return f"{self.region} - {self.name} ({self.aid}, {self.build}, {network})"

    def update(self, item: untangle.Element) -> 'AnlagenInfo':
        """
        attributwerte vom xml-dokument übernehmen.

        :param item: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        self.aid = int(item['aid'])
        self.name = item['name']
        self.build = int(item['simbuild'])
        self.region = item['region']
        self.online = str(item['online']).lower() == 'true'
        return self


class BahnsteigInfo:
    """
    objektklasse für bahnsteiginformationen.

    diese klasse entspricht dem xml-tag "bahnsteiginfo" mit eigenen ergänzungen.

    bemerkungen:
    - in der liste 'zuege', führt der klient die züge, die den bahnsteig in ihrem fahrplan haben.
    - die namen der nachbarbahnsteige wird in nachbar_namen gespeichert.
      der klient löst die namen in objekte auf und speichert sie in nachbarn.
    """

    # xml-tagname
    tag = 'bahnsteiginfo'

    def __init__(self):
        super().__init__()
        self.name: str = ""
        self.haltepunkt: bool = False
        self.nachbarn_namen: List[str] = []
        self.nachbarn: List['BahnsteigInfo'] = []
        self.zuege: List['ZugDetails'] = []

    def __str__(self) -> str:
        if self.haltepunkt:
            return f"Bahnsteig {self.name} (Haltepunkt)"
        else:
            return f"Bahnsteig {self.name}"

    def __repr__(self):
        return f"BahnsteigInfo {self.name}: haltepunkt={self.haltepunkt}"

    def update(self, item: untangle.Element) -> 'BahnsteigInfo':
        """
        attributwerte vom xml-dokument übernehmen.

        :param item: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        self.name = item['name']
        self.haltepunkt = str(item['haltepunkt']).lower() == 'true'
        try:
            self.nachbarn_namen = sorted([n['name'] for n in item.n])
        except AttributeError:
            self.nachbarn_namen = []
        self.nachbarn = []
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
        super().__init__()
        self.key: str = ""
        self.enr: int = 0
        self.name: str = ""
        self.typ: int = 0
        self.nachbarn: Set['Knoten'] = set()
        self.zuege: List['ZugDetails'] = []

    def __eq__(self, other: 'Knoten') -> bool:
        return self.key.__eq__(other.key)

    def __hash__(self) -> int:
        return self.key.__hash__()

    def __str__(self) -> str:
        return f"Knoten {self.key}: {self.TYP_NAME[self.typ]} {self.name}"

    def __repr__(self) -> str:
        return f"Knoten('{self.key}': enr={self.enr}, typ={self.typ}, name='{self.name}')"

    def update(self, shape: untangle.Element) -> 'Knoten':
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
        super().__init__()
        self.zid: int = 0
        self.name: str = ""
        self.von: str = ""
        self.nach: str = ""
        self.verspaetung: int = 0
        self.sichtbar: bool = False
        self.gleis: str = ""
        self.plangleis: str = ""
        self.amgleis: bool = False
        self.hinweistext: str = ""
        self.usertext: str = ""
        self.usertextsender: str = ""
        self.fahrplan: List['FahrplanZeile'] = []
        # index des aktuellen ziels. wird vom PluginClient aktualisiert
        self.ziel_index: Optional[int] = None
        # zeigt an, ob der zug im flag eines anderen vorkommt. wird vom PluginClient aktualisiert
        self.stammzug: Optional[ZugDetails] = None

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

    def update(self, zugdetails: untangle.Element) -> 'ZugDetails':
        """
        attributwerte vom xml-dokument übernehmen.

        der fahrplan wird von dieser methode nicht berührt.

        :param zugdetails: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        self.zid = int(zugdetails['zid'])
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
    def nummer(self) -> int:
        """
        zugnummer aus dem zugnamen.

        die nummer ist der hinterste numerische teil des zugnamens, z.b. 8376 in "S8 8376 RF"

        diese hat nichts mit der zug-id zu tun.

        :return: (int) zugnummer. 0 falls der name keine ziffer enthält.
        """

        s = "".join((c for c in self.name if c.isnumeric() or c == " "))
        try:
            return int(s.rsplit(maxsplit=1)[-1])
        except (IndexError, ValueError):
            return 0

    @property
    def ist_rangierfahrt(self) -> bool:
        """
        zug ist eine rangierfahrt (Lok, Ersatzlok oder RF)

        :return:
        """

        return self.name.startswith('Lok') or self.name.startswith('Ersatzlok') or \
               self.name.startswith('RF') or self.name.endswith('RF')

    def route(self, plan: bool = False) -> Iterable[str]:
        """
        route (reihe von stationen) des zuges als generator

        die route ist eine liste von stationen (gleisen, ein- und ausfahrt) in der reihenfolge des fahrplans.
        ein- und ausfahrten können bei ersatzzügen o.ä. fehlen.
        durchfahrtsgleise sind auch enthalten.

        :param plan: plangleise statt effektive gleise melden
        :return: generator
        """
        if self.von:
            yield self.von
        for fpz in self.fahrplan:
            if plan:
                yield fpz.plan
            else:
                yield fpz.gleis
        if self.nach:
            yield self.nach

    def graph(self) -> nx.DiGraph:
        """
        fahrplan im networkx directed graph format

        die knoten sind anschluss- oder gleisnamen und haben folgende attribute:
        typ: 'anschluss' oder 'gleis'
        an: ankunftszeit als datetime.time (kann fehlen)
        ab: ankunftszeit als datetime.time (kann fehlen)
        aufenthalt: aufenthaltszeit in sekunden (kann fehlen)

        die kanten haben folgende attribute:
        fahrzeit: planmässige fahrzeit in sekunden (kann fehlen)

        :return: nx.DiGraph
        """
        graph = nx.DiGraph()

        start = self.von
        startzeit = np.nan
        if start:
            graph.add_node(start, typ='anschluss')

        for zeile in self.fahrplan:
            ziel = zeile.gleis
            try:
                ankunftszeit = time_to_seconds(zeile.an)
            except AttributeError:
                ankunftszeit = np.nan
            try:
                abfahrtszeit = time_to_seconds(zeile.ab)
            except AttributeError:
                abfahrtszeit = np.nan

            if ziel:
                aufenthalt = abfahrtszeit - ankunftszeit if not zeile.durchfahrt() else 0
                graph.add_node(ziel, typ='gleis')
                if zeile.an:
                    graph.nodes[ziel]['an'] = zeile.an
                if zeile.ab:
                    graph.nodes[ziel]['ab'] = zeile.ab
                if not np.isnan(aufenthalt):
                    graph.nodes[ziel]['aufenthalt'] = aufenthalt

                if start:
                    fahrzeit = ankunftszeit - startzeit
                    graph.add_edge(start, ziel)
                    if not np.isnan(fahrzeit):
                        graph.edges[start][ziel]['fahrzeit'] = fahrzeit

            start = ziel
            startzeit = abfahrtszeit

        ziel = self.nach
        if ziel:
            graph.add_node(ziel, typ='anschluss')
            if start:
                graph.add_edge(start, ziel)

        return graph

    def find_fahrplanzeile(self, gleis: Optional[str] = None, plan: Optional[str] = None) -> Optional['FahrplanZeile']:
        """
        finde erste fahrplanzeile, in der ein bestimmtes gleis vorkommt.

        man kann entweder nach dem aktuellen gleis, dem plangleis oder beiden gleichzeitig suchen.

        :param gleis: (str)
        :param plan: (str)

        :return: FahrplanZeile objekt oder None.
        """
        for zeile in self.fahrplan:
            if (not gleis or gleis == zeile.gleis) and (not plan or plan == zeile.plan):
                return zeile
        return None

    def find_fahrplan_index(self, gleis: Optional[str] = None, plan: Optional[str] = None) -> Optional[int]:
        """
        finde den index der ersten fahrplanzeile, in der ein bestimmtes gleis vorkommt.

        man kann entweder nach dem aktuellen gleis, dem plangleis oder beiden gleichzeitig suchen.

        :param gleis: (str)
        :param plan: (str)

        :return: index in fahrplan-liste oder None.
        """
        for index, zeile in enumerate(self.fahrplan):
            if (not gleis or gleis == zeile.gleis) and (not plan or plan == zeile.plan):
                return index
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
    # attribute, wie im xml-verwendet
    attribute = ['zeit', 'zid', 'art', 'name', 'verspaetung', 'gleis', 'plangleis', 'von', 'nach', 'sichtbar',
                 'amgleis']

    def __init__(self):
        super().__init__()
        self.art: str = ""
        self.zeit: datetime.datetime = datetime.datetime.fromordinal(1)

    def __str__(self) -> str:
        return self.art + " " + super().__str__()

    def __repr__(self) -> str:
        return f"Ereignis({self.zid}, {self.art}, {self.name}, {self.von}, {self.nach}, {self.verspaetung:+}," \
               f"{self.sichtbar}, {self.gleis}/{self.plangleis}, {self.amgleis})"

    def __eq__(self, other: 'Ereignis') -> bool:
        """
        sind zwei ereignisse gleich?

        ereignisse werden als gleich erachtet, wenn art, zid und gleis gleich sind.
        dies kann dazu benutzt werden, wiederholte ereignismeldungen zu filtern.
        (die plugin-schnittstelle schickt gewisse ereignismeldungen wie rothalt und abfahrt wiederholt.)

        :param other:
        :return: bool
        """
        return self.art == other.art and self.zid == other.zid and self.gleis == other.gleis

    def __hash__(self) -> int:
        """
        hash-funktion basierend auf gleichheitsklasse.

        ereignisse werden als gleich erachtet, wenn art, zid und gleis gleich sind.
        für solchermassen "gleiche" ereignisse generiert diese funktion den gleichen hash-wert.
        dies kann dazu benutzt werden, wiederholte ereignismeldungen zu filtern.
        (die plugin-schnittstelle schickt gewisse ereignismeldungen wie rothalt und abfahrt wiederholt.)

        :return: int
        """
        return (self.art, self.zid, self.gleis).__hash__()

    def update(self, ereignis: untangle.Element) -> 'Ereignis':
        """
        attributwerte vom xml-dokument übernehmen.

        :param ereignis: dictionary mit den attributen aus dem xml-tag.

        :return: self
        """
        super().update(ereignis)
        self.art = ereignis['art']
        return self

    def to_dict(self) -> Dict:
        return {attr: getattr(self, attr) for attr in self.attribute}


class FahrplanZeile:
    """
    fahrplanzeile

    flags:
    - A: vorzeitige abfahrt
    - Bn: themenflag
    - D: durchfahrt
    - E(zid): ersatzzug
    - F(zid): flügeln
    - K(zid): kuppeln
    - L: lokumlauf
    - P: anfangsaufstellungsplatz
    - R: richtungsänderung
    - W[enr][enr]: lokwechsel
    """
    tag = 'gleis'

    def __init__(self, zug: ZugDetails):
        super().__init__()
        self.zug: ZugDetails = zug
        self.gleis: str = ""
        self.plan: str = ""
        self.an: Optional[datetime.time] = None
        self.ab: Optional[datetime.time] = None
        self.flags: str = ""
        self.hinweistext: str = ""

        # die nächsten drei attribute werden vom PluginClient anhand der flags aufgelöst.
        self.ersatzzug: Optional[ZugDetails] = None
        self.fluegelzug: Optional[ZugDetails] = None
        self.kuppelzug: Optional[ZugDetails] = None

    def __str__(self):
        if self.gleis == self.plan:
            return f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"FahrplanZeile({self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

    def update(self, item: untangle.Element) -> 'FahrplanZeile':
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

    def durchfahrt(self) -> bool:
        """
        zeigt das durchfahrt-flag an.

        :return: bool
        """
        return 'D' in self.flags

    def ersatz_zid(self) -> Optional[int]:
        """
        liest die zid aus dem ersatzzug-flag.

        die zid kann vom plugin-client zum ersatzzug-attribut aufgelöst werden.
        """
        mo = re.search(r"E[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def fluegel_zid(self) -> Optional[int]:
        """
        liest die zid aus dem fluegel-flag.

        die zid kann vom plugin-client zum fluegelzug-attribut aufgelöst werden.
        """
        mo = re.search(r"F[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def kuppel_zid(self) -> Optional[int]:
        """
        liest die zid aus dem kuppel-flag.

        die zid kann vom plugin-client zum kuppelzug-attribut aufgelöst werden.
        """
        mo = re.search(r"K[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def lokumlauf(self) -> bool:
        """
        zeigt das lokumlauf-flag an.

        :return: bool
        """
        return 'L' in self.flags

    def lokwechsel(self) -> Optional[Tuple[int, int]]:
        """
        zeigt das lokwechsel-flag an.

        :return: zweier-tuple mit element-nummern der ein- und ausfahrten (beliebige reihenfolge) oder None.
        """
        mo = re.search(r"W\[([0-9]+)]\[([0-9]+)]", self.flags)
        if mo:
            return int(mo.group(1)), int(mo.group(2))
        else:
            return None

    def richtungswechsel(self) -> bool:
        """
        zeigt das richtungswechsel-flag an.

        :return: bool
        """
        return 'R' in self.flags

    def vorzeitige_abfahrt(self) -> bool:
        """
        zeigt das vorzeitige-abfahrt-flag an.

        :return: bool
        """
        return 'A' in self.flags
