"""
Das Journal führt eine Liste von Fdl-Änderungen an den graphbasierten Betriebsdaten.
Diese Änderungen können z.B. nach einem neuen Import vom Simulator auf die jeweiligen Graphen aufgespielt werden,
um den Betriebszustand wiederherzustellen.
"""

from collections import defaultdict
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
                 target_graph: Optional[Hashable] = None,
                 target_node: Optional[Hashable] = None):
        self.target_graph = target_graph
        self.target_node = target_node
        self.removed_nodes: Set[Hashable] = set()
        self.added_nodes: Dict[Hashable, Mapping] = {}
        self.changed_nodes: Dict[Hashable, Mapping] = {}
        self.removed_edges: Set[Tuple[Hashable, Hashable]] = set()
        self.added_edges: Dict[Tuple[Hashable, Hashable], Mapping] = {}
        self.changed_edges: Dict[Tuple[Hashable, Hashable], Mapping] = {}

    def nodes(self) -> Set[Tuple[Hashable, Hashable]]:
        """
        Betroffene Knoten auflisten
        """

        _nodes = {self.target_node}
        _nodes.update(self.removed_nodes)
        _nodes.update(self.added_nodes)
        _nodes.update(self.changed_nodes)
        _nodes.update((e[0] for e in self.removed_edges))
        _nodes.update((e[1] for e in self.removed_edges))
        _nodes.update((e[0] for e in self.added_edges))
        _nodes.update((e[1] for e in self.added_edges))
        _nodes.update((e[0] for e in self.changed_edges))
        _nodes.update((e[1] for e in self.changed_edges))
        _nodes.discard(None)

        return _nodes

    def summary(self) -> Dict[Tuple[Hashable, Hashable], Set[str]]:
        """
        Zusammenfassung von Aenderungen

        Listet zu jedem betroffenen Knoten die gemachten Aenderungen.
        Die Aenderungen werden als String in einem Set wiedergegeben.
        '.' steht fuer den Targetknoten, '+' fuer einen neuen Knoten, '-' fuer einen geloeschten Knoten
        und '*' fuer einen geaenderten Knoten.
        """

        target = defaultdict(set)
        if self.target_node is not None:
            target[(self.target_graph, self.target_node)] = {'.'}

        removed = defaultdict(set)
        removed.update({(self.target_graph, n): {'-'} for n in self.removed_nodes})
        removed.update({(self.target_graph, e[0]): {'-'} for e in self.removed_edges})
        removed.update({(self.target_graph, e[1]): {'-'} for e in self.removed_edges})

        added = defaultdict(set)
        added.update({(self.target_graph, n): {'+'} for n in self.added_nodes})
        added.update({(self.target_graph, e[0]): {'+'} for e in self.added_edges})
        added.update({(self.target_graph, e[1]): {'+'} for e in self.added_edges})

        changed = defaultdict(set)
        changed.update({(self.target_graph, n): {'*'} for n in self.changed_nodes})
        changed.update({(self.target_graph, e[0]): {'*'} for e in self.changed_edges})
        changed.update({(self.target_graph, e[1]): {'*'} for e in self.changed_edges})

        nodes = target | removed | added | changed
        result = {n: target[n] | removed[n] | added[n] | changed[n] for n in nodes}

        return result

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

    def remove_node(self, n: Hashable):
        """
        Knoten löschen
        """

        self.removed_nodes.add(n)

    def remove_edge(self, u: Hashable, v: Hashable):
        """
        Kante löschen
        """

        self.removed_edges.add((u, v))

    def add_node(self, n: Hashable, **data):
        """
        Knoten hinzufügen

        Pro Knoten enthält das Journal nur einen Eintrag.
        Ein allfällig vorhandener Eintrag wird überschrieben.
        """

        self.added_nodes[n] = data

    def add_edge(self, u: Hashable, v: Hashable, **data):
        """
        Kante hinzufügen

        Pro Kante enthält das Journal nur einen Eintrag.
        Ein allfällig vorhandener Eintrag wird überschrieben.
        """

        self.added_edges[(u, v)] = data

    def change_node(self, n: Hashable, **data):
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

    def change_edge(self, u: Hashable, v: Hashable, **data):
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

    def replay(self, graph: Optional[nx.Graph] = None, graph_map: Optional[Mapping[Hashable, nx.Graph]] = None) -> Dict[str, Set[Hashable]]:
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

    def nodes(self) -> Set[Tuple[Hashable, Hashable]]:
        """
        Betroffene Knoten auflisten
        """

        nodes = [entry.nodes() for entry in self.entries]
        return set().union(*nodes)

    def summary(self) -> Dict[Tuple[Hashable, Hashable], Set[str]]:
        """
        Zusammenfassung von Aenderungen

        Listet zu jedem betroffenen Knoten die gemachten Aenderungen.
        Die Aenderungen werden als String in einem Set wiedergegeben.
        '.' steht fuer den Targetknoten, '+' fuer einen neuen Knoten, '-' fuer einen geloeschten Knoten
        und '*' fuer einen geaenderten Knoten.
        """

        summary: Dict[Tuple[Hashable, Hashable], Set[str]] = defaultdict(set)
        for entry in self.entries:
            entry_summary = entry.summary()
            for n in entry_summary:
                summary[n].update(entry_summary[n])

        return summary

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
