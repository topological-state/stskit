"""
Qt-Fenster Rangierplan
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from PyQt5 import Qt, QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QModelIndex, QSortFilterProxyModel, QItemSelectionModel

from stskit.dispo.anlage import Anlage
from stskit.plugin.stsobj import Ereignis
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


class Lokstatus:
    """
    Status von rangierenden Loks

    Der Status setzt sich aus zwei Elementen zusammen:
    1. Fahrzustand
    2. Gleisfehlerwarnung

    Die Gleisfehlerwarnung überlagert den Fahrzustand.
    """

    WERTEBEREICH = {"unbekannt",  # zustand unbekannt
                    "gleisfehler",  # lokgleis stimmt nicht mit zuggleis überein (können wir das erkennen?)
                    "unsichtbar",  # zug ist noch nicht im stellwerk
                    "unterwegs",  # zug/lok fährt
                    "halt",  # zug/lok hält vor signal oder sonstwo
                    "am gleis",  # zug ist am gleis, wo der rangiervorgang stattfinden soll
                    "erledigt"}

    DARSTELLUNGSTEXT = {"unbekannt": "",
                        "gleisfehler": "Gleisfehler",
                        "unsichtbar": "",
                        "unterwegs": "Fahrt",
                        "halt": "Halt",
                        "am gleis": "am Gleis",
                        "erledigt": "erledigt"}

    # SVG colors: https://www.w3.org/TR/SVG11/types.html#ColorKeywords
    DARSTELLUNGSFARBE = {"unbekannt": QtGui.QColor("white"),
                         "gleisfehler": QtGui.QColor("orangered"),
                         "unsichtbar": QtGui.QColor("white"),
                         "unterwegs": QtGui.QColor("limegreen"),
                         "halt": QtGui.QColor("tomato"),
                         "am gleis": QtGui.QColor("skyblue"),
                         "erledigt": QtGui.QColor("gray")}

    EREIGNIS_STATUS_MAP = {
        'einfahrt': 'unterwegs',
        'ausfahrt': 'erledigt',
        'ankunft': 'am gleis',
        'abfahrt': 'unterwegs',
        'rothalt': 'halt',
        'wurdegruen': 'unterwegs',
        'kuppeln': 'erledigt'

    }

    def __init__(self):
        self._status = "unbekannt"
        self._letztes_gleis = ""
        self._gleisfehler = False

    def __str__(self) -> str:
        return self.DARSTELLUNGSTEXT[self.status]

    @property
    def status(self) -> str:
        """
        Zusammenfassender Status einer Lok

        Der Status setzt sich aus zwei Elementen zusammen:
        1. Fahrzustand als String-Wert im Attribut _status
        2. Gleisfehlerwarnung als Bool-Wert im Attribut _gleisfehler

        Die Gleisfehlerwarnung überlagert den Fahrzustand.

        Der Property-Setter kann den Gleisfehlerzustand nur setzen, aber nicht löschen.
        Der Gleisfehler sollte daher nur über das Gleisfehler-Property geändert werden.
        """

        if self._gleisfehler:
            return "gleisfehler"
        else:
            return self._status

    @status.setter
    def status(self, status: str) -> None:
        if status not in self.WERTEBEREICH:
            raise ValueError(f"{status} ist kein erlaubter Lokstatus.")
        if status == "gleisfehler":
            self._gleisfehler = True
        else:
            self._status = status

    @property
    def gleisfehler(self) -> bool:
        """
        Gleisfehlerwarnung

        Ein Gleisfehler zeigt an, ob die Lok auf das falsche Gleis programmiert ist.
        Solange der Gleisfehler gesetzt ist, zeigt der Status "gleisfehler".
        Wenn er zurückgesetzt wird, zeigt der Status wieder den Fahrzustand.

        Der Gleisfehler muss von extern gesetzt werden, die Klasse selber kann ihn nicht erkennen.

        :return: True, wenn ein Gleisfehler vorliegt, sonst False.
        """

        return self._gleisfehler

    @gleisfehler.setter
    def gleisfehler(self, gleisfehler: bool) -> None:
        self._gleisfehler = gleisfehler

    @property
    def qt_farbe(self) -> QtGui.QColor:
        """
        In Qt-Farbe codierter Status.

        :return: QColor
        """

        return self.DARSTELLUNGSFARBE[self.status]

    def update_von_zug(self, lok: ZugGraphNode):
        """
        lokstqtus aus Zugdaten aktualisieren.

        :param lok:
        :return: Neuer Statuswert
        """

        if self.status in {"erledigt", "halt"}:
            return self.status

        if lok.sichtbar:
            status = "unterwegs"
        elif lok.ausgefahren:
            status = "erledigt"
        else:
            status = "unsichtbar"

        self.status = status
        return self.status

    def update_von_ereignis(self, ereignis: Ereignis) -> str:
        """
        Lokstatus aus Ereignisdaten aktualisieren.

        :param ereignis:
        :return: Neuer Statuswert
        """

        if self.status in {"erledigt"}:
            pass
        else:
            status = self.EREIGNIS_STATUS_MAP.get(ereignis.art, '')
            if status:
                self.status = status

        return self.status


class Zugstatus:
    """
    Status des rangierenden Zuges
    """

    WERTEBEREICH = {"unbekannt",
                    "unsichtbar",
                    "unterwegs",
                    "halt",
                    "am gleis",
                    "bereit",
                    "erledigt"}

    DARSTELLUNGSTEXT = {"unbekannt": "",
                        "unsichtbar": "",
                        "unterwegs": "Fahrt",
                        "halt": "Halt",
                        "am gleis": "am Gleis",
                        "bereit": "bereit",
                        "erledigt": "erledigt"}

    DARSTELLUNGSFARBE = {"unbekannt": QtGui.QColor("white"),
                         "unsichtbar": QtGui.QColor("white"),
                         "bereit": QtGui.QColor("khaki"),
                         "unterwegs": QtGui.QColor("limegreen"),
                         "halt": QtGui.QColor("tomato"),
                         "am gleis": QtGui.QColor("skyblue"),
                         "erledigt": QtGui.QColor("gray")}

    EREIGNIS_STATUS_MAP = {
        'einfahrt': 'unterwegs',
        'ausfahrt': 'erledigt',
        'ankunft': 'unterwegs', # ausser ankunft am zielgleis -> am gleis
        'abfahrt': 'unterwegs', # ausser abfahrt vom zielgleis -> bereit oder erledigt
        'rothalt': 'halt',
        'wurdegruen': 'unterwegs',
    }

    def __init__(self):
        self._status = "unbekannt"
        self._letztes_gleis = ""

    def __str__(self) -> str:
        return self.DARSTELLUNGSTEXT[self.status]

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, status: str) -> None:
        if status not in self.WERTEBEREICH:
            raise ValueError(f"{status} ist kein erlaubter Zugstatus.")
        self._status = status

    @property
    def qt_farbe(self) -> QtGui.QColor:
        return self.DARSTELLUNGSFARBE[self.status]

    def update_von_zug(self, zug: ZugGraphNode, plangleis: str) -> str:
        """
        Status anhand von Zugdaten aktualisieren.

        :param zug: Zugdaten
        :param plangleis: Geplantes Gleis des Rangiervorgangs
        :return: Neuer Status
        """

        if self.status in {"erledigt", "halt", "bereit"}:
            return self.status

        if zug.sichtbar:
            if zug.amgleis and zug.plangleis == plangleis:
                status = "am gleis"
            else:
                status = "unterwegs"
        elif zug.ausgefahren:
            status = "erledigt"
        else:
            status = "unsichtbar"

        self.status = status
        return self.status


    def update_von_ereignis(self, ereignis: Ereignis, plangleis: str) -> str:
        if self.status in {"erledigt"}:
            return self.status

        status = self.EREIGNIS_STATUS_MAP.get(ereignis.art, '')

        if ereignis.art == 'ankunft':
            self._letztes_gleis = ereignis.plangleis
            if ereignis.amgleis and ereignis.plangleis == plangleis:
                status = 'am gleis'
        elif ereignis.art == 'abfahrt' and self._letztes_gleis == plangleis:
            if ereignis.amgleis:
                status = 'bereit'
            else:
                status = 'erledigt'

        if status:
            self.status = status
        return self.status


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
    t_erledigt: Union[int, float] = 0

    zug_status: Zugstatus = field(default_factory=Zugstatus)
    # die lok-id wird erst beim abkuppeln bekannt
    lok_zid: Optional[int] = None
    lok_nach: Optional[BahnhofElement] = None
    lok_status: Lokstatus = field(default_factory=Lokstatus)
    # die ersatzlok wird erst bei der abfrage bekannt
    ersatzlok_zid: Optional[int] = None
    ersatzlok_von: Optional[BahnhofElement] = None
    ersatzlok_status: Lokstatus = field(default_factory=Lokstatus)


class Rangiertabelle:
    def __init__(self, anlage: Anlage):
        self.anlage = anlage
        self.rangierliste: Dict[ZielLabelType, Rangierdaten] = {}
        # zugname, zid
        self.loks: Dict[str, int] = {}
        # zugname, zid
        self.ersatzloks: Dict[str, int] = {}
        # lok-zid, key of rangierliste (loks und ersatzloks)
        self.lok_index: Dict[int, ZielLabelType] = {}
        # zug-zid, keys of rangierliste
        self.zug_index: Dict[int, Set[ZielLabelType]] = {}

    def update(self):
        """
        Reguläre Aktualisierung der Rangiertabelle.

        1. Sucht neue Loks im Zuggraphen.
        2. Sucht Zuege, die Rangiervorgänge im Fahrplan haben.
        3. Aktualisert die Zug- und Lokstatusdaten.

        Views der Rangiertabelle müssen nachher neu eingelesen werden.
        """

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
        """
        Züge suchen, die einen Rangiervorgang im Fahrplan haben.

        Die Fahrziele mit Lokumlauf oder Lokwechsel werden in die Rangierlieste geschrieben.
        Die Rangierdaten-Objekt werden so weit wie möglich ausgefüllt.
        Die Lokdaten (zid und status) werden hier offen gelassen.

        Die Methode sucht die Einfahrts- und Ausfahrtsknoten aus dem Lokwechselflag,
        um Ziel und Herkunft der Lok bzw. Ersatzlok zu bestimmen.
        Dies ist leider nicht immer möglich, weil die Daten von der Pluginschnittstelle oft unvollständig sind.
        Wenn nur die Relation einer Lok fehlt, kann der Name dieses Anschlusses nicht angezeigt werden.
        Wenn beide Relationen fehlen, können die Ursprungs- und Ersatzloks nicht zugeordnet werden.
        """

        for fid, ziel in self.anlage.zielgraph.nodes(data=True):
            if fid in self.rangierliste:
                continue

            if ziel.lokumlauf:
                zug = self.anlage.zuggraph.nodes[fid.zid]
                rd = self._neue_rangierdaten(zug, ziel, vorgang="Lokumlauf")
                rd.lok_nach = BahnhofElement("Gl", ziel.gleis)
                rd.zug_status.update_von_zug(zug, ziel.plan)
                self.rangierliste[fid] = rd

            elif (enrs := ziel.lokwechsel) is not None:
                zug = self.anlage.zuggraph.nodes[fid.zid]
                rd = self._neue_rangierdaten(zug, ziel, vorgang="Lokwechsel")
                # anhand der enr herausfinden, welches die ersatzlok ist!
                abstellgleise = {enr: self.anlage.bahnhofgraph.find_gleis_enr(enr) or BahnhofElement("Agl", f"{enr}?") for enr in enrs}
                typen = {enr: self.anlage.signalgraph.nodes[enr]['typ'] if self.anlage.signalgraph.has_node(enr) else 999 for enr in enrs}
                sortierte_enrs = sorted(enrs, key=lambda enr: typen[enr])

                for enr, renr in zip(sortierte_enrs, reversed(sortierte_enrs)):
                    if typen[enr] == 6:
                        rd.ersatzlok_von = abstellgleise[enr]
                        if rd.lok_nach is None:
                            rd.lok_nach = abstellgleise[renr]
                    elif typen[enr] == 7:
                        rd.lok_nach = abstellgleise[enr]
                        if rd.ersatzlok_von is None:
                            rd.ersatzlok_von = abstellgleise[renr]

                rd.zug_status.update_von_zug(zug, ziel.plan)
                self.rangierliste[fid] = rd

    def zuege_aktualisieren(self):
        for fid, rd in self.rangierliste.items():
            ziel = self.anlage.zielgraph.nodes[fid]

            rd.gleis = ziel.gleis
            rd.p_an = ziel.p_an
            try:
                rd.p_ab = ziel.p_ab
            except AttributeError:
                try:
                    fid2 = self.anlage.zielgraph.next_node(fid, ersatz_erlaubt=True)
                    ziel2 = self.anlage.zielgraph.nodes[fid2]
                    rd.p_ab = ziel2.p_an
                except (AttributeError, KeyError, ValueError):
                    rd.p_ab = None

            rd.v_an = ziel.v_an
            rd.v_ab = ziel.v_ab
            rd.t_an = ziel.p_an + ziel.v_an

            if fid.zid in self.zug_index:
                self.zug_index[fid.zid].add(fid)
            else:
                self.zug_index[fid.zid] = {fid}

            if rd.lok_zid is None:
                try:
                    rd.lok_zid = self.loks[rd.name]
                    rd.lok_status.status = "unbekannt"
                except KeyError:
                    pass
                else:
                    self.lok_index[rd.lok_zid] = fid
            if rd.lok_zid is not None:
                rd.lok_status.update_von_zug(self.anlage.zuggraph.nodes[rd.lok_zid])

            if rd.ersatzlok_zid is None:
                try:
                    rd.ersatzlok_zid = self.ersatzloks[rd.name]
                    rd.ersatzlok_status.status = "unbekannt"
                except KeyError:
                    pass
                else:
                    self.lok_index[rd.ersatzlok_zid] = fid
            if rd.ersatzlok_zid is not None:
                rd.ersatzlok_status.update_von_zug(self.anlage.zuggraph.nodes[rd.ersatzlok_zid])
                self.gleisfehler_pruefen(rd)

            if rd.t_erledigt == 0:
                if (rd.zug_status.status == "erledigt" and
                        (rd.lok_zid is None or rd.lok_status.status == "erledigt") and
                        (rd.ersatzlok_zid is None or rd.ersatzlok_status.status == "erledigt")):
                    rd.t_erledigt = self.anlage.simzeit_minuten

    def gleisfehler_pruefen(self, rd: Rangierdaten):
        """
        Rangiervoraang auf Gleisfehler prüfen.

        Prüft, ob die Ersatzlok auf das gleiche Gleis wie ihr Zielzug programmiert ist.
        Wenn nicht wird ein Gleisfehler gemeldet, so dass der Fdl die Lok auf das richtige Gleis leiten kann.

        :param rd: Rangierdaten des Zuges.
        """

        if rd.ersatzlok_zid not in self.anlage.zielgraph.zuganfaenge:
            return

        for fid in self.anlage.zielgraph.zugpfad(rd.ersatzlok_zid):
            ziel = self.anlage.zielgraph.nodes[fid]
            if ziel.plan == rd.plan:
                rd.ersatzlok_status.gleisfehler = ziel.gleis != rd.gleis
                break

    def loks_suchen(self):
        """
        Loks und Ersatzloks im Zuggraph suchen

        Sucht Züge im Zuggraph, die mit dem Präfix 'Lok' oder 'Ersatzlok' beginnen und eine negative zid haben.
        Der Präfix wird abgetrennt und die Lok in den loks- bzw. ersatzloks-Dictionaries eingetragen.
        """

        for zid, zug in self.anlage.zuggraph.nodes(data=True):
            if zid >= 0:
                continue

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

    def plugin_ereignis(self, ereignis: Ereignis) -> Set[ZielLabelType]:
        """
        Lokstatus nach Plugin-Ereignis aktualisieren
        """

        rd_ids = set()

        if ereignis.zid in self.lok_index:
            rd_ids.update(self.lok_ereignis(ereignis))
        elif ereignis.zid in self.zug_index:
            rd_ids.update(self.zug_ereignis(ereignis))

        return rd_ids

    def lok_ereignis(self, ereignis: Ereignis) -> Set[ZielLabelType]:
        """
        Lok- bzw. Ersatzlokstatus gemäss Plugin-Ereignis aktualisieren.

        :param ereignis:
        :return: fid der geänderten Rangierdatensätze oder None, wenn das Ereignis keine Auswirkung hatte.
        """

        rd_ids = set()

        try:
            fid = self.lok_index[ereignis.zid]
            rd = self.rangierliste[fid]
        except KeyError:
            return rd_ids

        if ereignis.zid in self.loks.values():
            if rd.lok_status.status != 'erledigt':
                rd.lok_status.update_von_ereignis(ereignis)
                rd_ids.add(fid)
        elif ereignis.zid in self.ersatzloks.values():
            if rd.ersatzlok_status.status != 'erledigt':
                rd.ersatzlok_status.update_von_ereignis(ereignis)
                rd_ids.add(fid)
        if rd_ids and ereignis.art == 'kuppeln':
            rd.zug_status.status = 'erledigt'

        return rd_ids

    def zug_ereignis(self, ereignis: Ereignis) -> Set[ZielLabelType]:
        """
        Zugstatus gemäss Plugin-Ereignis aktualisieren.

        :param ereignis:
        :return: fid der geänderten Rangierdatensätze oder None, wenn das Ereignis keine Auswirkung hatte.
        """

        rd_ids = set()

        try:
            fids = self.zug_index[ereignis.zid]
        except KeyError:
            return rd_ids

        for fid in fids:
            rd = self.rangierliste[fid]
            if rd.zug_status.status != 'erledigt':
                rd.zug_status.update_von_ereignis(ereignis, rd.plan)
                rd_ids.add(fid)

        return rd_ids

class RangiertabelleModell(QtCore.QAbstractTableModel):
    """
    Datenmodell für Rangiertabelle
    """

    def __init__(self, anlage: Anlage):
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
        self.rangiertabelle = Rangiertabelle(anlage)

    def update(self):
        self.beginResetModel()
        self.rangiertabelle.update()
        self._rangierziele = list(self.rangiertabelle.rangierliste.keys())
        self.endResetModel()

    def plugin_ereignis(self, ereignis: Ereignis):
        fids = self.rangiertabelle.plugin_ereignis(ereignis)

        for fid in fids:
            try:
                row = self._rangierziele.index(fid)
            except ValueError:
                return
            index1 = self.index(row, self._columns.index('Status'))
            index2 = self.index(row, len(self._columns)-1)
            self.dataChanged.emit(index1, index2)

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
                return rd.zug_status.status
            elif col == 'Verspätung':
                return rd.v_an
            elif col == 'Vorgang':
                return rd.vorgang
            elif col == 'Lok nach':
                return rd.lok_nach
            elif col == 'Lok Status':
                return rd.lok_status.status
            elif col == 'Ersatzlok von':
                return rd.ersatzlok_von
            elif col == 'Ersatzlok Status':
                return rd.ersatzlok_status.status
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
                if rd.p_ab is not None:
                    return format_minutes(rd.p_ab)
            elif col == 'Gleis':
                return rd.gleis
            elif col == 'Status':
                return str(rd.zug_status)
            elif col == 'Verspätung':
                return format_verspaetung(rd.v_an)
            elif col == 'Vorgang':
                return rd.vorgang
            elif col == 'Lok nach':
                return rd.lok_nach.name
            elif col == 'Lok Status':
                return str(rd.lok_status)
            elif col == 'Ersatzlok von':
                if rd.ersatzlok_von is not None:
                    return rd.ersatzlok_von.name
            elif col == 'Ersatzlok Status':
                return str(rd.ersatzlok_status)
            else:
                return None

        elif role == QtCore.Qt.ForegroundRole:
            # rgb = self.zugschema.zugfarbe_rgb(zug)
            # farbe = QtGui.QColor(*rgb)

            if col == 'ID':
                return None
            elif col == 'Status':
                return rd.zug_status.qt_farbe
            elif col == 'Lok Status':
                return rd.lok_status.qt_farbe
            elif col == 'Ersatzlok Status':
                return rd.ersatzlok_status.qt_farbe
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


class RangiertabelleFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent=...):
        super().__init__(parent)
        self._simzeit: int = 0
        self._vorlaufzeit: int = 0
        self._nachlaufzeit: int = 15

    @property
    def simzeit(self) -> int:
        return self._simzeit

    @simzeit.setter
    def simzeit(self, minuten: int):
        self._simzeit = minuten

    @property
    def vorlaufzeit(self) -> int:
        return self._vorlaufzeit

    @vorlaufzeit.setter
    def vorlaufzeit(self, minuten: int):
        self._vorlaufzeit = minuten

    @property
    def nachlaufzeit(self) -> int:
        return self._nachlaufzeit

    @nachlaufzeit.setter
    def nachlaufzeit(self, minuten: int):
        self._nachlaufzeit = minuten

    def filterAcceptsRow(self, source_row, source_parent):
        if self.simzeit <= 0:
            return True

        rangiertabelle_modell: Optional[RangiertabelleModell] = None
        while rangiertabelle_modell is None:
            source = self.sourceModel()
            if isinstance(source, RangiertabelleModell):
                rangiertabelle_modell = source
                break

        try:
            fid = rangiertabelle_modell._rangierziele[source_row]
            rd = rangiertabelle_modell.rangiertabelle.rangierliste[fid]
        except (IndexError, KeyError):
            return False

        status = rd.zug_status.status
        if status in {"unbekannt"}:
            return False
        elif status in {"unsichtbar"}:
            if self._vorlaufzeit <= 0:
                return True

            if rd.t_an > self.simzeit + self._vorlaufzeit:
                return False
        elif status in {"bereit", "erledigt"}:
            if self._nachlaufzeit <= 0 or rd.t_erledigt == 0:
                return True
            if self.simzeit - rd.t_erledigt > self._nachlaufzeit:
                return False

        return True


class RangierplanWindow(QtWidgets.QWidget):
    """
    Rangierplanwidget

    """

    def __init__(self, zentrale, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.zentrale = zentrale
        self.zentrale.planung_update.register(self.planung_update)
        self.zentrale.plugin_ereignis.register(self.plugin_ereignis)

        self.ui = Ui_RangierplanWidget()
        self.ui.setupUi(self)

        self.setWindowTitle("Rangierplan")

        self.rangiertabelle_modell = RangiertabelleModell(zentrale.anlage)
        self.rangiertabelle_modell.zugschema = self.zentrale.anlage.zugschema

        self.rangiertabelle_sort_filter = RangiertabelleFilterProxy(self)
        self.rangiertabelle_sort_filter.setSourceModel(self.rangiertabelle_modell)
        self.rangiertabelle_sort_filter.setSortRole(QtCore.Qt.UserRole)
        self.ui.zugliste_view.setModel(self.rangiertabelle_sort_filter)
        self.ui.zugliste_view.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.ui.zugliste_view.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.ui.zugliste_view.sortByColumn(self.rangiertabelle_modell._columns.index('Ankunft'), 0)
        self.ui.zugliste_view.setSortingEnabled(True)

        self.ui.vorlaufzeit_spin.setValue(self.rangiertabelle_sort_filter.vorlaufzeit)
        self.ui.nachlaufzeit_spin.setValue(self.rangiertabelle_sort_filter.nachlaufzeit)
        self.ui.vorlaufzeit_spin.valueChanged.connect(self.vorlaufzeit_changed)
        self.ui.nachlaufzeit_spin.valueChanged.connect(self.nachlaufzeit_changed)

        self.ui.suche_zug_edit.textEdited.connect(self.suche_zug_changed)
        self.ui.suche_loeschen_button.clicked.connect(self.suche_loeschen_clicked)

    def planung_update(self, *args, **kwargs) -> None:
        self.rangiertabelle_sort_filter.simzeit = self.zentrale.simzeit_minuten
        self.rangiertabelle_modell.update()

        self.ui.zugliste_view.resizeColumnsToContents()
        self.ui.zugliste_view.resizeRowsToContents()

    def plugin_ereignis(self, *args, **kwargs) -> None:
        self.rangiertabelle_modell.plugin_ereignis(kwargs["ereignis"])

    @pyqtSlot()
    def vorlaufzeit_changed(self):
        try:
            self.rangiertabelle_sort_filter.vorlaufzeit = self.ui.vorlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def nachlaufzeit_changed(self):
        try:
            self.rangiertabelle_sort_filter.nachlaufzeit = self.ui.nachlaufzeit_spin.value()
        except ValueError:
            pass

    @pyqtSlot()
    def suche_zug_changed(self):
        text = self.ui.suche_zug_edit.text()
        if not text:
            return

        column = self.rangiertabelle_modell._columns.index("Zug")
        start = self.rangiertabelle_sort_filter.index(0, column)
        matches = self.rangiertabelle_sort_filter.match(start, QtCore.Qt.DisplayRole, text, 1, QtCore.Qt.MatchContains)

        for index in matches:
            if index.column() == column:
                self.ui.zugliste_view.selectionModel().clear()
                self.ui.zugliste_view.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Select |
                                                              QItemSelectionModel.SelectionFlag.Rows)
                break
        else:
            self.ui.zugliste_view.selectionModel().clear()

    @pyqtSlot()
    def suche_loeschen_clicked(self):
        self.ui.suche_zug_edit.clear()
