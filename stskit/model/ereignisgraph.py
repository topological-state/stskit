"""
Ereignisgraph-Modul

Der Ereignisgraph ist die zentrale Datenstruktur zur Protokollierung von vergangenen Ereignissen
sowie zur Prognose des Zeitpunkts von zukünftigen Ereignissen und damit der Verspätung von Zügen.
Der Betriebsablauf wird hierzu in Zeitpunkte (Knoten) und Zeitabstände (Kanten) zerlegt,
so dass sich die Prognose aus einer Traverse des Graphen ableiten lässt.

Dieses Design ermöglicht es, den Prognosealgorithmus einfach zu halten,
wobei die Komplexität des Betriebsablaufs allein im Graph kodiert ist.

Der Ablauf ist wie folgt:

1. Der Ereignisgraph wird mit Plandaten aus einem Zielgraph erstellt.
   Nur die Startpunkte von Zügen ohne Vorgänger haben absolute Zeitangaben.
   Der restliche Pfad des Zuges enthält die Zeitinformation als minimale und maximale Zeitdauer
   in den Verbindungskanten.
2. Bei Ereignissen im laufenden Betrieb wird der Zeitpunkt in den entsprechenden Knoten protokolliert
   und die im Knoten erfasste Zeit festgelegt.
3. Bei noch nicht eingefahrenen Zügen wird periodisch die erwartete Ankunftszeit im ersten Knoten aktualisiert.
4. Der Fdl markiert Abhängigkeiten wie Anschlüsse, Kreuzungen, Überholungen etc.
   Diese werden als zusätzliche Kanten eingefügt.
5. Zur Prognose wird der Graph ausgehend von den Startpunkten traversiert und
   die in den Kanten erfassten Zeiten entlang der Zugpfade aufgerechnet.

"""

from abc import ABCMeta, abstractmethod
import copy
import itertools
import logging
import math
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.plugin.stsobj import Ereignis, format_minutes
from stskit.plugin.stsobj import time_to_minutes
from stskit.model.graphbasics import dict_property
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.zielgraph import ZielGraph, ZielGraphNode, ZielGraphEdge, ZielLabelType, MIN_MINUTES

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class EreignisLabelType(NamedTuple):
    """
    Identifikation des Ereignisses.

    """
    zid: int
    zeit: float
    typ: str


class EreignisGraphNode(dict):
    """
    EreignisGraphNode

    """

    zid = dict_property("zid", int, docstring="Zug-ID")
    fid = dict_property("fid", ZielLabelType,
                        docstring="""
                            Fahrplanziel-ID bestehend aus Zug-ID, Ankunfts- oder Abfahrtszeit in Minuten, Plangleis.
                            Dies ist das Nodelabel im Zielgraph, siehe stsobj.FahrplanZeile.fid.
                            Vom Fdl eingefügte Ereignisse haben kein fid.
                            """)
    typ = dict_property("typ", str,
                        docstring="""
                            Vorgang:
                                'An': Ankunft,
                                'Ab': Abfahrt,
                                'E': Ersatz,
                                'F': Flügelung,
                                'K': Kupplung.
                            """)
    quelle = dict_property("quelle", str,
                           docstring="""Quelle des Eintrags:
                            'sts': Zugdetails vom Simulator,
                            'fdl': Fahrdienstleiter
                           """)
    plan = dict_property("plan", str,
                         docstring="Gleis- oder Anschlussname nach Fahrplan.")
    plan_bst = dict_property("plan_bst", BahnhofElement,
                             docstring="Plangleis in Betriebsstellen-Notation.")
    gleis = dict_property("gleis", str,
                          docstring="Gleis- oder Anschlussname nach aktueller Disposition.")
    gleis_bst = dict_property("gleis_bst", BahnhofElement,
                              docstring="Effektives Gleis in Betriebsstellen-Notation.")
    zeit = dict_property("zeit", float,
                         docstring="""Zeitwert, der in der Knoten-ID verwendet wird.
                            Dieser entspricht, wo möglich, dem t_plan-Property,
                            kann aber auch davon abweichen, damit die ID eindeutig ist.
                            Der Wert muss vom Ersteller gesetzt werden.
                            """)
    t_plan = dict_property("t_plan", Optional[float], "Geplante Uhrzeit in Minuten")
    t_prog = dict_property("t_prog", Optional[float], "Geschätzte Uhrzeit in Minuten")
    t_mess = dict_property("t_mess", Optional[float], "Gemessene Uhrzeit in Minuten")
    s = dict_property("s", float, "Ort in Minuten")

    # die folgenden properties werden vom bildfahrplan genutzt und sind ausserhalb undefiniert!
    # der bahnhofgraph kann sich zur laufzeit ändern.
    # wir definieren daher keine statischen bf und bft properties.
    bst = dict_property("bst", BahnhofElement,
                        "Betriebsstelle (Bahnhof oder Anschlussgruppe), in der das Ereignis stattfindet. "
                        "Wird vom Bildfahrplan genutzt. Sonst undefiniert!")
    farbe = dict_property("farbe", str,
                        "Linienfarbe in Matplotlib-Notation. "
                        "Wird vom Bildfahrplan genutzt. Sonst undefiniert!")
    marker = dict_property("marker", str,
                           "Grafiksymbol nach Matplotlib-Notation. "
                           "Wird vom Bildfahrplan genutzt. Sonst undefiniert!")

    @property
    def node_id(self) -> EreignisLabelType:
        """
        Identifikation des Ereignisses.

        """

        return EreignisLabelType(self.zid, self.zeit, self.typ)

    @property
    def t_eff(self) -> float:
        """
        Effektive Uhrzeit des Ereignisses.

        Dies ist entweder die gemessene, prognostizierte oder geplante Zeit - je nachdem welches Attribut definiert ist.

        @raise AttributeError wenn keines der Attribute gesetzt ist.
        """
        result = self.get("t_mess") or self.get("t_prog") or self.get("t_plan")
        if result is not None:
            return result
        else:
            raise AttributeError(f"Ereignis {self.node_id} hat kein Zeitattribut.")


class EreignisGraphEdge(dict):
    zid = dict_property("zid", int)
    typ = dict_property("typ", str,
                        docstring="""
                            Verbindungstyp:
                                'P': planmässige Fahrt,
                                'H': Halt,
                                'B': Betriebshalt, vom Fdl angeordneter, ungeplanter Halt,
                                'E': Ersatz (Kante von E-Flag nach E-Knoten),
                                'F': Flügelung (Kante von F-Flag nach F-Knoten),
                                'K': Kupplung (Kante von K-Flag nach K-Knoten),
                                'R': vom Fdl angeordnete Rangierfahrt, z.B. bei Lokwechsel,
                                'A': vom Fdl angeordnete Abhängigkeit,
                                'O': Hilfskante für Sortierordnung.
                            """)
    quelle = dict_property("quelle", str,
                           docstring="""Quelle des Eintrags:
                            'sts': Zugdetails vom Simulator,
                            'fdl': Fahrdienstleiter
                           """)
    dt_min = dict_property("dt_min", float, "Minimale Dauer in Minuten")
    dt_max = dict_property("dt_max", float, "Maximale Dauer in Minuten")
    dt_fdl = dict_property("dt_fdl", float, "Fdl-Korrektur: positiv erhöht dt_min, negativ erniedrigt dt_max")
    # dt = dict_property("dt", float, "Effektive Dauer in Minuten")
    ds = dict_property("ds", float, "Strecke in Minuten")

    farbe = dict_property("farbe", str)
    titel = dict_property("titel", str)
    fontstyle = dict_property("fontstyle", str)
    linewidth = dict_property("linewidth", int)
    linestyle = dict_property("linestyle", str)
    auswahl = dict_property("auswahl", int)


class EreignisGraph(nx.DiGraph):
    """
    Zeitliche Abfolge von Ereignissen

    Der Ereignisgraph dient zur Protokollierung von vergangenen Ereignissen
    und zur Abschätzung des Zeitpunkts von zukünftigen Ereignissen.
    Der Graph ist darauf ausgelegt,
    dass die Prognose mittels eines einfachen Message-Passing-Algorithmus berechnet werden kann,
    der nicht von Knoten- und Kantentypen abhängt.

    Der EreignisGraph ist ein gerichteter Graph, der die einzelnen Betriebsereignisse und ihre Abfolge kodiert.
    Die Knoten sind Ereignisse wie Ankunft, Abfahrt, usw.
    Die Kanten definieren die Abfolge von Ereignissen und den zeitlichen Abstand.

    Konzeptuell wichtig ist, dass ein Ereignis keine Zeitdauer hat.
    Ein Aufenthalt muss daher mit zwei Knoten (Ankunft und Abfahrt) und einer Kante zwischen ihnen dargestellt werden.

    Der EreignisGraph ist gerichtet.

    Attribute
    ---------

    zuege: Verzeichnis (Set) der ID-Nummern der Züge, die im Graph vorkommen.
        Der Pfad eines Zuges (geordnete Abfolge von Knoten mit derselben Zug-ID)
        wird vom Generator zugpfad angegeben.

    zugpositionen: Letztes passiertes Ereignis der sichtbaren Züge.
        Wird von der Ereignisauswertung in sim_ereignis_uebernehmen verwaltet und gebraucht.

    zugplangleise: Letzte vom Sim gemeldeten Plangleise der sichtbaren Züge.
        Wird von der Ereignisauswertung in sim_ereignis_uebernehmen verwaltet und gebraucht.

    zugplanereignisse: Nächste erwartete Ereignisse der sichtbaren Züge.
        Wird von der Ereignisauswertung in sim_ereignis_uebernehmen verwaltet und gebraucht.
    """

    node_attr_dict_factory = EreignisGraphNode
    edge_attr_dict_factory = EreignisGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.zuege: Set[int] = set()
        self.zuganfaenge: Dict[int, EreignisLabelType] = {}
        self.zugpositionen: Dict[int, EreignisLabelType] = {}
        self.zugplangleise: Dict[int, str] = {}
        self.zugplanereignisse: Dict[int, EreignisLabelType] = {}

    def copy(self, as_view=False):
        obj = super().copy(as_view)

        if as_view:
            obj.zuege = self.zuege
            obj.zuganfaenge = self.zuganfaenge
            obj.zugpositionen = self.zugpositionen
            obj.zugplangleise = self.zugplangleise
            obj.zugplanereignisse = self.zugplanereignisse
        else:
            obj.zuege = self.zuege.copy()
            obj.zuganfaenge = self.zuganfaenge.copy()
            obj.zugpositionen = self.zugpositionen.copy()
            obj.zugplangleise = self.zugplangleise.copy()
            obj.zugplanereignisse = self.zugplanereignisse.copy()

        return obj

    def to_undirected_class(self):
        return EreignisGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def node_info(self, node: EreignisLabelType) -> str:
        """
        Information zu Ereignisknoten für Log
        """

        try:
            data = self.nodes[node]
        except KeyError:
            return f"Ereignisknoten {node} nicht im Ereignisgraph."

        result = (f"Ereignisknoten {node}: {data.get('typ', '?')}, {data.get('plan', '?')}, {data.get('quelle', '?')}, "
                  f"t_plan = {format_minutes(data.get('t_plan', 0))}, "
                  f"t_prog = {format_minutes(data.get('t_prog', 0))}, "
                  f"t_mess = {format_minutes(data.get('t_mess', 0))}")

        return result

    def edge_info(self, u: EreignisLabelType, v: EreignisLabelType) -> str:
        """
        Information zu Ereigniskante für Log
        """

        try:
            data = self.edges[(u, v)]
        except KeyError:
            return f"Kante {u},{v} nicht im Ereignisgraph."

        result = (f"Kante {u}, {v}: {data.get('typ', '?')}, {data.get('quelle', '?')}, "
                  f"ds = {data.get('ds', '-')}, "
                  f"dt_min = {data.get('dt_min', '-')}, "
                  f"dt_max = {data.get('dt_max', '-')}, "
                  f"dt_fdl = {data.get('dt_fdl', '-')}")

        return result

    def zugpfad(self, zid: int,
                start: Optional[EreignisLabelType] = None,
                stop: Optional[EreignisLabelType] = None,
                kuppeln: bool = False) -> Iterable[EreignisLabelType]:
        """
        Generator für die Knoten eines Zuges
        
        Beginnend mit dem Startknoten liefert der Generator die Knoten-IDs eines Zuges
        in der Reihenfolge ihres Auftretens.

        :param zid: Zug-ID
        :param start: Knoten-ID des ersten Knotens.
            Falls None (default) der erste Knoten des Zuges mit ID (zid, 0).
        :param stop: Knoten-ID des ersten nicht mehr gelieferten Knotens.
            Falls None (default) werden die Knoten bis einschliesslich des letzten des Zuges geliefert.
        :param kuppeln: Wenn True, fährt der Generator mit dem Folgezug (nach Ersatz oder Kuppeln) fort.
            Beim Flügeln, verläuft der Pfad immer über den Stammzug.
        :return: Generator von Knoten-IDs.
        """

        node = self.zuganfaenge[zid]
        if not self.has_node(node):
            logger.debug(f"EreignisGraph.zugpfad(zid={zid}, start={start}, stop={stop}), node {node} fehlt.")
            return

        while node is not None:
            if node == start:
                start = None
            if node == stop:
                return
            if start is None:
                yield node

            for n in self.successors(node):
                if n.zid == zid:
                    node = n
                    break
                elif kuppeln and self.nodes[n]['typ'] == 'K':
                    node = n
                    zid = n.zid
                    break
                elif kuppeln and self.nodes[node]['typ'] == 'E' and self.edges[(node, n)]['typ'] == 'H':
                    node = n
                    zid = n.zid
                    break
            else:
                node = None

    def prev_ereignis(self, label: EreignisLabelType, typ: Optional[str] = None) -> Optional[EreignisLabelType]:
        """
        Vorheriges Ereignislabel eines Zuges

        Diese Methode gibt das vorherige Ereignis des Zuges bzw. (bei Ersatz oder Flügelung) des Vorgängerzuges zurück.
        Wenn das typ-Argument gesetzt ist, wird das Ereignis nur zurückgegeben, wenn der Typ übereinstimmt.

        Vorsicht: Diese Methode sucht nicht nach einem bestimmten Ereignis!

        :param label: Label des Ereignisnodes
        :param typ: Ereignistyp (EreignisGraphNode.typ)
        :return Label des gefundenen Ereignisses oder None
        """

        for n in self.predecessors(label):
            if n.zid == label.zid or self.nodes[n]['typ'] in {'E', 'F'}:
                if typ is None or self.nodes[n]['typ'] == typ:
                    return n

        return None

    def next_ereignis(self, label: EreignisLabelType, typ: Optional[str] = None) -> Optional[EreignisLabelType]:
        """
        Nächstes Ereignislabel eines Zuges

        Diese Methode gibt das nächste Ereignis des Zuges bzw. (bei Ersatz oder Kupplung) des Folgezuges zurück.
        Wenn das typ-Argument gesetzt ist, wird das Ereignis nur zurückgegeben, wenn der Typ übereinstimmt.

        Vorsicht: Diese Methode sucht nicht nach einem bestimmten Ereignis!

        :param label: Label des Ereignisnodes
        :param typ: Ereignistyp (EreignisGraphNode.typ)
        :return Label des gefundenen Ereignisses oder None
        """

        try:
            start_typ = self.nodes[label]['typ']
        except KeyError:
            start_typ = None

        for n in self.successors(label):
            if (n.zid == label.zid or
                    (start_typ == 'E' and self.edges[(label, n)]['typ'] == 'H') or
                    self.nodes[n]['typ'] == 'K'):
                if typ is None or self.nodes[n]['typ'] == typ:
                    return n

        return None

    def _zuganfaenge_suchen(self):
        """
        Startknoten jedes Zuges markieren

        Der Startknoten eines Zuges ist in zuganfaenge verzeichnet.
        Dies ist unabhängig davon, ob der Startknoten aus einer Einfahrt, Startaufstellung oder
        einem anderen Zug hervorgeht.
        """

        for node in self.nodes:
            for p in self.predecessors(node):
                if p.zid == node.zid:
                    break
            else:
                self.zuganfaenge[node.zid] = node

    def zielgraph_importieren(self, zg: ZielGraph, clean=False, quelle='sts'):
        """
        Zielgraph importieren

        Der Ereignisgraph wird anhand eines vollständigen Zielgraphs aufgebaut oder aktualisiert.

        Fahrplanhalte werden in Ankunfts- und Abfahrtsereignisse aufgelöst,
        Betriebsvorgänge werden in entsprechende graphische Muster übersetzt.

        Die Methode arbeitet mit EreignisNodeBuilder- und EreignisEdgeBuilder-Objekten.
        In einem ersten Schritt werden alle Zielknoten in ZielEreignisNodeBuilder übersetzt.
        Im zweiten Schritt werden die Zielkanten in ZielEreignisEdgeBuilder übersetzt und ausgeführt.
        Bei der Ausführung der Builder werden die Zielelemente dem Ereignisgraphen hinzugefügt.

        Die gestaffelte Übersetzung von Knoten und Kanten in Builders bietet die notwendige Flexibilität
        in den folgenden Situationen:
        - Es gibt keine eindeutige Zuordnung von Zielknoten zu Ereignisknoten,
          jedoch im Verlauf dieser Methode eine Zuordnung von Zielknoten zu ZielEreignisNodeBuilder.
        - Die Labels von Ereignisknoten können nicht aus Zielknoten abgeleitet werden.
          Es wird eine fortlaufende Nummer eingesetzt.
          Lediglich der erste Ereignisknoten eines Zuges wird mit der Nummer 0 markiert.
        - Zielpunkte im Zielgraph ergeben je nach Typ eines oder zwei Ereignisse.
        - Betriebsvorgänge sind im Zielgraph im Kantentyp dargestellt, im Ereignisgraph durch die Topologie.
        - Beim Iterieren über Kanten kommen Knoten mehrmals vor.
          Knoten dürfen aber nur einmal in den Graphen eingesetzt werden,
          weil es keine eindeutige Zuordnung von Zielknoten zu Ereignisknoten gibt.

        :param zg: Zielgraph enthält die Ursprungsdaten
        :param clean: Ereignisgraph vollständig neu aufbauen (True)
            oder nur neue Züge hinzufügen (False, default).
            Bei True gehen Änderungen an den Attributen verloren, bei False werden sie beibehalten.
        """

        if clean:
            self.clear()
            self.zuege = set()

        node_builders = {}
        for zg1, zg1_data in zg.nodes(data=True):
            builder = ZielEreignisNodeBuilder(self)
            builder.import_ziel(zg, zg1_data)
            builder.quelle = quelle
            node_builders[zg1] = builder

        edge_builders = {}
        for zg1, zg2, zge_data in zg.edges(data=True):
            builder = None

            if zge_data.typ == 'P':
                builder = PlanfahrtEdgeBuilder(self)
            elif zge_data.typ == 'E':
                builder = ErsatzEdgeBuilder(self)
            elif zge_data.typ == 'F':
                builder = FluegelungEdgeBuilder(self)
            elif zge_data.typ == 'K':
                builder = KupplungEdgeBuilder(self)
            else:
                logger.warning(f"Unbekannter Zielkantentyp {zge_data.typ}")

            if builder is not None:
                builder.set_edge(node_builders[zg1], node_builders[zg2])
                builder.quelle = quelle
                edge_builders[(zg1, zg2)] = builder

        for builder in node_builders.values():
            builder.add_to_graph()
        for builder in edge_builders.values():
            builder.add_to_graph()

        self._zuganfaenge_suchen()

    def prognose(self):
        """
        Zeitprognose durchführen

        Für jeden nicht fixierten Knoten wird die erwartete Zeit berechnet.
        Die Zeit wird anhand der Fahrplanzeit und
        von aggregierten Minimal- und Maximalzeiten der einlaufenden Kanten bestimmt.

        Wenn die Fahrplanzeit zwischen Minimal- und Maximalzeit liegt, wird sie unverändert übernommen.
        Ansonsten wird sie auf das Maximum reduziert, wenn sie grösser als das Maximum ist,
        und auf das Minimum erhöht, wenn sie kleiner als das Minimum ist.
        Die resultierende Zeit ist in jedem Fall grösser oder gleich der Minimalzeit.

        Mit diesem Algorithmus können folgende Fälle abgebildet werden:
        1. Normaler Halt:
           dt_min ist die minimale Aufenthaltszeit für den Fahrgastwechsel oder andere Betriebsvorgänge.
           dt_max wird nicht definiert.
        2. Halt mit vorzeitiger Abfahrt:
           dt_min ist die minimale Aufenthaltszeit für den Fahrgastwechsel oder andere Betriebsvorgänge.
           dt_max wird deklariert, wenn der Zug vorzeitig abfahren soll.
        3. Durchfahrt:
           dt_min ist 0.
           dt_max wird nicht definiert.
        4. Abwarten eines anderen Ereignisses:
           dt_min definiert die zusätzliche Wartezeit zum vorausgehenden Ereignis.
           dt_max wird nicht definiert.
        5. Vorzeitige Abfahrt um einem anderen Zug auszuweichen:
           dt_max ist negativ und definiert wie viel früher der Zug abfahren soll.
           dt_min wird nicht definiert.

        """

        self._schleifen_aufbrechen()
        try:
            nodes = nx.topological_sort(self)
        except nx.NetworkXUnfeasible as e:
            logger.error("Fehler beim Sortieren des Zielgraphen")
            logger.exception(e)
            return

        for zielnode in nodes:
            ziel_data = self.nodes[zielnode]
            if ziel_data.get("t_mess") is not None:
                continue

            ziel_zeit = -math.inf
            if ziel_data.typ in {'Ab'}:
                if zielnode.zeit == MIN_MINUTES:
                    # einfahrt
                    ziel_zeit = ziel_data.get("t_mess") or ziel_data.get("t_prog") or ziel_data.get("t_plan") or ziel_zeit
                else:
                    ziel_zeit = ziel_data.get("t_plan") or ziel_zeit

            zeit_min = -math.inf
            zeit_max = math.inf
            for startnode in self.pred[zielnode]:
                start_data = self.nodes[startnode]
                edge = (startnode, zielnode)
                edge_data = self.edges[edge]
                dt_min = edge_data.get("dt_min", 0)
                dt_max = edge_data.get("dt_max", 0)
                dt_fdl = edge_data.get("dt_fdl", 0)

                start_zeit = start_data.get("t_mess") or start_data.get("t_prog") or start_data.get("t_plan")
                if start_zeit is None:
                    continue

                zeit_min = max(zeit_min, start_zeit + dt_min + dt_fdl)

                # das analoge für dt_max ist problematisch: was ist der defaultwert von dt_max?
                # zeit_max = min(zeit_max, start_zeit + edge_data.get("dt_max", math.inf) + min(0, edge_data.get("dt_fdl", 0)))

                # lösungsvorschlag:
                if dt_max > 0:
                    zeit_max = min(zeit_max, start_zeit + dt_max)
                if dt_fdl < 0:
                    zeit_max = min(zeit_max, ziel_zeit + dt_fdl)

            result = ziel_zeit
            result = min(result, zeit_max)
            result = max(result, zeit_min)
            if not math.isinf(result):
                ziel_data.t_prog = result
            else:
                logger.warning(f"Keine Zeitprognose möglich für Ereignis {zielnode}")

    def _schleifen_aufbrechen(self):
        """
        Schleifen aufbrechen

        Der Ereignisgraph ist ein gerichteter Graph und darf keine Schleifen enthalten.
        Wenn aus irgendeinem Grund, auch Fehlern in Programm oder Daten, Schleifen vorkommen,
        darf das Programm nicht abstürzen und sollte seine Arbeit so weit wie möglich trotzdem verrichten.
        Diese Funktion bricht etwaige Schleifen an einem willkürlichen Punkt auf und gibt eine Warnung im Log aus.
        """

        while True:
            try:
                cycle = nx.find_cycle(self)
            except nx.NetworkXNoCycle:
                break

            msg = ", ".join((str(edge) for edge in cycle))
            logger.error("Verbotene Schleife im Ereignisgraph: " + msg)
            for edge in cycle:
                if edge[0].zid != edge[1].zid:
                    break
            else:
                edge = cycle[-1]

            self.remove_edge(edge[0], edge[1])
            logger.warning(f"Verbindung {edge} entfernt.")

    def verspaetungen_nach_zielgraph(self, zg: ZielGraph):
        """
        Schreibt die berechneten Verspätungen in den Zielgraphen.

        Die Verspätungen werden aus der Differenz zwischen den t_eff- und t_plan-Feldern der An- und Ab-Knoten berechnet.

        :param zg: Zielgraph
        """

        for ereignis_node, ereignis_data in self.nodes(data=True):
            try:
                ziel_data = zg.nodes[ereignis_data.fid]
            except (AttributeError, KeyError):
                continue

            try:
                v = ereignis_data.t_eff - ereignis_data.t_plan
            except AttributeError:
                logger.warning(f"Unvollständige Zeitinformation für Verspätungsberechnung: {ereignis_data}")
                return

            # todo : E/F/K beachten
            if ereignis_data.typ == 'Ab':
                if ziel_data.typ in {'H', 'D'}:
                    ziel_data.v_ab = v
            elif ereignis_data.typ == 'An':
                if ziel_data.typ in {'H', 'D', 'A'}:
                    ziel_data.v_an = v
                if ziel_data.typ in {'D', 'A'}:
                    ziel_data.v_ab = v

    def sim_ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        Daten von einem Sim-Ereignis übernehmen.

        Aktualisiert die Verspätung und Status-Flags anhand eines Ereignisses im Simulator.

        Aktualisiert werden die folgenden Attribute:
        - zugpositionen
        - zugplangleise
        - zugplanereignisse
        - t_mess der Ereignisknoten

        Phantomzüge:
        Nach gewissen Nummernwechseln (mit Richtungsänderung?) schickt der Sim weiterhin Ereignisse
        unter der Nummer des nun unsichtbaren Zuges.
        Das sichtbar-Attribut des Ereignisarguments ist dabei False.
        Ausser bei den Ereignisarten 'Ausfahrt', 'Ersatz' sollten solche Ereignisse nicht beachtet werden.

        :param ereignis: Ereignis-objekt vom PluginClient
        :return:
        """

        # keine Rangierfahrten
        if ereignis.zid <= 0:
            return

        try:
            meth = getattr(self, "sim_ereignis_" + ereignis.art)
        except AttributeError:
            pass
        else:
            meth(ereignis)

    def _sim_ereignis_messzeit(self, label: EreignisLabelType, ereignis: Ereignis):
        """
        Gemessene Eintreffenszeit eines Ereignisses notieren.

        Die Zeit des Ereignisses wird in das t_mess-Attribut des Ereignisknotens geschrieben.

        Die Messzeit wird nicht geschrieben, wenn das Label None ist,
        der Knoten keine Daten hat, oder
        das Attribut bereits einen Wert hat.

        Untermethode der sim_ereignis-Methoden.

        :param label: Label des Ereignisknotens.
        :param ereignis: Ereignisobjekt vom PluginClient.
            Benötigt werden die Attribute `zid` und `zeit`.
        """

        if label is None:
            return

        try:
            data = self.nodes[label]
        except KeyError:
            logger.error(f"Ereignis {label} hat keine Daten.")
            return

        # Attribut hat bereits einen Wert
        if data.get('t_mess', None):
            return

        data.t_mess = ereignis.zeit.hour * 60 + ereignis.zeit.minute + ereignis.zeit.second / 60
        logger.debug(f"Messzeit {label}, {ereignis.plangleis}, {data.t_mess}")

    def _sim_ereignis_update_planereignis(self, ereignis: Ereignis,
                                          prev_label: EreignisLabelType,
                                          cur_label: EreignisLabelType,
                                          next_typ: str = 'An'):
        """
        Plangleis und Planereignis aus Sim-Ereignis aktualisieren.

        Aktualisiert die self.zugplangleise und self.zugplanereignisse Dictionaries.
        Ersteres wird bedingungslos vom Ereignis übernommen,
        bei letzterem erfolgt eine Konsistenzprüfung aus folgenden Gründen.

        ereignis.plangleis zeigt normalerweise auf Fahrt das nächste (planmässig) anzufahrende Gleis
        oder bei einem Halt (amgleis-Attribut) die (planmässige) Position des Zuges an.
        Das Attribut ist aber leider nicht immer korrekt gesetzt,
        kann also u.U. bei Fahrt noch das letzte Haltegleis anzeigen oder bei Halt bereits das nächste Ziel.

        Die Methode verlangt deshalb ein früher passiertes Ereignis und das letzte passierte Ereignis.
        Sie sucht dann das nächste erwartete Ereignis nach Typ und Plangleis.
        Wenn keines gefunden wird (weil Plangleis mit dem erwarteten Typ bereits abgefahren wurde)
        wird das Planereignis nicht verändert und bleibt u.U. hinter der aktuellen Position zurück,
        bis das nächste Ereignis gemeldet wird.

        Untermethode der sim_ereignis-Methoden.

        :param ereignis: Ereignisobjekt vom PluginClient
            Benötigt werden die Attribute `zid` und `plangleis`.
        :param prev_label: vorheriges passiertes Ereignislabel
        :param cur_label: gerade passiertes Ereignis entsprechend dem Sim-Ereignis.
        :param next_typ: Typ des nächsten erwarteten Ereignisses, 'An' oder 'Ab'.
        """

        self.zugplangleise[ereignis.zid] = ereignis.plangleis
        try:
            start_label = cur_label or prev_label
            next_label = self.zug_ereignis_suchen(ereignis.zid, start=start_label, plan=ereignis.plangleis, typ=next_typ)
        except ValueError:
            next_label = None
        else:
            if start_label is None or next_label.zeit > start_label.zeit:
                self.zugplanereignisse[ereignis.zid] = next_label
        return next_label

    def sim_ereignis_einfahrt(self, ereignis: Ereignis):
        cur_label = self.zuganfaenge[ereignis.zid]
        self._sim_ereignis_messzeit(cur_label, ereignis)
        self.zugpositionen[ereignis.zid] = cur_label
        self.zugplangleise[ereignis.zid] = ereignis.plangleis
        try:
            next_label = self.zug_ereignis_suchen(ereignis.zid, typ='An', quelle='sts')
        except ValueError:
            pass
        else:
            self.zugplanereignisse[ereignis.zid] = next_label

    def sim_ereignis_ausfahrt(self, ereignis: Ereignis):
        try:
            cur_label = list(self.zugpfad(ereignis.zid))[-1]
        except IndexError:
            pass
        else:
            self._sim_ereignis_messzeit(cur_label, ereignis)
        try:
            del self.zugpositionen[ereignis.zid]
            del self.zugplangleise[ereignis.zid]
            del self.zugplanereignisse[ereignis.zid]
        except KeyError:
            pass

    def sim_ereignis_ankunft(self, ereignis: Ereignis):
        # Phantomzug
        if not ereignis.sichtbar:
            return

        prev_label = self.zugpositionen.get(ereignis.zid)
        next_label = cur_label = None

        if ereignis.amgleis:
            # halt
            print("ankunft", ereignis.zid, ereignis.plangleis, ereignis.amgleis)
            try:
                cur_label = self.zug_ereignis_suchen(ereignis.zid, start=prev_label, plan=ereignis.plangleis, typ="An")
            except (AttributeError, ValueError, KeyError) as e:
                print("*** ankunftsereignis nicht gefunden ***")
                print(e)
                pass
            else:
                self._sim_ereignis_messzeit(cur_label, ereignis)
                self.zugpositionen[ereignis.zid] = cur_label

            next_label = self._sim_ereignis_update_planereignis(ereignis, prev_label, cur_label, 'Ab')

        else:
            # durchfahrt
            print("durchfahrt", ereignis.zid, ereignis.plangleis, ereignis.amgleis)
            try:
                cur_label = self.zugplanereignisse.get(ereignis.zid)
                if cur_label is None and prev_label is not None:
                    cur_label = self.next_ereignis(prev_label)
                cur_label = self.zug_ereignis_suchen(ereignis.zid, start=cur_label, typ='An', quelle='sts')
            except (AttributeError, ValueError, KeyError) as e:
                print("*** durchfahrtsereignis nicht gefunden ***")
                print(e)
                pass
            else:
                self._sim_ereignis_messzeit(cur_label, ereignis)
                self.zugpositionen[ereignis.zid] = cur_label

            next_label = self._sim_ereignis_update_planereignis(ereignis, prev_label, cur_label, 'An')

        # print(f"    prev_label: {self.node_info(prev_label)}")
        # print(f"    cur_label: {self.node_info(cur_label)}")
        # print(f"    next_label: {self.node_info(next_label)}")
        # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
        # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

    def sim_ereignis_abfahrt(self, ereignis: Ereignis):
        # Phantomzug
        if not ereignis.sichtbar:
            return

        prev_label = cur_label = next_label = None

        if ereignis.amgleis:
            # abfahrbereit
            prev_label = self.zugpositionen.get(ereignis.zid)
            try:
                cur_label = self.zug_ereignis_suchen(ereignis.zid, start=prev_label, plan=ereignis.plangleis, typ='An')
            except (AttributeError, ValueError, KeyError):
                pass
            else:
                self.zugpositionen[ereignis.zid] = cur_label
            self.zugplangleise[ereignis.zid] = ereignis.plangleis
        else:
            print("abfahrt", ereignis.zid, ereignis.plangleis, ereignis.amgleis)
            # abfahrt
            prev_label = self.zugpositionen.get(ereignis.zid)
            try:
                if prev_plan := self.zugplangleise.get(ereignis.zid):
                    cur_label = self.zug_ereignis_suchen(ereignis.zid, start=prev_label, plan=prev_plan, typ='Ab')
                else:
                    cur_label = self.zug_ereignis_suchen(ereignis.zid, start=prev_label, typ='Ab', quelle='sts')
            except (AttributeError, ValueError, KeyError) as e:
                # kommt vor bei abfahrbereit nach ersatz
                print("*** abfahrtsereignis nicht gefunden ***")
                print(e)
                print(f"    prev_label: {self.node_info(prev_label)}")
                print(f"    prev_plan: {self.zugplangleise.get(ereignis.zid)}")
                print(f"    cur_label: {self.node_info(cur_label)}")
            else:
                self._sim_ereignis_messzeit(cur_label, ereignis)
                self.zugpositionen[ereignis.zid] = cur_label

                next_label = self._sim_ereignis_update_planereignis(ereignis, prev_label, cur_label, 'An')  # ausfahrt?

            # print(f"    prev_label: {self.node_info(prev_label)}")
            # print(f"    cur_label: {self.node_info(cur_label)}")
            # print(f"    next_label: {self.node_info(next_label)}")
            # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
            # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

    def sim_ereignis_rothalt(self, ereignis: Ereignis):
        """
        Betriebshalt verarbeiten

        Es gibt zwei Arten von Betriebshalten:

        1. Der Betriebshalt erfolgt statt Durchfahrt.
            Das letzte Ereignis war eine Ankunft,
            die ausgehende Kante ist vom Typ "B",
            die Quelle der nächsten Abfahrt ist "fdl".
            In diesem Fall ist hier nichts zu tun,
            die Ankunft wurde bereits registriert,
            die Abfahrt wird in "wurdegruen" verarbeitet.
        2. Der Betriebshalt erfolgt zwischen an einem Gleis, das nicht im Fahrplan steht.
            Das letzte Ereignis war eine Abfahrt,
            die darauf folgenden zwei Ereignisse sind vom "fdl"
            und durch eine Kante vom Typ "B" verbunden.
            Wir wissen nicht, wo der Zug genau steht.
            Dieser Fall wird aktuell nicht ausgewertet.
        """

        # Phantomzug
        if not ereignis.sichtbar:
            return

        prev_label = self.zugpositionen.get(ereignis.zid)
        if prev_label is None:
            return
        next_label = cur_label = None

        if prev_label.typ == "An":
            cur_label = self.next_ereignis(prev_label, "Ab")
            try:
                if self.edges[(prev_label, cur_label)]['typ'] == "B":
                    print("Betriebshalt statt Durchfahrt")
            except KeyError:
                pass

        elif prev_label.typ == "Ab":
            cur_label = self.next_ereignis(prev_label, "An")
            next_label = self.next_ereignis(cur_label, "Ab")
            try:
                if self.edges[(cur_label, next_label)]['typ'] == "B":
                    print("Betriebshalt auf Strecke?")
                    # self.messzeit_setzen(cur_label, ereignis)
                    # self.zugpositionen[ereignis.zid] = cur_label
            except KeyError:
                pass

        # print("rothalt")
        # print(f"    prev_label: {self.node_info(prev_label)}")
        # print(f"    cur_label: {self.node_info(cur_label)}")
        # print(f"    next_label: {self.node_info(next_label)}")
        # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
        # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

        self.zugplangleise[ereignis.zid] = ereignis.plangleis

    def sim_ereignis_wurdegruen(self, ereignis: Ereignis):
        """
        Betriebshalt verarbeiten

        Es gibt zwei Arten von Betriebshalten:

        1. Der Betriebshalt erfolgt statt Durchfahrt.
            Das letzte Ereignis war eine Ankunft,
            die ausgehende Kante ist vom Typ "B",
            die Quelle der nächsten Abfahrt ist "fdl".
            In diesem Fall registrieren wir die Abfahrtszeit.
        2. Der Betriebshalt erfolgt zwischen an einem Gleis, das nicht im Fahrplan steht.
            Das letzte Ereignis war eine Abfahrt,
            die darauf folgenden zwei Ereignisse sind vom "fdl"
            und durch eine Kante vom Typ "B" verbunden.
            Wir wissen nicht, wo der Zug genau steht.
            Dieser Fall wird aktuell nicht ausgewertet.
        """

        # Phantomzug
        if not ereignis.sichtbar:
            return

        prev_label = self.zugpositionen.get(ereignis.zid)
        if prev_label is None:
            return
        next_label = cur_label = None

        print("wurdegruen", ereignis.zid, ereignis.plangleis)
        if prev_label.typ == "An":
            cur_label = self.next_ereignis(prev_label, "Ab")
            try:
                if self.edges[(prev_label, cur_label)]['typ'] == "B":
                    print("Abfahrt von Betriebshalt")
                    self._sim_ereignis_messzeit(cur_label, ereignis)
                    self.zugpositionen[ereignis.zid] = cur_label
            except KeyError:
                pass

        next_label = self._sim_ereignis_update_planereignis(ereignis, prev_label, cur_label, 'An')

        # print(f"    prev_label: {self.node_info(prev_label)}")
        # print(f"    cur_label: {self.node_info(cur_label)}")
        # print(f"    next_label: {self.node_info(next_label)}")
        # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
        # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

    def sim_ereignis_ersatz(self, ereignis: Ereignis):
        """
        Ersatz verarbeiten

        Das Ersatzereignis kommt aus dem Polling vom Pluginclient (stsplugin.PluginClient.request_zugliste),
        nicht vom Simulator!
        Es kann u.U. erst nach dem Abfahrtsereignis ankommen.

        ereignis.zid bezeichnet den Stammzug.
        Unser E-Ereignisknoten gehört zum Stammzug, der Ab-Knoten zum Folgezug.
        """

        prev_label = self.zugpositionen.get(ereignis.zid) or self.zuganfaenge.get(ereignis.zid)
        print("ersatz", ereignis.zid, ereignis.plangleis, prev_label)
        try:
            cur_label = self.zug_ereignis_suchen(start=prev_label, plan=ereignis.plangleis, typ="E")
        except (AttributeError, ValueError, KeyError) as e:
            print("*** ersatzereignis nicht gefunden ***")
            print(e)
            print(f"    prev_label: {self.node_info(prev_label)}")
            print(f"    prev_plan: {self.zugplangleise.get(ereignis.zid)}")
        else:
            self._sim_ereignis_messzeit(cur_label, ereignis)

            # folgezug aktualisieren, wenn das abfahrtsereignis noch nicht gemeldet wurde
            for next_label in self.successors(cur_label):
                if self.edges[(cur_label, next_label)]['typ'] == 'H':
                    if next_label.zid not in self.zugpositionen:
                        self.zugpositionen[next_label.zid] = cur_label
                        self.zugplangleise[next_label.zid] = ereignis.plangleis
                        self.zugplanereignisse[next_label.zid] = next_label

                        # print(f"    prev_label: {self.node_info(prev_label)}")
                        # print(f"    cur_label: {self.node_info(cur_label)}")
                        # print(f"    next_label: {self.node_info(next_label)}")
                        # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
                        # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

        try:
            del self.zugpositionen[ereignis.zid]
            del self.zugplangleise[ereignis.zid]
            del self.zugplanereignisse[ereignis.zid]
        except KeyError:
            pass

    def sim_ereignis_kuppeln(self, ereignis: Ereignis):
        """
        Kuppeln verarbeiten

        ereignis.zid bezeichnet den endenden Zug.
        Unser K-Ereignisknoten gehört zum durchgehenden Zug.
        """

        prev_label = self.zugpositionen.get(ereignis.zid) or self.zuganfaenge.get(ereignis.zid)
        print("kuppeln", ereignis.zid, ereignis.plangleis, prev_label)
        try:
            cur_label = self.zug_ereignis_suchen(start=prev_label, plan=ereignis.plangleis, typ="K")
        except (AttributeError, ValueError, KeyError) as e:
            print("*** kuppelnereignis nicht gefunden ***")
            print(e)
            print(f"    prev_label: {self.node_info(prev_label)}")
            print(f"    prev_plan: {self.zugplangleise.get(ereignis.zid)}")
        else:
            self._sim_ereignis_messzeit(cur_label, ereignis)
        try:
            del self.zugpositionen[ereignis.zid]
            del self.zugplangleise[ereignis.zid]
            del self.zugplanereignisse[ereignis.zid]
        except KeyError:
            pass

    def sim_ereignis_fluegeln(self, ereignis: Ereignis):
        """
        Flügeln verarbeiten

        ereignis.zid bezeichnet den Stammzug.
        Unser F-Ereignisknoten gehört zum (durchgehenden) Stammzug.
        """

        prev_label = self.zugpositionen.get(ereignis.zid) or self.zuganfaenge.get(ereignis.zid)
        print("flügeln", ereignis.zid, ereignis.plangleis, prev_label)
        try:
            cur_label = self.zug_ereignis_suchen(start=prev_label, plan=ereignis.plangleis, typ="F")
        except (AttributeError, ValueError, KeyError) as e:
            print("*** flügelnereignis nicht gefunden ***")
            print(e)
            print(f"    prev_label: {self.node_info(prev_label)}")
            print(f"    prev_plan: {self.zugplangleise.get(ereignis.zid)}")
            return
        else:
            self._sim_ereignis_messzeit(cur_label, ereignis)
            for next_label in self.successors(cur_label):
                if self.edges[(cur_label, next_label)]['typ'] == 'H':
                    self.zugpositionen[next_label.zid] = cur_label
                    self.zugplangleise[next_label.zid] = ereignis.plangleis
                    self.zugplanereignisse[next_label.zid] = next_label

                    # print(f"    prev_label: {self.node_info(prev_label)}")
                    # print(f"    cur_label: {self.node_info(cur_label)}")
                    # print(f"    next_label: {self.node_info(next_label)}")
                    # print(f"    edge(p,c): {self.edge_info(prev_label, cur_label)}")
                    # print(f"    edge(c,n): {self.edge_info(cur_label, next_label)}")

    def zug_ereignis_suchen(self, zid = None, start: EreignisLabelType = None, **kwargs) -> EreignisLabelType:
        """
        Ereignis mit gegebenen Attributen im Zugpfad suchen.

        Suche im Zugpfad ab einem wählbaren Startpunkt nach einem Ereignis mit den gegebenen Attributen.
        Die Suche folgt der Richtung des Graphen,
        läuft über durch E/F/K-Ereignisse verbundene Folgezüge
        und endet am Knoten, der keine Nachfolger hat.

        :param zid: Gesuchte Zug-ID (optional).
            Das gesuchte Ereignis muss diese Zug-ID haben.
            zid kann sich von start.zid unterscheiden,
            muss dann aber ein Folgezug von start.zid bezeichnen.
            Mindestens eines der Argumente zid und start muss angegeben werden.
        :param start: Startnode (optional).
            Die Suche startet an diesem Knoten (inklusiv).
            Wenn kein Start angegeben ist, beginnt die Suche am Zuganfang.
            Mindestens eines der Argumente zid und start muss angegeben werden.
        :param kwargs: Gesuchte Attributwerte.
            Die Keys müssen Attributnamen von EreignisGraphNode entsprechen.
            Bei float-Attributen gilt eine Toleranz von 0.0001.
        :raise KeyError: Zug wird nicht gefunden.
        :raise ValueError: Attributwerte werden nicht gefunden.
        """

        if start is None:
            start_zid = zid
        else:
            start_zid = start.zid
            if zid is not None:
                kwargs['zid'] = zid

        for label in self.zugpfad(start_zid, kuppeln=True):
            if start is not None:
                if label == start:
                    start = None
                else:
                    continue

            data = self.nodes[label]
            for kw, arg in kwargs.items():
                if kw in {'t_mess', 't_plan', 't_prog', 's'}:
                    if abs(arg - data.get(kw)) > 0.0001:
                        break
                elif data.get(kw) != arg:
                    break
            else:
                return label

        raise ValueError(f"Suche nach {kwargs} im Pfad von {start or zid} fehlgeschlagen.")


class EreignisGraphUngerichtet(nx.Graph):
    """
    Ungerichtete Variante von EreignisGraph

    Für gewisse Algorithmen kann es nötig sein, den Graphen vorübergehend in einen ungerichteten umzuwandeln.
    Diese Klasse sorgt dafür, dass die Knoten- und Kantendaten die richtige Klasse aufweisen.
    """
    node_attr_dict_factory = EreignisGraphNode
    edge_attr_dict_factory = EreignisGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return EreignisGraph


class EreignisNodeBuilder(metaclass=ABCMeta):
    """
    Abstrakter Ersteller von Ereignisblöcken

    Ein EreignisNodeBuilder erstellt auf Abruf Blöcke (oder Subgraphen) mit Knoten und Kanten in einem EreignisGraph.
    Die Struktur dieser Blöcke wird durch die abgeleitete Klasse definiert.
    Bevor die add_to_graph-Methode aufgerufen wird, kann der Builder Informationen zum Aufbau des Blocks erhalten.
    Erst mittels add_to_graph werden die Knoten und Kanten in den Graphen geschrieben.

    Der EreignisNodeBuilder wird eingesetzt, wo im ursprünglichen Graphen ein Knoten übersetzt wird.
    Der EreignisEdgeBuilder wird eingesetzt, wo im ursprünglichen Graphen eine Kante übersetzt wird.

    Builder werden nur einmal ausgeführt und dürfen bei weiteren Aufrufen keine weiteren Elemente hinzufügen.
    """
    def __init__(self, graph: EreignisGraph):
        self.graph = graph
        self.quelle: str = 'sts'
        self.ausgefuehrt = False

    @abstractmethod
    def first_label(self) -> EreignisLabelType:
        """
        Label des ersten erstellten Ereignisses.

        Das Ereignislabel wird von einlaufenden Kanten referenziert.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """
        return None

    @abstractmethod
    def last_label(self) -> EreignisLabelType:
        """
        Label des letzten erstellten Ereignisses.

        Das Ereignislabel wird von auslaufenden Kanten referenziert.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """
        return None

    @abstractmethod
    def add_to_graph(self):
        """
        Knoten und Kanten zum Ereignisgraphen hinzufügen.

        Die Methode fügt die von dem Builder verantworteten Knoten und internen Kanten dem EreignisGraph hinzu.
        Die Methode darf nur beim ersten Aufruf eine Wirkung zeigen.
        """
        self.ausgefuehrt = True


class ZielEreignisNodeBuilder(EreignisNodeBuilder):
    """
    Zielgraph-Node in Ereignisgraph-Node übersetzen.

    Dieser Builder übersetzt einen ZielGraph-Knoten in den enstprechenden Block von Ereignisknoten und -kanten.
    Bei Ein- und Ausfahrten wird ein Knoten erstellt,
    bei Planhalten und Durchfahrten ein Ankunfts- und ein Abfahrtsknoten mit Verbindungskante.

    Die Knoten- und Kantenattribute werden in der import_ziel-Methode entsprechend den Zielattributen gesetzt.
    Zu diesem Zeitpunkt werden auch die nodes- und edges-Listen mit einem einfachen Ankunft-Abfahrt-Muster initialisiert.
    Bei komplexen Betriebsvorgängen werden die nodes und edges von den EreignisEdgeBuildern verändert,
    bevor die Struktur mittels add_to_graph in den EreignisGraph geschrieben wird.
    """

    def __init__(self, graph: EreignisGraph):
        super().__init__(graph)
        # Diagnostik
        self.zid: Optional[int] = None
        # Diagnostik
        self.fid: Optional[ZielLabelType] = None
        # Speichert den ersten importierten Node, um Kopien herzustellen (new_node)
        self.node_template: Optional[EreignisGraphNode] = None
        # Speichert die importierte Kante, um Kopien herzustellen (new_edge)
        self.edge_template: Optional[EreignisGraphEdge] = None
        self.nodes: List[EreignisGraphNode] = []
        self.edges: List[EreignisGraphEdge] = []
        self.kupplungen: List[EreignisGraphNode] = []

    def first_label(self) -> EreignisLabelType:
        """
        Label des ersten erstellten Ereignisses.

        Dies ist das Label von n1d oder n2d.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """

        return self.nodes[0].node_id

    def last_label(self) -> EreignisLabelType:
        """
        Label des letzten erstellten Ereignisses.

        Dies ist das Label von n2d oder n1d.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """

        return self.nodes[-1].node_id

    def new_node(self, **attrs) -> EreignisGraphNode:
        """
        Neuen Knoten zum gleichen Ziel erstellen

        Mit den Eigenschaften des direkt importierten Ankunfts- oder Abfahrtsknotens (vor der Bearbeitung).
        Mit den Keyword-Argumenten können einzelne Attribute mit neuen Werten belegt werden.

        :param attrs: Attribute mit neuen Werten initialisieren.
        """
        node = copy.copy(self.node_template)
        node.update(**attrs)
        return node

    def new_edge(self, **attrs) -> EreignisGraphEdge:
        """
        Neue Kante zum gleichen Ziel erstellen

        Mit Typ 'H' und dem Ziel entsprechenden Mindestaufenthalt.
        Mit den Keyword-Argumenten können einzelne Attribute mit neuen Werten belegt werden.

        :param attrs: Attribute mit neuen Werten initialisieren.
        """
        edge = copy.copy(self.edge_template)
        edge.update(**attrs)
        return edge

    def import_ziel(self, ziel_graph: ZielGraph, ziel_node: ZielGraphNode):
        """
        Daten von Zielnode übernehmen.

        Erstellt bei gewöhnlichen Fahrzielen einen Ankunfts- und einen Abfahrtsknoten.
        Bei Ein- oder Ausfahrten wird nur ein Abfahrts- resp. Ankunftsknoten erstellt.

        Wenn der ziel_node der erste des Zuges ist, wird zuganfang auf True gesetzt.
        """

        self.zid = ziel_node.zid
        self.fid = ziel_node.fid

        # todo : Am Zuganfang durch E/F/K keinen Ankunftsknoten erzeugen.
        if ziel_node.typ in {'H', 'D', 'A'}:
            n1d = EreignisGraphNode(
                quelle=self.quelle,
                typ='An',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                zeit=ziel_node.fid.zeit,
                plan=ziel_node.plan,
                plan_bst=ziel_node.plan_bst,
                gleis=ziel_node.gleis,
                gleis_bst=ziel_node.gleis_bst,
                s=0
            )
            try:
                n1d.t_prog = n1d.t_plan = ziel_node.p_an
                n1d.t_prog += ziel_node.get("v_an", 0)
            except AttributeError:
                pass
            self.nodes.append(n1d)
            self.node_template = n1d

        if ziel_node.typ in {'H', 'E'}:
            n2d = EreignisGraphNode(
                quelle=self.quelle,
                typ='Ab',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                zeit=ziel_node.fid.zeit,
                plan=ziel_node.plan,
                plan_bst=ziel_node.plan_bst,
                gleis=ziel_node.gleis,
                gleis_bst=ziel_node.gleis_bst,
                s=0
            )
            try:
                n2d.t_prog = n2d.t_plan = ziel_node.p_ab
                n2d.t_prog += ziel_node.get("v_ab", 0)
            except AttributeError:
                try:
                    n2d.t_prog = n2d.t_plan = ziel_node.p_an
                    n2d.t_prog += ziel_node.get("v_an", 0)
                except AttributeError:
                    pass
            self.nodes.append(n2d)
            if self.node_template is None:
                self.node_template = n2d

        e2d = EreignisGraphEdge(
            quelle=self.quelle,
            typ='H',
            zid=ziel_node.zid,
            dt_min=ziel_node.get('mindestaufenthalt', 0),
            ds=0
        )
        self.edge_template = e2d
        if len(self.nodes) == 2:
            self.edges.append(e2d)

    def vorgang_einfuegen(self, node: EreignisGraphNode, edge: EreignisGraphEdge):
        """
        Hilfsknoten für Zugnummernänderung einfügen

        Hilfsknoten sind Zwischenknoten vom Typ E, K oder F.

        Der Knoten wird an Position 1 der nodes-Liste eingefügt, die Kante an Position 0.
        Aus der ursprünglichen Abfolge A -a-> B wird A -h-> H -a-> B.

        :param node: einzufügender Knoten
        :param edge: einzufügende Kanten zwischen Hilfs- und Abfahrtsknoten
        """
        self.nodes.insert(1, node)
        self.edges.insert(0, edge)

    def abfahrt_entfernen(self):
        """
        Abfahrtsknoten entfernen
        """
        try:
            if self.nodes[-1].typ == "Ab":
                self.nodes.pop(-1)
                self.edges.pop(-1)
        except IndexError:
            pass

    def ankunft_entfernen(self):
        """
        Ankunftsknoten entfernen
        """
        try:
            if self.nodes[0].typ == "An":
                self.nodes.pop(0)
                self.edges.pop(0)
        except IndexError:
            pass

    def abfahrt_verbinden(self, node: EreignisGraphNode, edge: EreignisGraphEdge):
        """
        Abfahrtsknoten mit Knoten von anderem Zug verbinden
        """
        if self.nodes[-1].typ == "Ab":
            self.nodes.insert(-1, node)
            self.edges.append(edge)

    def kuppeln(self, node: EreignisGraphNode):
        """
        Kupplungsknoten einfügen

        Ein Zug kann das Ziel mehrerer Kupplungsvorgänge sein.
        Die Kupplungsknoten werden gesammelt und erst in der add_to_graph-Methode aufgelöst.

        :param node: Kupplungsknoten (EreignisGraphNode mit Typ "K")
        """
        self.kupplungen.append(node)

    def add_to_graph(self):
        """
        Knoten und Kanten einem Ereignisgraphen hinzufügen.

        Die Methode hat nur beim ersten Aufruf eine Wirkung.

        Wenn bereits Ereignisknoten gleichen Typs zum ursprünglichen Zielknoten existieren, werden diese beibehalten.
        Die nodes und edges-Listen werden ggf. mit den effektiven Daten aktualisiert.
        """

        if self.ausgefuehrt:
            return None
        if not self.nodes:
            logger.debug(f"ZielEreignisNodeBuilder.add_to_graph(zid={self.zid}, fid={self.fid}): keine Nodes.")
            return

        for kupplung in sorted(self.kupplungen, key=lambda n: n.t_plan):
            self.nodes.insert(-1, kupplung)
            edge = EreignisGraphEdge(
                quelle=self.quelle,
                typ='H',
                zid=kupplung.zid,
                dt_min=0,
                ds=0)
            self.edges.append(edge)

        final_nodes = []
        for node in self.nodes:
            try:
                nid = self.graph.zug_ereignis_suchen(node.zid, fid=node.fid, typ=node.typ)
                final_node = self.graph.nodes[nid]
                final_node.gleis = node.gleis
                try:
                    final_node.t_prog = node.t_prog
                except AttributeError:
                    pass
            except (KeyError, ValueError):
                nid = node.node_id
                final_node = node
                self.graph.add_node(nid)
                self.graph.nodes[nid].update(node)
                self.graph.zuege.add(node.zid)
            final_nodes.append(final_node)
        self.nodes = final_nodes

        final_edges = []
        for n1d, n2d, edge in zip(self.nodes[:-1], self.nodes[1:], self.edges):
            n1 = n1d.node_id
            n2 = n2d.node_id
            try:
                final_edge = self.graph.edges[(n1, n2)]
            except KeyError:
                self.graph.add_edge(n1, n2)
                self.graph.edges[(n1, n2)].update(edge)
                final_edge = edge
            final_edges.append(final_edge)
        self.edges = final_edges

        self.ausgefuehrt = True


class EreignisEdgeBuilder(metaclass=ABCMeta):
    """
    Abstrakter Ersteller von Ereignisblöcken basierend auf Kanten

    Ein EreignisEdgeBuilder erstellt auf Abruf Blöcke (oder Subgraphen) mit Knoten und Kanten in einem EreignisGraph.
    Die Struktur dieser Blöcke wird durch die abgeleitete Klasse definiert.
    Bevor die add_to_graph-Methode aufgerufen wird, kann der Builder Informationen zum Aufbau des Blocks erhalten.
    Erst mittels add_to_graph werden die Knoten und Kanten in den Graphen geschrieben.

    Der EreignisEdgeBuilder wird eingesetzt, wo im ursprünglichen Graphen eine Kante übersetzt wird.
    Der EreignisNodeBuilder wird eingesetzt, wo im ursprünglichen Graphen ein Knoten übersetzt wird.

    EreignisEdgeBuild können Zugriff auf bereits erstellte EreignisNodeBuilder haben und diese modifizieren.

    Builder werden nur einmal ausgeführt und dürfen bei weiteren Aufrufen keine weiteren Elemente hinzufügen.
    """
    def __init__(self, graph: EreignisGraph):
        self.graph = graph
        self.quelle: str = 'sts'
        self.ausgefuehrt = False

    @abstractmethod
    def add_to_graph(self):
        """
        Knoten und Kanten zum Ereignisgraphen hinzufügen.

        Die Methode fügt die vom Builder verantworteten Knoten und internen Kanten dem EreignisGraph hinzu.
        Die Methode darf nur beim ersten Aufruf eine Wirkung zeigen.
        """
        self.ausgefuehrt = True


class ZielEreignisEdgeBuilder(EreignisEdgeBuilder):
    """
    Zwischenklasse zur für Builder, die Zielgraph-Kanten übersetzen.

    Diese Zwischenklasse speichert die zu einer Kante gehörenden EreignisNodeBuilder.
    Diese werden in allen abgeleiteten Klassen benötigt.
    """

    def __init__(self, graph: EreignisGraph):
        super().__init__(graph)
        self.node1_builder: Optional[ZielEreignisNodeBuilder] = None
        self.node2_builder: Optional[ZielEreignisNodeBuilder] = None
        self.edges: List[EreignisGraphEdge] = []

    def set_edge(self, node1_builder: EreignisNodeBuilder, node2_builder: EreignisNodeBuilder):
        self.node1_builder = node1_builder
        self.node2_builder = node2_builder


class PlanfahrtEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Builder für eine Planfahrt (normale Fahrt auf Strecke)

    Die Planfahrt erstellt eine Kante zwischen dem Abfahrtsereignis des ersten Ziels
    und dem Ankunftsereignis des zweiten Ziels.
    """

    def set_edge(self, node1_builder: ZielEreignisNodeBuilder, node2_builder: ZielEreignisNodeBuilder):
        super().set_edge(node1_builder, node2_builder)

        try:
            edge = EreignisGraphEdge(
                quelle=self.quelle,
                typ='P',
                zid=node1_builder.nodes[-1].zid,
                dt_min=node2_builder.nodes[0].t_plan - node1_builder.nodes[-1].t_plan,
            )
        except IndexError:
            logger.debug(f"PlanfahrtEdgeBuilder.set_edge(): keine Nodes")
        else:
            self.edges.append(edge)

    def add_to_graph(self):
        if self.ausgefuehrt:
            return

        try:
            n1 = self.node1_builder.last_label()
            n2 = self.node2_builder.first_label()
        except IndexError:
            pass
        else:
            if not self.graph.has_edge(n1, n2):
                self.graph.add_edge(n1, n2)
                self.graph.edges[(n1, n2)].update(self.edges[0])

        self.ausgefuehrt = True


class ErsatzEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Builder für einen Ersatzvorgang (E-Flag).

    Der Builder erstellt ein Ersatzereignis (Typ 'E') zwischen der Ankunft am ersten Ziel
    und der Abfahrt am zweiten Ziel.
    """

    def set_edge(self, node1_builder: ZielEreignisNodeBuilder, node2_builder: ZielEreignisNodeBuilder):
        """
        Ersatzvorgang darstellen

        Die Kante 1 -E-> 2 aus dem Zielgraph wird auf 3 Knoten und 2 Kanten abgebildet:
        An1 -E-> E -H-: Ab2

        Dazu wird in node1_builder der Abfahrtsknoten entfernt und ein E-Hilfsknoten angefügt.

        Der Zeitpunkt des Ersatzvorgangs entspricht der Abfahrtszeit von Zug 2.
        """

        super().set_edge(node1_builder, node2_builder)

        node = self.node1_builder.new_node(typ='E')
        node.t_plan = self.node2_builder.nodes[-1].t_plan
        edge = self.node1_builder.new_edge(typ='E')
        self.node1_builder.vorgang_einfuegen(node, edge)
        self.node1_builder.abfahrt_entfernen()

        edge = self.node2_builder.new_edge(typ='H', dt_min=0)
        self.node2_builder.abfahrt_verbinden(node, edge)
        self.node2_builder.ankunft_entfernen()

    def add_to_graph(self):
        """
        Keine Wirkung

        Alle Graphelemente werden durch die NodeBuilder erstellt.
        """


class KupplungEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Builder für einen Kupplungsvorgang (K-Flag).

    Der Builder erstellt ein Kupplungsereignis (Typ 'K') zwischen den Ankünften der zwei Züge
    (gegeben durch Anfangs- und Endpunkt der Kante im Zielgraph)
    und der Abfahrt des gekuppelten Zuges (gegeben durch den Endpunkt der Zielkante).
    """

    def set_edge(self, node1_builder: ZielEreignisNodeBuilder, node2_builder: ZielEreignisNodeBuilder):
        """
        Kupplungsvorgang darstellen

        An1 -K-> K, An2 -H-> K -H-> Ab2

        Der Kupplungszeitpunkt (Planzeit des K-Knotens) entspricht der letzten Ankunftszeit plus Minimalaufenthalt
        der einlaufenden Züge.

        Der Kupplungsknoten hat die zid des durchgehenden Zugs (2).
        """

        super().set_edge(node1_builder, node2_builder)

        node = self.node2_builder.new_node(typ='K')
        p1 = self.node1_builder.nodes[0].t_plan
        try:
            p1 += self.node1_builder.edges[0].dt_min
        except IndexError:
            pass
        p2 = self.node2_builder.nodes[0].t_plan
        try:
            p2 += self.node2_builder.edges[0].dt_min
        except IndexError:
            pass
        node.t_plan = max(p1, p2)

        edge = self.node1_builder.new_edge(typ='K')

        self.node1_builder.vorgang_einfuegen(node, edge)
        self.node1_builder.abfahrt_entfernen()
        self.node2_builder.kuppeln(node)

    def add_to_graph(self):
        """
        Keine Wirkung

        Alle Graphelemente werden durch die NodeBuilder erstellt.
        """
        pass


class FluegelungEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Builder für einen Flügelungsvorgang (F-Flag).

    Der Builder erstellt ein Flügelungsereignis (Typ 'F') zwischen der Ankunft des ersten Zuges
    und den Abfahrten der geflügelten Züge.
    """

    def set_edge(self, node1_builder: ZielEreignisNodeBuilder, node2_builder: ZielEreignisNodeBuilder):
        """
        Flügelungsvorgang darstellen

        An1 -F-> F -H-> Ab1, F -H-> Ab2

        Der Flügelungszeitpunkt entspricht der Ankunftszeit plus Minimalaufenthaltszeit.
        """
        super().set_edge(node1_builder, node2_builder)

        node = self.node1_builder.new_node(typ='F')
        node.t_plan = self.node1_builder.nodes[0].t_plan
        try:
            node.t_plan += self.node1_builder.edges[0].dt_min
        except IndexError:
            pass

        edge1 = self.node1_builder.new_edge(typ='F')

        self.node1_builder.vorgang_einfuegen(node, edge1)
        self.node1_builder.edges[-1].dt_min = 0

        edge2 = self.node2_builder.new_edge(typ='H', dt_min=0)

        self.node2_builder.abfahrt_verbinden(node, edge2)
        self.node2_builder.ankunft_entfernen()

    def add_to_graph(self):
        """
        Keine Wirkung

        Alle Graphelemente werden durch die NodeBuilder erstellt.
        """
        pass
