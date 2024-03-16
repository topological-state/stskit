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
from stskit.graphs.bahnhofgraph import BahnhofLabelType
from stskit.graphs.zielgraph import ZielGraph, ZielGraphNode, ZielGraphEdge, ZielLabelType

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
    fid = dict_property("fid", ZielLabelType,
                        docstring="""
                            Fahrplanziel-ID bestehend aus Zug-ID, Ankunfts- oder Abfahrtszeit in Minuten, Plangleis.
                            Dies ist das Nodelabel im Zielgraph.
                            Siehe stsobj.FahrplanZeile.fid.
                            Bei Ein- und Ausfahrten wird statt dem Gleiseintrag die Elementnummer (enr) eingesetzt,
                            und die Zeitkomponente ist MIN_MINUTES (Einfahrt) oder MAX_MINUTES (Ausfahrt).
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
    plan = dict_property("plan", str,
                         docstring="Gleis- oder Anschlussname nach Fahrplan.")
    gleis = dict_property("gleis", str,
                          docstring="Gleis- oder Anschlussname nach aktueller Disposition.")
    fix = dict_property("fix", bool, "True = Zeit t ist festgelegt")
    p = dict_property("p", float, "Fahrplanzeit in Minuten")
    t = dict_property("t", float, "Geschätzte oder erfolgte Uhrzeit in Minuten")
    s = dict_property("s", float, "Ort in Minuten")

    bst = dict_property("bst", BahnhofLabelType)
    farbe = dict_property("farbe", str)
    marker = dict_property("marker", str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._id = next(self.auto_inc)

    def __copy__(self) -> 'EreignisGraphNode':
        """
        Objekt kopieren, mit neuer ID
        """
        new = self.__class__()
        new.update(self)
        new._id = next(self.auto_inc)
        return new

    @property
    def node_id(self) -> EreignisLabelType:
        """
        Identifikation des Ereignisses.

        Die ID besteht aus der Zugnummer und einer beliebigen Nummer zur Unterscheidung.
        Der erste Knoten eines Zuges erhält die ID (zid, 0), damit der Anfang eines Zuges schnell gefunden werden kann.
        Bei allen anderen Knoten hat die zweite Komponente keine Bedeutung, nicht mal in Bezug auf eine Reihenfolge.
        """
        return self.zid, self._id


class EreignisGraphEdge(dict):
    zid = dict_property("zid", int)
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
        Der Anfangsknoten eines Zuges hat jeweils das Label (zid, 0).
        Der Pfad eines Zuges (geordnete Abfolge von Knoten mit derselben Zug-ID)
        wird vom Generator zugpfad angegeben.
    """
    node_attr_dict_factory = EreignisGraphNode
    edge_attr_dict_factory = EreignisGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.zuege: Set[int] = set()

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
        """

        self.clear()
        self.zuege = set()

        node_builders = {}
        for zg1, zg1_data in zg.nodes(data=True):
            builder = ZielEreignisNodeBuilder()
            builder.import_ziel(zg, zg1_data)
            node_builders[zg1] = builder

        edge_builders = {}
        for zg1, zg2, zge_data in zg.edges(data=True):
            builder = None

            if zge_data.typ == 'P':
                builder = PlanfahrtEdgeBuilder()
            elif zge_data.typ == 'E':
                builder = ErsatzEdgeBuilder()
            elif zge_data.typ == 'F':
                builder = FluegelungEdgeBuilder()
            elif zge_data.typ == 'K':
                builder = KupplungEdgeBuilder()
            else:
                logger.warning(f"Unbekannter Zielkantentyp {zge_data.typ}")

            if builder is not None:
                builder.set_edge(node_builders[zg1], node_builders[zg2])
                edge_builders[(zg1, zg2)] = builder

        for builder in node_builders.values():
            builder.add_to_graph(self)
        for builder in edge_builders.values():
            builder.add_to_graph(self)

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

        nodes = nx.topological_sort(self)

        for zielnode in nodes:
            ziel_data = self.nodes[zielnode]
            if ziel_data.fix:
                continue

            zeit_min = -math.inf
            zeit_max = math.inf
            for startnode in self.pred[zielnode]:
                start_data = self.nodes[startnode]
                edge = (startnode, zielnode)
                edge_data = self.edges[edge]
                try:
                    start_zeit = start_data.t
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

            ziel_zeit = -math.inf
            if ziel_data.typ in {'Ab'}:
                try:
                    ziel_zeit = ziel_data.p
                except (AttributeError, KeyError):
                    pass

            ziel_zeit = min(ziel_zeit, zeit_max)
            ziel_zeit = max(ziel_zeit, zeit_min)
            if not math.isinf(ziel_zeit):
                ziel_data.t = ziel_zeit
            else:
                logger.warning(f"Keine Zeitprognose möglich für Ereignis {zielnode}")

    def verspaetungen_nach_zielgraph(self, zg: ZielGraph):
        """
        Schreibt die berechneten Verspätungen in den Zielgraphen.

        Die Verspätungen werden aus der Differenz zwischen den t- und p-Feldern der An- und Ab-Knoten berechnet.
        Es werden nur die noch nicht erreichten Ziele aktualisiert.

        :param zg: Zielgraph
        """

        for ereignis_node, ereignis_data in self.nodes(data=True):
            try:
                ziel_data = zg.nodes[ereignis_data.fid]
            except (AttributeError, KeyError):
                continue

            try:
                v = ereignis_data.t - ereignis_data.p
            except AttributeError:
                logger.warning(f"Unvollständige Zeitinformation für Verspätungsberechnung: {ereignis_data}")
                return

            if ereignis_data.typ == 'Ab':
                if ziel_data.status == '' or ziel_data.status == 'an':
                    ziel_data.v_ab = v
            elif ereignis_data.typ == 'An':
                if ziel_data.status == '':
                    ziel_data.v_an = v


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
    def __init__(self):
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
    def add_to_graph(self, ereignis_graph: EreignisGraph):
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

    def __init__(self):
        super().__init__()
        self.zuganfang = False
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

        Wenn der ziel_node der erste des Zuges ist, wird zuganfang auf True gesetzt,
        damit in add_to_graph das Label des ersten Knotens mit (zid, 0) markiert werden kann.
        """

        self.zuganfang = False
        for p in ziel_graph.predecessors(ziel_node.fid):
            if ziel_graph.nodes[p].zid == ziel_node.zid:
                break
        else:
            self.zuganfang = True

        if ziel_node.typ in {'H', 'D', 'A'}:
            n1d = EreignisGraphNode(
                typ='An',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                plan=ziel_node.plan,
                gleis=ziel_node.gleis,
                fix=ziel_node.status in {"an", "ab"},
                s=0
            )
            try:
                n1d.p = ziel_node.p_an
                n1d.t = ziel_node.p_an + ziel_node.v_an
            except AttributeError:
                pass
            self.nodes.append(n1d)
            self.node_template = n1d

        if ziel_node.typ in {'H', 'E'}:
            n2d = EreignisGraphNode(
                typ='Ab',
                zid=ziel_node.zid,
                fid=ziel_node.fid,
                plan=ziel_node.plan,
                gleis=ziel_node.gleis,
                fix=ziel_node.status in {"ab"},
                s=0
            )
            try:
                n2d.p = ziel_node.p_ab
                n2d.t = ziel_node.p_ab + ziel_node.v_ab
            except AttributeError:
                pass
            self.nodes.append(n2d)
            if self.node_template is None:
                self.node_template = n2d

        if len(self.nodes) == 2:
            e2d = EreignisGraphEdge(
                typ='H',
                zid=ziel_node.zid,
                dt_min=ziel_node.mindestaufenthalt,
                ds=0
            )
            self.edges.append(e2d)
            self.edge_template = e2d

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

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Knoten und Kanten einem Ereignisgraphen hinzufügen.

        Die Methode hat nur beim ersten Aufruf eine Wirkung.
        """
        if self.ausgefuehrt:
            return None

        for kupplung in sorted(self.kupplungen, key=lambda n: n.p):
            self.nodes.insert(-1, kupplung)
            edge = EreignisGraphEdge(
                typ='H',
                zid=kupplung[0],
                dt_min=0,
                ds=0)
            self.edges.append(edge)

        zid_anfang = self.nodes[-1].zid if self.zuganfang else None
        for node in self.nodes:
            if node.zid == zid_anfang:
                node._id = 0
                zid_anfang = None
            nid = node.node_id
            ereignis_graph.add_node(nid)
            ereignis_graph.nodes[nid].update(node)
            ereignis_graph.zuege.add(node.zid)

        for n1d, n2d, edge in zip(self.nodes[:-1], self.nodes[1:], self.edges):
            n1 = n1d.node_id
            n2 = n2d.node_id
            ereignis_graph.add_edge(n1, n2)
            ereignis_graph.edges[(n1, n2)].update(edge)

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
    def __init__(self):
        self.ausgefuehrt = False

    @abstractmethod
    def add_to_graph(self, ereignis_graph: EreignisGraph):
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

    def __init__(self):
        super().__init__()
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

        edge = EreignisGraphEdge(
            typ='P',
            zid=node1_builder.nodes[-1].zid,
            dt_min=node2_builder.nodes[0].p - node1_builder.nodes[-1].p,
        )
        self.edges.append(edge)

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        if self.ausgefuehrt:
            return

        n1 = self.node1_builder.last_label()
        n2 = self.node2_builder.first_label()
        ereignis_graph.add_edge(n1, n2)
        ereignis_graph.edges[(n1, n2)].update(self.edges[0])

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
        node.p = self.node2_builder.nodes[-1].p
        edge = self.node1_builder.new_edge(typ='E')
        self.node1_builder.vorgang_einfuegen(node, edge)
        self.node1_builder.abfahrt_entfernen()

        edge = self.node2_builder.new_edge(typ='H', dt_min=0)
        self.node2_builder.abfahrt_verbinden(node, edge)
        self.node2_builder.ankunft_entfernen()

    def add_to_graph(self, ereignis_graph: EreignisGraph):
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

        Der Kupplungszeitpunkt (p-Zeit des K-Knotens) entspricht der letzten Ankunftszeit plus Minimalaufenthalt
        der einlaufenden Züge.

        Der Kupplungsknoten hat die zid des durchgehenden Zugs (2).
        """

        super().set_edge(node1_builder, node2_builder)

        node = self.node2_builder.new_node(typ='K')
        p1 = self.node1_builder.nodes[0].p
        try:
            p1 += self.node1_builder.edges[0].dt_min
        except IndexError:
            pass
        p2 = self.node2_builder.nodes[0].p
        try:
            p2 += self.node2_builder.edges[0].dt_min
        except IndexError:
            pass
        node.p = max(p1, p2)

        edge = self.node1_builder.new_edge(typ='K')

        self.node1_builder.vorgang_einfuegen(node, edge)
        self.node1_builder.abfahrt_entfernen()
        self.node2_builder.kuppeln(node)

    def add_to_graph(self, ereignis_graph: EreignisGraph):
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
        node.p = self.node1_builder.nodes[0].p
        try:
            node.p += self.node1_builder.edges[0].dt_min
        except IndexError:
            pass

        edge1 = self.node1_builder.new_edge(typ='F')

        self.node1_builder.vorgang_einfuegen(node, edge1)
        self.node1_builder.edges[-1].dt_min = 0

        edge2 = self.node2_builder.new_edge(typ='H', dt_min=0)

        self.node2_builder.abfahrt_verbinden(node, edge2)
        self.node2_builder.ankunft_entfernen()

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        """
        Keine Wirkung

        Alle Graphelemente werden durch die NodeBuilder erstellt.
        """
        pass


class AbfahrtAbwartenEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass


class AnkunftAbwartenEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass


class KreuzungEdgeBuilder(ZielEreignisEdgeBuilder):
    """
    Nicht verwendet.
    """

    def add_to_graph(self, ereignis_graph: EreignisGraph):
        pass
