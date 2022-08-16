import itertools
import logging
from typing import AbstractSet, Any, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

import matplotlib as mpl
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from auswertung import Auswertung
from anlage import Anlage
from planung import Planung, ZugDetailsPlanung, ZugZielPlanung
from stsplugin import PluginClient
from stsobj import FahrplanZeile, ZugDetails, time_to_minutes, format_verspaetung
from slotgrafik import hour_minutes_formatter, gleisname_sortkey, Slot, ZugFarbschema

from qt.ui_gleisbelegung import Ui_GleisbelegungWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

mpl.use('Qt5Agg')

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
        self._column_count = 1
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

        elif role == QtCore.Qt.CheckStateRole:
            if column == 0:
                return self.checkState()

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
        return False


class GleisauswahlModell(QtCore.QAbstractItemModel):
    def __init__(self, parent: Optional[QtCore.QObject]):
        super(GleisauswahlModell, self).__init__(parent)
        self._root = GleisauswahlItem(self, "root", "")

        self.alle_gleise: Set[str] = set([])

    def columnCount(self, parent: QModelIndex = ...) -> int:
        if parent.isValid():
            return parent.internalPointer().columnCount()
        return self._root.columnCount()

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
        self.alle_gleise = set(anlage.bahnsteigzuordnung.keys())

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
                    gleis_item = GleisauswahlItem(self, "Gleis", gleis)

                    if gleis == hauptgleis:
                        hauptgleise[hauptgleis] = gleis_item
                    else:
                        try:
                            hauptgleis_item = hauptgleise[hauptgleis]
                        except KeyError:
                            hauptgleis_item = GleisauswahlItem(self, "Hauptgleis", hauptgleis)
                            hauptgleise[hauptgleis] = hauptgleis_item

                        hauptgleis_item.addChild(gleis_item)

                for gleis in sorted(hauptgleise.keys()):
                    bahnhof_item.addChild(hauptgleise[gleis])

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


class GleisbelegungWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.planung: Optional[Planung] = None
        self.auswertung: Optional[Auswertung] = None
        self.farbschema: ZugFarbschema = ZugFarbschema()
        self.farbschema.init_schweiz()

        self._balken = None
        self._labels = []
        self._pick_event = False

        self._gleise: List[str] = []
        self._slots: List[Slot] = []
        self._gleis_slots: Dict[str, List[Slot]] = {}
        self._auswahl: List[Slot] = []

        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5

        self.ui = Ui_GleisbelegungWindow()
        self.ui.setupUi(self)
        self.gleisauswahl = GleisauswahlModell(None)
        self.ui.gleisView.setModel(self.gleisauswahl)

        self.setWindowTitle("Gleisbelegung")
        ss = f"background-color: {mpl.rcParams['axes.facecolor']};" \
             f"color: {mpl.rcParams['text.color']};"
        # further possible entries:
        # "selection-color: yellow;"
        # "selection-background-color: blue;"
        self.setStyleSheet(ss)

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_actions()

    def update_actions(self):
        display_mode = self.ui.stackedWidget.currentIndex() == 1

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented
        self.ui.actionLoeschen.setEnabled(display_mode and False)  # not implemented
        self.ui.actionPlusEins.setEnabled(display_mode and False)  # not implemented
        self.ui.actionMinusEins.setEnabled(display_mode and False)  # not implemented
        self.ui.actionAbfahrtAbwarten.setEnabled(display_mode and False)  # not implemented
        self.ui.actionAnkunftAbwarten.setEnabled(display_mode and False)  # not implemented

    def update(self):
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

        if not self._gleise:
            self._gleise = sorted(self._gleis_slots.keys(), key=gleisname_sortkey)
        self._slots = []
        for gleis, slots in self._gleis_slots.items():
            if gleis in self._gleise:
                self._slots.extend(slots)

    def slots_erstellen(self) -> Iterable[Slot]:
        for zug in self.planung.zugliste.values():
            for planzeile in zug.fahrplan:
                try:
                    plan_an = time_to_minutes(planzeile.an) + planzeile.verspaetung_an
                except AttributeError:
                    break
                try:
                    plan_ab = time_to_minutes(planzeile.ab) + planzeile.verspaetung_ab
                except AttributeError:
                    plan_ab = plan_an + 1

                if planzeile.gleis and not planzeile.einfahrt and not planzeile.ausfahrt:
                    slot = Slot(zug, planzeile, planzeile.gleis)
                    slot.zeit = plan_an
                    slot.dauer = max(1, plan_ab - plan_an)

                    if planzeile.ersatzzug:
                        slot.verbindung = planzeile.ersatzzug
                        slot.verbindungsart = "E"
                    elif planzeile.kuppelzug:
                        slot.verbindung = planzeile.kuppelzug
                        slot.verbindungsart = "K"
                    elif planzeile.fluegelzug:
                        slot.verbindung = planzeile.fluegelzug
                        slot.verbindungsart = "F"

                    yield slot

    def konflikte_loesen(self, gleis: str, slots: List[Slot]) -> List[Slot]:
        for s1, s2 in itertools.permutations(slots, 2):
            if s1.verbindung is not None and s1.verbindung == s2.zug:
                self.verbinden(s1, s2)
            elif s2.verbindung is not None and s2.verbindung == s1.zug:
                self.verbinden(s2, s1)
            elif s1.zeit <= s2.zeit < s1.zeit + s1.dauer:
                s1.konflikte.append(s2)
                s2.konflikte.append(s1)

        return slots

    @staticmethod
    def verbinden(s1: Slot, s2: Slot) -> None:
        s2.verbindung = s1.zug
        s2.verbindungsart = s1.verbindungsart
        try:
            s2_zeile = s2.zug.find_fahrplanzeile(gleis=s1.gleis)
            s2_an = time_to_minutes(s2_zeile.an) + s2_zeile.verspaetung_an
            if s2_an > s1.zeit:
                s1.dauer = s2_an - s1.zeit
            elif s1.zeit > s2_an:
                s2.dauer = s1.zeit - s2_an
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

        x_labels = self._gleise
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([self._gleise.index(slot.gleis) for slot in self._slots])
        y_bot = np.asarray([slot.zeit for slot in self._slots])
        y_hgt = np.asarray([slot.dauer for slot in self._slots])
        labels = [slot.titel for slot in self._slots]
        colors = ['yellow' if slot in self._auswahl else self.farbschema.zugfarbe(slot.zug) for slot in self._slots]

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
            self._axes.axhline(y=zeit, color=mpl.rcParams['axes.edgecolor'], linewidth=mpl.rcParams['axes.linewidth'])

        self._axes.figure.tight_layout()
        self._axes.figure.canvas.draw()

    def get_slot_hint(self, slot: Slot):
        name = slot.zug.name
        von = slot.zug.fahrplan[0].gleis
        nach = slot.zug.fahrplan[-1].gleis

        gleis_index = slot.zug.find_fahrplan_index(gleis=slot.gleis)
        try:
            gleis_zeile = slot.zug.fahrplan[gleis_index]
        except (IndexError, TypeError):
            fp = slot.gleis
        else:
            z1 = gleis_zeile.an.isoformat('minutes')
            z2 = gleis_zeile.ab.isoformat('minutes')
            v1 = f"{gleis_zeile.verspaetung_ab:+}"
            v2 = f"{gleis_zeile.verspaetung_an:+}"
            fp = f"{slot.gleis} an {z1}{v1}, ab {z2}{v2}"

        return f"{name} ({von} - {nach}): {fp}"

    def on_resize(self, event):
        self.grafik_update()

    def on_button_press(self, event):
        if self._auswahl and not self._pick_event:
            self._auswahl = []
            self.ui.zuginfoLabel.setText("")
            self.grafik_update()
            self.update_actions()

        self._pick_event = False

    def on_button_release(self, event):
        pass

    def on_pick(self, event):
        self._pick_event = True

        if event.mouseevent.inaxes == self._axes:
            gleis = self._gleise[round(event.mouseevent.xdata)]
            zeit = event.mouseevent.ydata
            text = []
            auswahl = []
            if isinstance(event.artist, mpl.patches.Rectangle):
                for slot in self._gleis_slots[gleis]:
                    if slot.zeit <= zeit <= slot.zeit + slot.dauer:
                        auswahl.append(slot)
                        text.append(self.get_slot_hint(slot))

            self.ui.zuginfoLabel.setText("\n".join(text))
            self._auswahl = auswahl
            self.grafik_update()
            self.update_actions()

    @pyqtSlot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)
        self.gleisauswahl.gleise_definieren(self.anlage)
        self.gleisauswahl.set_auswahl(self._gleise)
        self.ui.gleisView.expandAll()

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self._gleise = sorted(self.gleisauswahl.get_auswahl(), key=gleisname_sortkey)
        self.daten_update()
        self.grafik_update()

    @pyqtSlot()
    def page_changed(self):
        self.update_actions()

    @pyqtSlot()
    def action_plus_eins(self):
        pass

    @pyqtSlot()
    def action_minus_eins(self):
        pass

    @pyqtSlot()
    def action_loeschen(self):
        pass

