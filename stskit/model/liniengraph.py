import itertools
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.model.bahnhofgraph import BahnhofElement, BahnhofGraph, BahnsteigGraphNode, BahnhofLabelType
from stskit.model.zielgraph import ZielGraphNode

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class LinienGraphNode(dict):
    typ = dict_property("typ", str,
                        docstring="Typ entsprechend BahnsteigGraphNode.typ, i.d.R. Bf oder Anst.")
    name = dict_property("name", str,
                         docstring="Benutzerfreundlicher Name des Knotens")
    fahrten = dict_property("fahrten", int,
                            docstring="Anzahl der ausgewerteten Fahrten über diesen Knoten")


class LinienGraphEdge(dict):
    fahrzeit_min = dict_property("fahrzeit_min", Union[int, float],
                                 docstring="Minimale Fahrzeit in Minuten")
    fahrzeit_max = dict_property("fahrzeit_max", Union[int, float],
                                 docstring="Maximale Fahrzeit in Minuten")
    fahrten = dict_property("fahrten", int,
                            docstring="Anzahl der ausgewerteten Fahrten")
    fahrzeit_summe = dict_property("fahrzeit_summe", Union[int, float],
                                   docstring="Summe aller ausgewerteten Fahrzeiten in Minuten")
    fahrzeit_schnitt = dict_property("fahrzeit_schnitt", float,
                                     docstring="Mittelwert aller ausgewerteten Fahrzeiten in Minuten")
    fahrzeit_manuell = dict_property("fahrzeit_manuell", Union[int, float],
                                  docstring="Vom Benutzer eingestellte Fahrzeit. Ersetzt die berechnete Fahrzeit, sofern gesetzt und grösser Null.")
    markierung = dict_property("markierung", str,
                               docstring="Markierungsflags: E = Eingleisig")


LinienLabelType = BahnhofLabelType


class LinienGraph(nx.Graph):
    """
    Zugverbindungen zwischen Bahnhöfen.

    Dieser Graph zeigt bediente Verbindungen zwischen Bahnhöfen.
    Der Graph wird anhand der Zugfahrpläne erstellt.


    """
    node_attr_dict_factory = LinienGraphNode
    edge_attr_dict_factory = LinienGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)

        self._strecken_cache: Dict[Tuple[LinienLabelType, LinienLabelType], List[LinienLabelType]] = {}

    def to_undirected_class(self):
        return self.__class__

    @staticmethod
    def label(typ: str, name: str) -> LinienLabelType:
        """
        Das Label vom Liniengraph entspricht dem des BahnsteigGraph, i.d.R. auf Stufe Bf und Anst.
        """
        return LinienLabelType(typ, name)

    def linie_eintragen(self,
                        ziel1: ZielGraphNode, bahnhof1: BahnsteigGraphNode,
                        ziel2: ZielGraphNode, bahnhof2: BahnsteigGraphNode):
        """
        Liniengraph erstellen

        Sollte nicht mehr als einmal pro Zug aufgerufen werden, da sonst die Statistik verfälscht werden kann.
        """

        MAX_FAHRZEIT = 24 * 60

        try:
            fahrzeit = ziel2.p_an - ziel1.p_ab
            # beschleunigungszeit von haltenden zuegen
            if ziel1.typ == 'D':
                fahrzeit += 1
        except AttributeError:
            fahrzeit = 2

        bft1 = self.label(bahnhof1.typ, bahnhof1.name)
        bft2 = self.label(bahnhof2.typ, bahnhof2.name)

        try:
            knoten1_daten = self.nodes[bft1]
        except KeyError:
            knoten1_daten = LinienGraphNode(typ=bahnhof1.typ, name=bahnhof1.name, fahrten=0)
        try:
            knoten2_daten = self.nodes[bft2]
        except KeyError:
            knoten2_daten = LinienGraphNode(typ=bahnhof2.typ, name=bahnhof2.name, fahrten=0)

        knoten1_daten.fahrten += 1
        knoten2_daten.fahrten += 1

        try:
            liniendaten = self[bft1][bft2]
        except KeyError:
            liniendaten = LinienGraphEdge(fahrzeit_min=MAX_FAHRZEIT, fahrzeit_max=0,
                                          fahrten=0, fahrzeit_summe=0., fahrzeit_schnitt=0.)

        liniendaten.fahrzeit_min = min(liniendaten.fahrzeit_min, fahrzeit)
        liniendaten.fahrzeit_max = max(liniendaten.fahrzeit_max, fahrzeit)
        liniendaten.fahrten += 1
        liniendaten.fahrzeit_summe += fahrzeit
        liniendaten.fahrzeit_schnitt = liniendaten.fahrzeit_summe / liniendaten.fahrten

        self.add_edge(bft1, bft2, **liniendaten)
        self.add_node(bft1, **knoten1_daten)
        self.add_node(bft2, **knoten2_daten)

    def schleifen_aufloesen(self):
        """
        Schleifen auflösen

        Weil Züge nicht alle Haltestellen bedienen,
        kann es im Liniengraph mehrere Verbindungen zwischen zwei Knoten geben,
        die im Graphen eine Schleife (cycle) bilden.
        Damit eine Strecke möglichst dem tatsächlichen Gleisverlauf folgt,
        löst diese Funktion solche Schleifen auf, indem sie die längste Kante jeder Schleife entfernt.
        Die Länge der Kante ist die minimale Fahrzeit zwischen den Knoten.

        Wenn die längste Kante nicht eindeutig bestimmt werden kann, wird die Schleife nicht aufgelöst.
        Dies kann z.B. der Fall sein, wenn die Fahrzeit zwischen allen Knoten gleich lang ist,
        weil der durchfahrende Zug die Zeit zum Anhalten und Beschleunigen einspart.
        Die Funktion versucht, solche Fälle aufzulösen,
        indem sie Verbindungen zwischen Knoten mit Grad > 2 künstlich verlängert.
        """

        entfernen = set()

        for schleife in nx.simple_cycles(self):
            kanten = zip(schleife, schleife[1:] + schleife[:1])
            laengste_fahrzeit = 0
            summe_fahrzeit = 0
            laengste_kante = None

            for kante in kanten:
                fahrzeit = max(1, self.edges[kante].get("fahrzeit_min", 0))
                fahrzeit += max(0, self.degree[kante[0]] - 2)
                fahrzeit += max(0, self.degree[kante[1]] - 2)
                if self.degree[kante[0]] > 2 and self.degree[kante[1]] > 2:
                    summe_fahrzeit += fahrzeit
                    if fahrzeit > laengste_fahrzeit:
                        laengste_fahrzeit = fahrzeit
                        laengste_kante = kante

            if laengste_kante is not None:
                if laengste_fahrzeit > summe_fahrzeit - laengste_fahrzeit - len(schleife):
                    entfernen.add(laengste_kante)
                else:
                    schleifen_text = ", ".join((str(bst) for bst in schleife))
                    logger.debug(f"symmetrische schleife {schleifen_text}")

        for u, v in entfernen:
            try:
                self.remove_edge(u, v)
            except nx.NetworkXError:
                pass

    def strecke(self, start: LinienLabelType, ziel: LinienLabelType) -> List[LinienLabelType]:
        """
        Kürzeste Verbindung zwischen zwei Punkten bestimmen

        Start und Ziel sind die Labels zweier beliebiger Knoten im Liniengraph.
        Die berechnete Strecke ist eine geordnete Liste von Labels.

        Da die Streckenberechnung aufwändig sein kann, werden die Resultate im self._strecken_cache gespeichert.
        Der Cache muss gelöscht werden, wenn der Graph verändert wird.

        :param start: bahnhof- oder anschlussname
        :param ziel: bahnhof- oder anschlussname
        :return: liste von befahrenen gleisgruppen vom start zum ziel.
            die liste kann leer sein, wenn kein pfad gefunden wurde!
        """

        try:
            return self._strecken_cache[(start, ziel)]
        except KeyError:
            pass

        try:
            strecke = nx.shortest_path(self, start, ziel)
        except nx.NetworkXException:
            strecke = []

        self._strecken_cache[(start, ziel)] = strecke
        return strecke

    def strecken_vorschlagen(self, min_fahrten: int = 0, min_laenge: int = 2) -> List[List[LinienLabelType]]:
        """
        Strecken aus Liniengraph vorschlagen

        Diese Funktion bestimmt die kürzesten Strecken zwischen allen Kombinationen von Anschlüssen.
        Wenig frequentierte Anschlüsse können ausgeschlossen werden.

        Eine Strecke besteht aus einer Liste von Bahnhöfen inklusive Einfahrt am Anfang und Ausfahrt am Ende.
        Die Elemente sind Knotenlabels des Liniengraphen.

        :param: min_fahrten: Minimale Anzahl von Fahrten, die ein Anschluss aufweisen muss,
            um in die Auswahl aufgenommen zu werden.
            Per default (0), werden auch Strecken zwischen unbenutzten Anschlüssen erstellt.

        :param: min_laenge: Minimale Länge (Anzahl Wegpunkte) einer Strecke.
            Kürzere Strecken werden ignoriert.
            Die Defaultlänge 2 liefert auch direkte Strecken zwischen Einfahrt und Ausfahrt.

        :return: Liste von Listen von Liniengraphlabels
        """

        anschluesse = [x for x, d in self.nodes(data=True) if d.get('typ', '?') == 'Anst']
        strecken = []

        for ein, aus in itertools.permutations(anschluesse, 2):
            try:
                fahrten = min(self.nodes[ein]['fahrten'], self.nodes[aus]['fahrten'])
            except KeyError:
                fahrten = -1

            if ein != aus and fahrten >= min_fahrten:
                strecke = self.strecke(ein, aus)
                if len(strecke) >= min_laenge:
                    strecken.append(strecke)

        return strecken

    def strecken_zeitachse(self, strecke: List[BahnhofElement], metrik: str = 'fahrzeit_min') -> List[Union[int, float]]:
        """
        Distanzen entlang einer Strecke berechnen

        Kumulierte Distanzen der Haltepunkte ab dem ersten Punkt der Strecke berechnen.
        Die Distanz wird als Fahrzeit in Minuten angegeben.

        Als Fahrzeit wird für jeden Abschnitt der erste der folgenden Werte genommen, der grösser als Null ist:
        1. 'fahrzeit_manuell'-Attribut der Liniengraph-Kante (vom Benutzer konfiguriert).
        2. Vom parameter-Argument bezeichnetes Attribut der Liniengraph-Kante.
        3. 1 (default, auch bei fehlender Kante im Liniengraph).

        Args:
            strecke: Liste von Linienpunkten
            metrik: Kantenattribut im Liniengraph:
                fahrzeit_min, fahrzeit_schnitt oder fahrzeit_max.

        Returns: distanz = Fahrzeit in Minuten.
            Die Liste enthält die gleiche Anzahl Elemente wie die Strecke.
            Das erste Element ist 0.
        """

        kanten = zip(strecke[:-1], strecke[1:])
        integrierte_distanz = 0.
        result = [integrierte_distanz]
        for kante in kanten:
            u, v = kante
            integrierte_distanz += self.distanz(u, v, metrik)
            result.append(integrierte_distanz)

        return result

    def distanz(self, u: BahnhofElement, v: BahnhofElement, metrik: str) -> Any:
        """
        Distanz zwischen zwei Bahnh"ofen

        Es muss eine direkte Kante zwischen den zwei Bahnh"ofen bestehen.

        Args:
            u: Erste Betriebsstelle (Bf oder Anst)
            v: Zweite Betriebsstelle (Bf oder Anst)
            metrik: Kantenattribut im Liniengraph:
                fahrzeit_min, fahrzeit_schnitt oder fahrzeit_max.
        """

        try:
            data = self[u][v]
            zeit = data.get('fahrzeit_manuell', 0) or data.get(metrik, 0)
        except KeyError:
            logger.warning(f"Verbindung {u}-{v} nicht im Liniengraph.")
            zeit = 0

        return max(1, zeit)

    def import_konfiguration(self,
                             streckenmarkierung_konfig: Iterable[Dict[str, Any]],
                             bahnhofgraph: BahnhofGraph):
        """
        Streckenmarkierungen aus der Konfiguration übernehmen
        """

        for markierung_kfg in streckenmarkierung_konfig:
            station1 = BahnhofElement.from_string(markierung_kfg['station1'])
            station2 = BahnhofElement.from_string(markierung_kfg['station2'])
            fahrzeit = markierung_kfg.get('fahrzeit', 0)
            markierung = markierung_kfg.get('flags', '')
            if station1 in bahnhofgraph and station2 in bahnhofgraph:
                self.edges[station1, station2]['markierung'] = markierung
                self.edges[station1, station2]['fahrzeit_manuell'] = fahrzeit


    def export_konfiguration(self) -> Sequence[Dict[str, Union[str, int, float, bool]]]:
        """
        Streckenmarkierung in Konfigurationsformat exportieren
        """

        result = []
        for e1, e2, data in self.edges(data=True):
            m = data.get('markierung', '')
            z = data.get('fahrzeit_manuell', 0)
            d = {}
            if m:
                d['flags'] = m
            if z > 0:
                d['fahrzeit'] = z
            if d:
                d['station1'] = str(e1)
                d['station2'] = str(e2)
                result.append(d)

        return result


class Strecken:
    """
    Strecken

    Verwaltet konfigurierte Verbindungen zwischen Bahnhöfen.
    Strecken werden aus dem Liniengraph automatisch erstellt oder aus der Konfiguration gelesen.

    Attribute:
        - liniengraph:
        - strecken: Die Streckendefinition ist ein Dictionary Streckenname -> Liste von Stationen.
        - ordnung: Die Streckenliste wird anhand dieses Index sortiert.
        - auto: Strecke wurde automatisch generiert. False, wenn der Benutzer sie bearbeitet hat.
        - hauptstrecke: Name der Hauptstrecke. Wird beim Oeffnen des Streckenfahrplans voreingestellt.
    """

    def __init__(self):
        super().__init__()
        self.liniengraph:Optional[LinienGraph] = None
        self.strecken: Dict[str, List[BahnhofElement]] = {}
        self.ordnung: Dict[str, int] = {}
        self.auto: Dict[str, bool] = {}
        self._hauptstrecke: Optional[str] = None

    @property
    def hauptstrecke(self) -> str | None:
        return self._hauptstrecke

    @hauptstrecke.setter
    def hauptstrecke(self, name: str | None) -> None:
        if name is None or name in self.strecken:
            self._hauptstrecke = name

    def streckengraph(self, strecke: str) -> LinienGraph:
        """
        Strecke als Liniengraph darstellen

        Kann nützlich sein, wenn auf Liniengraphdaten für eine Strecke zugegriffen werden soll.
        Das Resultat ist ein View und daher nicht veränderbar.

        Todo: Mir ist noch nicht klar, wie dynamisch der View ist,
        d.h. ob Änderungen am Basisgraph automatisch sichtbar werden.
        Ausserdem: Können Attribute verändert werden?
        """

        def fn(node: BahnhofElement) -> bool:
            return node in self.strecken[strecke]

        def fe(node1: BahnhofElement, node2: BahnhofElement) -> bool:
            return node1 in self.strecken[strecke] and node2 in self.strecken[strecke]

        return nx.subgraph_view(self.liniengraph, filter_node=fn, filter_edge=fe)

    def add_strecke(self,
                    name: str,
                    stationen: Iterable[BahnhofElement],
                    ordnung: int = 99,
                    auto: bool = True,
                    ) -> None:
        """
        Strecke definieren
        """

        stationen = list(stationen)
        if len(stationen) < 2:
            return

        self.strecken[name] = list(stationen)
        self.ordnung[name] = ordnung
        self.auto[name] = auto

    def remove_strecke(self, name: str):
        """
        Streckendefinition entfernen
        """

        try:
            del self.strecken[name]
        except KeyError:
            pass
        try:
            del self.ordnung[name]
        except KeyError:
            pass
        try:
            del self.auto[name]
        except KeyError:
            pass
        if self._hauptstrecke == name:
            self._hauptstrecke = None

    def clear(self):
        """
        Alle Streckendefinitionen löschen
        """

        self.strecken.clear()
        self.ordnung.clear()
        self.auto.clear()
        self._hauptstrecke = None

    def validate(self, bahnhofgraph: BahnhofGraph):
        """
        Strecken mit Bahnhofgraph abgleichen

        Überprüft die Streckendefinitionen auf korrekte Stationen und
        entfernt nicht vorhandene Stationen. Bei weniger als zwei Stationen
        wird die Strecke gelöscht.
        """

        korrekturen = {}
        for name in self.strecken.keys():
            strecke = self.strecken[name]
            stationen = [station for station in strecke if bahnhofgraph.has_node(station)]
            if len(stationen) != len(strecke):
                korrekturen[name] = stationen

        for name, stationen in korrekturen.items():
            if len(stationen) >= 2:
                self.strecken[name] = stationen
            else:
                self.remove_strecke(name)

    def import_konfiguration(self,
                             strecken_konfig: Iterable[Dict[str, Any]],
                             bahnhofgraph: BahnhofGraph):
        """
        Streckendefinition aus der Konfiguration übernehmen
        """

        strecken = {}
        haupt = {}
        ordnung = {}
        auto = {}
        for strecke_kfg in strecken_konfig:
            strecke = []
            for station in strecke_kfg['stationen']:
                if bahnhofgraph.has_node(node := BahnhofElement.from_string(station)):
                    strecke.append(node)
            if len(strecke) < 2:
                continue

            key = strecke_kfg.get('name')
            if not key:
                key = "-".join((str(strecke[0]), str(strecke[-1])))

            strecken[key] = strecke
            haupt[key] = strecke_kfg.get('haupt', False)
            ordnung[key] = strecke_kfg.get('ordnung', 99)
            auto[key] = strecke_kfg.get('auto', True)

        for key in ordnung:
            self.strecken[key] = strecken[key]
            self.ordnung[key] = ordnung[key]
            self.auto[key] = auto[key]

        hauptstrecken = [k for k, v in haupt.items() if v]
        if hauptstrecken:
            self.hauptstrecke = min(hauptstrecken, key=ordnung.get)
        else:
            self.hauptstrecke = None

    def export_konfiguration(self) -> Sequence[Dict[str, Any]]:
        """
        Streckendeklaration in Konfigurationsformat exportieren
        """

        konfig = []

        for key in sorted(self.ordnung.keys(), key=self.ordnung.get):
            stationen = [str(station) for station in self.strecken[key]]
            konfig.append({'name': key,
                           'haupt': key == self.hauptstrecke,
                           'ordnung': self.ordnung[key],
                           'auto': self.auto[key],
                           'stationen': stationen})

        return konfig
