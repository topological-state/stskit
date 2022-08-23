"""
datenstrukturen fuer slotgrafik

die slotgrafik besteht aus einem balkendiagramm das die belegung von einzelnen gleisen durch züge im lauf der zeit darstellt.
spezifische implementationen sind die gleisbelegungs-, einfahrts- und ausfahrtsdiagramme.
"""

from dataclasses import dataclass, field
import itertools
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
import numpy as np

from auswertung import Auswertung
from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


def gleisname_sortkey(gleis: str) -> Tuple[str, int, str]:
    """
    gleisname in sortierschlüssel umwandeln

    annahme: gleisname setzt sich aus präfix, nummer und suffix zusammen.
    präfix und suffix bestehen aus buchstaben und leerzeichen oder fehlen ganz.
    präfix und suffix können durch leerzeichen von der nummer abgetrennt sein, müssen aber nicht.

    :param gleis: gleisname, wie er im fahrplan der züge steht
    :return: tupel (präfix, nummer, suffix). leerzeichen entfernt.
    """
    expr = r"([a-zA-Z ]*)([0-9]*)([a-zA-Z ]*)"
    mo = re.match(expr, gleis)
    prefix = mo.group(1).replace(" ", "")
    try:
        nummer = int(mo.group(2))
    except ValueError:
        nummer = 0
    suffix = mo.group(3).replace(" ", "")
    return prefix, nummer, suffix


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


SLOT_TYPEN = {'gleis', 'einfahrt', 'ausfahrt'}


@dataclass
class Slot:
    """
    repräsentation eines zugslots im belegungsplan.

    dieses objekt enthält alle daten für die darstellung in der slotgrafik.
    die daten sind fertig verarbeitet, zugpaarung ist eingetragen, konflikte sind markiert oder gelöst.

    properties berechnen gewisse statische darstellungsmerkmale wie farben.
    """

    zug: ZugDetailsPlanung
    plan: ZugZielPlanung
    typ: str = ""
    gleis: str = ""
    zeit: int = 0
    dauer: int = 0
    verbindung: Optional[ZugDetailsPlanung] = None
    verbindungsart: str = ""
    konflikte: List['Konflikt'] = field(default_factory=list)

    def __eq__(self, other) -> bool:
        return self.zug.name == other.zug.name and self.gleis == other.gleis

    def __hash__(self) -> int:
        return hash((self.gleis, self.zug.name))

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

        if self.plan.verspaetung_an:
            s = f"{self.zug.name} ({self.plan.verspaetung_an:+})"
        else:
            s = f"{self.zug.name}"
        if self.plan.einfahrt:
            s = "→ " + s
        elif self.plan.ausfahrt:
            s = s + " →"
        return s

    @property
    def fontstyle(self) -> str:
        """
        schriftstil markiert halt oder durchfahrt

        :return: "normal" oder "italic"
        """

        return "italic" if self.plan.durchfahrt() else "normal"

    @property
    def linestyle(self) -> str:
        """
        linienstil markiert halt oder durchfahrt

        :return: "-" oder "--"
        """

        return "--" if self.plan.durchfahrt() else "-"

    @property
    def linewidth(self) -> int:
        """
        linienbreite

        in der aktuellen version immer 1

        :return: 1 oder 2
        """

        return 1


KONFLIKT_STATUS = ['undefiniert', 'gleis', 'hauptgleis', 'ersatz', 'kuppeln', 'flügeln', 'fdl-markiert', 'fdl-ignoriert']
VERBINDUNGS_KONFLIKT = {'E': 'ersatz', 'K': 'kuppeln', 'F': 'flügeln'}
KONFLIKT_FARBE = {'undefiniert': 'gray',
                  'gleis': 'red',
                  'hauptgleis': 'orange',
                  'ersatz': 'darkblue',
                  'kuppeln': 'magenta',
                  'flügeln': 'darkgreen',
                  'fdl-markiert': 'red',
                  'fdl-ignoriert': 'gray'}
KONFLIKT_BREITE = {'undefiniert': 1,
                   'gleis': 2,
                   'hauptgleis': 2,
                   'ersatz': 1,
                   'kuppeln': 2,
                   'flügeln': 2,
                   'fdl-markiert': 2,
                   'fdl-ignoriert': 1}


@dataclass
class Konflikt:
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
    # ziele: List[ZugZielPlanung] = field(default_factory=list)  # ueber slots[].plan erreichbar
    slots: List[Slot] = field(default_factory=list)

    def __eq__(self, other: 'Konflikt') -> bool:
        return self.gleise == other.gleise and self.zeit == other.zeit

    def __hash__(self) -> int:
        return hash((*sorted(self.gleise), self.zeit))

    def __str__(self) -> str:
        return f"Konflikt ({self.status}) um {hour_minutes_formatter(self.zeit, None)} auf {self.gleise}"

    @property
    def randfarbe(self) -> str:
        """
        randfarbe markiert konflikte und kuppelvorgänge

        :return: farbbezeichnung für matplotlib
        """

        return KONFLIKT_FARBE[self.status]

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

        return KONFLIKT_BREITE[self.status]


GLEIS_TYPEN = {'haupt', 'sektor', 'zufahrt'}


class Gleisbelegung:
    def __init__(self, anlage: Anlage):
        self.anlage: Anlage = anlage
        self.gleise: List[str] = []
        self.gleis_typen: Dict[str, str] = {}
        self.slots: List[Slot] = []
        self.gleis_slots: Dict[str, List[Slot]] = {}
        self.hauptgleis_slots: Dict[str, List[Slot]] = {}
        self.konflikte: List[Konflikt] = []
        self.gleis_konflikte: Dict[str, List[Konflikt]] = {}

    def update(self, zugliste: Iterable[ZugDetailsPlanung]):
        """
        daten einlesen und slotliste neu aufbauen.

        diese methode liest die zugdaten neu ein und baut die attribute neu auf.
        in einem zweiten schritt, werden pro gleis, allfällige konflikte gelöst.

        :return: None
        """

        if len(self.gleise) == 0:
            self.gleise_auswaehlen(self.anlage.gleiszuordnung.keys())
        self.slots_erstellen(zugliste)
        self.konflikte_erkennen()

    def gleise_auswaehlen(self, gleise: Iterable[str]):
        self.gleise = sorted(gleise, key=gleisname_sortkey)

    def slots_erstellen(self, zugliste: Iterable[ZugDetailsPlanung]):
        self.slots = []
        self.gleis_slots = {}
        self.hauptgleis_slots = {}

        for zug in zugliste:
            for planzeile in zug.fahrplan:
                try:
                    plan_an = time_to_minutes(planzeile.an) + planzeile.verspaetung_an
                except AttributeError:
                    break
                try:
                    plan_ab = time_to_minutes(planzeile.ab) + planzeile.verspaetung_ab
                except AttributeError:
                    plan_ab = plan_an + 1

                if planzeile.gleis in self.gleise:
                    slot = Slot(zug, planzeile)
                    slot.gleis = planzeile.gleis
                    slot.zeit = plan_an
                    slot.dauer = max(1, plan_ab - plan_an)

                    if planzeile.einfahrt:
                        slot.typ = 'einfahrt'
                    elif planzeile.ausfahrt:
                        slot.typ = 'ausfahrt'
                    else:
                        slot.typ = 'gleis'

                    if planzeile.ersatzzug:
                        slot.verbindung = planzeile.ersatzzug
                        slot.verbindungsart = "E"
                    elif planzeile.kuppelzug:
                        slot.verbindung = planzeile.kuppelzug
                        slot.verbindungsart = "K"
                    elif planzeile.fluegelzug:
                        slot.verbindung = planzeile.fluegelzug
                        slot.verbindungsart = "F"

                    self.slots.append(slot)

                    try:
                        gls = self.gleis_slots[planzeile.gleis]
                    except KeyError:
                        gls = []
                        self.gleis_slots[planzeile.gleis] = gls
                    gls.append(slot)

                    hauptgleis = self.anlage.sektoren.hauptgleis(planzeile.gleis)
                    try:
                        gls = self.hauptgleis_slots[hauptgleis]
                    except KeyError:
                        gls = []
                        self.hauptgleis_slots[hauptgleis] = gls
                    gls.append(slot)

    def konflikte_erkennen(self):
        self.konflikte.clear()
        for gleis, slots in self.gleis_slots.items():
            if gleis in self.anlage.anschlusszuordnung.keys():
                self.zufahrt_konflikte_loesen(slots)
            else:
                self.gleis_konflikte_loesen(slots)

        for gleis, slots in self.hauptgleis_slots.items():
            self.hauptgleis_konflikte_loesen(slots)

    def gleis_konflikte_loesen(self, slots: List[Slot]):
        for s1, s2 in itertools.permutations(slots, 2):
            if s1.zug == s2.zug:
                continue
            if s1.verbindung is not None and s1.verbindung == s2.zug:
                self.verbinden(s1, s2)
            elif s2.verbindung is not None and s2.verbindung == s1.zug:
                self.verbinden(s2, s1)
            elif s1.zeit <= s2.zeit <= s1.zeit + s1.dauer:
                k = Konflikt(gleise={s1.gleis, s2.gleis}, zeit=s1.zeit, status="gleis")
                k.dauer = max(s1.dauer, s2.zeit + s2.dauer - s1.zeit)
                k.slots = [s1, s2]
                self.konflikte.append(k)
                s1.konflikte.append(k)
                s2.konflikte.append(k)

    def hauptgleis_konflikte_loesen(self, slots: List[Slot]):
        for s1, s2 in itertools.permutations(slots, 2):
            if s1.zug == s2.zug or s1.gleis == s2.gleis:
                continue
            if s1.verbindung is not None and s1.verbindung == s2.zug:
                pass
            elif s2.verbindung is not None and s2.verbindung == s1.zug:
                pass
            elif s1.zeit <= s2.zeit <= s1.zeit + s1.dauer:
                k = Konflikt(gleise={s1.gleis, s2.gleis}, zeit=s1.zeit, status="hauptgleis")
                k.dauer = max(s1.dauer, s2.zeit + s2.dauer - s1.zeit)
                k.slots = [s1, s2]
                self.konflikte.append(k)
                s1.konflikte.append(k)
                s2.konflikte.append(k)

    def zufahrt_konflikte_loesen(self, slots: List[Slot]):
        slots = sorted(slots, key=lambda s: s.zeit)
        letzter = slots[0]
        frei = letzter.zeit + letzter.dauer
        konflikt = None
        for slot in slots[1:]:
            if slot.zeit < frei:
                if konflikt is None:
                    konflikt = Konflikt(gleise={letzter.gleis}, zeit=letzter.zeit, status="gleis")
                    konflikt.slots.append(letzter)
                    self.konflikte.append(konflikt)
                konflikt.slots.append(slot)
                slot.konflikte.append(konflikt)
                letzter.konflikte.append(konflikt)
                slot.zeit = max(frei, slot.zeit)
                konflikt.dauer = slot.zeit + slot.dauer - konflikt.zeit
                frei = slot.zeit + slot.dauer
                letzter = slot
            else:
                konflikt = None

    def verbinden(self, s1: Slot, s2: Slot) -> None:
        s2.verbindung = s1.zug
        s2.verbindungsart = s1.verbindungsart
        try:
            s2_zeile = s2.zug.find_fahrplanzeile(gleis=s1.gleis)
            s2_an = time_to_minutes(s2_zeile.an) + s2_zeile.verspaetung_an
            if s2_an > s1.zeit:
                s1.dauer = s2_an - s1.zeit
            elif s1.zeit > s2_an:
                s2.dauer = s1.zeit - s2_an
            k = Konflikt(gleise={s1.gleis, s2.gleis})
            k.status = VERBINDUNGS_KONFLIKT[s1.verbindungsart]
            k.zeit = min(s1.zeit, s2.zeit)
            k.dauer = max(s1.zeit + s1.dauer - k.zeit, s2.zeit + s2.dauer - k.zeit)
            k.slots = [s1, s2]
            self.konflikte.append(k)
            s1.konflikte.append(k)
            s2.konflikte.append(k)
        except AttributeError:
            pass
