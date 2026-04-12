"""
Objektklassen für die Stellwerksim Pluginschnittstelle

Dieses Modul deklariert das Datenmodell des Pluginklienten (`stsplugin`-Modul).
Die Gliederung entspricht weitgehend der Struktur der xml-Daten von der Schnittstelle.
Für jedes Tag gibt es eine Klasse mit den Tag-Attributen.
Die Tag- und Attributnamen sind ähnlich wie im xml-Protokoll, es gibt aber Abweichungen.
Die Daten werden in Python-Typen übersetzt.
Einige der Klassen haben noch zusätzliche Attribute, die vom Klienten ausgefüllt werden.

Alle Objekte werden leer konstruiert und über die update-Methode mit Daten gefüllt.
Die update-Methoden erwarten geparste xml-Daten in einem untangle.Element-Objekt.
"""

from __future__ import annotations
from collections.abc import Iterable, Mapping, Generator
import datetime
import logging
import networkx as nx
import numpy as np
import re
from typing import NamedTuple
import untangle
import weakref

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def time_to_minutes(dt: datetime.datetime | datetime.time | datetime.timedelta) -> int:
    """
    Uhrzeit in Minuten seit Mitternacht umrechnen.

    Args:
        dt: Das Datum wird ignoriert.

    Returns:
        Minuten, ganzzahlig

    Raises:
        AttributeError: Typ nicht kompatibel oder None.
    """
    try:
        # datetime, time
        return dt.hour * 60 + dt.minute + round(dt.second / 60)
    except AttributeError:
        # timedelta
        return round(dt.seconds / 60)


def time_to_seconds(dt: datetime.datetime | datetime.time | datetime.timedelta) -> int:
    """
    Uhrzeit in Sekunden seit Mitternacht umrechnen.

    Args:
        dt: Das Datum wird ignoriert.

    Returns:
        Sekunden, ganzzahlig

    Raises:
        AttributeError: Typ nicht kompatibel oder None.
    """
    try:
        # datetime, time
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    except AttributeError:
        # timedelta
        return dt.seconds


def minutes_to_time(minutes: float) -> datetime.time:
    """
    Minuten seit Mitternacht in Uhrzeit umrechnen.

    Args:
        minutes: Minuten seit Mitternacht. Dezimalstellen geben Sekunden an.

    Returns:
        Zeit als `datetime.time` auf ganze Sekunden gerundet.
    """
    return seconds_to_time(minutes * 60)


def seconds_to_time(seconds: float) -> datetime.time:
    """
    Sekunden seit Mitternacht in Uhrzeit umrechnen.

    Args:
        seconds: Sekunden seit Mitternacht. Dezimalstellen werden auf ganze Sekunden gerundet.

    Returns:
        Zeit als `datetime.time` auf ganze Sekunden gerundet.
    """
    s = round(seconds)
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    return datetime.time(hour=h, minute=m, second=s)


def format_verspaetung(verspaetung: int | float | None) -> str:
    """
    Verspätung formatieren.
    """
    if verspaetung is not None:
        if abs(verspaetung) >= 0.5:
            return f"{int(verspaetung):+}"
        else:
            return "0"
    else:
        return ""


def format_minutes(minutes: int | float) -> str:
    """
    Minuten in Stunden:Minuten formatieren.

    Params:
        minutes: Zeit in Minuten

    Returns:
        Formatierte Zeit
    """
    minutes = round(minutes)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


class AnlagenInfo:
    """
    Anlageninformationen.

    Diese Klasse entspricht dem xml-Tag "anlageninfo".

    Attributes:
        aid: Nummer des Stellwerks.
        name: Name des Stellwerks.
        build: Build-Nummer von Stellwerksim.
        region: Name der Region.
        online: Online-Spiel (True) oder Sandbox (False).
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

    def update(self, item: Mapping) -> AnlagenInfo:
        """
        Attribute vom xml-Dokument übernehmen.

        Args:
            item: Dictionary mit den Attributen aus dem xml-Tag.

        Returns:
            AnlagenInfo-Objekt
        """
        self.aid = int(item['aid'])
        self.name = str(item['name']).strip()
        self.build = int(item['simbuild'])
        self.region = item['region']
        self.online = str(item['online']).lower() == 'true'
        return self


class BahnsteigInfo:
    """
    Bahnsteiginformationen.

    Diese Klasse entspricht dem xml-Tag "bahnsteig" mit den Ergänzungen `nachbarn` und `zuege`.

    Attributes:
        name: Name des Bahnsteigs.
        haltepunkt: Haltepunkt (True) oder Bahnhofgleis (False).
            Bestimmt, ob eine Fahrstrasse beim Halt aufgelöst wird (False) oder nicht (True).
            Hat in STSdispo keine bedeutung.
        nachbarn_namen: Namen von Nachbarbahnsteigen.
            Alle miteinander verbundenen Nachbarbahnsteige bilden in STSdispo einen _Bahnhofteil_.
        nachbarn: Dictionary von BahnsteigInfo-Objekten nach Namen.
        zuege: Liste von Zügen, die den Bahnsteig in ihrem Fahrplan haben (disponiertes Gleis).
            Diese Liste wird nicht automatisch gefüllt.
            Um sie zu nutzen, muss sie durch Aufruf von [stskit.plugin.stsplugin.PluginClient.update_bahnsteig_zuege]
            explizit gefüllt werden.
    """

    # xml-tagname
    tag = 'bahnsteig'

    def __init__(self):
        super().__init__()
        self.name: str = ""
        self.haltepunkt: bool = False
        self.nachbarn_namen: list[str] = []
        self.nachbarn: weakref.WeakValueDictionary[str, BahnsteigInfo] = weakref.WeakValueDictionary()
        self.zuege: weakref.WeakValueDictionary[int, ZugDetails] = weakref.WeakValueDictionary()

    def __str__(self) -> str:
        if self.haltepunkt:
            return f"Bahnsteig {self.name} (Haltepunkt)"
        else:
            return f"Bahnsteig {self.name}"

    def __repr__(self):
        return f"BahnsteigInfo {self.name}: haltepunkt={self.haltepunkt}"

    def update(self, item: untangle.Element) -> BahnsteigInfo:
        """
        Attribute vom xml-Dokument übernehmen.

        Die Namen der Nachbarbahnsteige werden in `nachbarn_namen` gespeichert.
        Die `nachbarn` und `zuege` Attribute sind möglicherweise veraltet.

        Args:
            item: Dictionary mit den Attributen aus dem xml-Tag.

        Returns:
            Self
        """

        self.name = str(item['name']).strip()
        self.haltepunkt = str(item['haltepunkt']).lower() == 'true'
        try:
            self.nachbarn_namen = sorted([str(n['name']).strip() for n in item.n])
        except AttributeError:
            self.nachbarn_namen = []

        return self


class Knoten:
    """
    Gleisbildelement ("Knoten").

    Diese Klasse entspricht dem xml-Tag `shape` aus dem `wege`-Tag.
    Verbindungen aus `connector`-Tags werden im Attribut `nachbarn` gespeichert.

    Bahnsteige haben nur einen Namen.
    Alle anderen Tags haben eine `enr`-Nummer und einen Namen.
    Die `enr` ist fortlaufend über alle Elemente beginnend bei 1.
    Die `enr` hat nichts mit Signal- oder Weichennummern gemeinsam.
    Die `enr` wird, wo vorhanden, im `connector`-Tag verwendet.
    Bei Bahnsteigen wird der Name angegeben.
    Anschlüsse können den gleichen Namen wie ein Bahnsteig haben, da sie per `enr` identifiziert werden.

    Da wir alle Elemente im gleichen Dictionary speichern wollen,
    deklariert diese klasse noch einen `key`, der den Knoten eindeutig identifiziert.
    Der `key` ist, wo deklariert, gleich der `enr`-Nummer und sonst gleich dem Namen.

    Attributes:
        key: Entspricht `enr` falls definiert, sonst `name`.
            Bahnsteige und Haltepunkte haben nur einen Namen,
            die anderen Elemente haben sowohl eine Nummer und einen Namen.
            Dieses Attribut für jedes Element definiert und eindeutig.
        enr: `enr`-Nummer vom Simulator, falls deklariert, sonst None.
            Bahnsteige und Haltepunkte haben keine `enr`.
        name: `name` vom Simulator, falls deklariert, sonst None.
            Es kann mehrere Elemente mit dem gleichen Namen geben (z.B. Anschluss und Bahnsteig).
        typ: Typnummer, s. `TYP_NAME` oder `TYP_NUMMER`.
        nachbarn: Nachbarelemente aus den `connector`-Tags.
        zuege: Züge, die über das Gleiselement fahren
            (nur bei Einfahrten, Ausfahrten, Bahnsteigen und Haltepunkten).
            Diese Liste wird nicht automatisch gefüllt.
            Um sie zu nutzen, muss sie durch Aufruf von [stskit.plugin.stsplugin.PluginClient.update_wege_zuege]
            explizit gefüllt werden.
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
        self.key: int | str | None = None
        self.enr: int | None = None
        self.name: str | None = None
        self.typ: int = 0
        self.nachbarn: weakref.WeakValueDictionary[int | str, Knoten] = weakref.WeakValueDictionary()
        self.zuege: weakref.WeakValueDictionary[int, ZugDetails] = weakref.WeakValueDictionary()

    def __eq__(self, other: Knoten) -> bool:
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __str__(self) -> str:
        return f"Knoten {self.key}: {self.TYP_NAME[self.typ]} {self.name}"

    def __repr__(self) -> str:
        return f"Knoten('{self.key}': enr={self.enr}, typ={self.typ}, name='{self.name}')"

    def update(self, shape: Mapping) -> Knoten:
        """
        Attributwerte vom xml-Dokument übernehmen.

        Args:
            shape: Mapping mit den Attributen aus dem xml-Tag.

        Returns:
            self
        """

        try:
            self.enr = int(shape['enr'])
        except TypeError:
            self.enr = None
        try:
            self.name = str(shape['name']).strip()
        except TypeError:
            self.name = None
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
    Zugdetails.

    Die Attribute entsprechen dem `zugdetails`-Tag der Pluginschnittstelle
    mit den Ergänzungen `ziel_index` und `stamm_zids`.

    Attributes:
        zid: Identifikationsnummer.
            Die zid ist für den Anwender verborgen.
            Die zid kann negativ sein (z.B. Ersatzloks).
        name: Zugname (Gattung + Nummer + ev. andere Zusätze)
        von: Herkunft (Name des Gleises)
        nach: Endziel (Name des Gleises)
        verspaetung: Verspätung (oder Verfrühung, wenn negativ) in Minuten
        sichtbar: Zug ist im Stellwerk.
        gleis: Nächstes, disponiertes Zielgleis.
            Umgeleitete und ausfahrende Züge haben kein Zielgleis.
        plangleis: Nächstes Zielgleis nach Fahrplan.
            Umgeleitete und ausfahrende Züge haben kein Plangleis.
        amgleis: Zug steht am Gleis `gleis`.
        hinweistext:
        usertext:
        usertextsender:
        fahrplan: Fahrplaneinträge.
        ziel_index: Fahrplanindex des aktuellen Ziels.
            Wird vom PluginClient aktualisiert.
        stamm_zids: Menge von `zid` aller Züge, in deren Flags dieser Zug vorkommt.
            Wird vom PluginClient aktualisiert.
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
        self.fahrplan: list[FahrplanZeile] = []
        self.ziel_index: int | None = None
        self.stamm_zids: set[int] = set()

    def __eq__(self, other: ZugDetails) -> bool:
        return self.zid == other.zid

    def __hash__(self) -> int:
        return hash(self.zid)

    def __str__(self) -> str:
        """
        Einfach lesbare Beschreibung

        Zeigt den Zugnamen, von/nach, das nächste Gleis, die Verspätung und Unsichtbarkeit an.

        Returns:
            Beschreibung als String.
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

    def update(self, zugdetails: Mapping) -> ZugDetails:
        """
        Attributwerte vom xml-Dokument übernehmen.

        Der Fahrplan wird von dieser Methode nicht berührt.

        Args:
            zugdetails: Mapping mit den Attributen aus dem xml-Tag.

        Returns:
            self
        """
        self.zid = int(zugdetails['zid'])
        self.name = str(zugdetails['name']).strip()
        try:
            self.verspaetung = int(zugdetails['verspaetung'])
        except TypeError:
            pass
        # todo: ausfahrende Züge haben kein gleis und plangleis. umgeleitete auch nicht.
        self.gleis = str(zugdetails['gleis']).strip() or self.gleis
        self.plangleis = str(zugdetails['plangleis']).strip() or self.plangleis
        self.von = str(zugdetails['von']).strip()
        self.nach = str(zugdetails['nach']).strip()
        self.sichtbar = str(zugdetails['sichtbar']).lower() == 'true'
        self.amgleis = str(zugdetails['amgleis']).lower() == 'true'
        self.usertext = str(zugdetails['usertext'])
        self.usertextsender = str(zugdetails['usertextsender'])
        self.hinweistext = str(zugdetails['hinweistext'])
        return self

    @property
    def gattung(self) -> str | None:
        """
        Zuggattung aus dem Zugnamen.

        Die Zuggattung ist das alphabetische Präfix aus dem Zugnamen, z.B. "ICE".
        In gewissen Regionen wie z.B. der Schweiz oder Grossbritannien fehlt dieses Präfix.

        Returns:
            Zuggattung. None, wenn keine Gattung bestimmt werden kann.
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
        Zugnummer aus dem Zugnamen.

        Die Nummer ist der hinterste rein numerische Teil des Zugnamens, z.b. 8376 in "S8 8376 RF"
        Diese hat nichts mit der `zid` zu tun.

        Beispiele von Zugnummern:
        - "536": 536
        - "ICE 624": 624
        - "S8 8376 RF": 8376
        - "S 8449 S12": 8449

        Returns:
            Zugnummer. 0, falls der Name keine Ziffer enthält.
        """

        nummern = [int(part) for part in self.name.split() if part.isnumeric()]
        try:
            return nummern[-1]
        except (IndexError, ValueError):
            return 0

    @property
    def ist_rangierfahrt(self) -> bool:
        """
        Rangierfahrt anzeigen.

        Als Rangierfahrten gelten Züge, die den Zusatz Lok, Ersatzlok oder RF im Namen tragen.

        Returns:
            True, wenn der Zug eine Rangierfahrt darstellt.
        """

        return self.name.startswith('Lok') or self.name.startswith('Ersatzlok') or \
               self.name.startswith('RF') or self.name.endswith('RF')

    def route(self, plan: bool = False) -> Generator[str, None, None]:
        """
        Route (Reihe von Stationen) des Zuges als Generator

        Die Route ist eine Liste von Stationen (Gleisen, inkl. Ein- und Ausfahrt) in der Reihenfolge des Fahrplans.
        Ein- und Ausfahrten können bei Ersatzzügen o.ä. fehlen.
        Durchfahrtsgleise sind auch enthalten.

        Ein etwaiges Präfix 'Gleis' bei Nummernwechsel wird entfernt.

        Args:
            plan: Plangleise statt effektive Gleise melden

        Returns:
            Generator von Gleisnamen.
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
        Fahrplan im networkx directed Graph Format

        Die Knoten sind Anschluss- oder Gleisnamen und haben folgende Attribute:

        - typ: 'anschluss' oder 'gleis'
        - an: Ankunftszeit als datetime.time (kann fehlen)
        - ab: Ankunftszeit als datetime.time (kann fehlen)
        - aufenthalt: Aufenthaltszeit in sekunden (kann fehlen)

        Die Kanten haben folgende Attribute:

        - fahrzeit: Planmässige Fahrzeit in sekunden (kann fehlen)

        Returns:
            networkx-Graph
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

    def find_fahrplanzeile(self,
                           gleis: str | None = None,
                           plan: str | None = None,
                           zeit: datetime.time | None = None,
                           ) -> FahrplanZeile | None:
        """
        Fahrplanzeile nach Gleis und/oder Zeit suchen.

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        Diese Methode ist ein Wrapper von find_fahrplan, der nur das Fahrplanobjekt zurückgibt.

        Args:
            gleis: Gleiskriterium (Gross-/Kleinschreibung egal)
            plan: Plangleiskriterium (Gross-/Kleinschreibung egal)
            zeit: Zeitkriterium, wahr, wenn der Wert zwischen Ankunft und Abfahrt des Eintrags liegt

        Returns:
            FahrplanZeile-Objekt oder None.
        """

        _, zeile = self.find_fahrplan(gleis=gleis, plan=plan, zeit=zeit)
        return zeile

    def find_fahrplan_index(self,
                            gleis: str | None = None,
                            plan: str | None = None,
                            zeit: datetime.time | None = None,
                            ) -> int | None:
        """
        Fahrplanzeilenindex nach Gleis und/oder Zeit suchen

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        Diese Methode ist ein Wrapper von find_fahrplan, der nur den Index zurückgibt.

        Args:
            gleis: Gleiskriterium (Gross-/Kleinschreibung egal)
            plan: Plangleiskriterium (Gross-/Kleinschreibung egal)
            zeit: Zeitkriterium, wahr, wenn der Wert zwischen Ankunft und Abfahrt des Eintrags liegt

        Returns:
            Listenindex in Fahrplan oder None.
            Vorsicht, 0 ist ein gültiges Resultat!
        """

        index, _ = self.find_fahrplan(gleis=gleis, plan=plan, zeit=zeit)
        return index

    def find_fahrplan(self,
                      gleis: str | None = None,
                      plan: str | None = None,
                      zeit: datetime.time | None = None,
                      ) -> tuple[int | None, FahrplanZeile | None]:
        """
        Index und Fahrplanzeile nach Gleis und/oder Zeit suchen

        Alle angegebenen Kriterien müssen zutreffen.
        Die Zeit muss grösser oder gleich der Ankunftszeit (wenn bekannt)
        und kleiner oder gleich der Abfahrtszeit (wenn bekannt) sein.
        Wenn eine der Zeiten nicht bekannt ist, wird das entsprechende Kriterium als erfüllt gewertet.

        Args:
            gleis: Gleiskriterium (Gross-/Kleinschreibung egal)
            plan: Plangleiskriterium (Gross-/Kleinschreibung egal)
            zeit: Zeitkriterium, wahr, wenn der Wert zwischen Ankunft und Abfahrt des Eintrags liegt

        Returns:
            Listenindex im Fahrplan und FahrplanZeile-Objekt.
            Beide Resultate sind None, wenn kein passender Eintrag gefunden wurde.
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
    Ereignis der Pluginschnittstelle

    Ein Ereignis-Tag von der Pluginschnittstelle sieht z.B. so aus:

    ~~~~~~ xml
    <ereignis zid='1' art='einfahrt' name='RE 10' verspaetung='+2' gleis='1' plangleis='1'
    von='A-Stadt' nach='B-Hausen' sichtbar='true' amgleis='true' />
    ~~~~~~

    Der Tag enthält dieselben Daten wie ein Zugdetails-Tag und zusätzlich die Art des Ereignisses.
    Die Zeit wird vom PluginClient gesetzt.

    Zusätzlich zu den von der Pluginschnittstelle gemeldeten Ereignissen (in Ereignis.arten),
    erzeugt der PluginClient ein Ereignis 'ersatz', wenn ein Zug durch Ersatz (Nummernwechsel) unsichtbar wird.
    Der Zugdetailsinhalt entspricht in diesem Fall dem letzten Ankunftsereignis, wobei sichtbar = False.
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

    def __eq__(self, other: Ereignis) -> bool:
        """
        Gleichheit zweier Ereignisse

        Ereignisse werden als gleich erachtet, wenn art, zid und gleis gleich sind.
        Dies kann dazu benutzt werden, wiederholte Ereignismeldungen zu filtern.
        (Die Pluginschnittstelle schickt gewisse ereignismeldungen wie rothalt und abfahrt wiederholt.)
        """
        return self.art == other.art and self.zid == other.zid and self.gleis == other.gleis

    def __hash__(self) -> int:
        """
        hash-Funktion basierend auf Gleichheitsklasse.

        Ereignisse werden als gleich erachtet, wenn art, zid und gleis gleich sind.
        Für solchermassen "gleiche" Ereignisse generiert diese Funktion den gleichen hash-Wert.
        Dies kann dazu benutzt werden, wiederholte Ereignismeldungen zu filtern.
        (Die Pluginschnittstelle schickt gewisse ereignismeldungen wie rothalt und abfahrt wiederholt.)
        """
        return hash((self.art, self.zid, self.gleis))

    def update(self, ereignis: Mapping) -> Ereignis:
        """
        Attributwerte vom xml-Dokument übernehmen.

        Args:
            ereignis: Mapping mit den Attributen aus dem xml-Tag.
        """
        super().update(ereignis)
        self.art = str(ereignis['art'])

        return self

    def to_dict(self) -> dict:
        return {attr: getattr(self, attr) for attr in self.attribute}


class FahrplanZeileID(NamedTuple):
    zid: int
    zeit: int
    plan: str


class FahrplanZeile:
    """
    Fahrplanzeile

    Attributes:
        zug: Zugehöriges Zug-Objekt.
        gleis: Disponiertes Gleis.
        plan: Plangleis.
        an: Ankunftszeit.
            Nicht alle Fahrplanzeilen haben eine Ankunftszeit.
        ab: Abfahrtszeit.
            Nicht alle Fahrplanzeilen haben eine Abfahrtszeit.
        flags: Siehe unten.
        hinweistext:

    Flags:
      - `A`: Vorzeitige Abfahrt möglich
      - `Bn`: Themenflag
      - `D`: Durchfahrt
      - `E(zid)`: Nummernwechsel
      - `F(zid)`: Flügeln
      - `K(zid)`: Kuppeln
      - `L`: Lokumlauf
      - `P`: Anfangsaufstellungsplatz
      - `R`: Richtungsänderung
      - `W[enr][enr]`: Lokwechsel
    """

    tag = 'gleis'

    def __init__(self, zug: ZugDetails):
        super().__init__()

        # übergeordnetes zug-objekt
        self.zug: ZugDetails = zug

        # diese attribut wird beim ersten property-aufruf erzeugt
        self._fid: FahrplanZeileID | None = None

        # die folgenden attribute werden von der plugin-schnittstelle geliefert
        self.gleis: str = ""
        self.plan: str = ""
        self.an: datetime.time | None = None
        self.ab: datetime.time | None = None
        self.flags: str = ""
        self.hinweistext: str = ""

        # Die nächsten drei Attribute werden vom PluginClient anhand der Flags aufgelöst.
        # Lokal speichern wir Weak References.
        # Daher nur via die entsprechenden öffentlichen Properties zugreifen!
        self._ersatzzug: weakref.ReferenceType[ZugDetails] | None = None
        self._fluegelzug: weakref.ReferenceType[ZugDetails] | None = None
        self._kuppelzug: weakref.ReferenceType[ZugDetails] | None = None

    @property
    def fid(self) -> FahrplanZeileID:
        """
        Fahrplanziel-Identifikation

        Die `fid` bildet den eindeutigen Fahrzielschlüssel für den Zielgraph.

        Die Identifikation besteht aus den eindeutigen Attributen `zid`, Zeit in Minuten und Plangleis.
        Die ID wird beim ersten Gebrauch aus den genannten Attributen generiert und bleibt danach konstant.
        Das Property sollte daher nicht verwendet werden, bevor die Attribute ausgefüllt sind.

        Die Attribute `an`, `ab` und `plan` alleine sind (auch für einen Zug) nicht eindeutig:
        `an` oder `ab` können `None` sein, das Gleis kann mehrmals angefahren werden.
        `an` kann sich beim Nummernwechsel ändern.

        Returns:
            Dreiertupel (`zid`, `zeit`, `plan`).
            `zeit` ist entweder die Ankunfts- oder Abfahrtszeit in Minuten.
            `plan` ist das Plangleis.
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

        Der Hash basiert auf der `fid`.

        Returns:
            Hash-Wert
        """

        return hash(self.fid)

    def __eq__(self, other: FahrplanZeile) -> bool:
        """
        Gleichheit von zwei Fahrplanzeilen feststellen.

        Gleichheit bedeutet: gleicher Zug und gleiches Plangleis.
        Jedes plangleis kommt im sts-Fahrplan nur einmal vor.

        Args:
            other: zu vergleichendes FahrplanZeile-Objekt

        Returns:
            True, wenn Zug und Plangleis übereinstimmen, sonst False
        """
        return self.zug.zid == other.zug.zid and self.plan == other.plan

    def __str__(self):
        if self.gleis == self.plan:
            return f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"FahrplanZeile({self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

    def update(self, item: Mapping) -> FahrplanZeile:
        """
        Daten von untangle-Element oder anderer FahrplanZeile übernehmen.

        Es werden nur die Attribute übernommen, die von der Pluginschnittstelle geliefert werden.

        Args:
            item: eines von folgenden Objekten:

                - untangle.Element mit dem gleis-Tag von der Simulatorschnittstelle,
                - ein anderes FahrplanZeile-Objekt,
                - Dictionary mit Werten, die den Attributen dieser Klasse entsprechen.
        """

        if isinstance(item, self.__class__):
            item = item.__dict__

        if isinstance(item, untangle.Element):
            self.gleis = str(item['name']).strip()
        else:
            self.gleis = str(item['gleis']).strip()

        self.plan = str(item['plan']).strip()

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

        self.flags = str(item['flags']).strip()
        self.hinweistext = str(item['hinweistext'])

        return self

    @property
    def ersatzzug(self) -> ZugDetails | None:
        if self._ersatzzug is not None:
            return self._ersatzzug()
        else:
            return None

    @ersatzzug.setter
    def ersatzzug(self, val: ZugDetails):
        if val is not None:
            self._ersatzzug = weakref.ref(val)
        else:
            self._ersatzzug = None

    @property
    def fluegelzug(self) -> ZugDetails | None:
        if self._fluegelzug is not None:
            return self._fluegelzug()
        else:
            return None

    @fluegelzug.setter
    def fluegelzug(self, val: ZugDetails):
        if val is not None:
            self._fluegelzug = weakref.ref(val)
        else:
            self._fluegelzug = None

    @property
    def kuppelzug(self) -> ZugDetails | None:
        if self._kuppelzug is not None:
            return self._kuppelzug()
        else:
            return None

    @kuppelzug.setter
    def kuppelzug(self, val: ZugDetails):
        if val is not None:
            self._kuppelzug = weakref.ref(val)
        else:
            self._kuppelzug = None

    def durchfahrt(self) -> bool:
        """
        Durchfahrt-Flag
        """
        return 'D' in self.flags

    def ersatz_zid(self) -> int | None:
        """
        zid aus dem Ersatz-Flag
        """
        mo = re.search(r"E[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def fluegel_zid(self) -> int | None:
        """
        zid aus dem Fluegeln-Flag
        """
        mo = re.search(r"F[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def kuppel_zid(self) -> int | None:
        """
        zid aus dem Kuppel-Flag
        """
        mo = re.search(r"K[0-9]?\(([0-9]+)\)", self.flags)
        if mo:
            return int(mo.group(1))
        else:
            return None

    def lokumlauf(self) -> bool:
        """
        Lokumlauf-Flag
        """
        return 'L' in self.flags

    def lokwechsel(self) -> tuple[int, int] | None:
        """
        Lokwechsel-Flag

        Returns:
            Elementnummern der Ein- und Ausfahrgleise oder None.
            Die Gleise können in einer beliebigen Reihenfolge auftreten.
            Einfahrt/Ausfahrt kann aus dem Elementtyp bestimmt werden.
        """
        mo = re.search(r"W\[([0-9]+)]\[([0-9]+)]", self.flags)
        if mo:
            return int(mo.group(1)), int(mo.group(2))
        else:
            return None

    def richtungswechsel(self) -> bool:
        """
        Richtungswechsel-Flag
        """
        return 'R' in self.flags

    def vorzeitige_abfahrt(self) -> bool:
        """
        Vorzeitige-Abfahrt-Flag
        """
        return 'A' in self.flags
