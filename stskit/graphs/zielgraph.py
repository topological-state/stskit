from dataclasses import dataclass
import datetime
import logging
from typing import Any, Callable, Dict, Iterable, NamedTuple, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.graphs.bahnhofgraph import BahnhofGraph
from stskit.interface.stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from stskit.interface.stsobj import Knoten, FahrplanZeile, ZugDetails, FahrplanZeileID

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass
class PlanungParams:
    mindestaufenthalt_planhalt: int = 0
    mindestaufenthalt_lokwechsel: int = 5
    mindestaufenthalt_lokumlauf: int = 2
    mindestaufenthalt_richtungswechsel: int = 3
    mindestaufenthalt_ersatz: int = 1
    mindestaufenthalt_kupplung: int = 1
    mindestaufenthalt_fluegelung: int = 1
    wartezeit_ankunft_abwarten: int = 0
    wartezeit_abfahrt_abwarten: int = 2


MIN_MINUTES = 0
MAX_MINUTES = 24 * 60


class ZielLabelType(NamedTuple):
    """
    Ziellabelklasse

    Das Ziellabel ist ähnlich wie die FahrplanZeileID aufgebaut.
    Für Ein- und Ausfahrten wird jedoch die Elementnummer statt des Anschlussnamens verwendet.
    """
    zid: int
    zeit: int
    ort: Union[int, str]

    @classmethod
    def from_fahrplanzeile(cls, fid: FahrplanZeileID) -> 'ZielLabelType':
        """
        Konstruktor aus einer Fahrplanzeilen-ID.

        Der Ortsteil einer Fahrplanzeilen-ID bezieht sich immer auf ein Bahnhofsgleis (kein Anschlussgleis).
        """
        return cls(fid.zid, fid.zeit, fid.plan)


class ZielGraphNode(dict):
    obj = dict_property("obj", Any,
                        docstring="""
                            stsobj.FahrplanZeile-Objekt (fehlt bei Ein- und Ausfahrten).
                            """)
    fid = dict_property("fid", ZielLabelType,
                        docstring="""
                            Fahrplanziel-ID bestehend aus Zug-ID, Ankunfts- oder Abfahrtszeit in Minuten, Plangleis.
                            Siehe stsobj.FahrplanZeile.fid.
                            Bei Ein- und Ausfahrten wird statt dem Gleiseintrag die Elementnummer (enr) eingesetzt,
                            und die Zeitkomponente ist MIN_MINUTES (Einfahrt) oder MAX_MINUTES (Ausfahrt).
                            """)
    zid = dict_property("zid", int, docstring="Zug-ID")
    typ = dict_property("typ", str,
                        docstring="""
                            Zielpunkttyp:
                                'H': Planmässiger Halt
                                'D': Durchfahrt
                                'E': Einfahrt
                                'A': Ausfahrt
                                'B': Betriebshalt (vom Sim nicht verwendet)
                                'S': Signalhalt (vom Sim nicht verwendet)
                            """)
    plan = dict_property("plan", str,
                         docstring="""
                            Gleis- oder Anschlussname nach Fahrplan.
                            """)
    gleis = dict_property("gleis", str,
                         docstring="""
                            Gleis- oder Anschlussname nach aktueller Disposition.
                            """)
    p_an = dict_property("p_an", Union[int, float],
                       docstring="""
                            Planmässige Ankunftszeit in Minuten.
                            Bei Ein- und Ausfahrten wird die Ankunfts- und Abfahrtszeit geschätzt.
                            """)
    p_ab = dict_property("p_ab", Union[int, float],
                       docstring="""
                            Planmässige Abfahrtszeit in Minuten.
                            Bei Ein- und Ausfahrten wird die Ankunfts- und Abfahrtszeit geschätzt.
                            """)
    flags = dict_property("flags", str, docstring="Originalflags")

    # Die folgenden Properties werden nicht vom Simulator geliefert
    mindestaufenthalt = dict_property("mindestaufenthalt", Union[int, float],
                                      docstring="""
                                          Minimale Aufenthaltsdauer in Minuten.
                                          Schätzung, wie lange sich der Zug mindestens an diesem Ziel aufhält,
                                          auch wenn er laut Fahrplan früher abfahren müsste.
                                          
                                          Die Mindestaufenthaltsdauer wird von der Simulatorschnittstelle nicht angegeben
                                          und muss von uns geschätzt werden, 
                                          z.B. mittels konfigurierten Parametern durch mindestaufenthalt_setzen.
                                          """)
    status = dict_property("status", str, docstring="""
                            Status des Ziels. Bestimmt, ob die Ankunfts- und/oder Abfahrtszeit definitiv ist. 
                            '': noch nicht erreicht,  
                            'an': angekommen,
                            'ab': abgefahren.
                            """)
    v_an = dict_property("v_an", Union[int, float], docstring="Ankunftsverspätung in Minuten")
    v_ab = dict_property("v_ab", Union[int, float], docstring="Abfahrtsverspätung in Minuten")

    @property
    def e_an(self) -> Union[int, float]:
        """
        Erwartete Ankunftszeit in Minuten

        AttributeError, wenn keine Ankunftszeit gespeichert ist.
        Wenn keine Verspätung gespeichert ist, wird 0 angenommen.
        """
        return self.p_an + self.get('v_an', 0)

    @property
    def e_ab(self) -> Union[int, float]:
        """
        Erwartete Abfahrtszeit in Minuten

        AttributeError, wenn keine Abfahrtszeit gespeichert ist.
        Wenn keine Verspätung gespeichert ist, wird 0 angenommen.
        """
        return self.p_ab + self.get('v_ab', 0)

    @property
    def enr(self) -> Optional[int]:
        """
        Elementnummer des Anschlussgleises bei Ein- oder Ausfahrt.

        None, wenn das Ziel ein normales Gleis ist.
        """
        try:
            return int(self.fid.ort)
        except ValueError:
            return None

    @property
    def plan_bst(self) -> Tuple[str, str]:
        """
        Plangleis in Betriebsstellen-Notation.
        """
        if self.typ in {'E', 'A'}:
            return 'Agl', self.plan
        else:
            return 'Gl', self.plan

    @property
    def gleis_bst(self) -> Tuple[str, str]:
        """
        Effektives Gleis in Betriebsstellen-Notation.
        """
        if self.typ in {'E', 'A'}:
            return 'Agl', self.gleis
        else:
            return 'Gl', self.gleis

    @classmethod
    def from_fahrplanzeile(cls, fahrplanzeile: FahrplanZeile):
        """
        Daten aus Fahrplanzeile übernehmen.

        Die folgenden Properties werden direkt übernommen:
        obj, fid, zid, plan, gleis, typ, flags, p_an, p_ab.
        mindestaufenthalt wird auf 0 gesetzt.
        Alle anderen müssen separat gesetzt werden.

        :param fahrplanzeile: Fahrplanzeile-Objekt von der Simulatorschnittstelle.
        """

        d = cls(
            obj=fahrplanzeile,
            fid=fahrplanzeile.fid,
            zid=fahrplanzeile.zug.zid,
            plan=fahrplanzeile.plan,
            gleis=fahrplanzeile.gleis,
            typ='D' if fahrplanzeile.durchfahrt() else 'H',
            flags=fahrplanzeile.flags,
            status='',
            mindestaufenthalt=0
        )

        if fahrplanzeile.an is not None:
            d['p_an'] = time_to_minutes(fahrplanzeile.an)
        if fahrplanzeile.ab is not None:
            d['p_ab'] = time_to_minutes(fahrplanzeile.ab)

        return d

    def mindestaufenthalt_setzen(self, params: Optional[PlanungParams] = None):
        """
        Mindestaufenthalt-Property auf Vorgabewert setzen.

        Der Mindestaufenthalt wird gemäss übergebenen Parametern aus dem Zieltyp und den Flags berechnet.
        Er setzt sich zusammen aus einer Basiskomponente nach Planhalt, Ersatz, Kupplung oder Flügelung,
        und einer additiven Komponente bei Richtungswechsel, Lokwechsel oder Lokumlauf.

        :param params: Aufenthaltsparameter aus Konfiguration.
            Wenn das Argument fehlt, werden die Defaultwerte der PlanungParams-Klasse verwendet.
        """

        if params is None:
            params = PlanungParams

        if self.typ == 'H':
            result = params.mindestaufenthalt_planhalt
        elif 'E' in self.flags:
            result = params.mindestaufenthalt_ersatz
        elif 'F' in self.flags:
            result = params.mindestaufenthalt_fluegelung
        elif 'K' in self.flags:
            result = params.mindestaufenthalt_kupplung
        else:
            result = 0

        if 'L' in self.flags:
            result += params.mindestaufenthalt_lokumlauf
        elif 'R' in self.flags:
            result += params.mindestaufenthalt_richtungswechsel
        elif 'W' in self.flags:
            result += params.mindestaufenthalt_lokwechsel

        self.mindestaufenthalt = result


class ZielGraphEdge(dict):
    typ = dict_property("typ", str,
                        docstring="""
                            Verbindungstyp:
                                'P': planmässige Fahrt,
                                'E': Ersatzzug,
                                'F': Flügelung,
                                'K': Kupplung,
                                'R': vom Fdl angeordnete Rangierfahrt, z.B. bei Lokwechsel,
                                'A': vom Fdl angeordnete Abhängigkeit,
                                'O': Hilfskante für Sortierordnung.
                            """)
    v = dict_property("v", Union[int, float],
                      docstring="""
                            Verspätung auf dieser Verbindung in Minuten. 
                            Wird in der Prognose verwendet, ist daher nicht persistent.
                            """)


class ZielGraph(nx.DiGraph):
    """
    Fahrplan in Graphform.

    Der Zielgraph enthält den Fahrplan aller Züge.
    Die Punkte sind gemäss Anordnung im Fahrplan
    sowie planmässigen (Ersatz, Kuppeln, Flügeln)
    und dispositiven Abhängigkeiten (Kreuzung, Ueberholen, Abwarten, Betriebshalt, etc.) verbunden.

    Der Zielgraph ist gerichtet.
    """
    node_attr_dict_factory = ZielGraphNode
    edge_attr_dict_factory = ZielGraphEdge

    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        self.zuganfaenge: Dict[int, ZielLabelType] = {}
        self.zugenden: Dict[int, ZielLabelType] = {}
        self._pendente_verbindungen: Set[Tuple[ZielLabelType, int, str]] = set()

    def to_undirected_class(self):
        return ZielGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def zugpfad(self, zid: int) -> Iterable[ZielLabelType]:
        """
        Generator für die Knoten eines Zuges

        Beginnend mit dem Startknoten liefert der Generator die Knoten-IDs eines Zuges
        in der Reihenfolge ihres Auftretens.
        """

        node = self.zuganfaenge[zid]
        while node is not None:
            yield node

            for n in self.successors(node):
                if n.zid == zid:
                    node = n
                    break
            else:
                node = None

    def zug_details_importieren(self, zug: ZugDetails,
                                einfahrt: Optional[Knoten],
                                ausfahrt: Optional[Knoten],
                                params: Optional[PlanungParams]) -> Set[Tuple[str, int, int]]:
        """
        Ziel- und Zuggraphen nach Fahrplan eines Zuges aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Diese Methode fügt neue Knoten und ihre Kanten zum Graphen hinzu oder aktualisiert bestehende.
        Es werden keine Knoten und Kanten gelöscht.

        Bemerkungen
        -----------

        - Der vom Simulator gemeldete Fahrplan enthält nur anzufahrende Ziele.
          Im Zielgraphen werden die abgefahrenen Ziele jedoch beibehalten.
        - Die Methode fügt auch Knoten und Kanten für Einfahrten und Ausfahrten ein,
          wenn diese in den von- und nach-Feldern angegeben sind.
          Einfahrten werden nur eingefügt, wenn der Zug noch nicht eingefahren ist.

        :param zug: ZugDetails-Objekt vom Simulator.
        :param einfahrt: Einfahrtsknoten, falls im von-Feld angegeben.
        :param ausfahrt: Ausfahrtssknoten, falls im nach-Feld angegeben.
        :param zugliste: Referenz auf die Zugliste des PluginClient oder GraphClient.
            Wird benötigt, um Verknüpfungen mit anderen Zügen aufzulösen.
        :param params: Parametrisierung der Mindestaufenthaltsdauer nach Zieltyp.
            Wenn None, werden die Defaultwerte der PlanungParams-Klasse verwendet.

        :return: Abgehende Verknüpfungen des Zuges mit anderen Zügen.
            Tupel von Typ ('E', 'K', 'F'), zid des Stammzuges, zid des Folgezuges.
        """

        if params is None:
            params = PlanungParams

        ziel1 = None
        fid1 = None
        anfang = None
        ende = None
        zug2 = zug
        zid2 = zug2.zid
        links = set()

        for ziel2 in zug2.fahrplan:
            fid2 = ZielLabelType.from_fahrplanzeile(ziel2.fid)
            if anfang is None:
                anfang = fid2
            ende = fid2

            ziel_data = ZielGraphNode.from_fahrplanzeile(ziel2)
            ziel_data.mindestaufenthalt_setzen(params)
            self.add_node(fid2, **ziel_data)

            if ziel1:
                if fid1 != fid2 and not self.has_edge(fid1, fid2):
                    self.add_edge(fid1, fid2, typ='P')

            if zid3 := ziel2.ersatz_zid():
                self._ziele_verbinden(fid2, zid3, 'E')
                links.add(('E', zid2, zid3))

            if zid3 := ziel2.kuppel_zid():
                self._ziele_verbinden(fid2, zid3, 'K')
                links.add(('K', zid2, zid3))

            if zid3 := ziel2.fluegel_zid():
                self._ziele_verbinden(fid2, zid3, 'F')
                links.add(('F', zid2, zid3))

            ziel1 = ziel2
            fid1 = fid2

        if not zug2.sichtbar and einfahrt is not None:
            fz2 = zug2.fahrplan[0]
            fid2 = ZielLabelType.from_fahrplanzeile(fz2.fid)
            einfahrtszeit = time_to_minutes(fz2.an or fz2.ab) - 1

            try:
                fid1 = ZielLabelType(zid2, MIN_MINUTES, einfahrt.enr)
                ziel_data = ZielGraphNode(
                    obj=None,
                    fid=fid1,
                    zid=zid2,
                    typ='E',
                    plan=einfahrt.name,
                    gleis=einfahrt.name,
                    flags='',
                    status='',
                    p_an=einfahrtszeit,
                    p_ab=einfahrtszeit,
                    mindestaufenthalt=0
                )
            except (AttributeError, KeyError, TypeError):
                logger.error(f"Fehler in Einfahrtsdaten {fid1}, Knoten {einfahrt}")
            else:
                self.add_node(fid1, **ziel_data)
                anfang = fid1
                if ende is None:
                    ende = fid1
                if not self.has_edge(fid1, fid2):
                    self.add_edge(fid1, fid2, typ='P')

        if zug2.nach and ausfahrt is not None:
            fz2 = zug2.fahrplan[-1]
            fid2 = ZielLabelType.from_fahrplanzeile(fz2.fid)
            ausfahrtszeit = time_to_minutes(fz2.ab or fz2.an) + 1

            try:
                fid1 = ZielLabelType(zid2, MAX_MINUTES, ausfahrt.enr)
                ziel_data = ZielGraphNode(
                    obj=None,
                    fid=fid1,
                    zid=zid2,
                    typ='A',
                    plan=ausfahrt.name,
                    gleis=ausfahrt.name,
                    flags='',
                    status='',
                    p_an=ausfahrtszeit,
                    p_ab=ausfahrtszeit,
                    mindestaufenthalt=0
                )
            except (AttributeError, KeyError):
                logger.warning(f"Fehler in Ausfahrtsdaten {fid1}, Knoten {ausfahrt}")
            else:
                self.add_node(fid1, **ziel_data)
                if anfang is None:
                    anfang = fid1
                ende = fid1
                if not self.has_edge(fid2, fid1):
                    self.add_edge(fid2, fid1, typ='P')

        if zid2 not in self.zuganfaenge:
            self.zuganfaenge[zid2] = anfang
            self.zugenden[zid2] = ende
        self.ziel_status_von_zug(zug2)
        self.verspaetung_von_zug(zug2)
        self._verbindungen_herstellen(zid2)

        return links

    def _ziele_verbinden(self, fid1: ZielLabelType, zid2: int, typ: str):
        """
        Zugziele verknüpfen.

        Unterfunktion von zug_details_importieren.
        Die Funktion sucht zunächst das entsprechende Ziel im Folgezug anhand des Gleisnamens und der Ankunftszeit
        und erstellt dann eine Kante mit dem angegebenen Typ vom Ursprungsziel zum Folgeziel.

        Wenn der Folgezug noch nicht erfasst ist, kann das Folgeziel nicht aufgelöst werden.
        Die Verbindung wird dann zu den _pendente_verbindungen hinzugefügt und
        kann später mittels _verbindungen_herstellen hergestellt werden.

        :param fid1: Label des Ursprungsziels.
        :param zid2: ID des Folgezuges.
        :param typ: Verbindungstyp (Typ-Attribut der Verbindungskante)
        """

        _, fid2 = self._verbindung_herstellen(fid1, zid2, typ)
        if fid2 is None:
            self._pendente_verbindungen.add((fid1, zid2, typ))

    def _verbindungen_herstellen(self, zid2: Optional[int] = None):
        """
        Pendente Zielverbindungen herstellen.

        S. _ziele_verbinden

        :param zid2: Nur Verbindungen, die zu diesen Zug führen, herstellen.
        """

        erledigt = set()
        for v in self._pendente_verbindungen:
            if zid2 is None or v[1] == zid2:
                fid1, fid2 = self._verbindung_herstellen(*v)
                if fid2 is not None:
                    erledigt.add(v)

        self._pendente_verbindungen.difference_update(erledigt)

    def _verbindung_herstellen(self, fid1: ZielLabelType, zid2: int, typ: str) -> Tuple[ZielLabelType, ZielLabelType]:
        """
        Einzelne Zielverbindung herstellen.

        Unterfunktion von _ziele_verbinden und _verbindungen_herstellen.

        :param fid1: Label des Ursprungsziels.
        :param zid2: ID des Folgezugs.
        :param typ: Verbindungstyp

        :return: Labels der Verbindungskante.
            Das erste Label entspricht immer fid1, das zweite ist das Folgeziel.
            Das Folgeziel ist None, wenn es nicht gefunden wurde.
        """

        ziel1 = self.nodes[fid1]
        plan1 = ziel1.plan.casefold()
        zeit1 = ziel1.p_an

        try:
            fid2 = self.zuganfaenge[zid2]
        except KeyError:
            fid2 = None
            logger.debug(f"Finde kein {typ}-Ziel von Zug {ziel1.zid}, Ziel {fid1} zu Zug {zid2}.")

        if fid2 is not None and typ == 'K':
            for fid in self.zugpfad(zid2):
                ziel = self.nodes[fid]
                try:
                    if plan1 != ziel.plan.casefold():
                        continue
                except (AttributeError, TypeError):
                    continue

                try:
                    if ziel.p_an and zeit1 < ziel.p_an:
                        continue
                except (AttributeError, TypeError):
                    continue

                try:
                    if ziel.p_ab and zeit1 > ziel.p_ab:
                        continue
                except (AttributeError, TypeError):
                    continue

                fid2 = fid
                break
            else:
                logger.debug(f"Finde kein {typ}-Ziel von Zug {ziel1.zid}, Ziel {fid1} zu Zug {zid2}.")

        if fid2 is not None and fid1 != fid2:
            self.add_edge(fid1, fid2, typ=typ)

        return fid1, fid2

    def ziel_status_von_zug(self, zug: ZugDetails):
        """
        Zielstatusfelder aus ZugDetails übernehmen.

        Die Zielstatusfelder werden anhand der ZugDetails aktualisiert.
        Von ZugDetails benötigt werden: fahrplan[].fid, ziel_index, amgleis

        Abgefahrene Zielknoten werden mit 'ab' markiert, die noch nicht abgefahrenen mit ''.
        Wenn der Zug an einem Ziel steht, ist der Status 'an'.
        """

        status = 'ab' if zug.sichtbar else ''
        try:
            fid_aktuell = ZielLabelType.from_fahrplanzeile(zug.fahrplan[zug.ziel_index].fid)
        except (IndexError, KeyError, TypeError):
            # kein ziel oder kein fahrplan
            fid_aktuell = None
            if len(zug.fahrplan):
                # noch nicht eingefahren
                status = ''
            else:
                # ausgefahren
                status = 'ab'

        for fid in self.zugpfad(zug.zid):
            data = self.nodes[fid]
            if data.fid == fid_aktuell:
                status = 'an' if zug.amgleis else ''
            elif status == 'an':
                status = ''
            data.status = status

    def verspaetung_von_zug(self, zug: ZugDetails):
        """
        Verspätungsfelder von ZugDetails übernehmen.

        Die Verspätungsfelder werden anhand der ZugDetails aktualisiert.
        Die Statusfelder müssen bereits korrekt gesetzt sein.
        Es werden nur die noch nicht abgefahrenen Ziele aktualisiert.
        """

        for fid in self.zugpfad(zug.zid):
            data = self.nodes[fid]
            if data.status == '':
                data.v_an = zug.verspaetung
                data.v_ab = zug.verspaetung
            elif data.status == 'an':
                data.v_ab = zug.verspaetung

    def einfahrtszeiten_korrigieren(self, lg: 'LinienGraph', bg: BahnhofGraph):
        """
        Ein- und Ausfahrtszeiten korrigieren.

        Da der Simulator keine Ein- und Ausfahrtszeiten angibt,
        bietet diese Methode an, sie aus dem nächsten Ziel und der gemessenen Fahrzeit im Liniengraph abzuschätzen.

        :param lg: Der Liniengraph enthält die Fahrzeiten zwischen den Bahnhofteilen.
        :param bg: Der Bahnhofgraph enthält die Zuordnung von Gleisen zu Bahnhofteilen.
        """

        for fid1, fid2 in self.edges(data=False):
            ziel1_data = self.nodes[fid1]
            ziel2_data = self.nodes[fid2]
            if ziel1_data.typ == 'E' or ziel2_data.typ == 'A':
                bst1 = bg.find_superior(ziel1_data.plan_bst, {'Anst', 'Bf'})
                bst2 = bg.find_superior(ziel2_data.plan_bst, {'Anst', 'Bf'})

                try:
                    fahrzeit = lg.edges[bst1][bst2]['fahrzeit_schnitt']
                    if fahrzeit < 1:
                        continue
                except KeyError:
                    continue

                if ziel1_data.typ == 'E':
                    try:
                        dt = datetime.datetime.combine(datetime.datetime.today(), ziel2_data.p_an)
                    except AttributeError:
                        continue
                    else:
                        dt -= datetime.timedelta(minutes=fahrzeit)
                        einfahrtszeit = dt.time()
                        ziel1_data.update(p_an=time_to_minutes(einfahrtszeit),
                                          p_ab=time_to_minutes(einfahrtszeit))

                elif ziel2_data.typ == 'A':
                    try:
                        dt = datetime.datetime.combine(datetime.datetime.today(), ziel1_data.p_ab)
                    except AttributeError:
                        continue
                    else:
                        dt += datetime.timedelta(minutes=fahrzeit)
                        ausfahrtszeit = dt.time()
                        ziel2_data.update(p_an=time_to_minutes(ausfahrtszeit),
                                          p_ab=time_to_minutes(ausfahrtszeit))


class ZielGraphUngerichtet(nx.Graph):
    """
    Ungerichtete Variante von ZugGraph

    Fuer gewisse Algorithmen kann es noetig sein, den Zielgraphen voruebergehend in einen ungerichteten umzuwandeln.
    """
    node_attr_dict_factory = ZielGraphNode
    edge_attr_dict_factory = ZielGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return ZielGraph
