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
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import matplotlib as mpl
from PyQt5 import Qt, QtCore, QtGui
from PyQt5.QtCore import QModelIndex, QSortFilterProxyModel, QItemSelectionModel, QObject

from stskit.stsobj import time_to_minutes, ZugDetails

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

REGIONEN_SCHEMA = {
    "Bern - Lötschberg": "Schweiz",
    "Ostschweiz": "Schweiz",
    "Tessin": "Schweiz",
    "Westschweiz": "Schweiz",
    "Zentralschweiz": "Schweiz",
    "Zürich und Umgebung": "Schweiz"}


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

    # verfuegbare zugschema-dateien. key = schema-name, value = dateipfad
    schemas: Dict[str, os.PathLike] = {}

    def __init__(self):
        self.name: str = ""
        self.pfad: Optional[Path] = None
        self.gattungen: Dict[str, str] = {}
        self.nummern: Dict[Tuple[int, int], str] = {}
        self.kategorien: Dict[str, Dict[str, str]] = {}

        d = {"kategorien": self.DEFAULT_KATEGORIEN}
        self.set_config(d)

    def set_config(self, config: Dict):
        try:
            for kat, schema in config['kategorien'].items():
                try:
                    self.kategorien[kat] = {"beschreibung": schema[0], "farbe": schema[1]}
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

    def get_config(self) -> Dict:
        kategorien = {kat: [schema["beschreibung"], schema["farbe"]] for kat, schema in self.kategorien.items()}
        gattungsnamen = [[name, 0, 0, kat] for name, kat in self.gattungen.items()]
        gattungsnummern = [["", nummern[0], nummern[1], kat] for nummern, kat in self.nummern.items()]
        config = {"kategorien": kategorien,
                  "gattungen": gattungsnamen + gattungsnummern}
        return config

    def load_config(self, name: str, region: str = ""):
        """
        Lädt das Zugschema.

        Das Dictionary self.schemas muss vorher mittels find_schemas befüllt werden.
        Die Methode wählt das Schema in der folgenden Reihenfolge aus:

        - name (kommt i.d.R. aus der Stellwerkskonfiguration)
        - REGIONEN_SCHEMA der Region (nicht alle Regionen sind dort erfasst)
        - "deutschland" als default

        :param name: Name des Zugschemas. Der Name ist ein Schlüssel in self.schemas.
        :param region: Name der Stellwerksregion aus der Anlageninfo. Optional.
        :return: None
        """

        if name:
            name = name.lower()
        else:
            try:
                name = REGIONEN_SCHEMA[region].lower()
            except KeyError:
                name = "deutschland"

        try:
            p = self.schemas[name]
        except KeyError:
            self.name = ""
            self.pfad = None
        else:
            try:
                with open(p) as fp:
                    d = json.load(fp)
                self.set_config(d)
                self.pfad = p
            except OSError:
                self.name = ""
                self.pfad = None

    @classmethod
    def find_schemas(cls, path: os.PathLike):
        """
        Zugschemadateien suchen und in Liste aufnehmen

        Sucht Zugschemadateien im angegebenen Verzeichnis und nimmt ihre Pfade in die klasseninterne Liste schemas auf.
        Die Methode kann mehrmals aufgerufen werden und überschreibt dann vorbestehende Pfade gleichen Dateinamens.

        :param path: Directorypfad
        :return:
        """

        p = Path(path)
        for fp in p.glob("zugschema.*.json"):
            try:
                name = fp.name.split('.')[1]
            except IndexError:
                pass
            else:
                cls.schemas[name] = fp

    def kategorie(self, zug: ZugDetails) -> str:
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

    def zugfarbe(self, zug: ZugDetails) -> str:
        """
        Matplotlib-Farbcode eines Zuges

        :param zug:
        :return: str
        """

        kat = self.kategorie(zug)
        return self.kategorien[kat]["farbe"]

    def zugfarbe_rgb(self, zug: ZugDetails) -> Tuple[int]:
        """
        RGB-Farbcode eines Zuges

        :param zug:
        :return: tupel (r,g,b). r,g,b sind Integer im Bereich 0-255.
        """

        farbe = self.zugfarbe(zug)
        frgb = mpl.colors.to_rgb(farbe)
        rgb = [round(255 * v) for v in frgb]
        return tuple(rgb)

    def kategorie_farbe(self, kat: str) -> str:
        """
        Matplotlib-Farbcode einer Zugkategorie.

        :param kat: Kategoriekürzel, z.B. "F"
        :return: str
        """

        return self.kategorien[kat]["farbe"]

    def kategorie_rgb(self, kat: str) -> Tuple[int]:
        """
        RGB-Farbcode einer Zugskategorie

        Kann mit QtGui.QColor(*rgb) in einen Qt-Farbcode umgewandelt werden.

        :param kat: Kategoriekürzel, z.B. "F"
        :return: tupel (r,g,b). r,g,b sind Integer im Bereich 0-255.
        """

        farbe = self.kategorien[kat]["farbe"]
        frgb = mpl.colors.to_rgb(farbe)
        rgb = [round(255 * v) for v in frgb]
        return tuple(rgb)


class ZugkategorienAuswahlModell(QtCore.QAbstractTableModel):
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
        self._auswahl_erlauben = True
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
            if self._auswahl_erlauben:
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
            if self._auswahl_erlauben and col == -1:
                if kat in self._auswahl:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.ForegroundRole:
            return self._farben[kat]

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
            if self._auswahl_erlauben:
                col -= 1
            row = index.row()
            kat = self._kategorien[row]
        except (IndexError, KeyError):
            return False

        if role == QtCore.Qt.CheckStateRole:
            if self._auswahl_erlauben and col == -1:
                if value == QtCore.Qt.Checked:
                    self._auswahl.add(kat)
                else:
                    self._auswahl.remove(kat)
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
            if self._auswahl_erlauben:
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
        self._titel = {k: v["beschreibung"] for k, v in self._zugschema.kategorien.items()}
        self._farben = {k: QtGui.QColor(*self._zugschema.kategorie_rgb(k)) for k in self._kategorien}
        self._auswahl.intersection_update(self._kategorien)
        self._spalten = ["Kürzel", "Titel"]
        if self._auswahl_erlauben:
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


class Zugbeschriftung:
    """
    Konfigurieren und Formatieren von Zugbeschriftungen

    Idee: Jede Darstellung unterhält ein zugeordnetes Zugbeschriftungsobjekt.
    In diesem wird das Format der Zugbeschriftung sowie die enthaltenen Elemente konfiguriert.

    Meist bleibt das Format für eine bestimmte Darstellung unverändert und wird programmatisch gesetzt.
    Die in der Beschriftung verwendeten Elemente werden vom Benutzer konfiguriert,
    z.B. mittels ZugBeschriftungAuswahlModell.
    """

    ELEMENTE = ['Gleis', 'Name', 'Nummer', 'Richtung', 'Zeit', 'Verspätung']
    SITUATIONEN = ['Ankunft', 'Abfahrt']
    DEFAULT_MUSTER = {
        'Anschlussmatrix': ['Gleis', 'Name', 'Nummer', 'Richtung', 'Zeit', 'Verspätung'],
        'Bildfahrplan': ['Name', 'Nummer', 'Verspätung'],
        'Gleisbelegung': ['Name', 'Nummer', 'Zeit', 'Verspätung'],
        'default': ['Name', 'Verspätung']
    }
    DEFAULT_ELEMENTE = {
        'Anschlussmatrix': ['Nummer', 'Richtung', 'Verspätung'],
        'Bildfahrplan': ['Nummer', 'Verspätung'],
        'Gleisbelegung': ['Nummer', 'Verspätung'],
        'default': ['Name', 'Verspätung']
    }

    def __init__(self, einstellung: str = 'default'):
        self._muster: List[str] = self.DEFAULT_MUSTER[einstellung]
        self._elemente: Set[str] = self.DEFAULT_ELEMENTE[einstellung]

    @property
    def muster(self) -> List[str]:
        return self._muster

    @muster.setter
    def muster(self, muster: Iterable[str]):
        self._muster = list(muster)

    @property
    def elemente(self) -> Set[str]:
        return self._elemente

    @elemente.setter
    def elemente(self, elemente: Iterable[str]):
        self._elemente = set(elemente)

    def format(self,
               ziel: 'ZugZielPlanung',
               situation: Optional[Union[str, Set[str]]] = None) -> str:

        """
        zugbeschriftung nach ankunfts- oder abfahrtsmuster formatieren

        Gleis Name Nummer Richtung Zeit (Verspätung)

        :param ziel: zugziel
        :param situation: 'Abfahrt' (default) und/oder 'Ankunft'
        :return: str
        """

        if situation is None:
            situation = {'Abfahrt'}
        elif isinstance(situation, str):
            situation = {situation}

        args = {'Name': ziel.zug.name,
                'Nummer': str(ziel.zug.nummer),
                'Gleis': ziel.gleis + ':',
                'Richtung': '',
                'Zeit': None,
                'Verspätung': None
                }

        if 'Ankunft' in situation:
            args['Richtung'] = ziel.zug.von.replace("Gleis ", "").split(" ")[0]
            args['Zeit'] = ziel.an
            args['Verspätung'] = ziel.verspaetung_an

        if 'Abfahrt' in situation:
            args['Richtung'] = ziel.zug.nach.replace("Gleis ", "").split(" ")[0]
            args['Zeit'] = ziel.ab
            args['Verspätung'] = ziel.verspaetung_ab

        try:
            args['Zeit'] = time_to_minutes(args['Zeit'])
        except AttributeError:
            try:
                del args["Zeit"]
            except ValueError:
                pass
        else:
            args['Zeit'] = f"{int(args['Zeit']) // 60:02}:{int(args['Zeit']) % 60:02}"

        if args['Verspätung']:
            args['Verspätung'] = f"({int(args['Verspätung']):+})"
        else:
            try:
                del args["Verspätung"]
            except ValueError:
                pass

        beschriftung = " ".join((args[element] for element in self._muster if element in self._elemente and element in args))
        return beschriftung


class ZugbeschriftungAuswahlModell(QtCore.QAbstractTableModel):
    """
    Tabellenmodell zum Einstellen Zugbeschriftung

    Die Tabelle enthält die Spalten 'Auswahl', 'Beschreibung'.
    Die Zeilen enthalten die wählbaren Elemente 'Gleis', 'Zug', 'Nummer', 'Richtung', 'Zeit', 'Verspätung'.

    Implementiert die Methoden von QAbstractTableModel.
    """

    def __init__(self, *args, beschriftung: Zugbeschriftung = ..., **kwargs) -> None:
        """

        :param args: Für Superklasse
        :param elemente: Wählbare Elemente
        :param kwargs: Für Superklasse
        """

        super().__init__(*args, **kwargs)

        self._beschriftung = beschriftung
        self._spalten: List[str] = ['Auswahl', 'Beschreibung']
        self._elemente: List[str] = list(beschriftung.muster)
        self._auswahl: Set[str] = set(beschriftung.elemente)

    @property
    def elemente(self) -> Iterable[str]:
        return self._elemente

    @elemente.setter
    def elemente(self, elemente: Iterable[str]):
        self.beginResetModel()
        self._elemente = list(elemente)
        self.endResetModel()

    @property
    def auswahl(self) -> Set[str]:
        """
        Aktuelle Auswahl

        :return: Menge von Beschriftungselementen
        """

        return self._auswahl.copy()

    @auswahl.setter
    def auswahl(self, auswahl: Iterable[str]):
        """
        Auswahl ändern

        :param auswahl: Menge von Beschriftungselementen
        :return:
        """

        self.beginResetModel()
        self._auswahl = set(auswahl)
        self.endResetModel()

    def columnCount(self, parent: QModelIndex = ...) -> int:
        """
        anzahl spalten in der tabelle

        :param parent: nicht verwendet
        :return: die spaltenzahl ist fix.
        """
        return len(self._spalten)

    def rowCount(self, parent: QModelIndex = ...) -> int:
        """
        anzahl zeilen (züge)

        :param parent: nicht verwendet
        :return: anzahl dargestellte zeilen.
        """
        return len(self._elemente)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        """
        Daten pro Zelle an den Viewer ausgeben.

        :param index: enthält spalte und zeile der gewünschten zelle
        :param role: gewünschtes datenfeld:
        :return: verschiedene
        """

        if not index.isValid():
            return None

        try:
            col = index.column()
            row = index.row()
            element = self._elemente[row]
        except (IndexError, KeyError):
            return None

        if role == QtCore.Qt.DisplayRole:
            if col == 1:
                return element

        elif role == QtCore.Qt.CheckStateRole:
            if col == 0:
                if element in self._auswahl:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        elif role == QtCore.Qt.TextAlignmentRole:
            if col == 0:
                return QtCore.Qt.AlignHCenter + QtCore.Qt.AlignVCenter
            else:
                return QtCore.Qt.AlignLeft + QtCore.Qt.AlignVCenter

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
            row = index.row()
            element = self._elemente[row]
        except (IndexError, KeyError):
            return False

        if role == QtCore.Qt.CheckStateRole:
            if col == 0:
                if value == QtCore.Qt.Checked:
                    self._auswahl.add(element)
                else:
                    self._auswahl.remove(element)
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
            row = index.row()
            element = self._elemente[row]
        except (IndexError, KeyError):
            return None

        if col == 0:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable
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
