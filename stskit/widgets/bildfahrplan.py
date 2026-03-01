"""
Bildfahrplanfenster
"""

from collections import namedtuple
from dataclasses import dataclass, field
from functools import partial, wraps
import logging
from typing import Callable, Generator, Optional, Tuple, Iterable

from PySide6.QtCore import Slot, QStringListModel
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6 import QtWidgets

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.ereignisgraph import EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.plugin.stsobj import time_to_minutes
from stskit.plugin.stsplugin import PluginClient
from stskit.plots.bildfahrplan import BildfahrplanPlot
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_bildfahrplan import Ui_BildfahrplanWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

@dataclass(order=True, frozen=True)
class AuswahlMuster:
    """
    Ausgewählte Kombination von Knoten und Kante

    Je nach relativer Position eines Mausklicks zu einer Trasse
    kann eines oder mehrere der folgenden Muster unterschieden werden:

        - A-An: Ankunft mit eingehender Kante vom Typ A.
        - A-Ab: Abfahrt mit eingehender Kante vom Typ A.
        - H-Ab: Abfahrt mit eingehender Kante vom Typ B, D oder H (Halt oder Durchfahrt).
        - P-An: Ankunft mit eingehender Kante vom Typ P (Fahrt).
        - An-H: Ankunft mit ausgehender Kante vom Typ B, D oder H.
        - S: Freier Auswahlknoten und Kante vom Typ P (Fahrt).

    S. BildFahrplanWindow.auswahl_unterscheiden

    Attributes:
        index: Reihenfolge des Auswahlvorgangs (0 = erste Auswahl).
        typ: Kurzbezeichnung des Musterstyps (siehe Aufzählung oben).
        knoten: Daten des ausgewählten Knotens.
            Der Knoten kann entweder der start- oder ziel-Knoten der Kante sein,
            oder im Fall des S-Musters ein freier Knoten, der im Graph nicht vorkommt.
        kante: Daten der ausgewählten Kante.
            Die Kante existiert im Bildgraph zwischen den start- und ziel-Knoten.
        start: Label des Ausgangspunkts der Kante.
            Der entsprechende Knoten muss im Bildgraph vorkommen.
        ziel: Label des Endpunkts der Kante.
            Der entsprechende Knoten muss im Bildgraph vorkommen.
    """
    index: int
    typ: str
    knoten: EreignisGraphNode = field(compare=False)
    kante: EreignisGraphEdge = field(compare=False)
    start: EreignisLabelType
    ziel: EreignisLabelType


def auswahl_muster_filtern(alle_muster: Iterable[AuswahlMuster],
                           index: int | None = None,
                           typen: set[str] | None = None) -> Generator[AuswahlMuster, None, None]:
    """
    Liste von Auswahlmustern nach Index und/oder Typ filtern
    """
    for muster in alle_muster:
        if (index is None or muster.index == index) and (typen is None or muster.typ in typen):
            yield muster


class GleiswahlDialog(QtWidgets.QDialog):
    def __init__(self, gleise: Iterable[str], parent=None):
        super(GleiswahlDialog, self).__init__(parent)

        self.auswahl: str = ""
        self.setWindowTitle("Gleis wählen")

        self.list_box = QtWidgets.QListWidget()
        self.list_box.addItems(list(gleise))
        self.list_box.currentTextChanged.connect(self.text_changed)

        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.button_box = QtWidgets.QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.list_box)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def text_changed(self, text):
        self.auswahl = text


class BildFahrplanWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale
        self.zentrale.anlage_update.register(self.anlage_update)
        self.zentrale.plan_update.register(self.plan_update)
        self.zentrale.betrieb_update.register(self.plan_update)
        self.updating = True

        self.ui = Ui_BildfahrplanWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Streckenfahrplan")

        self.display_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ui.displayLayout = QtWidgets.QHBoxLayout(self.ui.grafikWidget)
        self.ui.displayLayout.setObjectName("displayLayout")
        self.ui.displayLayout.addWidget(self.display_canvas)

        self.ui.actionAnzeige.triggered.connect(self.display_button_clicked)
        self.ui.actionSetup.triggered.connect(self.settings_button_clicked)
        self.ui.actionPlusEins.triggered.connect(self.action_plus_eins)
        self.ui.actionMinusEins.triggered.connect(self.action_minus_eins)
        self.ui.actionLoeschen.triggered.connect(self.action_loeschen)
        self.ui.actionAnkunftAbwarten.triggered.connect(self.action_ankunft_abwarten)
        self.ui.actionAbfahrtAbwarten.triggered.connect(self.action_abfahrt_abwarten)
        self.ui.actionKreuzung.triggered.connect(self.action_kreuzung_abwarten)
        self.ui.actionZugfolge.setEnabled(False)
        self.ui.actionBetriebshaltEinfuegen.triggered.connect(self.action_betriebshalt_einfuegen)
        self.ui.actionActionBetriebshaltLoeschen.triggered.connect(self.action_betriebshalt_loeschen)
        self.ui.actionVorzeitigeAbfahrt.triggered.connect(self.action_vorzeitige_abfahrt)

        self.ui.stackedWidget.currentChanged.connect(self.page_changed)

        self.vordefiniert_model = QStringListModel()
        self.ui.vordefiniert_combo.setModel(self.vordefiniert_model)
        self.ui.vordefiniert_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.von_model = QStringListModel()
        self.ui.von_combo.setModel(self.von_model)
        self.ui.von_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.via_model = QStringListModel()
        self.ui.via_combo.setModel(self.via_model)
        self.ui.via_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.nach_model = QStringListModel()
        self.ui.nach_combo.setModel(self.nach_model)
        self.ui.nach_combo.currentIndexChanged.connect(self.strecke_selection_changed)
        self.strecke_model = QStringListModel()
        self.ui.strecke_list.setModel(self.strecke_model)

        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self.plot = BildfahrplanPlot(zentrale, self.display_canvas)
        self.plot.auswahl_geaendert.register(self.plot_selection_changed)

        self.plot.default_strecke_waehlen()
        self.anlage_update()
        self.plan_update()
        self.updating = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    @property
    def client(self) -> PluginClient:
        return self.zentrale.client

    def closeEvent(self, event, /):
        self.zentrale.anlage_update.unregister(self)
        self.zentrale.plan_update.unregister(self)
        self.zentrale.betrieb_update.unregister(self)
        super().closeEvent(event)

    def anlage_update(self, *args, **kwargs):
        """
        Anlagenupdate

        Bei einem Anlagenupdate können geändert werden:
        - Bahnhofmodell und Streckendefinition
        - Zugschema
        """

        self.plot.update_strecke()
        self.update_widgets()

    def plan_update(self, *args, **kwargs):
        self.daten_update()
        self.grafik_update()
        self.update_actions()

    def daten_update(self):
        self.plot.zeit = time_to_minutes(self.client.calc_simzeit())
        self.plot.update_ereignisgraph()

    def grafik_update(self):
        self.plot.draw_graph()

    def update_widgets(self):
        """
        Widget-Zustände gemäss Plotattributen aktualisieren.
        """

        self.updating = True

        bg = self.anlage.bahnhofgraph
        bst_liste = sorted(bg.list_children(bg.root(), {'Bf', 'Anst'}))
        bst_liste = ["", *map(str, bst_liste)]
        strecken_liste = sorted(self.anlage.strecken.strecken.keys(), key=self.anlage.strecken.ordnung.get)

        self.von_model.setStringList(bst_liste)
        self.via_model.setStringList(bst_liste)
        self.nach_model.setStringList(bst_liste)
        self.vordefiniert_model.setStringList(["", *strecken_liste])

        name = self.plot.strecken_name
        von = self.plot.strecke_von
        via = self.plot.strecke_via
        nach = self.plot.strecke_nach

        try:
            self.ui.vordefiniert_combo.setCurrentIndex(self.vordefiniert_model.stringList().index(name))
        except ValueError:
            pass
        try:
            self.ui.von_combo.setCurrentIndex(self.von_model.stringList().index(str(von)))
        except ValueError:
            pass
        try:
            self.ui.via_combo.setCurrentIndex(self.via_model.stringList().index(str(via)))
        except ValueError:
            pass
        try:
            self.ui.nach_combo.setCurrentIndex(self.nach_model.stringList().index(str(nach)))
        except ValueError:
            pass

        enable_detailwahl = not bool(name)
        self.ui.von_combo.setEnabled(enable_detailwahl)
        self.ui.via_combo.setEnabled(enable_detailwahl)
        self.ui.nach_combo.setEnabled(enable_detailwahl)

        self.strecke_model.setStringList([str(be) for be in self.plot.strecke])

        if self.plot.strecken_name:
            titel = f"Streckenfahrplan {self.plot.strecken_name}"
        elif self.plot.strecke_von and self.plot.strecke_nach:
            titel = f"Streckenfahrplan {self.plot.strecke_von.name}-{self.plot.strecke_nach.name}"
        else:
            titel = "Streckenfahrplan (keine Strecke ausgewählt)"
        self.setWindowTitle(titel)

        self.ui.vorlaufzeit_spin.setValue(self.plot.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.plot.nachlaufzeit)

        self.updating = False

    def update_actions(self):
        self.updating = True

        display_mode = self.ui.stackedWidget.currentIndex() == 1
        trasse_auswahl = len(self.plot.auswahl_kanten) >= 1
        trasse_nachbar = None

        self.ui.actionSetup.setEnabled(display_mode)
        self.ui.actionAnzeige.setEnabled(not display_mode and len(self.plot.strecke) >= 2)
        self.ui.actionFix.setEnabled(display_mode and False)  # not implemented

        auswahl_muster = self.auswahl_unterscheiden() if display_mode and trasse_auswahl else []
        auswahl_indices = {m.index for m in auswahl_muster}
        auswahl_typen = {m.typ for m in auswahl_muster}
        auswahl_zid = {m.knoten.zid for m in auswahl_muster}
        auswahl_bst = {m.knoten.bst for m in auswahl_muster}
        auswahl_index_typen = {(m.index, m.typ) for m in auswahl_muster}

        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'A-Ab', 'A-An', 'H-Ab', 'P-An'}))
        self.ui.actionPlusEins.setEnabled(w)
        self.ui.actionMinusEins.setEnabled(w)
        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'A-Ab', 'A-An'}))
        self.ui.actionLoeschen.setEnabled(w)
        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'H-Ab'}))
        self.ui.actionVorzeitigeAbfahrt.setEnabled(w)

        w1 = (len(auswahl_indices) == 2 and
              len(auswahl_zid) == 2 and
              bool(auswahl_index_typen.intersection({(0, 'H-Ab')})) and
              bool(auswahl_index_typen.intersection({(1, 'H-Ab')})))
        self.ui.actionAbfahrtAbwarten.setEnabled(w1)
        w2 = (len(auswahl_indices) == 2 and
              len(auswahl_zid) == 2 and
              bool(auswahl_index_typen.intersection({(0, 'H-Ab')})) and
              bool(auswahl_index_typen.intersection({(1, 'An-H')})))
        self.ui.actionAnkunftAbwarten.setEnabled(w2)
        w3 = (len(auswahl_indices) == 2 and
              len(auswahl_zid) == 2 and
              len(auswahl_bst) == 1 and
              bool(auswahl_index_typen.intersection({(0, 'H-Ab')})) and
              bool(auswahl_index_typen.intersection({(1, 'H-Ab')})))
        self.ui.actionKreuzung.setEnabled(w3)

        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'H-Ab', 'S'}))
        if w:
            m1 = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'H-Ab'}), None)
            m2 = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'S'}), None)
            bh_aus = m1 is not None and m1.kante.typ == 'B'
            bh_ein = m2 is not None or m1 is not None and m1.kante.typ == 'D'
        else:
            bh_aus = False
            bh_ein = False
        self.ui.actionBetriebshaltEinfuegen.setEnabled(bh_ein)
        self.ui.actionActionBetriebshaltLoeschen.setEnabled(bh_aus)

        self.updating = False

    @Slot()
    def strecke_selection_changed(self):
        """
        Neue Streckenwahl von Widgets übernehmen.
        """
        if self.updating:
            return

        name = self.ui.vordefiniert_combo.currentText()
        try:
            von = BahnhofElement(*self.ui.von_combo.currentText().split(" ", 1))
        except TypeError:
            von = None
        try:
            via = BahnhofElement(*self.ui.via_combo.currentText().split(" ", 1))
        except TypeError:
            via = None
        try:
            nach = BahnhofElement(*self.ui.nach_combo.currentText().split(" ", 1))
        except TypeError:
            nach = None

        changed = name != self.plot.strecken_name
        if not name:
            changed = changed or \
                      von != self.plot.strecke_von or \
                      nach != self.plot.strecke_nach or \
                      via != self.plot.strecke_via

        if changed:
            self.plot.strecken_name = name
            if not name:
                self.plot.strecke_von = von
                self.plot.strecke_nach = nach
                self.plot.strecke_via = via

            self.plot.update_strecke()
            self.update_widgets()
            self.update_actions()

    @Slot()
    def settings_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(0)

    @Slot()
    def display_button_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        if self.plot.strecke_von and self.plot.strecke_nach:
            self.daten_update()
            self.grafik_update()

    @Slot()
    def page_changed(self):
        self.update_actions()

    @Slot()
    def vorlaufzeit_changed(self):
        try:
            self.plot.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @Slot()
    def nachlaufzeit_changed(self):
        try:
            self.plot.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    def plot_selection_changed(self, *args, **kwargs):
        text = "\n".join(self.plot.auswahl_text)
        self.ui.zuginfoLabel.setText(text)
        self.update_actions()

    def auswahl_unterscheiden(self) -> list[AuswahlMuster] | None:
        """
        Mustererkennung Trassenauswahl

        - A-An: Ankunft mit eingehender Kante vom Typ A.
        - A-Ab: Abfahrt mit eingehender Kante vom Typ A.
        - H-Ab: Abfahrt mit eingehender Kante vom Typ B, D oder H (Halt oder Durchfahrt).
        - P-An: Ankunft mit eingehender Kante vom Typ P (Fahrt).
        - An-H: Ankunft mit ausgehender Kante vom Typ B, D oder H.
        - S: Freier Auswahlknoten und Kante vom Typ P (Fahrt).

        Hinweis: Es können mehrere Muster gleichzeitig gegeben sein.

        Returns:
            Liste mit allen zutreffenden Mustern.
        """

        muster: list[AuswahlMuster] = []

        for index, node_label in enumerate(self.plot.auswahl_knoten):
            try:
                node_data = self.plot.bildgraph.nodes[node_label]
            except KeyError:
                continue

            if node_data.typ == 'S':
                edge_data = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[index], default=None)
                if edge_data.typ == 'P':
                    muster.append(AuswahlMuster(index, 'S', node_data, edge_data, *self.plot.auswahl_kanten[index]))
                continue

            try:
                for u, v, data in self.plot.bildgraph.in_edges(node_label, data=True):
                    if data.typ == 'A':
                        muster.append(AuswahlMuster(index, 'A-' + node_data.typ, node_data, data, u, v))
                    elif node_data['typ'] == 'Ab' and data['typ'] in {'B', 'D', 'H'}:
                        muster.append(AuswahlMuster(index, 'H-Ab', node_data, data, u, v))
                    elif node_data['typ'] == 'An' and data['typ'] == 'P':
                        muster.append(AuswahlMuster(index, 'P-An', node_data, data, u, v))
                for u, v, data in self.plot.bildgraph.out_edges(node_label, data=True):
                    if node_data['typ'] == 'An' and data['typ'] in {'B', 'D', 'H', 'E', 'F', 'K'}:
                        muster.append(AuswahlMuster(index, 'An-H', node_data, data, u, v))
            except KeyError:
                pass

        return muster

    @Slot()
    def action_plus_eins(self):
        self.action_dauer_aendern(+1, True)

    @Slot()
    def action_minus_eins(self):
        self.action_dauer_aendern(-1, True)

    def action_dauer_aendern(self, dt: int, relativ: bool):
        """
        Dauer erhöhen

        Die folgenden Fälle sind möglich. Der erste zutreffende wird ausgeführt.
        - Anschlusszeit erhöhen: Ausgewählter Knoten hat eingehende Kante A (A-An, A-Ab).
            Das fdl-Attribut der Kante wird um eine Minute erhöht.
        - Haltezeit erhöhen: Ausgewählter Knoten ist Abfahrt von Kante B, D oder H (H-Ab).
            Das fdl-Attribut der Haltekante wird um eine Minute erhöht.
        - Fahrzeit erhöhen: Ausgewählter Knoten ist Ankunft von Kante P (P-An).
            Das fdl-Attribut der Fahrtkante wird um eine Minute erhöht.
        """

        auswahl_muster = self.auswahl_unterscheiden()
        try:
            muster = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'H-Ab', 'P-An', 'A-An', 'A-Ab'}))
        except StopIteration:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return

        if muster.typ in {'A-An', 'A-Ab', 'P-An'}:
            target = muster.ziel
            kante = (muster.start, muster.ziel)
        elif muster.typ in {'H-Ab'}:
            target = muster.start
            kante = None
        else:
            return

        try:
            self.zentrale.betrieb.wartezeit_aendern(target, kante, dt, relativ)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

    @Slot()
    def action_vorzeitige_abfahrt(self):
        """
        Vorzeitige Abfahrt

        Die Wartezeit wird auf das Minimum reduziert.

        Die folgenden Fälle sind möglich. Der erste zutreffende wird ausgeführt.
        - Haltezeit verkürzen: Ausgewählter Knoten ist Abfahrt von Kante H (H-Ab).
            Das fdl-Attribut der Haltekante wird um eine Minute erhöht.
        """

        auswahl_muster = self.auswahl_unterscheiden()
        try:
            muster = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'H-Ab'}))
        except StopIteration:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return

        if muster.typ in {'H-Ab'}:
            target = muster.ziel
        else:
            return

        try:
            self.zentrale.betrieb.vorzeitige_abfahrt(target)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_loeschen(self):
        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_knoten[0]]
        except (IndexError, KeyError):
            return
        try:
            self.zentrale.betrieb.abfahrt_zuruecksetzen(ziel)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_abfahrt_abwarten(self):
        """
        Abfahrt eines Zuges abwarten, Ueberholung

        Freie Auswahl ist nicht erlaubt (zuerst Betriebshalt einfügen!).
        Bei Durchfahrt wird automatisch ein Betriebshalt erstellt.

        Erforderliches Auswahlmuster (s. `auswahl_unterscheiden`):
            - Wartender Zug: 'H-Ab' nach B/D/H-Kante.
            - Abzuwartender Zug: 'An-H'
        """

        auswahl_muster = self.auswahl_unterscheiden()
        try:
            ziel = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'H-Ab'}))
            referenz = next(auswahl_muster_filtern(auswahl_muster, index=1, typen={'H-Ab'}))
        except StopIteration:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return

        try:
            self.zentrale.betrieb.abfahrt_abwarten(ziel.knoten, referenz.knoten, wartezeit=2)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_ankunft_abwarten(self):
        """
        Ankunft eines Zuges (Anschluss) abwarten

        Freie Auswahl ist nicht erlaubt (zuerst Betriebshalt einfügen!).
        Bei Durchfahrt wird automatisch ein Betriebshalt erstellt.

        Erforderliches Auswahlmuster (s. `auswahl_unterscheiden`):
            - Wartender Zug: 'H-Ab' nach B/D/H-Kante.
            - Abzuwartender Zug: 'An-H'
        """

        auswahl_muster = self.auswahl_unterscheiden()
        try:
            ziel = next(auswahl_muster_filtern(auswahl_muster, index=0, typen={'H-Ab'}))
            referenz = next(auswahl_muster_filtern(auswahl_muster, index=1, typen={'An-H'}))
        except StopIteration:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return

        try:
            self.zentrale.betrieb.ankunft_abwarten(ziel.knoten, referenz.knoten, wartezeit=1)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_kreuzung_abwarten(self):
        """
        Gegenseitige Ankunft abwarten (Kreuzung)

        Es müssen Abfahrtsereignisse (Halt, Durchfahrt, Betriebshalt) von zwei Zügen ausgewählt sein.
        Falls am gewünschten Ort kein Fahrplaneintrag besteht, muss vorgängig ein Betriebshalt erstellt werden.

        Erforderliches Auswahlmuster (s. `auswahl_unterscheiden`):
            - Beide Züge: 'H-Ab' nach B/D/H-Kante.
        """

        auswahl_muster = self.auswahl_unterscheiden()
        auswahl_muster = sorted(auswahl_muster_filtern(auswahl_muster, typen={'H-Ab'}),
                                key=lambda k: k.index)
        auswahl_knoten = [m.knoten for m in auswahl_muster]
        try:
            self.zentrale.betrieb.kreuzung_abwarten(*auswahl_knoten, wartezeit=0)
        except (KeyError, TypeError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_betriebshalt_einfuegen(self):
        """
        Betriebshalt einfügen


        Ein Betriebshalt kann entweder an einem Fahrplanziel mit Durchfahrt
        oder an einem Bahnhof auf der Strecke (ohne Fahrplaneintrag) eingefügt werden.
        Im letzteren Fall ist ein 'freier' Knoten vom Typ S ausgewählt.
        Der Benutzer wird in einem GleiswahlDialog aufgefordert, das Zielgleis festzulegen.

        Erforderliches Auswahlmuster (s. `auswahl_unterscheiden`):
            - 'H-Ab'
            - 'S' mit 'D'-Kante
        """

        auswahl_muster = self.auswahl_unterscheiden()
        if len(auswahl_muster) == 1:
            halt_data = auswahl_muster[0].knoten
            kante = (auswahl_muster[0].start, auswahl_muster[0].ziel)
        else:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return

        match auswahl_muster[0].typ:
            case 'H-Ab':
                gleis = halt_data.gleis_bst
                zeit = halt_data.t_plan
            case 'S':
                gleise = sorted(self.anlage.bahnhofgraph.bahnhofgleise(halt_data.bst.name))
                dlg = GleiswahlDialog(gleise, parent=self)
                if dlg.exec():
                    gleis = BahnhofElement('Gl', dlg.auswahl)
                    zeit = halt_data.t_plan
                else:
                    return
            case _:
                self.ui.zuginfoLabel.setText("Ungültige Auswahl")
                return

        try:
            self.zentrale.betrieb.betriebshalt_einfuegen(halt_data, kante, gleis, zeit, wartezeit=1)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()

    @Slot()
    def action_betriebshalt_loeschen(self):
        """
        Betriebshalt löschen

        Der Betriebshalt muss ausgewählt sein und einen Dispo-Journaleintrag haben.

        Erforderliches Auswahlmuster (s. `auswahl_unterscheiden`):
            - 'H-Ab' mit 'B'-Kante
        """

        auswahl_muster = self.auswahl_unterscheiden()
        if len(auswahl_muster) != 1 or auswahl_muster[0].kante.typ not in {'B'}:
            self.ui.zuginfoLabel.setText("Ungültige Auswahl")
            return
        else:
            data = auswahl_muster[0].knoten

        try:
            self.zentrale.betrieb.betriebshalt_loeschen(data)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
