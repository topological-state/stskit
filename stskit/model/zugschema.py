"""
Zugschema und Zugbeschriftung

Das Zugschema ordnet den Zügen eine Kategorie und eine Farbe zu.
Es ist mittels Konfigurationsdateien einstellbar.

Die Zugbeschriftung definiert, wie Züge in den Grafiken beschriftet werden.

Das Modul enthält neben den Datenklassen auch Modelle für Qt-Widgets.
"""

import json
import logging
import os
import typing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import matplotlib as mpl
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QModelIndex

from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.ereignisgraph import EreignisGraphNode
from stskit.model.zielgraph import ZielGraphNode
from stskit.plugin.stsobj import ZugDetails
from stskit.model.zuggraph import ZugGraphNode

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Uebersetzung von Regionen in Schema-Regionen (Regionen, die das gleiche Schema verwenden).
# Das erste Wort des Regionsnamens ist ausschlaggebend.
REGIONEN_SCHEMA = {
    "Belgien": "Benelux",
    "Bern": "Schweiz",
    "Danmark": "Schweden",
    "Grand": "Frankreich",
    "Großbritannien": "Grossbritannien",
    "Hauts-de-France": "Frankreich",
    "Île-de-France": "Frankreich",
    "Italien": "Italien",
    "Lombardia": "Italien",
    "Luxemburg": "Benelux",
    "Merxferri": "Deutschland",
    "Niederlande": "Benelux",
    "Normandie": "Frankreich",
    "Ostschweiz": "Schweiz",
    "Polen": "Polen",
    "Sverige": "Schweden",
    "Tessin": "Schweiz",
    "Triveneto": "Italien",
    "Tschechien": "Tschechien",
    "Westschweiz": "Schweiz",
    "Zentralschweiz": "Schweiz",
    "Zürich": "Schweiz"
    }


class Zugschema:
    """
    Zugkategorien und Farbschema

    Das Zugschema legt die Zuordnung von Zügen zu Kategorien sowie die Zuordnung von Kategorien zu Farben fest.
    Beide Zuordnungsschritte sind konfigurierbar.
    Die Zuordnung von Zügen zu einer bestimmten Kategorie basiert auf Gattung und Nummer.

    Als Zugkategorien sollten nur die unter DEFAULT_KATEGORIEN vordefinierten verwendet werden,
    da diesen eine spezielle Bedeutung zukommt (z.b. ob ein Zug in der Anschlussmatrix vorkommt).

    Alle von matplotlib erkannten Farben wie auch RGB-Werte #RRGGBB können verwendet werden.
    Eine Liste von Farben gibt es unter https://matplotlib.org/stable/gallery/color/named_colors.html.
    """

    DEFAULT_KATEGORIEN = {
        "X": ["Hochgeschwindigkeitszug", "tab:red"],
        "F": ["Fernverkehr", "tab:orange"],
        "N": ["Nahverkehr", "tab:olive"],
        "S": ["S-Bahn", "tab:brown"],
        "G": ["Güterzug", "tab:blue"],
        "E": ["Schneller Güterzug", "tab:cyan"],
        "K": ["Kombiverkehr", "tab:purple"],
        "D": ["Dienstzug", "tab:green"],
        "O": ["Sonderzug", "tab:pink"],
        "R": ["Übriger Verkehr", "tab:gray"]}

    # Verfügbare zugschema-dateien. key = schema-name, value = dateipfad
    schemadateien: Dict[str, os.PathLike] = {}
    # titel = Benutzerfreundlicher Name des Zugschemas
    schematitel: Dict[str, str] = {}

    def __init__(self):
        # Name des Zugschemas, wie er im Namen der Konfigurationsdatei vorkommt
        self.name: str = ""
        # Benutzerfreundlicher Name des Zugschemas.
        # Der Titel des Zugschemas wird in der Konfigurationsdatei deklariert.
        self.titel: str = ""
        # Pfad der Konfigurationsdatei
        self.pfad: Optional[Path] = None
        # Zuordnung von Gattungsnamen zu Zugkategorien
        self.gattungen: Dict[str, str] = {}
        # Zuordnung von Zugnummerbereichen zu Zugkategorien
        self.nummern: Dict[Tuple[int, int], str] = {}
        # Zugkategorien: Kategorienkürzel -> Beschreibung
        self.kategorien: Dict[str, str] = {}
        # Farbschema: Kategorienkürzel -> Matplotlib-Farben
        self.farben: Dict[str, str] = {}
        # Farbschema: Kategorienkürzel -> Index in Farbtabelle
        self.farbwert: Dict[str, float] = {}
        # Farbschema in Matplotlib-Colormap: kategorienindex -> Farbe
        self.farbtabelle: Optional[mpl.Colormap] = None

        d = {"kategorien": self.DEFAULT_KATEGORIEN}
        self.set_config(d)

    def reset(self):
        """
        Schemadaten löschen und auf Ausgangswerte zurücksetzen

        Die Kategorien werden auf DEFAULT_KATEGORIEN zurückgesetzt,
        alle anderen Attribute sind leer.

        :return: None
        """

        self.name = ""
        self.titel = ""
        self.pfad = None
        self.gattungen = {"Ersatzlok": "R", "Lok": "R"}
        self.nummern = {}

        d = {"kategorien": self.DEFAULT_KATEGORIEN}
        self.set_config(d)

    def _update_farbtabelle(self):
        n = len(self.farben) - 1
        self.farbwert = {kat: idx / n for idx, kat in enumerate(self.farben.keys())}
        farben = [farbe for farbe in self.farben.values()]
        self.farbtabelle = mpl.colors.ListedColormap(farben)

    def set_config(self, config: Dict):
        """
        Zugschema aus Konfiguration (Dictionary) übernehmen.

        Diese Methode setzt alle Objektattribute ausser self.name und self.pfad.
        Attribute, die im Dictionary fehlen, werden nicht verändert.

        :param config:
        :return:
        """

        try:
            self.titel = config['titel']
        except KeyError:
            try:
                # hatte früher einen anderen namen
                self.titel = config['name']
            except KeyError:
                pass

        try:
            for kat, schema in config['kategorien'].items():
                try:
                    self.kategorien[kat] = schema[0]
                    self.farben[kat] = schema[1]
                except IndexError:
                    pass
        except KeyError:
            pass

        try:
            for gattung in config['gattungen']:
                try:
                    if gattung[0]:
                        self.gattungen[gattung[0]] = gattung[3]
                    elif gattung[2] > gattung[1] > 0:
                        self.nummern[(gattung[1], gattung[2])] = gattung[3]
                except (IndexError, TypeError):
                    pass
        except KeyError:
            pass

        self._update_farbtabelle()

    def get_config(self) -> Dict:
        """
        Konfiguration als Dictionary auslesen.

        Der Dictinary kann direkt in eine JSON-Konfigurationsdatei geschrieben werden.

        :return:
        """

        kategorien = {kat: [self.kategorien[kat], self.farben[kat]] for kat in self.kategorien.keys()}
        gattungsnamen = [[name, 0, 0, kat] for name, kat in self.gattungen.items()]
        gattungsnummern = [["", nummern[0], nummern[1], kat] for nummern, kat in self.nummern.items()]
        config = {"_version": 1,
                  "titel": self.titel,
                  "kategorien": kategorien,
                  "gattungen": gattungsnamen + gattungsnummern}

        return config

    def load_config(self, name: str, region: str = ""):
        """
        Zugschema aus Konfigurationsdatei laden.

        Das Dictionary self.schemadateien muss vorher mittels find_schemas befüllt werden.
        Die Methode wählt das Schema in der folgenden Reihenfolge aus:

        - name (kommt i.d.R. aus der Stellwerkskonfiguration)
        - REGIONEN_SCHEMA der Region (nicht alle Regionen sind dort erfasst)
        - "deutschland" als default

        Wenn der Name nicht aufgelöst werden kann, wird das alphabetisch erste erfasste Schema geladen.
        Wenn kein Schema erfasst ist, bleibt das Schema leer
        und eine Fehlermeldung wird in die Log-Datei geschrieben.

        :param name: Name des Zugschemas.
            Der Name bestimmt die Konfigurationsdatei in self.schemadateien.
        :param region: Name der Stellwerksregion aus der Anlageninfo. Optional.
        :return: None
        """

        self.reset()

        if name:
            name = name.lower()
        else:
            try:
                name = REGIONEN_SCHEMA[region.split(maxsplit=1)[0]].lower()
            except (IndexError, KeyError):
                name = "deutschland"

        try:
            p = self.schemadateien[name]
        except KeyError:
            try:
                name = sorted(self.schemadateien.keys())[0]
                p = self.schemadateien[name]
            except IndexError:
                logger.error("Kein Zugschema definiert")
                return

        try:
            with open(p, encoding='utf-8') as fp:
                d = json.load(fp)
            self.set_config(d)
            self.name = name
            self.pfad = p
        except OSError:
            logger.error(f"Fehler beim Laden des Zugschemas {name} von {p}")

    @classmethod
    def find_schemas(cls, path: os.PathLike):
        """
        Zugschemadateien suchen und in Liste aufnehmen

        Sucht Zugschemadateien im angegebenen Verzeichnis und nimmt ihre Pfade in die klasseninterne Liste schemadateien auf.
        Die Methode kann mehrmals aufgerufen werden (z.B. für Vorgabe und Benutzerkonfiguration).
        Sie überschreibt dann vorbestehende Pfade gleichen Namens.

        :param path: Directorypfad
        :return:
        """

        p = Path(path)
        for fp in p.glob("zugschema.*.json"):
            try:
                name = fp.name.split('.')[1]
            except IndexError:
                continue

            try:
                with open(fp, encoding='utf-8') as f:
                    d = json.load(f)
                    try:
                        titel = d['titel']
                    except KeyError:
                        try:
                            titel = d['name']
                        except KeyError:
                            titel = name
            except OSError:
                continue

            cls.schemadateien[name] = fp
            cls.schematitel[name] = titel

    def kategorie(self, zug: Union[ZugDetails, ZugGraphNode]) -> str:
        """
        Ermittelt die Kategorie eines Zuges

        :param zug: ZugDetails oder davon abgeleitetes Objekt
        :return: Kategorienkürzel, z.B. "F"
        """

        try:
            return self.gattungen[zug.gattung]
        except KeyError:
            pass

        nummer = zug.nummer
        for t, f in self.nummern.items():
            if t[0] <= nummer < t[1]:
                return f
        else:
            return "R"

    def zugfarbe(self, zug: Union[ZugDetails, ZugGraphNode]) -> str:
        """
        Matplotlib-Farbcode eines Zuges

        :param zug: ZugDetails oder davon abgeleitetes Objekt
        :return: str
        """

        kat = self.kategorie(zug)
        return self.farben[kat]

    def zugfarbe_rgb(self, zug: Union[ZugDetails, ZugGraphNode]) -> Tuple[int]:
        """
        RGB-Farbcode eines Zuges

        :param zug: ZugDetails oder davon abgeleitetes Objekt
        :return: tupel (r,g,b). r,g,b sind Integer im Bereich 0-255.
        """

        farbe = self.zugfarbe(zug)
        frgb = mpl.colors.to_rgb(farbe)
        rgb = [round(255 * v) for v in frgb]
        return tuple(rgb)

    def zug_farbwert(self, zug: Union[ZugDetails, ZugGraphNode]) -> float:
        """
        Farbwert eines Zuges
        """
        kat = self.kategorie(zug)
        return self.farbwert[kat]

    def kategorie_farbwert(self, kat: str) -> float:
        """
        Farbwert einer Zugkategorie
        """
        return self.farbwert[kat]

    def kategorie_farbe(self, kat: str) -> str:
        """
        Matplotlib-Farbcode einer Zugkategorie.

        Aequivalent zu self.farben[kat].

        :param kat: Kategorienkürzel, z.B. "F"
        :return: str: Matplotlib-Farbe
        """

        return self.farben[kat]

    def kategorie_rgb(self, kat: str) -> Tuple[int]:
        """
        RGB-Farbcode einer Zugskategorie

        Kann mit QtGui.QColor(*rgb) in einen Qt-Farbcode umgewandelt werden.

        :param kat: Kategorienkürzel, z.B. "F"
        :return: tupel (r,g,b). r,g,b sind Integer im Bereich 0-255.
        """

        farbe = self.farben[kat]
        frgb = mpl.colors.to_rgb(farbe)
        rgb = [round(255 * v) for v in frgb]
        return tuple(rgb)


class ZugschemaAuswahlModell(QtCore.QAbstractTableModel):
    """
    Tabellenmodell zur Auswahl von Zugkategorien

    Diese Klasse enthält die ganze Logik, um dem User die Auswahl von Zugkategorien in einem QTableView zu ermöglichen.

    Dazu muss eine Instanz erzeugt werden und dem betreffenden QTableView zugewiesen werden.
    Die Auswahl wird dann über das Property auswahl ein- und ausgelesen.

    Wenn das Zugschema verändert wurde, muss danach die Update-Methode aufgerufen werden.

    Die privaten Attribute dürfen von aussen nicht verändert werden!
    """

    def __init__(self, *args, zugschema: Zugschema = ..., **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._zugschema = zugschema
        self.auswahl_erlauben = True
        self._kategorien: List[str] = []
        self._titel: Dict[str, str] = {}
        self._farben: Dict[str, QtGui.QColor] = {}
        self._spalten: List[str] = []
        try:
            self._auswahl = set(zugschema.kategorien.keys())
        except AttributeError:
            self._auswahl = set()
        self.update()

    def data(self, index: QModelIndex, role: int = ...) -> typing.Any:
        """
        Daten an das QListView übergeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - UserRole gibt die originaldaten aus (zum sortieren benötigt).
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - CheckStateRole gibt an, ob ein zug am gleis steht.
            - DecorationRole
            - ForegroundRole färbt die eingefahrenen, ausgefahrenen und noch unsichtbaren züge unterschiedlich ein.
            - TextAlignmentRole richtet den text aus.
            - ToolTipRole
        :return: verschiedene
        """

        if not index.isValid():
            return None

        try:
            col = index.column()
            if self.auswahl_erlauben:
                col -= 1
            row = index.row()
            kat = self._kategorien[row]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return kat
            elif col == 1:
                return self._titel[kat]

        elif role == QtCore.Qt.CheckStateRole:
            if self.auswahl_erlauben and col == -1:
                if kat in self._auswahl:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.ForegroundRole:
            return self._farben[kat]

        elif role == QtCore.Qt.TextAlignmentRole:
            if col < 1:
                return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter
            else:
                return QtCore.Qt.AlignVCenter

        return None

    def setData(self, index: QModelIndex, value: typing.Any, role: int = ...) -> bool:
        """
        Datenänderung vom QListView übernehmen.

        Wir reagieren nur auf geänderte Auswahl

        :param index: Zeilenindex
        :param role: Rolle
        :param value: neuer Wert
        :return: True, wenn sich das Model geändert hat.
        """

        if not index.isValid():
            return False

        try:
            col = index.column()
            if self.auswahl_erlauben:
                col -= 1
            row = index.row()
            kat = self._kategorien[row]
        except (IndexError, KeyError):
            return False

        if role == QtCore.Qt.CheckStateRole:
            value = QtCore.Qt.CheckState(value)
            if self.auswahl_erlauben and col == -1:
                if value == QtCore.Qt.Checked:
                    self._auswahl.add(kat)
                else:
                    self._auswahl.discard(kat)
                return True

        return False

    def flags(self, index: QModelIndex) -> Optional[QtCore.Qt.ItemFlags]:
        """
        Flags an QListView übergeben

        :param index: Zeilenindex
        :return: Alle Felder enabled und selectable. Erste Spalte checkable, wenn Auswahl erlaubt.
        """

        if not index.isValid():
            return None

        try:
            col = index.column()
            if self.auswahl_erlauben:
                col -= 1
            row = index.row()
            kat = self._kategorien[row]
        except (IndexError, KeyError):
            return None

        if col == -1:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable
        elif col == 0:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        elif col == 1:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile und -spalte aus.
        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den titel aus.
        :return:
        """

        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._spalten[section]
            elif orientation == QtCore.Qt.Vertical:
                return None

    def columnCount(self, parent: QModelIndex = ...) -> int:
        """
        Zeilenanzahl an QListView übergeben

        :param parent: nicht verwendet
        :return:
        """

        return len(self._spalten)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        """
        Zeilenanzahl an QListView übergeben

        :param parent: nicht verwendet
        :return: Anzahl wählbare Kategorien
        """

        return len(self._kategorien)

    def update(self):
        """
        Zugschema übernehmen

        Das Zugschema wird aus der Anlage ausgelesen und Modell und View neu aufgebaut.

        :return: None
        """

        self.beginResetModel()
        self._kategorien = list(self._zugschema.kategorien.keys())
        self._titel = self._zugschema.kategorien.copy()
        self._farben = {k: QtGui.QColor(*self._zugschema.kategorie_rgb(k)) for k in self._kategorien}
        self._auswahl.intersection_update(self._kategorien)
        self._spalten = ["Kürzel", "Titel"]
        if self.auswahl_erlauben:
            self._spalten.insert(0, "Auswahl")
        self.endResetModel()

    @property
    def auswahl(self) -> Set[str]:
        """
        Aktuelle Auswahl

        :return: Menge von Kategorieschlüsseln, z.B. {"X", "F", "N"}
        """

        return self._auswahl.copy()

    @auswahl.setter
    def auswahl(self, auswahl: Set[str]):
        """
        Auswahl ändern

        :param auswahl: Menge von Kategorieschlüsseln, z.B. {"X", "F", "N"}.
        :return:
        """

        self.beginResetModel()
        self._auswahl = auswahl
        self.endResetModel()


class ZugschemaBearbeitungModell(QtCore.QAbstractTableModel):
    """
    Tabellenmodell zur Bearbeitung von Zugkategorien

    Diese Klasse enthält die ganze Logik,
    um dem User die Bearbeitung von Zugkategorien in einem QTableView zu ermöglichen.

    Dazu muss eine Instanz erzeugt werden und dem betreffenden QTableView zugewiesen werden.
    Die Auswahl wird dann über das Property zugschema ein- und ausgelesen.

    Wenn das Zugschema verändert wurde, muss danach die Update-Methode aufgerufen werden.

    Die privaten Attribute dürfen von aussen nicht verändert werden!
    """

    def __init__(self, *args, zugschema: Zugschema = ..., **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._zugschema = zugschema
        self._tabelle: List[Dict[str, Union[int, str, QtGui.QColor]]] = []
        self._spalten: List[str] = ["Gattung", "Nummern", "Kürzel", "Kategorie"]
        self.update()

    def data(self, index: QModelIndex, role: int = ...) -> typing.Any:
        """
        Daten an das QListView übergeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
            - UserRole gibt die originaldaten aus (zum sortieren benötigt).
            - DisplayRole gibt die daten formatiert als str oder int aus.
            - CheckStateRole gibt an, ob ein zug am gleis steht.
            - DecorationRole
            - ForegroundRole färbt die eingefahrenen, ausgefahrenen und noch unsichtbaren züge unterschiedlich ein.
            - TextAlignmentRole richtet den text aus.
            - ToolTipRole
        :return: verschiedene
        """

        if not index.isValid():
            return None

        try:
            col = index.column()
            spalte = self._spalten[col]
            row = index.row()
            datum = self._tabelle[row]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.DisplayRole:
            try:
                return datum[spalte]
            except KeyError:
                return None

        elif role == QtCore.Qt.ForegroundRole:
            try:
                return datum["Farbe"]
            except KeyError:
                return None

        elif role == QtCore.Qt.TextAlignmentRole:
            if spalte == "Kategorie":
                return QtCore.Qt.AlignVCenter
            else:
                return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        """
        gibt den text der kopfzeile und -spalte aus.
        :param section: element-index
        :param orientation: wahl zeile oder spalte
        :param role: DisplayRole gibt den titel aus.
        :return:
        """

        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self._spalten[section]
            elif orientation == QtCore.Qt.Vertical:
                return None

    def columnCount(self, parent: QModelIndex = ...) -> int:
        """
        Zeilenanzahl an QListView übergeben

        :param parent: nicht verwendet
        :return:
        """

        return len(self._spalten)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        """
        Zeilenanzahl an QListView übergeben

        :param parent: nicht verwendet
        :return: Anzahl wählbare Kategorien
        """

        return len(self._tabelle)

    def update(self):
        """
        Zugschema übernehmen

        Das Zugschema wird aus der Anlage ausgelesen und Modell und View neu aufgebaut.

        :return: None
        """

        self.beginResetModel()
        liste_gattungen = [{"Kürzel": kat, "Kategorie": self._zugschema.kategorien[kat],
                            "Gattung": gatt, "Nummern": "",
                            "Farbe": QtGui.QColor(*self._zugschema.kategorie_rgb(kat))}
                           for gatt, kat in self._zugschema.gattungen.items()]
        liste_nummern = [{"Kürzel": kat, "Kategorie": self._zugschema.kategorien[kat],
                          "Gattung": "", "Nummern": f"{num[0]}-{num[1]}",
                          "Farbe": QtGui.QColor(*self._zugschema.kategorie_rgb(kat))}
                         for num, kat in self._zugschema.nummern.items()]
        self._tabelle = liste_gattungen + liste_nummern
        self.endResetModel()


class ZugFormatter:
    """
    Formatiert Elemente der Zugbeschriftung

    Die formatierten Elemente werden als Properties dargestellt,
    basierend auf den bei der Erstellung angegebenen Graphdaten.

    Die Angabe der Anlage und des Zuges sind immer zwingend.
    Für die Gleisbelegung kann entweder das Ziel oder die Ankunfts- und Abfahrtsereignisse angegeben werden.
    Für den Bildfahrplan und die Anschlussmatrix ist die Angabe der Ankunfts- und/oder Abfahrtsereignisse erforderlich,
    das Fahrplanziel ist nicht nötig.
    Die Ereignisangaben haben Priorität.
    """

    def __init__(self,
                 anlage: 'Anlage',
                 zug: ZugGraphNode,
                 ziel: Optional[ZielGraphNode] = None,
                 ankunft: Optional[EreignisGraphNode] = None,
                 abfahrt: Optional[EreignisGraphNode] = None,
                 null_zeigen: bool = False):

        super().__init__()
        self._anlage = anlage
        self._zug = zug
        self._ziel = ziel
        self._ankunft = ankunft
        self._abfahrt = abfahrt
        self._null_zeigen = null_zeigen

    @property
    def von(self) -> str:
        """
        Anfang des Zuges

        Dies ist der Name einer Anschlussstelle oder eines Bahnhofs.
        """

        try:
            zuganfang = self._anlage.original_zielgraph.zuganfaenge[self._zug.zid]
            anfangsziel = self._anlage.original_zielgraph.nodes[zuganfang]
            result = self._anlage.bahnhofgraph.find_superior(anfangsziel.gleis_bst, {"Anst", "Bf"}).name
        except (AttributeError, KeyError):
            result = ""

        return result

    @property
    def nach(self) -> str:
        """
        Ende des Zuges

        Dies ist der Name einer Anschlussstelle oder eines Bahnhofs.
        """

        try:
            zugende = self._anlage.original_zielgraph.zugenden[self._zug.zid]
            endziel = self._anlage.original_zielgraph.nodes[zugende]
            result = self._anlage.bahnhofgraph.find_superior(endziel.gleis_bst, {"Anst", "Bf"}).name
        except (AttributeError, KeyError):
            result = ""

        return result

    @property
    def zug(self) -> str:
        """
        Zugbeschreibung mit Name, Anfang und Ende

        Format: Name (von - nach)
        """

        von = self.von or '?'
        nach = self.nach or '?'
        return f"{self._zug.name} ({von} - {nach})"

    @property
    def name(self) -> str:
        """
        Zugname (Gattung und Nummer)
        """

        try:
            return self._zug.name
        except (AttributeError, KeyError):
            return ""

    @property
    def nummer(self) -> str:
        """
        Zugnummer
        """

        try:
            return str(self._zug.nummer)
        except (AttributeError, KeyError):
            return ""

    @property
    def gleis_an(self) -> str:
        """
        Name des disponierten Ankunftsgleises
        """

        try:
            if self._ankunft is not None:
                g = self._ankunft.gleis
            elif self._ziel is not None:
                g = self._ziel.gleis
            else:
                return ""
        except (AttributeError, KeyError):
            return ""

        return g

    @property
    def gleis_ab(self) -> str:
        """
        Name des disponierten Abfahrtsgleises
        """

        try:
            if self._abfahrt is not None:
                g = self._abfahrt.gleis
            elif self._ziel is not None:
                g = self._ziel.gleis
            else:
                return ""
        except (AttributeError, KeyError):
            return ""

        return g

    @property
    def gleis_plan_an(self) -> str:
        """
        Namen der geplanten und disponierten Ankunftsgleise

        Format: disponiert/geplant falls verschieden.
        Wenn das Gleis nicht geändert wurde, wird nur das Plangleis ausgegeben.
        """

        try:
            if self._ankunft is not None:
                g = self._ankunft.gleis
                p = self._ankunft.plan
            elif self._ziel is not None:
                g = self._ziel.gleis
                p = self._ziel.plan
            else:
                return ""
        except (AttributeError, KeyError):
            return ""

        if g == p:
            return g
        else:
            return f"{g}/{p}"

    @property
    def gleis_plan_ab(self) -> str:
        """
        Namen der geplanten und disponierten Abfahrtsgleise

        Format: disponiert/geplant falls verschieden.
        Wenn das Gleis nicht geändert wurde, wird nur das Plangleis ausgegeben.
        """

        try:
            if self._abfahrt is not None:
                g = self._abfahrt.gleis
                p = self._abfahrt.plan
            elif self._ziel is not None:
                g = self._ziel.gleis
                p = self._ziel.plan
            else:
                return ""
        except (AttributeError, KeyError):
            return ""

        if g == p:
            return g
        else:
            return f"{g}/{p}"

    @property
    def zeit_v_an(self):
        """
        Geplante Ankunftszeit und Verspätung

        Format: ← HH:MM+V ABH
        Die Verspätung erscheint nur, wenn sie ungleich 0 ist, oder das Attribut null_zeigen gesetzt ist.
        Wenn Abhängigkeiten (abh_an Property) bestehen, werden diese angefügt.
        """

        zv = f"← {self.zeit_an}{self.v_an}"
        l = [zv]
        abh = self.abh_an
        if abh:
            l.append(abh)
        return " ".join(l)

    @property
    def zeit_v_ab(self):
        """
        Geplante Abfahrtszeit und Verspätung

        Format: → HH:MM+V ABH
        Die Verspätung erscheint nur, wenn sie ungleich 0 ist, oder das Attribut null_zeigen gesetzt ist.
        Wenn Abhängigkeiten (abh_ab Property) bestehen, werden diese angefügt.
        """

        zv = f"→ {self.zeit_ab}{self.v_ab}"
        l = [zv]
        abh = self.abh_ab
        if abh:
            l.append(abh)
        return " ".join(l)

    @property
    def zeit_an(self) -> str:
        """
        Geplante Ankunftszeit

        Format: HH:MM
        """

        try:
            zeit = self._ankunft.t_plan
        except (AttributeError, KeyError):
            try:
                zeit = self._ziel.p_an
            except (AttributeError, KeyError):
                return ""

        result = f"{int(zeit) // 60:02}:{int(zeit) % 60:02}"
        return result

    @property
    def zeit_ab(self) -> str:
        """
        Geplante Abfahrtszeit

        Format: HH:MM
        """

        try:
            zeit = self._abfahrt.t_plan
        except (AttributeError, KeyError):
            try:
                zeit = self._ziel.p_ab  # todo
            except (AttributeError, KeyError):
                return ""

        result = f"{int(zeit) // 60:02}:{int(zeit) % 60:02}"
        return result

    @property
    def v_an(self) -> str:
        """
        Ankunftsverspätung inkl. Vorzeichen

        Format: +V
        Die Verspätung erscheint nur, wenn sie ungleich 0 ist, oder das Attribut null_zeigen gesetzt ist.
        """

        try:
            if self._ankunft is not None:
                v = self._ankunft.t_eff - self._ankunft.t_plan
            elif self._ziel is not None:
                v = self._ziel.v_an
            else:
                v = 0
        except (AttributeError, KeyError, TypeError):
            return ""

        v += 0.5
        if self._null_zeigen or abs(v) > 0.5:
            result = f"{int(v):+}"
        else:
            result = ""
        return result

    @property
    def v_ab(self) -> str:
        """
        Abfahrtsverspätung inkl. Vorzeichen

        Format: +V
        Die Verspätung erscheint nur, wenn sie ungleich 0 ist, oder das Attribut null_zeigen gesetzt ist.
        """

        try:
            if self._abfahrt is not None:
                v = self._abfahrt.t_eff - self._abfahrt.t_plan
            elif self._ziel is not None:
                v = self._ziel.v_ab
            else:
                v = 0
        except (AttributeError, KeyError, TypeError):
            return ""

        v += 0.5
        if self._null_zeigen or abs(v) > 0.5:
            result = f"{int(v):+}"
        else:
            result = ""
        return result

    @property
    def abh_an(self) -> str:
        """
        Ankunftsabhängigkeiten (nicht implementiert)
        """

        return ""

    @property
    def abh_ab(self) -> str:
        """
        Abfahrtsabhängigkeiten (nicht implementiert)
        """

        return ""


class Zugbeschriftung:
    """
    Formatieren von Zugbeschriftungen

    Diese Klasse formatiert die Zugbeschriftungen (Labels und Infos) für die wichtigen Anzeigemodule.
    Sie stellt Formatierungsmethoden für deren Zwecke bereit.
    Die Methoden in dieser Klasse definieren das Muster der jeweiligen Beschriftungen.
    Die Muster bestehen aus Elementen, die jeweils von einem ZugFormatter-Objekt gestellt werden.

    Die folgenden Formate werden produziert:

    Slot-Info
        IC 2662 (WI - TG), BG5/BG4, ← 15:03+6, → 15:04+5

    Slot-Label
        2662 +6

    Trasse-Info
        IC 2662 (WI - TG), B 2/B 1 → 15:30+3, C 3 ← 15:40+3

    Trasse kurz
        2662 +6|+5

    Anschluss-Info
        IC 2662 (WI - TG), C 3 ← 15:20+3, C 3 → 15:30+3

    Anschluss-Label
        IC 2662 / WI

    Anschluss-Inset
        C 3, 15:20, +3

    """

    def __init__(self, anlage: 'Anlage'):
        self._anlage = anlage

    def format_slot_label(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert ein Slot-Label für die Gleisbelegungsgrafik

        Format: Zugnummer
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)

        t = ""
        if ziel is not None:
            typ = ziel.get("typ", "?")
            if typ == 'E':
                t = "← "
            elif typ == 'A':
                t = "→ "

        result = t + fmt.nummer

        return result

    def format_slot_info(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert die Zuginfo für die Gleisbelegungsgrafik

        Format: Zug, Ankunft, Abfahrt
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)
        zug = fmt.zug
        ankunft = " ".join([fmt.gleis_plan_an, fmt.zeit_v_an])
        abfahrt = fmt.zeit_v_ab

        l = [zug]
        if ankunft:
            l.append(ankunft)
        if abfahrt:
            l.append(abfahrt)

        result = ", ".join(l)
        return result

    def format_trasse_label(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert das Trassenlabel für den Bildfahrplan

        Format: Zugnummer, Verspätung
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)
        l = []
        v_ab = fmt.v_ab
        if v_ab:
            l.append(v_ab)
        v_an = fmt.v_an
        if v_an:
            l.append(v_an)
        if v_ab == v_an:
            v = v_an
        else:
            v = "|".join(l)

        l = [fmt.nummer]
        if v:
            l.append(v)
        result = " ".join(l)

        return result

    def format_trasse_info(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert die Zuginfo für den Bildfahrplan

        Format: Zug, Abfahrt, Ankunft
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)
        zug = fmt.zug
        ankunft = " ".join([fmt.gleis_plan_an, fmt.zeit_v_an])
        abfahrt = " ".join([fmt.gleis_plan_ab, fmt.zeit_v_ab])

        l = [zug]
        if abfahrt:
            l.append(abfahrt)
        if ankunft:
            l.append(ankunft)

        result = ", ".join(l)
        return result

    def format_anschluss_label(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert ein Achsenlabel der Anschlussmatrix

        Format: Zug, von/nach
        von/nach je nachdem, ob das Ankunfts- oder Abfahrtsereignis angegeben wird.
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt)
        zeilen = [fmt.name]
        if ankunft:
            anst = fmt.von
        elif abfahrt:
            anst = fmt.nach
        else:
            anst = ""
        if anst:
            zeilen.append(anst)

        return "\n".join(zeilen)

    def format_anschluss_inset(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert ein Inset der Anschlussmatrix

        Format: Gleis (abgekürzt), Zeit, Verspätung

        Zeit und Verspätung werden ausgeblendet, nachdem das Ereignis eingetreten ist.
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)
        l = []
        g = z = v = ""
        if ankunft:
            g = fmt.gleis_an
            if not ankunft.get("t_mess"):
                z = fmt.zeit_an
                v = fmt.v_an
        elif abfahrt:
            g = fmt.gleis_ab
            if not abfahrt.get("t_mess"):
                z = fmt.zeit_ab
                v = fmt.v_ab

        g = self._anlage.gleisschema.gleisname_kurz(g)[:6]
        l.append(g)
        l.append(z)
        if int(v or "0") > 0:
            l.append(v)
        result = "\n".join(l)

        return result

    def format_anschluss_info(self,
               zug: ZugGraphNode,
               ziel: Optional[ZielGraphNode] = None,
               ankunft: Optional[EreignisGraphNode] = None,
               abfahrt: Optional[EreignisGraphNode] = None) -> str:

        """
        Formatiert die Zuginfo für die Anschlussmatrix

        Format: Zug, Ankunft, Abfahrt
        """

        fmt = ZugFormatter(self._anlage, zug, ziel, ankunft, abfahrt, null_zeigen=False)
        zug = fmt.zug
        ankunft = " ".join([fmt.gleis_plan_an, fmt.zeit_v_an])
        abfahrt = fmt.zeit_v_ab

        l = [zug]
        if ankunft:
            l.append(ankunft)
        if abfahrt:
            l.append(abfahrt)

        result = ", ".join(l)
        return result
