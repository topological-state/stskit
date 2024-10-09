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

import copy
import logging
import math
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from stskit.dispo.anlage import Anlage
from stskit.model.bahnhofgraph import BahnhofElement
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

    def _betriebshalt_statt_durchfahrt(self,
                                       durchfahrt: EreignisLabelType,
                                       wartezeit: int = 1):

        """
        Betriebshalt statt Durchfahrt

        Ersetzt die Ereignisfolge `Ab1 --P--> An2 --P--> An3` (Durchfahrt in 2)
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`
        Es werden ein neuer Knoten und zwei neue Kanten eingefuegt.
        Die Kante von An2 nach An3 wird entfernt.

        durchfahrt: Durchfahrtsereignis An2
        """

        eg = self.anlage.ereignisgraph

        an2_label = durchfahrt
        an3_label = eg.next_ereignis(an2_label)

        an2_node = eg.nodes[an2_label]
        an3_node = eg.nodes[an3_label]
        edge_alt = eg.edges[(an2_label, an3_label)]

        if edge_alt.typ != 'P':
            raise ValueError(f"Kante {an2_label}-{an3_label} (Typ {edge_alt.typ}) ist keine Planfahrt.")
        if an2_node.typ != 'An':
            raise ValueError(f"Ursprungsereignis {an2_label} ist keine Ankunft.")
        if an3_node.typ != 'An':
            raise ValueError(f"Folgeereignis {an3_label} ist keine Ankunft.")

        ab2_node = copy.copy(an2_node)
        ab2_node.typ = 'Ab'
        ab2_label = ab2_node.node_id

        halt_edge = copy.copy(edge_alt)
        halt_edge.typ = 'B'
        halt_edge.dt_min = 0
        halt_edge.dt_max = math.inf
        halt_edge.dt_fdl = wartezeit
        halt_edge.ds = 0

        abfahrt_edge = copy.copy(edge_alt)

        eg.add_node(ab2_label, **ab2_node)
        eg.add_edge(an2_label, ab2_label, **halt_edge)
        eg.add_edge(ab2_label, an3_label, **abfahrt_edge)
        eg.remove_edge(an2_label, an3_label)

    def _betriebshalt_auf_strecke(self,
                                  vorher: EreignisLabelType,
                                  bst: BahnhofElement,
                                  wartezeit: int = 1):

        """
        Betriebshalt unterwegs (Bst nicht im Fahrplan)

        Ersetzt die Ereignisfolge `Ab1 --P-> An3`
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`.
        Es werden zwei neue Knoten und drei neue Kanten eingefuegt.
        Die Kante von Ab1 nach An3 wird entfernt.
        """

        eg = self.anlage.ereignisgraph

        ab1_label = vorher
        an3_label = eg.next_ereignis(ab1_label)

        ab1_node = eg.nodes[ab1_label]
        an3_node = eg.nodes[an3_label]
        alt_edge = eg.edges[(ab1_label, an3_label)]

        if alt_edge.typ != 'P':
            raise ValueError(f"Abfolge {ab1_label}-{an3_label} ist keine Planfahrt.")
        if ab1_node.typ != 'Ab':
            raise ValueError(f"Ursprungsereignis {ab1_label} ist keine Abfahrt.")
        if an3_node.typ != 'An':
            raise ValueError(f"Folgeereignis {ab1_label} ist keine Ankunft.")

        teiler: float = 0.5

        an2_node = copy.copy(ab1_node)
        an2_node.quelle = 'fdl'
        an2_node.typ = 'An'
        an2_node.fid = None
        an2_node.plan = an2_node.gleis = bst.name
        an2_node.t_plan = an2_node.zeit = ab1_node.zeit + teiler * (an3_node.zeit - ab1_node.zeit)
        an2_node.t_mess = None
        an2_node.s = an2_node.zeit = ab1_node.s + teiler * (an3_node.s - ab1_node.s)
        an2_node.bst = self.anlage.bahnhofgraph.find_superior(bst, {"Bft"})
        an2_label = an2_node.node_id

        ab2_node = copy.copy(an2_node)
        ab2_node.typ = 'Ab'
        an2_node.t_plan = an2_node.zeit = ab1_node.zeit + (1. - teiler) * (an3_node.zeit - ab1_node.zeit)
        an2_node.s = an2_node.zeit = ab1_node.s + (1. - teiler) * (an3_node.s - ab1_node.s)
        ab2_label = ab2_node.node_id

        ankunft_edge = copy.copy(alt_edge)
        ankunft_edge.quelle = 'fdl'
        ankunft_edge.dt_min = alt_edge.dt_min * teiler
        ankunft_edge.ds = alt_edge.ds * teiler
        ankunft_edge.dt_max = math.inf
        ankunft_edge.dt_fdl = 0

        halt_edge = copy.copy(alt_edge)
        halt_edge.typ = 'B'
        halt_edge.dt_min = 0
        halt_edge.dt_max = math.inf
        halt_edge.dt_fdl = max(alt_edge.dt_fdl, wartezeit)
        halt_edge.ds = 0

        abfahrt_edge = copy.copy(alt_edge)
        abfahrt_edge.dt_min = alt_edge.dt_min * (1. - teiler)
        abfahrt_edge.ds = alt_edge.ds * (1. - teiler)
        abfahrt_edge.dt_max = math.inf
        abfahrt_edge.dt_fdl = 0

        eg.add_node(ab2_label, **ab2_node)
        eg.add_node(an2_label, **an2_node)
        eg.add_edge(ab1_label, an2_label, **ankunft_edge)
        eg.add_edge(an2_label, ab2_label, **halt_edge)
        eg.add_edge(ab2_label, an3_label, **abfahrt_edge)
        eg.remove_edge(ab1_label, an3_label)

    def _betriebshalt_loeschen(self, halt_ereignis: EreignisLabelType):
        """
        Betriebshalt aus Ereignisgraph loeschen

        Ersetzt die Ereignisfolge `Ab1 --P-> An2 --B-> Ab2 --P-> An3`
        durch `Ab1 --P--> An2 --P--> An3`, wenn An2 im Fahrplan ist,
        sonst `Ab1 --P--> An3`.

        halt_ereignis: Ereignislabel von An2 oder Ab2
        """
        eg = self.anlage.ereignisgraph

        halt_node = eg.nodes[halt_ereignis]
        if halt_node.typ == 'An':
            an2_label = halt_ereignis
            ab2_label = eg.next_ereignis(halt_ereignis)
        elif halt_node.typ == 'Ab':
            ab2_label = halt_ereignis
            an2_label = eg.prev_ereignis(halt_ereignis)
        else:
            raise ValueError(f"{halt_ereignis} ist kein Betriebshalt.")

        halt_edge = eg.edges[(an2_label, ab2_label)]

        an2_node = eg.nodes[an2_label]
        ab2_node = eg.nodes[ab2_label]

        ab1_label = eg.prev_ereignis(an2_label)
        an3_label = eg.next_ereignis(ab2_label)
        ab1_node = eg.nodes[ab1_label]
        an3_node = eg.nodes[an3_label]

        ankunft_edge = eg.edges[(ab1_label, an2_label)]
        abfahrt_edge = eg.edges[(ab2_label, an3_label)]

        if ankunft_edge.typ != 'P':
            raise ValueError(f"Abfolge {ab1_label}-{an2_label} ist keine Planfahrt.")
        if abfahrt_edge.typ != 'P':
            raise ValueError(f"Abfolge {ab2_label}-{an3_label} ist keine Planfahrt.")
        if ab1_node.typ != 'Ab':
            raise ValueError(f"Ursprungsereignis {ab1_label} ist keine Abfahrt.")
        if an3_node.typ != 'An':
            raise ValueError(f"Folgeereignis {ab1_label} ist keine Ankunft.")
        if halt_edge.typ != 'B':
            raise ValueError(f"Abfolge {an2_label}-{ab2_label} ist kein Betriebshalt.")

        if an2_node.fid:
            # An2 ist im Fahrplan
            edge_neu = copy.copy(abfahrt_edge)
            eg.remove_node(ab2_label)
            eg.add_edge(an2_label, an3_label, **edge_neu)
        else:
            # An2 ist nicht im Fahrplan
            edge_neu = copy.copy(ankunft_edge)
            edge_neu.dt_min = ankunft_edge.dt_min + abfahrt_edge.dt_min
            edge_neu.ds = ankunft_edge.ds + abfahrt_edge.ds
            edge_neu.dt_max = math.inf
            edge_neu.dt_fdl = 0

            eg.remove_node(an2_label)
            eg.remove_node(ab2_label)
            eg.add_edge(ab1_label, an3_label, **edge_neu)

    def betriebshalt_einfuegen(self,
                               vorheriges_ziel: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                               gleis: Union[str, BahnhofElement],
                               wartezeit: int = 1):
        """
        Betriebshalt einfügen

        Wenn das angegebene Fahrziel/Ereignis eine Durchfahrt bezeichnet,
        wird die Durchfahrt in einen Betriebshalt umgewandelt.
        Ansonsten wird ein neues Fahrziel eingefügt.

        vorheriges_ziel: Vorheriges Abfahrts- oder Durchfahrtsereignis.
        gleis: Gleis, an dem gehalten wird.
        wartezeit: Wartezeit in Minuten
        """

        vorher_label = self._get_ereignis_label(vorheriges_ziel, {'Ab'})
        if vorher_label is None:
            vorher_label = self._get_ereignis_label(vorheriges_ziel, {'An'})
        if vorher_label is None:
            raise ValueError(f"Ereignis {vorheriges_ziel} nicht gefunden.")

        if vorher_label.typ == 'Ab':
            if not hasattr(gleis, 'typ'):
                gleis = BahnhofElement('Gl', gleis)
            self._betriebshalt_auf_strecke(vorher_label, gleis, wartezeit)
        elif vorher_label.typ == 'An':
            self._betriebshalt_statt_durchfahrt(vorher_label, wartezeit)
        else:
            raise  ValueError(f"Kann nach Ereignis {vorheriges_ziel} keinen Betriebshalt einfügen.")

    def betriebshalt_loeschen(self, betriebshalt: EreignisLabelType):
        self._betriebshalt_loeschen(betriebshalt)

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
