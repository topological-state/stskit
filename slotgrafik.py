"""
abstraktes slotgrafik-fenster

die slotgrafik besteht aus einem balkendiagramm das die belegung von einzelnen gleisen durch züge im lauf der zeit darstellt.

spezifische implementationen sind die gleisbelegungs-, einfahrts- und ausfahrtstabellen.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
from PyQt5 import Qt, QtCore, QtGui, QtWidgets

from auswertung import Auswertung
from anlage import Anlage
from planung import Planung
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


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

        self.nach_nummer = {
            (1, 400): 'tab:red',
            (400, 1700): 'tab:orange',
            (1700, 3400): 'tab:green',
            (3400, 6000): 'tab:blue',
            (6000, 8000): 'tab:blue',
            (8000, 9000): 'tab:cyan',
            (9200, 9800): 'tab:red',
            (9850, 9899): 'tab:blue',
            (10000, 11000): 'tab:pink',
            (11000, 13000): 'tab:cyan',
            (13600, 26000): 'tab:cyan',
            (26000, 27000): 'tab:blue',
            (27000, 40000): 'tab:pink',
            (40000, 50000): 'tab:purple',
            (50000, 60000): 'tab:olive',
            (60000, 70000): 'tab:brown'
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


@dataclass
class Slot:
    """
    repräsentation eines zugslots im belegungsplan.

    dieses objekt enthält alle daten für die darstellung in der slotgrafik.
    die daten sind fertig verarbeitet, zugpaarung ist eingetragen, konflikte sind markiert oder gelöst.

    properties berechnen gewisse statische darstellungsmerkmale wie farben.
    """
    zug: ZugDetails
    plan: FahrplanZeile
    gleis: str = ""
    zeit: int = 0
    dauer: int = 0
    verbindung: Optional[ZugDetails] = None
    verbindungsart: str = ""
    konflikte: List['Slot'] = field(default_factory=list)

    def __eq__(self, other):
        return self.zug.name == other.zug.name and self.gleis == other.gleis

    def __hash__(self):
        return hash((self.gleis, self.zug.name))

    @property
    def randfarbe(self) -> str:
        """
        randfarbe markiert konflikte und kuppelvorgänge

        :return: farbbezeichnung für matplotlib
        """
        if self.konflikte:
            return 'r'
        elif self.verbindungsart == 'E':
            return 'darkblue'
        elif self.verbindungsart == 'K':
            return 'm'
        elif self.verbindungsart == 'F':
            return 'darkgreen'
        else:
            return 'k'

    @property
    def titel(self) -> str:
        """
        "zugname (verspätung)"

        :return: (str) zugtitel
        """
        if self.zug.verspaetung:
            return f"{self.zug.name} ({self.zug.verspaetung:+})"
        else:
            return f"{self.zug.name}"

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
        linienbreite verdoppeln bei konflikt oder kuppelvorgang.

        :return: 1 oder 2
        """
        return 2 if self.konflikte or self.verbindungsart == 'K' else 1


class SlotWindow(QtWidgets.QMainWindow):
    """
    gemeinsamer vorfahr für slotdiagrammfenster

    nachfahren implementieren die slots_erstellen- und konflikte_loesen-methoden.

    der code besteht im wesentlichen aus drei teilen:
    - die interpretation von zugdaten geschieht in der daten_update-methode
      und den von ihr aufgerufenen slots_erstellen und konflikte_loesen methoden.
      die interpretierten zugdaten werden in _slots zwischengespeichert.
    - die grafische darstellung geschieht in der grafik_update-methode.
      diese setzt die information aus _slots in grafikbefehle um,
      und sollte keine interpretation von zugdaten durchführen.
    - interaktion. als einzige interaktion kann der user auf einen balken klicken,
      wonach der fahrplan des zuges sowie ggf. jener von konfliktzügen angezeigt wird.
    """

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.planung: Optional[Planung] = None
        self.auswertung: Optional[Auswertung] = None

        self.setWindowTitle("slot-grafik")
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(canvas)
        self._axes = canvas.figure.subplots()
        self._balken = None
        self._labels = []
        self._zugdetails: mpl.text.Text = None

        self._gleise: List[str] = []
        self._slots: List[Slot] = []
        self._gleis_slots: Dict[str, List[Slot]] = {}

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5
        self.farbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

        canvas.mpl_connect("pick_event", self.on_pick)

    def update(self):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """
        self.daten_update()
        self.grafik_update()

    def daten_update(self):
        """
        slotliste neu aufbauen.

        diese methode liest die zugdaten vom client neu ein und
        baut die _slots, _gleis_slots und _gleise attribute neu auf.

        die wesentliche arbeit, die slot-objekte aufzubauen wird an die slots_erstellen methode delegiert,
        die erst von nachfahrklassen implementiert wird.

        in einem zweiten schritt, werden pro gleis, allfällige konflikte gelöst.
        dies wird an die konflikte_loesen methode delegiert,
        die ebenfalls erst von nachfahrklassen implementiert wird.

        :return: None
        """
        self._slots = []
        self._gleis_slots = {}
        self._gleise = []

        for slot in self.slots_erstellen():
            try:
                slots = self._gleis_slots[slot.gleis]
            except KeyError:
                slots = self._gleis_slots[slot.gleis] = []
            if slot not in slots:
                slots.append(slot)

        g_s_neu = {}
        for gleis, slots in self._gleis_slots.items():
            g_s_neu[gleis] = self.konflikte_loesen(gleis, slots)
        self._gleis_slots = g_s_neu

        self._gleise = sorted(self._gleis_slots.keys(), key=gleisname_sortkey)
        self._slots = []
        for slots in self._gleis_slots.values():
            self._slots.extend(slots)

    def slots_erstellen(self) -> Iterable[Slot]:
        """
        slots erstellen (abstrakt)

        diese methode erstellt für jeden slot, der in der grafik dargestellt werden soll, ein Slot-objekt
        und gibt es in einer iterablen (liste, generator, etc.) zurück.

        diese methode muss von nachfahrklassen implementiert werden - sonst bleibt die grafik leer.

        alle Slot-attribute müssen gemäss dokumentation gesetzt werden,
        ausser des konflikte-attributes (dieses wird von konflikte_loesen bearbeitet):

        :return: iterable oder generator liefert eine sequenz von Slot-objekten.
        """
        return []

    def konflikte_loesen(self, gleis: str, slots: List[Slot]) -> List[Slot]:
        """
        konflikte erkennen und markieren oder lösen

        diese methode erkennt und löst belegungskonflikte.

        diese methode kann von nachfahrklassen implementiert werden,
        sofern sie eine konflikterkennung anbieten.

        :param gleis: name des gleises für das konflikte bearbeitet werden sollen.
        :param slots: liste aller slots, die zu dem gleis erfasst sind.
        :return: veränderte oder identische slots-liste.
            die liste kann frei verändert oder gleich belassen werden,
            sie muss lediglich vollständig definierte Slot-objekte zu dem angegebenen gleis enthalten.
        """
        return slots

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

        x_labels = self._gleise
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([self._gleise.index(slot.gleis) for slot in self._slots])
        y_bot = np.asarray([slot.zeit for slot in self._slots])
        y_hgt = np.asarray([slot.dauer for slot in self._slots])
        labels = [slot.titel for slot in self._slots]
        colors = [self.farbschema.zugfarbe(slot.zug) for slot in self._slots]

        self._axes.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')
        self._axes.yaxis.set_major_formatter(hour_minutes_formatter)
        self._axes.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._axes.yaxis.set_major_locator(mpl.ticker.MultipleLocator(5))
        self._axes.yaxis.grid(True, which='major')
        self._axes.xaxis.grid(True)

        zeit = time_to_minutes(self.client.calc_simzeit())
        self._axes.set_ylim(bottom=zeit + self.zeitfenster_voraus, top=zeit - self.zeitfenster_zurueck, auto=False)

        self._balken = self._axes.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, picker=True, **kwargs)

        for balken, slot in zip(self._balken, self._slots):
            balken.set(linestyle=slot.linestyle, linewidth=slot.linewidth, edgecolor=slot.randfarbe)

        self._labels = self._axes.bar_label(self._balken, labels=labels, label_type='center')
        for label, slot in zip(self._labels, self._slots):
            label.set(fontstyle=slot.fontstyle, fontsize='small', fontstretch='condensed')

        for item in (self._axes.get_xticklabels() + self._axes.get_yticklabels()):
            item.set_fontsize('small')

        if self.zeitfenster_zurueck > 0:
            self._axes.axhline(y=zeit, color='k', lw=1)

        self._axes.figure.tight_layout()

        self._zugdetails = self._axes.text(1, zeit, 'leerfahrt', bbox={'facecolor': 'yellow', 'alpha': 0.5},
                                           fontsize='small', fontstretch='condensed', visible=False)

        self._axes.figure.canvas.draw()

    def get_slot_hint(self, slot: Slot):
        gleise = [fpz.gleis for fpz in slot.zug.fahrplan if fpz.gleis and not fpz.durchfahrt()]
        weg = " - ".join(gleise)
        return "\n".join([slot.titel, weg])

    def on_pick(self, event):
        if event.mouseevent.inaxes == self._axes:
            gleis = self._gleise[round(event.mouseevent.xdata)]
            zeit = event.mouseevent.ydata
            text = []
            ymin = 24 * 60
            ymax = 0
            if isinstance(event.artist, mpl.patches.Rectangle):
                for slot in self._gleis_slots[gleis]:
                    if slot.zeit <= zeit <= slot.zeit + slot.dauer:
                        ymin = min(ymin, slot.zeit)
                        ymax = max(ymax, slot.zeit + slot.dauer)
                        text.append(self.get_slot_hint(slot))
                self._zugdetails.set(text="\n".join(text), visible=True, x=self._gleise.index(gleis),
                                     y=(ymin + ymax) / 2)
                self._axes.figure.canvas.draw()
        else:
            # im mouseclick event behandeln
            self._zugdetails.set_visible(False)
            self._axes.figure.canvas.draw()
