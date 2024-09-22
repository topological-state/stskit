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
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Union
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


def format_minutes(minutes: Union[int, float]) -> str:
    """
    Minuten in Stunden:Minuten formatieren.

    :param minutes: Zeit in Minuten
    """
    minutes = round(minutes)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


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

    def update(self, item: Mapping) -> 'AnlagenInfo':
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
    Objektklasse für ein Gleisbildelement ("Knoten").

    Diese Klasse entspricht dem xml-Tag "shape".
    Verbindungen aus "connector"-Tags werden im Attribut `nachbarn` gespeichert.

    Bemerkungen
    -----------

    - Bahnsteige haben nur einen Namen.
      Alle anderen Tags haben eine enr-Nummer und einen Namen.
      Die enr ist fortlaufend über alle Elemente beginnend bei 1.
      Die enr hat nichts mit Signal- oder Weichennummern gemeinsam.
      Die enr wird, wo vorhanden, im connector-Tag verwendet.
      Bei Bahnsteigen wird der Name angegeben.
      Anschlüsse können den gleichen Namen wie ein Bahnsteig haben, da sie per enr identifiziert werden.
    - Da wir alle Elemente im gleichen Dictionary speichern wollen,
      deklariert diese klasse noch einen 'key', der den Knoten eindeutig identifiziert.
      Der key ist, wo deklariert, gleich der enr-Nummer und sonst gleich dem Namen.
    - Der Elementtyp wird numerisch gespeichert.
      Er kann mittels der Dicts TYP_NAME und TYP_NUMMER übersetzt werden.
    - In der Liste 'zuege', führt der Klient die Züge, die über das Gleiselement fahren
      (nur bei Einfahrten, Ausfahrten und Bahnsteigen).
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
        self.key: Optional[Union[int, str]] = None
        self.enr: Optional[int] = None
        self.name: Optional[str] = None
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

    def update(self, shape: Mapping) -> 'Knoten':
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
        try:
            self.typ = int(shape['type'])
        except TypeError:
            self.typ = 0
        if self.enr is not None:
            self.key = self.enr
        else:
            self.key = self.name
        return self

    @property
    def typ_name(self) -> str:
        return self.TYP_NAME[self.typ]


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
        # zids aller zuege, in deren flags dieser zug vorkommt. wird vom PluginClient aktualisiert
        self.stamm_zids: Set[int] = set([])

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

    def update(self, zugdetails: Mapping) -> 'ZugDetails':
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
        self.gleis = zugdetails['gleis'] or self.gleis
        self.plangleis = zugdetails['plangleis'] or self.plangleis
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

        die nummer ist der hinterste rein numerische teil des zugnamens, z.b. 8376 in "S8 8376 RF"
        diese hat nichts mit der zug-id zu tun.

        beispiele von zugnummern:
        - "536" -> 536
        - "ICE 624" -> 624
        - "S8 8376 RF" -> 8376
        - "S 8449 S12" -> 8449

        :return: (int) zugnummer. 0 falls der name keine ziffer enthält.
        """

        nummern = [int(part) for part in self.name.split() if part.isnumeric()]
        try:
            return nummern[-1]
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
            yield self.von.replace("Gleis ", "")
        for fpz in self.fahrplan:
            if plan:
                yield fpz.plan.replace("Gleis ", "")
            else:
                yield fpz.gleis.replace("Gleis ", "")
        if self.nach:
            yield self.nach.replace("Gleis ", "")

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

    def find_fahrplanzeile(self, gleis: Optional[str] = None, plan: Optional[str] = None,
                           zeit: Optional[datetime.time] = None) -> Optional['FahrplanZeile']:
        """
        Finde eine Fahrplanzeile nach Gleis und/oder Zeit.

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        Diese Methode ist ein Wrapper von find_fahrplan, der nur das Fahrplanobjekt zurückgibt.

        :param gleis: (str) Gleis (Gross-/Kleinschreibung egal)
        :param plan: (str) Plangleis (Gross-/Kleinschreibung egal)
        :param zeit: (datetime.time) Zeit, >= Ankunft und <= Abfahrt

        :return: FahrplanZeile-Objekt oder None.
        """

        _, zeile = self.find_fahrplan(gleis=gleis, plan=plan, zeit=zeit)
        return zeile

    def find_fahrplan_index(self, gleis: Optional[str] = None, plan: Optional[str] = None,
                            zeit: Optional[datetime.time] = None) -> Optional[int]:
        """
        Finde eine Fahrplanzeile nach Gleis und/oder Zeit.

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        Diese Methode ist ein Wrapper von find_fahrplan, der nur den Index zurückgibt.

        :param gleis: (str) Gleis (Gross-/Kleinschreibung egal)
        :param plan: (str) Plangleis (Gross-/Kleinschreibung egal)
        :param zeit: (datetime.time) Zeit, >= Ankunft und <= Abfahrt

        :return: Listenindex in Fahrplan oder None.
            Vorsicht: 0 ist ein gültiges Resultat.
        """

        index, _ = self.find_fahrplan(gleis=gleis, plan=plan, zeit=zeit)
        return index

    def find_fahrplan(self, gleis: Optional[str] = None, plan: Optional[str] = None,
                            zeit: Optional[datetime.time] = None) -> Tuple[Optional[int], Optional['FahrplanZeile']]:
        """
        Finde Index und Fahrplanzeile nach Gleis und/oder Zeit.

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        :param gleis: (str) Gleis (Gross-/Kleinschreibung egal)
        :param plan: (str) Plangleis (Gross-/Kleinschreibung egal)
        :param zeit: (datetime.time) Zeit, >= Ankunft und <= Abfahrt

        :return: Listenindex im Fahrplan und FahrplanZeile-Objekt.
                 Die Objekte sind None, wenn kein passender Eintrag gefunden wurde.
        """

        gleis = gleis.casefold() if gleis else None
        plan = plan.casefold() if plan else None

        for index, zeile in enumerate(self.fahrplan):
            if gleis and gleis != zeile.gleis.casefold():
                continue
            if plan and plan != zeile.plan.casefold():
                continue
            if zeit and zeile.an and zeit < zeile.an:
                continue
            if zeit and zeile.ab and zeit > zeile.ab:
                continue
            return index, zeile

        return None, None


class Ereignis(ZugDetails):
    """
    objektklasse für ereignisse.

    ein ereignis-tag von der plugin-schnittstelle sieht z.b. so aus:

    ~~~~~~{.xml}
    <ereignis zid='1' art='einfahrt' name='RE 10' verspaetung='+2' gleis='1' plangleis='1'
    von='A-Stadt' nach='B-Hausen' sichtbar='true' amgleis='true' />
    ~~~~~~

    der tag enthält dieselben daten wie ein zugdetails-tag und zusätzlich die art des ereignisses.
    die zeit wird vom PluginClient gesetzt.

    zusätzlich zu den von der plugin-schnittstelle gemeldeten ereignissen (in Ereignis.arten),
    erzeugt der PluginClient ein ereignis 'ersatz', wenn ein zug durch ersatz/nummernwechsel unsichtbar wird.
    der zugdetails-inhalt entspricht in diesem fall dem letzten ankunftsereignis, wobei sichtbar = False.
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

    def update(self, ereignis: Mapping) -> 'Ereignis':
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


class FahrplanZeileID(NamedTuple):
    zid: int
    zeit: int
    plan: str


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

        # übergeordnetes zug-objekt
        self.zug: ZugDetails = zug

        # diese attribut wird beim ersten property-aufruf erzeugt
        self._fid: Optional[FahrplanZeileID] = None

        # die folgenden attribute werden von der plugin-schnittstelle geliefert
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

    @property
    def fid(self) -> FahrplanZeileID:
        """
        Fahrplanziel-Identifikation

        Die Identifikation besteht aus den eindeutigen Attributen Zug-ID, Zeit in Minuten und Plangleis.
        Die ID wird beim ersten Gebrauch aus den genannten Attributen generiert und bleibt danach konstant.
        Das Property sollte daher nicht verwendet werden, bevor die Attribute ausgefüllt sind.

        Die Attribute an, ab und plan alleine sind (auch für einen Zug) nicht eindeutig:
        an oder ab können None sein, das Gleis kann mehrmals angefahren werden.
        an kann sich beim Nummernwechsel ändern.

        :return: Dreiertupel (zid, zeit, plan). zeit ist entweder die Ankunfts- oder Abfahrtszeit in Minuten.
        """

        if self._fid is None:
            try:
                zeit = time_to_minutes(self.an or self.ab)
            except (AttributeError, TypeError):
                zeit = 0
            self._fid = FahrplanZeileID(self.zug.zid, zeit, self.plan)

        return self._fid

    def __hash__(self) -> int:
        """
        Zugziel-Hash

        Der Hash basiert auf der fid.

        :return: Hash-Wert
        """

        return hash(self.fid)

    def __eq__(self, other: 'FahrplanZeile') -> bool:
        """
        gleichheit von zwei fahrplanzeilen feststellen.

        gleichheit bedeutet: gleicher zug und gleiches plangleis.
        jedes plangleis kommt im sts-fahrplan nur einmal vor.

        :param other: zu vergleichendes FahrplanZeile-objekt
        :return: True, wenn zug und plangleis übereinstimmen, sonst False
        """
        return self.zug.zid == other.zug.zid and self.plan == other.plan

    def __str__(self):
        if self.gleis == self.plan:
            return f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"FahrplanZeile({self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

    def update(self, item: Mapping) -> 'FahrplanZeile':
        """
        Daten von untangle-Element oder anderer FahrplanZeile übernehmen.

        Es werden nur die Attribute übernommen, die von der Pluginschnittstelle geliefert werden.

        :param item: eines von folgenden Objekten:
            - untangle.Element mit dem gleis-Tag von der Simulatorschnittstelle,
            - ein anderes FahrplanZeile-Objekt,
            - Dictionary mit Werten, die den Attributen dieser Klasse entsprechen.

        :return: self
        """

        if isinstance(item, self.__class__):
            item = item.__dict__

        if isinstance(item, untangle.Element):
            self.gleis = item['name']
        else:
            self.gleis = item['gleis']

        self.plan = item['plan']

        try:
            if item['an'] is None or isinstance(item['an'], datetime.time):
                self.an = item['an']
            else:
                self.an = datetime.time.fromisoformat(item['an'])
        except (TypeError, ValueError):
            self.an = None

        try:
            if item['an'] is None or isinstance(item['ab'], datetime.time):
                self.ab = item['ab']
            else:
                self.ab = datetime.time.fromisoformat(item['ab'])
        except (TypeError, ValueError):
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
