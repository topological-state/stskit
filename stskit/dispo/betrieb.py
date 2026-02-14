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

        abwarten_label = self._ereignis_label_finden(abzuwartende_abfahrt, {'Ab'})
        pfad = self._halt_ereignispfad_finden(wartende_abfahrt, {'Ab'})
        if abwarten_label is None or len(pfad) < 2:
            raise ValueError("Ungültige/unvollständige Zugsangaben.")

        wartend_label = pfad[-2]
        wartend_data = self.anlage.dispo_ereignisgraph.nodes[wartend_label]
        bst = self.anlage.bahnhofgraph.find_superior(wartend_data.plan_bst, {'Bf', 'Anst'})

        haltekante = self.anlage.dispo_ereignisgraph.get_edge_data(*pfad[-2:])
        if haltekante.typ == 'D':
            self._betriebshalt_statt_durchfahrt(journal, pfad[0], wartezeit)

        wartekante = (abwarten_label, pfad[-1])
        edge = EreignisGraphEdge(typ="A", zid=wartekante[1].zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartekante[1])
        egj.add_edge(*wartekante, **edge)
        journal.add_entry(egj)
        journal.valid = True

        if not dry_run and journal.valid:
            jid = JournalIDType("Abfahrt", wartend_label.zid, bst)
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

        abwarten_label = self._ereignis_label_finden(abzuwartende_ankunft, {'An'})
        pfad = self._halt_ereignispfad_finden(wartende_abfahrt, {'Ab'})
        if abwarten_label is None or len(pfad) < 2:
            raise ValueError("Ungültige/unvollständige Zugsangaben.")

        wartend_label = pfad[-2]
        wartend_data = self.anlage.dispo_ereignisgraph.nodes[wartend_label]
        bst = self.anlage.bahnhofgraph.find_superior(wartend_data.plan_bst, {'Bf', 'Anst'})

        haltekante = self.anlage.dispo_ereignisgraph.get_edge_data(*pfad[-2:])
        if haltekante.typ == 'D':
            self._betriebshalt_statt_durchfahrt(journal, pfad[0], wartezeit)

        wartekante = (abwarten_label, pfad[-1])
        edge = EreignisGraphEdge(typ="A", zid=wartekante[1].zid, dt_fdl=wartezeit or 0, quelle='fdl')
        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=wartekante[1])
        egj.add_edge(*wartekante, **edge)
        journal.add_entry(egj)
        journal.valid = True

        if not dry_run and journal.valid:
            jid = JournalIDType("Ankunft", wartend_label.zid, bst)
            self._journal_anwenden(jid, journal)

        return journal

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

        zugpfade = [self._halt_ereignispfad_finden(k) for k in knoten]
        laengen = [len(pfad) for pfad in zugpfade]
        if min(laengen) < 2:
            raise ValueError("Ungültige/unvollständige Kreuzungsangaben.")

        for pfad in zugpfade:
            kante = self.anlage.dispo_ereignisgraph.get_edge_data(*pfad[-2:])
            if kante.typ == 'D':
                self._betriebshalt_statt_durchfahrt(journal, pfad[0], wartezeit)

        ankunft_labels = [l[0] for l in zugpfade]
        abfahrt_labels = [l[-1] for l in zugpfade]

        abfahrt_data = [self.anlage.dispo_ereignisgraph.nodes[l] for l in abfahrt_labels]
        bst = {self.anlage.bahnhofgraph.find_superior(d.plan_bst, {'Bf', 'Anst'}) for d in abfahrt_data}
        if len(bst) != 1:
            raise ValueError("Kreuzung in verschiedenen Bahnhöfen nicht möglich")

        warte_kanten = [(ankunft_labels[0], abfahrt_labels[1]), (ankunft_labels[1], abfahrt_labels[0])]
        for kante in warte_kanten:
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

    def _halt_ereignispfad_finden(self,
                                  ereignis_oder_ziel: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode,
                                  ereignis_typen: set[str] | None = None,
                                  ) -> list[EreignisLabelType]:
        """
        Zu einem Halt oder Ziel gehörende Ereignisse finden

        Liefert die zu einem Halt gehörenden Ereignisse von Ankunft bis Abfahrt entlang des Zugpfads.
        Im einfachsten Fall sind dies ein Ankunfts- und ein Abfahrtsereignis.
        Im Fall von E/F/K kann der Pfad länger sein und mehr als zwei Ereignisse enthalten.
        Die Anfangs- und Endknoten können dann auch verschiedene Zugnummern aufweisen.

        Args:
            - ereignis_oder_ziel. Das Ereignis oder Ziel muss zu einem Halt oder Durchfahrt gehören.
            - ereignis_typen. Ausgangspunkt des Zugspfads.
              Wenn ereignis_oder_ziel ein Fahrziel ist, wird zuerst das Ereignis gesucht, das diesem Typ entspricht.
              Wenn ereignis_oder_ziel ein Ereignis ist, muss sein Typ einem dieser Typen entsprechen,
              sonst schlägt die Funktion fehl.
              Default: {'An', 'Ab'}.

        Returns:
            Liste von Ereignissen als Ausschnitt aus dem Zugpfad von Ankunft bis Abfahrt.
            Wenn kein geschlossenes Segment gefunden werden kann, ist die Liste leer.
        """

        if ereignis_typen is None:
            ereignis_typen = {'An', 'Ab'}

        ziel_label = self._ereignis_label_finden(ereignis_oder_ziel, ereignis_typen)
        ereignisse: list[EreignisLabelType] = []

        match ziel_label:
            case None:
                pass

            case EreignisLabelType(zid=zid, typ='An'):
                for ereignis in self.anlage.dispo_ereignisgraph.zugpfad(zid, start=ziel_label, ersatz=True, kuppeln=True):
                    ereignisse.append(ereignis)
                    if ereignis.typ == 'Ab':
                        break
                else:
                    ereignisse = []

            case EreignisLabelType(zid=zid, typ='Ab'):
                for ereignis in self.anlage.dispo_ereignisgraph.rueckpfad(zid, start=ziel_label, ersatz=True, fluegeln=True):
                    ereignisse.insert(0, ereignis)
                    if ereignis.typ == 'An':
                        break
                else:
                    ereignisse = []

        return ereignisse

    def _ereignis_label_finden(self,
                               ereignis_oder_ziel: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode,
                               typen: set[str],
                               ) -> EreignisLabelType | None:
        """
        Ereignis zu Fahrziel oder Ereignis herausfinden

        Liefert das erste Ereignis eines Zuges, das zu den angegebenen Argumenten passt.
        Wenn das Argument ein Ereignis ist, wird es geliefert, falls es einen der angegebenen Typen hat.
        Wenn das Argument ein Fahrziel ist, wird das erste Ereignis geliefert,
        das zu diesem Ziel gehört und einen der angegebenen Typen hat.
        Anderenfalls wird None zurückgegeben.

        Hinweis: Wenn das Argument ein Ereignis ist, sucht die Methode nicht nach einem anderen Ereignistyp.

        Args:
            ereignis_oder_ziel: Folgende Argumente werden erkannt:
                - Ereignislabel: Attribute zid, zeit und typ
                - Ereignisdaten: Attribut node_id
                - Ziellabel: Attribute zid, zeit und ort
                - Zieldaten: Attribut fid

        Returns:
            Entsprechendes Ereignislabel oder None
        """

        ereignis_label: EreignisLabelType | None = None

        def _ziel_ereignis(**kwargs) -> EreignisLabelType | None:
            for _label in self.anlage.dispo_ereignisgraph.zugpfad(kwargs['zid']):
                _data = self.anlage.dispo_ereignisgraph.nodes[_label]
                if (_data.typ in typen and
                        _data.plan == kwargs['plan'] and
                        kwargs['p_an'] - 0.001 <= _data.t_plan <= kwargs['p_ab'] + 0.001):
                    return _label
            return None

        match ereignis_oder_ziel:
            case EreignisLabelType(typ=typ) if typ in typen:
                ereignis_label = ereignis_oder_ziel

            case EreignisGraphNode(node_id=node_id) if node_id.typ in typen:
                ereignis_label: EreignisLabelType = node_id

            case ZielLabelType():
                ziel_data: ZielGraphNode = self.anlage.dispo_zielgraph.nodes[ereignis_oder_ziel]
                ereignis_label = _ziel_ereignis(**ziel_data)

            case ZielGraphNode():
                ereignis_label = _ziel_ereignis(**ereignis_oder_ziel)

        return ereignis_label

    def _journal_anwenden(self, jid: JournalIDType, journal: JournalEntryGroup):
        try:
            self.anlage.dispo_journal.entries[jid].merge(journal)
        except KeyError:
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
                           target: Union[EreignisLabelType, EreignisGraphNode, ZielLabelType, ZielGraphNode],
                           ) -> None:
        """
        Vorzeitige Abfahrt
        """

        journal = JournalEntryGroup()
        journal.title = "Vorzeitige Abfahrt"
        journal.timestamp = self.anlage.simzeit_minuten

        pfad = self._halt_ereignispfad_finden(target, ereignis_typen={'Ab'})
        if len(pfad) < 2:
            raise ValueError(f"Ungültige Ereignisangabe {target}")

        abfahrt = pfad[-1]
        abfahrt_data = self.anlage.dispo_ereignisgraph.nodes[abfahrt]
        abfahrt_bst = self.anlage.bahnhofgraph.find_superior(abfahrt_data.plan_bst, {'Bf', 'Anst'})
        if not abfahrt_data.vorzeitig:
            raise ValueError("Vorzeitige Abfahrt nicht erlaubt.")

        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=abfahrt)
        egj.change_node(abfahrt, t_plan=None)
        journal.add_entry(egj)
        journal.valid = True

        if journal.valid:
            jid = JournalIDType("Abfahrtszeit", abfahrt_data.zid, abfahrt_bst)
            self._journal_anwenden(jid, journal)
            logger.debug(f"Abfahrtszeit geändert, {jid}")

    def wartezeit_aendern(self,
                          target: EreignisLabelType | EreignisGraphNode | ZielLabelType | ZielGraphNode,
                          kante: Tuple[EreignisLabelType, EreignisLabelType] | None,
                          wartezeit: int,
                          relativ: bool = False):
        """
        Wartezeit ändern

        Die Wartezeit kann geändert werden für:
        - Eingehende Abhängigkeit
        - Halt, Durchfahrt, Betriebshalt
        """

        journal = JournalEntryGroup()
        journal.title = "Wartezeit ändern"
        journal.timestamp = self.anlage.simzeit_minuten

        pfad = self._halt_ereignispfad_finden(target)
        if len(pfad) < 2:
            raise ValueError(f"Ungültige Ereignisangabe {target}")
        if kante is None:
            kante = tuple(pfad[-2:])
        abfahrt = pfad[-1]
        abfahrt_data = self.anlage.dispo_ereignisgraph.nodes[abfahrt]
        abfahrt_bst = self.anlage.bahnhofgraph.find_superior(abfahrt_data.plan_bst, {'Bf', 'Anst'})

        self._wartezeit_aendern(journal, abfahrt, kante, wartezeit, relativ=relativ)
        journal.valid = True

        if journal.valid:
            jid = JournalIDType("Wartezeit", abfahrt_data.zid, abfahrt_bst)
            self._journal_anwenden(jid, journal)
            logger.debug(f"Wartezeit geändert, {jid}")

    def _wartezeit_aendern(self,
                           journal: JournalEntryGroup,
                           target: EreignisLabelType,
                           kante: Tuple[EreignisLabelType, EreignisLabelType],
                           wartezeit: int,
                           relativ: bool = False):

        eg = self.anlage.dispo_ereignisgraph
        egj = JournalEntry[str, EreignisLabelType, EreignisGraphNode](target_graph='ereignisgraph', target_node=target)
        edge_data = eg.edges[kante]

        if relativ:
            try:
                startwert = edge_data.dt_fdl
            except (AttributeError, KeyError):
                startwert = 0
            dt = startwert + wartezeit
        else:
            dt = wartezeit
        egj.change_edge(*kante, dt_fdl=dt)
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

        wartend_label = self._ereignis_label_finden(wartend, {'Ab', 'An'})
        if wartend_label is None:
            raise ValueError(f"Fehlerhafte Referenz beim Korrektur Rücksetzen: {wartend}")
        wartend_data = self.anlage.dispo_ereignisgraph.nodes[wartend_label]
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
                                       wartezeit: int = 1) -> EreignisLabelType:

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

        return ab2_label

    def _betriebshalt_auf_strecke(self,
                                  journal: JournalEntryGroup,
                                  vorherige_abfahrt: EreignisLabelType,
                                  gleis: BahnhofElement,
                                  ankunftszeit: float | int,
                                  wartezeit: int = 1) -> EreignisLabelType:

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

        return ab2_label

    def betriebshalt_einfuegen(self,
                               neuer_halt: EreignisLabelType | EreignisGraphNode,
                               kante: tuple[EreignisLabelType, EreignisLabelType],
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
            1. vorheriges_ziel bezeichnet ein Abfahrtsereignis oder ein Fahrziel mit Durchfahrt.
                gleis gehört zu der Betriebsstelle des Ereignisses bzw. Ziels.
                Die Durchfahrt wird in einen Betriebshalt umgewandelt.
            2. vorheriges_ziel bezeichnet ein Abfahrtsereignis oder ein Fahrziel mit Halt oder Durchfahrt.
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

        halt_pfad = self._halt_ereignispfad_finden(neuer_halt)
        if len(halt_pfad) == 2:
            ankunft_label = halt_pfad[0]
            abfahrt_label = halt_pfad[-1]
        elif len(halt_pfad) == 0:
            abfahrt_label = kante[0]
            ankunft_label = kante[1]
        else:
            raise ValueError("Betriebshalt nicht möglich.")

        abfahrt_node = self.anlage.dispo_ereignisgraph.nodes[abfahrt_label]
        abfahrt_bst = self.anlage.bahnhofgraph.find_superior(abfahrt_node.plan_bst, {'Bf', 'Anst'})
        halt_bst = self.anlage.bahnhofgraph.find_superior(gleis, {'Bf', 'Anst'})

        if abfahrt_bst == halt_bst:
            abfahrt_label = self._betriebshalt_statt_durchfahrt(journal, ankunft_label, wartezeit)
        else:
            abfahrt_label = self._betriebshalt_auf_strecke(journal, abfahrt_label, gleis, ankunftszeit, wartezeit)

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

        pfad = self._halt_ereignispfad_finden(betriebshalt)
        if len(pfad) < 2:
            raise ValueError(f"Ungültige Referenz {betriebshalt} für Betriebshalt")
        ankunft_label, abfahrt_label = pfad[0], pfad[-1]
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
