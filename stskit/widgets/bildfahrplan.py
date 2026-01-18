"""
Bildfahrplanfenster
"""

from collections import namedtuple
import logging
from typing import Generator, Optional, Tuple, Iterable

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


AuswahlMuster = namedtuple(
    "AuswahlMuster",
    "index typ knoten kante"
)

def auswahl_muster_filtern(alle_muster: Iterable[AuswahlMuster],
                           index: int | None = None,
                           typ: str | None = None) -> Generator[AuswahlMuster, None, None]:
    """
    Liste von Auswahlmustern nach Index und/oder Typ filtern
    """
    for muster in alle_muster:
        if (index is None or muster.index == index) and (typ is None or muster.typ == typ):
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

        self.strecke_model.setStringList(map(str, self.plot.strecke))

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
        auswahl_index_typen = {(m.index, m.typ) for m in auswahl_muster}

        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'A-Ab', 'A-An', 'H-Ab', 'P-An'}))
        self.ui.actionPlusEins.setEnabled(w)
        self.ui.actionMinusEins.setEnabled(w)
        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'A-Ab', 'A-An'}))
        self.ui.actionLoeschen.setEnabled(w)

        w1 = (len(auswahl_indices) == 2 and
             bool(auswahl_index_typen.intersection({(0, 'H-Ab'), (0, 'S')})) and
             bool(auswahl_index_typen.intersection({(1, 'H-Ab')})))
        self.ui.actionAbfahrtAbwarten.setEnabled(w1)
        w2 = (len(auswahl_indices) == 2 and
             bool(auswahl_index_typen.intersection({(0, 'H-Ab'), (0, 'S')})) and
             bool(auswahl_index_typen.intersection({(1, 'An-H')})))
        self.ui.actionAnkunftAbwarten.setEnabled(w2)
        w3 = (len(auswahl_indices) == 2 and
             bool(auswahl_index_typen.intersection({(0, 'H-Ab'), (0, 'S')})) and
             bool(auswahl_index_typen.intersection({(1, 'H-Ab'), (1, 'S')})))
        self.ui.actionKreuzung.setEnabled(w3)

        w = len(auswahl_indices) == 1 and bool(auswahl_typen.intersection({'H-Ab', 'S'}))
        if w:
            m1 = next(auswahl_muster_filtern(auswahl_muster, index=0, typ='H-Ab'), None)
            m2 = next(auswahl_muster_filtern(auswahl_muster, index=0, typ='S'), None)
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
                    muster.append(AuswahlMuster(index, 'S', node_data, edge_data))
                continue

            try:
                for u, v, data in self.plot.bildgraph.in_edges(node_label, data=True):
                    if data.typ == 'A':
                        muster.append(AuswahlMuster(index, 'A-' + node_data.typ, node_data, data))
                    elif node_data['typ'] == 'Ab' and data['typ'] in {'B', 'D', 'H'}:
                        muster.append(AuswahlMuster(index, 'H-Ab', node_data, data))
                    elif node_data['typ'] == 'An' and data['typ'] == 'P':
                        muster.append(AuswahlMuster(index, 'P-An', node_data, data))
                for u, v, data in self.plot.bildgraph.out_edges(node_label, data=True):
                    if node_data['typ'] == 'An' and data['typ'] in {'B', 'D', 'H'}:
                        muster.append(AuswahlMuster(index, 'An-H', node_data, data))
            except KeyError:
                pass

        return muster

    @Slot()
    def action_plus_eins(self):
        """
        Dauer erhöhen

        Die folgenden Fälle sind möglich. Der erste zutreffende wird ausgeführt.
        - Anschlusszeit erhöhen: Ausgewählter Knoten hat eingehende Kante A. (A-An, A-Ab)
            Das fdl-Attribut der Kante wird um eine Minute erhöht.
        - Haltezeit erhöhen: Ausgewählter Knoten ist Abfahrt von Kante B, D oder H. (H-Ab)
            Das fdl-Attribut der Haltekante wird um eine Minute erhöht.
        - Fahrzeit erhöhen: Ausgewählter Knoten ist Ankunft von Kante P. (P-An)
            Das fdl-Attribut der Fahrtkante wird um eine Minute erhöht.
        """

        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_knoten[0]]
        except (IndexError, KeyError):
            return
        try:
            self.zentrale.betrieb.wartezeit_aendern(ziel, 1, True)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    @Slot()
    def action_minus_eins(self):
        """
        Dauer erniedrigen

        Die folgenden Fälle sind möglich. Der erste zutreffende wird ausgeführt.
        - Anschlusszeit erniedrigen: Ausgewählter Knoten hat eingehende Kante A
        - Haltezeit erniedrigen: Ausgewählter Knoten ist Abfahrt von Kante B, D oder H
        - Fahrzeit erniedrigen: Ausgewählter Knoten ist Ankunft von Kante P
        """

        try:
            ziel = self.plot.bildgraph.nodes[self.plot.auswahl_knoten[0]]
        except (IndexError, KeyError):
            return
        try:
            self.zentrale.betrieb.wartezeit_aendern(ziel, -1, True)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

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
        self.grafik_update()
        self.update_actions()

    @Slot()
    def action_abfahrt_abwarten(self):
        """
        Abfahrt eines Zuges abwarten, Ueberholung

        Mögliche Auswahl von Kanten und Knoten:
        - Wartender Zug:
          - Regulärer Abfahrtsknoten am Kantenanfang: erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: erlaubt, Betriebshalt wird eingefügt.
          - Regulärer Ankunftsknoten am Kantenende: nicht erlaubt!
          - Freier Auswahlknoten: nicht erlaubt!
        - Abzuwartender Zug:
          - Regulärer Abfahrtsknoten am Kantenanfang: erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: nicht erlaubt! (Zuerst manuell einen Betriebshalt einfuegen.)
          - Regulärer Ankunftsknoten am Kantenende: nicht erlaubt!
          - Freier Auswahlknoten: nicht erlaubt!
        - Knoten in verschiedenen Bahnhöfen: erlaubt, aber möglicherweise nicht sinnvoll.
        """

        nodes = self.kann_abfahrt_abwarten()
        if nodes is None:
            return
        try:
            ziel, referenz = nodes
            self.zentrale.betrieb.abfahrt_abwarten(ziel, referenz, wartezeit=2)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_abfahrt_abwarten(self) -> Optional[Tuple[EreignisGraphNode, EreignisGraphNode]]:
        """
        Prüfen, ob "Abfahrt abwarten" für aktuelle Auswahl möglich ist

        Bedingungen siehe action_abfahrt_abwarten.

        Returns:
            Zielereignis und Referenzereignis, wenn der Befehl möglich ist, sonst None
        """

        try:
            ziel_edge = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[0])
            if ziel_edge.typ not in {'P'}:
                return None
            ziel_node = self.plot.auswahl_knoten[0]
            ziel_data = self.plot.bildgraph.nodes[ziel_node]
            if ziel_node != self.plot.auswahl_kanten[0][0]:
                return None
            if ziel_node.typ not in {'Ab', 'An'}:
                return None
        except (IndexError, KeyError):
            return None

        try:
            ref_edge = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[1])
            if ref_edge.typ not in {'P'}:
                return None
            ref_node = self.plot.auswahl_knoten[1]
            ref_data = self.plot.bildgraph.nodes[ref_node]
            if ref_node != self.plot.auswahl_kanten[1][0]:
                return None
            if ref_node.typ not in {'Ab'}:
                return None
        except (IndexError, KeyError):
            return None

        if ziel_node.zid == ref_node.zid:
            return None
        if ziel_data.bst != ref_data.bst:
            return None

        return ziel_data, ref_data

    @Slot()
    def action_ankunft_abwarten(self):
        """
        Ankunft eines Zuges (Anschluss) abwarten

        Mögliche Auswahl von Kanten und Knoten:
        - Wartender Zug:
          - Regulärer Abfahrtsknoten am Kantenanfang: erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: erlaubt, Betriebshalt wird eingefügt.
          - Regulärer Ankunftsknoten am Kantenende: erlaubt! (halbe Kreuzung)
          - Freier Auswahlknoten: nicht erlaubt!
        - Abzuwartender Zug:
          - Regulärer Abfahrtsknoten am Kantenanfang: nicht erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: nicht erlaubt!
          - Regulärer Ankunftsknoten am Kantenende: erlaubt!
          - Freier Auswahlknoten: nicht erlaubt!
        - Knoten in verschiedenen Bahnhöfen: erlaubt, aber möglicherweise nicht sinnvoll.
        """

        nodes = self.kann_ankunft_abwarten()
        if nodes is None:
            return
        try:
            ziel, referenz = nodes
            self.zentrale.betrieb.ankunft_abwarten(ziel, referenz, wartezeit=1)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_ankunft_abwarten(self) -> Optional[Tuple[EreignisGraphNode, EreignisGraphNode]]:
        """
        Prüfen, ob "Ankunft abwarten" für aktuelle Auswahl möglich ist

        Bedingungen siehe action_abfahrt_abwarten.

        Returns:
            Zielereignis und Referenzereignis, wenn der Befehl möglich ist, sonst None
        """

        try:
            ziel_edge = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[0])
            if ziel_edge.typ not in {'P'}:
                return None
            ziel_node = self.plot.auswahl_knoten[0]
            ziel_data = self.plot.bildgraph.nodes[ziel_node]
            if ziel_node != self.plot.auswahl_kanten[0][0] and ziel_node != self.plot.auswahl_kanten[0][1]:
                return None
            if ziel_node.typ not in {'Ab', 'An'}:
                return None
        except (IndexError, KeyError):
            return None

        try:
            ref_edge = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[1])
            if ref_edge.typ not in {'P'}:
                return None
            ref_node = self.plot.auswahl_knoten[1]
            ref_data = self.plot.bildgraph.nodes[ref_node]
            if ref_node != self.plot.auswahl_kanten[1][1]:
                return None
            if ref_node.typ not in {'An'}:
                return None
        except (IndexError, KeyError):
            return None

        if ziel_node.zid == ref_node.zid:
            return None
        if ziel_data.bst != ref_data.bst:
            return None

        return ziel_data, ref_data

    @Slot()
    def action_kreuzung_abwarten(self):
        """
        Gegenseitige Ankunft abwarten (Kreuzung)

        Mögliche Auswahl von Kanten und Knoten:
        - Beide Züge:
          - Regulärer Abfahrtsknoten am Kantenanfang: nicht erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: nicht erlaubt!
          - Regulärer Ankunftsknoten am Kantenende: erlaubt!
          - Freier Auswahlknoten: nicht erlaubt!
        - Knoten in verschiedenen Bahnhöfen: erlaubt, aber möglicherweise nicht sinnvoll.
        """

        nodes = self.kann_kreuzung_abwarten()
        if nodes is None:
            return
        try:
            ankunft1, ankunft2 = nodes
            self.zentrale.betrieb.kreuzung_abwarten(ankunft1, ankunft2, wartezeit=0)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_kreuzung_abwarten(self) -> Tuple[EreignisGraphNode, EreignisGraphNode] | None:
        try:
            edge1 = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[0])
            if edge1.typ not in {'P'}:
                return None
            node1 = self.plot.auswahl_knoten[0]
            data1 = self.plot.bildgraph.nodes[node1]
            if node1 != self.plot.auswahl_kanten[0][1]:
                return None
            if node1.typ not in {'An'}:
                return None
        except (IndexError, KeyError):
            return None

        try:
            edge2 = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[1])
            if edge2.typ not in {'P'}:
                return None
            node2 = self.plot.auswahl_knoten[1]
            data2 = self.plot.bildgraph.nodes[node2]
            if node2 != self.plot.auswahl_kanten[1][1]:
                return None
            if node2.typ not in {'An'}:
                return None
        except (IndexError, KeyError):
            return None

        if node1.zid == node2.zid:
            return None
        if data1.bst != data2.bst:
            return None

        return data1, data2

    @Slot()
    def action_betriebshalt_einfuegen(self):
        """
        Betriebshalt einfügen

        Mögliche Auswahl von Kanten und Knoten:
          - Regulärer Abfahrtsknoten: nicht erlaubt!
          - Regulärer Ankunftsknoten am Kantenanfang: erlaubt!
          - Regulärer Ankunftsknoten am Kantenende: erlaubt!
          - Freier Auswahlknoten (Bahnhof verschieden von Kantenenden): erlaubt!
        """

        node_data = self.kann_betriebshalt_einfuegen()
        if node_data is None:
            return
        else:
            node, data = node_data

        if data.typ == 'S':
            gleise = sorted(self.anlage.bahnhofgraph.bahnhofgleise(data.bst.name))
            dlg = GleiswahlDialog(gleise, parent=self)
            if dlg.exec():
                gleis = BahnhofElement('Gl', dlg.auswahl)
            else:
                return
        else:
            gleis = data.plan_bst

        data.gleis_bst = data.plan_bst = gleis
        data.gleis = data.plan = gleis.name
        try:
            self.zentrale.betrieb.betriebshalt_einfuegen(node, data.gleis_bst, data.t_plan, wartezeit=1)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_betriebshalt_einfuegen(self) -> Tuple[EreignisLabelType, EreignisGraphNode] | None:
        """
        Prüfen, ob bei der aktuellen Trassenauswahl ein Betriebshalt eingefügt werden kann

        Returns:
            Label des Referenzknotens und Daten des ausgewählten Knotens, wenn ein Halt eingefügt werden kann, sonst None.
            Referenz und Auswahl gehören zum gleichen Knoten, wenn der Knoten in einen Betriebshalt umgewandelt werden kann.
            Wenn ein neuer Halt eingefügt werden muss, ist die Referenz der Ausgangsknoten der gewählten Kante.
        """
        try:
            edge1 = self.plot.bildgraph.get_edge_data(*self.plot.auswahl_kanten[0])
            if edge1.typ not in {'P'}:
                return None
            node1 = self.plot.auswahl_knoten[0]
            data1 = self.plot.bildgraph.nodes[node1]
            if node1.typ == 'S' and self.anlage.bahnhofgraph.has_node(data1.bst):
                node1 = self.plot.auswahl_kanten[0][0]
            elif node1.typ == 'Ab':
                pass
            else:
                return None
        except (AttributeError, IndexError, KeyError):
            return None

        return node1, data1

    @Slot()
    def action_betriebshalt_loeschen(self):
        node_data = self.kann_betriebshalt_loeschen()
        if node_data is None:
            return
        else:
            node, data = node_data

        try:
            self.zentrale.betrieb.betriebshalt_loeschen(node)
        except (KeyError, ValueError) as e:
            self.ui.zuginfoLabel.setText(str(e))

        self.plot.clear_selection()
        self.grafik_update()
        self.update_actions()

    def kann_betriebshalt_loeschen(self) -> Tuple[EreignisLabelType, EreignisGraphEdge] | None:
        """
        Prüfen, ob bei der aktuellen Trassenauswahl ein Betriebshalt gelöscht werden kann

        Returns:
            Label des ausgewählten Knotens und Kante des Betriebshalts, wenn ein Halt gelöscht werden kann, sonst None.
        """

        try:
            node = self.plot.auswahl_knoten[0]
        except (IndexError, KeyError):
            return None

        try:
            for u, v, data in self.plot.bildgraph.in_edges(node, data=True):
                if data['typ'] == 'B':
                    return node, data
            for u, v, data in self.plot.bildgraph.out_edges(node, data=True):
                if data['typ'] == 'B':
                    return node, data
        except (AttributeError, IndexError, KeyError):
            return None
