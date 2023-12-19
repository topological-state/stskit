import datetime

import trio
import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union

import networkx as nx

from stskit.interface.stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from stskit.interface.stsobj import Knoten, FahrplanZeile, ZugDetails
from stskit.interface.stsplugin import PluginClient, TaskDone


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


T = TypeVar('T')


def dict_property(name: str, T, docstring: str = None):
    """
    Generic factory function for a property that corresponds to a dictionary value.

    The owning class must be a subclass of dict.

    :param name: The name of the property.
    :param T: The type of the property.
    :param docstring: The docstring of the property.
    """
    def getter(self) -> T:
        return self[name]

    def setter(self, value: T):
        self[name] = value

    def deleter(self):
        del self[name]

    return property(getter, setter, deleter, doc=docstring)


class SignalGraphNode(dict):
    enr = dict_property("enr", int, docstring="Elementnummer")
    name = dict_property("name", str, docstring="Elementname")
    typ = dict_property("typ", int, docstring="Elementtyp, s. stsobj.Knoten.TYP_NUMMER")


class SignalGraphEdge(dict):
    typ = dict_property("typ", str, docstring="""
        'gleis' zwischen knoten mit namen, sonst 'verbindung' (z.b. weichen).
        """)
    distanz = dict_property("distanz", int, docstring="""
        Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten.
        Wird auf 1 gesetzt.
        """)


class SignalGraph(nx.DiGraph):
    """
    Der Signalgraph stellt die Bahninfrastruktur dar.

    Die Daten stammen aus dem Wege-Datensatz der Pluginschnittstelle oder sind daraus abgeleitet.
    Der urspruengliche Signalgraph ist gerichtet.
    Fuer die Verarbeitung kann es noetig sein, ihn in die ungerichtete Variante SignalGraphUngerichtet zu verwandeln.
    """
    node_attr_dict_factory = SignalGraphNode
    edge_attr_dict_factory = SignalGraphEdge

    def to_undirected_class(self):
        return SignalGraphUngerichtet

    def to_directed_class(self):
        return self.__class__


class SignalGraphUngerichtet(nx.Graph):
    """
    Ungerichtete Variante von SignalGraph

    Der urspruengliche Signalgraph ist gerichtet.
    Fuer die Verarbeitung kann es noetig sein, ihn in die ungerichtete Variante SignalGraphUngerichtet zu verwandeln.
    """
    node_attr_dict_factory = SignalGraphNode
    edge_attr_dict_factory = SignalGraphEdge

    def to_undirected_class(self):
        return self.__class__

    def to_directed_class(self):
        return SignalGraph


class BahnsteigGraphNode(dict):
    name = dict_property("name", str, docstring="""
        Bahnsteig
        """)


class BahnsteigGraphEdge(dict):
    typ = dict_property("typ", str, docstring="""
        Bahnsteig
        """)
    distanz = dict_property("distanz", int, docstring="""
        Länge (Anzahl Knoten) des kürzesten Pfades zwischen den Knoten. Wird auf 0 gesetzt.
        """)


class BahnsteigGraph(nx.Graph):
    """
    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.
    Kanten werden entsprechend der Nachbarrelationen gesetzt.
    Der Graph ist ungerichtet, da die Nachbarbeziehung als reziprok aufgefasst wird.

    Der Graph sollte nicht verändert werden.
    Es wird nicht erwartet, dass sich der Graph im Laufe eines Spiels ändert.
    """
    node_attr_dict_factory = BahnsteigGraphNode
    edge_attr_dict_factory = BahnsteigGraphEdge

    def to_undirected_class(self):
        return self.__class__


class ZugGraphNode(dict):
    obj = dict_property("obj", ZugDetails, docstring="Zugobjekt")
    zid = dict_property("zid", int, docstring="Zug-ID")
    name = dict_property("name", str)
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
            von=zug_details.von,
            nach=zug_details.nach,
            verspaetung=zug_details.verspaetung,
            sichtbar=zug_details.sichtbar,
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
    bft = dict_property("bft", str,
                        docstring="""
                            Name des Bahnhofteils.
                            Bei Ein- und Ausfahrten der Name des Anschlusses.
                            Gleisänderungen können nur innerhalb eines Bahnhofteils disponiert werden.
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
    mindestaufenthalt = dict_property("mindestaufenthalt", Union[int, float], docstring="Mindestaufenthaltsdauer in Minuten")
    status = dict_property("status", str, docstring="Status des Ziels")
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
            flags=fahrplanzeile.flags
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


class ZielGraph(nx.DiGraph):
    """
    Der Zielgraph enthält den Fahrplan aller Züge.
    Die Punkte sind gemäss Anordnung im Fahrplan
    sowie planmässigen (Ersatz, Kuppeln, Flügeln)
    und dispositiven Abhängigkeiten (Kreuzung, Ueberholen, Abwarten, Betriebshalt, etc.) verbunden.

    Der Zielgraph ist gerichtet.
    """
    node_attr_dict_factory = ZielGraphNode
    edge_attr_dict_factory = ZielGraphEdge

    def to_undirected_class(self):
        return ZugGraphUngerichtet

    def to_directed_class(self):
        return self.__class__


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
        return ZugGraph


class LinienGraphNode(dict):
    typ = dict_property("typ", int,
                        docstring="Typ des entsprechenden Elements des Signalgraphs")


class LinienGraphEdge(dict):
    fahrzeit_min = dict_property("fahrzeit_min", Union[int, float],
                                 docstring="Minimale Fahrzeit in Minuten")
    fahrzeit_max = dict_property("fahrzeit_max", Union[int, float],
                                 docstring="Maximale Fahrzeit in Minuten")
    fahrten = dict_property("fahrten", int,
                            docstring="Anzahl der ausgewerteten Fahrten")
    fahrzeit_summe = dict_property("fahrzeit_summe", Union[int, float],
                                   docstring="Summe aller ausgewerteten Fahrzeiten in Minuten")
    fahrzeit_schnitt = dict_property("fahrzeit_schnitt", float,
                                     docstring="Mittelwert aller ausgewerteten Fahrzeiten in Minuten")


class LinienGraph(nx.Graph):
    """
    Graph class to represent train connections in the railroad network

    This graph is generated from the train schedules.
    """
    node_attr_dict_factory = LinienGraphNode
    edge_attr_dict_factory = LinienGraphEdge

    def to_undirected_class(self):
        return self.__class__


class GraphClient(PluginClient):
    """
    Erweiterter PluginClient mit Graphdarstellung der Basisdaten vom Simulator.

    Die Klasse unterhält folgende Graphen:

    Signalgraph
    ===========

    Der _Signalgraph_ enthält das Gleisbild aus der Wegeliste der Plugin-Schnittstelle mit sämtlichen Knoten und Kanten.
    Das 'typ'-Attribut wird auf den sts-Knotentyp (int) gesetzt.
    Kanten werden entsprechend der Nachbarrelationen aus der Wegeliste ('typ'-attribut 'gleis') gesetzt.
    Der Graph ist gerichtet, da die nachbarbeziehung i.a. nicht reziprok ist.
    Die Kante zeigt auf die Knoten, die als Nachbarn aufgeführt sind.
    Meist werden von der Schnittstelle jedoch Kanten in beide Richtungen angegeben,
    weshalb z.B. nicht herausgefunden werden kann, für welche Richtung ein Signal gilt.

    Der Graph sollte nicht verändert werden.
    Es wird nicht erwartet, dass sich der Graph im Laufe eines Spiels ändert.

    Die Signaldistanz wird am Anfang auf 1 gesetzt.

    Bahnsteiggraph
    ==============

    Der _Bahnsteiggraph_ enthält alle Bahnsteige aus der Bahnsteigliste der Plugin-Schnittstelle als Knoten.
    Kanten werden entsprechend der Nachbarrelationen gesetzt.
    Der Graph ist ungerichtet, da die Nachbarbeziehung als reziprok aufgefasst wird.

    Der Graph sollte nicht verändert werden.
    Es wird nicht erwartet, dass sich der Graph im Laufe eines Spiels ändert.

    Zuggraph
    ========

    Der _Zuggraph_ enthält alle Züge aus der Zugliste der Plugin-Schnittstelle als Knoten.
    Kanten werden aus den Ersatz-, Kuppeln- und Flügeln-Flags gebildet.

    Der Zuggraph verändert sich im Laufe eines Spiels.
    Neue Züge werden hinzugefügt.

    In der aktuellen Entwicklerversion werden ausgefahrene Züge beibehalten.
    Falls sich das als nicht praktikabel erweist, werden die Züge wie in der Zugliste gelöscht.

    Zielgraph
    =========

    Der Zielgraph enthält die Zielpunkte aller Züge.
    Die Punkte sind gemäss Anordnung im Fahrplan
    sowie planmässigen Abhängigkeiten (Ersatz, Kuppeln, Flügeln) verbunden.

    Bei Ein- und Ausfahrten wird die Ankunfts- und Abfahrtszeit auf 1 Minute vor bzw. nach dem Halt geschätzt.

    Weitere Instanzattribute
    ========================

    bahnhofteile: Ordnet jedem Gleis einen Bahnhofteil zu.
        Der Bahnhofteil entspricht dem alphabetisch ersten Gleis in der Nachbarschaft.
        Der Dictionary wird durch _bahnhofteile_gruppieren gefüllt.
    """

    def __init__(self, name: str, autor: str, version: str, text: str):
        super().__init__(name, autor, version, text)

        self.signalgraph = SignalGraph()
        self.bahnsteiggraph = BahnsteigGraph()
        self.zuggraph = ZugGraph()
        self.zielgraph = ZielGraph()
        self.liniengraph = LinienGraph()
        self.bahnhofteile: Dict[str, str] = {}
        self.anschlussgruppen: Dict[int, str] = {}

    async def request_bahnsteigliste(self):
        await super().request_bahnsteigliste()
        self._bahnsteiggraph_erstellen()
        self._bahnhofteile_gruppieren()

    async def request_wege(self):
        await super().request_wege()
        self._signalgraph_erstellen()
        self._anschluesse_gruppieren()

    async def request_zugliste(self):
        await super().request_zugliste()
        self._zuggraph_erstellen()

    async def request_zugdetails_einzeln(self, zid: int):
        result = await super().request_zugdetails_einzeln(zid)
        if result:
            self._zuggraph_update_zug(zid)
        return result

    async def request_zugfahrplan_einzeln(self, zid: int) -> bool:
        result = await super().request_zugfahrplan_einzeln(zid)
        if result:
            self._zielgraph_update_zug(zid)
        return result

    def _signalgraph_erstellen(self):
        """
        Signalgraph erstellen.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        :return: None
        """

        self.signalgraph.clear()

        for knoten1 in self.wege.values():
            if knoten1.key:
                self.signalgraph.add_node(knoten1.key, typ=knoten1.typ, name=knoten1.name, enr=knoten1.enr)
                for knoten2 in knoten1.nachbarn:
                    self.signalgraph.add_edge(knoten1.key, knoten2.key, typ='verbindung', distanz=1)

        for knoten1, typ in self.signalgraph.nodes(data='typ', default='kein'):
            if typ == 'kein':
                print(f"_signalgraph_erstellen: Knoten {knoten1} hat keinen Typ.")
                self.signalgraph.remove_node(knoten1)

        self.signalgraph.remove_edges_from(nx.selfloop_edges(self.signalgraph))

    def _bahnsteiggraph_erstellen(self):
        """
        Bahnsteiggraph erstellen.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        :return: None
        """

        self.bahnsteiggraph.clear()

        for bs1 in self.bahnsteigliste.values():
            self.bahnsteiggraph.add_node(bs1.name)
            for bs2 in bs1.nachbarn:
                self.bahnsteiggraph.add_edge(bs1.name, bs2.name, typ='bahnsteig', distanz=0)

    def _bahnhofteile_gruppieren(self):
        """
        Bahnhofteile nach Nachbarschaftsbeziehung gruppieren

        Diese Funktion erstellt das bahnhofteile Dictionary.
        """

        self.bahnhofteile = {}

        for comp in nx.connected_components(self.bahnsteiggraph.to_undirected(as_view=True)):
            hauptgleis = sorted(comp)[0]
            for gleis in comp:
                self.bahnhofteile[gleis] = hauptgleis

    def _anschluesse_gruppieren(self):
        for anschluss, data in self.signalgraph.nodes(data=True):
            if data['typ'] in {Knoten.TYP_NUMMER['Einfahrt'], Knoten.TYP_NUMMER['Ausfahrt']}:
                self.anschlussgruppen[anschluss] = data['name']

    def _zuggraph_erstellen(self, clean=False):
        """
        Zuggraph erstellen bzw. aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Per Voreinstellung (clean=False),
        fügt diese Methode neue Knoten und ihre Kanten zum Graphen hinzu.
        Bestehende Knoten werden nicht verändert.
        Um den Graphen neu aufzubauen, sollte clean=True übergeben werden.

        :return: None
        """

        if clean:
            self.zuggraph.clear()

        for zid in self.zugliste:
            self._zuggraph_update_zug(zid)

    def _zuggraph_update_zug(self, zid: int):
        """
        Einzelnen Zug im Zuggraph aktualisieren.

        Wenn der Zugknoten existiert wird er aktualisiert, sonst neu erstellt.
        """

        zug = self.zugliste[zid]
        zug_data = ZugGraphNode.from_zug_details(zug)
        self.zuggraph.add_node(zid, **zug_data)

    def _zielgraph_erstellen(self, clean=False):
        """
        Ziel- und Zuggraphen erstellen bzw. aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Per Voreinstellung (clean=False),
        fügt diese Methode neue Knoten und ihre Kanten zum Graphen hinzu.
        Bestehende Knoten werden nicht verändert.
        Um den Graphen neu aufzubauen, sollte clean=True übergeben werden.

        :return: None
        """

        if clean:
            self.zuggraph.clear()
            self.zielgraph.clear()
            self.liniengraph.clear()

        for zid2, zug2 in self.zugliste.items():
            self._zielgraph_update_zug(zid2)

    def _zielgraph_update_zug(self, zid: int):
        """
        Ziel- und Zuggraphen nach Fahrplan eines Zuges aktualisieren.

        Die Graphen werden in der Dokumentation der Klasse beschrieben.

        Diese Methode fügt neue Knoten und ihre Kanten zum Graphen hinzu oder aktualisiert bestehende.
        Es werden keine Knoten und Kanten gelöscht.

        Bemerkungen
        -----------

        - Der vom Simulator gemeldete Fahrplan enthält nur anzufahrende Ziele.
          Im Zielgraphen werden die abgefahrenen Ziele jedoch beibehalten.

        :param: zid: Zug-ID. Der Zug muss in der Zugliste enthalten sein.
        :return: None
        """

        ziel1 = None
        fid1 = None
        zid2 = zid
        zug2 = self.zugliste[zid]

        self._zuggraph_update_zug(zid)

        for ziel2 in zug2.fahrplan:
            fid2 = ziel2.fid
            ziel_data = ZielGraphNode.from_fahrplanzeile(ziel2)
            ziel_data.bft = self.bahnhofteile[ziel2.plan]
            self.zielgraph.add_node(fid2, **ziel_data)

            if ziel1:
                if fid1 != fid2 and not self.zielgraph.has_edge(fid1, fid2):
                    self.zielgraph.add_edge(fid1, fid2, typ='P')
                    self._liniengraph_add_linie(fid1, fid2)

            if zid3 := ziel2.ersatz_zid():
                self._zielgraph_link_flag(ziel2, zid3, 'E')

            if zid3 := ziel2.kuppel_zid():
                self._zielgraph_link_flag(ziel2, zid3, 'K')

            if zid3 := ziel2.fluegel_zid():
                self._zielgraph_link_flag(ziel2, zid3, 'F')

            ziel1 = ziel2
            fid1 = fid2

        if zug2.von and not zug2.von.startswith("Gleis"):
            fid2 = zug2.fahrplan[0].fid
            dt = datetime.datetime.combine(datetime.datetime.today(), fid2[1])
            dt -= datetime.timedelta(minutes=1)
            einfahrtszeit = dt.time()

            k = self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Einfahrt']].get(zug2.von, None) or \
                self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Ausfahrt']].get(zug2.von, None)
            try:
                fid1 = (zid2, einfahrtszeit, einfahrtszeit, k.enr)
                ziel_data = {'fid': fid1,
                             'zid': zid2,
                             'typ': 'E',
                             'plan': k.enr,
                             'gleis': k.enr,
                             'bft': self.anschlussgruppen[k.enr],
                             'p_an': time_to_minutes(einfahrtszeit),
                             'p_ab': time_to_minutes(einfahrtszeit)}
            except (AttributeError, KeyError):
                logger.error(f"Fehler in Einfahrtsdaten {fid1}, Knoten {k}")
            else:
                self.zielgraph.add_node(fid1, **ziel_data)
                if not self.zielgraph.has_edge(fid1, fid2):
                    self.zielgraph.add_edge(fid1, fid2, typ='P')
                    self._liniengraph_add_linie(fid1, fid2)

        if zug2.nach and not zug2.nach.startswith("Gleis"):
            fid2 = zug2.fahrplan[-1].fid
            dt = datetime.datetime.combine(datetime.datetime.today(), fid2[1])
            dt += datetime.timedelta(minutes=1)
            ausfahrtszeit = dt.time()

            k = self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Ausfahrt']].get(zug2.nach, None) or \
                self.wege_nach_typ_namen[Knoten.TYP_NUMMER['Einfahrt']].get(zug2.nach, None)
            try:
                fid1 = (zid2, ausfahrtszeit, ausfahrtszeit, k.enr)
                ziel_data = {'fid': fid1,
                             'zid': zid2,
                             'typ': 'A',
                             'plan': k.enr,
                             'gleis': k.enr,
                             'bft': self.anschlussgruppen[k.enr],
                             'p_an': time_to_minutes(ausfahrtszeit),
                             'p_ab': time_to_minutes(ausfahrtszeit)}
            except (AttributeError, KeyError):
                logger.warning(f"Fehler in Ausfahrtsdaten {fid1}, Knoten {k}")
            else:
                self.zielgraph.add_node(fid1, **ziel_data)
                if not self.zielgraph.has_edge(fid2, fid1):
                    self.zielgraph.add_edge(fid2, fid1, typ='P')
                    self._liniengraph_add_linie(fid2, fid1)

    def _zielgraph_link_flag(self, ziel2, zid3, typ):
        """
        Zugziele verknüpfen.

        Unterfunktion von _zielgraph_update_zug.
        """

        fid2 = ziel2.fid
        zid2 = ziel2.zug.zid

        if zid2 != zid3:
            self.zuggraph.add_edge(zid2, zid3, typ=typ)
        try:
            zug3 = self.zugliste[zid3]
            if typ == 'K':
                _, ziel3 = zug3.find_fahrplan(plan=ziel2.plan, zeit=ziel2.an)
            else:
                ziel3 = zug3.fahrplan[0]
            fid3 = ziel3.fid
        except (AttributeError, IndexError, KeyError):
            logger.debug(f"{typ}-Ziel von {fid2} oder Zug {zid3} nicht gefunden")
        else:
            if fid2 != fid3:
                self.zielgraph.add_edge(fid2, fid3, typ=typ)

    def _liniengraph_add_linie(self, fid1, fid2):
        """
        Liniengrpah erstellen

        Der Liniengraph benötigt den Zielgraph und den Bahnsteiggraph.

        Sollte nicht mehr als einmal pro Zug aufgerufen werden, da sonst die Statistik verfaelscht werden kann.
        """

        MAX_FAHRZEIT = 24 * 60

        halt1 = self.zielgraph.nodes[fid1]
        halt2 = self.zielgraph.nodes[fid2]

        try:
            typ1 = self.signalgraph.nodes[fid1[3]]['typ']
            typ2 = self.signalgraph.nodes[fid2[3]]['typ']
        except KeyError:
            logger.warning(f"Liniengraph erstellen: Fehlende Typ-Angabe im Zielgraph von Knoten {fid1} oder {fid2}")
            return

        try:
            bft1 = halt1['bft']
            bft2 = halt2['bft']
        except KeyError:
            logger.warning(f"Liniengraph erstellen: Fehlende Bft-Angabe im Zielgraph von Knoten {fid1} oder {fid2}")
            return

        try:
            fahrzeit = halt2['an'] - halt1['ab']
            # beschleunigungszeit von haltenden zuegen kompensieren
            if halt1['typ'] == 'D':
                fahrzeit += 1
        except KeyError:
            fahrzeit = 2

        try:
            liniendaten = self.liniengraph[bft1][bft2]
        except KeyError:
            liniendaten = dict(fahrzeit_min=MAX_FAHRZEIT, fahrzeit_max=0,
                               fahrten=0, fahrzeit_summe=0., fahrzeit_schnitt=0.)

        liniendaten['fahrzeit_min'] = min(liniendaten['fahrzeit_min'], fahrzeit)
        liniendaten['fahrzeit_max'] = max(liniendaten['fahrzeit_max'], fahrzeit)
        liniendaten['fahrten'] = liniendaten['fahrten'] + 1
        liniendaten['fahrzeit_summe'] = liniendaten['fahrzeit_summe'] + fahrzeit
        liniendaten['fahrzeit_schnitt'] = liniendaten['fahrzeit_summe'] / liniendaten['fahrten']

        self.liniengraph.add_edge(bft1, bft2, **liniendaten)
        self.liniengraph.add_node(bft1, typ=typ1)
        self.liniengraph.add_node(bft2, typ=typ2)


async def test() -> GraphClient:
    """
    Testprogramm

    Das testprogramm fragt alle Daten einmalig vom Simulator ab.

    Der GraphClient bleibt bestehen, damit weitere Details aus den statischen Attributen ausgelesen werden können.
    Die Kommunikation mit dem Simulator wird jedoch geschlossen.

    :return: GraphClient-instanz
    """

    client = GraphClient(name='test', autor='tester', version='0.0', text='testing the graph client')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                await client.request_bahnsteigliste()
                await client.request_wege()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
                await client.resolve_zugflags()
                raise TaskDone()
    except TaskDone:
        pass

    return client


if __name__ == '__main__':
    trio.run(test)
