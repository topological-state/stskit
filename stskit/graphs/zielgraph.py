from dataclasses import dataclass
import datetime
import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.graphs.graphbasics import dict_property
from stskit.interface.stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from stskit.interface.stsobj import Knoten, FahrplanZeile, ZugDetails

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


class ZielGraphNode(dict):
    obj = dict_property("obj", Any,
                        docstring="""
                            Fahrplanziel-Objekt (fehlt bei Ein- und Ausfahrten).
                            """)
    fid = dict_property("fid", Tuple[int, Optional[datetime.time], Optional[datetime.time], Union[int, str]],
                        docstring="""
                            Fahrplanziel-ID bestehend aus Zug-ID, Ankunftszeit, Abfahrtszeit, Plangleis. 
                            Siehe stsobj.FahrplanZeile.fid.
                            Bei Ein- und Ausfahrten wird statt dem Gleiseintrag die Elementnummer (enr) eingesetzt.
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
    plan = dict_property("plan", Union[int, str],
                         docstring="""
                            Plangleis. 
                            Bei Ein- und Ausfahrten die Elementnummer des Anschlusses.
                            """)
    gleis = dict_property("gleis", Union[int, str],
                         docstring="""
                            Geändertes Gleis. 
                            Bei Ein- und Ausfahrten die Elementnummer des Anschlusses.
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
                                      docstring="Minimale Aufenthaltsdauer in Minuten")
    status = dict_property("status", str, docstring="""
                            Status des Ziels. Bestimmt, ob die Ankunfts- und/oder Abfahrtszeit definitiv ist. 
                            '': noch nicht erreicht,  
                            'an': angekommen,
                            'ab': abgefahren.
                            """)
    v_an = dict_property("v_an", Union[int, float], docstring="Ankunftsverspätung in Minuten")
    v_ab = dict_property("v_ab", Union[int, float], docstring="Abfahrtsverspätung in Minuten")
    f_an = dict_property("f_an", Union[int, float], docstring="Effektive Ankunftszeit in Minuten")
    f_ab = dict_property("f_ab", Union[int, float], docstring="Effektive Abfahrtszeit in Minuten")

    def e_an(self) -> Union[int, float]:
        """
        Erwartete Ankunftszeit in Minuten
        """
        return self['p_an'] + self['v_an']

    def e_ab(self) -> Union[int, float]:
        """
        Erwartete Abfahrtszeit in Minuten
        """
        return self['p_ab'] + self['v_ab']

    @classmethod
    def from_fahrplanzeile(cls, fahrplanzeile: FahrplanZeile):
        d = cls(
            obj=fahrplanzeile,
            fid=fahrplanzeile.fid,
            zid=fahrplanzeile.zug.zid,
            plan=fahrplanzeile.plan,
            gleis=fahrplanzeile.gleis,
            typ='D' if fahrplanzeile.durchfahrt() else 'H',
            flags=fahrplanzeile.flags,
            mindestaufenthalt=0
        )

        if fahrplanzeile.an is not None:
            d['p_an'] = time_to_minutes(fahrplanzeile.an)
        if fahrplanzeile.ab is not None:
            d['p_ab'] = time_to_minutes(fahrplanzeile.ab)

        return d


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

    def to_undirected_class(self):
        return ZielGraphUngerichtet

    def to_directed_class(self):
        return self.__class__

    def zug_details_importieren(self, zug: ZugDetails, einfahrt: Optional[Knoten], ausfahrt: Optional[Knoten],
                                zugliste: Dict[int, ZugDetails]) -> Set[Tuple[str, int, int]]:
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
          wenn diese in den von- und nach-Feldertn angegeben sind.
          Einfahrten werden nur eingefügt, wenn der Zug noch nicht eingefahren ist.

        :param: zid: Zug-ID. Der Zug muss in der Zugliste enthalten sein.
        :return: Abgehende Verknüpfungen des Zuges mit anderen Zügen.
            Tupel von Typ ('E', 'K', 'F'), zid des Stammzuges, zid des Folgezuges.
        """

        ziel1 = None
        fid1 = None
        zug2 = zug
        zid2 = zug2.zid
        links = set()

        for ziel2 in zug2.fahrplan:
            fid2 = ziel2.fid
            ziel_data = ZielGraphNode.from_fahrplanzeile(ziel2)
            self.add_node(fid2, **ziel_data)

            if ziel1:
                if fid1 != fid2 and not self.has_edge(fid1, fid2):
                    self.add_edge(fid1, fid2, typ='P')

            if zid3 := ziel2.ersatz_zid():
                self.ziele_verbinden(ziel2, zid3, 'E', zugliste)
                links.add(('E', zid2, zid3))

            if zid3 := ziel2.kuppel_zid():
                self.ziele_verbinden(ziel2, zid3, 'K', zugliste)
                links.add(('K', zid2, zid3))

            if zid3 := ziel2.fluegel_zid():
                self.ziele_verbinden(ziel2, zid3, 'F', zugliste)
                links.add(('F', zid2, zid3))

            ziel1 = ziel2
            fid1 = fid2

        if not zug2.sichtbar and zug2.von and not zug2.von.startswith("Gleis"):
            fid2 = zug2.fahrplan[0].fid
            dt = datetime.datetime.combine(datetime.datetime.today(), fid2[1])
            dt -= datetime.timedelta(minutes=1)
            einfahrtszeit = dt.time()

            try:
                fid1 = (zid2, einfahrtszeit, einfahrtszeit, einfahrt.enr)
                ziel_data = ZielGraphNode(
                    fid=fid1,
                    zid=zid2,
                    typ='E',
                    plan=einfahrt.enr,
                    gleis=einfahrt.enr,
                    p_an=time_to_minutes(einfahrtszeit),
                    p_ab=time_to_minutes(einfahrtszeit)
                )
            except (AttributeError, KeyError, TypeError):
                logger.error(f"Fehler in Einfahrtsdaten {fid1}, Knoten {einfahrt}")
            else:
                self.add_node(fid1, **ziel_data)
                if not self.has_edge(fid1, fid2):
                    self.add_edge(fid1, fid2, typ='P')

        if zug2.nach and not zug2.nach.startswith("Gleis"):
            fid2 = zug2.fahrplan[-1].fid
            dt = datetime.datetime.combine(datetime.datetime.today(), fid2[1])
            dt += datetime.timedelta(minutes=1)
            ausfahrtszeit = dt.time()

            try:
                fid1 = (zid2, ausfahrtszeit, ausfahrtszeit, ausfahrt.enr)
                ziel_data = ZielGraphNode(
                    fid=fid1,
                    zid=zid2,
                    typ='A',
                    plan=ausfahrt.enr,
                    gleis=ausfahrt.enr,
                    p_an=time_to_minutes(ausfahrtszeit),
                    p_ab=time_to_minutes(ausfahrtszeit)
                )
            except (AttributeError, KeyError):
                logger.warning(f"Fehler in Ausfahrtsdaten {fid1}, Knoten {ausfahrt}")
            else:
                self.add_node(fid1, **ziel_data)
                if not self.has_edge(fid2, fid1):
                    self.add_edge(fid2, fid1, typ='P')

        return links

    def ziele_verbinden(self, ziel2: FahrplanZeile, zid3: int, typ: str, zugliste: Dict[int, ZugDetails]):
        """
        Zugziele verknüpfen.

        Unterfunktion von zug_details_importieren.
        """

        fid2 = ziel2.fid

        try:
            zug3 = zugliste[zid3]
            if typ == 'K':
                _, ziel3 = zug3.find_fahrplan(plan=ziel2.plan, zeit=ziel2.an)
            else:
                ziel3 = zug3.fahrplan[0]
            fid3 = ziel3.fid
        except (AttributeError, IndexError, KeyError):
            logger.debug(f"{typ}-Ziel von {fid2} oder Zug {zid3} nicht gefunden")
        else:
            if fid2 != fid3:
                self.add_edge(fid2, fid3, typ=typ)

    def mindestaufenthalt_setzen(self, params: PlanungParams):
        for node, node_data in self.nodes(data=True):
            if node_data.typ == 'H':
                node_data.mindestaufenthalt = 1
            elif node_data.typ == 'E':
                node_data.mindestaufenthalt = params.mindestaufenthalt_ersatz
            elif node_data.typ == 'F':
                node_data.mindestaufenthalt = params.mindestaufenthalt_fluegelung
            elif node_data.typ == 'K':
                node_data.mindestaufenthalt = params.mindestaufenthalt_kupplung
            else:
                node_data.mindestaufenthalt = 0

            if 'R' in node_data.flags:
                node_data.mindestaufenthalt += params.mindestaufenthalt_richtungswechsel
            if 'L' in node_data.flags:
                node_data.mindestautfenthalt += params.mindestaufenthalt_lokumlauf
            if 'W' in node_data.flags:
                node_data.mindestaufenthalt += params.mindestaufenthalt_lokwechsel


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
