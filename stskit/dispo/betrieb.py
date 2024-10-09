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
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

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
                         wartend: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         abzuwarten: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 1,
                         dry_run: bool = False) -> Optional[Tuple[EreignisLabelType, EreignisLabelType]]:
        """
        Abfahrt/Überholung abwarten

        Wird in folgenden Situationen angewendet:

        - Überholung durch einen anderen Zug.
        - Herstellung der gewünschten Zugreihenfolge.

        Ereignisse können als Ereignisse oder Fahrplanziele angegeben werden.
        In letzterem Fall wird zuerst das zugehörige Abfahrtsereignis (oder Ankunftsereignis bei Durchfahrt) gesucht.
        Ereignisse und Ziele können als Label oder Node Data angegeben werden.

        Bemerkung: Bei Durchfahrt kann ein Zug nicht warten.
        In diesem Fall ist vorher ein Betriebshalt zu erstellen.

        wartend: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
        abzuwarten: Abzuwartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        wartend2 = self._get_ereignis_label(wartend, {'Ab'})
        abzuwarten2 = self._get_ereignis_label(abzuwarten, {'Ab'})
        if abzuwarten2 is None:
            abzuwarten2 = self._get_ereignis_label(abzuwarten, {'An'})
            wartezeit = max(1, wartezeit)
        if wartend2 and abzuwarten2:
            return self._abhaengigkeit_setzen(wartend2, abzuwarten2, wartezeit, dry_run)

    def ankunft_abwarten(self,
                         wartend: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         abzuwarten: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 1,
                         dry_run: bool = False) -> Optional[Tuple[EreignisLabelType, EreignisLabelType]]:
        """
        Ankunft/Kreuzung/Anschluss abwarten

        Wird in folgenden Situationen angewendet:

        - Abwarten eines Anschlusszuges für Umsteigepassagiere.
        - Kreuzung auf eingleisiger Strecke.
        - Herstellung der gewünschten Zugreihenfolge.

        Ereignisse können als Ereignisse oder Fahrplanziele angegeben werden.
        In letzterem Fall wird zuerst das zugehörige Ankunftsereignis gesucht.
        Ereignisse und Ziele können als Label oder Node Data angegeben werden.

        Bemerkung: Bei Durchfahrt kann ein Zug nicht warten.
        In diesem Fall ist vorher ein Betriebshalt zu erstellen.

        wartend: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
        abzuwarten: Abzuwartende Ankunft (Ereignis- oder Ziel-, -Label oder -Daten).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        wartend2 = self._get_ereignis_label(wartend, {'Ab'})
        abzuwarten2 = self._get_ereignis_label(abzuwarten, {'An'})
        if wartend2 and abzuwarten2:
            return self._abhaengigkeit_setzen(wartend2, abzuwarten2, wartezeit, dry_run)

    def _get_ereignis_label(self,
                            objekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                            typen: Set[str]):
        """
        Ereignislabel zu Ziel- oder Ereignis-Argument herausfinden

        Unterscheidung von Argumenten:
        Ereignislabel: NamedTuple(zid, zeit, typ)
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
                if (data.typ in typen and
                        data.plan == objekt.plan and
                        objekt.p_an - 0.001 <= data.t_plan <= objekt.p_ab + 0.001):
                    objekt = label
                    break
            else:
                objekt = None

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
        edge = EreignisGraphEdge(typ="A", zid=subjekt.zid, dt_fdl=wartezeit or 0, quelle='fdl')
        if eg.has_node(objekt) and eg.has_node(subjekt):
            if not dry_run:
                eg.add_edge(objekt, subjekt, **edge)
                self.abhaengigkeiten.add_edge(objekt, subjekt, dt_fdl=edge.dt_fdl)
                self.anlage.ereignisgraph.prognose()
                print("Abhängigkeit gesetzt:", subjekt, objekt, edge)
            return objekt, subjekt
        else:
            return None

    def vorzeitige_abfahrt(self,
                           abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                           verfruehung: int,
                           relativ: bool = False):

        abfahrt = self._get_ereignis_label(abfahrt, {'Ab'})
        if abfahrt:
            return self._wartezeit_aendern(abfahrt, "H", -verfruehung, relativ=relativ)

    def wartezeit_aendern(self,
                          abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int,
                          relativ: bool = False):

        abfahrt = self._get_ereignis_label(abfahrt, {'Ab'})
        if abfahrt:
            return self._wartezeit_aendern(abfahrt, "A", wartezeit, relativ=relativ)

    def _wartezeit_aendern(self,
                           ereignis: EreignisLabelType,
                           kantentyp: str,
                           wartezeit: int,
                           relativ: bool = False):

        n = ereignis
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
            print("Wartezeit geändert:", ereignis, pre, edge_data)
            update_noetig = True

        if update_noetig:
            self.anlage.ereignisgraph.prognose()

    def abfahrt_zuruecksetzen(self,
                              wartend: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                              abzuwarten: Optional[Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode]] = None):
        """
        Abfahrtsabhängigkeit zurücksetzen

        subjekt: Wartende Abfahrt
        objekt: Abzuwartendes Ereignis (Label oder zugeordnete node data).
            Wenn None (default), werden alle eingehenden Abhängigkeiten des Abfahrtsereignisses gelöscht.
        """

        wartend = self._get_ereignis_label(wartend, {'Ab'})
        if abzuwarten is not None:
            abzuwarten = self._get_ereignis_label(abzuwarten, {'An'})

        eg = self.anlage.ereignisgraph
        update_noetig = False

        if abzuwarten is None:
            preds = eg.predecessors(wartend)
        else:
            preds = [abzuwarten]

        loeschen = []
        for pre in preds:
            try:
                edge_data = eg.edges[(pre, wartend)]
            except KeyError:
                continue
            if edge_data.typ != 'A':
                continue

            loeschen.append((pre, wartend))
            update_noetig = True
            print("Abhängigkeit gelöscht:", wartend, pre, edge_data)

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
