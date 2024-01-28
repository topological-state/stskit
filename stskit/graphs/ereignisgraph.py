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
import datetime
import itertools
import logging
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.graphs.zielgraph import ZielGraph, ZielGraphNode, ZielGraphEdge

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


EreignisLabelType = Tuple[int, int]


class EreignisGraphNode(dict):
    """
    EreignisGraphNode

    Die Node-ID besteht aus Zug-ID und einer beliebigen Nummer.
    Der Startpunkt jedes Zuges erhält die ID (zid, 0), so dass der Zug einfach gefunden werden kann.
    """
    auto_inc = itertools.count(1)

    zid = dict_property("zid", int, docstring="Zug-ID")
    fid = dict_property("fid", Tuple[int, Optional[datetime.time], Optional[datetime.time], Union[int, str]],
                        docstring="""
                            Fahrplanziel-ID bestehend aus Zug-ID, Ankunftszeit, Abfahrtszeit, Plangleis. 
                            Siehe stsobj.FahrplanZeile.fid.
                            Bei Ein- und Ausfahrten wird statt dem Gleiseintrag die Elementnummer (enr) eingesetzt.
                            """)
    typ = dict_property("typ", str,
                        docstring="""
                            Vorgang:
                                'An': Ankunft,
                                'Ab': Abfahrt,
                                'E': Ersatz,
                                'F': Flügelung,
                                'K': Kupplung,
                                '+': Zuganfang,
                                '-': Zugende.
                            """)
    passiert = dict_property("passiert", bool, "True = Ereignis in Vergangenheit, Zeit t ist festgelegt")
    p = dict_property("p", float, "Fahrplanzeit in Minuten")
    t = dict_property("t", float, "Geschätzte oder erfolgte Uhrzeit in Minuten")
    s = dict_property("s", float, "Ort in Minuten")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._id = next(self.auto_inc)

    def node_id(self) -> EreignisLabelType:
        """
        Identifikation des Ereignisses.

        Die ID besteht aus der Zugnummer und einer beliebigen Nummer zur Unterscheidung.
        Der erste Knoten eines Zuges erhält die ID (zid, 0), damit der Anfang eines Zuges schnell gefunden werden kann.
        Bei allen anderen Knoten hat die zweite Komponente keine Bedeutung, nicht mal in Bezug auf eine Reihenfolge.
        """
        return self.zid, self._id


class EreignisGraphEdge(dict):
    typ = dict_property("typ", str,
                        docstring="""
                            Verbindungstyp:
                                'P': planmässige Fahrt,
                                'H': Halt,
                                'E': Ersatz (Kante von E-Flag nach E-Knoten),
                                'F': Flügelung (Kante von F-Flag nach F-Knoten),
                                'K': Kupplung (Kante von K-Flag nach K-Knoten),
                                'R': vom Fdl angeordnete Rangierfahrt, z.B. bei Lokwechsel,
                                'A': vom Fdl angeordnete Abhängigkeit,
                                'O': Hilfskante für Sortierordnung.
                            """)
    dt_min = dict_property("dt_min", float, "Minimale Dauer in Minuten")
    dt_max = dict_property("dt_max", float, "Maximale Dauer in Minuten")
    # dt = dict_property("dt", float, "Effektive Dauer in Minuten")
    ds = dict_property("ds", float, "Strecke in Minuten")


class EreignisGraph(nx.DiGraph):
    """
    Zeitliche Abfolge von Ereignissen

    Der Ereignisgraph dient zur Protokollierung von vergangenen Ereignissen
    und zur Abschätzung des Zeitpunkts von zukünftigen Ereignissen.
    Der Graph ist darauf ausgelegt, dass die Prognose mittels eines einfachen Traverse-Algorithmus berechnet werden kann.

    Der EreignisGraph ist ein gerichteter Graph, der die einzelnen Betriebsereignisse und ihre Abfolge kodiert.
    Die Knoten sind Ereignisse wie Ankunft, Abfahrt, usw.
    Die Kanten definieren die Abfolge von Ereignissen und den zeitlichen Abstand.

    Konzeptuell wichtig ist, dass ein Ereignis keine Zeitdauer hat.
    Ein Aufenthalt muss daher mit zwei Knoten (Ankunft und Abfahrt) und einer Kante zwischen ihnen dargestellt werden.

    Der EreignisGraph ist gerichtet.
    """
    node_attr_dict_factory = EreignisGraphNode
    edge_attr_dict_factory = EreignisGraphEdge

    def to_undirected_class(self):
        return EreignisGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def zugpfad(self, zid: int) -> Iterable[EreignisLabelType]:
        """
        Generator für die Knoten eines Zuges
        
        Beginnend mit dem Startknoten liefert der Generator die Knoten-IDs eines Zuges
        in der Reihenfolge ihres Auftretens.
        """

        node = (zid, 0)
        while node is not None:
            yield node

            for n in self.successors(node):
                if n[0] == zid:
                    node = n
                    break
            else:
                node = None

    def _zugstart_markieren(self):
        """
        Startknoten jedes Zuges markieren

        Der Startknoten eines Zuges hat die Form (zid, 0).
        Dies ist unabhängig davon, ob der Startknoten aus einer Einfahrt, Startaufstellung oder
        einem anderen Zug hervorgeht.
        """

        mapping = {}
        for node in self.nodes:
            for p in self.predecessors(node):
                if p[0] == node[0]:
                    break
            else:
                mapping[node] = (node[0], 0)

        nx.relabel_nodes(self, mapping, copy=False)

    def zielgraph_importieren(self, zg: ZielGraph):
        """
        Zielgraph importieren

        Der Ereignisgraph wird anhand eines vollständigen Zielgraphs aufgebaut.

        Fahrplanhalte werden in Ankunfts- und Abfahrtsereignisse aufgelöst,
        Betriebsvorgänge werden in entsprechende graphische Muster übersetzt.

        Die Methode arbeitet mit EreignisNodeFactories.
        In einem ersten Schritt werden alle Zielknoten in ZielEreignisNodeFactories übersetzt.
        Im zweiten Schritt werden die Zielkanten in ZielEreignisEdgeFactories übersetzt und ausgeführt.
        Bei der Ausführung der Factories werden die Zielelemente dem Ereignisgraphen hinzugefügt.

        Die gestaffelte Übersetzung von Knoten und Kanten in Factories bietet die notwendige Flexibilität
        in den folgenden Situationen:
        - Es gibt keine eindeutige Zuordnung von Zielknoten zu Ereignisknoten,
          jedoch im Verlauf dieser Methode eine Zuordnung von Zielknoten zu ZielEreignisNodeFactories.
        - Die Labels von Ereignisknoten können nicht aus Zielknoten abgeleitet werden.
          Es wird eine fortlaufende Nummer eingesetzt.
          Lediglich der erste Ereignisknoten eines Zuges wird mit der Nummer 0 markiert.
        - Zielpunkte im Zielgraph ergeben je nach Typ eines oder zwei Ereignisse.
        - Betriebsvorgänge sind im Zielgraph im Kantentyp dargestellt, im Ereignisgraph durch die Topologie.
        - Beim Iterieren über Kanten kommen Knoten mehrmals vor.
          Knoten dürfen aber nur einmal in den Graphen eingesetzt werden,
          weil es keine eindeutige Zuordnung von Zielknoten zu Ereignisknoten gibt.
        """

        node_factories = {}
        for zg1, zg1_data in zg.nodes(data=True):
            factory = ZielEreignisNodeFactory()
            factory.import_ziel(zg, zg1_data)
            node_factories[zg1] = factory

        edge_factories = {}
        for zg1, zg2, zge_data in zg.edges(data=True):
            factory = None

            if zge_data.typ == 'P':
                factory = PlanfahrtFactory()
            elif zge_data.typ == 'E':
                factory = ErsatzFactory()
            elif zge_data.typ == 'F':
                factory = FluegelungFactory()
            elif zge_data.typ == 'K':
                factory = KupplungFactory()
            else:
                logger.warning(f"Unbekannter Zielkantentyp {zge_data.typ}")

            if factory is not None:
                factory.set_edge(node_factories[zg1], node_factories[zg2])
                edge_factories[(zg1, zg2)] = factory

        for factory in node_factories.values():
            factory.add_to_graph(self)
        for factory in edge_factories.values():
            factory.add_to_graph(self)

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

        # todo : zyklen auflösen
        nodes = nx.topological_sort(self)

        for zielnode in nodes:
            ziel_data = self.nodes[zielnode]
            if ziel_data.passiert:
                continue

            zeit_min = -math.inf
            zeit_max = math.inf
            for startnode, start_data in self.pred[zielnode]:
                edge = (startnode, zielnode)
                edge_data = self.edges[edge]
                try:
                    start_zeit = start_data.p
                except (AttributeError, KeyError):
                    continue
                try:
                    zeit_min = max(zeit_min, start_zeit + edge_data.dt_min)
                except (AttributeError, KeyError):
                    pass
                try:
                    zeit_max = min(zeit_max, start_zeit + edge_data.dt_max)
                except (AttributeError, KeyError):
                    pass

            try:
                ziel_zeit = ziel_data.p
            except (AttributeError, KeyError):
                ziel_zeit = math.inf

            ziel_zeit = min(ziel_zeit, zeit_max)
            ziel_zeit = max(ziel_zeit, zeit_min)
            if not math.isinf(ziel_zeit):
                ziel_data.t = ziel_zeit
            else:
                logger.warning(f"Keine Zeitprognose möglich für Ereignis {zielnode}")


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


class EreignisNodeFactory(metaclass=ABCMeta):
    """
    Abstrakte Node Factory

    Eine EreignisNodeFactory muss die abstrakten Methoden implementieren,
    die einem Ereignisgraphen die der Klasse entsprechenden Knoten und Kanten hinzufügt.

    Factories werden nur einmal ausgeführt und dürfen bei weiteren Aufrufen keine weiteren Elemente hinzufügen.
    """
    def __init__(self):
        self.ausgefuehrt = False

    @abstractmethod
    def first_label(self) -> EreignisLabelType:
        """
        Label des ersten von der Factory erstellten Ereignisses.

        Das Ereignislabel wird von einlaufenden Kanten referenziert.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """
        return None

    @abstractmethod
    def last_label(self) -> EreignisLabelType:
        """
        Label des letzten von der Factory erstellten Ereignisses.

        Das Ereignislabel wird von auslaufenden Kanten referenziert.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """
        return None

    @abstractmethod
    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Knoten und Kanten zum Ereignisgraphen hinzufügen.

        Die Methode fügt die von einer Factory verwalteten Knoten und internen Kanten dem Ereignisgraphen hinzu.
        Die Methode darf nur beim ersten Aufruf eine Wirkung zeigen.
        """
        self.ausgefuehrt = True


class ZielEreignisNodeFactory(EreignisNodeFactory):
    """
    Zielgraph-Node in Ereignisgraph-Node übersetzen.

    Diese Factory übersetzt alle aktuell definierten Zielgraphknoten in Ereignisknoten und -kanten.
    Bei Ein- und Ausfahrten wird ein Knoten erstellt,
    bei Planhalten und Durchfahrten ein Ankunfts- und ein Abfahrtsknoten mit Verbindungskante.

    Die Knoten- und Kantenattribute werden in der import_ziel-Methode entsprechend den Zielattributen gesetzt.
    Die Knotenlabels sind zu diesem Zeitpunkt noch nicht definitiv!
    """

    def __init__(self):
        super().__init__()
        self.zuganfang = False
        self.nodes: List[EreignisGraphNode] = []
        self.edges: List[EreignisGraphEdge] = []

    def first_label(self) -> EreignisLabelType:
        """
        Label des ersten von der Factory erstellten Ereignisses.

        Dies ist das Label von n1d oder n2d.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """

        return self.nodes[0].node_id()

    def last_label(self) -> EreignisLabelType:
        """
        Label des letzten von der Factory erstellten Ereignisses.

        Dies ist das Label von n2d oder n1d.
        Das Label ist erst nach Ausführen der add_to_graph-Methode gültig!
        """

        return self.nodes[-1].node_id()

    def import_ziel(self, ziel_graph: ZielGraph, ziel_node: ZielGraphNode):
        """
        Daten von Zielnode in Factory übernehmen.
        """
        self.zuganfang = False
        for p in ziel_graph.predecessors(ziel_node.fid):
            if ziel_graph.nodes[p].zid == ziel_node.zid:
                break
        else:
            self.zuganfang = True

        if ziel_node.typ != 'E':
            n1d = EreignisGraphNode(
                typ='An',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                passiert=ziel_node.status in {"an", "ab"},
                s=0
            )
            try:
                n1d.p = ziel_node.p_an
                n1d.t = ziel_node.p_an + ziel_node.v_an
            except AttributeError:
                pass
            self.nodes.append(n1d)

        if ziel_node.typ != 'A':
            n2d = EreignisGraphNode(
                typ='Ab',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                passiert=ziel_node.status in {"ab"},
                s=0
            )
            try:
                n2d.p = ziel_node.p_ab
                n2d.t = ziel_node.p_ab + ziel_node.v_ab
            except AttributeError:
                pass
            self.nodes.append(n2d)

        if len(self.nodes) == 2:
            e2d = EreignisGraphEdge(
                typ='H',
                dt_min=ziel_node.mindestaufenthalt,
                ds=0
            )
            self.edges.append(e2d)

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Knoten und Kanten einem Ereignisgraphen hinzufügen.

        Die Methode hat nur beim ersten Aufruf eine Wirkung.
        """
        if self.ausgefuehrt:
            return None

        if self.zuganfang:
            self.nodes[0]._id = 0

        for node in self.nodes:
            nid = node.node_id()
            ereignis_graph.add_node(nid)
            ereignis_graph.nodes[nid].update(node)

        for n1d, n2d, edge in zip(self.nodes[:-1], self.nodes[1:], self.edges):
            n1 = n1d.node_id()
            n2 = n2d.node_id()
            ereignis_graph.add_edge(n1, n2)
            ereignis_graph.edges[(n1, n2)].update(edge)

        self.ausgefuehrt = True


class EreignisEdgeFactory(metaclass=ABCMeta):
    """
    Abstrakte Edge Factory

    Eine EreignisEdgeFactory muss die abstrakten Methoden implementieren,
    die einem Ereignisgraphen die der Klasse entsprechenden Kanten hinzufügt.

    Factories werden nur einmal ausgeführt und dürfen bei weiteren Aufrufen keine weiteren Elemente hinzufügen.
    """
    def __init__(self):
        self.ausgefuehrt = False

    @abstractmethod
    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Knoten und Kanten zum Ereignisgraphen hinzufügen.

        Die Methode fügt die von einer Factory verwalteten Knoten und internen Kanten dem Ereignisgraphen hinzu.
        Die Methode darf nur beim ersten Aufruf eine Wirkung zeigen.
        """
        self.ausgefuehrt = True


class ZielEreignisEdgeFactory(EreignisEdgeFactory):
    """
    Zwischenklasse für Edge-Factories

    Diese Zwischenklasse speichert die zu einer Kante gehörenden EreignisNodeFactories.
    Diese werden in allen abgeleiteten Klassen benötigt.
    """

    def __init__(self):
        super().__init__()
        self.node1_factory: Optional[ZielEreignisNodeFactory] = None
        self.node2_factory: Optional[ZielEreignisNodeFactory] = None
        self.e1d: Optional[EreignisGraphEdge] = None
        self.e2d: Optional[EreignisGraphEdge] = None

    def set_edge(self, node1_factory: EreignisNodeFactory, node2_factory: EreignisNodeFactory):
        self.node1_factory = node1_factory
        self.node2_factory = node2_factory


class PlanfahrtFactory(ZielEreignisEdgeFactory):
    """
    Factory für eine Planfahrt (normale Fahrt auf Strecke)

    Die Planfahrt erstellt eine Kante zwischen dem Abfahrtsereignis des ersten Ziels
    und em Ankunftsereignis des zweiten Ziels.
    """

    def set_edge(self, node1_factory: EreignisNodeFactory, node2_factory: EreignisNodeFactory):
        super().set_edge(node1_factory, node2_factory)
        self.e1d = EreignisGraphEdge(
            typ='P',
            dt_min=0,
            ds=0
        )

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        if self.ausgefuehrt:
            return

        n1 = self.node1_factory.last_label()
        n2 = self.node2_factory.first_label()
        ereignis_graph.add_edge(n1, n2)
        ereignis_graph.edges[(n1, n2)].update(self.e1d)

        self.ausgefuehrt = True


class ErsatzFactory(ZielEreignisEdgeFactory):
    """
    Factory für einen Ersatzvorgang (E-Flag).

    Die Factory erstellt ein Ersatzereignis (Typ 'E') zwischen der Ankunft am ersten Ziel
    und der Abfahrt am zweiten Ziel.
    """

    def set_edge(self, node1_factory: EreignisNodeFactory, node2_factory: EreignisNodeFactory):
        super().set_edge(node1_factory, node2_factory)
        self.node1_factory.nodes[1].typ = 'E'
        self.node1_factory.nodes[1].p = self.node2_factory.nodes[1].p
        self.node1_factory.edges[0].typ = 'E'
        self.node2_factory.nodes.pop(0)
        self.node2_factory.edges.pop(0)

        self.e1d = EreignisGraphEdge(
            typ='H',
            dt_min=0,
            ds=0
        )

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Ersatzvorgang darstellen

        Die Knoten von Helper 1 werden beibehalten, wobei der zweite in Typ E umgewandelt wird.
        Von Helper 2 wird nur der Abfahrtsknoten behalten.
        Der Zeitpunkt des Ersatzvorgangs entspricht der Abfahrtszeit von Helper 2.

        Die Kante 1 -E-> 2 aus dem Zielgraph wird damit auf 3 Knoten und 2 Kanten abgebildet:
        An1 -E-> E -H-: Ab2
        """

        if self.ausgefuehrt:
            return

        n1 = self.node1_factory.last_label()
        n2 = self.node2_factory.first_label()
        ereignis_graph.add_edge(n1, n2)
        ereignis_graph.edges[(n1, n2)].update(self.e1d)

        self.ausgefuehrt = True


class KupplungFactory(ZielEreignisEdgeFactory):
    """
    Factory für einen Kupplungsvorgang (K-Flag).

    Die Factory erstellt ein Kupplungsereignis (Typ 'K') zwischen den Ankünften der zwei Züge
    (gegeben durch Anfangs- und Endpunkt der Kante im Zielgraph)
    und der Abfahrt des gekuppelten Zuges (gegeben durch den Endpunkt der Zielkante).
    """

    def set_edge(self, node1_factory: EreignisNodeFactory, node2_factory: EreignisNodeFactory):
        super().set_edge(node1_factory, node2_factory)

        self.e1d = EreignisGraphEdge(
            typ='H',
            dt_min=self.node2_factory.edges[0].dt_min,
            ds=0
        )

        self.e2d = EreignisGraphEdge(
            typ='H',
            dt_min=0,
            ds=0
        )

        self.node1_factory.nodes[1].typ = 'K'
        self.node1_factory.nodes[1].zid = self.node2_factory.nodes[0].zid
        self.node1_factory.nodes[1].p = max(self.node1_factory.nodes[0].p + self.node1_factory.edges[0].dt_min, self.node2_factory.nodes[0].p + self.node2_factory.edges[0].dt_min)
        self.node1_factory.edges[0].typ = 'K'
        self.node2_factory.edges.pop(0)

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Kupplungsvorgang darstellen

        An1 -K-> K, An2 -H-> K -H-> Ab2

        Der Kupplungszeitpunkt (p-Zeit des K-Knotens) entspricht der letzten Ankunftszeit plus Minimalaufenthalt
        der einlaufenden Züge.
        """

        if self.ausgefuehrt:
            return

        n1 = self.node2_factory.first_label()
        n2 = self.node1_factory.last_label()
        n3 = self.node2_factory.last_label()
        ereignis_graph.add_edge(n1, n2)
        ereignis_graph.edges[(n1, n2)].update(self.e1d)
        ereignis_graph.add_edge(n2, n3)
        ereignis_graph.edges[(n2, n3)].update(self.e2d)

        self.ausgefuehrt = True


class FluegelungFactory(ZielEreignisEdgeFactory):
    """
    Factory für einen Flügelungsvorgang (F-Flag).

    Die Factory erstellt ein Flügelungsereignis (Typ 'F') zwischen der Ankunft des ersten Zuges
    und den Abfahrten der geflügelten Züge.
    """

    def set_edge(self, node1_factory: EreignisNodeFactory, node2_factory: EreignisNodeFactory):
        super().set_edge(node1_factory, node2_factory)

        e1d = EreignisGraphEdge(
            typ='F',
            dt_min=self.node1_factory.edges[0].dt_min,
            ds=0
        )
        e2d = EreignisGraphEdge(
            typ='H',
            dt_min=0,
            ds=0
        )
        self.e1d = EreignisGraphEdge(
            typ='H',
            dt_min=0,
            ds=0
        )

        fnode = copy.copy(self.node1_factory.nodes[0])
        fnode.typ = 'F'
        fnode.p = self.node1_factory.nodes[0].p + self.node1_factory.edges[0].dt_min
        self.node1_factory.nodes.insert(1, fnode)
        self.node1_factory.edges = [e1d, e2d]
        node2 = self.node2_factory.nodes.pop(0)
        fnode._id = node2._id
        self.node2_factory.edges.pop(0)

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Flügelungsvorgang darstellen

        An1 -F-> F -H-> Ab1, F -H-> Ab2

        Der Flügelungszeitpunkt entspricht der Ankunftszeit plus Minimalaufenthaltszeit.
        """

        if self.ausgefuehrt:
            return

        n1 = self.node1_factory.nodes[1].node_id()
        n2 = self.node2_factory.first_label()
        ereignis_graph.add_edge(n1, n2)
        ereignis_graph.edges[(n1, n2)].update(self.e1d)

        self.ausgefuehrt = True


class AbfahrtAbwartenFactory(ZielEreignisEdgeFactory):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass


class AnkunftAbwartenFactory(ZielEreignisEdgeFactory):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass


class KreuzungFactory(ZielEreignisEdgeFactory):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass
