import logging
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.plugin.stsobj import AnlagenInfo, BahnsteigInfo, Knoten
from stskit.model.signalgraph import SignalGraph

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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


class BahnsteigGraphNode(dict):
    """
    Klasse der Knotenattribute von BahnsteigGraph und BahnhofGraph
    """
    name = dict_property("name", str, docstring="Name")
    enr = dict_property("enr", int, docstring="Elementnummer bei Anschlussgleisen. Nur für Agl definiert.")
    typ = dict_property("typ", str, docstring="""
        'Gl': Gleis(sektor)bezeichnung, wie sie in den Fahrplänen vorkommt. Vom Sim deklariert. 
        'Bs': Bahnsteigbezeichnung, fasst Gleissektoren zusammen.
        'Bft': Bahnhofteil, fasst Bahnsteige zusammen, auf die ein Zug umdisponiert werden kann.
        'Bf': Bahnhof für grafische Darstellung und Fahrzeitauswertung.
        'Agl': Anschluss- oder Übergabegleis. Vom Sim deklariert.
        'Anst': Anschluss- oder Übergabestelle, fasst Anschlussgleise zusammen auf die ein Zug umdisponiert werden kann. 
        'Bst': Betriebsstelle. Entweder 'Bf' oder 'Anst'.
        'Anl': Anlage.
        """)
    auto = dict_property("auto", bool, docstring="True bei automatischer, False bei manueller Konfiguration.")
    einfahrt = dict_property("einfahrt", bool, docstring="True, wenn das Gleis eine Einfahrt ist. Nur für Agl definiert.")
    ausfahrt = dict_property("ausfahrt", bool, docstring="True, wenn das Gleis eine Ausfahrt ist. Nur für Agl definiert.")
    sperrung = dict_property("sperrung", bool, docstring="Gleissperrung")


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
        Label des obersten Knoten

        Im Moment ist das das Anlagenelement.

        :return: Label ('Anl', Anlagenname)
        """
        for node in self.nodes():
            if node.typ == 'Anl':
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

    def list_children(self, label: BahnhofLabelType, typen: Set[str]) -> Iterable[BahnhofLabelType]:
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
        anl_label = BahnhofLabelType('Anl', anlageninfo.name)
        self.add_node(anl_label, typ=anl_label.typ, name=anl_label.name, auto=True, aid=anlageninfo.aid,
                      region=anlageninfo.region, build=anlageninfo.build, online=anlageninfo.online)

    def import_bahnsteiggraph(self,
                              bahnsteiggraph: BahnsteigGraph,
                              f_bahnsteigname: Callable,
                              f_bahnhofname: Callable):
        """
        Importiert Gleise und Bahnsteige aus einem Bahnsteiggraphen.
        """

        anl_label = self.root()
        bf_label = BahnhofLabelType('Bst', 'Bf')
        self.add_node(bf_label, typ=bf_label.typ, name=bf_label.name, auto=True)
        self.add_edge(anl_label, bf_label, typ=anl_label.typ, auto=True)

        for comp in nx.connected_components(bahnsteiggraph):
            gleis = min(comp, key=len)
            bft = f_bahnsteigname(gleis)
            bf = f_bahnhofname(bft)
            self.add_node(BahnhofLabelType('Bf', bf), name=bf, typ='Bf', auto=True)
            self.add_edge(bf_label, BahnhofLabelType('Bf', bf), typ=bf_label.typ, auto=True)
            self.add_node(BahnhofLabelType('Bft', bft), name=bft, typ='Bft', auto=True)
            self.add_edge(BahnhofLabelType('Bf', bf), BahnhofLabelType('Bft', bft), typ='Bf', auto=True)

            for gleis in comp:
                bs = f_bahnsteigname(gleis)
                self.add_node(BahnhofLabelType('Bs', bs), name=bs, typ='Bs', auto=True)
                self.add_node(BahnhofLabelType('Gl', gleis), name=gleis, typ='Gl', auto=True)
                self.ziel_gleis[gleis] = BahnhofLabelType('Gl', gleis)
                self.add_edge(BahnhofLabelType('Bft', bft), BahnhofLabelType('Bs', bs), typ='Bft', auto=True)
                self.add_edge(BahnhofLabelType('Bs', bs), BahnhofLabelType('Gl', gleis), typ='Bs', auto=True)

    def import_signalgraph(self,
                           signalgraph: SignalGraph,
                           f_anschlussname: Callable):
        """
        Importiert Anschlussgleise aus einem Signalgraphen.
        """

        anl_label = self.root()
        anst_label = BahnhofLabelType('Bst', 'Anst')
        self.add_node(anst_label, typ=anst_label.typ, name=anst_label.name, auto=True)
        self.add_edge(anl_label, anst_label, typ=anl_label.typ, auto=True)

        for anschluss, data in signalgraph.nodes(data=True):
            if data.typ in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                agl = data.name
                agl_data = dict(name=agl, typ='Agl', enr=data.enr, auto=True)
                if data['typ'] == Knoten.TYP_NUMMER['Einfahrt']:
                    agl_data['einfahrt'] = True
                if data['typ'] == Knoten.TYP_NUMMER['Ausfahrt']:
                    agl_data['ausfahrt'] = True

                anst = f_anschlussname(agl)
                self.add_node(BahnhofLabelType('Agl', agl), **agl_data)
                self.add_edge(anst_label, BahnhofLabelType('Anst', anst), typ=anst_label.typ, auto=True)
                self.ziel_gleis[data.enr] = BahnhofLabelType('Agl', agl)
                self.add_node(BahnhofLabelType('Anst', anst), name=anst, typ='Anst', auto=True)
                self.add_edge(BahnhofLabelType('Anst', anst), BahnhofLabelType('Agl', agl), typ='Anst', auto=True)

    def konfigurieren(self, config: Dict[Tuple[str, str], Tuple[str, ...]]) -> None:
        """
        Modifiziert den Bahnhofgraphen anhand von Konfigurationsdaten

        :param config: Mapping von STS-Gleisnamen zu Tupel (Bahnsteig, Bahnhofteil, Bahnhof) bzw. (Anschlussstelle)
        """

        relabeling = {}

        def bahnhof_ast(graph: nx.Graph, gl: BahnhofLabelType) -> Optional[List[BahnhofLabelType]]:
            """
            Finde den Bf bzw. Anst-Knoten und gib den Pfad zum Gleisknoten zurück.
            :param graph: Bahnhofgraph
            :param gl: Gleislabel (typ, name)
            :return: Liste von Bahnhofgraphlabels von Bf zu Gl, bzw. Anst zu Agl
            """

            try:
                pfade = nx.shortest_path(graph, target=gl)
            except nx.NodeNotFound:
                return None

            for key, pfad in pfade.items():
                if key.typ in {'Bf', 'Anst'}:
                    return pfad

        for gleis, bf_bft_bs in config.items():
            ast = bahnhof_ast(self, BahnhofLabelType(gleis[0], gleis[1]))
            if ast:
                for label_alt, name_neu in zip(ast, bf_bft_bs):
                    # die alten konfigurationsdaten unterscheiden nicht zwischen Bf und Bft.
                    # die bahnhofsnamen sind mit einem fragezeichen markiert.
                    if name_neu.endswith("?"):
                        bf_neu = name_neu[:-1]
                        continue
                    typ, name_alt = label_alt
                    if name_neu != name_alt:
                        relabeling[label_alt] = BahnhofLabelType(typ, name_neu)

        nx.relabel_nodes(self, relabeling, copy=False)

        for node, data in self.nodes(data=True):
            if data['name'] != node.name:
                data['name'] = node.name
                data['auto'] = False

    def bereinigen(self):
        """
        Fehler im Graph bereinigen

        - Mehrfache eingehende Kanten: Behalte die Kante zum Knoten mit dem kürzesten Namen und lösche die anderen.

        :return:
        """

        kanten_entfernen = []

        for node, data in self.nodes(data=True):
            preds = list(self.predecessors(node))
            if len(preds) > 1:
                keep = min(sorted(preds), key=lambda n: len(n[1]))
                preds.remove(keep)
                for pred in preds:
                    kanten_entfernen.append((pred, node))

        self.remove_edges_from(kanten_entfernen)
