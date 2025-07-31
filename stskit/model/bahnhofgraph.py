import logging
import sys
from typing import Any, Callable, Dict, Generator, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.plugin.stsobj import AnlagenInfo, BahnsteigInfo, Knoten
from stskit.model.gleisschema import Gleisschema
from stskit.model.signalgraph import SignalGraph

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


BAHNHOFELEMENT_TYPEN = {'Gl', 'Bs', 'Bft', 'Bf', 'Agl', 'Anst', 'Bst', 'Stw'}
BAHNHOFELEMENT_HIERARCHIE = {'Gl': 'Bs', 'Bs': 'Bft', 'Bft': 'Bf', 'Bf': 'Bst', 'Agl': 'Anst', 'Anst': 'Bst', 'Bst': 'Stw'}

BAHNHOFELEMENT_BESCHREIBUNG = {'Gl': 'Gleis',
                               'Bs': 'Bahnsteig',
                               'Bft': 'Bahnhofteil',
                               'Bf': 'Bahnhof',
                               'Agl': 'Anschlussgleis',
                               'Anst': 'Anschlussstelle',
                               'Bst': 'Betriebsstelle',
                               'Stw': 'Stellwerk'}


class BahnhofElement(NamedTuple):
    """
    Vollständige Bahnhofelementbezeichnung (Typ und Name)

    Bahnhofelemente sind alle benannten Gleise, Bahnsteige, etc., die im Bahnhofgraph als Knoten vorkommen.
    Dazu gehören also in Erweiterung des üblichen Sprachgebrauchs ausdrücklich auch Anschlussgleise und Haltepunkte.

    Eine Bahnhofelementbezeichnung enthält den Typ und den Namen des Elements,
    die auch als Property im BahnsteigGraphNode vorkommen.
    Typ und Namen werden verwendet, weil Anschlussgleise und Bahnhofgleise den gleichen Namen tragen können.
    """
    typ: str
    name: str

    def __str__(self):
        """
        Benutzerfreundliche Bezeichnung, wird im UI verwendet.
        """
        return f"{self.typ} {self.name}"

    @classmethod
    def from_string(cls, s: str) -> 'BahnhofElement':
        """
        Bahnhofelement aus Stringdarstellung

        :raises: ValueError bei fehlerhaftem Format oder unbekanntem Elementtyp.
            Ueberprueft nicht, ob das Bahnhofelement in der Anlage existiert.
        """

        typ, name = s.split(" ", 1)
        if typ not in BAHNHOFELEMENT_TYPEN:
            raise ValueError(f"Unbekannter Bahnhofelementtyp {typ} in {s}")
        if not name:
            raise ValueError(f"Undefinierter Bahnhofelementname {name} in {s}")
        return BahnhofElement(typ, name)


class BahnsteigGraphNode(dict):
    """
    Klasse der Knotenattribute von BahnsteigGraph und BahnhofGraph
    """
    name = dict_property("name", str, docstring="Name")
    enr = dict_property("enr", int, docstring="Elementnummer bei Anschlussgleisen. Nur für Agl definiert.")
    typ = dict_property("typ", str, docstring="""
        'Gl': Gleis- oder Haltepunktbezeichnung, wie sie in den Fahrplänen vorkommt. Vom Sim deklariert. 
        'Bs': Bahnsteigbezeichnung, fasst Gleissektoren bzw. Haltepunkte zusammen.
        'Bft': Bahnhofteil, fasst Bahnsteige zusammen, auf die ein Zug umdisponiert werden kann.
        'Bf': Bahnhof für grafische Darstellung und Fahrzeitauswertung.
        'Agl': Anschluss- oder Übergabegleis. Vom Sim deklariert.
        'Anst': Anschluss- oder Übergabestelle, fasst Anschlussgleise zusammen auf die ein Zug umdisponiert werden kann. 
        'Bst': Betriebsstelle. Entweder 'Bf' oder 'Anst'.
        'Stw': Stellwerk/Anlage.
        """)
    auto = dict_property("auto", bool, docstring="True bei automatischer, False bei manueller Konfiguration.")
    stamm = dict_property("stamm", str, docstring="""
        Name des übergeordneten Knoten. 
        Wird im Konfigurationsimport und -export verwendet und ist ansonsten undefiniert.
        Der Typ erschliesst sich aus `BAHNHOFELEMENT_HIERARCHIE[typ]`.
        """)
    gleise = dict_property("gleise", int, docstring="""
        Anzahl Gleise mit dem gleichen Namen.
        Normalerweise 1, ausser z.B. bei Haltestellen oder Anschlussgleisen ohne Gleisnummer.
        In diesem Fall wird bei Mehrfachbelegung kein Konflikt angezeigt.  
        Nur bei Gl, Bs und Agl.
        Im Moment wird der Wert nur bei Agl automatisch aus dem Signalgraphen ausgewertet. 
        """)
    einfahrt = dict_property("einfahrt", bool, docstring="True, wenn das Gleis eine Einfahrt ist. Nur für Agl definiert.")
    ausfahrt = dict_property("ausfahrt", bool, docstring="True, wenn das Gleis eine Ausfahrt ist. Nur für Agl definiert.")
    sperrung = dict_property("sperrung", bool, docstring="Gleissperrung")
    linienstil = dict_property("linienstil", str, docstring="Linienstil für die Darstellung der Station.")


class BahnsteigGraphEdge(dict):
    """
    Klasse der Kantenattribute von BahnsteigGraph und BahnhofGraph
    """
    typ = dict_property("typ", str, docstring="""
        'Nachbar': Nachbarbeziehung gemäss Simulator.
        'Hierarchie': Von StsDispo definierte Hierarchiebeziehung.
        """)
    distanz = dict_property("distanz", int, docstring="""
        Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten.
        """)


class BahnsteigGraph(nx.Graph):
    """
    Bahnsteige

    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.
    Kanten werden entsprechend der Nachbarrelationen gesetzt.
    Der Graph ist ungerichtet, da die Nachbarbeziehung als reziprok aufgefasst wird.

    Vom Simulator werden nur die Gleisbezeichnungen der untersten Hierarchie sowie ihre Nachbarbeziehungen angegeben.
    Die Gruppierung in Bahnhofteile, Bahnhöfe und Anschlussstellen wird von der Klasse unterstützt,
    muss aber vom Besitzer gemacht werden.
    """
    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return BahnhofGraph

    def bahnsteige_importieren(self, bahnsteige: Iterable[BahnsteigInfo]):
        """
        Bahnsteiggraph aus Plugindaten erstellen.

        :param bahnsteige: Iterable von stsobj.BahnsteigInfo vom PluginClient
        :return: None
        """

        self.clear()

        for bs1 in bahnsteige:
            self.add_node(bs1.name, name=bs1.name, typ='Gl')
            for bs2 in bs1.nachbarn:
                self.add_edge(bs1.name, bs2.name, typ='Nachbar', distanz=0)


BahnhofLabelType = BahnhofElement


class BahnhofGraph(nx.DiGraph):
    """
    Bahnhöfe und ihre Gleishierarchie

    Der _Bahnhofgraph_ stellt die Gleishierarchie der Bahnhöfe dar
    und ordnet Bahnhöfe, Bahnhofteile, Bahnsteige und Gleise einander zu.

    Die Attribute der Knoten haben die Klasse BahnsteigGraphNode, die Kanten BahnsteigGraphEdge.

    Der Graph ist gerichtet, die Kanten zeigen von Bahnhöfen zu Gleisen.
    Die ungerichtete Variante ist der BahnsteigGraph.

    Attribute
    ---------

    ziel_gleis: Ordnet jedem Gleisnamen und jeder Anschlussnummer das entsprechende Graphlabel zu.
    """

    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.ziel_gleis: Dict[Union[int, str], BahnhofLabelType] = {}

    def to_directed_class(self):
        return self.__class__

    def to_undirected_class(self):
        return BahnsteigGraph

    @staticmethod
    def label(typ: str, name: str) -> BahnhofLabelType:
        """
        Das Label Besteht aus Typ und Name des BahnsteigGraphNode.
        """
        return BahnhofLabelType(typ, name)

    def root(self) -> BahnhofLabelType:
        """
        Label des höchsten Knotens

        Der höchste Knoten ist das Stellwerk.

        :return: Label ('Stw', Stellwerkname)
        """
        for node in self.nodes():
            if node.typ == 'Stw':
                return node
        else:
            raise KeyError('Bahnhofgraph enthält kein Anlagenelement.')

    def find_superior(self, label: BahnhofLabelType, typen: Set[str]) -> BahnhofLabelType:
        """
        Übergeordnetes Element suchen

        :param label: Label des Ausgangselements
        :param typen: Set von Elementtypen, z.B. {'Anst', 'Bf'}
        :return: Label des gefundenen Elements
        :raise: KeyError, wenn nicht gefunden
        """

        try:
            for node in nx.ancestors(self, label):
                if node.typ in typen:
                    return node
            else:
                raise KeyError(f"{label} ist keinem übergeordnetem {typen} zugeordnet")
        except nx.NetworkXError:
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def list_parents(self, label: BahnhofLabelType) -> Generator[BahnhofLabelType, None, None]:
        """
        Uebergeordnete Bahnhofelemente zu einem Gleis.
        :param label: Gleislabel (typ, name)
        :return: Generator von übergeordneten Elementen (typ, name) von unten nach oben.
            Das Ausgangselement wird nicht geliefert.
        :raise: KeyError, wenn das Gleis nicht existiert.
        """

        if self.has_node(label):
            for parent, child in nx.bfs_edges(self, label, reverse=True):
                yield child
        else:
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def gleis_parents(self) -> Dict[BahnhofLabelType, Dict[str, BahnhofLabelType]]:
        """
        Summary: Generates a dictionary of parents for each Gl and Agl node in the graph.

        This method traverses the graph in reverse breadth-first search (BFS) to find all parent nodes of each Gl and Agl node.
        It organizes these parent nodes into a nested dictionary where the keys are the Gl or Agl nodes,
        and the values are dictionaries mapping child node types to their corresponding child nodes.

        Parameters:
            None

        Returns:
            Dict[BahnhofLabelType, Dict[str, BahnhofLabelType]]: A dictionary containing parent nodes for each Gl and Agl node.
        """

        result = {}
        for gl in self.list_by_type({'Gl', 'Agl'}):
            for parent, child in nx.bfs_edges(self, gl, reverse=True):
                if gl in result:
                    result[gl][child.typ] = child
                else:
                    result[gl] = {child.typ: child}

        return result

    def list_children(self, label: BahnhofLabelType, typen: Set[str]) -> Generator[BahnhofLabelType, None, None]:
        """
        Listet die untergeordneten Elemente bestimmter Typen auf.

        Die Suchreihenfolge ist Breadth First.

        :param label: Label des Ausgangselements
        :param typen: Set von Elementtypen, z.B. {'Anst', 'Bf'}
        :return: Iterator über gefundene Elemente
        :raise: KeyError, wenn label nicht gefunden wird
        """

        try:
            for parent, child in nx.bfs_edges(self, label):
                if child.typ in typen:
                    yield child
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def list_by_type(self, typen: Set[str]) -> Generator[BahnhofLabelType, None, None]:
        """
        Listet die alle Elemente bestimmter Typen auf.
        """

        for label in self.nodes:
            if label.typ in typen:
                yield label

    def find_name(self, name: str) -> Optional[BahnhofLabelType]:
        """
        Betriebsstelle nach Namen suchen.

        Wenn der Typ nicht bekannt ist.
        Sucht zuerst in den Bahnhöfen und Anschlussstellen, dann in den weiteren Hierarchie.

        :param name: Name der Betriebsstelle
        :return: Label (Typ und Name) der Betriebsstelle oder None
        """

        for u, v in nx.bfs_edges(self, ('Bst', 'Bf')):
            if v.name == name:
                return v

        for u, v in nx.bfs_edges(self, ('Bst', 'Anst')):
            if v.name == name:
                return v

        return None

    def find_gleis_enr(self, name_enr: Union[int, str]) -> Optional[BahnhofLabelType]:
        """
        Gleis nach Name oder Anschlussgleis nach enr suchen.

        Der Zielgraph enthält für Anschlussgleise die enr.
        Mit dieser Methode kann sie in ein Label des Bahnhofgraphs überführt werden.
        Die Gleise sind indiziert in self.ziel_gleis.
        Dieser Dictionary kann alternativ verwendet werden.

        :param name_enr: Gleisname oder Elementnummer (enr) aus Signalgraph
        :return: Gleislabel (typ, name) oder None, wenn nicht gefunden
        """

        try:
            return self.ziel_gleis[name_enr]
        except KeyError:
            return None

    def replace_parent(self, gleis: BahnhofLabelType,
                       new_parent: BahnhofLabelType,
                       new_data: Optional[BahnsteigGraphNode] = None,
                       del_old_parent: bool = False):
        """
        Ersetzt den Elternknoten eines Gleises.

        Dies ist nützlich, wenn ein Gleis von einem anderen Bahnhof übernommen wird.
        Der Elternknoten kann ein beliebiger übergeordneter Knoten des Gleises sein.

        Der Elternknoten kann existieren oder wird neu erstellt.
        Der alte Knoten wird gelöscht, wenn der Parameter `del_old_parent` auf True gesetzt ist und er keine Kinder mehr hat.

        Hinweis: Es können leere Gruppen zurückbleiben.
            Am Ende der Bearbeitung daher ggf. leere_gruppen_entfernen aufrufen!

        :param gleis: Das Gleis, dessen Elternknoten ersetzt werden soll.
            Kann auch ein Element einer höheren Ebene sein, so lange die Ebene tiefer ist als die von new_parent.
        :param new_parent: Der neue Elternknoten des Gleises.
            Gibt den Typ und Namen des neuen Elternknotens an.
            Der Knoten kann existieren oder wird aus einer Kopie des alten neu erstellt.
        :param new_data: Daten des neuen Elternknotens. Wenn None, werden die alten Daten verwendet.
        :param del_old_parent: Alten Knoten löschen, wenn er keine Kinder hat. Standardmäßig False.
        :return: Label des alten Knotens
        """

        old_path = [gleis] + [element for element in self.list_parents(gleis)]
        old_parents = {element.typ: element for element in old_path}
        try:
            old_parent = old_parents[new_parent.typ]
            old_data = self.nodes[old_parent]
        except KeyError:
            # Fehler im Graph: Das Gleis hat keinen entsprechenden Elternknoten!
            logger.error(f"Fehler im Bahnhofgraph: Das Gleis {gleis} hat keinen Elternknoten vom Typ {new_parent.typ}!")
            return None

        if new_data is None and not self.has_node(new_parent):
            new_data = old_data.copy()
        if new_data is not None:
            new_data['name'] = new_parent.name
            new_data['typ'] = new_parent.typ
            self.add_node(new_parent, **new_data)

        for element in old_path:
            if self.has_edge(old_parent, element):
                data = self.get_edge_data(old_parent, element)
                self.add_edge(new_parent, element, **data)
                self.nodes[element]['auto'] = False
                self.remove_edge(old_parent, element)
            if self.has_edge(element, old_parent):
                data = self.get_edge_data(element, old_parent)
                self.add_edge(element, new_parent, **data)

        if del_old_parent and not any(self.successors(old_parent)):
            self.remove_node(old_parent)

        return old_parent

    def gleis_bahnsteig(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnsteig nachschlagen

        Nur für Bahnhofgleise.

        :param: gleis: Gleisname wie im STS
        :return: Bahnsteigname
        :raise: KeyError, wenn nicht gefunden
        """

        bs = self.find_superior(BahnhofLabelType('Gl', gleis), {'Bs'})
        return bs.name

    def gleis_bahnhofteil(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhofteil nachschlagen

        Nur für Bahnhofgleise.

        :param: gleis: Gleisname wie im STS
        :return: Bahnhofteilname
        :raise: KeyError, wenn nicht gefunden
        """

        bft = self.find_superior(BahnhofLabelType('Gl', gleis), {'Bft'})
        return bft.name

    def gleis_bahnhof(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhof nachschlagen

        Nur für Bahnhofgleise.

        :param: gleis: Gleisname wie im STS
        :return: Bahnhofname
        :raise: KeyError, wenn nicht gefunden
        """

        bf = self.find_superior(BahnhofLabelType('Gl', gleis), {'Bf'})
        return bf.name

    def anschlussstelle(self, gleis: str) -> str:
        """
        Zu Anschlussgleis zugeordnete Anschlussstelle nachschlagen

        Nur für Anschlussgleise.

        :param: gleis: Anschlussgleisname wie im STS
        :return: Name der Anschlussstelle
        :raise: KeyError, wenn nicht gefunden
        """

        anst = self.find_superior(BahnhofLabelType('Agl', gleis), {'Anst'})
        return anst.name

    def bahnhofgleise(self, bahnhof: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhof gehörenden Gleise auf.

        Nur für Bahnhofgleise.

        :param: bahnhof: Name des Bahnhofs
        :return: Iterator von Gleisnamen
        :raise: KeyError, wenn der Bahnhof nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, ('Bf', bahnhof)):
                if child.typ == 'Gl':
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Bf {bahnhof} ist im Bahnhofgraph nicht verzeichnet.")

    def bahnhofteilgleise(self, bahnhofteil: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhofteil gehörenden Gleise auf.

        Nur für Bahnhofgleise.

        :param: bahnhofteil: Name des Bahnhofteils
        :return: Iterator von Gleisnamen
        :raise: KeyError, wenn der Bahnhofteil nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, BahnhofLabelType('Bft', bahnhofteil)):
                if child.typ == 'Gl':
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Bft {bahnhofteil} ist im Bahnhofgraph nicht verzeichnet.")

    def anschlussgleise(self, anst: str) -> Iterable[str]:
        """
        Listet die zu einer Anschlussstelle gehörenden Gleise auf.

        Nur für Anschlussgleise.

        :param: anst: Name der Anschlussstelle
        :return: Iterator von Gleisnamen
        :raise: KeyError, wenn die Anst nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, BahnhofLabelType('Anst', anst)):
                if child.typ == 'Agl':
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Anst {anst} ist im Bahnhofgraph nicht verzeichnet.")

    def bahnhoefe(self) -> Iterable[str]:
        """
        Listet alle Bahnhöfe auf.

        :return: Iterator von Bahnhofnamen
        """

        for node in self.list_children(BahnhofLabelType('Bst', 'Bf'), {'Bf'}):
            yield node.name

    def anschlussstellen(self) -> Iterable[str]:
        """
        Listet alle Anschlussstellen auf.

        :return: Iterator von Anschlussstellennamen
        """

        for node in self.list_children(BahnhofLabelType('Bst', 'Anst'), {'Anst'}):
            yield node.name

    def import_anlageninfo(self, anlageninfo: AnlagenInfo):
        """
        Importiert die Anlageninformation in den Stellwerksknoten.
        """

        anl_label = BahnhofLabelType('Stw', anlageninfo.name)
        self.add_node(anl_label, typ=anl_label.typ, name=anl_label.name, auto=True, aid=anlageninfo.aid,
                      region=anlageninfo.region, build=anlageninfo.build, online=anlageninfo.online)

    def import_bahnsteiggraph(self,
                              bahnsteiggraph: BahnsteigGraph,
                              gleisschema: Gleisschema):
        """
        Importiert Gleise und Bahnsteige aus einem Bahnsteiggraphen.
        """

        anl_label = self.root()
        bf_label = BahnhofLabelType('Bst', 'Bf')
        self.add_node(bf_label, typ=bf_label.typ, name=bf_label.name, auto=True)
        self.add_edge(anl_label, bf_label, typ=anl_label.typ, auto=True)

        for comp in nx.connected_components(bahnsteiggraph):
            gleis = min(comp, key=len)
            bft = gleisschema.bahnsteigname(gleis)
            bf = gleisschema.bahnhofname(bft)
            self.add_node(BahnhofLabelType('Bf', bf), name=bf, typ='Bf', auto=True)
            self.add_edge(bf_label, BahnhofLabelType('Bf', bf), typ=bf_label.typ, auto=True)
            self.add_node(BahnhofLabelType('Bft', bft), name=bft, typ='Bft', auto=True)
            self.add_edge(BahnhofLabelType('Bf', bf), BahnhofLabelType('Bft', bft), typ='Bf', auto=True)

            for gleis in comp:
                bs = gleisschema.bahnsteigname(gleis)
                self.add_node(BahnhofLabelType('Bs', bs), name=bs, typ='Bs', gleise=1, auto=True)
                self.add_node(BahnhofLabelType('Gl', gleis), name=gleis, typ='Gl', gleise=1, auto=True)
                self.ziel_gleis[gleis] = BahnhofLabelType('Gl', gleis)
                self.add_edge(BahnhofLabelType('Bft', bft), BahnhofLabelType('Bs', bs), typ='Bft', auto=True)
                self.add_edge(BahnhofLabelType('Bs', bs), BahnhofLabelType('Gl', gleis), typ='Bs', auto=True)

    def import_signalgraph(self,
                           signalgraph: SignalGraph,
                           gleisschema: Gleisschema):
        """
        Importiert Anschlussgleise aus einem Signalgraphen.
        """

        anl_label = self.root()
        bst_label = BahnhofLabelType('Bst', 'Anst')
        self.add_node(bst_label, typ=bst_label.typ, name=bst_label.name, auto=True)
        self.add_edge(anl_label, bst_label, typ=anl_label.typ, auto=True)

        agl_gleise = {}
        for anschluss, data in signalgraph.nodes(data=True):
            if data.typ in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                agl = data.name
                agl_label = BahnhofLabelType('Agl', agl)
                try:
                    agl_data = self.nodes[agl_label]
                except KeyError:
                    agl_data = BahnsteigGraphNode(name=agl, typ='Agl', enr=data.enr, gleise=0, auto=True)
                    agl_gleise[agl_label] = 0.

                if data['typ'] == Knoten.TYP_NUMMER['Einfahrt']:
                    agl_data['einfahrt'] = True
                    if agl_label in agl_gleise:
                        agl_gleise[agl_label] += 0.5
                if data['typ'] == Knoten.TYP_NUMMER['Ausfahrt']:
                    agl_data['ausfahrt'] = True
                    if agl_label in agl_gleise:
                        agl_gleise[agl_label] += 0.5

                anst = gleisschema.anschlussname(agl)
                anst_label = BahnhofLabelType('Anst', anst)
                self.add_node(agl_label, **agl_data)
                self.add_edge(bst_label, anst_label, typ=bst_label.typ, auto=True)
                self.ziel_gleis[data.enr] = agl_label
                self.add_node(anst_label, name=anst, typ='Anst', auto=True)
                self.add_edge(anst_label, agl_label, typ='Anst', auto=True)

        for agl_label, gleise in agl_gleise.items():
            self.nodes[agl_label]['gleise'] = int(gleise + 0.5)

    def import_konfiguration(self, elemente: Iterable[Dict[str, Any]]):
        """
        Konfiguration importieren

        Strategie
        ---------

        1. Alle Knoten von bestehendem Graph importieren.
           Kanten _nicht_ importieren, sondern Vorfahr im stamm-Attribut verzeichnen.
        2. Knoten mit Attributen aus Elementen importieren, bestehende überschreiben.
           Vorfahr im stamm-Attribut verzeichnen.
           In der Anlage nicht vorkommende Gleise nicht übernehmen.
        3. Kanten gem. stamm-Attribut schichtweise zur Vorfahrenebene konstruieren,
           beginnend mit Gl und Agl.
        4. Kantenlose Knoten entfernen:
           Alle ohne eingehende Kanten, alle nicht-Gleise ohne ausgehende Kanten.
           Gl und Agl haben keine ausgehenden Kanten und müssen beibehalten werden.
        """

        # Schritt 1: Default-Graph importieren
        new_graph = BahnhofGraph()
        for node, data in self.nodes(data=True):
            data.auto = True
            try:
                parent_node = next(self.list_parents(node), BahnhofLabelType(None, None))
                data.stamm = parent_node.name
            except KeyError:
                continue
            new_graph.add_node(node, **data)

        # Schritt 2: Konfiguration importieren, wo auto==False
        konfig_graph = BahnhofGraph()
        for element in elemente:
            node = BahnhofElement(element['typ'], element['name'])
            auto = element.get('auto', True)
            stamm = element.get('stamm', None)

            data = {"auto": auto, "typ": element['typ'], "name": element['name'], "stamm": stamm}
            if "sichtbar" in element:
                data["sichtbar"] = element['sichtbar']
            if "gleise" in element:
                data["gleise"] = element['gleise']
            if "flags" in element:
                data["sperrung"] = "S" in element['flags']
            if "linienstil" in element:
                data["linienstil"] = element['linienstil']

            if element['typ'] in {'Gl', 'Agl'}:
                if node not in self:
                    logger.warning(f"Gleis {node} existiert nicht im Simulator")
                    continue

            # element einfuegen oder attribute aktualisieren
            konfig_graph.add_node(node, **data)

        # Schritt 2.5: reine auto-Knoten filtern
        for node, data in konfig_graph.nodes(data=True):
            parent_node = BahnhofElement(BAHNHOFELEMENT_HIERARCHIE[data['typ']], data['stamm'])
            parent_auto = not konfig_graph.has_node(parent_node) or konfig_graph.nodes[parent_node]['auto']
            if not data.auto or not parent_auto:
                new_graph.add_node(node, **data)

        # Schritt 3: Kanten erstellen gem. stamm-Attributen
        TYPEN_FOLGE = ['Gl', 'Agl', 'Bs', 'Bft', 'Bf', 'Anst']
        for typ in TYPEN_FOLGE:
            if typ == "Bst":
                break
            for node in new_graph.list_by_type({typ}):
                data = new_graph.nodes[node]
                try:
                    if typ == "Bf":
                        parent_node = BahnhofElement("Bst", "Bf")
                    elif typ == "Anst":
                        parent_node = BahnhofElement("Bst", "Anst")
                    else:
                        parent_node = BahnhofElement(BAHNHOFELEMENT_HIERARCHIE[data['typ']], data['stamm'])
                except KeyError:
                    continue
                if parent_node in new_graph:
                    new_graph.add_edge(parent_node, node, auto=data.get('auto', True))

        new_graph.add_edge(self.root(), BahnhofElement('Bst', 'Bf'))
        new_graph.add_edge(self.root(), BahnhofElement('Bst', 'Anst'))

        # Schritt 4: kinder- und elternlose Knoten entfernen
        for typ in TYPEN_FOLGE:
            to_remove = set()
            for node in new_graph.list_by_type({typ}):
                if new_graph.in_degree(node) == 0:
                    to_remove.add(node)
                if typ in {'Gl', 'Agl'}:
                    continue
                if new_graph.out_degree(node) == 0:
                    to_remove.add(node)
            for node in to_remove:
                new_graph.remove_node(node)

        # Schritt 5: Import abschliessen
        self.clear()
        self.update(new_graph)
        self.validate()

    def leere_gruppen_entfernen(self):
        """
        Gruppen ohne Elemente aus dem Graphen entfernen.

        Bei der Bearbeitung mittels replace_parent kann es vorkommen, dass leere Gruppen (Bahnhöfe etc.) zurückbleiben.
        Diese Methode räumt sie auf.
        """

        # die reihenfolge und getrennte behandlung der ebenen ist wichtig:
        for typ in ['Bs', 'Bft', 'Bf', 'Anst']:
            entfernen = []
            for n in self.nodes():
                if n.typ == typ and self.out_degree[n] == 0:
                    entfernen.append(n)
            for n in entfernen:
                self.remove_node(n)

    def validate(self):
        for gl in self.list_by_type({'Gl', 'Agl'}):
            if gl.typ == 'Gl':
                check = {'Gl', 'Bs', 'Bft', 'Bf', 'Bst', 'Stw'}
            elif gl.typ == 'Agl':
                check = {'Agl', 'Anst', 'Bst', 'Stw'}
            else:
                raise ValueError(f"Ungueltiger Gleistyp {gl}")

            # gl_data = self.nodes[gl]
            try:
                for be in self.list_parents(gl):
                    # be_data = self.nodes[be]
                    check -= {be.typ}
                    if self.in_degree(be) > 1:
                        logger.error(f"{be} hat mehrere Eltern.")
                if not check:
                    logger.error(f"{gl} hat fehlende Eltern {check}")
            except KeyError as e:
                logger.exception(f"{gl} nicht im bahnhofgraph", exc_info=e)

    def export_konfiguration(self) -> Sequence[Dict[str, Union[str, int, float, bool]]]:
        """
        Bahnhofgraph exportieren fuer Konfigurationsdatei

        :return: Liste von Bahnhof-Elementen fuer das 'elemente'-Arrays gemaess config.schema3.json.
        """

        elemente = {}
        for e1, e2 in self.edges():
            # e1 ist der stammknoten
            if e1.typ == 'Stw':
                continue
            data1: BahnsteigGraphNode = self.nodes[e1]
            data2: BahnsteigGraphNode = self.nodes[e2]
            element = {'name': e2.name,
                       'typ': e2.typ,
                       'auto': data2.auto,
                       'sichtbar': True,
                       'flags': ''}
            if e1.typ != 'Bst':
                element['stamm'] = e1.name
            if data2.get('sperrung'):
                element['flags'] = 'S'
                element['auto'] = False
            if element['typ'] in {'Gl', 'Bs', 'Agl'}:
                element['gleise'] = data2.get('gleise', 1)
            elif element['typ'] in {'Bf', 'Anst'}:
                if stil := data2.get('linienstil'):
                    element['linienstil'] = stil
            elemente[e2] = element

        return list(elemente.values())
