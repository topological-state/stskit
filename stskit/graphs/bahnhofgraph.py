import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.interface.stsobj import AnlagenInfo, BahnsteigInfo, Knoten
from stskit.graphs.signalgraph import SignalGraph

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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


BahnhofLabelType = Tuple[str, str]


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
    def label(typ: str, name: str) -> Tuple[str, str]:
        """
        Das Label Besteht aus Typ und Name des BahnsteigGraphNode.
        """
        return typ, name

    def root(self) -> Tuple[str, str]:
        """
        Label des obersten Knoten

        Im Moment ist das das Anlagenelement.

        :return: Label ('Anl', Anlagenname)
        """
        for node in self.nodes():
            if node[0] == 'Anl':
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
                if node[0] in typen:
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
                if child[0] in typen:
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
            if v[1] == name:
                return v

        for u, v in nx.bfs_edges(self, ('Bst', 'Anst')):
            if v[1] == name:
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

        _, bs = self.find_superior(('Gl', gleis), {'Bs'})
        return bs

    def gleis_bahnhofteil(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhofteil nachschlagen

        Nur für Bahnhofgleise.

        :param: gleis: Gleisname wie im STS
        :return: Bahnhofteilname
        :raise: KeyError, wenn nicht gefunden
        """

        _, bft = self.find_superior(('Gl', gleis), {'Bft'})
        return bft

    def gleis_bahnhof(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhof nachschlagen

        Nur für Bahnhofgleise.

        :param: gleis: Gleisname wie im STS
        :return: Bahnhofname
        :raise: KeyError, wenn nicht gefunden
        """

        _, bf = self.find_superior(('Gl', gleis), {'Bf'})
        return bf

    def anschlussstelle(self, gleis: str) -> str:
        """
        Zu Anschlussgleis zugeordnete Anschlussstelle nachschlagen

        Nur für Anschlussgleise.

        :param: gleis: Anschlussgleisname wie im STS
        :return: Name der Anschlussstelle
        :raise: KeyError, wenn nicht gefunden
        """

        _, anst = self.find_superior(('Agl', gleis), {'Anst'})
        return anst

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
                if child[0] == 'Gl':
                    yield child[1]
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
            for parent, child in nx.dfs_edges(self, ('Bft', bahnhofteil)):
                if child[0] == 'Gl':
                    yield child[1]
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
            for parent, child in nx.dfs_edges(self, ('Anst', anst)):
                if child[0] == 'Agl':
                    yield child[1]
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Anst {anst} ist im Bahnhofgraph nicht verzeichnet.")

    def bahnhoefe(self) -> Iterable[str]:
        """
        Listet alle Bahnhöfe auf.

        :return: Iterator von Bahnhofnamen
        """

        for node in self.list_children(('Bst', 'Bf'), {'Bf'}):
            yield node[1]

    def anschlussstellen(self) -> Iterable[str]:
        """
        Listet alle Anschlussstellen auf.

        :return: Iterator von Anschlussstellennamen
        """

        for node in self.list_children(('Bst', 'Anst'), {'Anst'}):
            yield node[1]

    def import_anlageninfo(self, anlageninfo: AnlagenInfo):
        anl_label = ('Anl', anlageninfo.name)
        self.add_node(anl_label, typ=anl_label[0], name=anl_label[1], auto=True, aid=anlageninfo.aid,
                      region=anlageninfo.region, build=anlageninfo.build, online=anlageninfo.online)

    def import_bahnsteiggraph(self,
                              bahnsteiggraph: BahnsteigGraph,
                              f_bahnsteigname: Callable,
                              f_bahnhofname: Callable):
        """
        Importiert Gleise und Bahnsteige aus einem Bahnsteiggraphen.
        """

        anl_label = self.root()
        bf_label = ('Bst', 'Bf')
        self.add_node(bf_label, typ=bf_label[0], name=bf_label[1], auto=True)
        self.add_edge(anl_label, bf_label, typ=anl_label[0], auto=True)

        for comp in nx.connected_components(bahnsteiggraph):
            gleis = min(comp, key=len)
            bft = f_bahnsteigname(gleis)
            bf = f_bahnhofname(bft)
            self.add_node(('Bf', bf), name=bf, typ='Bf', auto=True)
            self.add_edge(bf_label, ('Bf', bf), typ=bf_label[0], auto=True)
            self.add_node(('Bft', bft), name=bft, typ='Bft', auto=True)
            self.add_edge(('Bf', bf), ('Bft', bft), typ='Bf', auto=True)

            for gleis in comp:
                bs = f_bahnsteigname(gleis)
                self.add_node(('Bs', bs), name=bs, typ='Bs', auto=True)
                self.add_node(('Gl', gleis), name=gleis, typ='Gl', auto=True)
                self.ziel_gleis[gleis] = ('Gl', gleis)
                self.add_edge(('Bft', bft), ('Bs', bs), typ='Bft', auto=True)
                self.add_edge(('Bs', bs), ('Gl', gleis), typ='Bs', auto=True)

    def import_signalgraph(self,
                           signalgraph: SignalGraph,
                           f_anschlussname: Callable):
        """
        Importiert Anschlussgleise aus einem Signalgraphen.
        """

        anl_label = self.root()
        anst_label = ('Bst', 'Anst')
        self.add_node(anst_label, typ=anst_label[0], name=anst_label[1], auto=True)
        self.add_edge(anl_label, anst_label, typ=anl_label[0], auto=True)

        for anschluss, data in signalgraph.nodes(data=True):
            if data.typ in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                agl = data.name
                agl_data = dict(name=agl, typ='Agl', enr=data.enr, auto=True)
                if data['typ'] == Knoten.TYP_NUMMER['Einfahrt']:
                    agl_data['einfahrt'] = True
                if data['typ'] == Knoten.TYP_NUMMER['Ausfahrt']:
                    agl_data['ausfahrt'] = True

                anst = f_anschlussname(agl)
                self.add_node(('Agl', agl), **agl_data)
                self.add_edge(anst_label, ('Anst', anst), typ=anst_label[0], auto=True)
                self.ziel_gleis[data.enr] = ('Agl', agl)
                self.add_node(('Anst', anst), name=anst, typ='Anst', auto=True)
                self.add_edge(('Anst', anst), ('Agl', agl), typ='Anst', auto=True)

    def konfigurieren(self, config: Dict[Tuple[str, str], Tuple[str, ...]]) -> None:
        """
        Modifiziert den Bahnhofgraphen anhand von Konfigurationsdaten

        :param config: Mapping von STS-Gleisnamen zu Tupel (Bahnsteig, Bahnhofteil, Bahnhof) bzw. (Anschlussstelle)
        """

        relabeling = {}

        def bahnhof_ast(graph: nx.Graph, gl: Tuple[str, str]) -> Optional[List[Tuple[str, str]]]:
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
                if key[0] in {'Bf', 'Anst'}:
                    return pfad

        for gleis, bf_bft_bs in config.items():
            ast = bahnhof_ast(self, gleis)
            if ast:
                for label_alt, name_neu in zip(ast, bf_bft_bs):
                    # die alten konfigurationsdaten unterscheiden nicht zwischen Bf und Bft.
                    # die bahnhofsnamen sind mit einem fragezeichen markiert.
                    if name_neu.endswith("?"):
                        bf_neu = name_neu[:-1]
                        continue
                    typ, name_alt = label_alt
                    if name_neu != name_alt:
                        relabeling[label_alt] = (typ, name_neu)

        nx.relabel_nodes(self, relabeling, copy=False)

        for node, data in self.nodes(data=True):
            if data['name'] != node[1]:
                data['name'] = node[1]
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
