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

    In der aktuellen Entwicklerversion werden ausgefahrene Züge beibehalten.
    Falls sich das als nicht praktikabel erweist, werden die Züge wie in der Zugliste gelöscht.
    """
    node_attr_dict_factory = ZugGraphNode
    edge_attr_dict_factory = ZugGraphEdge

    def to_undirected_class(self):
        return ZugGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def zug_details_importieren(self, zug: ZugDetails):
        """
        Einzelnen Zug im Zuggraph aktualisieren.

        Wenn der Zugknoten existiert wird er aktualisiert, sonst neu erstellt.
        """

        zug_data = ZugGraphNode.from_zug_details(zug)
        self.add_node(zug.zid, **zug_data)

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
