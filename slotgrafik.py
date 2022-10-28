"""
datenstrukturen fuer slotgrafik

die slotgrafik besteht aus einem balkendiagramm das die belegung von einzelnen gleisen durch züge im lauf der zeit darstellt.
spezifische implementationen sind die gleisbelegungs-, einfahrts- und ausfahrtsdiagramme.
"""

from dataclasses import dataclass, field
import functools
import itertools
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
import networkx as nx
import numpy as np

from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


GLEISNAME_REGEXP = re.compile(r"([a-zA-Z ]*)([0-9]*)([a-zA-Z ]*)")


def gleisname_sortkey(gleis: str) -> Tuple[str, int, str]:
    """
    gleisname in sortierschlüssel umwandeln

    annahme: gleisname setzt sich aus präfix, nummer und suffix zusammen.
    präfix und suffix bestehen aus buchstaben und leerzeichen oder fehlen ganz.
    präfix und suffix können durch leerzeichen von der nummer abgetrennt sein, müssen aber nicht.

    :param gleis: gleisname, wie er im fahrplan der züge steht
    :return: tupel (präfix, nummer, suffix). leerzeichen entfernt.
    """

    mo = re.match(GLEISNAME_REGEXP, gleis)
    prefix = mo.group(1).replace(" ", "")
    try:
        nummer = int(mo.group(2))
    except ValueError:
        nummer = 0
    suffix = mo.group(3).replace(" ", "")
    return prefix, nummer, suffix


def gleis_sektor_sortkey(gleis_sektor: Tuple[str, str]) -> Tuple[str, int, str, str, int, str]:
    """
    hauptgleis und sektorgleis in sortierschlüssel umwandeln

    :param gleis_sektor: tupel aus hauptgleis und sektorgleis.
        sektorgleis, wie es im fahrplan der züge steht,
        hauptgleis, wie es in der anlagenkonfiguration steht.
    :return: tupel aus präfix, nummer, suffix des hauptgleises
        und darauf folgend präfix, nummer, suffix des sektorgleises,
        jeweils wie von gleisname_sortkey.
    """

    g1, g2, g3 = gleisname_sortkey(gleis_sektor[0])
    s1, s2, s3 = gleisname_sortkey(gleis_sektor[1])
    return g1, g2, g3, s1, s2, s3


@dataclass(init=False)
class ZugFarbschema:
    """
    any color accepted by matplotlib can be used, even RGB colors.
    a table of named colors can be found at https://matplotlib.org/stable/gallery/color/named_colors.html.
    however, only few colors should be used to avoid confusion, for instance,
    the tableau colors (matplotlib.colors.TABLEAU_COLORS):

    tab:red - hochgeschwindigkeit
    tab:orange - international und intercity
    tab:green - interregio
    tab:blue - regionalexpress/regionalbahn
    tab:cyan - staedt. nahverkehr
    tab:pink - extrazuege
    tab:brown - langsame gueter
    tab:olive - schnelle gueter und betriebs-/dienst-/leerfahrten
    tab:purple - spezielle gueter (z.b. RoLa, SIM)
    tab:gray - uebrige
    """

    nach_gattung: Dict[str, str]
    nach_nummer: Dict[Tuple[int, int], str]

    def zugfarbe(self, zug: ZugDetails) -> str:
        """
        matplotlib-farbcode eines zuges

        :param zug:
        :return: str
        """
        try:
            return self.nach_gattung[zug.gattung]
        except KeyError:
            pass

        nummer = zug.nummer
        for t, f in self.nach_nummer.items():
            if t[0] <= nummer < t[1]:
                return f
        else:
            return "tab:gray"

    def zugfarbe_rgb(self, zug: ZugDetails) -> Tuple[int]:
        """
        rgb-farbcode eines zuges

        :param zug:
        :return: tupel (r,g,b)
        """
        farbe = self.zugfarbe(zug)
        frgb = mpl.colors.to_rgb(farbe)
        rgb = [round(255 * v) for v in frgb]
        return tuple(rgb)

    def init_schweiz(self):
        self.nach_gattung = {
            'ICE': 'tab:red',
            'TGV': 'tab:red',
            'Lok': 'tab:gray'
        }

        self.nach_nummer = {
            (1, 4100): 'tab:red',
            (4100, 9000): 'tab:orange',
            (9000, 9850): 'tab:red',
            (9850, 9900): 'tab:orange',
            (9900, 11000): 'tab:red',
            (11000, 27000): 'tab:orange',
            (27000, 28000): 'tab:pink',
            (28000, 29000): 'tab:green',
            (29000, 30000): 'tab:blue',
            (30000, 36000): 'tab:green',
            (36000, 37000): 'tab:blue',
            (37000, 40000): 'tab:green',
            (40000, 43000): 'tab:blue',
            (43000, 45000): 'tab:purple',
            (45000, 50000): 'tab:cyan',
            (50000, 50200): 'tab:olive',
            (50200, 87600): 'tab:cyan',
            (87600, 88000): 'tab:red',
            (88000, 96000): 'tab:cyan',
            (96000, 97000): 'tab:blue',
            (97000, 100000): 'tab:pink'
        }

    def init_deutschland(self):
        self.nach_gattung = {
            'ICE': 'tab:red',
            'TGV': 'tab:red',
            'IC': 'tab:orange',
            'EC': 'tab:orange',
            'RJ': 'tab:orange',
            'IR': 'tab:green',
            'IRE': 'tab:green',
            'CNL': 'tab:green',
            'RE': 'tab:blue',
            'RB': 'tab:blue',
            'TER': 'tab:blue',
            'S': 'tab:cyan',
            'G': 'tab:brown',
            'Lok': 'tab:olive',
            'RoLa': 'tab:purple'
        }

        self.nach_nummer = {}


@functools.total_ordering
@dataclass
class Slot:
    """
    repräsentation eines zugslots im belegungsplan.

    dieses objekt enthält alle daten für die darstellung in der slotgrafik.
    die daten sind fertig verarbeitet, zugpaarung ist eingetragen, konflikte sind markiert oder gelöst.

    properties berechnen gewisse statische darstellungsmerkmale wie farben.

    attribute
    ---------

    zugstamm : set von zid-nummern von allen zügen, die über flags miteinander verknüpft sind.
        bei zügen aus demselben stamm werden keine gleiskonflikte angezeigt.
    """

    zug: ZugDetailsPlanung
    ziel: ZugZielPlanung
    zugstamm: Set[int] = field(default_factory=set)
    gleistyp: str = ""
    gleis: str = ""
    zeit: int = 0
    dauer: int = 0
    verbindung: Optional[ZugDetailsPlanung] = None
    verbindungsart: str = ""

    def __init__(self, zug: ZugDetailsPlanung, ziel: ZugZielPlanung):
        self.zug = zug
        self.ziel = ziel
        self.zugstamm = set([])
        self.gleistyp = ziel.gleistyp
        self.gleis = ziel.gleis
        self.zeit = 0
        self.dauer = 0

        if ziel.ersatzzug:
            self.verbindung = ziel.ersatzzug
            self.verbindungsart = "E"
        elif ziel.kuppelzug:
            self.verbindung = ziel.kuppelzug
            self.verbindungsart = "K"
        elif ziel.fluegelzug:
            self.verbindung = ziel.fluegelzug
            self.verbindungsart = "F"
        else:
            self.verbindung = None
            self.verbindungsart = ""

    @property
    def key(self) -> Tuple[str, str, int]:
        """
        identifikationsschlüssel des slots

        definiert die unterscheidungsmerkmale von slots.

        :return: tupel aus gleisname, zugname und zielnummer
        """

        return self.gleis, self.zug.name, self.ziel.zielnr

    @staticmethod
    def build_key(ziel: ZugZielPlanung):
        """
        identifikationsschlüssel wie key-property aufbauen

        diese methode kann benutzt werden, wenn man den schlüssel eines fahrplanziels wissen will,
        ohne ein Slot-objekt aufzubauen.

        :param ziel: zugziel
        :return: tupel aus gleisname, zugname und zielnummer
        """

        return ziel.gleis, ziel.zug.name, ziel.zielnr

    def __eq__(self, other: 'Slot') -> bool:
        """
        gleichheit von slots

        die gleichheit von slots wird anhand ihrer key-properties bestimmt.

        :param other: anderes Slot-objekt
        :return: bool
        """
        return self.key == other.key

    def __lt__(self, other: 'Slot') -> bool:
        """
        kleiner als operator

        der operator wird zum sortieren gebraucht.
        slots werden nach self.key sortiert.

        :param other: Slot
        :return: bool
        """
        return self.key < other.key

    def __hash__(self) -> int:
        """
        hash-wert

        der hash wird aus dem self.key berechnet.

        :return: int
        """
        return hash(self.key)

    def __str__(self) -> str:
        name = self.zug.name
        von = self.zug.fahrplan[0].gleis
        nach = self.zug.fahrplan[-1].gleis

        gleis_index = self.zug.find_fahrplan_index(gleis=self.gleis)
        try:
            gleis_zeile = self.zug.fahrplan[gleis_index]
        except (IndexError, TypeError):
            fp = self.gleis
        else:
            zt = []
            try:
                z1 = gleis_zeile.an.isoformat('minutes')
                v1 = f"{gleis_zeile.verspaetung_an:+}"
                zt.append(f"{z1}{v1}")
            except AttributeError:
                pass

            try:
                z2 = gleis_zeile.ab.isoformat('minutes')
                v2 = f"{gleis_zeile.verspaetung_ab:+}"
                zt.append(f"{z2}{v2}")
            except AttributeError:
                pass

            fp = self.gleis + " " + " - ".join(zt)

        return f"{name} ({von} - {nach}): {fp}"

    @property
    def randfarbe(self) -> str:
        """
        randfarbe markiert konflikte und kuppelvorgänge

        :return: farbbezeichnung für matplotlib
        """

        return 'k'

    @property
    def titel(self) -> str:
        """
        "zugname (verspätung)"

        :return: (str) zugtitel
        """

        s = f"{self.zug.name}"
        if self.ziel.einfahrt:
            s = "→ " + s
        elif self.ziel.ausfahrt:
            s = s + " →"

        return s

    @property
    def fontstyle(self) -> str:
        """
        schriftstil markiert halt oder durchfahrt

        :return: "normal" oder "italic"
        """

        return "italic" if self.ziel.durchfahrt() else "normal"

    @property
    def linestyle(self) -> str:
        """
        linienstil markiert halt oder durchfahrt

        :return: "-" oder "--"
        """

        return "--" if self.ziel.durchfahrt() else "-"

    @property
    def linewidth(self) -> int:
        """
        linienbreite

        in der aktuellen version immer 1

        :return: 1 oder 2
        """

        return 1


WARNUNG_STATUS = ['undefiniert', 'gleis', 'hauptgleis', 'ersatz', 'kuppeln', 'flügeln', 'fdl-markiert', 'fdl-ignoriert']
WARNUNG_VERBINDUNG = {'E': 'ersatz', 'K': 'kuppeln', 'F': 'flügeln'}
WARNUNG_FARBE = {'undefiniert': 'gray',
                 'gleis': 'red',
                 'hauptgleis': 'orange',
                 'ersatz': 'darkblue',
                 'kuppeln': 'magenta',
                 'flügeln': 'darkgreen',
                 'fdl-markiert': 'red',
                 'fdl-ignoriert': 'gray'}
WARNUNG_BREITE = {'undefiniert': 1,
                  'gleis': 2,
                  'hauptgleis': 2,
                  'ersatz': 1,
                  'kuppeln': 2,
                  'flügeln': 2,
                  'fdl-markiert': 2,
                  'fdl-ignoriert': 1}


@functools.total_ordering
@dataclass
class SlotWarnung:
    """
    repräsentation eines gleiskonflikts im belegungsplan.

    dieses objekt enthält alle daten für die darstellung in der slotgrafik.
    die daten sind fertig verarbeitet.

    properties berechnen gewisse statische darstellungsmerkmale wie farben.
    """

    gleise: Set[str] = field(default_factory=set)
    zeit: int = 0
    dauer: int = 0
    status: str = "undefiniert"
    slots: Set[Slot] = field(default_factory=set)

    @property
    def key(self) -> frozenset:
        """
        identifikationsschlüssel der warnung

        warnung werden anhand der betroffenen slots identifiziert.

        :return: frozenset von Slot.key von alle self.slots
        """

        return frozenset((s.key for s in self.slots))

    def __eq__(self, other: 'SlotWarnung') -> bool:
        return self.key == other.key

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __str__(self) -> str:
        return f"Warnung ({self.status}) um {hour_minutes_formatter(self.zeit, None)} auf {self.gleise}"

    @property
    def randfarbe(self) -> str:
        """
        randfarbe markiert konflikte und kuppelvorgänge

        :return: farbbezeichnung für matplotlib
        """

        return WARNUNG_FARBE[self.status]

    @property
    def linestyle(self) -> str:
        """
        linienstil

        :return: "-" oder "--"
        """

        return "--"

    @property
    def linewidth(self) -> int:
        """
        linienbreite verdoppeln bei konflikt oder kuppelvorgang.

        :return: 1 oder 2
        """

        return WARNUNG_BREITE[self.status]


GLEIS_TYPEN = {'haupt', 'sektor', 'zufahrt'}


class Gleisbelegung:
    """
    gleisbelegungsmodell

    diese klasse stellt die gleisbelegung für eine auswahl von gleisen dar.
    ausserdem wertet sie die gleisbelegung aus und erstellt warnungen bei konflikten oder betrieblichen vorgängen.

    in einem model-view-controller-muster implementiert diese klasse das modell.
    view und controller werden im gleisbelegungsfenster implementiert.

    verwendung
    ----------

    1. zu beobachtende gleise auswaehlen (gleise_auswaehlen methode)
    2. (wiederholt) daten von zugliste übernehmen (update methode)
    3. daten aus den relevanten attributen auslesen.
       die daten sollten nicht verändert werden, da sie bis auf ein paar ausnahmen beim update überschrieben werden.
       die ausnahmen sind: status-attribut von warnungen.
    4. schritte 2-3 nach bedarf wiederholen.

    attribute
    ---------

    anlage: link zum anlagenobjekt. wird für gleiszuordnung benötigt.

    gleise: liste von verwalteten gleisen. sortiert nach gleisname_sortkey.

    slots: dict von slots. keys sind Slot.key.

    gleis_slots: slots aufgeschlüsselt nach gleis.
        werte sind dict von slots mit Slot.key als schlüssel.

    hauptgleis_slots: slots aufgeschlüsselt nach hauptgleis (union von sektorgleisen).
        werte sind dict von slots mit Slot.key als schlüssel.

    belegte_gleise: namen der gleise, die irgendwann von einem zug belegt sind.

    warnungen: dict von warnungen. keys sind SlotWarnung.key.
    """

    def __init__(self, anlage: Anlage):
        self.anlage: Anlage = anlage
        self.gleise: List[str] = []
        self.slots: Dict[Any, Slot] = {}
        self.gleis_slots: Dict[str, Dict[Any, Slot]] = {}
        self.hauptgleis_slots: Dict[str, Dict[Any, Slot]] = {}
        self.belegte_gleise: Set[str] = set([])
        self.warnungen: Dict[Any, SlotWarnung] = {}

    def slot_warnungen(self, slot: Slot) -> Iterable[SlotWarnung]:
        """
        warnungen zu einem bestimmten slot auflisten.

        :param slot: zu suchender slot
        :return: generator von zugehörigen SlotWarnung objekten aus self.warnungen
        """

        for w in self.warnungen.values():
            if slot in w.slots:
                yield w

    def update(self, planung: Planung):
        """
        daten einlesen und slotliste neu aufbauen.

        diese methode liest die zugdaten neu ein und baut die attribute neu auf.
        in einem zweiten schritt, werden pro gleis, allfällige konflikte gelöst.

        :param planung: planungsmodul

        :return: None
        """

        if len(self.gleise) == 0:
            self.gleise_auswaehlen(self.anlage.gleiszuordnung.keys())
        self.slots_erstellen(planung)
        self.warnungen_aktualisieren()

    def gleise_auswaehlen(self, gleise: Iterable[str]):
        """
        zu beobachtende gleise wählen.

        :param gleise: sequenz von gleisnamen.
        :return: None
        """

        self.gleise = sorted(gleise, key=gleisname_sortkey)

    def slots_erstellen(self, planung: Planung):
        """
        slotliste aus zugdaten erstellen/aktualisieren.

        :param planung: Planungsmodul

        :return: None
        """

        keys_bisherige = set(self.slots.keys())

        for zug in planung.zuege():
            for ziel in zug.fahrplan:
                plan_an = ziel.ankunft_minute
                if plan_an is None:
                    continue
                plan_ab = ziel.abfahrt_minute
                if plan_ab is None:
                    plan_ab = plan_an + 1

                slot = Slot(zug, ziel)
                key = slot.key
                if ziel.gleis in self.gleise:
                    try:
                        # slot existiert schon?
                        slot = self.slots[key]
                    except KeyError:
                        # neuen slot übernehmen
                        self.slots[key] = slot
                    # aktuellen fahrplan übernehmen
                    slot.gleis = ziel.gleis
                    slot.zeit = plan_an
                    if slot.ziel.einfahrt or slot.ziel.ausfahrt:
                        slot.dauer = 1
                    else:
                        slot.dauer = max(1, plan_ab - plan_an)
                    slot.zugstamm = planung.zugstamm[zug.zid]
                    keys_bisherige.discard(key)

        for key in keys_bisherige:
            del self.slots[key]

        self._kataloge_aktualisieren()

    def _kataloge_aktualisieren(self):
        """
        aktualisiert die gleis_slots und hauptgleis_slots kataloge.

        untermethode von slots_erstellen.

        :return: None
        """

        self.gleis_slots = {}
        self.hauptgleis_slots = {}
        self.belegte_gleise = set([])

        for gleis in self.gleise:
            self.gleis_slots[gleis] = {}
            hauptgleis = self.anlage.sektoren.hauptgleis(gleis)
            self.hauptgleis_slots[hauptgleis] = {}

        for slot in self.slots.values():
            gleis = slot.ziel.gleis
            hauptgleis = self.anlage.sektoren.hauptgleis(gleis)
            key = slot.key
            self.gleis_slots[gleis][key] = slot
            self.hauptgleis_slots[hauptgleis][key] = slot
            self.belegte_gleise.add(gleis)

    def warnungen_aktualisieren(self):
        """
        erstellt warnungen basierend auf den gleisbelegungsdaten

        warnungen betreffen gleiskonflikte, konflikte auf zufahrten, betriebliche vorgänge.
        die warnungen stehen nachher in self.warnungen.

        bereits vorhandene warnungen (identifiziert anhand ihres SlotWarnung.key) werden aktualisiert,
        neue warnungen hinzugefügt, veraltete entfernt.

        :return: None
        """

        keys_bisherige = set(self.warnungen.keys())
        for w in self.warnungen.values():
            if w.status.startswith("fdl"):
                keys_bisherige.discard(w.key)

        for w_neu in self._warnungen():
            key = w_neu.key
            try:
                w = self.warnungen[key]
                w.zeit = w_neu.zeit
                w.dauer = w_neu.dauer
            except KeyError:
                w = w_neu
                self.warnungen[key] = w_neu
            keys_bisherige.discard(key)

        for key in keys_bisherige:
            del self.warnungen[key]

    def _warnungen(self) -> Iterable[SlotWarnung]:
        """
        warnungen generieren.

        private untermethode von warnungen_aktualisieren.

        :return: generator von SlotWarnung
        """

        for gleis, slot_dict in self.gleis_slots.items():
            slots = slot_dict.values()
            if gleis in self.anlage.anschlusszuordnung.keys():
                yield from self._zufahrtwarnungen(slots)
            else:
                yield from self._gleiswarnungen(slots)

        for gleis, slot_dict in self.hauptgleis_slots.items():
            slots = slot_dict.values()
            yield from self._hauptgleiswarnungen(slots)

    def _gleiswarnungen(self, slots: Iterable[Slot]) -> Iterable[SlotWarnung]:
        """
        warnungen von gleiskonflikten generieren.

        private untermethode von warnungen_aktualisieren.

        :param slots: alles slots müssen zum gleichen gleis gehären
        :return: generator von SlotWarnung
        """

        for s1, s2 in itertools.permutations(slots, 2):
            if s1.zug == s2.zug:
                continue
            if s1.verbindung is not None and s1.verbindung == s2.zug:
                yield from self._zugfolgewarnung(s1, s2)
            elif s2.zug.zid in s1.zugstamm:
                pass
            elif s1.zeit <= s2.zeit <= s1.zeit + s1.dauer:
                k = SlotWarnung(gleise={s1.gleis, s2.gleis}, zeit=s1.zeit, status="gleis")
                k.dauer = max(s1.dauer, s2.zeit + s2.dauer - s1.zeit)
                k.slots = {s1, s2}
                yield k

    def _hauptgleiswarnungen(self, slots: Iterable[Slot]) -> Iterable[SlotWarnung]:
        """
        warnungen von sektorkonflikten generieren.

        private untermethode von warnungen_aktualisieren.

        :param slots: alles slots müssen zum gleichen gleis gehären
        :return: generator von SlotWarnung
        """

        for s1, s2 in itertools.permutations(slots, 2):
            if s1.zug == s2.zug or s1.gleis == s2.gleis:
                continue
            if s2.zug.zid in s1.zugstamm:
                pass
            elif s1.zeit <= s2.zeit <= s1.zeit + s1.dauer:
                k = SlotWarnung(gleise={s1.gleis, s2.gleis}, status="hauptgleis")
                k.zeit = max(s1.zeit, s2.zeit)
                k.dauer = min(s1.zeit + s1.dauer, s2.zeit + s2.dauer) - k.zeit
                k.slots = {s1, s2}
                yield k

    def _zufahrtwarnungen(self, slots: Iterable[Slot]) -> Iterable[SlotWarnung]:
        """
        warnungen von überlappenden zufahrten generieren.

        zufahrt = einfahrt oder ausfahrt.

        private untermethode von warnungen_aktualisieren.

        :param slots: alles slots müssen zum gleichen gleis gehären
        :return: generator von SlotWarnung
        """
        slots = sorted(slots, key=lambda s: s.zeit)
        try:
            letzter = slots[0]
        except IndexError:
            return None

        frei = letzter.zeit + letzter.dauer
        konflikt = None
        for slot in slots[1:]:
            if slot.zeit < frei:
                if konflikt is None:
                    konflikt = SlotWarnung(gleise={letzter.gleis}, zeit=letzter.zeit, status="gleis")
                    konflikt.slots.add(letzter)
                konflikt.slots.add(slot)
                slot.zeit = slot.ziel.ankunft_minute
                if slot.zeit is None or frei > slot.zeit:
                    slot.zeit = frei
                konflikt.dauer = slot.zeit + slot.dauer - konflikt.zeit
                frei = slot.zeit + slot.dauer
                letzter = slot
            else:
                if konflikt is not None:
                    yield konflikt
                    konflikt = None
                letzter = slot
                frei = slot.zeit + slot.dauer

        if konflikt is not None:
            yield konflikt

    def _zugfolgewarnung(self, s1: Slot, s2: Slot) -> Iterable[SlotWarnung]:
        """
        verbindet zwei slots und erstellt eine warnung

        passt die längen des ersten slots so an, dass sich die slots berühren.

        der erste slot muss den zweiten als folgeslot (infolge ersatz, kupplung, flügelung) haben
        und insbesondere im gleichen gleis liegen.

        :param s1: erster slot
        :param s2: zweiter slot (später als s1)
        :return: generator von SlotWarnung
        """

        if s1.verbindungsart == "K":
            pass
        elif s2.ziel.zielnr > 0:
            return

        try:
            s2_zeile = s2.ziel
            s2_an = time_to_minutes(s2_zeile.an) + s2_zeile.verspaetung_an
            if s2_an > s1.zeit:
                s1.dauer = s2_an - s1.zeit

            k = SlotWarnung(gleise={s1.gleis, s2.gleis})
            k.status = WARNUNG_VERBINDUNG[s1.verbindungsart]
            k.zeit = min(s1.zeit, s2.zeit)
            k.dauer = max(s1.zeit + s1.dauer - k.zeit, s2.zeit + s2.dauer - k.zeit)
            k.slots = {s1, s2}
            yield k
        except AttributeError:
            pass

    def warnung_setzen(self, warnung: SlotWarnung) -> None:
        self.warnungen[warnung.key] = warnung

    def warnung_loeschen(self, key: Any) -> None:
        del self.warnungen[key]
