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
import itertools
import logging
import math
import os
from typing import Any, Optional, Set, Tuple, Union

from stskit.dispo.anlage import Anlage
from stskit.model.journal import JournalEntry, JournalIDType, JournalEntryGroup
from stskit.model.bahnhofgraph import BahnhofElement
from stskit.model.ereignisgraph import EreignisGraph, EreignisGraphNode, EreignisGraphEdge, EreignisLabelType
from stskit.model.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode, ZielLabelType

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

        Args:
            wartende_abfahrt: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
            abzuwartende_abfahrt: Abzuwartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten).
            wartezeit: Zusätzliche Wartezeit
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
                Optional, per Default wird eine neue Journalgruppe angelegt.
            dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.

        Returns:
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.

        Raises:
            KeyError, ValueError
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Abfahrt abwarten"
            journal.timestamp = self.anlage.simzeit_minuten

        abzuwarten_label, abzuwarten_data = self._ereignis_label_finden(abzuwartende_abfahrt, {'Ab'})
        if abzuwarten_label is None:
            abzuwarten_label, _ = self._ereignis_label_finden(abzuwartende_abfahrt, {'An'})
            wartezeit = max(1, wartezeit)

        wartend_label, wartend_data = self._wartende_abfahrt_finden(journal, wartende_abfahrt)
        if wartend_label is None or abzuwarten_label is None:
            raise ValueError(f"Ungueltige Ereignisangaben {abzuwartende_abfahrt=} -> {wartende_abfahrt=}")

        abzuwarten_bst = self.anlage.bahnhofgraph.find_superior(abzuwarten_data.plan_bst, {'Bf', 'Anst'})
        wartend_bst = self.anlage.bahnhofgraph.find_superior(wartend_data.plan_bst, {'Bf', 'Anst'})

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartend_label)
        edge = EreignisGraphEdge(typ="A", zid=wartend_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj.add_edge(abzuwarten_label, wartend_label, **edge)
        journal.add_entry(egj)
        journal.valid = True

        if not dry_run and journal.valid:
            jid = JournalIDType("Abfahrt", wartend_label.zid, wartend_bst)
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

        Args:
            wartende_abfahrt: Wartende Abfahrt (Ereignis- oder Ziel-, -Label oder -Daten)
            abzuwartende_ankunft: Abzuwartende Ankunft (Ereignis- oder Ziel-, -Label oder -Daten).
            wartezeit: Zusätzliche Wartezeit
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
                Optional, per Default wird eine neue Journalgruppe angelegt.
            dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.

        Returns:
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.

        Raises:
            KeyError, ValueError
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Ankunft abwarten"
            journal.timestamp = self.anlage.simzeit_minuten

        abzuwarten_label, abzuwarten_data = self._ereignis_label_finden(abzuwartende_ankunft, {'An'})
        wartend_label, wartend_data = self._wartende_abfahrt_finden(journal, wartende_abfahrt)
        if wartend_label is None or abzuwarten_label is None:
            raise ValueError(f"Ungueltige Ereignisangaben {abzuwartende_ankunft=} -> {wartende_abfahrt=}")

        abzuwarten_bst = self.anlage.bahnhofgraph.find_superior(abzuwarten_data.plan_bst, {'Bf', 'Anst'})
        wartend_bst = self.anlage.bahnhofgraph.find_superior(wartend_data.plan_bst, {'Bf', 'Anst'})

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartend_label)
        edge = EreignisGraphEdge(typ="A", zid=wartend_label.zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj.add_edge(abzuwarten_label, wartend_label, **edge)
        journal.add_entry(egj)
        journal.valid = True

        if not dry_run and journal.valid:
            jid = JournalIDType("Ankunft", wartend_label.zid, wartend_bst)
            self._journal_anwenden(jid, journal)

        return journal

    def _wartende_abfahrt_finden(self,
                                 journal: JournalEntryGroup,
                                 wartend: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode) -> Tuple[EreignisLabelType | None, EreignisGraphNode | None]:
        """
        Abfahrtsereignis des wartenden Zuges suchen, ggf. Betriebshalt erstellen

        Erstellt einen Betriebshalt, wenn das Abfahrtereignis zu einer Durchfahrt (Kante vom Typ D) gehört.

        Args:
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
            wartend: Abfahrtereignis oder Fahrziel, wo der Zug warten soll.

        Returns:
            Ereignislabel und -daten der Abfahrt. None, wenn nicht gefunden.
        """

        abfahrt_data = None
        ankunft_label, abfahrt_label = self._ankunft_abfahrt_finden(wartend)
        kante = self.anlage.dispo_ereignisgraph.get_edge_data(ankunft_label, abfahrt_label)
        if kante is not None and kante.typ == 'D':
            abfahrt_label, abfahrt_data = self._betriebshalt_statt_durchfahrt(journal, ankunft_label, 1)
        elif abfahrt_data is None and abfahrt_label is not None:
            abfahrt_data = self.anlage.dispo_ereignisgraph.nodes[abfahrt_label]

        return abfahrt_label, abfahrt_data

    def kreuzung_abwarten(self,
                          *knoten: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int = 0,
                          journal: JournalEntryGroup | None = None,
                          dry_run: bool = False) -> JournalEntryGroup:
        """
        Kreuzung abwarten

        Zwei Züge kreuzen sich an einer Ausweichstelle auf einer eingleisigen Strecke.
        Der frühere wartet auf die Ankunft des späteren.
        Die Abhängigkeit ist symmetrisch, die Züge können frühestens abfahren, wenn beide angekommen sind.

        Züge können als Ereignisse oder Fahrplanziele angegeben werden.
        Ereignisse und Ziele können als Label oder Node Data angegeben werden.
        Im Fall von Ereignissen kann jeweils das zu dem Halt oder der Durchfahrt
        gehörende Ankunfts- oder Abfahrtsereignis angegeben werden.
        Beide Ziele müssen im gleichen Bahnhof liegen.

        Bei Durchfahrt wird implizit ein Betriebshalt eingefügt.

        Args:
            knoten: Ankünfte oder Abfahrten der Züge (Ereignis- oder Ziel-, -Label oder -Daten).
                Es werden genau zwei Argumente erwartet.
            wartezeit: Zusätzliche Wartezeit
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
                Optional, per Default wird eine neue Journalgruppe angelegt.
            dry_run: Wenn False, nur prüfen, ob Abwarten möglich ist.

        Returns:
            journal: Änderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.

        Raises:
            KeyError, ValueError
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Kreuzung"
            journal.timestamp = self.anlage.simzeit_minuten

        labels = [self._ankunft_abfahrt_finden(k) for k in knoten]
        labels_set = {l for l in itertools.chain(*labels) if l is not None}
        zids_set = {l.zid for l in labels_set}
        if len(labels_set) != 4 or len(zids_set) != 2:
            raise ValueError("Ungültige/unvollständige Kreuzungsangaben.")

        for label in labels:
            kante = self.anlage.dispo_ereignisgraph.get_edge_data(*label)
            if kante.typ == 'D':
                self._betriebshalt_statt_durchfahrt(journal, label[0], wartezeit)

        ankunft_labels = [l[0] for l in labels]
        abfahrt_labels = [l[1] for l in labels]

        abfahrt_data = [self.anlage.dispo_ereignisgraph.nodes[l] for l in abfahrt_labels]
        bst = {self.anlage.bahnhofgraph.find_superior(d.plan_bst, {'Bf', 'Anst'}) for d in abfahrt_data}
        if len(bst) != 1:
            raise ValueError("Kreuzung in verschiedenen Bahnhöfen nicht möglich")

        warte_kanten = itertools.product(ankunft_labels, abfahrt_labels)
        for kante in warte_kanten:
            if kante[0].zid != kante[1].zid:
                edge = EreignisGraphEdge(typ="A", zid=kante[1].zid, dt_fdl=wartezeit or 0, quelle='fdl')
                egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=kante[1])
                egj.add_edge(*kante, **edge)
                journal.add_entry(egj)
                journal.valid = True

        if not dry_run and journal.valid:
            items = sorted(zip(abfahrt_labels, abfahrt_data, bst), key=lambda x: x[0].zeit)
            _, jid_data, jid_bst = items[0]
            jid = JournalIDType("Kreuzung", jid_data.zid, jid_bst)
            self._journal_anwenden(jid, journal)

        return journal

    def zug_folgen(self):
        pass

    def trasse_verschieben(self):
        pass

    def _ankunft_abfahrt_finden(self,
                                ereignis_oder_ziel: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode) -> tuple[
                                EreignisLabelType | None, EreignisLabelType | None]:
        """
        Zu einem Ereignis oder Ziel gehörende Ankunft- und Abfahrtereignisse finden

        Args:
            ereignis_oder_ziel. Das Ereignis oder Ziel muss zu einem Halt oder einer Fahrt gehören.

        Returns:
            Ankunft und Abfahrtereignisse. None, wenn nicht gefunden.
        """
        vorher_label, _ = self._ereignis_label_finden(ereignis_oder_ziel, {'An', 'Ab'})
        if vorher_label.typ == 'An':
            ankunft1_label = vorher_label
            abfahrt1_label = self.anlage.dispo_ereignisgraph.next_ereignis(ankunft1_label, "Ab")
        elif vorher_label.typ == 'Ab':
            abfahrt1_label = vorher_label
            ankunft1_label = self.anlage.dispo_ereignisgraph.prev_ereignis(abfahrt1_label, "An")
        else:
            ankunft1_label = None
            abfahrt1_label = None
        return ankunft1_label, abfahrt1_label

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
                           abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                           verfruehung: int,
                           relativ: bool = False):
        """
        Vorzeitige Abfahrt
        """

        # todo : ueberarbeiten

        journal = JournalEntryGroup()
        journal.title = "Vorzeitige Abfahrt"
        journal.timestamp = self.anlage.simzeit_minuten

        abfahrt_label, abfahrt_data = self._ereignis_label_finden(abfahrt, {'Ab'})
        if abfahrt_label is None:
            raise ValueError(f"Ungueltige Ereignisangabe {abfahrt}")

        self._wartezeit_aendern(journal, abfahrt_label, "H", -verfruehung, relativ=relativ)
        abfahrt_bst = self.anlage.bahnhofgraph.find_superior(abfahrt_data.plan_bst, {'Bf', 'Anst'})

        if journal.valid:
            jid = JournalIDType("Wartezeit", abfahrt_data.zid, abfahrt_bst)
            self._journal_anwenden(jid, journal)

    def wartezeit_aendern(self,
                          abfahrt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                          wartezeit: int,
                          relativ: bool = False):
        """
        Wartezeit ändern
        """

        # todo : ueberarbeiten

        journal = JournalEntryGroup()
        journal.title = "Wartezeit ändern"
        journal.timestamp = self.anlage.simzeit_minuten

        abfahrt_label, abfahrt_data = self._ereignis_label_finden(abfahrt, {'Ab'})
        if abfahrt_label is None:
            raise ValueError(f"Ungueltige Ereignisangabe {abfahrt}")

        self._wartezeit_aendern(journal, abfahrt_label, "A", wartezeit, relativ=relativ)
        abfahrt_bst = self.anlage.bahnhofgraph.find_superior(abfahrt_data.plan_bst, {'Bf', 'Anst'})

        if journal.valid:
            jid = JournalIDType("Wartezeit", abfahrt_data.zid, abfahrt_bst)
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

        wartend_label, wartend_data = self._ereignis_label_finden(wartend, {'Ab', 'An'})
        zid = wartend.zid
        bst = self.anlage.bahnhofgraph.find_superior(wartend_data.plan_bst, {'Bf', 'Anst'})

        loeschen = []
        for jid, j in self.anlage.dispo_journal.entries.items():
            if jid.typ not in {"Ankunft", "Abfahrt", "Kreuzung"}:
                continue

            for node in j.target_nodes():
                try:
                    node_data = self.anlage.dispo_ereignisgraph.nodes[node]
                    node_zid = node_data.zid
                    node_bst = self.anlage.bahnhofgraph.find_superior(node_data.plan_bst, {'Bf', 'Anst'})
                except KeyError:
                    continue
                else:
                    if zid == node_zid and bst == node_bst:
                        loeschen.append(jid)

        for jid in loeschen:
            self.anlage.dispo_journal.delete_entry(jid)
            logger.debug("Korrektur gelöscht: {jid}")

    def _betriebshalt_statt_durchfahrt(self,
                                       journal: JournalEntryGroup,
                                       ankunftsereignis: EreignisLabelType,
                                       wartezeit: int = 1) -> Tuple[EreignisLabelType, EreignisGraphNode]:

        """
        Betriebshalt statt Durchfahrt

        Ersetzt die Ereignisfolge `Ab1 --P--> An2 --D--> Ab2 --P--> An3` (Durchfahrt in 2)
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`

        Args:
            journal: Aenderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
            ankunftsereignis: Ankunftsereignis An2 am Durchfahrtsbahnhof
            wartezeit: Voraussichtliche Wartezeit

        Returns:
            Ereignislabel des Abfahrtsknotens

        Raises:
            ValueError: Betriebshalt konnte nicht gesetzt werden.
        """

        if not isinstance(ankunftsereignis, EreignisLabelType):
            raise ValueError(f"Argument ankunftsereignis ({type(ankunftsereignis)}) ist kein Ereignislabel.")

        eg = self.anlage.dispo_ereignisgraph
        an2_label = ankunftsereignis
        ab2_label = eg.next_ereignis(an2_label)
        an2_node = eg.nodes[an2_label]
        ab2_node = eg.nodes[ab2_label]

        edge_alt = eg.edges[(an2_label, ab2_label)]
        if edge_alt.typ != 'D':
            raise ValueError(f"Kante {an2_label} --{edge_alt.typ}--> {ab2_label} ist keine Durchfahrt.")
        if an2_node.typ != 'An':
            raise ValueError(f"Ursprungsereignis {an2_label} ist keine Ankunft.")
        if ab2_node.typ != 'Ab':
            raise ValueError(f"Folgeereignis {ab2_label} ist keine Abfahrt.")

        halt_edge = EreignisGraphEdge()
        halt_edge.typ = 'B'
        halt_edge.quelle = 'fdl'
        halt_edge.dt_min = 0
        halt_edge.dt_max = math.inf
        halt_edge.dt_fdl = wartezeit
        halt_edge.ds = 0

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=an2_label)
        egj.change_edge(an2_label, ab2_label, **halt_edge)
        journal.add_entry(egj)

        zgj = JournalEntry[str, ZielLabelType, ZielGraphNode](target_graph='zielgraph', target_node=an2_node.fid)
        zgj.change_node(an2_node.fid, typ='B')
        journal.add_entry(zgj)

        logger.debug("Betriebshalt erstellt")
        logger.debug(f"    Ankunft: {self.anlage.dispo_ereignisgraph.node_info(an2_label)}")
        logger.debug(f"    Abfahrt: {self.anlage.dispo_ereignisgraph.node_info(ab2_label)}")

        return ab2_label, ab2_node

    def _betriebshalt_auf_strecke(self,
                                  journal: JournalEntryGroup,
                                  vorherige_abfahrt: EreignisLabelType,
                                  gleis: BahnhofElement,
                                  ankunftszeit: float | int,
                                  wartezeit: int = 1) -> Tuple[EreignisLabelType, EreignisGraphNode]:

        """
        Betriebshalt unterwegs (Bst nicht im Fahrplan)

        Ersetzt die Ereignisfolge `Ab1 --P-> An3`
        durch `Ab1 --P--> An2 --B--> Ab2 --P--> An3`.
        Es werden zwei neue Knoten und drei neue Kanten eingefuegt.
        Die Kante von Ab1 nach An3 wird entfernt.

        Args:
            journal: Aenderungen an 'ereignisgraph' und 'zielgraph' als JournalEntry-Einträge.
            vorherige_abfahrt: Vorhergehendes Abfahrtsereignis im Ereignisgraph
            gleis: Gleis für Betriebshalt in Betriebsstellen-Notation. Muss vom Typ 'Gl' sein.
            ankunftszeit: Ankunftszeit in Minuten.
            wartezeit: Voraussichtliche Wartezeit in Minuten

        Returns:
            Ereignislabel des Abfahrtsknotens

        Raises:
            ValueError: Betriebshalt konnte nicht gesetzt werden.
        """

        if not isinstance(vorherige_abfahrt, EreignisLabelType):
            raise ValueError(f"Argument vorherige_abfahrt ({type(vorherige_abfahrt)}) ist kein Ereignislabel.")

        eg = self.anlage.dispo_ereignisgraph
        zg = self.anlage.dispo_zielgraph

        ab1_label = vorherige_abfahrt
        an3_label = eg.next_ereignis(ab1_label)

        ab1_node = eg.nodes[ab1_label]
        an3_node = eg.nodes[an3_label]
        alt_edge = eg.edges[(ab1_label, an3_label)]

        if alt_edge.typ != 'P':
            raise ValueError(f"Kante {ab1_label} --{alt_edge.typ}--> {an3_label} ist keine Planfahrt.")
        if ab1_node.typ != 'Ab':
            raise ValueError(f"Ursprungsereignis {ab1_label} ist keine Abfahrt.")
        if an3_node.typ != 'An':
            raise ValueError(f"Folgeereignis {ab1_label} ist keine Ankunft.")
        if gleis.typ != 'Gl':
            raise ValueError(f"Ungültige Gleisbezeichnung {gleis}.")

        try:
            teiler = (ab1_node.t_plan - ankunftszeit) / (ab1_node.t_plan - an3_node.t_plan)
        except ZeroDivisionError:
            teiler = 0.5

        an2_node = copy.copy(ab1_node)
        an2_node.quelle = 'fdl'
        an2_node.typ = 'An'
        an2_node.plan = an2_node.gleis = gleis.name
        an2_node.plan_bst = an2_node.gleis_bst = gleis
        an2_node.t_plan = an2_node.zeit = ankunftszeit
        an2_node.t_mess = None
        an2_label = an2_node.node_id
        an2_node.fid = ZielLabelType(ab1_node.zid, int(an2_node.t_plan), an2_node.gleis)

        ab2_node = copy.copy(an2_node)
        ab2_node.typ = 'Ab'
        ab2_label = ab2_node.node_id

        ankunft_edge = copy.copy(alt_edge)
        ankunft_edge.quelle = 'fdl'
        try:
            ankunft_edge.dt_min = alt_edge.dt_min * teiler
        except AttributeError:
            pass
        try:
            ankunft_edge.ds = alt_edge.ds * teiler
        except AttributeError:
            pass
        ankunft_edge.dt_max = math.inf
        ankunft_edge.dt_fdl = 0

        halt_edge = copy.copy(alt_edge)
        halt_edge.typ = 'B'
        halt_edge.dt_min = 0
        halt_edge.dt_max = math.inf
        try:
            halt_edge.dt_fdl = max(alt_edge.dt_fdl, wartezeit)
        except AttributeError:
            halt_edge.dt_fdl = wartezeit
        halt_edge.ds = 0

        abfahrt_edge = copy.copy(alt_edge)
        abfahrt_edge.dt_min = alt_edge.dt_min * (1. - teiler)
        try:
            abfahrt_edge.ds = alt_edge.ds * (1. - teiler)
        except AttributeError:
            pass
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

        ziel1 = zg.nodes[ab1_node.fid]
        ziel3 = zg.nodes[an3_node.fid]
        ziel2 = ZielGraphNode()
        ziel2.fid = an2_node.fid
        ziel2.zid = an2_node.zid
        ziel2.typ = 'B'
        ziel2.plan = ziel2.gleis = gleis.name
        ziel2.p_an = an2_node.t_plan
        ziel2.p_ab = ab2_node.t_plan
        ziel2.flags = ""
        ziel2.status = ""
        ziel2.lokwechsel = None
        ziel2.lokumlauf = False

        edge12 = ZielGraphEdge()
        edge12.typ = 'P'
        edge23 = copy.copy(edge12)

        zgj = JournalEntry[str, ZielLabelType, ZielGraphNode](target_graph='zielgraph', target_node=an2_node.fid)
        zgj.add_node(ziel2.fid, **ziel2)
        zgj.add_edge(ziel1.fid, ziel2.fid, **edge12)
        zgj.add_edge(ziel2.fid, ziel3.fid, **edge23)
        zgj.remove_edge(ziel1.fid, ziel3.fid)
        journal.add_entry(zgj)

        logger.debug("Betriebshalt erstellt")
        logger.debug(f"    Ankunft: {self.anlage.dispo_ereignisgraph.node_info(an2_label)}")
        logger.debug(f"    Abfahrt: {self.anlage.dispo_ereignisgraph.node_info(ab2_label)}")
        logger.debug(f"    vorher:  {self.anlage.dispo_ereignisgraph.node_info(vorherige_abfahrt)}")

        return ab2_label, ab2_node

    def betriebshalt_einfuegen(self,
                               vorheriges_ziel: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                               gleis: BahnhofElement,
                               ankunftszeit: float | int,
                               wartezeit: int = 1,
                               journal: JournalEntryGroup | None = None,
                               dry_run: bool = False) -> JournalEntryGroup:
        """
        Betriebshalt einfügen

        Wenn das angegebene Fahrziel/Ereignis eine Durchfahrt bezeichnet,
        wird die Durchfahrt in einen Betriebshalt umgewandelt.
        Ansonsten wird ein neues Fahrziel eingefügt.

        Die Funktion prüft nicht, ob die Betriebsstelle auf dem Weg des Zugs liegt!

        Unterstützte Fälle:
            1. vorheriges_ziel bezeichnet ein Ankunftsereignis oder ein Fahrziel mit Durchfahrt.
                gleis gehört zu der Betriebsstelle des Ereignisses bzw. Ziels.
                Die Durchfahrt wird in einen Betriebshalt umgewandelt.
            2. vorheriges_ziel bezeichnet ein Ankunfts- oder Abfahrtsereignis oder ein Fahrziel mit Halt oder Durchfahrt.
                gleis gehört zu einer Betriebsstelle, die im Fahrplan des Zuges _nicht_ vorkommt.
                Der Betriebshalt wird als neues Fahrziel eingefügt.

        Args:
            vorheriges_ziel: Ereignis oder Fahrziel, das zum Betriebshalt wird oder dem Betriebshalt vorangeht.
            gleis: Gleis für Betriebshalt in Betriebsstellen-Notation. Muss vom Typ 'Gl' sein.
            ankunftszeit: Ankunftszeit in Minuten.
            wartezeit: Wartezeit in Minuten
            journal: Bestehende JournalEntryGroup zu der die Aenderungen hinzugefügt werden.
                Per default erstellt die Funktion eine neue Gruppe.
            dry_run: Falls True, werden die notwendigen Aenderungen berechnet und als JournalEntryGroup zurückgeliefert.
                Falls False (default), werden die Aenderungen ausserdem gleich angewendet.

        Returns:
            JournalEntryGroup mit den gemachten bzw. erforderlichen Aenderungen.
            Bei dry_run = False wurden diese bereits auf die dispo-Graphen angewendet.
        """

        if journal is None:
            journal = JournalEntryGroup()
            journal.title = "Betriebshalt"
            journal.timestamp = self.anlage.simzeit_minuten
            journal.valid = True

        ankunft1_label, abfahrt1_label = self._ankunft_abfahrt_finden(vorheriges_ziel)
        if abfahrt1_label is None is None:
            raise ValueError(f"Ungültige Referenz {vorheriges_ziel} für Betriebshalt")

        vorher_node = self.anlage.dispo_ereignisgraph.nodes[abfahrt1_label]
        vorher_bst = self.anlage.bahnhofgraph.find_superior(vorher_node.plan_bst, {'Bf', 'Anst'})
        halt_bst = self.anlage.bahnhofgraph.find_superior(gleis, {'Bf', 'Anst'})

        if vorher_bst == halt_bst:
            if ankunft1_label is None:
                raise ValueError(f"Ungültige Referenz {vorheriges_ziel} für Betriebshalt in {halt_bst}")
            abfahrt_label, abfahrt_data = self._betriebshalt_statt_durchfahrt(journal, ankunft1_label, wartezeit)
        else:
            abfahrt_label, abfahrt_data = self._betriebshalt_auf_strecke(journal, abfahrt1_label, gleis, ankunftszeit, wartezeit)

        if not dry_run and journal.valid:
            jid = JournalIDType(typ="Betriebshalt", zid=abfahrt_label.zid, bst=halt_bst)
            self._journal_anwenden(jid, journal)

        return journal

    def betriebshalt_loeschen(self, betriebshalt: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode]):
        """
        Betriebshalt aus Ereignisgraph löschen

        Der Betriebshalt wird aus dem Dispojournal gelöscht.
        Der Ereignisgraph wird direkt nicht verändert und muss neu aufgebaut werden.

        Args:
            betriebshalt: Zum Betriebshalt gehöriges Ankunfts- oder Abfahrtsereignis oder Ziel.

        Raises:
            KeyError: Betriebshalt nicht gefunden.
        """

        ankunft_label, abfahrt_label = self._ankunft_abfahrt_finden(betriebshalt)
        abfahrt_node = self.anlage.dispo_ereignisgraph.nodes[abfahrt_label]
        bst = self.anlage.bahnhofgraph.find_superior(abfahrt_node.plan_bst, {'Bf', 'Anst'})
        jid = JournalIDType(typ="Betriebshalt", zid=abfahrt_label.zid, bst=bst)
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
