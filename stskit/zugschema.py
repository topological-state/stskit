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
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QModelIndex

from stskit.graphs.ereignisgraph import EreignisGraphNode
from stskit.graphs.zielgraph import ZielGraphNode
from stskit.interface.stsobj import time_to_minutes, ZugDetails
from stskit.graphs.zuggraph import ZugGraphNode

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

REGIONEN_SCHEMA = {
    "Bern - Lötschberg": "Schweiz",
    "Italien Nord": "Italien",
    "Merxferri": "Deutschland",
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
                name = REGIONEN_SCHEMA[region].lower()
            except KeyError:
                name = "deutschland"

        try:
            p = self.schemadateien[name]
        except KeyError:
            try:
                name = sorted(self.schemadateien.keys())[0]
                p = self.schemadateien[name]
            except IndexError:
                logger.error(f"Kein Zugschema definiert")
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
            if self.auswahl_erlauben and col == -1:
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


class Zugbeschriftung:
    """
    Konfigurieren und Formatieren von Zugbeschriftungen

    Idee: Jede Darstellung unterhält ein zugeordnetes Zugbeschriftungsobjekt.
    In diesem wird das Format der Zugbeschriftung sowie die enthaltenen Elemente konfiguriert.

    Meist bleibt das Format für eine bestimmte Darstellung unverändert und wird programmatisch gesetzt.
    Die in der Beschriftung verwendeten Elemente werden vom Benutzer konfiguriert,
    z.B. mittels ZugBeschriftungAuswahlModell.

    Attribute:
        stil: Name des Stils entspricht dem Ziel der Anzeige: z.B. Anschlussmatrix, Bildfahrplan, Gleisbelegung.
            Jeder Stil hat ein vorgegebenes Muster und Elemente.
        muster: Reihenfolge, in der die Elemente dargestellt werden.
        elemente: Elemente, die in der Beschriftung enthalten sein sollen.
            Dieses Attribut kann vom Benutzer eingestellt werden.
    """

    ELEMENTE = ['Gleis', 'Name', 'Nummer', 'Richtung', 'Zeit', 'Verspätung']
    SITUATIONEN = ['Ankunft', 'Abfahrt']
    DEFAULT_MUSTER = {
        'Anschlussmatrix': ['Gleis', 'Name', 'Nummer', 'Richtung', 'Zeit', 'Verspätung'],
        'Bildfahrplan': ['Name', 'Nummer', 'Verspätung'],
        'Gleisbelegung': ['Name', 'Nummer', 'Verspätung'],
        'default': ['Name', 'Verspätung']
    }
    DEFAULT_ELEMENTE = {
        'Anschlussmatrix': ['Nummer', 'Richtung', 'Verspätung'],
        'Bildfahrplan': ['Nummer', 'Verspätung'],
        'Gleisbelegung': ['Nummer', 'Verspätung'],
        'default': ['Name', 'Verspätung']
    }

    def __init__(self, stil: str = 'default'):
        self._stil: str = stil
        self._muster: List[str] = self.DEFAULT_MUSTER[stil]
        self._elemente: Set[str] = self.DEFAULT_ELEMENTE[stil]

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
               zug_data: ZugGraphNode,
               ziel_data: Union[ZielGraphNode, EreignisGraphNode],
               situation: Optional[Union[str, Set[str]]] = None) -> str:

        """
        Zugbeschriftung nach Ankunfts- oder Abfahrtsmuster formatieren

        Gleis Name Nummer Richtung Zeit (Verspätung)

        :param zug_data: Zugdaten
        :param ziel_data: Zieldaten
        :param situation: 'Abfahrt' (default) und/oder 'Ankunft'
        :return: str
        """

        if situation is None:
            situation = {'Abfahrt'}
        elif isinstance(situation, str):
            situation = {situation}

        args = {'Name': zug_data.name,
                'Nummer': str(zug_data.nummer),
                'Gleis': ziel_data.gleis + ':',
                'Richtung': '',
                'Zeit': None,
                'Verspätung': None
                }

        if 'Ankunft' in situation:
            try:
                args['Richtung'] = zug_data.von.replace("Gleis ", "").split(" ")[0]
            except AttributeError:
                pass
            try:
                if ziel_data.typ == 'An':
                    args['Zeit'] = ziel_data.t_plan
                else:
                    args['Zeit'] = ziel_data.p_an
            except AttributeError:
                pass
            try:
                if ziel_data.typ == 'An':
                    args['Verspätung'] = ziel_data.t_eff - ziel_data.t_plan
                else:
                    args['Verspätung'] = ziel_data.v_an
            except AttributeError:
                pass

        if 'Abfahrt' in situation:
            try:
                args['Richtung'] = zug_data.nach.replace("Gleis ", "").split(" ")[0]
            except AttributeError:
                pass
            try:
                if ziel_data.typ == 'Ab':
                    args['Zeit'] = ziel_data.t_plan
                else:
                    args['Zeit'] = ziel_data.p_ab
            except AttributeError:
                pass
            try:
                if ziel_data.typ == 'Ab':
                    args['Verspätung'] = ziel_data.t_eff - ziel_data.t_plan
                else:
                    args['Verspätung'] = ziel_data.v_ab
            except AttributeError:
                pass

        if args['Zeit']:
            args['Zeit'] = f"{int(args['Zeit']) // 60:02}:{int(args['Zeit']) % 60:02}"
        else:
            del args['Zeit']

        if args['Verspätung']:
            args['Verspätung'] = f"({int(args['Verspätung']):+})"
        else:
            del args["Verspätung"]

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
