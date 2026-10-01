from __future__ import annotations
from enum import StrEnum
import logging
from typing import Any, Dict, Generator, Iterable, NamedTuple, Optional, Sequence, Set, Tuple, Union

import networkx as nx

from stskit.model.graphbasics import dict_property
from stskit.plugin.stsobj import AnlagenInfo, BahnsteigInfo, Knoten
from stskit.model.gleisschema import Gleisschema
from stskit.model.signalgraph import SignalGraph

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BahnhofElement(NamedTuple):
    """
    Vollständige Bahnhofelementbezeichnung (Typ und Name)

    Bahnhofelemente sind alle benannten Gleise, Bahnsteige etc., die im Bahnhofgraph als Knoten vorkommen.
    Dazu gehören also in Erweiterung des üblichen Sprachgebrauchs ausdrücklich auch Anschlussgleise und Haltepunkte.

    Eine Bahnhofelementbezeichnung enthält den Typ und den Namen des Elements,
    die auch als Property im `BahnsteigGraphNode` vorkommen.
    Typ und Namen werden verwendet, weil Anschlussgleise und Bahnhofgleise den gleichen Namen tragen können.
    
    Attributes:
        typ: Bahnhofelementtyp aus dem Enum `BahnhofElement.Typ`.
        name: Bahnhofelementname. Name des Elements gemäss Simulator.
    """
    
    class Typ(StrEnum):
        GL = "Gl" 
        BS = "Bs" 
        BFT = "Bft" 
        BF = "Bf"
        AGL = "Agl" 
        ANST = "Anst" 
        BST = "Bst"
        STW = "Stw"

        @property
        def vollname(self) -> str:
            return _bahnhofelement_vollname[self]

        @property
        def supertyp(self) -> Typ:
            return _bahnhofelement_supertyp[self]

    typ: Typ
    name: str

    def __str__(self):
        """
        Benutzerfreundliche Bezeichnung, wird im UI verwendet.
        """
        return f"{self.typ} {self.name}"

    @classmethod
    def from_string(cls, typ_und_name: str) -> BahnhofElement:
        """
        Bahnhofelement aus Stringdarstellung

        Args:
            typ_und_name: Typ und Name des Bahnhofelements als String, getrennt durch Leerzeichen.

        Raises: 
            ValueError: Fehlerhaftes Format oder unbekannter Elementtyp.
                Überprüft nicht, ob das Bahnhofelement in der Anlage existiert.
        """

        typ, name = typ_und_name.split(" ", 1)
        try:
            typ_enum = cls.Typ(typ)
        except ValueError:
            raise ValueError(f"Unbekannter Bahnhofelementtyp {typ} in {typ_und_name}")
        if not name:
            raise ValueError(f"Undefinierter Bahnhofelementname {name} in {typ_und_name}")
        return BahnhofElement(typ_enum, name)

    @classmethod
    def from_strings(cls, typ: str, name: str) -> BahnhofElement:
        """
        Bahnhofelement aus 2-Stringdarstellung

        Args:
            typ: Typ des Bahnhofelements als String.
            name: Name des Bahnhofelements als String.

        Raises:
            ValueError: Fehlerhaftes Format oder unbekannter Elementtyp.
                Überprüft nicht, ob das Bahnhofelement in der Anlage existiert.
        """

        try:
            typ_enum = cls.Typ(typ)
        except ValueError:
            raise ValueError(f"Unbekannter Bahnhofelementtyp {typ}")
        if not name:
            raise ValueError(f"Undefinierter Bahnhofelementname {name}")
        return BahnhofElement(typ_enum, name)


_bahnhofelement_vollname: dict[BahnhofElement.Typ, str] = {
        BahnhofElement.Typ.GL: "Gleis",
        BahnhofElement.Typ.BS: "Bahnsteig",
        BahnhofElement.Typ.BFT: "Bahnhofteil",
        BahnhofElement.Typ.BF: "Bahnhof",
        BahnhofElement.Typ.AGL: "Anschlussgleis",
        BahnhofElement.Typ.ANST: "Anschlussstelle",
        BahnhofElement.Typ.BST: "Betriebsstelle",
        BahnhofElement.Typ.STW: "Stellwerk",
    }

_bahnhofelement_supertyp: dict[BahnhofElement.Typ, BahnhofElement.Typ] = {
        BahnhofElement.Typ.GL: BahnhofElement.Typ.BS,
        BahnhofElement.Typ.BS: BahnhofElement.Typ.BFT,
        BahnhofElement.Typ.BFT: BahnhofElement.Typ.BF,
        BahnhofElement.Typ.BF: BahnhofElement.Typ.BST,
        BahnhofElement.Typ.AGL: BahnhofElement.Typ.ANST,
        BahnhofElement.Typ.ANST: BahnhofElement.Typ.BST,
        BahnhofElement.Typ.BST: BahnhofElement.Typ.STW,
    }


class BahnsteigGraphNode(dict):
    """
    Klasse der Knotenattribute von BahnsteigGraph und BahnhofGraph
    
    Attributes:
        name: Name
        enr: Elementnummer bei Anschlussgleisen. Nur für Agl definiert.
        typ: Bahnhofelementtyp
        
            | Wert | Bedeutung |
            |:---:|:---|
            | Gl | Gleis- oder Haltepunktbezeichnung, wie sie in den Fahrplänen vorkommt. Vom Sim deklariert. | 
            | Bs | Bahnsteigbezeichnung, fasst Gleissektoren bzw. Haltepunkte zusammen. |
            | Bft | Bahnhofteil, fasst Bahnsteige zusammen, auf die ein Zug umdisponiert werden kann. |
            | Bf | Bahnhof für grafische Darstellung und Fahrzeitauswertung. |
            | Agl | Anschluss- oder Übergabegleis. Vom Sim deklariert. |
            | Anst | Anschluss- oder Übergabestelle, fasst Anschlussgleise zusammen auf die ein Zug umdisponiert werden kann. | 
            | Bst | Betriebsstelle. Entweder BahnhofElement.Typ.BF oder BahnhofElement.Typ.ANST. |
            | Stw | Stellwerk/Anlage. |

        auto: True bei automatischer, False bei manueller Konfiguration.
        stamm: Name des übergeordneten Knoten. 
            Wird im Konfigurationsimport und -export verwendet und ist ansonsten undefiniert.
            Der Typ erschliesst sich aus `BAHNHOFELEMENT_HIERARCHIE[typ]`.
        ordnung: Sortierordnung innerhalb der Gruppe.
            Bahnhofelemente innerhalb der Gruppe werden gemäss dem Tupel (ordnung, name) sortiert.
        gleise: Anzahl Gleise mit dem gleichen Namen.
            Normalerweise 1, ausser z.B. bei Haltestellen oder Anschlussgleisen ohne Gleisnummer.
            In diesem Fall wird bei Mehrfachbelegung kein Konflikt angezeigt.  
            Nur bei Gl, Bs und Agl.
            Im Moment wird der Wert nur bei Agl automatisch aus dem Signalgraphen ausgewertet. 
        einfahrt: True, wenn das Gleis eine Einfahrt ist. Nur für Agl definiert.
        ausfahrt: True, wenn das Gleis eine Ausfahrt ist. Nur für Agl definiert.
        sperrung: Gleissperrung
        linienstil: Linienstil für die Darstellung der Station.
    """

    name = dict_property("name", str,)
    enr = dict_property("enr", int,)
    typ = dict_property("typ", BahnhofElement.Typ,)
    auto = dict_property("auto", bool,)
    stamm = dict_property("stamm", str,)
    ordnung = dict_property("ordnung", int,)
    gleise = dict_property("gleise", int,)
    einfahrt = dict_property("einfahrt", bool,)
    ausfahrt = dict_property("ausfahrt", bool,)
    sperrung = dict_property("sperrung", bool,)
    linienstil = dict_property("linienstil", str,)


class BahnsteigGraphEdge(dict):
    """
    Klasse der Kantenattribute von BahnsteigGraph und BahnhofGraph

    Attributes:
        typ: Beziehungstyp

            | Wert | Bedeutung |
            |:---:|:---|
            | Nachbar | Nachbarbeziehung gemäss Simulator. |
            | Hierarchie | Von StsDispo definierte Hierarchiebeziehung. |

        distanz:
            Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten.
    """

    typ = dict_property("typ", str,)
    distanz = dict_property("distanz", int,)


class BahnsteigGraph(nx.Graph):
    """
    Bahnsteige

    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.

    Die Labels der Knoten sind die Gleisbezeichnungen der Bahnsteige.
    Von den Datenattributen werden nur `typ` und `name` verwendet,
    wobei `typ` immer `BahnhofElement.Typ.GL` ist.

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

        Args:
            bahnsteige: Iterable von stsobj.BahnsteigInfo vom PluginClient
        """

        self.clear()

        for bs1 in bahnsteige:
            self.add_node(bs1.name, name=bs1.name, typ=BahnhofElement.Typ.GL)
            for bs2 in bs1.nachbarn.values():
                self.add_edge(bs1.name, bs2.name, typ='Nachbar', distanz=0)


class BahnhofGraph(nx.DiGraph):
    """
    Bahnhöfe und ihre Gleishierarchie

    Der _Bahnhofgraph_ stellt die Gleishierarchie der Bahnhöfe dar
    und ordnet Bahnhöfe, Bahnhofteile, Bahnsteige und Gleise einander zu.

    Die Attribute der Knoten haben die Klasse BahnsteigGraphNode, die Kanten BahnsteigGraphEdge.

    Der Graph ist gerichtet, die Kanten zeigen von Bahnhöfen zu Gleisen.
    Die ungerichtete Variante ist der BahnsteigGraph.

    Attributes:
        ziel_gleis: Ordnet jedem Gleisnamen und jeder Anschlussnummer das entsprechende Graphlabel zu.
    """

    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.ziel_gleis: Dict[Union[int, str], BahnhofElement] = {}
        self.gleisschema = Gleisschema()

    def to_directed_class(self):
        return self.__class__

    def to_undirected_class(self):
        return BahnsteigGraph

    @staticmethod
    def label(typ: str, name: str) -> BahnhofElement:
        """
        Das Label besteht aus Typ und Namen des BahnsteigGraphNode.
        """

        typ = BahnhofElement.Typ(typ)
        return BahnhofElement(typ, name)

    def root(self) -> BahnhofElement:
        """
        Label des höchsten Knotens

        Der höchste Knoten ist das Stellwerk.

        Returns:
            Label `('Stw', Stellwerkname)`
        """
        for node in self.nodes():
            if node.typ is BahnhofElement.Typ.STW:
                return node
        else:
            raise KeyError('Bahnhofgraph enthält kein Anlagenelement.')

    def find_superior(self,
                      label: BahnhofElement,
                      typen: Set[BahnhofElement.Typ],
                      ) -> BahnhofElement:
        """
        Übergeordnetes Element suchen.

        Args:
            label: Label des Ausgangselements.
            typen: Set von Elementtypen, z.B. `{BahnhofElement.Typ.ANST, BahnhofElement.Typ.BF}`.

        Returns:
            Label des gefundenen Elements.

        Raises:
            KeyError: Wenn nicht gefunden.
        """

        try:
            for node in nx.ancestors(self, label):
                assert isinstance(node, BahnhofElement)
                if node.typ in typen:
                    return node
            else:
                raise KeyError(f"{label} ist keinem übergeordnetem {typen} zugeordnet")
        except nx.NetworkXError:
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def list_parents(self, label: BahnhofElement) -> Generator[BahnhofElement, None, None]:
        """
        Übergeordnete Bahnhofelemente zu einem Gleis.

        Args:
            label: Gleislabel (typ, name).

        Returns:
            Generator von übergeordneten Elementen (typ, name) von unten nach oben.
            Das Ausgangselement wird nicht geliefert.

        Raises:
            KeyError: Wenn das Gleis nicht existiert.
        """

        if self.has_node(label):
            for parent, child in nx.bfs_edges(self, label, reverse=True):
                yield child
        else:
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def gleis_parents(self) -> Dict[BahnhofElement, Dict[str, BahnhofElement]]:
        """
        Generates a dictionary of parents for each Gl and Agl node in the graph.

        This method traverses the graph in reverse breadth-first search (BFS) to find all parent nodes of each Gl and Agl node.
        It organizes these parent nodes into a nested dictionary where the keys are the Gl or Agl nodes,
        and the values are dictionaries mapping child node types to their corresponding child nodes.

        Returns:
            A dictionary containing parent nodes for each Gl and Agl node.
        """

        result = {}
        typen = {BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}
        for gl in self.list_by_type(typen):
            for parent, child in nx.bfs_edges(self, gl, reverse=True):
                assert isinstance(child, BahnhofElement)
                if gl in result:
                    result[gl][child.typ] = child
                else:
                    result[gl] = {child.typ: child}

        return result

    def list_children(self,
                      label: BahnhofElement,
                      typen: Set[BahnhofElement.Typ],
                      ) -> Generator[BahnhofElement, None, None]:
        """
            Listet die untergeordneten Elemente bestimmter Typen auf.

            Die Suchreihenfolge ist Breadth First.

            Args:
                label: Label des Ausgangselements.
                typen: Set von Elementtypen, z.B. `{BahnhofElement.Typ.ANST, BahnhofElement.Typ.BF}`.

            Returns:
                Iterator über gefundene Elemente.

            Raises:
                KeyError: Wenn label nicht gefunden wird.
            """

        try:
            for parent, child in nx.bfs_edges(self, label):
                assert isinstance(child, BahnhofElement)
                if child.typ in typen:
                    yield child
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Element {label} ist im Bahnhofgraph nicht verzeichnet.")

    def list_siblings(self,
                      label: BahnhofElement,
                      ) -> Generator[BahnhofElement, None, None]:
        """
        Listet die Geschwisterelemente eines Bahnhofelements auf.

        Geschwisterelemente haben den gleichen Typ und das gleiche Elternelement.
        Das Originalelement ist enthalten.
        """

        parent = self.find_superior(label, {label.typ.supertyp})
        yield from self.list_children(parent, {label.typ})

    def list_by_type(self, typen: Set[BahnhofElement.Typ]) -> Generator[BahnhofElement, None, None]:
        """
        Listet die alle Elemente bestimmter Typen auf.
        """

        for label in self.nodes:
            assert isinstance(label, BahnhofElement)
            if label.typ in typen:
                yield label

    def find_name(self, name: str) -> Optional[BahnhofElement]:
        """
        Betriebsstelle nach Namen suchen.

        Wenn der Typ nicht bekannt ist.
        Sucht zuerst in den Bahnhöfen und Anschlussstellen, dann in der weiteren Hierarchie.

        Args:
            name: Name der Betriebsstelle
        
        Returns:
            Label (Typ und Name) der Betriebsstelle oder None
        """

        for u, v in nx.bfs_edges(self, BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.BF)):
            assert isinstance(v, BahnhofElement)
            if v.name == name:
                return v

        for u, v in nx.bfs_edges(self, BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.ANST)):
            assert isinstance(v, BahnhofElement)
            if v.name == name:
                return v

        return None

    def find_gleis_enr(self, name_enr: Union[int, str]) -> Optional[BahnhofElement]:
        """
        Gleis nach Namen oder Anschlussgleis nach `enr` suchen.

        Der Zielgraph enthält für Anschlussgleise die `enr`.
        Mit dieser Methode kann sie in ein Label des Bahnhofgraphs überführt werden.
        Die Gleise sind indiziert in `ziel_gleis`.
        Dieser Dictionary kann alternativ verwendet werden.

        Args:
            name_enr: Gleisname oder Elementnummer (enr) aus Signalgraph

        Returns:            
            Gleislabel (typ, name) oder None, wenn nicht gefunden
        """

        try:
            return self.ziel_gleis[name_enr]
        except KeyError:
            return None

    def _find_parent_to_replace(self,
                                gleis: BahnhofElement,
                                level: BahnhofElement.Typ,
                                ) -> Tuple[Sequence[BahnhofElement], BahnhofElement | None, BahnsteigGraphNode | None]:
        """
        Sucht den Parent eines bestimmten Typs des angegebenen Gleises.

        Untermethode von `replace_parent` und `can_replace_parent`.
        """

        old_path = [gleis] + [element for element in self.list_parents(gleis)]
        old_parents = {element.typ: element for element in old_path}
        try:
            old_parent = old_parents[level]
            old_data = self.nodes[old_parent]
        except KeyError:
            # Fehler im Graph: Das Gleis hat keinen entsprechenden Elternknoten!
            logger.error(f"Fehler im Bahnhofgraph: Das Gleis {gleis} hat keinen Elternknoten vom Typ {level}!")
            old_parent = None
            old_data = None

        return old_path, old_parent, old_data

    def replace_parent(self, gleis: BahnhofElement,
                       new_parent: BahnhofElement,
                       new_data: Optional[BahnsteigGraphNode] = None,
                       del_old_parent: bool = False,
                       dry_run: bool = False) -> bool:
        """
        Ersetzt den Elternknoten eines Gleises.

        Dies ist nützlich, wenn ein Gleis von einem anderen Bahnhof übernommen wird.
        Der Elternknoten kann ein beliebiger übergeordneter Knoten des Gleises sein.
        Der Elternknoten kann existieren oder wird neu erstellt.
        Der alte Knoten wird gelöscht, wenn der Parameter `del_old_parent` auf True gesetzt ist und er keine Kinder mehr hat.

        Hinweis:
            Es können leere Gruppen zurückbleiben. Am Ende der Bearbeitung daher ggf.
            `leere_gruppen_entfernen` aufrufen!

        Args:
            gleis: Das Gleis, dessen Elternknoten ersetzt werden soll. Kann auch ein Element
                einer höheren Ebene sein, so lange die Ebene tiefer ist als die von `new_parent`.
            new_parent: Der neue Elternknoten des Gleises. Gibt den Typ und Namen des neuen
                Elternknotens an. Der Knoten kann existieren oder wird aus einer Kopie des alten
                neu erstellt.
            new_data: Daten des neuen Elternknotens. Wenn None, werden die alten Daten verwendet.
            del_old_parent: Alten Knoten löschen, wenn er keine Kinder hat. Standardmäßig False.
            dry_run: True = prüfen, ob die Aktion möglich ist, Graph aber nicht verändern.
                Bei einem Fehler wird ein ValueError gemeldet.

        Returns:
            True, wenn erfolgreich.

        Raises:
            ValueError: Wenn der Stammknoten nicht gefunden wird oder das Gleis bereits zum neuen
                Stamm gehört.
        """

        old_path, old_parent, old_data = self._find_parent_to_replace(gleis, new_parent.typ)
        if old_parent is None:
            raise ValueError(f"Gleis {gleis} hat keinen Stammknoten vom Typ {new_parent.typ}!")
        if new_parent == old_parent:
            raise ValueError(f"Gleis {gleis} ist schon ein Mitglied von {new_parent}!")

        if new_data is None and not self.has_node(new_parent):
            new_data = old_data.copy()
        if new_data is not None:
            new_data['name'] = new_parent.name
            new_data['typ'] = new_parent.typ
            if not dry_run:
                self.add_node(new_parent, **new_data)

        for element in old_path:
            if self.has_edge(old_parent, element):
                data = self.get_edge_data(old_parent, element)
                if not dry_run:
                    self.add_edge(new_parent, element, **data)
                    self.nodes[element]['auto'] = False
                    self.remove_edge(old_parent, element)
            if self.has_edge(element, old_parent):
                data = self.get_edge_data(element, old_parent)
                if not dry_run:
                    self.add_edge(element, new_parent, **data)

        if not dry_run and del_old_parent and not any(self.successors(old_parent)):
            self.remove_node(old_parent)

        return dry_run or self.has_edge(new_parent, gleis)

    def gleis_bahnsteig(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnsteig nachschlagen.

        Nur für Bahnhofgleise.

        Args:
            gleis: Gleisname wie im STS.

        Returns:
            Bahnsteigname.

        Raises:
            KeyError: Wenn nicht gefunden.
        """

        bs = self.find_superior(BahnhofElement(BahnhofElement.Typ.GL, gleis), {BahnhofElement.Typ.BS})
        return bs.name

    def gleis_bahnhofteil(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhofteil nachschlagen.

        Nur für Bahnhofgleise.

        Args:
            gleis: Gleisname wie im STS.

        Returns:
            Bahnhofteilname.

        Raises:
            KeyError: Wenn nicht gefunden.
        """

        bft = self.find_superior(BahnhofElement(BahnhofElement.Typ.GL, gleis), {BahnhofElement.Typ.BFT})
        return bft.name

    def gleis_bahnhof(self, gleis: str) -> str:
        """
        Zu Gleis zugeordneten Bahnhof nachschlagen.

        Nur für Bahnhofgleise.

        Args:
            gleis: Gleisname wie im STS.

        Returns:
            Bahnhofname.

        Raises:
            KeyError: Wenn nicht gefunden.
        """

        bf = self.find_superior(BahnhofElement(BahnhofElement.Typ.GL, gleis), {BahnhofElement.Typ.BF})
        return bf.name

    def anschlussstelle(self, gleis: str) -> str:
        """
        Zu Anschlussgleis zugeordnete Anschlussstelle nachschlagen.

        Nur für Anschlussgleise.

        Args:
            gleis: Anschlussgleisname wie im STS.

        Returns:
            Name der Anschlussstelle.

        Raises:
            KeyError: Wenn nicht gefunden.
        """

        anst = self.find_superior(BahnhofElement(BahnhofElement.Typ.AGL, gleis), {BahnhofElement.Typ.ANST})
        return anst.name

    def bahnhofgleise(self, bahnhof: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhof gehörenden Gleise auf.

        Nur für Bahnhofgleise.

        Args:
            bahnhof: Name des Bahnhofs.

        Returns:
            Iterator von Gleisnamen.

        Raises:
            KeyError: Wenn der Bahnhof nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, BahnhofElement(BahnhofElement.Typ.BF, bahnhof)):
                assert  isinstance(child, BahnhofElement)
                if child.typ is BahnhofElement.Typ.GL:
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Bf {bahnhof} ist im Bahnhofgraph nicht verzeichnet.")

    def bahnhofteilgleise(self, bahnhofteil: str) -> Iterable[str]:
        """
        Listet die zu einem Bahnhofteil gehörenden Gleise auf.

        Nur für Bahnhofgleise.

        Args:
            bahnhofteil: Name des Bahnhofteils.

        Returns:
            Iterator von Gleisnamen.

        Raises:
            KeyError: Wenn der Bahnhofteil nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, BahnhofElement(BahnhofElement.Typ.BFT, bahnhofteil)):
                assert  isinstance(child, BahnhofElement)
                if child.typ is BahnhofElement.Typ.GL:
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Bft {bahnhofteil} ist im Bahnhofgraph nicht verzeichnet.")

    def anschlussgleise(self, anst: str) -> Iterable[str]:
        """
        Listet die zu einer Anschlussstelle gehörenden Gleise auf.

        Nur für Anschlussgleise.

        Args:
            anst: Name der Anschlussstelle.

        Returns:
            Iterator von Gleisnamen.

        Raises:
            KeyError: Wenn die Anst nicht gefunden wird.
        """

        try:
            for parent, child in nx.dfs_edges(self, BahnhofElement(BahnhofElement.Typ.ANST, anst)):
                assert isinstance(child, BahnhofElement)
                if child.typ is BahnhofElement.Typ.AGL:
                    yield child.name
        except nx.NetworkXError as e:
            logger.exception(e)
            raise KeyError(f"Anst {anst} ist im Bahnhofgraph nicht verzeichnet.")

    def bahnhoefe(self) -> Iterable[str]:
        """
        Listet alle Bahnhöfe auf.

        Returns:
            Iterator von Bahnhofnamen
        """

        for node in self.list_children(BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.BF), {BahnhofElement.Typ.BF}):
            assert isinstance(node, BahnhofElement)
            yield node.name

    def anschlussstellen(self) -> Iterable[str]:
        """
        Listet alle Anschlussstellen auf.

        Returns:
            Iterator von Anschlussstellennamen
        """

        for node in self.list_children(BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.ANST), {BahnhofElement.Typ.ANST}):
            yield node.name

    def hierarchical_index(self, elements: Iterable[BahnhofElement]) -> Dict[BahnhofElement, Tuple[Union[int, str], ...]]:
        """
        Erstellt einen hierarchischen Sortierindex von Gleisen.

        Der Index ist ein Dictionary mit folgenden Eigenschaften:

        Die Schlüssel sind Tupel mit den Namen aller Elemente im Pfad vom Root-Element zum jeweiligen Gleis.

        Namen, die numerische Elemente enthalten, werden zusätzlich aufgespalten,
        damit Gleisnummern numerisch sortiert werden.
        Die Aufspaltung wird vom Gleisschema durchgeführt.

        Der Dictionary kann in der sorted-Funktion verwendet werden:
        `gleise = sorted(result.keys(), key=result.get)`

        Args:
            elements: Liste von Gleisen (Bahnhofelemente vom Typ Gl oder Agl)
                Wenn leer oder None, werden alle Gleise und Anschlussgleise inkludiert.

        Returns:
            Zuordnung Gleis zu Sortierschlüssel.
        """

        if not elements:
            elements = self.list_by_type({BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL})

        sortierung = {}
        for be in elements:
            parents = [be] + list(self.list_parents(be))
            keys = []
            for e in reversed(parents):
                node = self.nodes[e]
                key = self.gleisschema.gleisname_sortkey(node.name)
                keys.append(node.get('ordnung', 0))
                keys.extend(key)
            sortierung[be] = tuple(keys)
        return sortierung

    def map_from_other_graph(self, original_element: BahnhofElement, original_graph: 'BahnhofGraph') -> Optional[BahnhofElement]:
        """
        Bahnhofelement von einem anderen Graphen übersetzen

        Wenn zwei Graphen dieselbe Anlage abbilden, übersetzt diese Methode ein Bahnhofelement des anderen Graphen
        anhand eines repräsentativen Gleises in ein Bahnhofelement des eigenen Graphen.
        Beide Graphen müssen dieselben Gleise enthalten.

        Args:
            original_element: BahnhofElement im anderen Graphen.
            original_graph: anderer BahnhofGraph, der original_element enthält.
        """

        if original_element.typ in {BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}:
            return original_element
        else:
            try:
                gl = next(original_graph.list_children(original_element, {BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}))
                result = self.find_superior(gl, {original_element.typ})
                return result
            except KeyError:
                return None

    def import_anlageninfo(self, anlageninfo: AnlagenInfo):
        """
        Importiert die Anlageninformation in den Stellwerksknoten.
        """

        anl_label = BahnhofElement(BahnhofElement.Typ.STW, anlageninfo.name)
        self.add_node(anl_label, typ=anl_label.typ, name=anl_label.name, auto=True, aid=anlageninfo.aid,
                      region=anlageninfo.region, build=anlageninfo.build, online=anlageninfo.online)
        self.gleisschema = Gleisschema.regionsschema(anlageninfo.name, anlageninfo.region)

    def import_bahnsteiggraph(self,
                              bahnsteiggraph: BahnsteigGraph,
                              gleisschema: Gleisschema):
        """
        Importiert Gleise und Bahnsteige aus einem Bahnsteiggraphen.
        """

        anl_label = self.root()
        bf_label = BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.BF)
        self.add_node(bf_label, typ=bf_label.typ, name=bf_label.name, auto=True)
        self.add_edge(anl_label, bf_label, typ=anl_label.typ, auto=True)

        for comp in nx.connected_components(bahnsteiggraph):
            gleis = str(min(comp, key=len))
            bft = gleisschema.bahnsteigname(gleis)
            bf = gleisschema.bahnhofname(bft)
            self.add_node(BahnhofElement(BahnhofElement.Typ.BF, bf), name=bf, typ=BahnhofElement.Typ.BF, auto=True)
            self.add_edge(bf_label, BahnhofElement(BahnhofElement.Typ.BF, bf), typ=bf_label.typ, auto=True)
            self.add_node(BahnhofElement(BahnhofElement.Typ.BFT, bft), name=bft, typ=BahnhofElement.Typ.BFT, auto=True)
            self.add_edge(BahnhofElement(BahnhofElement.Typ.BF, bf), BahnhofElement(BahnhofElement.Typ.BFT, bft), typ=BahnhofElement.Typ.BF, auto=True)

            for gleis in comp:
                bs = gleisschema.bahnsteigname(gleis)
                self.add_node(BahnhofElement(BahnhofElement.Typ.BS, bs), name=bs, typ=BahnhofElement.Typ.BS, gleise=1, auto=True)
                self.add_node(BahnhofElement(BahnhofElement.Typ.GL, gleis), name=gleis, typ=BahnhofElement.Typ.GL, gleise=1, auto=True)
                self.ziel_gleis[gleis] = BahnhofElement(BahnhofElement.Typ.GL, gleis)
                self.add_edge(BahnhofElement(BahnhofElement.Typ.BFT, bft), BahnhofElement(BahnhofElement.Typ.BS, bs), typ=BahnhofElement.Typ.BFT, auto=True)
                self.add_edge(BahnhofElement(BahnhofElement.Typ.BS, bs), BahnhofElement(BahnhofElement.Typ.GL, gleis), typ=BahnhofElement.Typ.BS, auto=True)

    def import_signalgraph(self,
                           signalgraph: SignalGraph,
                           gleisschema: Gleisschema):
        """
        Importiert Anschlussgleise aus einem Signalgraphen.
        """

        anl_label = self.root()
        bst_label = BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.ANST)
        self.add_node(bst_label, typ=bst_label.typ, name=bst_label.name, auto=True)
        self.add_edge(anl_label, bst_label, typ=anl_label.typ, auto=True)

        agl_gleise = {}
        for anschluss, data in signalgraph.nodes(data=True):
            if data.typ in {Knoten.Typ.EINFAHRT, Knoten.Typ.AUSFAHRT}:
                agl = data.name
                agl_label = BahnhofElement(BahnhofElement.Typ.AGL, agl)
                try:
                    agl_data = self.nodes[agl_label]
                except KeyError:
                    agl_data = BahnsteigGraphNode(name=agl, typ=BahnhofElement.Typ.AGL, enr=data.enr, gleise=0, auto=True)
                    agl_gleise[agl_label] = 0.

                if data.typ is Knoten.Typ.EINFAHRT:
                    agl_data.einfahrt = True
                    if agl_label in agl_gleise:
                        agl_gleise[agl_label] += 0.5
                if data.typ is Knoten.Typ.AUSFAHRT:
                    agl_data.ausfahrt = True
                    if agl_label in agl_gleise:
                        agl_gleise[agl_label] += 0.5

                anst = gleisschema.anschlussname(agl)
                anst_label = BahnhofElement(BahnhofElement.Typ.ANST, anst)
                self.add_node(agl_label, **agl_data)
                self.add_edge(bst_label, anst_label, typ=bst_label.typ, auto=True)
                self.ziel_gleis[data.enr] = agl_label
                self.add_node(anst_label, name=anst, typ=BahnhofElement.Typ.ANST, auto=True)
                self.add_edge(anst_label, agl_label, typ=BahnhofElement.Typ.ANST, auto=True)

        for agl_label, gleise in agl_gleise.items():
            self.nodes[agl_label]['gleise'] = int(gleise + 0.5)

    def import_konfiguration(self, elemente: Iterable[Dict[str, Any]]):
        """
        Konfiguration importieren

        Strategie:
            1. Alle Knoten von bestehendem Graph importieren.
                Kanten _nicht_ importieren, sondern Vorfahr im `stamm`-Attribut verzeichnen.
            2. Knoten mit Attributen aus Elementen importieren, bestehende überschreiben.
                Vorfahr im `stamm`-Attribut verzeichnen.
                In der Anlage nicht vorkommende Gleise nicht übernehmen.
            3. Kanten gem. `stamm`-Attribut schichtweise zur Vorfahrebene konstruieren,
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
                parent_node = next(self.list_parents(node), None)
                if parent_node is not None:
                    data.stamm = parent_node.name
                else:
                    data.stamm = None
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
            if "ordnung" in element:
                data["ordnung"] = element['ordnung']
            if "gleise" in element:
                data["gleise"] = element['gleise']
            if "flags" in element:
                data["sperrung"] = "S" in element['flags']
            if "linienstil" in element:
                data["linienstil"] = element['linienstil']

            if element['typ'] in {BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}:
                if node not in self:
                    logger.warning(f"Gleis {node} existiert nicht im Simulator")
                    continue

            # element einfuegen oder attribute aktualisieren
            konfig_graph.add_node(node, **data)

        original_count = len(list(new_graph.list_by_type({BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL})))
        konfig_count = len(list(konfig_graph.list_by_type({BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL})))
        logger.info(f"Konfiguration importieren. Original {original_count} Gleise, Konfiguration {konfig_count} Gleise")

        # Schritt 2.5: reine auto-Knoten filtern
        for node, data in konfig_graph.nodes(data=True):
            parent_typ = BahnhofElement.Typ(data['typ']).supertyp
            parent_node = BahnhofElement(parent_typ, data['stamm'])
            parent_auto = not konfig_graph.has_node(parent_node) or konfig_graph.nodes[parent_node]['auto']
            if node not in new_graph or not data.auto or not parent_auto:
                new_graph.add_node(node, **data)
            else:
                logger.debug(f"BahnhofGraph.import_konfiguration: Ignoriere Auto-Element {node}.")

        # Schritt 3: Kanten erstellen gem. stamm-Attributen
        TYPEN_FOLGE = [BahnhofElement.Typ.GL,
                       BahnhofElement.Typ.AGL,
                       BahnhofElement.Typ.BS,
                       BahnhofElement.Typ.BFT,
                       BahnhofElement.Typ.BF,
                       BahnhofElement.Typ.ANST]
        for typ in TYPEN_FOLGE:
            for node in new_graph.list_by_type({typ}):
                data = new_graph.nodes[node]
                try:
                    if typ is BahnhofElement.Typ.BF:
                        parent_node = BahnhofElement(BahnhofElement.Typ.BST, str(typ))
                    elif typ is BahnhofElement.Typ.ANST:
                        parent_node = BahnhofElement(BahnhofElement.Typ.BST, str(typ))
                    else:
                        parent_node = BahnhofElement(data['typ'].supertyp, data['stamm'])
                except KeyError:
                    continue
                if parent_node in new_graph:
                    new_graph.add_edge(parent_node, node, auto=data.get('auto', True))
                else:
                    logger.warning(f"BahnhofGraph.import_konfiguration: Fehlendes Stammelement {parent_node} zu {node}.")

        new_graph.add_edge(self.root(), BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.BF))
        new_graph.add_edge(self.root(), BahnhofElement(BahnhofElement.Typ.BST, BahnhofElement.Typ.ANST))

        # Schritt 4: kinder- und elternlose Knoten entfernen
        for typ in TYPEN_FOLGE:
            to_remove = set()
            for node in new_graph.list_by_type({typ}):
                if new_graph.in_degree(node) == 0:
                    to_remove.add(node)
                if typ in {BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}:
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
        for typ in [BahnhofElement.Typ.BS, BahnhofElement.Typ.BFT, BahnhofElement.Typ.BF, BahnhofElement.Typ.ANST]:
            entfernen = []
            for n in self.nodes():
                if n.typ is typ and self.out_degree[n] == 0:
                    entfernen.append(n)
            for n in entfernen:
                self.remove_node(n)

    def validate(self):
        """
        Vollständigkeit des Bahnhofgraphen prüfen.

        - Hat jedes Gleis eine zugeordnete Bst?
        - Hat jedes Element genau ein Stammelement?
        """

        logger.debug("Validating BahnhofGraph")
        for gl in self.list_by_type({BahnhofElement.Typ.GL, BahnhofElement.Typ.AGL}):
            if gl.typ is BahnhofElement.Typ.GL:
                check = {
                    BahnhofElement.Typ.GL, 
                    BahnhofElement.Typ.BS, 
                    BahnhofElement.Typ.BFT, 
                    BahnhofElement.Typ.BF, 
                    BahnhofElement.Typ.BST, 
                    BahnhofElement.Typ.STW,
                }
            elif gl.typ is BahnhofElement.Typ.AGL:
                check = {
                    BahnhofElement.Typ.AGL,
                    BahnhofElement.Typ.ANST,
                    BahnhofElement.Typ.BST,
                    BahnhofElement.Typ.STW,
                }
            else:
                raise ValueError(f"Ungültiger Gleistyp {gl}")

            try:
                for be in self.list_parents(gl):
                    check -= {be.typ}
                if not check:
                    logger.error(f"{gl} hat fehlende Eltern {check}")
            except KeyError as e:
                logger.exception(f"{gl} nicht im Bahnhofgraph", exc_info=e)

        for node, data in self.nodes(data=True):
            if self.in_degree(node) > 1:
                path = [str(node) for node in nx.ancestors(self, node)]
                logger.error(f"{node} hat mehrere Eltern. {path}")

    def export_konfiguration(self) -> Sequence[Dict[str, Union[str, int, float, bool]]]:
        """
        Bahnhofgraph exportieren für Konfigurationsdatei

        Returns:
            Liste von Bahnhof-Elementen für das `elemente`-Array gemäss `config.schema3.json`.
        """

        elemente = {}
        gleis_typen = {
            str(be)
            for be in [
                BahnhofElement.Typ.GL,
                BahnhofElement.Typ.BS,
                BahnhofElement.Typ.AGL,
            ]
        }
        bahnhof_typen = {
            str(be)
            for be in [
                BahnhofElement.Typ.BF,
                BahnhofElement.Typ.ANST,
            ]
        }

        for e1, e2 in self.edges():
            # e1 ist der Stammknoten
            if e1.typ is BahnhofElement.Typ.STW:
                continue
            data1: BahnsteigGraphNode = self.nodes[e1]
            data2: BahnsteigGraphNode = self.nodes[e2]
            element = {'name': e2.name,
                       'typ': str(e2.typ),
                       'auto': data2.auto and data1.auto,
                       'ordnung': data2.get('ordnung', 0),
                       'sichtbar': True,
                       'flags': ''}
            if e1.typ is not BahnhofElement.Typ.BST:
                element['stamm'] = e1.name
            if data2.get('sperrung'):
                element['flags'] = 'S'
                element['auto'] = False
            if element['typ'] in gleis_typen:
                element['gleise'] = data2.get('gleise', 1)
            elif element['typ'] in bahnhof_typen:
                if stil := data2.get('linienstil'):
                    element['linienstil'] = stil
            elemente[e2] = element

        return list(elemente.values())
