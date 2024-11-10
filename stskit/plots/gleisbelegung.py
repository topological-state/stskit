"""
Datenstrukturen für Gleisbelegungsgrafik

Die Gleisbelegungsgrafik stellt die Belegung von einzelnen Gleisen durch Züge im Lauf der Zeit dar.
Die horizontale Achse listet kategorisch die Gleise auf,
die vertikale Achse ist die Zeitachse.

Die Grafik enthält folgende Elemente:

- Gefüllte Rechtecke (Balken) zeigen die zeitliche Belegung eines Gleises an.
- Umrisse zeigen Warnungen zu Betriebsvorgängen oder Belegungskonflikten an.

"""

from dataclasses import dataclass, field
import functools
import itertools
import logging
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

import matplotlib as mpl
import numpy as np
import networkx as nx

from stskit.utils.observer import Observable
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.zielgraph import ZielGraphNode, ZielLabelType
from stskit.plugin.stsobj import time_to_minutes, format_minutes, format_verspaetung
from stskit.plots.plotbasics import hour_minutes_formatter
from stskit.model.zugschema import Zugbeschriftung
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


GLEISNAME_REGEXP = re.compile(r"(\D*)(\d*)(\D*)")


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


@functools.total_ordering
@dataclass
class Slot:
    """
    Zugslot im Belegungsplan.

    Dieses Objekt enthält alle Daten für die Darstellung im Belegungsplan.
    Die Daten sind fertig verarbeitet, Zugpaarung ist eingetragen, Konflikte sind markiert oder gelöst.

    Properties berechnen gewisse statische Darstellungsmerkmale wie Farbe.

    Attribute
    ---------

    zugstamm : Set von zid-Nummern von allen Zügen, die miteinander verknüpft sind.
        Bei zügen aus demselben Stamm werden keine Gleiskonflikte angezeigt.
    """

    zid: int
    fid: ZielLabelType
    zugname: str
    zugstamm: Set[int] = field(default_factory=set)
    zieltyp: str = ""
    gleis: BahnhofElement = ("", "")
    durchfahrt: bool = False
    zeit: int = 0
    dauer: int = 0
    verspaetung_an: int = 0
    verspaetung_ab: int = 0
    titel: str = ""
    farbe: str = "gray"
    randfarbe: str = "k"
    linestyle: str = "-"
    linewidth: int = 1
    fontstyle: str = "normal"
    verbunden: bool = False

    def __init__(self, ziel_id: ZielLabelType, ziel_data: ZielGraphNode):
        self.zid = ziel_id[0]
        self.fid = ziel_id
        self.zugstamm = set([])
        self.zieltyp = ziel_data.typ
        self.gleis = BahnhofElement("Agl" if ziel_data.typ in {'A', 'E'} else "Gl", ziel_data.gleis)
        self.zeit = 0
        self.dauer = 0
        self.titel = ""

    @property
    def key(self) -> Tuple[BahnhofElement, int, int]:
        """
        identifikationsschlüssel des slots

        definiert die unterscheidungsmerkmale von slots.

        :return: tupel aus gleisname, zugname und zielnummer
        """

        return self.gleis, self.fid[0], self.fid[1]

    @staticmethod
    def build_key(gleis: BahnhofElement, fid: ZielLabelType):
        """
        identifikationsschlüssel wie key-property aufbauen

        diese methode kann benutzt werden, wenn man den schlüssel eines fahrplanziels wissen will,
        ohne ein Slot-objekt aufzubauen.

        :return: Tupel aus Gleisname, Zug-ID und Ankunftszeit
        """

        return gleis, fid[0], fid[1]

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
        v_an = format_verspaetung(self.verspaetung_an) if self.verspaetung_an else ""
        v_ab = format_verspaetung(self.verspaetung_ab) if self.verspaetung_ab else ""
        if v_an or v_ab:
            v_an = v_an or "+0"
            v_ab = v_ab or "+0"
        if v_an == v_ab:
            v_ab = ""
        if v_an and v_ab:
            v = f"{v_an}/{v_ab}"
        else:
            v = v_an or v_ab
        if v:
            v = f" ({v})"

        s = (f"{self.titel}"
             f" @ {self.gleis.name}:"
             f" {format_minutes(self.zeit)} - {format_minutes(self.zeit + self.dauer)}{v}")

        return s


WARNUNG_STATUS = ['undefiniert', 'gleis', 'bahnsteig', 'ersatz', 'kuppeln', 'flügeln', 'fdl-markiert', 'fdl-ignoriert']
WARNUNG_VERBINDUNG = {'E': 'ersatz', 'K': 'kuppeln', 'F': 'flügeln'}
WARNUNG_FARBE = {'undefiniert': 'gray',
                 'gleis': 'red',
                 'bahnsteig': 'orange',
                 'ersatz': 'darkblue',
                 'kuppeln': 'magenta',
                 'flügeln': 'darkgreen',
                 'fdl-markiert': 'red',
                 'fdl-ignoriert': 'gray'}
WARNUNG_BREITE = {'undefiniert': 1,
                  'gleis': 2,
                  'bahnsteig': 2,
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

    gleise: Set[BahnhofElement] = field(default_factory=set)
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


class Gleisbelegung:
    """
    Gleisbelegungsmodell

    Diese klasse stellt die Gleisbelegung für eine Auswahl von Gleisen dar.
    Ausserdem wertet sie die Gleisbelegung aus und erstellt Warnungen bei Konflikten oder betrieblichen Vorgängen.

    In einer Model-View-Controller-Architektur implementiert diese Klasse das Modell.
    Der View wird im GleisbelegungPlot und der Controller im GleisbelegungWidget implementiert.

    Verwendung
    ----------

    1. Zu beobachtende Gleise auswählen (gleise_auswaehlen methode).
    2. (Wiederholt) Daten von Zuggraph und Zielgraph übernehmen (update-Methode).
    3. Daten aus den relevanten Attributen auslesen.
       Die Daten sollten nicht verändert werden, da sie bis auf ein paar Ausnahmen beim Update überschrieben werden.
       Die ausnahmen sind: Status-Attribut von Warnungen.
    4. Schritte 2-3 nach Bedarf wiederholen.

    Attribute
    ---------

    anlage: Link zum Anlagenobjekt. Wird für die Gleiszuordnung benötigt.

    gleise: Liste von verwalteten Gleisen. Sortiert nach gleisname_sortkey.

    slots: Dict von slots. keys sind Slot.key.

    gleis_slots: slots aufgeschlüsselt nach gleis.
        werte sind dict von slots mit Slot.key als schlüssel.

    hauptgleis_slots: slots aufgeschlüsselt nach hauptgleis (union von sektorgleisen).
        werte sind dict von slots mit Slot.key als schlüssel.

    belegte_gleise: Namen der Gleise, die im Beobachtungszeitfenster von einem Zug belegt sind.

    warnungen: Dict von Warnungen. keys sind SlotWarnung.key.
    """

    def __init__(self, zentrale: DatenZentrale):
        self.zentrale: DatenZentrale = zentrale
        self.anlage = zentrale.anlage
        self.gleise: List[BahnhofElement] = []
        self.slots: Dict[Any, Slot] = {}
        self.gleis_slots: Dict[BahnhofElement, Dict[Any, Slot]] = {}
        self.hauptgleis_slots: Dict[BahnhofElement, Dict[Any, Slot]] = {}
        self.belegte_gleise: Set[BahnhofElement] = set()
        self.warnungen: Dict[Any, SlotWarnung] = {}
        self.zugbeschriftung = Zugbeschriftung(stil="Gleisbelegung")

    def slot_warnungen(self, slot: Slot) -> Iterable[SlotWarnung]:
        """
        warnungen zu einem bestimmten slot auflisten.

        :param slot: zu suchender slot
        :return: generator von zugehörigen SlotWarnung objekten aus self.warnungen
        """

        for w in self.warnungen.values():
            if slot in w.slots:
                yield w

    def update(self):
        """
        Daten einlesen und Slotliste aufbauen.

        Diese Methode liest die Zugdaten ein und baut die Attribute neu auf.
        In einem zweiten Schritt werden pro Gleis mögliche Konflikte identifiziert.

        :return: None
        """

        if len(self.gleise) == 0:
            return
        self.slots_erstellen()
        self.slots_formatieren()
        self.warnungen_aktualisieren()

    def gleise_auswaehlen(self, gleise: Iterable[BahnhofElement]):
        """
        Zu beobachtende Gleise wählen.

        :param gleise: Sequenz von Gleisnamen.
        :return: None
        """

        self.gleise = sorted(gleise, key=lambda x: gleisname_sortkey(x.name))

    def slots_erstellen(self):
        """
        Slotliste aus Zugdaten erstellen/aktualisieren.

        :return: None
        """

        keys_bisherige = set(self.slots.keys())
        undirected_zuggraph = self.anlage.zuggraph.to_undirected(as_view=True)

        for fid, ziel_data in self.anlage.zielgraph.nodes(data=True):
            try:
                plan_an = ziel_data.p_an
            except AttributeError:
                continue

            try:
                plan_ab = ziel_data.p_ab
            except AttributeError:
                plan_ab = plan_an + 1

            slot = Slot(fid, ziel_data)
            gl = slot.gleis
            key = slot.key
            if slot.gleis in self.gleise:
                try:
                    # slot existiert schon?
                    slot = self.slots[key]
                except KeyError:
                    # neuen slot übernehmen
                    self.slots[key] = slot
                # aktuellen fahrplan übernehmen
                slot.gleis = gl
                slot.verspaetung_an = ziel_data.get('v_an', 0)
                slot.verspaetung_ab = ziel_data.get('v_ab', 0)
                slot.zeit = plan_an + slot.verspaetung_an
                if ziel_data.typ == 'D' or slot.gleis.typ == 'Agl':
                    slot.dauer = 1
                else:
                    slot.dauer = max(1, plan_ab + 1 + slot.verspaetung_ab - slot.zeit)
                slot.zugstamm = {zid for zid in nx.node_connected_component(undirected_zuggraph, slot.zid)}
                keys_bisherige.discard(key)

        for key in keys_bisherige:
            del self.slots[key]

        self._kataloge_aktualisieren()

    def _kataloge_aktualisieren(self):
        """
        Aktualisiert die gleis_slots und hauptgleis_slots Kataloge.

        Untermethode von slots_erstellen.

        :return: None
        """

        self.gleis_slots = {}
        self.hauptgleis_slots = {}
        self.belegte_gleise = set([])

        for gleis in self.gleise:
            self.gleis_slots[gleis] = {}
            try:
                hauptgleis = self.anlage.bahnhofgraph.find_superior(gleis, {'Bs'})
                self.hauptgleis_slots[hauptgleis] = {}
            except KeyError:
                pass

        for slot in self.slots.values():
            key = slot.key
            gleis = slot.gleis
            self.gleis_slots[gleis][key] = slot
            self.belegte_gleise.add(gleis)

            try:
                hauptgleis = self.anlage.bahnhofgraph.find_superior(gleis, {'Bs'})
            except KeyError:
                pass
            else:
                self.hauptgleis_slots[hauptgleis][key] = slot

    def slots_formatieren(self):
        for slot in self.slots.values():
            zug_data = self.anlage.zuggraph.nodes[slot.zid]
            ziel_data = self.anlage.zielgraph.nodes[slot.fid]
            slot.titel = self.zugbeschriftung.format(zug_data=zug_data, ziel_data=ziel_data)

            if "Name" in self.zugbeschriftung.elemente:
                s = zug_data.name
            else:
                s = str(zug_data.nummer)
            if slot.zieltyp == 'E':
                s = "→ " + s
            elif slot.zieltyp == 'A':
                s = s + " →"
            slot.titel = s

            slot.farbe = self.anlage.zugschema.zugfarbe(zug_data)
            slot.randfarbe = "k"
            slot.fontstyle = "italic" if slot.zieltyp == 'D' else "normal"
            slot.linestyle = "--" if slot.zieltyp == 'D' else "-"
            slot.linewidth = 1

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
            if gleis.typ == 'Agl':
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
            if s1.zid == s2.zid:
                continue
            elif self.zentrale.anlage.zielgraph.has_edge(s1.fid, s2.fid):
                verbindungsdaten = self.zentrale.anlage.zielgraph.get_edge_data(s1.fid, s2.fid)
                if verbindungsdaten.typ in {'E', 'F'}:
                    s2.verbunden = True
                yield from self._zugfolgewarnung(s1, s2, verbindungsdaten.typ)
            elif s2.zid in s1.zugstamm:
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
            if s1.zid == s2.zid or s1.gleis == s2.gleis:
                continue
            if s2.zid in s1.zugstamm:
                pass
            elif s1.zeit <= s2.zeit <= s1.zeit + s1.dauer:
                k = SlotWarnung(gleise={s1.gleis, s2.gleis}, status="bahnsteig")
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
                # todo : ???
                # slot.zeit = slot.ziel.ankunft_minute
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

    def _zugfolgewarnung(self, s1: Slot, s2: Slot, verbindungsart: str) -> Iterable[SlotWarnung]:
        """
        verbindet zwei slots und erstellt eine warnung

        passt die längen des ersten slots so an, dass sich die slots berühren.

        der erste slot muss den zweiten als folgeslot (infolge ersatz, kupplung, flügelung) haben
        und insbesondere im gleichen gleis liegen.

        :param s1: erster slot
        :param s2: zweiter slot (später als s1)
        :return: generator von SlotWarnung
        """

        if verbindungsart == "K":
            pass

        try:
            d = s2.zeit - s1.zeit
            if d > 0:
                s1.dauer = d

            k = SlotWarnung(gleise={s1.gleis, s2.gleis})
            k.status = WARNUNG_VERBINDUNG[verbindungsart]
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


class GleisbelegungPlot:
    def __init__(self, zentrale: DatenZentrale, canvas: mpl.backend_bases.FigureCanvasBase) -> None:
        self.zentrale = zentrale
        self.anlage = zentrale.anlage

        self.belegte_gleise_zeigen = False

        self._balken = None
        self._labels = []
        self._slot_auswahl: List[Slot] = []
        self._warnung_auswahl: List[SlotWarnung] = []

        self.belegung = Gleisbelegung(self.zentrale)

        self.zugbeschriftung = Zugbeschriftung(stil="Gleisbelegung")

        self.vorlaufzeit = 55
        self.nachlaufzeit = 5

        self.selection_changed = Observable(self)
        self.selection_text: List[str] = []

        self._canvas = canvas
        self._axes = self._canvas.figure.subplots()
        self._pick_event = False

        self._canvas.mpl_connect("button_press_event", self.on_button_press)
        self._canvas.mpl_connect("button_release_event", self.on_button_release)
        self._canvas.mpl_connect("pick_event", self.on_pick)
        self._canvas.mpl_connect("resize_event", self.on_resize)


    def grafik_update(self):
        """
        erstellt das balkendiagramm basierend auf slot-daten

        diese methode beinhaltet nur grafikcode.
        alle interpretation von zugdaten soll in daten_update, slots_erstellen, etc. gemacht werden.

        :return: None
        """

        self._axes.clear()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        kwargs['width'] = 1.0

        if self.belegte_gleise_zeigen:
            gleise = [gleis for gleis in self.belegung.gleise if gleis in self.belegung.belegte_gleise]
        else:
            gleise = self.belegung.gleise
        slots = [slot for slot in self.belegung.slots.values() if slot.gleis in gleise]
        x_labels = [gleis.name for gleis in gleise]
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([gleise.index(slot.gleis) for slot in slots])

        y_bot = np.asarray([slot.zeit for slot in slots])
        y_hgt = np.asarray([slot.dauer for slot in slots])
        labels = [slot.titel for slot in slots]

        colors = {slot: slot.farbe for slot in slots}
        if len(self._slot_auswahl) == 2:
            colors[self._slot_auswahl[0]] = 'yellow'
            colors[self._slot_auswahl[1]] = 'cyan'
        else:
            for slot in self._slot_auswahl:
                colors[slot] = 'yellow'
        colors = [colors[slot] for slot in slots]

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(5))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        zeit = self.anlage.simzeit_minuten
        self._axes.set_ylim(bottom=zeit + self.vorlaufzeit, top=zeit - self.nachlaufzeit, auto=False)

        self._plot_sperrungen(x_labels, x_labels_pos, kwargs)
        self._plot_verspaetungen(slots, x_pos, colors)

        # balken
        _slot_balken = self._axes.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, picker=True, **kwargs)
        for balken, slot in zip(_slot_balken, slots):
            balken.set(linestyle=slot.linestyle, linewidth=slot.linewidth, edgecolor=slot.randfarbe)
            balken.slot = slot
        _slot_labels = self._axes.bar_label(_slot_balken, labels=labels, label_type='center')
        for label, slot in zip(_slot_labels, slots):
            label.set(fontstyle=slot.fontstyle, fontsize='small', fontstretch='condensed')

        self._plot_abhaengigkeiten(slots, x_pos, x_labels, x_labels_pos, colors)
        self._plot_warnungen(x_labels, x_labels_pos, kwargs)

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.nachlaufzeit > 0:
            self._axes.axhline(y=zeit, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def _plot_sperrungen(self, x_labels, x_labels_pos, kwargs):
        """
        gleissperrungen mit einer schraffur markieren

        :param x_labels: liste von gleisnamen
        :param x_labels_pos: liste von x-koordinaten der gleise
        :param kwargs: kwargs-dict, der für die axes.bar-methode vorgesehen ist.
        :return: None
        """

        try:
            sperrungen = self.anlage.gleissperrungen
        except AttributeError:
            sperrungen = []
        for gleis in sperrungen:
            ylim = self._axes.get_ylim()
            try:
                x = x_labels_pos[x_labels.index(gleis.name)]
                xy = (x - kwargs['width'] / 2, min(ylim))
                w = kwargs['width']
            except ValueError:
                continue
            h = max(ylim) - min(ylim)
            r = mpl.patches.Rectangle(xy, w, h, fill=False, hatch='/', color='r', linewidth=None)
            self._axes.add_patch(r)

    def _plot_verspaetungen(self, slots, x_pos, colors):
        for x, c, slot in zip(x_pos, colors, slots):
            if slot.verbunden:
                continue
            elif slot.verspaetung_an > 15:
                v = 15
                ls = "--"
            else:
                v = slot.verspaetung_an
                ls = "-"
            pos_x = [x, x]
            pos_y = [slot.zeit - v, slot.zeit]
            self._axes.plot(pos_x, pos_y, color=c, ls=ls, lw=2, marker=None, alpha=0.5)

    def _plot_abhaengigkeiten(self, slots, x_pos, x_labels, x_labels_pos, colors):
        pass

    def _plot_warnungen(self, x_labels, x_labels_pos, kwargs):
        for warnung in self.belegung.warnungen.values():
            warnung_gleise = [gleis for gleis in warnung.gleise if gleis in self.belegung.gleise]
            try:
                x = [x_labels_pos[x_labels.index(gleis.name)] for gleis in warnung_gleise]
                xy = (min(x) - kwargs['width'] / 2, warnung.zeit)
                w = max(x) - min(x) + kwargs['width']
            except ValueError:
                continue
            h = warnung.dauer
            r = mpl.patches.Rectangle(xy, w, h, fill=False, linestyle=warnung.linestyle, linewidth=warnung.linewidth,
                                      edgecolor=warnung.randfarbe, picker=True)
            self._axes.add_patch(r)

    def on_resize(self, event):
        self.grafik_update()

    def on_button_press(self, event):
        if self._pick_event:
            self.grafik_update()
        else:
            if self._slot_auswahl:
                self._slot_auswahl = []
                self._warnung_auswahl = []
                self.selection_text = []
                self.grafik_update()

        self._pick_event = False
        self.selection_changed.notify()

    def on_button_release(self, event):
        pass

    def on_pick(self, event):
        if event.mouseevent.inaxes == self._axes:
            # gleis = self.belegung.gleise[round(event.mouseevent.xdata)]
            # zeit = event.mouseevent.ydata
            auswahl = list(self._slot_auswahl)
            self._pick_event = True

            if isinstance(event.artist, mpl.patches.Rectangle):
                try:
                    slot = event.artist.slot
                except AttributeError:
                    pass
                else:
                    try:
                        auswahl.remove(slot)
                    except ValueError:
                        auswahl.append(slot)
            elif isinstance(event.artist, mpl.patches.FancyArrowPatch):
                try:
                    auswahl = [event.artist.ziel_slot, event.artist.ref_slot]
                except AttributeError:
                    pass

            warnungen = set([])
            for slot in auswahl:
                warnungen = warnungen | set(self.belegung.slot_warnungen(slot))
            self._warnung_auswahl = list(warnungen)

            slots = set(auswahl)
            for warnung in warnungen:
                slots = slots | warnung.slots

            self.selection_text = [str(slot) for slot in sorted(slots, key=lambda s: s.zeit)]

            self._slot_auswahl = auswahl
