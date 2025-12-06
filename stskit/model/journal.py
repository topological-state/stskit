"""
Das Journal führt eine Liste von Fdl-Änderungen an den graphbasierten Betriebsdaten.
Diese Änderungen können z.B. nach einem neuen Import vom Simulator auf die jeweiligen Graphen aufgespielt werden,
um den Betriebszustand wiederherzustellen.
"""

from typing import Any, Dict, Hashable, Iterable, List, Mapping, NamedTuple, Optional, Protocol, Sequence, Set, Tuple, Union

import networkx as nx

from stskit.model.bahnhofgraph import BahnhofElement


class JournalEntry:
    """
    Journal von Änderungen an einem Graphen.

    Das Journal enthält Einträge von gelöschten, eingefügten und geänderten Knoten und Kanten.
    Die Einträge werden in Sets bzw. Dictionaries gehalten und sind nach Knoten- bzw. Kantenlabel aufgeschlüsselt.

    Von gelöschten Knoten und Kanten werden nur die Labels gespeichert.
    Bei hinzugefügten und geänderten Knoten und Kanten werden die Knotendaten (Attribute) in Dictionaries mitgespeichert.
    Bei hinzugefügten sollten alle nötigen Attribute deklariert sein,
    bei geänderten nur die zu ändernden Attribute.
    Insbesondere sollten keine Defaultwerte übergeben werden!

    Änderungen werden über die bereitgestellten Methoden gemeldet.
    Das Journal kann darauf über die Replay-Methode auf einen Graphen angewendet werden.
    Der vorherige Zustand wird nicht gespeichert und kann nicht wiederhergestellt werden.

    Das Journal enthält zu jedem Knoten/jeder Kante maximal einen Lösch-, Einfügungs- und Änderungseintrag.
    Die Einträge Einfügen und Löschen wirken auf den gesamten Knoten bzw. Kante inklusive allen Attributen.
    Änderungen wirken auf einzelne Attribute. Die Änderungen werden gesammelt.
    """

    def __init__(self,
                 target_graph: Optional[Union[nx.Graph, Hashable]] = None,
                 target_node: Optional[Any] = None):
        self.target_graph = target_graph
        self.target_node = target_node
        self.removed_nodes: Set[Any] = set()
        self.added_nodes: Dict[Any, Any] = {}
        self.changed_nodes: Dict[Any, Any] = {}
        self.removed_edges: Set[Tuple[Any, Any]] = set()
        self.added_edges: Dict[Tuple[Any, Any], Any] = {}
        self.changed_edges: Dict[Tuple[Any, Any], Any] = {}

    def clear(self):
        """
        Journal löschen
        """

        self.removed_nodes = set()
        self.added_nodes = {}
        self.changed_nodes = {}
        self.removed_edges = set()
        self.added_edges = {}
        self.changed_edges = {}

    def remove_node(self, n):
        """
        Knoten löschen
        """

        self.removed_nodes.add(n)

    def remove_edge(self, u, v):
        """
        Kante löschen
        """

        self.removed_edges.add((u, v))

    def add_node(self, n, **data):
        """
        Knoten hinzufügen

        Pro Knoten enthält das Journal nur einen Eintrag.
        Ein allfällig vorhandener Eintrag wird überschrieben.
        """

        self.added_nodes[n] = data

    def add_edge(self, u, v, **data):
        """
        Kante hinzufügen

        Pro Kante enthält das Journal nur einen Eintrag.
        Ein allfällig vorhandener Eintrag wird überschrieben.
        """

        self.added_edges[(u, v)] = data

    def change_node(self, n, **data):
        """
        Knoten ändern

        Pro Knoten enthält das Journal nur einen Eintrag.
        Die zu ändernden Attribute werden in einen allfällig existierenden Eintrag übernommen.

        Vorsicht: Die Knotendaten sollten keine Attribute mit Defaultwerten enthalten!
        """

        if n in self.changed_nodes:
            self.changed_nodes[n].update(data)
        else:
            self.changed_nodes[n] = data

    def change_edge(self, u, v, **data):
        """
        Kantenanttribute ändern

        Pro Kante enthält das Journal nur einen Eintrag.
        Die zu ändernden Attribute werden in einen allfällig existierenden Eintrag übernommen.

        Vorsicht: Die Kantendaten sollten keine Attribute mit Defaultwerten enthalten!
        """

        if (u, v) in self.changed_edges:
            self.changed_edges[(u, v)].update(data)
        else:
            self.changed_edges[(u, v)] = data

    def merge(self, other: 'JournalEntry'):
        """
        Mit anderem Journal zusammenführen

        Hat den gleichen Effekt, wie wenn die add-, change-, remove-Methoden für jedes Element aufgerufen würden.
        """

        self.removed_edges.update(other.removed_edges)
        self.removed_nodes.update(other.removed_nodes)
        self.added_edges.update(other.added_edges)
        self.removed_nodes.update(other.removed_nodes)
        for edge, data in other.changed_edges.items():
            self.change_edge(*edge, **data)
        for node, data in other.changed_nodes.items():
            self.change_node(node, **data)

    def replay(self, graph: Optional[nx.Graph] = None, graph_map: Optional[Mapping[Any, nx.Graph]] = None) -> Dict[str, Set[Hashable]]:
        """
        Journal abspielen

        Die Abspielreihenfolge ist:

        1. Kanten löschen
           Der Knoten muss existieren, ansonsten bleibt die Änderung wirkungslos.
        2. Knoten löschen
           Die Kante muss existieren, ansonsten bleibt die Änderung wirkungslos.
        3. Knoten hinzufügen.
           Wenn der Knoten existiert, werden die Attribute gelöscht und überschrieben.
        4. Kanten hinzufügen
           Wenn die Kante existiert, werden die Attribute gelöscht und überschrieben.
        5. Knoten ändern
           Der Knoten muss existieren, ansonsten bleibt die Änderung wirkungslos.
           Im Änderungseintrag erfasste Attribute werden überschrieben, die übrigen bleiben bestehen.
        6. Knoten ändern
           Die Kante muss existieren, ansonsten bleibt die Änderung wirkungslos.
           Im Änderungseintrag erfasste Attribute werden überschrieben, die übrigen bleiben bestehen.

        Return
        ------

        Dictionary mit Fehlermeldungen.
        Moegliche Keys: 'remove_edge', 'add_edge', 'change_edge', 'remove_node', 'add_node', 'change_node'.
        Values: Set von edge oder node Labels.
        """

        fails = {}
        def _failed(operation, item):
            if operation in fails:
                fails[operation].add(item)
            else:
                fails[operation] = {item}

        if graph is None:
            graph = self.target_graph
        if not isinstance(graph, nx.Graph):
            graph = graph_map.get(graph)
        if graph is None:
            _failed('unresolved_target', self.target_graph)

        for edge in self.removed_edges:
            try:
                graph.remove_edge(*edge)
            except (AttributeError, nx.NetworkXError):
                _failed('remove_edge', edge)

        for label in self.removed_nodes:
            try:
                graph.remove_node(label)
            except (AttributeError, nx.NetworkXError):
                _failed('remove_node', label)

        for label, data in self.added_nodes.items():
            try:
                if graph.has_node(label):
                    graph.nodes[label].clear()
                graph.add_node(label, **data)
            except (AttributeError, nx.NetworkXError):
                _failed('add_node', label)

        for edge, data in self.added_edges.items():
            try:
                if graph.has_edge(*edge):
                    graph.edges[edge].clear()
                graph.add_edge(*edge, **data)
            except (AttributeError, nx.NetworkXError):
                _failed('add_edge', edge)

        for label, data in self.changed_nodes.items():
            try:
                if graph.has_node(label):
                    graph.add_node(label, **data)
                else:
                    _failed('change_node', label)
            except (AttributeError, nx.NetworkXError):
                _failed('change_node', label)

        for edge, data in self.changed_edges.items():
            try:
                if graph.has_edge(*edge):
                    graph.add_edge(*edge, **data)
                else:
                    _failed('change_edge', edge)
            except (AttributeError, nx.NetworkXError):
                _failed('change_edge', edge)

        return fails


class JournalEntryGroup:
    def __init__(self, *entries):
        self.entries: List[JournalEntry] = list(entries)

    def add_entry(self, entry: JournalEntry):
        self.entries.append(entry)

    def remove_entry(self, entry: JournalEntry):
        self.entries.remove(entry)

    def replay(self, graph_map: Optional[Union[Mapping[Hashable, nx.Graph]]] = None):
        for entry in self.entries:
            entry.replay(graph_map=graph_map)


class JournalIDType(NamedTuple):
    """
    Identifikation des Journals

    Ein Journal wird durch Typ, Zug, Bst identifiziert.
    """

    typ: str  # Betriebshalt, Ankunft, Abfahrt, Kreuzung
    zid: int
    bst: BahnhofElement

    def __str__(self):
        return f"{self.typ}, {self.zid}, {self.bst}"


class Journal:
    """
    Journal von Aenderungen an einem Graph

    Journal wird zum Erfassen von Fdl-Korrekturen an den Graphdaten verwendet.
    Es erlaubt, Aenderungen an verschiedenen Graphen unter einer Korrektur-ID zusammenzufassen.

    Anhand der Korrektur-ID können Journals wiedergefunden und gelöscht werden.
    Es werden dann jeweils alle zu einem Ereignis gehörenden Korrekturen gelöscht.
    """
    
    def __init__(self):
        self.entries: Dict[Hashable, Union[JournalEntry, JournalEntryGroup]] = {}

    def replay(self, graph_map: Optional[Union[Mapping[Hashable, nx.Graph]]] = None):
        for entry in self.entries.values():
            entry.replay(graph_map=graph_map)

    def add_entry(self, id_, *entries: JournalEntry):
        group = JournalEntryGroup(*entries)
        self.entries[id_] = group

    def delete_entry(self, id_: Hashable):
        del self.entries[id_]
