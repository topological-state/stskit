"""
Änderungen im Betriebsablauf verwalten

Dieses Modul stellt Klassen und Methoden bereit,
über die der Fdl Änderungen an der Anlage und am Fahrplan vornehmen kann.
Änderungen sollten nicht direkt an den Originaldaten vorgenommen werden.
Dank der zentralen Schnittstelle werden:
- Prozesse vereinheitlicht und delegiert,
- Konsistenz der Betriebsdaten sichergestellt,
- andere Module über die Änderungen informiert,
- (ev. später) Änderungen protokolliert und rücknehmbar,
- ...
"""

import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from stskit.dispo.anlage import Anlage
from stskit.model.ereignisgraph import EreignisGraph, EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.model.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode, ZielLabelType
from stskit.model.zuggraph import ZugGraph
from stskit.model.zugschema import Zugschema

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Betrieb:
    def __init__(self):
        self.anlage: Anlage = Anlage()
        self.abhaengigkeiten = EreignisGraph()

    def update(self, anlage: Anlage, config_path: os.PathLike):
        self.anlage = anlage

    def abfahrt_abwarten(self,
                         subjekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         objekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 1,
                         dry_run: bool = False) -> Optional[Tuple[EreignisLabelType, EreignisLabelType]]:
        """
        Abfahrt/Überholung abwarten

        Wird in folgenden Situationen angewendet:

        - Überholung durch einen anderen Zug.
        - Herstellung der gewünschten Zugreihenfolge.

        subjekt: Wartendes Abfahrtsereignis (Label oder zugeordnete node data)
        objekt: Abzuwartendes Abfahrtsereignis (Label oder zugeordnete node data).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        subjekt = self._get_ereignis_label(subjekt, 'Ab')
        objekt = self._get_ereignis_label(objekt, 'Ab')
        return self._abhaengigkeit_setzen(subjekt, objekt, wartezeit, dry_run)

    def ankunft_abwarten(self,
                         subjekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         objekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 1,
                         dry_run: bool = False) -> Optional[Tuple[EreignisLabelType, EreignisLabelType]]:
        """
        Ankunft/Kreuzung/Anschluss abwarten

        Wird in folgenden Situationen angewendet:

        - Abwarten eines Anschlusszuges für Umsteigepassagiere.
        - Kreuzung auf eingleisiger Strecke.
        - Herstellung der gewünschten Zugreihenfolge.

        subjekt: Wartendes Abfahrtsereignis (Label oder zugeordnete node data)
        objekt: Abzuwartendes Ankunftsereignis (Label oder zugeordnete node data).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        subjekt = self._get_ereignis_label(subjekt, 'Ab')
        objekt = self._get_ereignis_label(objekt, 'An')
        return self._abhaengigkeit_setzen(subjekt, objekt, wartezeit, dry_run)

    def _get_ereignis_label(self,
                            objekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                            typ: str):
        """
        Ereignislabel zu Ziel- oder Ereignis-Argument herausfinden

        Unterscheidung von Argumenten:
        Ereignislabel: NamedTuple(zid, eid)
        Ereignisdaten: Attribut node_id
        Ziellabel: NamedTuple(zid, zeit, ort)
        Zieldaten: Attribut fid
        """

        if hasattr(objekt, "node_id"):
            objekt = objekt.node_id

        if hasattr(objekt, "zid") and hasattr(objekt, "ort") and hasattr(objekt, "zeit"):
            objekt = self.anlage.zielgraph.nodes[objekt]

        if hasattr(objekt, "fid"):
            for label in self.anlage.ereignisgraph.zugpfad(objekt.zid):
                data = self.anlage.ereignisgraph.nodes[label]
                if (data.typ == typ and
                        data.plan == objekt.plan and
                        objekt.p_an - 0.001 <= data.t_plan <= objekt.p_ab + 0.001):
                    objekt = label
                    break
            else:
                return None

        return objekt

    def _abhaengigkeit_setzen(self,
                         subjekt: EreignisLabelType,
                         objekt: EreignisLabelType,
                         wartezeit: int,
                         dry_run: bool = False) -> Optional[Tuple[EreignisLabelType, EreignisLabelType]]:
        """
        Gemeinsamer Teil von Abfahrt/Ankunft abwarten
        """

        eg = self.anlage.ereignisgraph
        edge = EreignisGraphEdge(typ="A", zid=subjekt.zid, dt_fdl=wartezeit or 0)
        if eg.has_node(objekt) and eg.has_node(subjekt):
            if not dry_run:
                eg.add_edge(objekt, subjekt, **edge)
                self.abhaengigkeiten.add_edge(objekt, subjekt, dt_fdl=edge.dt_fdl)
                self.anlage.ereignisgraph.prognose()
                print("abhängigkeit gesetzt:", subjekt, objekt, edge)
            return objekt, subjekt
        else:
            return None

    def vorzeitige_abfahrt(self,
                           subjekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                           verfruehung: int,
                           relativ: bool = False):

        subjekt = self._get_ereignis_label(subjekt, 'Ab')
        return self._wartezeit_aendern(subjekt, "H", -verfruehung, relativ=relativ)

    def wartezeit_aendern(self,
                          subjekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int,
                          relativ: bool = False):

        subjekt = self._get_ereignis_label(subjekt, 'Ab')
        return self._wartezeit_aendern(subjekt, "A", wartezeit, relativ=relativ)

    def _wartezeit_aendern(self,
                           subjekt: EreignisLabelType,
                           kantentyp: str,
                           wartezeit: int,
                           relativ: bool = False):

        n = subjekt
        eg = self.anlage.ereignisgraph
        update_noetig = False
        for pre in eg.predecessors(n):
            edge_data = eg.edges[(pre, n)]
            if edge_data.typ != kantentyp:
                continue

            if relativ:
                try:
                    startwert = edge_data.dt_fdl
                except (AttributeError, KeyError):
                    startwert = 0
                edge_data.dt_fdl = startwert + wartezeit
            else:
                edge_data.dt_fdl = wartezeit
            self.abhaengigkeiten.add_edge(pre, n, dt_fdl=edge_data.dt_fdl)
            print("wartezeit geändert:", subjekt, pre, edge_data)
            update_noetig = True

        if update_noetig:
            self.anlage.ereignisgraph.prognose()

    def abfahrt_zuruecksetzen(self,
                              subjekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                              objekt: Optional[Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode]] = None):
        """
        Abfahrtsabhängigkeit zurücksetzen

        subjekt: Wartendes Abfahrtsereignis (Label oder zugeordnete node data)
        objekt: Abzuwartendes Ankunftsereignis (Label oder zugeordnete node data).
            Wenn None (default), werden alle eingehenden Abhängigkeiten des Abfahrtsereignisses gelöscht.
        """

        subjekt = self._get_ereignis_label(subjekt, 'Ab')
        if objekt is not None:
            objekt = self._get_ereignis_label(objekt, 'An')

        eg = self.anlage.ereignisgraph
        update_noetig = False

        if objekt is None:
            preds = eg.predecessors(subjekt)
        else:
            preds = [objekt]

        loeschen = []
        for pre in preds:
            try:
                edge_data = eg.edges[(pre, subjekt)]
            except KeyError:
                continue
            if edge_data.typ != 'A':
                continue

            loeschen.append((pre, subjekt))
            update_noetig = True
            print("abhängigkeit gelöscht:", subjekt, pre, edge_data)

        for edge in loeschen:
            try:
                eg.remove_edge(*edge)
            except KeyError:
                pass
            try:
                self.abhaengigkeiten.remove_edge(*edge)
            except KeyError:
                pass

        if update_noetig:
            self.anlage.ereignisgraph.prognose()

    def betriebshalt_einfuegen(self, vorheriges_ziel, bst, ankunftszeit, abfahrtszeit):
        pass

    def betriebshalt_loeschen(self, subjekt):
        pass

    def bst_verbinden(self):
        pass

    def bst_umbenennen(self):
        pass

    def bst_erstellen(self):
        pass

    def linie_aufbrechen(self):
        pass

    def linie_verbinden(self):
        pass
