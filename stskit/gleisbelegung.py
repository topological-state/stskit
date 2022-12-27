import itertools
import logging
from typing import AbstractSet, Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Type, Union

import matplotlib as mpl
import matplotlib.pyplot as plt
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from stskit.auswertung import Auswertung
from stskit.anlage import Anlage
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung, FesteVerspaetung, \
    AbfahrtAbwarten, AnkunftAbwarten, ZugAbwarten, ZugNichtAbwarten
from stskit.stsplugin import PluginClient
from stskit.stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung
from stskit.slotgrafik import hour_minutes_formatter, Slot, ZugFarbschema, Gleisbelegung, SlotWarnung, gleis_sektor_sortkey, \
    WARNUNG_VERBINDUNG, WARNUNG_STATUS
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_gleisbelegung import Ui_GleisbelegungWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')


def weginfo_kurz(zug: ZugDetailsPlanung, gleis_index: int) -> str:
    gleise = []
    ell_links = False
    ell_rechts = False

    for fpz in zug.fahrplan:
        if fpz.durchfahrt():
            gleise.append("(" + fpz.gleis + ")")
        else:
            gleise.append(fpz.gleis)

    while gleis_index < len(gleise) - 3:
        del gleise[-2]
        ell_rechts = True

    while gleis_index > 2:
        del gleise[1]
        gleis_index -= 1
        ell_links = True

    if ell_links:
        gleise.insert(1, "...")
    if ell_rechts:
        gleise.insert(-1, "...")

    return " - ".join(gleise)


class GleisauswahlItem:
    TYPEN = {"root", "Kategorie", "Gruppe", "Hauptgleis", "Gleis"}

    def __init__(self, modell: 'GleisauswahlModell', typ: str, name: str):
        super().__init__()
        assert typ in self.TYPEN, f"Unbekannter GleisauswahlItem-Typ {typ}"
        self.modell = modell
        self.typ = typ
        self.name = name
        self.sperrung: bool = False
        self._column_count = 2 if self.typ == "Gleis" else 1
        self._parent = None
        self._children = []
        self._row = 0
        self._check_state: bool = False

    def columnCount(self) -> int:
        return self._column_count

    def childCount(self) -> int:
        return len(self._children)

    def child(self, row: int) -> Optional['GleisauswahlItem']:
        try:
            return self._children[row]
        except IndexError:
            return None

    def children(self) -> Iterable['GleisauswahlItem']:
        for child in self._children:
            yield child

    def parent(self):
        return self._parent

    def row(self):
        return self._row

    def addChild(self, child: 'GleisauswahlItem'):
        child._parent = self
        child._row = len(self._children)
        self._children.append(child)
        self._column_count = max(child.columnCount(), self._column_count)

    def checkState(self) -> QtCore.Qt.CheckState:
        if len(self._children):
            checked = 0
            unchecked = 0
            undefined = 0
            for item in self._children:
                state = item.checkState()
                if state == QtCore.Qt.Checked:
                    checked += 1
                elif state == QtCore.Qt.Unchecked:
                    unchecked += 1
                else:
                    undefined += 1

            if checked == len(self._children):
                return QtCore.Qt.Checked
            elif unchecked == len(self._children):
                return QtCore.Qt.Unchecked
            else:
                return QtCore.Qt.PartiallyChecked
        else:
            return QtCore.Qt.Checked if self._check_state else QtCore.Qt.Unchecked

    def setCheckState(self, check_state: QtCore.Qt.CheckState):
        if len(self._children) == 0:
            self._check_state = check_state == QtCore.Qt.Checked

    def flags(self):
        flags = QtCore.Qt.ItemIsEnabled

        if self.name:
            flags = flags | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable
        if self.typ == "Gleis":
            flags = flags | QtCore.Qt.ItemNeverHasChildren
        else:
            flags = flags | QtCore.Qt.ItemIsAutoTristate

        return flags

    def data(self, column, role):
        if role == QtCore.Qt.DisplayRole:
            if column == 0:
                return self.name
            if column == 1:
                return ""

        elif role == QtCore.Qt.CheckStateRole:
            if column == 0:
                return self.checkState()
            elif column == 1 and self.typ == "Gleis":
                return QtCore.Qt.Checked if self.sperrung else QtCore.Qt.Unchecked

        return None

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        column = index.column()
        if role == QtCore.Qt.EditRole:
            return False
        elif role == QtCore.Qt.CheckStateRole:
            if column == 0:
                self.setCheckState(value)
                if len(self._children):
                    for child in self._children:
                        child_index = self.modell.index(child._row, column, index)
                        child.setData(child_index, value, role)
                self.modell.dataChanged.emit(index, index)
                return True
            elif column == 1 and self.typ == "Gleis":
                self.sperrung = value != QtCore.Qt.Unchecked
                self.modell.dataChanged.emit(index, index)
                return True

        return False


class GleisauswahlModell(QtCore.QAbstractItemModel):
    def __init__(self, parent: Optional[QtCore.QObject]):
        super(GleisauswahlModell, self).__init__(parent)
        self._root = GleisauswahlItem(self, "root", "")

        self.alle_gleise: Set[str] = set([])

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = ...) -> int:
        if parent.isValid():
            return parent.internalPointer().childCount()
        else:
            return self._root.childCount()

    def index(self, row: int, column: int, _parent: QModelIndex = ...) -> QModelIndex:
        if not _parent or not _parent.isValid():
            parent = self._root
        else:
            parent = _parent.internalPointer()

        if not QtCore.QAbstractItemModel.hasIndex(self, row, column, _parent):
            return QtCore.QModelIndex()

        child = parent.child(row)
        if child:
            return QtCore.QAbstractItemModel.createIndex(self, row, column, child)
        else:
            return QtCore.QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        if child.isValid():
            p = child.internalPointer().parent()
            if p and p is not self._root:
                return QtCore.QAbstractItemModel.createIndex(self, p.row(), 0, p)
        return QtCore.QModelIndex()

    def addChild(self, node: GleisauswahlItem, _parent: QModelIndex) -> None:
        if not _parent or not _parent.isValid():
            parent = self._root
        else:
            parent = _parent.internalPointer()
        parent.addChild(node)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                if section == 0:
                    return "Gleis"
                elif section == 1:
                    return "Sperrung"

        return None

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled

        node: GleisauswahlItem = index.internalPointer()
        return node.flags()

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        node: GleisauswahlItem = index.internalPointer()
        return node.data(index.column(), role)

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if not index.isValid():
            return False

        node: GleisauswahlItem = index.internalPointer()

        if role == QtCore.Qt.CheckStateRole:
            node.setData(index, value, role)

            parent_index = index
            while True:
                parent_index = self.parent(parent_index)
                if parent_index.isValid():
                    self.dataChanged.emit(parent_index, parent_index)
                else:
                    break

            return True

        return False

    def gleise_definieren(self, anlage: Anlage, zufahrten=False, bahnsteige=True) -> None:
        self.beginResetModel()

        self._root = GleisauswahlItem(self, "root", "")
        self.alle_gleise = set(anlage.gleiszuordnung.keys())

        if zufahrten:
            zufahrten_item = GleisauswahlItem(self, "Kategorie", "Zufahrten")
            self._root.addChild(zufahrten_item)

            for gruppe, gleise in anlage.anschlussgruppen.items():
                gruppen_item = GleisauswahlItem(self, "Gruppe", gruppe)
                zufahrten_item.addChild(gruppen_item)
                for gleis in sorted(gleise):
                    gleis_item = GleisauswahlItem(self, "Gleis", gleis)
                    gruppen_item.addChild(gleis_item)

        if bahnsteige:
            bahnsteige_item = GleisauswahlItem(self, "Kategorie", "Bahnsteige")
            self._root.addChild(bahnsteige_item)

            for bahnhof, gleise in anlage.bahnsteiggruppen.items():
                bahnhof_item = GleisauswahlItem(self, "Gruppe", bahnhof)
                bahnsteige_item.addChild(bahnhof_item)

                hauptgleise = {}
                for gleis in sorted(gleise):
                    hauptgleis = anlage.sektoren.hauptgleis(gleis)
                    try:
                        hauptgleis_item = hauptgleise[hauptgleis]
                    except KeyError:
                        hauptgleis_item = GleisauswahlItem(self, "Hauptgleis", hauptgleis)
                        hauptgleise[hauptgleis] = hauptgleis_item

                    gleis_item = GleisauswahlItem(self, "Gleis", gleis)
                    hauptgleis_item.addChild(gleis_item)

                for hauptgleis in sorted(hauptgleise.keys()):
                    hauptgleis_item = hauptgleise[hauptgleis]
                    if hauptgleis_item.childCount() > 1:
                        bahnhof_item.addChild(hauptgleis_item)
                    else:
                        bahnhof_item.addChild(hauptgleis_item.child(0))

        self.endResetModel()

    def gleis_items(self, parent: Optional[GleisauswahlItem] = None, level: int = 0) -> Iterable[GleisauswahlItem]:
        if parent is None:
            parent = self._root
        for i in range(parent.childCount()):
            item = parent.child(i)
            if item.childCount() > 0:
                yield from self.gleis_items(parent=item, level=level+1)
            else:
                yield item

    def set_auswahl(self, gleise: Union[AbstractSet[str], Sequence[str]]) -> None:
        for item in self.gleis_items():
            state = QtCore.Qt.Checked if item.name in gleise else QtCore.Qt.Unchecked
            item.setCheckState(state)

        self.dataChanged.emit(self.index(0, 0, QModelIndex()),
                              self.index(self._root.columnCount() - 1, self._root.childCount() - 1, QModelIndex()))

    def get_auswahl(self) -> Set[str]:
        gleise = set([])
        for item in self.gleis_items():
            name = item.name
            state = item.checkState()
            if name in self.alle_gleise and state == QtCore.Qt.Checked:
                gleise.add(name)

        return gleise

    def set_sperrungen(self, gleissperrungen: AbstractSet[str]) -> None:
        for item in self.gleis_items():
            item.sperrung = item.name in gleissperrungen

    def get_sperrungen(self) -> Set[str]:
        sperrungen = (item.name for item in self.gleis_items() if item.sperrung and item.typ == "Gleis")
        return set(sperrungen)


class GleisbelegungWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.farbschema: ZugFarbschema = ZugFarbschema()
        self.farbschema.init_schweiz()
        self.show_zufahrten: bool = False
        self.show_bahnsteige: bool = True

        self._balken = None
        self._labels = []
        self._pick_event = False

        self._gleise: List[str] = []
        self._slot_auswahl: List[Slot] = []
        self._warnung_auswahl: List[SlotWarnung] = []
        self.belegung: Optional[Gleisbelegung] = None

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5
        self.belegte_gleise_zeigen = False

        self.ui = Ui_GleisbelegungWindow()
        self.ui.setupUi(self)
        self.gleisauswahl = GleisauswahlModell(None)
        self.ui.gleisView.setModel(self.gleisauswahl)

        self.setWindowTitle("Gleisbelegung")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionBelegteGleise.triggered.connect(self.action_belegte_gleise)
        self.ui.actionWarnungSetzen.triggered.connect(self.action_warnung_setzen)
        self.ui.actionWarnungIgnorieren.triggered.connect(self.action_warnung_ignorieren)
        self.ui.actionWarnungReset.triggered.connect(self.action_warnung_reset)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_actions()

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    @property
    def planung(self) -> Planung:
        return self.zentrale.planung

    @property
    def auswertung(self) -> Auswertung:
        return self.zentrale.auswertung

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode)
        self.ui.actionBelegteGleise.setEnabled(display_mode)
        self.ui.actionBelegteGleise.setChecked(self.belegte_gleise_zeigen)
        self.ui.actionWarnungSetzen.setEnabled(display_mode and len(self._slot_auswahl))
        self.ui.actionWarnungReset.setEnabled(display_mode and len(self._warnung_auswahl))
        self.ui.actionWarnungIgnorieren.setEnabled(display_mode and len(self._warnung_auswahl))
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and len(self._slot_auswahl))
        self.ui.actionPlusEins.setEnabled(display_mode and len(self._slot_auswahl))
        self.ui.actionMinusEins.setEnabled(display_mode and len(self._slot_auswahl))
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and len(self._slot_auswahl) == 2)
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and len(self._slot_auswahl) == 2)

    def planung_update(self, *args, **kwargs):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """
        if self.farbschema is None:
            self.farbschema = ZugFarbschema()
            regionen_schweiz = {"Bern - Lötschberg", "Ostschweiz", "Tessin", "Westschweiz", "Zentralschweiz",
                                "Zürich und Umgebung"}
            if self.anlage.anlage.region in regionen_schweiz:
                self.farbschema.init_schweiz()
            else:
                self.farbschema.init_deutschland()

        self.daten_update()
        self.grafik_update()

    def daten_update(self):
        if self.belegung is None:
            self.belegung = Gleisbelegung(self.anlage)
            self.gleisauswahl.gleise_definieren(self.anlage, zufahrten=self.show_zufahrten,
                                                bahnsteige=self.show_bahnsteige)
            self.gleisauswahl.set_auswahl(self.gleisauswahl.alle_gleise)
            self.gleisauswahl.set_sperrungen(self.anlage.gleissperrungen)
            self.set_gleise(self.gleisauswahl.get_auswahl())

        self.belegung.gleise_auswaehlen(self._gleise)
        try:
            self.belegung.update(self.planung)
        except AttributeError:
            pass

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
            gleise = [gleis for gleis in self._gleise if gleis in self.belegung.belegte_gleise]
        else:
            gleise = self._gleise
        slots = [slot for slot in self.belegung.slots.values() if slot.gleis in gleise]
        x_labels = gleise
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([gleise.index(slot.gleis) for slot in slots])

        y_bot = np.asarray([slot.zeit for slot in slots])
        y_hgt = np.asarray([slot.dauer for slot in slots])
        labels = [slot.titel for slot in slots]

        colors = {slot: self.farbschema.zugfarbe(slot.zug) for slot in slots}
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

        zeit = time_to_minutes(self.client.calc_simzeit())
        self._axes.set_ylim(bottom=zeit + self.zeitfenster_voraus, top=zeit - self.zeitfenster_zurueck, auto=False)

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

        if self.zeitfenster_zurueck > 0:
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
                x = x_labels_pos[x_labels.index(gleis)]
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
            elif slot.ziel.verspaetung_an > 15:
                v = 15
                ls = "--"
            else:
                v = slot.ziel.verspaetung_an
                ls = "-"
            pos_x = [x, x]
            pos_y = [slot.zeit - v, slot.zeit]
            self._axes.plot(pos_x, pos_y, color=c, ls=ls, lw=2, marker=None, alpha=0.5)

    def _plot_abhaengigkeiten(self, slots, x_pos, x_labels, x_labels_pos, colors):
        for x1, c, slot1 in zip(x_pos, colors, slots):
            for korr in slot1.ziel.fdl_korrektur.values():
                if isinstance(korr, AbfahrtAbwarten) or \
                        isinstance(korr, AnkunftAbwarten) or \
                        isinstance(korr, FesteVerspaetung):
                    y1 = slot1.zeit + slot1.dauer
                    y2 = slot1.zeit
                    x2 = x1

                    try:
                        ref = korr.ursprung
                        ziel = self.planung.zielgraph.nodes[ref]['obj']
                        slot2 = self.belegung.slots[Slot.build_key(ziel)]
                        x2 = x_labels_pos[x_labels.index(slot2.gleis)]
                        if isinstance(korr, AnkunftAbwarten):
                            y2 = slot2.zeit
                        elif isinstance(korr, AbfahrtAbwarten):
                            y2 = slot2.zeit + slot2.dauer
                    except (AttributeError, KeyError, ValueError):
                        slot2 = None
                        try:
                            y2 = y1 - korr.verspaetung
                        except AttributeError:
                            pass

                    if x1 < x2:
                        x1 += 0.25
                        x2 -= 0.25
                    else:
                        x1 -= 0.25
                        x2 += 0.25

                    if y1 < y2:
                        y1 += 0.1
                        y2 -= 0.1
                    else:
                        y1 -= 0.1
                        y2 += 0.2

                    arrow = mpl.patches.FancyArrowPatch((x2, y2), (x1, y1), arrowstyle='-|>', mutation_scale=10,
                                                        color='#7f7f7f', picker=True)
                    arrow.ziel_slot = slot1
                    arrow.ref_slot = slot2
                    self._axes.add_patch(arrow)

    def _plot_warnungen(self, x_labels, x_labels_pos, kwargs):
        for warnung in self.belegung.warnungen.values():
            warnung_gleise = [gleis for gleis in warnung.gleise if gleis in self._gleise]
            try:
                x = [x_labels_pos[x_labels.index(gleis)] for gleis in warnung_gleise]
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
            self.update_actions()
        else:
            if self._slot_auswahl:
                self._slot_auswahl = []
                self._warnung_auswahl = []
                self.ui.zuginfoLabel.setText("")
                self.grafik_update()
                self.update_actions()

        self._pick_event = False

    def on_button_release(self, event):
        pass

    def on_pick(self, event):
        if event.mouseevent.inaxes == self._axes:
            gleis = self._gleise[round(event.mouseevent.xdata)]
            zeit = event.mouseevent.ydata
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

            text = "\n".join((str(slot) for slot in sorted(slots, key=lambda s: s.zeit)))
            self.ui.zuginfoLabel.setText(text)
            self._slot_auswahl = auswahl

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.gleisauswahl.gleise_definieren(self.anlage, zufahrten=self.show_zufahrten, bahnsteige=self.show_bahnsteige)
        self.gleisauswahl.set_auswahl(self._gleise)
        self.gleisauswahl.set_sperrungen(self.anlage.gleissperrungen)
        self.ui.gleisView.expandAll()
        self.ui.gleisView.resizeColumnToContents(0)

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.set_gleise(self.gleisauswahl.get_auswahl())
        self.anlage.gleissperrungen = self.gleisauswahl.get_sperrungen()
        self.daten_update()
        self.grafik_update()

    def set_gleise(self, gleise):
        hauptgleise = [self.anlage.sektoren.hauptgleis(gleis) for gleis in gleise]
        gleis_sektoren = sorted(zip(hauptgleise, gleise), key=gleis_sektor_sortkey)
        self._gleise = [gs[1] for gs in gleis_sektoren]

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    @pyqtSlot()
    def action_belegte_gleise(self):
        self.belegte_gleise_zeigen = not self.belegte_gleise_zeigen
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_plus_eins(self):
        try:
            self.verspaetung_aendern(self._slot_auswahl[0], 1, True)
        except IndexError:
            pass
        else:
            self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_minus_eins(self):
        try:
            self.verspaetung_aendern(self._slot_auswahl[0], -1, True)
        except IndexError:
            pass
        else:
            self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_loeschen(self):
        try:
            slot = self._slot_auswahl[0]
        except IndexError:
            pass
        else:
            self.planung.fdl_korrektur_loeschen(slot.ziel)
            self.planung.zugverspaetung_korrigieren(slot.zug)
            self.daten_update()
            self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        try:
            self.abhaengigkeit_definieren(AbfahrtAbwarten, self._slot_auswahl[0], self._slot_auswahl[1].ziel, 1)
        except IndexError:
            return

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        try:
            self.abhaengigkeit_definieren(AnkunftAbwarten, self._slot_auswahl[0], self._slot_auswahl[1].ziel, 1)
        except IndexError:
            return

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_warnung_ignorieren(self):
        for w in self._warnung_auswahl:
            if w.status not in WARNUNG_VERBINDUNG.values():
                w.status = "fdl-ignoriert"
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_warnung_setzen(self):
        gleise = set((slot.gleis for slot in self._slot_auswahl))
        k = SlotWarnung(gleise=gleise, status="fdl-markiert")
        k.zeit = min((slot.zeit for slot in self._slot_auswahl))
        k.dauer = max((slot.zeit + slot.dauer for slot in self._slot_auswahl)) - k.zeit
        k.slots = set(self._slot_auswahl)
        self.belegung.warnung_setzen(k)
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_warnung_reset(self):
        for w in self._warnung_auswahl:
            self.belegung.warnung_loeschen(w.key)
        self.daten_update()
        self.grafik_update()
        self.update_actions()

    def verspaetung_aendern(self, slot: Slot, verspaetung: int, relativ: bool = False):
        neu = True
        for korrektur in slot.ziel.fdl_korrektur.values():
            if hasattr(korrektur, "wartezeit"):
                if relativ:
                    korrektur.wartezeit += verspaetung
                    neu = False
            elif hasattr(korrektur, "verspaetung"):
                neu = False
                if relativ:
                    korrektur.verspaetung += verspaetung
                else:
                    korrektur.verspaetung = verspaetung

        if neu:
            korrektur = FesteVerspaetung(self.planung)
            if relativ:
                korrektur.verspaetung = slot.ziel.verspaetung_ab + verspaetung
            else:
                korrektur.verspaetung = verspaetung
            self.planung.fdl_korrektur_setzen(korrektur, slot.ziel)

        self.planung.zugverspaetung_korrigieren(slot.zug)
        self.daten_update()

    def abhaengigkeit_definieren(self, klasse: Type[ZugAbwarten],
                                 slot: Slot, referenz: ZugZielPlanung,
                                 wartezeit: int = 0):

        korrektur = klasse(self.planung)
        korrektur.node = slot.ziel
        korrektur.ursprung = referenz
        korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, slot.ziel)
        self.planung.zugverspaetung_korrigieren(slot.zug)
