import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.interface.stsobj import ZugDetails

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZugGraphNode(dict):
    obj = dict_property("obj", ZugDetails, docstring="Zugobjekt")
    zid = dict_property("zid", int, docstring="Zug-ID")
    name = dict_property("name", str)
    nummer = dict_property("nummer", int)
    gattung = dict_property("gattung", str)
    von = dict_property("von", str)
    nach = dict_property("nach", str)
    verspaetung = dict_property("verspaetung", Union[int, float], docstring="Verspaetung in Minuten")
    sichtbar = dict_property("sichtbar", bool)
    ausgefahren = dict_property("ausgefahren", bool)
    gleis = dict_property("gleis", str)
    plangleis = dict_property("plangleis", str)
    amgleis = dict_property("amgleis", bool)

    @classmethod
    def from_zug_details(cls, zug_details: ZugDetails):
        return cls(
            obj=zug_details,
            zid=zug_details.zid,
            name=zug_details.name,
            nummer=zug_details.nummer,
            gattung=zug_details.gattung,
            von=zug_details.von,
            nach=zug_details.nach,
            verspaetung=zug_details.verspaetung,
            sichtbar=zug_details.sichtbar,
            ausgefahren=False,
            gleis=zug_details.gleis,
            plangleis=zug_details.plangleis,
            amgleis=zug_details.amgleis)


class ZugGraphEdge(dict):
    typ = dict_property("typ", str,
                        docstring="""
                            Verbindungstyp
                                'P': planmässige Fahrt
                                'E': Ersatzzug
                                'F': Flügelung
                                'K': Kupplung
                            """)


class ZugGraph(nx.DiGraph):
    """
    Der _Zuggraph_ enthält alle Züge aus der Zugliste der Plugin-Schnittstelle als Knoten.
    Kanten werden aus den Ersatz-, Kuppeln- und Flügeln-Flags gebildet.

    Der Zuggraph verändert sich im Laufe eines Spiels.
    Neue Züge werden hinzugefügt.

    Der Zuggraph ist gerichtet.

    Attribute
    =========

    aenderungen: Dictionary Zug-ID -> ZugGraphNode.
        Der ZugGraphNode enthält die alten Werte der Attribute, die bei der letzten Aktualisierung geändert worden sind.
        Unveränderte Attribute sind nicht verzeichnet.
        Wenn der Zug neu ist, ist der Wert None.

        Der Besitzer darf Einträge des Dictionary löschen, z.B. via reset_aenderungen,
        sollte aber die Objekte nicht verändern.

        Die ZugGraphNode-Objekte sind unvollständig und sollten daher nicht direkt in den Graphen übernommen werden.
    """

    node_attr_dict_factory = ZugGraphNode
    edge_attr_dict_factory = ZugGraphEdge

    def to_undirected_class(self):
        return ZugGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.aenderungen: Dict[int, ZugGraphNode] = {}

    def reset_aenderungen(self):
        self.aenderungen = {}

    def zug_details_importieren(self, zug: ZugDetails) -> Optional[ZugGraphNode]:
        """
        Einzelnen Zug im Zuggraph aktualisieren.

        Wenn der Zugknoten existiert wird er aktualisiert, sonst neu erstellt.

        Die Änderungen werden in self.aenderungen verzeichnet und als Resultat zurückgegeben.

        :param zug: Zugdetails von der Pluginschnittstelle.

        :return: Wenn der Knoten bereits existiert hat, gibt die Methode ein ZugGraphNode-Objekt zurück,
            das nur die geänderten Attribute mit ihren vorherigen Werten enthält.
            Wenn der Knoten neu ist, wird None zurückgegeben.
            Das Objekt wird ausserdem in das aenderungen-Dictionary übernommen.
        """

        changes = {}
        zug_data = ZugGraphNode.from_zug_details(zug)
        if self.has_node(zug.zid):
            old_data = self.nodes(zug.zid)
            for key, data in zug_data.items():
                if key != "obj" and key in old_data:
                    if data != old_data[key]:
                        changes[key] = old_data[key]

        self.add_node(zug.zid, **zug_data)

        changed = ZugGraphNode(**changes) if changes else None
        self.aenderungen[zug.zid] = changed

        return changed

    def zuege_verknuepfen(self, typ: str, zid1: int, zid2: int):
        if zid1 != zid2:
            self.add_edge(zid1, zid2, typ=typ)


class ZugGraphUngerichtet(nx.Graph):
    """
    Ungerichtete Variante von ZugGraph
    """
    node_attr_dict_factory = ZugGraphNode
    edge_attr_dict_factory = ZugGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return ZugGraph
