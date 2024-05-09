import logging
from typing import AbstractSet, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Type, Union

import matplotlib as mpl
import networkx as nx
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QModelIndex

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from stskit.auswertung import Auswertung
from stskit.dispo.anlage import Anlage
from stskit.planung import Planung, ZugDetailsPlanung, ZugZielPlanung, FesteVerspaetung, \
    AbfahrtAbwarten, AnkunftAbwarten, ZugAbwarten
from stskit.interface.stsplugin import PluginClient
from stskit.interface.stsobj import time_to_minutes
from stskit.slotgrafik import hour_minutes_formatter, Slot, Gleisbelegung, SlotWarnung, gleis_sektor_sortkey, \
    WARNUNG_VERBINDUNG
from stskit.widgets.gleisauswahl import GleisauswahlModell
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


class GleisbelegungWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.show_zufahrten: bool = False
        self.show_bahnsteige: bool = True

        self._balken = None
        self._labels = []
        self._pick_event = False

        self._gleise: List[str] = []
        self._slot_auswahl: List[Slot] = []
        self._warnung_auswahl: List[SlotWarnung] = []
        self.belegung: Optional[Gleisbelegung] = None

        self.vorlaufzeit = 55
        self.nachlaufzeit = 5
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

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self._axes = self.display_canvas.figure.subplots()
        self.display_canvas.mpl_connect("button_press_event", self.on_button_press)
        self.display_canvas.mpl_connect("button_release_event", self.on_button_release)
        self.display_canvas.mpl_connect("pick_event", self.on_pick)
        self.display_canvas.mpl_connect("resize_event", self.on_resize)

        self.update_widgets()
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

    def update_widgets(self):
        self.ui.vorlaufzeit_spin.setValue(self.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.nachlaufzeit)
        try:
            if "Name" in self.belegung.zugbeschriftung.elemente:
                self.ui.name_button.setChecked(True)
            else:
                self.ui.nummer_button.setChecked(True)
        except AttributeError:
            pass

    @pyqtSlot()
    def vorlaufzeit_changed(self):
        try:
            self.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def nachlaufzeit_changed(self):
        try:
            self.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    def planung_update(self, *args, **kwargs):
        """
        daten und grafik neu aufbauen.

        nötig, wenn sich z.b. der fahrplan oder verspätungsinformationen geändert haben.
        einfache fensterereignisse werden von der grafikbibliothek selber bearbeitet.

        :return: None
        """

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
            gleise = [gleis for gleis in self.belegung.gleise if gleis in self.belegung.belegte_gleise]
        else:
            gleise = self.belegung.gleise
        slots = [slot for slot in self.belegung.slots.values() if slot.gleis in gleise]
        x_labels = gleise
        x_labels_pos = list(range(len(x_labels)))
        x_pos = np.asarray([gleise.index(slot.gleis) for slot in slots])

        y_bot = np.asarray([slot.zeit for slot in slots])
        y_hgt = np.asarray([slot.dauer for slot in slots])
        labels = [slot.titel for slot in slots]

        colors = {slot: self.anlage.zugschema.zugfarbe(slot.zug) for slot in slots}
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
        self.update_widgets()

    @pyqtSlot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.set_gleise(self.gleisauswahl.get_auswahl())
        self.anlage.gleissperrungen = self.gleisauswahl.get_sperrungen()
        if self.ui.name_button.isChecked():
            self.belegung.zugbeschriftung.elemente = ["Name"]
        else:
            self.belegung.zugbeschriftung.elemente = ["Nummer"]
        self.daten_update()
        self.grafik_update()

    def set_gleise(self, gleise):
        self._gleise = list(gleise)

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
            ziel2 = self._slot_auswahl[1].ziel
        except (IndexError, AttributeError):
            ziel2 = None
        try:
            ziel1 = self._slot_auswahl[0].ziel
        except (IndexError, AttributeError):
            pass
        else:
            self.planung.fdl_korrektur_loeschen(ziel1, ziel2, alle=len(self._slot_auswahl) == 1)
            self.planung.zugverspaetung_korrigieren(ziel1.zug)
            self.daten_update()
            self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_abfahrt_abwarten(self):
        try:
            self.abhaengigkeit_definieren(AbfahrtAbwarten, self._slot_auswahl[0], self._slot_auswahl[1].ziel)
        except IndexError:
            return

        self.daten_update()
        self.grafik_update()
        self.update_actions()

    @pyqtSlot()
    def action_ankunft_abwarten(self):
        try:
            self.abhaengigkeit_definieren(AnkunftAbwarten, self._slot_auswahl[0], self._slot_auswahl[1].ziel)
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
                                 wartezeit: Optional[int] = None):

        korrektur = klasse(self.planung)
        korrektur.node = slot.ziel
        korrektur.ursprung = referenz
        if wartezeit is not None:
            korrektur.wartezeit = wartezeit

        self.planung.fdl_korrektur_setzen(korrektur, slot.ziel)
        self.planung.zugverspaetung_korrigieren(slot.zug)
