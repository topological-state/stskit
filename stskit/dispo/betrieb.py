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

import networkx as nx

from stskit.dispo.anlage import Anlage
from stskit.model.journal import JournalEntry, JournalIDType, JournalEntryGroup
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

    def update(self, anlage: Anlage, config_path: os.PathLike):
        self.anlage = anlage
        self.journal_bereinigen()

    def abfahrt_abwarten(self,
                         wartende_abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         abzuwartende_abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 1,
                         journal: JournalEntryGroup | None = None,
                         dry_run: bool = False) -> JournalEntryGroup:
        """
        Abfahrt/Überholung abwarten

        Wird in folgenden Situationen angewendet:

        - Überholung durch einen anderen Zug.
        - Herstellung der gewünschten Zugreihenfolge.

        Ereignisse können als Ereignisse oder Fahrplanziele angegeben werden.
        In letzterem Fall wird zuerst das zugehörige Abfahrtsereignis (oder Ankunftsereignis bei Durchfahrt) gesucht.
        Ereignisse und Ziele können als Label oder Node Data angegeben werden.

        Bemerkung: Bei Durchfahrt kann ein Zug nicht warten.
        In diesem Fall wird implizit ein Betriebshalt eingefügt.

        wartende_abfahrt: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
        abzuwartende_abfahrt: Abzuwartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Abfahrt abwarten"
            journal.timestamp = self.anlage.simzeit_minuten

        abzuwartendes_label, _ = self._ereignis_label_finden(abzuwartende_abfahrt, {'Ab'})
        if abzuwartendes_label is None:
            abzuwartendes_label, _ = self._ereignis_label_finden(abzuwartende_abfahrt, {'An'})
            wartezeit = max(1, wartezeit)

        wartendes_label, wartendes_data = self._wartende_abfahrt_suchen(journal, wartende_abfahrt)

        if wartendes_label and abzuwartendes_label:
            egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartendes_label)
            edge = EreignisGraphEdge(typ="A", zid=wartendes_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
            egj.add_edge(abzuwartendes_label, wartendes_label, **edge)
            journal.add_entry(egj)
            journal.valid = True

        if not dry_run and journal.valid:
            bst = wartendes_data.plan_bst
            jid = JournalIDType("Abfahrt", wartendes_label.zid, bst)
            self._journal_anwenden(jid, journal)

        return journal

    def ankunft_abwarten(self,
                         wartende_abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         abzuwartende_ankunft: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                         wartezeit: int = 0,
                         journal: JournalEntryGroup | None = None,
                         dry_run: bool = False) -> JournalEntryGroup:
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
        In diesem Fall wird implizit ein Betriebshalt eingefügt.

        wartende_abfahrt: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
        abzuwartende_ankunft: Abzuwartende Ankunft (Ereignis- oder Ziel-, -Label oder -Daten).
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Ankunft abwarten"
            journal.timestamp = self.anlage.simzeit_minuten

        abzuwartendes_label, _ = self._ereignis_label_finden(abzuwartende_ankunft, {'An'})

        wartendes_label, wartendes_data = self._wartende_abfahrt_suchen(journal, wartende_abfahrt)

        if wartendes_label and abzuwartendes_label:
            egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartendes_label)
            edge = EreignisGraphEdge(typ="A", zid=wartendes_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
            egj.add_edge(abzuwartendes_label, wartendes_label, **edge)
            journal.add_entry(egj)
            journal.valid = True

        if not dry_run and journal.valid:
            bst = wartendes_data.plan_bst
            jid = JournalIDType("Ankunft", wartendes_label.zid, bst)
            self._journal_anwenden(jid, journal)

        return journal

    def _wartende_abfahrt_suchen(self,
                                 journal: JournalEntryGroup,
                                 wartend: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode) -> Tuple[EreignisLabelType | None, EreignisGraphNode | None]:

        """
        Abfahrtsereignis des wartenden Zuges suchen oder erstellen

        Erstellt ggf. einen Betriebshalt
        """

        label, data = self._ereignis_label_finden(wartend, {'Ab'})
        if label is None:
            label, data = self._ereignis_label_finden(wartend, {'An'})
            if label is not None:
                try:
                    label, data = self._betriebshalt_statt_durchfahrt(journal, label, 1)
                except ValueError:
                    label = data = None

        return label, data

    def kreuzung_abwarten(self,
                          ankunft1_label: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          ankunft2_label: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int = 0,
                          journal: JournalEntryGroup | None = None,
                          dry_run: bool = False) -> JournalEntryGroup:
        """
        Kreuzung abwarten

        Wird in folgenden Situationen angewendet:

        - Kreuzung auf eingleisiger Strecke.

        Zuege können als Ereignisse oder Fahrplanziele angegeben werden.
        In letzterem Fall wird zuerst das zugehörige Ankunftsereignis gesucht.
        Ereignisse und Ziele können als Label oder Node Data angegeben werden.

        Bemerkung: Bei Durchfahrt kann ein Zug nicht warten.
        In diesem Fall wird implizit ein Betriebshalt eingefügt.

        ankunft1, ankunft2: Ankunftsereignisse der kreuzenden Zuege (Ereignis- oder Ziel-, -Label oder -Daten)
        wartezeit: Zusätzliche Wartezeit
        dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Kreuzung"
            journal.timestamp = self.anlage.simzeit_minuten

        ankunft1_label, _ = self._ereignis_label_finden(ankunft1_label, {'An'})
        ankunft2_label, _ = self._ereignis_label_finden(ankunft2_label, {'An'})
        if ankunft1_label is None or ankunft2_label is None:
            return journal

        next1 = self.anlage.dispo_ereignisgraph.next_ereignis(ankunft1_label)
        abfahrt1_label, abfahrt1_data = self._wartende_abfahrt_suchen(journal, next1)
        next2 = self.anlage.dispo_ereignisgraph.next_ereignis(ankunft2_label)
        abfahrt2_label, abfahrt2_data = self._wartende_abfahrt_suchen(journal, next2)
        if abfahrt1_label is None or abfahrt2_label is None:
            return journal

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=abfahrt1_label)
        edge = EreignisGraphEdge(typ="A", zid=abfahrt1_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj.add_edge(ankunft2_label, abfahrt1_label, **edge)
        journal.add_entry(egj)

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=abfahrt2_label)
        edge = EreignisGraphEdge(typ="A", zid=abfahrt2_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj.add_edge(ankunft1_label, abfahrt2_label, **edge)
        journal.add_entry(egj)

        journal.valid = True

        if not dry_run and journal.valid:
            abfahrt_data = abfahrt1_data if abfahrt1_label.zeit <= abfahrt2_label.zeit else abfahrt2_data
            jid = JournalIDType("Kreuzung", abfahrt_data.zid, abfahrt_data.plan_bst)
            self._journal_anwenden(jid, journal)

        return journal

    def zug_folgen(self):
        pass

    def trasse_verschieben(self):
        pass

    def _ereignis_label_finden(self,
                               objekt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                               typen: Set[str]) -> Tuple[EreignisLabelType | None, EreignisGraphNode | None]:
        """
        Ereignislabel zu Ziel- oder Ereignis-Argument herausfinden

        Unterscheidung von Argumenten:
        Ereignislabel: NamedTuple(zid, zeit, typ)
        Ereignisdaten: Attribut node_id
        Ziellabel: NamedTuple(zid, zeit, ort)
        Zieldaten: Attribut fid
        """

        data = None

        if hasattr(objekt, "node_id"):
            data = objekt
            objekt = objekt.node_id

        if hasattr(objekt, "zid") and hasattr(objekt, "ort") and hasattr(objekt, "zeit"):
            objekt = self.anlage.dispo_zielgraph.nodes[objekt]
            data = None

        if hasattr(objekt, "fid"):
            for label in self.anlage.dispo_ereignisgraph.zugpfad(objekt.zid):
                data = self.anlage.dispo_ereignisgraph.nodes[label]
                if (data.typ in typen and
                        data.plan == objekt.plan and
                        objekt.p_an - 0.001 <= data.t_plan <= objekt.p_ab + 0.001):
                    objekt = label
                    break
            else:
                objekt = None
                data = None

        if data is None and self.anlage.dispo_ereignisgraph.has_node(objekt):
            data = self.anlage.dispo_ereignisgraph.nodes[objekt]

        return objekt, data

    def _journal_anwenden(self, jid: JournalIDType, journal: JournalEntryGroup):
        self.anlage.dispo_journal.add_entry(jid, journal)
        gm = {'ereignisgraph': self.anlage.dispo_ereignisgraph,
              'zielgraph': self.anlage.dispo_zielgraph}
        journal.replay(graph_map=gm)

    def journal_bereinigen(self):
        """
        Vergangene Abhaengigkeiten bereinigen
        """

        entfernen = []
        for jid, j in self.anlage.dispo_journal.entries.items():
            if not self.anlage.zuggraph.has_node(jid.zid) or self.anlage.zuggraph.nodes[jid.zid].get("ausgefahren", False):
                entfernen.append(jid)
                continue

            for node in j.target_nodes():
                if self.anlage.dispo_ereignisgraph.has_node(node):
                    data = self.anlage.dispo_ereignisgraph.nodes[node]
                    if data.get("t_mess") is None:
                        break
            else:
                entfernen.append(jid)
        for jid in entfernen:
            self.anlage.dispo_journal.delete_entry(jid)

    def vorzeitige_abfahrt(self,
                           abfahrt_label: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                           verfruehung: int,
                           relativ: bool = False):
        """
        Vorzeitige Abfahrt
        """

        journal = JournalEntryGroup()
        journal.title = "Vorzeitige Abfahrt"
        journal.timestamp = self.anlage.simzeit_minuten

        abfahrt_label, abfahrt_data = self._ereignis_label_finden(abfahrt_label, {'Ab'})
        if abfahrt_label:
            self._wartezeit_aendern(journal, abfahrt_label, "H", -verfruehung, relativ=relativ)

        if journal.valid:
            jid = JournalIDType("Wartezeit", abfahrt_data.zid, abfahrt_data.plan_bst)
            self._journal_anwenden(jid, journal)

    def wartezeit_aendern(self,
                          abfahrt_label: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int,
                          relativ: bool = False):
        """
        Wartezeit ändern
        """

        journal = JournalEntryGroup()
        journal.title = "Wartezeit ändern"
        journal.timestamp = self.anlage.simzeit_minuten

        abfahrt_label, abfahrt_data = self._ereignis_label_finden(abfahrt_label, {'Ab'})
        if abfahrt_label:
            self._wartezeit_aendern(journal, abfahrt_label, "A", wartezeit, relativ=relativ)

        if journal.valid:
            jid = JournalIDType("Wartezeit", abfahrt_data.zid, abfahrt_data.plan_bst)
            self._journal_anwenden(jid, journal)
            logger.debug(f"Wartezeit geändert, {jid}")

    def _wartezeit_aendern(self,
                           journal: JournalEntryGroup,
                           ereignis: EreignisLabelType,
                           kantentyp: str,
                           wartezeit: int,
                           relativ: bool = False):

        n = ereignis
        eg = self.anlage.dispo_ereignisgraph
        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=n)

        for pre in eg.predecessors(n):
            edge_data = eg.edges[(pre, n)]
            if edge_data.typ != kantentyp:
                continue

            if relativ:
                try:
                    startwert = edge_data.dt_fdl
                except (AttributeError, KeyError):
                    startwert = 0
                dt = startwert + wartezeit
            else:
                dt = wartezeit
            egj.change_edge(pre, n, dt_fdl=dt)

        journal.add_entry(egj)

    def abfahrt_zuruecksetzen(self,
                              wartend: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                              abzuwarten: Optional[Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode]] = None):
        """
        Abfahrtskorrektur zurücksetzen

        subjekt: Wartende Abfahrt
        objekt: Abzuwartendes Ereignis (Label oder zugeordnete node data).
            Wenn None (default), werden alle eingehenden Abhängigkeiten des Abfahrtsereignisses gelöscht.
            Im Moment nicht verwendet.
        """

        # wartend_label, _ = self._ereignis_label_finden(wartend, {'Ab', 'An'})
        zid = wartend.zid
        loeschen = []
        for jid, j in self.anlage.dispo_journal.entries.items():
            zids = {node.zid for node in j.target_nodes() if hasattr(node, 'zid')}
            if zid in zids and jid.typ in {"Ankunft", "Abfahrt", "Kreuzung"}:
                loeschen.append(jid)
        for jid in loeschen:
            self.anlage.dispo_journal.delete_entry(jid)
            logger.debug("Korrektur gelöscht: {jid}")

    def _betriebshalt_statt_durchfahrt(self,
                                       journal: JournalEntryGroup,
                                       durchfahrt: EreignisLabelType,
                                       wartezeit: int = 1) -> Tuple[EreignisLabelType, EreignisGraphNode]:

        """
        Betriebshalt statt Durchfahrt

        Ersetzt die Ereignisfolge `Ab1 --P--> An2 --P--> An3` (Durchfahrt in 2)
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`
        Es werden ein neuer Knoten und zwei neue Kanten eingefuegt.
        Die Kante von An2 nach An3 wird entfernt.

        durchfahrt: Durchfahrtsereignis An2

        Return
        ------

        Ereignislabel des Abfahrtsknotens

        Exceptions
        ----------

        ValueError: Betriebshalt konnte nicht gesetzt werden.
        """

        eg = self.anlage.dispo_ereignisgraph
        zg = self.anlage.dispo_zielgraph

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
        ab2_node.quelle = 'fdl'
        ab2_label = ab2_node.node_id

        halt_edge = copy.copy(edge_alt)
        halt_edge.typ = 'B'
        halt_edge.quelle = 'fdl'
        halt_edge.dt_min = 0
        halt_edge.dt_max = math.inf
        halt_edge.dt_fdl = wartezeit
        halt_edge.ds = 0

        abfahrt_edge = copy.copy(edge_alt)
        abfahrt_edge.quelle = 'fdl'

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=ab2_label)
        egj.add_node(ab2_label, **ab2_node)
        egj.add_edge(an2_label, ab2_label, **halt_edge)
        egj.add_edge(ab2_label, an3_label, **abfahrt_edge)
        egj.remove_edge(an2_label, an3_label)
        journal.add_entry(egj)

        zgj = JournalEntry[str, ZielLabelType, ZielGraphNode](target_graph='zielgraph', target_node=an2_node.fid)
        ziel = zg.nodes[an2_node.fid]
        zgj.change_node(an2_node.fid, flags=ziel.flags.replace('D', ''))
        journal.add_entry(zgj)

        logger.debug(f"Betriebshalt erstellt")
        logger.debug(f"    Ankunft: {self.anlage.dispo_ereignisgraph.node_info(an2_label)}")
        logger.debug(f"    Abfahrt: {self.anlage.dispo_ereignisgraph.node_info(ab2_label)}")

        assert isinstance(ab2_label, EreignisLabelType)
        assert isinstance(ab2_node, EreignisGraphNode)
        return ab2_label, ab2_node

    def _betriebshalt_auf_strecke(self,
                                  journal: JournalEntryGroup,
                                  vorher: EreignisLabelType,
                                  bst: BahnhofElement,
                                  wartezeit: int = 1) -> Tuple[EreignisLabelType, EreignisGraphNode]:

        """
        Betriebshalt unterwegs (Bst nicht im Fahrplan)

        Ersetzt die Ereignisfolge `Ab1 --P-> An3`
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`.
        Es werden zwei neue Knoten und drei neue Kanten eingefuegt.
        Die Kante von Ab1 nach An3 wird entfernt.

        Argumente
        ---------

        vorher: Vorhergehendes Ereignis im Ereignisgraph

        bst: Plangleis in Betriebsstellen-Notation. Muss vom Typ 'Gl' sein.

        Return
        ------

        Ereignislabel des Abfahrtsknotens

        Exceptions
        ----------

        ValueError: Betriebshalt konnte nicht gesetzt werden.
        """

        eg = self.anlage.dispo_ereignisgraph
        zg = self.anlage.dispo_zielgraph

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
        if bst.typ != 'Gl':
            raise ValueError(f"Ungültige Gleisbezeichnung {bst}.")

        teiler: float = 0.5

        an2_node = copy.copy(ab1_node)
        an2_node.quelle = 'fdl'
        an2_node.typ = 'An'
        an2_node.fid = None
        an2_node.plan = an2_node.gleis = bst.name
        an2_node.plan_bst = an2_node.gleis_bst = bst
        an2_node.t_plan = an2_node.zeit = ab1_node.zeit + teiler * (an3_node.zeit - ab1_node.zeit)
        an2_node.t_mess = None
        an2_node.s = an2_node.zeit = ab1_node.s + teiler * (an3_node.s - ab1_node.s)
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

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=ab2_label)
        egj.add_node(ab2_label, **ab2_node)
        egj.add_node(an2_label, **an2_node)
        egj.add_edge(ab1_label, an2_label, **ankunft_edge)
        egj.add_edge(an2_label, ab2_label, **halt_edge)
        egj.add_edge(ab2_label, an3_label, **abfahrt_edge)
        egj.remove_edge(ab1_label, an3_label)
        journal.add_entry(egj)

        # todo : zielgraph?

        logger.debug(f"Betriebshalt erstellt")
        logger.debug(f"    Ankunft: {self.anlage.dispo_ereignisgraph.node_info(an2_label)}")
        logger.debug(f"    Abfahrt: {self.anlage.dispo_ereignisgraph.node_info(ab2_label)}")
        logger.debug(f"    vorher:  {self.anlage.dispo_ereignisgraph.node_info(vorher)}")

        return ab2_label, ab2_node

    def betriebshalt_einfuegen(self,
                               vorheriges_ziel: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                               gleis: Union[str, BahnhofElement],
                               wartezeit: int = 1,
                               journal: JournalEntryGroup | None = None,
                               dry_run: bool = False) -> JournalEntryGroup:
        """
        Betriebshalt einfügen

        Wenn das angegebene Fahrziel/Ereignis eine Durchfahrt bezeichnet,
        wird die Durchfahrt in einen Betriebshalt umgewandelt.
        Ansonsten wird ein neues Fahrziel eingefügt.

        vorheriges_ziel: Vorheriges Abfahrts- oder Durchfahrtsereignis.
        gleis: Gleis, an dem gehalten wird.
        wartezeit: Wartezeit in Minuten
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Betriebshalt"
            journal.timestamp = self.anlage.simzeit_minuten

        vorher_label, _ = self._ereignis_label_finden(vorheriges_ziel, {'Ab'})
        if vorher_label is None:
            vorher_label, _ = self._ereignis_label_finden(vorheriges_ziel, {'An'})
        if vorher_label is None:
            return journal

        if vorher_label.typ == 'Ab':
            if not hasattr(gleis, 'typ'):
                gleis = BahnhofElement('Gl', gleis)
            abfahrt_label, abfahrt_data = self._betriebshalt_auf_strecke(journal, vorher_label, gleis, wartezeit)
        elif vorher_label.typ == 'An':
            abfahrt_label, abfahrt_data = self._betriebshalt_statt_durchfahrt(journal, vorher_label, wartezeit)
        else:
            return journal

        journal.valid = True

        if not dry_run and journal.valid:
            jid = JournalIDType(typ="Betriebshalt", zid=abfahrt_label.zid, bst=abfahrt_data.plan_bst)
            self._journal_anwenden(jid, journal)

        return journal

    def betriebshalt_loeschen(self, halt_ereignis: EreignisLabelType):
        """
        Betriebshalt aus Ereignisgraph loeschen

        Der Betriebshalt wird aus dem Dispojournal gelöscht.
        Der Ereignisgraph wird direkt nicht verändert und muss neu aufgebaut werden.

        halt_ereignis: Ereignislabel von An2 oder Ab2
        """

        ereignis_label, ereignis_data = self._ereignis_label_finden(halt_ereignis, {'An'})
        if ereignis_label is None:
            return

        for jid in self.anlage.dispo_journal.entries:
            if jid.typ == "Betriebshalt" and jid.zid == ereignis_label.zid:
                self.anlage.dispo_journal.delete_entry(jid)
                logger.debug("Betriebshalt gelöscht: {jid}")

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
