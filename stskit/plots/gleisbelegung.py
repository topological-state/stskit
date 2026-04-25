"""
Datenstrukturen für Gleisbelegungsgrafik

Die Gleisbelegungsgrafik stellt die Belegung von einzelnen Gleisen durch Züge im Lauf der Zeit dar.
Die horizontale Achse listet kategorisch die Gleise auf,
die vertikale Achse ist die Zeitachse.

Die Grafik enthält folgende Elemente:

- Gefüllte Rechtecke (Balken) zeigen die zeitliche Belegung eines Gleises an.
- Umrisse zeigen Warnungen zu Betriebsvorgängen oder Belegungskonflikten an.

"""

from __future__ import annotations
from collections.abc import Generator, Iterable, Sequence
from dataclasses import dataclass, field
import functools
import itertools
import logging
from typing import Any

import matplotlib as mpl
from matplotlib.backend_bases import FigureCanvasBase, Event, PickEvent
import numpy as np
import networkx as nx
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.ticker import MultipleLocator

from stskit.utils.observer import Observable
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.zielgraph import ZielGraphNode, ZielLabelType
from stskit.plots.plotbasics import hour_minutes_formatter
from stskit.model.zugschema import Zugbeschriftung
from stskit.zentrale import DatenZentrale

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@functools.total_ordering
@dataclass
class Slot:
    """
    Zugslot im Belegungsplan.

    Dieses Objekt enthält alle Daten für die Darstellung im Belegungsplan.
    Die Daten sind fertig verarbeitet, Zugpaarung ist eingetragen, Konflikte sind markiert oder gelöst.

    Properties berechnen gewisse statische Darstellungsmerkmale wie Farbe.

    Attributes:
        zugstamm : zid von allen Zügen, die miteinander verknüpft sind.
            Bei Zügen aus demselben Stamm werden keine Gleiskonflikte angezeigt.
        zeit: Anfangszeit des Slots in Minuten nach Mitternacht.
            In der Regel entspricht dieser Wert der voraussichtlichen Ankunftszeit (inklusive Verspätung).
            Bei Slotverbindungen kann der Wert abweichen.
        dauer: Länge des Slots in Minuten. Der Slot endet bei `zeit + dauer`.
        abfahrt: Voraussichtliche Abfahrtszeit (inklusive Verspätung) in Minuten.
            Das Ende des Slots kann bei Slotverbindungen von dieser Zeit abweichen.
        verspaetung_an: Voraussichtliche Ankunftsverspätung in Minuten.
        verspaetung_ab: Voraussichtliche Abfahrtsverspätung in Minuten.
    """

    zid: int
    fid: ZielLabelType
    gleis: BahnhofElement
    zugname: str
    zugstamm: set[int] = field(default_factory=set)
    zieltyp: str = ""
    durchfahrt: bool = False
    zeit: int | float = 0
    dauer: int | float = 0
    abfahrt: int | float = 0
    verspaetung_an: int | float = 0
    verspaetung_ab: int | float = 0
    titel: str = ""
    info: str = ""
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
        self.abfahrt = 0
        self.titel = ""
        self.info = ""

    @property
    def key(self) -> tuple[BahnhofElement, int, int]:
        """
        Identifikationsschlüssel des Slots

        Der Schlüssel wird benutzt, um den Slot in einem Dictionary zu speichern.
        Der Schlüssel enthält alle Unterscheidungsmerkmale eines Slots.

        Returns:
            Tupel aus Bahnhofelement, ZID und Zeit
        """

        return self.gleis, self.fid[0], self.fid[1]

    @staticmethod
    def build_key(gleis: BahnhofElement, fid: ZielLabelType) -> tuple[BahnhofElement, int, int]:
        """
        Identifikationsschlüssel wie `key`-Property aufbauen

        Diese methode kann benutzt werden, wenn man den Schlüssel eines Fahrplanziels wissen will,
        ohne ein `Slot`-Objekt aufzubauen.

        Args:
            gleis: Gleiselement aus dem Bahnhofgraph
            fid: Ziellabel aus dem Zielgraph

        Returns:
            Tupel aus Bahnhofelement, ZID und Zeit
        """

        return gleis, fid[0], fid[1]

    def __eq__(self, other: Slot) -> bool:
        """
        Gleichheit von Slots

        Die Gleichheit von Slots wird anhand ihrer `key`-Properties bestimmt.

        Args:
            other: zu vergleichendes `Slot`-Objekt

        Returns:
            True, wenn beide Objekte denselben Slot bezeichnen.
        """
        return self.key == other.key

    def __lt__(self, other: Slot) -> bool:
        """
        Kleiner-als Operator

        Der Operator wird zum Sortieren gebraucht.
        Slots werden nach `key` sortiert.

        Args:
            other: zu vergleichendes `Slot`-Objekt

        Returns:
            True, wenn `Self` kleiner ist als der andere.
        """
        return self.key < other.key

    def __hash__(self) -> int:
        """
        Hash-Wert

        Dies ist der Hash-Wert des `key`.

        Returns:
            Hash-Wert
        """
        return hash(self.key)

    def __str__(self) -> str:
        """
        Infotext

        Returns:
            Inhalt des `info`-Attributs.
        """
        return self.info


WARNUNG_STATUS: list[str] = [
    'undefiniert',
    'gleis',
    'bahnsteig',
    'ersatz',
    'kuppeln',
    'kuppeln-reihenfolge',
    'flügeln',
    'fdl-markiert',
    'fdl-ignoriert',
]
"Typ und Status der Warnung"

WARNUNG_VERBINDUNG: dict[str, str] = {
    'E': 'ersatz',
    'K': 'kuppeln',
    'F': 'flügeln',
}
"Verbindungsart zweier Slots nach Flag"

WARNUNG_FARBE: dict[str, str] = {
    'undefiniert': 'gray',
    'gleis': 'red',
    'bahnsteig': 'orange',
    'ersatz': 'darkblue',
    'kuppeln': 'darkmagenta',
    'kuppeln-reihenfolge': 'magenta',
    'flügeln': 'darkgreen',
    'fdl-markiert': 'red',
    'fdl-ignoriert': 'gray',
}
"""
Linienfarben nach Warnung

Farbnamen für Matplotlib.
"""

WARNUNG_BREITE: dict[str, int] = {
    'undefiniert': 1,
    'gleis': 2,
    'bahnsteig': 2,
    'ersatz': 1,
    'kuppeln': 2,
    'kuppeln-reihenfolge': 2,
    'flügeln': 2,
    'fdl-markiert': 2,
    'fdl-ignoriert': 1,
}
"Linienbreiten nach Warnung"


@functools.total_ordering
@dataclass
class SlotWarnung:
    """
    Repräsentation einer Warnung im Belegungsplan.

    Dieses Objekt enthält alle Daten für die Darstellung in der Grafik.
    Die Daten sind fertig verarbeitet.

    Properties berechnen gewisse statische Darstellungsmerkmale wie Farben.

    Attributes:
        gleise: Betroffene Gleise
        zeit: Anfangszeit in Minuten
        dauer: Dauer in Minuten
        status: Warnungsart und Status nach [WARNUNG_STATUS]
        slots: Betroffene Slots
    """

    gleise: set[BahnhofElement] = field(default_factory=set)
    zeit: int | float = 0
    dauer: int | float = 0
    status: str = "undefiniert"
    slots: set[Slot] = field(default_factory=set)

    @property
    def key(self) -> frozenset[tuple[BahnhofElement, int, int]]:
        """
        Identifikationsschlüssel der Warnung

        Warnungen werden anhand der betroffenen Slots identifiziert.

        Returns:
            Nicht-mutierbare Menge von `Slot.key` aus `slots`
        """

        return frozenset((s.key for s in self.slots))

    def __eq__(self, other: SlotWarnung) -> bool:
        return self.key == other.key

    def __lt__(self, other) -> bool:
        return self.key < other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __str__(self) -> str:
        return f"Warnung ({self.status}) um {hour_minutes_formatter(self.zeit, None)} auf {self.gleise}"

    @property
    def randfarbe(self) -> str:
        """
        Farbe der Warnung

        Returns:
             Farbbezeichnung für matplotlib
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

    Diese Klasse stellt die Gleisbelegung für eine Auswahl von Gleisen dar.
    Ausserdem wertet sie die Gleisbelegung aus und erstellt Warnungen bei Konflikten oder betrieblichen Vorgängen.

    In einer Model-View-Controller-Architektur implementiert diese Klasse das Modell.
    Der View wird im `GleisbelegungPlot` und der Controller im `GleisbelegungWidget` implementiert.

    Verwendung:

    1. Zu beobachtende Gleise auswählen ([gleise_auswaehlen]).
    2. (Wiederholt) Daten von Zuggraph und Zielgraph übernehmen ([update]).
    3. Daten aus den relevanten Attributen auslesen.
       Die Daten sollten nicht verändert werden, da sie bis auf ein paar Ausnahmen beim Update überschrieben werden.
       Die Ausnahmen sind: Status-Attribut von Warnungen.
    4. Schritte 2-3 nach Bedarf wiederholen.

    Attributes:

        anlage: Link zum Anlagenobjekt. Wird für die Gleiszuordnung benötigt.
        gleise: Liste von verwalteten Gleisen. Sortiert nach `gleisname_sortkey`.
        slots: Dict von Slots. Keys sind Slot.key.
        gleis_slots: Slots aufgeschlüsselt nach gleis.
            Werte sind Dict von Slots mit `Slot.key` als Schlüssel.
        hauptgleis_slots: Slots aufgeschlüsselt nach Hauptgleis (Union von Sektorgleisen).
            Werte sind Dict von Slots mit Slot.key als Schlüssel.
        belegte_gleise: Namen der Gleise, die im Beobachtungszeitfenster von einem Zug belegt sind.
        warnungen: Dict von Warnungen. Keys sind SlotWarnung.key.
    """

    def __init__(self, zentrale: DatenZentrale):
        self.zentrale: DatenZentrale = zentrale
        self.anlage = zentrale.anlage
        self.betrieb = zentrale.betrieb
        self.gleise: list[BahnhofElement] = []
        self.slots: dict[Any, Slot] = {}
        self.gleis_slots: dict[BahnhofElement, dict[Any, Slot]] = {}
        self.hauptgleis_slots: dict[BahnhofElement, dict[Any, Slot]] = {}
        self.belegte_gleise: set[BahnhofElement] = set()
        self.warnungen: dict[Any, SlotWarnung] = {}
        self.zugbeschriftung = Zugbeschriftung(self.zentrale.anlage)

    def slot_warnungen(self, slot: Slot) -> Generator[SlotWarnung, None, None]:
        """
        Warnungen zu einem bestimmten Slot auflisten.

        Args:
            slot: Betroffener Slot.
        
        Returns:
            Zugehörige [SlotWarnung]-Objekten aus [warnungen].
        """

        for w in self.warnungen.values():
            if slot in w.slots:
                yield w

    def update(self) -> None:
        """
        Daten einlesen und Slotliste aufbauen.

        Diese Methode liest die Zugdaten ein und baut die Attribute neu auf.
        In einem zweiten Schritt werden pro Gleis mögliche Konflikte identifiziert.
        """

        if len(self.gleise) == 0:
            return
        self.slots_erstellen()
        self.slots_formatieren()
        self.warnungen_aktualisieren()

    def gleise_auswaehlen(self, gleise: Iterable[BahnhofElement]) -> None:
        """
        Darzustellende Gleise wählen.

        Params:
            gleise: Darzustellende Gleise (vom Typ 'Gl' oder 'Agl').
        """

        sortierung = self.anlage.bahnhofgraph.hierarchical_index(gleise)
        self.gleise = sorted(gleise, key=sortierung.get)  # ty:ignore[no-matching-overload]

    def slots_erstellen(self) -> None:
        """
        Slotliste aus Zugdaten erstellen/aktualisieren.
        """

        keys_bisherige = set(self.slots.keys())
        undirected_zuggraph = self.anlage.zuggraph.to_undirected(as_view=True)

        for fid, ziel_data in self.betrieb.zielgraph.nodes(data=True):
            if fid.zid < 0:
                continue

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
                slot.abfahrt = plan_ab + slot.verspaetung_ab
                if ziel_data.typ == 'D' or slot.gleis.typ == 'Agl':
                    slot.dauer = 1
                else:
                    slot.dauer = max(1, slot.abfahrt - slot.zeit)
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
        """
        Grafik und Text der Slots gemäss Fahrplandaten formatieren

        Die Fahrplandaten werden aus dem zuggraph and zielgraph der Anlage bestimmt.

        Der Titel ist die Kurzbezeichnung des Zuges in der Grafik.
        Bei Ein- und Ausfahrten wird ein Pfeil "→" vorangestellt oder angehängt.
        Die Info ist die ausführliche Beschreibung für das Statusfeld.

        Die Farbe des Rechtecks wird anhand des Zugschemas bestimmt,
        die Randfarbe anhand der Flags.

        Format des Info-Strings:
        ```
        IC 2662 (WI → TG): Gleis 5, an 15:03+6, ab 15:04+5
        {name} ({von} → {nach}): {gleis}/{plan}, an {an}+{v_an}, ab {ab}+{v_ab}
        ```
        """

        for slot in self.slots.values():
            zug_data = self.anlage.zuggraph.nodes[slot.zid]
            ziel_data = self.betrieb.zielgraph.nodes[slot.fid]
            slot.info = self.zugbeschriftung.format_slot_info(zug_data, ziel=ziel_data)
            slot.titel = self.zugbeschriftung.format_slot_label(zug_data, ziel=ziel_data)
            slot.farbe = self.anlage.zugschema.zugfarbe(zug_data)
            slot.randfarbe = "magenta" if ziel_data.lokwechsel or ziel_data.lokumlauf else "k"
            slot.fontstyle = "italic" if slot.zieltyp == 'D' else "normal"
            slot.linestyle = "--" if slot.zieltyp == 'D' else "-"
            slot.linewidth = 1

    def warnungen_aktualisieren(self):
        """
        Warnungen basierend auf den Gleisbelegungsdaten erzeugen

        Warnungen betreffen Gleiskonflikte, Konflikte auf Zufahrten und Manöver.
        Die warnungen stehen nachher in `warnungen`.

        Bereits vorhandene warnungen (identifiziert anhand ihres SlotWarnung.key) werden aktualisiert,
        Neue warnungen hinzugefügt, veraltete ohne korrespondierende Slots entfernt.
        """

        keys_bisherige = set(self.warnungen.keys())
        for w in self.warnungen.values():
            if w.status == "fdl-markiert":
                # behalten, solange slots existieren
                for s in w.slots:
                    if s.key not in self.slots:
                        break
                else:
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

    def _warnungen(self) -> Generator[SlotWarnung, None, None]:
        """
        Warnungen generieren.

        Private Untermethode von `warnungen_aktualisieren`.

        Returns:
            Generator von `SlotWarnung`
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

    def _gleiswarnungen(self,
                        slots: Iterable[Slot],
                        ) -> Generator[SlotWarnung, None, None]:
        """
        Warnungen zu Gleiskonflikten generieren.

        Private Untermethode von `warnungen_aktualisieren`.

        Params:
            slots: Alle Slots müssen zum gleichen Gleis gehören.

        Returns:
            Generator von `SlotWarnung`
        """

        for s1, s2 in itertools.permutations(slots, 2):
            if s1.zid == s2.zid:
                continue
            elif self.betrieb.zielgraph.has_successor(s1.fid, s2.fid):
                verbindungsdaten = self.betrieb.zielgraph.get_edge_data(s1.fid, s2.fid)
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

    def _hauptgleiswarnungen(self,
                             slots: Iterable[Slot],
                             ) -> Generator[SlotWarnung, None, None]:
        """
        warnungen von sektorkonflikten generieren.

        Private Untermethode von `warnungen_aktualisieren`.

        Params:
            slots: Alle Slots müssen zum gleichen Gleis gehören.

        Returns:
            Generator von `SlotWarnung`
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

    def _zufahrtwarnungen(self, 
                          slots: Iterable[Slot],
                          ) -> Generator[SlotWarnung, None, None]:
        """
        Warnungen von überlappenden Zufahrten generieren.

        Zufahrt = Einfahrt oder Ausfahrt.

        Private Untermethode von `warnungen_aktualisieren`.

        Params:
            slots: Alle Slots müssen zum gleichen Gleis gehören.

        Returns:
            Generator von `SlotWarnung`
        """

        slots: list[Slot] = sorted(slots, key=lambda s: s.zeit)
        try:
            letzter = slots[0]
        except IndexError:
            return

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

    def _zugfolgewarnung(self, 
                         s1: Slot, 
                         s2: Slot, 
                         verbindungsart: str,
                         ) -> Generator[SlotWarnung, None, None]:
        """
        Verbindet zwei Slots und erstellt eine Warnung

        Passt die Länge des ersten Slots so an, dass sich die Slots berühren.
        Der erste Slot muss den zweiten als Folgeslot (infolge Ersatz, Kupplung, Flügelung) haben
        und insbesondere im gleichen Gleis liegen.

        Ersatz: Der erste Slot wird bis zum zweiten gedehnt.
            Der zweite beginnt frühestens 1 Minute nach dem ersten.

        Flügelung: Der erste Slot wird bis zum zweiten gedehnt.
            Der zweite beginnt frühestens 1 Minute nach dem ersten.

        Kupplung: Die Slots überlappen sich planmässig.
            Wenn der erste Slot vor dem zweiten liegt, wird er gedehnt und eine Reihenfolge-Warnung gesetzt.

        Args:
            s1: erster Slot
            s2: zweiter Slot (später als s1)
            verbindungsart: 'E', 'F' oder 'K'
        
        Returns:
            Generiert eine oder keine Slotwarnungen.
        """

        try:
            d = s2.zeit - s1.zeit
            w = WARNUNG_VERBINDUNG[verbindungsart]
            if verbindungsart == "E":
                if d < 1:
                    s1.dauer = 1
                s2.zeit = s1.zeit + s1.dauer
                s2.dauer = max(1, s2.abfahrt - s2.zeit)

            elif verbindungsart == "F":
                s2.zeit = max(s2.zeit, s1.zeit + 1)
                s2.zeit = min(s2.zeit, s1.zeit + s1.dauer)
                s2.dauer = max(s2.abfahrt - s2.zeit, s1.abfahrt - s2.zeit)

            elif verbindungsart == "K":
                if d >= 1:
                    # warnen und s1 bis anfang s2 ausdehnen
                    w += "-reihenfolge"
                    s1.dauer = d
                    s2.zeit = s1.zeit + s1.dauer
                elif d <= -1:
                    # s2 bis ende s1 ausdehnen, wenn noetig
                    s2.dauer = max(s2.dauer, s1.abfahrt - s2.zeit)
                else:
                    # warnen
                    w += "-reihenfolge"

            else:
                raise ValueError("Fehlerhaftes Argument in Gleisbelegung._zugfolgewarnung")

            k = SlotWarnung(gleise={s1.gleis, s2.gleis})
            k.status = w
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
    """
    Grafische Darstellung der Gleisbelegung als Balkendiagramm in Matplotlib
    
    Die Klasse registriert auch Mausklick- und Resize-Events.
    """
    def __init__(self, zentrale: DatenZentrale, canvas: FigureCanvasBase) -> None:
        self.zentrale = zentrale
        self.anlage = zentrale.anlage

        self.gleis_axis = "top"
        self.unbelegte_gleise_zeigen = False

        self._balken = None
        self._labels = []
        self._slot_auswahl: list[Slot] = []
        self._warnung_auswahl: list[SlotWarnung] = []

        self.belegung = Gleisbelegung(self.zentrale)

        self.zugbeschriftung = Zugbeschriftung(self.zentrale.anlage)

        self.vorlaufzeit = 55
        self.nachlaufzeit = 5

        self.selection_changed = Observable(self)
        self.selection_text: list[str] = []

        self._canvas = canvas
        self._axes = self._canvas.figure.subplots()
        self._pick_event = False

        self._canvas.mpl_connect("button_press_event", self.on_button_press)
        self._canvas.mpl_connect("button_release_event", self.on_button_release)
        self._canvas.mpl_connect("pick_event", self.on_pick)
        self._canvas.mpl_connect("resize_event", self.on_resize)


    def grafik_update(self):
        """
        Erstellt das balkendiagramm basierend auf slot-daten

        Diese Methode beinhaltet nur Grafikcode.
        Alle Interpretation von Zugdaten muss vorher in `gleisbelegung` gemacht werden.
        """

        self._axes.clear()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        kwargs['width'] = 1.0

        if not self.unbelegte_gleise_zeigen:
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

        if self.gleis_axis == "top":
            self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='left')
            self._axes.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
        else:
            self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
            self._axes.tick_params(top=False, bottom=True, labeltop=False, labelbottom=True)
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(MultipleLocator(1))
        self._axes.yaxis.set_major_locator(MultipleLocator(5))
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
        for balken, label, slot in zip(_slot_balken, labels, slots):
            self._axes.text(balken.get_x() + balken.get_width() / 2, balken.get_y() + 0.1, label,
                            ha='center', va='top', clip_on=True,
                            fontstyle=slot.fontstyle, fontsize='small', fontstretch='condensed')

        self._plot_abhaengigkeiten(slots, x_pos, x_labels, x_labels_pos, colors)
        self._plot_warnungen(x_labels, x_labels_pos, kwargs)

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.nachlaufzeit > 0:
            self._axes.axhline(y=zeit, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def _plot_sperrungen(self, 
                         x_labels: Sequence[str], 
                         x_labels_pos: Sequence[float], 
                         kwargs: dict[str, Any],
                         ) -> None:
        """
        Gesperrte Gleise schraffieren

        Args:
            x_labels: liste von gleisnamen
            x_labels_pos: liste von x-koordinaten der gleise
            kwargs: `kwargs`-Dict für `axes.bar` von matplotlib.
        """

        try:
            sperrungen = [gleis for gleis, sperrung in self.anlage.bahnhofgraph.nodes(data='sperrung') if sperrung]
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
            r = Rectangle(xy, w, h, fill=False, hatch='/', color='r', linewidth=None)
            self._axes.add_patch(r)

    def _plot_verspaetungen(self, 
                            slots: Sequence[Slot], 
                            x_pos: Sequence[float], 
                            colors: Sequence[str],
                            ) -> None:
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

    def _plot_abhaengigkeiten(self,
                              slots: Sequence[Slot],
                              x_pos: Sequence[float],
                              x_labels: Sequence[str],
                              x_labels_pos: Sequence[float],
                              colors: Sequence[str],
                              ) -> None:
        pass

    def _plot_warnungen(self,
                        x_labels: Sequence[str],
                        x_labels_pos: Sequence[float],
                        kwargs: dict[str, Any],
                        ) -> None:
        for warnung in self.belegung.warnungen.values():
            if warnung.status == "fdl-ignoriert":
                continue
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

    def on_resize(self, event: Event, ) -> None:
        """
        Resize-Event

        Die Grösse der Grafik hat sich geändert.
        Wir zeichnen sie neu.
        """
        self.grafik_update()

    def on_button_press(self, event: Event, ) -> None:
        """
        Button-Press-Event

        Wenn der Benutzer ein Grafikelement ausgewählt hat (`_pick_event`-Attribut), aktualisieren wir die Grafik.
        Wenn nicht, löschen wir die Auswahl und aktualisieren die Grafik.
        """

        if self._pick_event:
            self.grafik_update()
            self._pick_event = False
            self.selection_changed.notify()
        else:
            self.auswahl_loeschen()

    def auswahl_loeschen(self):
        if self._slot_auswahl:
            self._slot_auswahl = []
            self._warnung_auswahl = []
            self.selection_text = []
            self.grafik_update()
            self.selection_changed.notify()

    def on_button_release(self, event: Event, ) -> None:
        """
        Nichts zu tun.
        """
        pass

    def on_pick(self, event: Event, ) -> None:
        """
        Matplotlib Pick-Event

        Der Benutzer hat auf eines unserer Grafikelemente geklickt.
        Wir fügen es der Auswahl hinzu.

        Die Grafik wird erst später im `on_button_press`-Event aktualisiert.
        """

        if not isinstance(event, PickEvent):
            return
        if event.mouseevent.inaxes != self._axes:
            return

        # gleis = self.belegung.gleise[round(event.mouseevent.xdata)]
        # zeit = event.mouseevent.ydata
        auswahl = list(self._slot_auswahl)
        self._pick_event = True

        if isinstance(event.artist, Rectangle):
            try:
                slot = event.artist.slot
            except AttributeError:
                pass
            else:
                try:
                    auswahl.remove(slot)
                except ValueError:
                    auswahl.append(slot)
        elif isinstance(event.artist, FancyArrowPatch):
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
