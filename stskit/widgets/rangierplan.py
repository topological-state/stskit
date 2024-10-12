"""
Qt-Fenster Rangierplan
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PyQt5 import Qt, QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement
from stskit.model.signalgraph import SignalGraph
from stskit.model.zielgraph import ZielGraph, ZielGraphNode, ZielLabelType
from stskit.model.zuggraph import ZugGraph, ZugGraphNode
from stskit.plugin.stsobj import format_minutes, format_verspaetung
from stskit.qt.ui_rangierplan import Ui_RangierplanWidget


# fragen
# - erhalten wir ereignisse fuer loks? speziell: einfahrt, ausfahrt, kuppeln
#   rothalt erhalten wir, aber ohne ortsangabe
# - erkennen wir, ob die lok auf das falsche gleis programmiert ist?

RANGIERSTATUS = ["unbekannt",   # zustand unbekannt
                 "gleisfehler", # lokgleis stimmt nicht mit zuggleis überein (können wir das erkennen?)
                 "unsichtbar",  # zug ist noch nicht im stellwerk
                 "bereit",      # zug/lok ist abfahrbereit
                 "fahrt",       # zug/lok fährt
                 "halt",        # zug/lok hält vor signal oder sonstwo
                 "am gleis",    # zug ist am gleis, wo der rangiervorgang stattfinden soll
                 "erledigt"]    # lok gekuppelt bzw. abgestellt, zug abgefahren

# SVG colors: https://www.w3.org/TR/SVG11/types.html#ColorKeywords
STATUSFARBE = {"unbekannt": QtGui.QColor("white"),
               "gleisfehler": QtGui.QColor("orangered"),
               "unsichtbar": QtGui.QColor("white"),
               "bereit": QtGui.QColor("khaki"),
               "fahrt": QtGui.QColor("limegreen"),
               "halt": QtGui.QColor("tomato"),
               "am gleis": QtGui.QColor("skyblue"),
               "erledigt": QtGui.QColor("gray"),
               "default": QtGui.QColor("white")
                }

@dataclass
class Rangierdaten:
    vorgang: str = ""
    zid: int = ""
    name: str = ""
    von: str = ""
    nach: str = ""

    fid: ZielLabelType = None
    gleis: str = ""
    plan: str = ""
    p_an: Union[int, float] = 0
    p_ab: Union[int, float] = 0
    v_an: Union[int, float] = 0
    v_ab: Union[int, float] = 0
    t_an: Union[int, float] = 0

    zug_status: str = "unbekannt"
    # die lok-id wird erst beim abkuppeln bekannt
    lok_zid: Optional[int] = None
    lok_nach: Optional[BahnhofElement] = None
    lok_status: str = "unbekannt"
    # die ersatzlok wird erst bei der abfrage bekannt
    ersatzlok_zid: Optional[int] = None
    ersatzlok_von: Optional[BahnhofElement] = None
    ersatzlok_status: str = "unbekannt"


class Rangiertabelle:
    def __init__(self, zuggraph: ZugGraph, zielgraph: ZielGraph, bahnhofgraph: BahnhofGraph, signalgraph: SignalGraph):
        self.bahnhofgraph = bahnhofgraph
        self.signalgraph = signalgraph
        self.zuggraph = zuggraph
        self.zielgraph = zielgraph
        self.rangierliste: Dict[ZielLabelType, Rangierdaten] = {}
        self.loks: Dict[str, int] = {}
        self.ersatzloks: Dict[str, int] = {}

    def update(self):
        self.loks_suchen()
        self.zuege_suchen()
        self.zuege_aktualisieren()

    def _neue_rangierdaten(self,
                           zug: ZugGraphNode,
                           ziel: ZielGraphNode,
                           **kwargs) -> Rangierdaten:
        """
        unveraenderliche attribute einmalig initialisieren
        :param zug:
        :param ziel:
        :param kwargs:
        :return:
        """

        rd = Rangierdaten(**kwargs)
        rd.zid = zug.zid
        rd.fid = ziel.fid
        rd.name = zug.name
        rd.von = zug.von
        rd.nach = zug.nach
        rd.plan = ziel.plan
        rd.gleis = zug.gleis

        return rd

    def zuege_suchen(self):
        for fid, ziel in self.zielgraph.nodes(data=True):
            if fid in self.rangierliste:
                continue

            if ziel.lokumlauf:
                zug = self.zuggraph.nodes[fid.zid]
                rd = self._neue_rangierdaten(zug, ziel, vorgang="Lokumlauf")
                rd.ersatzlok_von = rd.lok_nach = BahnhofElement("Gl", ziel.gleis)
                self._init_zugstatus(rd, zug)
                self.rangierliste[fid] = rd

            elif (enrs := ziel.lokwechsel) is not None:
                zug = self.zuggraph.nodes[fid.zid]
                rd = self._neue_rangierdaten(zug, ziel, vorgang="Lokwechsel")
                # anhand der enr herausfinden, welches die ersatzlok ist!
                abstellgleise = [self.bahnhofgraph.find_gleis_enr(enr) for enr in enrs]
                #abstellgleisdaten = {agl: self.bahnhofgraph.nodes[agl] for agl in abstellgleise if agl is not None}
                anschluesse = [self.signalgraph.nodes[enr] for enr in enrs]

                for agl, anschluss in zip(abstellgleise, anschluesse):
                    if anschluss.typ == 6:
                        rd.ersatzlok_von = agl
                    elif anschluss.typ == 7:
                        rd.lok_nach = agl

                self._init_zugstatus(rd, zug)
                self.rangierliste[fid] = rd

    def zuege_aktualisieren(self):
        for fid, rd in self.rangierliste.items():
            ziel = self.zielgraph.nodes[fid]
            zug = self.zuggraph.nodes[fid.zid]

            rd.gleis = ziel.gleis
            rd.p_an = ziel.p_an
            rd.p_ab = ziel.p_ab
            rd.v_an = ziel.v_an
            rd.v_ab = ziel.v_ab
            rd.t_an = ziel.p_an + ziel.v_an

            if rd.lok_zid is None:
                try:
                    rd.lok_zid = self.loks[rd.name]
                    rd.lok_status = "unbekannt"
                except KeyError:
                    pass
                else:
                    self._init_lokstatus(rd, self.zuggraph.nodes[rd.lok_zid])

            if rd.ersatzlok_zid is None:
                try:
                    rd.ersatzlok_zid = self.ersatzloks[rd.name]
                    rd.ersatzlok_status = "unbekannt"
                except KeyError:
                    pass
                else:
                    self._init_ersatzlokstatus(rd, self.zuggraph.nodes[rd.ersatzlok_zid])

    def _init_zugstatus(self, rd: Rangierdaten, zug: ZugGraphNode):
        """

        :param rd:
        :return:
        """

        if rd.zug_status != "unbekannt":
            return rd.zug_status

        if zug.sichtbar:
            if rd.ersatzlok_zid and rd.ersatzlok_status == "erledigt":
                status = "erledigt"
            elif zug.amgleis and zug.plangleis == rd.plan:
                status = "am gleis"
            else:
                status = "fahrt"
        elif zug.ausgefahren:
            status = "erledigt"
        else:
            status = "unsichtbar"

        rd.zug_status = status
        return status

    def _init_lokstatus(self, rd: Rangierdaten, lok: ZugGraphNode):
        """
        lokstqtus initialisieren

        :param rd:
        :param lok:
        :return:
        """

        if rd.lok_status != "unbekannt":
            return rd.lok_status
        if lok.sichtbar:
            status = "bereit"
        elif lok.ausgefahren:
            status = "erledigt"
        else:
            status = "unsichtbar"

        rd.zug_status = status
        return status

    def _init_ersatzlokstatus(self, rd: Rangierdaten, lok: ZugGraphNode):
        """
        ersatzlokstatus initialisieren

        :param rd:
        :param lok:
        :return:
        """

        if rd.ersatzlok_status != "unbekannt":
            return rd.ersatzlok_status
        if lok.sichtbar:
            status = "bereit"
        elif lok.ausgefahren:
            status = "erledigt"
        else:
            status = "unsichtbar"

        rd.zug_status = status
        return status

    def loks_suchen(self):
        """
        Loks und Ersatzloks im Zuggraph suchen

        """
        for zid, zug in self.zuggraph.nodes(data=True):
            try:
                parts = zug.name.split()
            except AttributeError:
                continue

            if parts[0] == "Lok":
                zug_name = " ".join(parts[1:])
                self.loks[zug_name] = zid
            elif parts[0] == "Ersatzlok":
                zug_name = " ".join(parts[1:])
                self.ersatzloks[zug_name] = zid


class RangiertabelleModell(QtCore.QAbstractTableModel):
    """
    Datenmodell für Rangiertabelle
    """

    def __init__(self, zuggraph: ZugGraph, zielgraph: ZielGraph, bahnhofgraph: BahnhofGraph, signalgraph: SignalGraph):
        super().__init__()

        self._columns: List[str] = ['Zug',
                                    'Von',
                                    'Ankunft',
                                    'Abfahrt',
                                    'Gleis',
                                    'Status',
                                    'Verspätung',
                                    'Vorgang',
                                    'Lok nach',
                                    'Lok Status',
                                    'Ersatzlok von',
                                    'Ersatzlok Status']
        self._rangierziele: List[ZielLabelType] = []
        self.zuggraph = zuggraph
        self.zielgraph = zielgraph
        self.bahnhofgraph = bahnhofgraph
        self.signalgraph = signalgraph
        self.rangiertabelle = Rangiertabelle(zuggraph, zielgraph, bahnhofgraph, signalgraph)

    def update(self):
        self.beginResetModel()
        self.rangiertabelle.update()
        self._rangierziele = list(self.rangiertabelle.rangierliste.keys())
        self.endResetModel()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return len(self._columns)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self._rangierziele)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        """
        daten pro zelle ausgeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - UserRole gibt die originaldaten aus (zum sortieren benötigt).
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - CheckStateRole gibt an, ob ein zug am gleis steht.
            - ForegroundRole färbt die eingefahrenen, ausgefahrenen und noch unsichtbaren züge unterschiedlich ein.
            - TextAlignmentRole richtet den text aus.
        :return: verschiedene
        """

        if not index.isValid():
            return None

        try:
            fid = self._rangierziele[index.row()]
            rd = self.rangiertabelle.rangierliste[fid]
            col = self._columns[index.column()]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.UserRole:
            if col == 'ID':
                return rd.zid
            elif col == 'Zug':
                return rd.name
            elif col == 'Von':
                return rd.von
            elif col == 'Ankunft':
                return rd.t_an
            elif col == 'Abfahrt':
                return rd.p_ab
            elif col == 'Gleis':
                return rd.gleis
            elif col == 'Status':
                return rd.zug_status
            elif col == 'Verspätung':
                return rd.v_an
            elif col == 'Vorgang':
                return rd.vorgang
            elif col == 'Lok nach':
                return rd.lok_nach
            elif col == 'Lok Status':
                return rd.lok_status
            elif col == 'Ersatzlok von':
                return rd.ersatzlok_von
            elif col == 'Ersatzlok Status':
                return rd.ersatzlok_status
            else:
                return None

        if role == QtCore.Qt.DisplayRole:
            if col == 'ID':
                return rd.zid
            elif col == 'Zug':
                return rd.name
            elif col == 'Von':
                return rd.von
            elif col == 'Ankunft':
                return format_minutes(rd.t_an)
            elif col == 'Abfahrt':
                return format_minutes(rd.p_ab)
            elif col == 'Gleis':
                return rd.gleis
            elif col == 'Status':
                return rd.zug_status
            elif col == 'Verspätung':
                return format_verspaetung(rd.v_an)
            elif col == 'Vorgang':
                return rd.vorgang
            elif col == 'Lok nach':
                return rd.lok_nach.name
            elif col == 'Lok Status':
                return rd.lok_status
            elif col == 'Ersatzlok von':
                return rd.ersatzlok_von.name
            elif col == 'Ersatzlok Status':
                return rd.ersatzlok_status
            else:
                return None

        elif role == QtCore.Qt.ForegroundRole:
            # rgb = self.zugschema.zugfarbe_rgb(zug)
            # farbe = QtGui.QColor(*rgb)

            if col == 'ID':
                return STATUSFARBE["default"]
            elif col == 'Zug':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Von':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Ankunft':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Abfahrt':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Gleis':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Status':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Verspätung':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Vorgang':
                return STATUSFARBE[getattr(rd, "zug_status", "default")]
            elif col == 'Lok nach':
                return STATUSFARBE[getattr(rd, "lok_status", "default")]
            elif col == 'Lok Status':
                return STATUSFARBE[getattr(rd, "lok_status", "default")]
            elif col == 'Ersatzlok von':
                return STATUSFARBE[getattr(rd, "ersatzlok_status", "default")]
            elif col == 'Ersatzlok Status':
                return STATUSFARBE[getattr(rd, "ersatzlok_status", "default")]
            else:
                return None

        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile und -spalte aus.
        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den spaltentitel oder die zug-id aus.
        :return:
        """
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._columns[section]
            elif orientation == QtCore.Qt.Vertical:
                return self._rangierziele[section]


class RangierplanWindow(QtWidgets.QWidget):
    """
    Rangierplanwidget

    """

    def __init__(self, zentrale, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)

        self.ui = Ui_RangierplanWidget()
        self.ui.setupUi(self)

        self.setWindowTitle("Rangierplan")

        self.rangiertabelle_modell = RangiertabelleModell(zentrale.anlage.zuggraph, zentrale.anlage.zielgraph,
                                                          zentrale.anlage.bahnhofgraph, zentrale.anlage.signalgraph)
        self.rangiertabelle_modell.zugschema = self.zentrale.anlage.zugschema

        self.ui.zugliste_view.setModel(self.rangiertabelle_modell)
        self.ui.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.zugliste_view.sortByColumn(0, 0)
        self.ui.zugliste_view.setSortingEnabled(True)

    def planung_update(self, *args, **kwargs) -> None:
        self.rangiertabelle_modell.update()

        self.ui.zugliste_view.resizeColumnsToContents()
        self.ui.zugliste_view.resizeRowsToContents()
