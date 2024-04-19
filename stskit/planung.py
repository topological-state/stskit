from dataclasses import dataclass
import datetime
import json
import logging
import os
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Type, Union
import weakref

import numpy as np
import networkx as nx
import trio

from stskit.stsobj import ZugDetails, FahrplanZeile, Ereignis
from stskit.stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from stskit.stsplugin import PluginClient, TaskDone
from stskit.auswertung import Auswertung


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZugZielNode(NamedTuple):
    """
    knotenobjekt für zugziel-graph

    der knoten ist ein eindeutiger schlüssel des zugziels
    und besteht aus einem tupel von zid, plangleis und zielnummer.
    um einen knoten im zielgraph zu finden, muss zuerst ein ZugZielNode als schlüssel für den graphen erstellt werden.
    die zielnummer ist nötig, damit ein gleis mehrmals befahren werden kann.
    """

    zid: int
    zielnr: int
    plangleis: str

    @classmethod
    def neu(cls, ziel: 'ZugZielPlanung' = None, plangleis: Optional[str] = None, zid: Optional[int] = None,
            zielnr: Optional[int] = None) -> 'ZugZielNode':
        """
        knoten für zugziel-graph erstellen

        der knoten ist ein eindeutiger schlüssel des zugziels vom typ ZugZielNode.
        zwei ZugZielNodes, die mit denselben argumenten definiert werden, werden als gleich erachtet.

        der schlüssel kann aus einem ZugZielPlanung oder den einzelnen komponenten erstellt werden.
        zur bedeutung der typenflags, siehe die beschreibung der _zielgraph_erstellen-methode.
        die zielnummer dient der disambiguation bei mehrfach befahrenen gleisen.

        :param ziel: zielobjekt, zu dem ein schlüssel generiert werden soll.
            wenn das ziel nicht angegeben wird, müssen alle andere keywords deklariert werden.
        :param plangleis: überschreibt das plangleis von ziel
        :param zid: überschreibt das zid von ziel
        :param zielnr: überschreibt zielnr von ziel
        :return: ZugZielNode
        """

        if plangleis is None:
            plangleis = ziel.plan

        if zid is None:
            zid = ziel.zug.zid

        if zielnr is None:
            zielnr = ziel.zielnr

        return cls(zid, zielnr, plangleis)

    @staticmethod
    def zieltyp(ziel: 'ZugZielPlanung'):
        if ziel.einfahrt:
            typ = 'E'
        elif ziel.ausfahrt:
            typ = 'A'
        elif ziel.zielnr > int(ziel.zielnr / 1000) * 1000:
            typ = 'B'
        elif ziel.durchfahrt():
            typ = 'D'
        else:
            typ = 'H'
        return typ

    @classmethod
    def init_zieldata(cls, ziel: 'ZugZielPlanung') -> Dict:
        """
        erstellt den data-dictionary eines knotens im zielbaum

        :param ziel: ZugZielPlanung-objekt
        :return: dict
        """
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            plan_an = None
        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an
        if plan_an is None:
            plan_an = plan_ab

        data = {'typ': cls.zieltyp(ziel),
                'obj': ziel,
                'zid': ziel.zug.zid,
                'zielnr': ziel.zielnr,
                'plan': ziel.plan,
                'd_min': ziel.mindestaufenthalt,
                'p_an': plan_an,
                'p_ab': plan_ab,
                'v_an': ziel.verspaetung_an,
                'v_ab': ziel.verspaetung_ab}

        return data


def graph_pred_filter_flag(graph: nx.DiGraph, node: ZugZielNode, typ: str) -> Iterable[ZugZielNode]:
    for zzid in graph.predecessors(node):
        if graph.edges[zzid, node]['typ'] == typ:
            yield zzid


def graph_succ_filter_flag(graph: nx.DiGraph, node: ZugZielNode, typ: str) -> Iterable[ZugZielNode]:
    for zzid in graph.successors(node):
        if graph.edges[node, zzid]['typ'] == typ:
            yield zzid


class VerspaetungsKorrektur:
    """
    basisklasse für die anpassung der verspätungszeit eines fahrplanziels

    eine VerspaetungsKorrektur-klasse besteht im wesentlichen aus der anwenden-methode.
    diese berechnet für das gegebene ziel die abfahrtsverspätung aus der ankunftsverspätung
    und ggf. weiteren ziel- bzw. zugdaten.

    über das _planung-attribut hat die klasse zugriff auf die ganze zugliste.
    sie darf jedoch nur das angegebene ziel sowie allfällige verknüpfte züge direkt ändern.

    """
    def __init__(self, planung: 'Planung'):
        # super().__init__()
        self._planung = planung
        self.edge_typ = ""
        self.rang: int = 0
        self.display_name = "Default"
        self._node: ZugZielNode = None

    def __str__(self):
        return self.display_name

    @property
    def node(self) -> ZugZielNode:
        return self._node

    @node.setter
    def node(self, node: Union[ZugZielNode, 'ZugZielPlanung']):
        if isinstance(node, ZugZielNode):
            self._node = node
        else:
            self._node = ZugZielNode.neu(node)

    @property
    def relation(self) -> Tuple[ZugZielNode, ...]:
        """
        gibt die abhängigkeit (kante) im zielgraph an

        wenn die klasse ein attribut ursprung enthält, ist die relation (ursprung, node).
        wenn die klasse ein attribut folge enthält, ist die relation (node, folge).
        ansonsten liefert das property (node), d.h. die korrektur hat keine abhängigkeit im zielgraph.

        :return: tuple von ZugZielNode
        """

        try:
            return self.ursprung, self.node
        except AttributeError:
            try:
                return self.node, self.folge
            except AttributeError:
                return self.node

    def ankunft_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        """
        ankunftsverspätung berechnen

        die methode erhält den zielgraphen mit schlüssel und zieldaten.
        die methode berechnet die ankunftsverspätung v_an am angegebenen fahrziel.
        sie darf dazu die daten von allen eingehenden kanten des zielgraphen verwenden.

        in dieser klasse ist eine default-verarbeitung implementiert,
        die die ankunftsverspätung von eingehenden P-kanten übernimmt,
        entsprechend einem regulären ziel, ohne die verspätung aufzuholen.
        """

        ankunft = None
        for pred in graph.pred[node]:
            try:
                pred_data = graph.nodes[pred]
                pred_v_ab = pred_data['v_ab']
                pred_v_an = pred_data['v_an']
                pred_p_an = pred_data['p_an']
                pred_p_ab = pred_data['p_ab']
                edge_data = graph[pred][node]
                edge_typ = edge_data['typ']
            except KeyError:
                continue
            else:
                if edge_typ == 'P':
                    # gleiche verspaetung wie vorgaenger
                    ankunft = max(ankunft or 0, node_data['p_an'] + pred_v_ab)
                elif edge_typ == 'E':
                    # ankunft ist gleich abfahrt des vorgaengers
                    try:
                        ankunft = max(ankunft or 0, pred_p_ab + pred_v_ab)
                    except TypeError:
                        logger.warning(f"ankunft berechnen: stammzug hat keine abfahrtszeit {pred_data}")
                elif edge_typ == 'F':
                    # ankunft ist gleich ankunft des vorgaengers
                    ankunft = max(ankunft or 0, pred_p_an + pred_v_an)
                elif edge_typ == 'K':
                    # ankunft des kuppelziels haengt nicht vom kuppelnden zug ab
                    pass

        if ankunft is not None:
            node_data['v_an'] = ankunft - node_data['p_an']

        logger.debug(f"{self.__class__.__name__}.ankunft_berechnen: {node}, {node_data}")

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        """
        abfahrtsverspätung berechnen

        die methode erhält den zielgraphen mit schlüssel und zieldaten.
        die methode berechnet die abfahrtsverspätung v_ab am angegebenen fahrziel.
        sie darf dazu die daten von allen eingehenden kanten des zielgraphen verwenden.
        anfangs ist v_ab = v_an.
        der werte sollte wenn nötig via max-funktion erhöht werden und
        nur in speziellen fällen bedingungslos überschrieben oder verkleinert werden.

        in dieser klasse ist eine default-verarbeitung implementiert,
        die lediglich ankunftsverspätung übernimmt,
        entsprechend einem regulären halt, ohne die verspätung aufzuholen.
        """

        node_data['v_ab'] = node_data['v_an']

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class Durchfahrt(VerspaetungsKorrektur):
    """
    durchfahrt

    dies ist die normale abfertigung, soweit kein anderer zug involviert ist.
    die verspätung wird durchgereicht.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Durchfahrt"


class Planhalt(VerspaetungsKorrektur):
    """
    planmässige abfahrt oder verspätung aufholen wenn möglich

    dies ist die normale abfertigung, soweit kein anderer zug involviert ist.
    die verspätung wird soweit möglich reduziert, ohne die mindestaufenthaltsdauer zu unterschreiten.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Planhalt"

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        ankunft = node_data['p_an'] + node_data['v_an']
        v_ab = max(0, node_data['d_min'] + ankunft - node_data['p_ab'])
        node_data['v_ab'] = v_ab

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class FesteVerspaetung(VerspaetungsKorrektur):
    """
    abfahrtsverspätung auf einen festen wert setzen.

    kann bei vorzeitiger abfahrt auch negativ sein.

    diese klasse ist für manuelle eingriffe des fahrdienstleiters gedacht.
    die aktuelle betriebslage wird nicht berücksichtigt.

    die korrektur ist nicht geeignet in kombination mit anderen abhängigkeiten.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.verspaetung: int = 0
        self.display_name = "Verspätung"

    def __str__(self):
        return f"{self.display_name}({self.verspaetung})"

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")
        node_data['v_ab'] = self.verspaetung


class Signalhalt(FesteVerspaetung):
    """
    verspätung durch signalhalt

    diese klasse wird in der verarbeitung des Abfahrt-ereignisses eingesetzt,
    wenn der zug an einem bahnsteig steht, auf ein offenes signal wartet und dadurch verspätet wird.
    die wirkung auf den fahrplan ist dieselbe wie von FesteVerspaetung.
    der andere name und objekt-string dient der unterscheidung.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Signalhalt"


class Einfahrtszeit(VerspaetungsKorrektur):
    """
    verspätete einfahrt

    die vom simulator gemeldete einfahrtszeit (inkl. verspätung) ist manchmal kleiner als die aktuelle sim-zeit.
    in diesem fall erhöht diese korrektur die verspätung, so dass die einfahrtszeit der aktuellen uhrzeit entspricht.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Einfahrt"

    def ankunft_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        logger.debug(f"{self.__class__.__name__}.ankunft_berechnen: {node}, {node_data}")

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        ankunft = node_data['p_an'] + node_data['v_an']
        abfahrt = max(ankunft, self._planung.simzeit_minuten)
        node_data['v_ab'] = abfahrt - node_data['p_ab']
        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class AbhaengigkeitsZiel:
    """
    verspätungsmixin fuer ursprungszug

    die verspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach einem anderen zug.

    diese klasse führt das property ursprung ein.

    attribute
    --------

    - ursprung: fahrplanziel des verknuepften zuges
    - ursprung_name: name des verknuepften zuges - fuer anzeige
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self._ursprung: Optional[ZugZielNode] = None

    @property
    def ursprung(self) -> ZugZielNode:
        return self._ursprung

    @ursprung.setter
    def ursprung(self, value):
        if isinstance(value, ZugZielNode):
            self._ursprung = value
        else:
            self._ursprung = ZugZielNode.neu(ziel=value)

    @property
    def ursprung_name(self) -> Union[str, int]:
        try:
            return self._planung.zielgraph.nodes[self._ursprung]['obj'].zug.name
        except AttributeError:
            return self._ursprung.zid
        except KeyError:
            pass
        return "-----"


class AbhaengigkeitsUrsprung:
    """
    verspätungsmixin fuer zielzug

    die verspätung des zuges wirkt sich auf einen anderen aus.

    diese klasse führt das property folge ein.

    attribute
    --------

    - folge: fahrplanziel des verknuepften zuges
    - folge_name: name des verknuepften zuges - fuer anzeige
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self._folge: Optional[ZugZielNode] = None

    @property
    def folge(self) -> ZugZielNode:
        return self._folge

    @folge.setter
    def folge(self, value):
        if isinstance(value, ZugZielNode):
            self._folge = value
        else:
            self._folge = ZugZielNode.neu(ziel=value)

    @property
    def folge_name(self) -> Union[str, int]:
        try:
            return self._planung.zielgraph.nodes[self._folge]['obj'].zug.name
        except AttributeError:
            pass
        except KeyError:
            pass
        except TypeError:
            pass
        return "(?)"


class ZugAbwarten(VerspaetungsKorrektur, AbhaengigkeitsZiel):
    """
    wartet auf einen anderen zug.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach einem anderen zug.

    diese klasse ist eine abstrakte klasse für AnkunftAbwarten und AbfahrtAbwarten.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "A"
        self.display_name = "Zug"
        self.wartezeit: int = 0

    def __str__(self):
        return f"{self.display_name}({self.ursprung_name}, {self._ursprung.plangleis}, {self.wartezeit})"

    def ankunft_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        """
        ankunft wird von dieser korrektur nicht beruehrt

        :param graph:
        :param node:
        :param node_data:
        :return:
        """
        logger.debug(f"{self.__class__.__name__}.ankunft_berechnen: {node}, {node_data}")

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        """
        default-verarbeitung für abhängigkeiten

        die default-verarbeitung verändert keine verspätungsparameter.
        die verarbeitung wird in abgeleiteten objekten definiert.

        :param graph:
        :param node:
        :param node_data:
        :return:
        """

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class AnkunftAbwarten(ZugAbwarten):
    """
    wartet auf die ankunft eines anderen zuges.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der effektiven ankunftszeit des anderen zuges
    oder der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei ersatzzügen, kupplungen und flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Ankunft"
        self.wartezeit = planung.params.wartezeit_ankunft_abwarten

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        ankunft = node_data['p_an'] + node_data['v_an']
        aufenthalt = max(node_data['p_ab'] - ankunft, node_data['d_min'])
        anschluss = graph.nodes[self.ursprung]
        anschluss_an = anschluss['p_an'] + anschluss['v_an']
        anschluss_ab = anschluss_an + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        node_data['v_ab'] = max(node_data['v_ab'], abfahrt - node_data['p_ab'])

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class AbfahrtAbwarten(ZugAbwarten):
    """
    wartet, bis ein anderer zug abgefahren ist.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der abfahrtszeit des anderen zuges und der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Abfahrt"
        self.wartezeit = planung.params.wartezeit_abfahrt_abwarten

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        ankunft = node_data['p_an'] + node_data['v_an']
        aufenthalt = max(node_data['p_ab'] - ankunft, node_data['d_min'])
        anschluss = graph.nodes[self.ursprung]
        anschluss_ab = anschluss['p_ab'] + anschluss['v_ab']
        anschluss_ab = anschluss_ab + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        node_data['v_ab'] = max(node_data['v_ab'], abfahrt - node_data['p_ab'])

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class ZugNichtAbwarten(ZugAbwarten):
    """
    wartet nicht auf einen anderen zug.

    diese klasse dient als markierung, dass der zug einen anschluss nicht abwartet.
    sie hat keine auswirkung auf die verspätung.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "X"
        self.display_name = "Nicht warten"


class FlagKorrektur(VerspaetungsKorrektur):
    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Flag"


class FlagUrsprung(FlagKorrektur, AbhaengigkeitsUrsprung):
    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Flag"

    def __str__(self):
        return f"{self.display_name} → {self.folge_name}"


class FlagZiel(FlagKorrektur, AbhaengigkeitsZiel):
    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Flagziel"

    def __str__(self):
        return f"{self.display_name} ← {self.ursprung_name}"


class ErsatzUrsprung(FlagUrsprung):
    """
    abfahrt frühestens wenn nummernwechsel abgeschlossen ist

    p_an: planmaessige ankunftszeit am bahnsteig
    p_ab: zeit des nummernwechsels. muss gleich sein wie p_an des folgeziels.

    das erste fahrplanziel des ersatzzuges muss it einer ErsatzZiel-korrektur markiert sein.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "E"
        self.display_name = "Ersatz"

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        """
        abfahrtszeit = zeit des nummernwechsels
        """

        ankunft = node_data['p_an'] + node_data['v_an']
        aufenthalt = max(node_data['p_ab'] - ankunft, node_data['d_min'])
        abfahrt = ankunft + aufenthalt
        node_data['v_ab'] = abfahrt - node_data['p_ab']

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class ErsatzZiel(FlagZiel):
    """
    abfahrt frühestens wenn nummernwechsel abgeschlossen ist

    p_an: zeit des nummernwechsels. muss gleich sein wie p_ab des stammziels.
    p_ab: planmaessige abfahrtszeit

    funkioniert in verbindung mit ErsatzUrsprung.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.display_name = "Ersatz"
        self.rang = 1

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        ankunft = node_data['p_an'] + node_data['v_an']
        aufenthalt = max(node_data['p_ab'] - ankunft, node_data['d_min'])
        abfahrt = ankunft + aufenthalt
        node_data['v_ab'] = abfahrt - node_data['p_ab']

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class FluegelungUrsprung(FlagUrsprung):
    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "F"
        self.display_name = "Flügelung"


class FluegelungZiel(FlagZiel):
    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "P"
        self.display_name = "Flügelung"
        self.rang = 2

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        try:
            pred_data = graph.nodes[self.ursprung]
            pred_v_ab = pred_data['v_ab']
            pred_v_an = pred_data['v_an']
            pred_p_ab = pred_data['p_ab']
        except KeyError:
            logger.warning(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data} - keine ursprungsdaten!")
            return

        abfahrt = max(pred_p_ab + pred_v_ab, node_data['p_ab'])
        node_data['v_ab'] = abfahrt - node_data['p_ab']

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}")


class KupplungUrsprung(FlagUrsprung):
    """
    zwei züge kuppeln

    gekuppelter zug kann erst abfahren, wenn beide züge angekommen sind.

    bemerkung: der zug mit dem kuppel-flag verschwindet. der verlinkte zug fährt weiter.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "K"
        self.display_name = "Kupplung"


class KupplungZiel(FlagZiel):
    """
    zwei züge kuppeln

    gekuppelter zug kann erst abfahren, wenn beide züge angekommen sind.

    bemerkung: der zug mit dem kuppel-flag verschwindet. der verlinkte zug fährt weiter.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.edge_typ = "P"
        self.display_name = "Kupplung"
        self.rang = 3

    def abfahrt_berechnen(self, graph: nx.DiGraph, node: ZugZielNode, node_data: Dict[str, Any]):
        try:
            ursprung_data = graph.nodes[self.ursprung]
            bereitschaft1 = ursprung_data['p_an'] + ursprung_data['v_an']
        except KeyError:
            logger.warning(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data} - keine ursprungsdaten!")
            ursprung_data = None
            bereitschaft1 = 0

        try:
            ankunft2 = node_data['p_an'] + node_data['v_an']
            aufenthalt2 = max(node_data['p_ab'] - ankunft2, node_data['d_min'])
            bereitschaft2 = ankunft2 + aufenthalt2
        except KeyError:
            bereitschaft2 = 0

        kuppelzeit = max(bereitschaft1, bereitschaft2)

        if ursprung_data is not None:
            ursprung_data['v_ab'] = kuppelzeit - ursprung_data['p_ab']
        try:
            node_data['v_ab'] = kuppelzeit - node_data['p_ab']
        except KeyError:
            node_data['v_ab'] = ursprung_data['v_ab']

        logger.debug(f"{self.__class__.__name__}.abfahrt_berechnen: {node}, {node_data}, kuppelzeit: {kuppelzeit}")


class ZugDetailsPlanung(ZugDetails):
    """
    ZugDetails für das planungsmodul

    dies ist eine unterklasse von ZugDetails, wie sie vom planungsmodul verwendet wird.
    im planungsmodul haben einige attribute eine geänderte bedeutung.
    insbesondere bleibt der fahrplan vollständig (abgefahrene ziele werden nicht gelöscht)
    und enthält auch die ein- und ausfahrten als erste/letzte zeile
    (ausser der zug beginnt oder endet im stellwerk).

    wenn der zug neu angelegt wird, übernimmt die assign_zug_details-methode die daten vom PluginClient.
    die update_zug_details-methode aktualisert die veränderlichen attribute, z.b. gleis, verspätung etc.
    """
    def __init__(self):
        super().__init__()
        self.ausgefahren: bool = False
        self.folgezuege_aufgeloest: bool = False
        self.korrekturen_definiert: bool = False

    @property
    def einfahrtszeit(self) -> datetime.time:
        """
        planmässige einfahrtszeit (ohne verspätung)

        dies entspricht der abfahrtszeit des ersten fahrplaneintrags (einfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[0].ab

    @property
    def ausfahrtszeit(self) -> datetime.time:
        """
        planmässige ausfahrtszeit (ohne verspätung)

        dies enstspricht der ankunftszeit des letzten fahrplaneintrags (ausfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[-1].an

    def route(self, plan: bool = False) -> Iterable[str]:
        """
        route (reihe von stationen) des zuges als generator

        die route ist eine liste von stationen (gleisen, ein- und ausfahrt) in der reihenfolge des fahrplans.
        ein- und ausfahrten können bei ersatzzügen o.ä. fehlen.
        durchfahrtsgleise sind auch enthalten.

        die methode liefert das gleiche ergebnis wie die überschriebene methode.
        aber da in der planung die ein- und ausfahrten im fahrplan enthalten sind,
        ist die implementierung etwas einfacher.

        :param plan: plangleise statt effektive gleise melden
        :return: generator
        """
        for fpz in self.fahrplan:
            if plan:
                yield fpz.plan
            else:
                yield fpz.gleis

    def assign_zug_details(self, zug: ZugDetails):
        """
        objekt mit stammdaten vom PluginClient initialisieren.

        unterschiede zum original-ZugDetails:
        - ein- und ausfahrtsgleise werden als separate fahrplanzeile am anfang bzw. ende der liste eingefügt
          und mit den attributen einfahrt bzw. ausfahrt markiert.
          ankunfts- und abfahrtszeiten werden dem benachbarten fahrplanziel gleichgesetzt.
          versteckte ein- und ausfahrtsgleise werden entfernt.
        - der text 'Gleis', wenn der zug im stellwerk beginnt oder endet, wird aus dem von/nach entfernt.
          das gleis befindet sich bereits im fahrplan, es wird keine zusätzliche ein-/ausfahrt-zeile eingefügt.

        :param zug: original-ZugDetails-objekt vom PluginClient.zugliste.
        :return: None
        """
        self.zid = zug.zid
        self.name = zug.name
        self.von = zug.von.replace("Gleis ", "") if zug.von else ""
        self.nach = zug.nach.replace("Gleis ", "") if zug.nach else ""
        self.hinweistext = zug.hinweistext

        self.fahrplan = []
        zug_fahrplan = zug.fahrplan

        # einfahrt
        if not zug.sichtbar and self.von and not zug.von.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            self.fahrplan.append(ziel)
            ziel.einfahrt = True
            ziel.variable_zeit = True
            ziel.plan = ziel.gleis = self.von
            try:
                ziel.ab = ziel.an = zug.fahrplan[0].an
                if zug.fahrplan[0].plan == ziel.plan:
                    ziel.variable_zeit = False
                    zug_fahrplan = zug.fahrplan[1:]
            except IndexError:
                pass

        # bahnsteige
        for zeile in zug_fahrplan:
            ziel = ZugZielPlanung(self)
            ziel.assign_fahrplan_zeile(zeile)
            self.fahrplan.append(ziel)

        # ausfahrt
        if self.nach and not zug.nach.startswith("Gleis"):
            ziel = self.fahrplan[-1]
            if ziel.plan != zug.nach:
                ziel = ZugZielPlanung(self)
                self.fahrplan.append(ziel)
                ziel.variable_zeit = True

            ziel.plan = ziel.gleis = self.nach
            try:
                ziel.ab = ziel.an = zug.fahrplan[-1].ab
            except IndexError:
                pass
            ziel.ausfahrt = True

        for n, z in enumerate(self.fahrplan):
            z.zielnr = n * 1000

        # zug ist neu in liste und schon im stellwerk -> startaufstellung
        if zug.sichtbar:
            ziel_index = self.find_fahrplan_index(plan=zug.plangleis)
            if ziel_index is None:
                # ziel ist ausfahrt
                ziel_index = -1
            for ziel in self.fahrplan[0:ziel_index]:
                ziel.abgefahren = ziel.angekommen = True
                ziel.verspaetung_ab = ziel.verspaetung_an = zug.verspaetung
            if zug.amgleis:
                ziel = self.fahrplan[ziel_index]
                ziel.angekommen = True
                ziel.verspaetung_an = zug.verspaetung

    def update_zug_details(self, zug: ZugDetails):
        """
        aktualisiert die veränderlichen attribute eines zuges

        die folgenden attribute werden aktualisert, alle anderen bleiben unverändert.
        gleis, plangleis, amgleis, sichtbar, verspaetung, usertext, usertextsender, fahrplanzeile.
        wenn der zug ausfährt, wird das gleis dem nach-attribut gleichgesetzt.

        im fahrplan werden die gleisänderungen aktualisiert.

        anstelle des zuges kann auch ein ereignis übergeben werden.
        Ereignis-objekte entsprechen weitgehend den ZugDetails-objekten,
        enthalten jedoch keinen usertext und keinen fahrplan.

        :param zug: ZugDetails- oder Ereignis-objekt vom PluginClient.
        :return: None
        """

        if zug.gleis:
            self.gleis = zug.gleis
            self.plangleis = zug.plangleis
        else:
            self.gleis = self.plangleis = self.nach

        self.verspaetung = zug.verspaetung
        self.amgleis = zug.amgleis
        self.sichtbar = zug.sichtbar

        if not isinstance(zug, Ereignis):
            self.usertext = zug.usertext
            self.usertextsender = zug.usertextsender

        for zeile in zug.fahrplan:
            ziel = self.find_fahrplanzeile(plan=zeile.plan)
            try:
                ziel.update_fahrplan_zeile(zeile)
            except AttributeError:
                pass

        route = list(self.route(plan=True))
        try:
            self.ziel_index = route.index(zug.plangleis)
        except ValueError:
            # zug faehrt aus
            if not zug.plangleis:
                self.ziel_index = -1
        else:
            # falls ein ereignis vergessen gegangen ist, vergangene ziele markieren
            if self.sichtbar:
                for ziel in self.fahrplan[0:max(0, self.ziel_index)]:
                    ziel.angekommen = ziel.angekommen or True
                for ziel in self.fahrplan[0:max(0, self.ziel_index-1)]:
                    ziel.abgefahren = ziel.abgefahren or True

    def find_fahrplan_zielnr(self, zielnr: int) -> 'ZugZielPlanung':
        """
        fahrplaneintrag nach zielnummer suchen

        :param zielnr: gesuchte zielnr
        :return: ZugZielPlanung
        :raise: ValueError, wenn zielnr nicht gefunden wird.
        """

        for ziel in self.fahrplan:
            if ziel.zielnr == zielnr:
                return ziel
        else:
            raise ValueError(f"zielnr {zielnr} nicht gefunden in zug {self.name}")


class ZugZielPlanung(FahrplanZeile):
    """
    fahrplanzeile im planungsmodul

    in ergänzung zum originalen FahrplanZeile objekt, führt diese klasse:
    - nach ziel aufgelöste ankunfts- und abfahrtsverspätung.
    - daten zur verspätungsanpassung.
    - status des fahrplanziels.
      nach ankunft/abfahrt sind die entsprechenden verspätungsangaben effektiv, vorher schätzwerte.

    attribute
    ---------

    zielnr: definiert die reihenfolge von fahrzielen.
            bei originalen fahrzielen entspricht sie fahrplan-index multipliziert mit 1000.
            bei eingefügten betriebshalten ist sie nicht durch 1000 teilbar.
            die zielnummer wird als schlüssel in der gleisbelegung verwendet.
            sie wird vom ZugDetailsPlanung-objekt gesetzt
            und ändert sich über die lebensdauer des zugobjekts nicht.

    einfahrt: zeigt an, ob das fahrziel die einfahrt beschreibt.

    ausfahrt: zeigt an, ob das fahrziel die ausfahrt beschreibt.

    variable_zeit: zeigt bei ein- und ausfahrten an, dass die ankunfts- und abfahrtszeiten geschätzt werden
        (methode `einfahrten_korrigieren`).

    verspaetung_an: ankunftsverspätung in minuten.
        die verspätung ist effektiv, wenn `angekommen` True ist, sonst geschätzt.

    verspaetung_ab: abfahrtsverspätung in minuten.
        die verspätung ist effektiv, wenn `abgefahren` True ist, sonst geschätzt.

    mindestaufenthalt: mindestaufenthaltsdauer an diesem fahrziel in minuten.
        wird von `korrekturen_definieren` bestimmt.

    auto_korrektur: automatische verspätungskorrektur.
        wird von `korrekturen_definieren` bestimmt.

    fdl_korrektur: vom fdl definierte korrekturen und abhängigkeiten.

    angekommen: zeigt an, ob der zug an dem ziel bereits angekommen ist.

    abgefahren: zeigt an, ob der zug an dem ziel bereits abgefahren ist.
    """

    def __init__(self, zug: ZugDetails):
        super().__init__(zug)

        self.zielnr: Optional[int] = None
        self.einfahrt: bool = False
        self.ausfahrt: bool = False
        self.variable_zeit: bool = False
        self.verspaetung_an: int = 0
        self.verspaetung_ab: int = 0
        self.mindestaufenthalt: int = 0
        self.auto_korrektur: Optional[VerspaetungsKorrektur] = None
        self.fdl_korrektur: Dict[Tuple[ZugZielNode, ...], VerspaetungsKorrektur] = {}
        self._angekommen: Union[bool, datetime.datetime] = False
        self._abgefahren: Union[bool, datetime.datetime] = False

    def __hash__(self) -> int:
        """
        zugziel-hash

        der hash basiert auf den eindeutigen, unveränderlichen attributen zug.zid und plan.

        :return: hash-wert
        """
        return hash((self.zug.zid, self.plan, self.zielnr))

    def __eq__(self, other: 'ZugZielPlanung') -> bool:
        """
        gleichheit von zwei fahrplanzeilen feststellen.

        gleichheit bedeutet: gleicher zug und gleiches plangleis.
        jedes plangleis kommt im sts-fahrplan nur einmal vor.

        :param other: zu vergleichendes FahrplanZeile-objekt
        :return: True, wenn zug und plangleis übereinstimmen, sonst False
        """
        return self.zug.zid == other.zug.zid and self.zielnr == other.zielnr and self.plan == other.plan

    def __str__(self):
        if self.gleis == self.plan:
            return f"Ziel {self.zug.zid}-{self.zielnr}: " \
                   f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Ziel {self.zug.zid}-{self.zielnr}: " \
                   f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"ZugZielPlanung({self.zug.zid}-{self.zielnr}," \
               f"{self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

    def assign_fahrplan_zeile(self, zeile: FahrplanZeile):
        """
        objekt aus fahrplanzeile initialisieren.

        die gemeinsamen attribute werden übernommen.
        folgezüge bleiben leer.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
        self.gleis = zeile.gleis
        self.plan = zeile.plan
        self.an = zeile.an
        self.ab = zeile.ab
        self.flags = zeile.flags
        self.hinweistext = zeile.hinweistext

        # die nächsten drei attribute werden separat anhand der flags aufgelöst.
        self.ersatzzug = None
        self.fluegelzug = None
        self.kuppelzug = None

    def update_fahrplan_zeile(self, zeile: FahrplanZeile):
        """
        objekt aus fahrplanzeile aktualisieren.

        aktualisiert werden nur:
        - gleis: weil möglicherweise eine gleisänderung vorgenommen wurde.

        alle anderen attribute sind statisch oder werden vom Planung objekt aktualisiert.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
        self.gleis = zeile.gleis

    @property
    def ankunft_minute(self) -> Optional[int]:
        """
        ankunftszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.an) + self.verspaetung_an
        except AttributeError:
            return None

    @property
    def abfahrt_minute(self) -> Optional[int]:
        """
        abfahrtszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.ab) + self.verspaetung_ab
        except AttributeError:
            return None

    @property
    def verspaetung(self) -> int:
        """
        abfahrtsverspaetung

        dies ist ein alias von verspaetung_ab und sollte in neuem code nicht mehr verwendet werden.

        :return: verspaetung in minuten
        """
        return self.verspaetung_ab

    @property
    def gleistyp(self) -> str:
        if self.einfahrt:
            return 'Einfahrt'
        elif self.ausfahrt:
            return 'Ausfahrt'
        else:
            return 'Gleis'

    @property
    def angekommen(self) -> Union[bool, datetime.datetime]:
        """
        (wann) ist der zug am ziel angekommen?

        gibt, falls bekannt, die effektive ankunftszeit an.
        wenn der zug angekommen ist, die zeit aber unbekannt, ist der wert True.
        wenn eine abfahrt, aber keine ankunft erfasst ist, gibt das property den wert des abgefahren-property an.

        solange der zug nicht angekommen ist, ist der wert False.

        :return: ankunftszeit, abfahrtszeit oder boolean
        """
        return self._angekommen or self._abgefahren

    @angekommen.setter
    def angekommen(self, ankunft: Union[bool, datetime.datetime]):
        self._angekommen = ankunft

    @property
    def abgefahren(self) -> Union[bool, datetime.datetime]:
        """
        (wann) ist der zug am ziel abgefahren?

        gibt, falls bekannt, die effektive abfahrtszeit an.
        wenn der zug abgefahren ist, die zeit aber unbekannt, ist der wert True.

        solange der zug nicht abgefahren ist, ist der wert False.

        :return: ankunftszeit, abfahrtszeit oder boolean
        """
        return self._abgefahren

    @abgefahren.setter
    def abgefahren(self, abfahrt: Union[bool, datetime.datetime]):
        self._abgefahren = abfahrt


@dataclass
class PlanungParams:
    mindestaufenthalt_lokwechsel: int = 5
    mindestaufenthalt_lokumlauf: int = 2
    mindestaufenthalt_richtungswechsel: int = 3
    mindestaufenthalt_ersatz: int = 1
    mindestaufenthalt_kupplung: int = 1
    mindestaufenthalt_fluegelung: int = 1
    wartezeit_ankunft_abwarten: int = 0
    wartezeit_abfahrt_abwarten: int = 2


class JSONEncoder(json.JSONEncoder):
    """
    translate non-standard objects to JSON objects.

    currently implemented: Set.

    ~~~~~~{.py}
    encoded = json.dumps(data, cls=JSONEncoder)
    decoded = json.loads(encoded, object_hook=json_object_hook)
    ~~~~~~
    """

    def default(self, obj):
        if isinstance(obj, Set):
            return dict(__class__='Set', data=list(obj))
        elif isinstance(obj, frozenset):
            return dict(__class__='frozenset', data=list(obj))
        elif isinstance(obj, nx.Graph):
            return "networkx.Graph"
        elif isinstance(obj, VerspaetungsKorrektur):
            return str(obj)
        elif isinstance(obj, ZugZielPlanung):
            return str(obj)
        else:
            return super().default(obj)


class Planung:
    """
    zug-planung und disposition

    diese klasse führt einen fahrplan ähnlich wie der PluginClient.
    der fahrplan wird in dieser klasse jedoch vom fahrdienstleiter und vordefinierten algorithmen bearbeitet
    (z.b. für die verspätungsfortpflanzung).

    - die planung erfolgt mittels ZugDetailsPlanung-objekten (entsprechend ZugDetails im PluginClient).
    - züge werden bei ihrem ersten auftreten von den quelldaten übernommen und bleiben in der planung,
      bis sie explizit entfernt werden.
    - bei folgenden quelldatenübernahmen, werden nur noch die zielattribute nachgeführt,
      die fahrplaneingträge bleiben bestehen (im PluginClient werden abgefahrene ziele entfernt).
    - die fahrpläne der züge haben auch einträge zur einfahrt und ausfahrt.

    attribute
    ---------

    zugbaum: der zugbaum ist der primäre speicherort für alle fahrplan-daten.
        der zugbaum ist ein networkx-DiGraph, wobei die nodes zid-nummern sind
        und die edges gerichtete referenzen von stammzügen auf folgezüge.

        das ZugDetailsPlanung-objekt ist, falls vorhanden, im node-attribut obj referenziert.
        das objekt kann fehlen, wenn der fahrplan vom simulator noch nicht übermittelt worden ist.
        edges haben die attribute flag ('E', 'F', 'K') und zielnr (zielnr-attribut im stammzug).

        hinweise:
        - einzelne zugobjekte werden über zugbaum.nodes[zid]['obj'] abgefragt.
          für einen einfachern zugriff steht alternativ das attribut zugliste zur verfügung.
        - dict(zugbaum) liefert einen dict: zid -> {'obj': ZugDetailsPlanung}
        - list(zugbaum) liefert eine liste von zids
        - self.zugbaum.nodes.data(data='obj') liefert einen iterator (zid, ZugDetailsPlanung)

    zugliste: ist ein abgeleitetes objekt und ermöglicht einen kürzeren zugriff auf das zugobjekt.
        der dict ist topologisch sortiert (s. zugsortierung).

    zuege: erstellt einen topologisch sortierten generator von zügen (s. zugsortierung).

    zugbaum_ungerichtet: view auf zugbaum mit ungerichteten kanten.

    zugsortierung: topologisch sortierte liste von zid.
        folgezüge kommen in dieser liste nie vor dem stammzug.

    zugstamm: gibt zu jedem zid den stamm an, d.h. ein set mit allen verknüpften zid.

    auswertung: ...

    simzeit_minuten: ...
    """

    def __init__(self):
        self.zugliste: Dict[int, ZugDetailsPlanung] = dict()
        self.zugbaum = nx.DiGraph()
        self.zugbaum_ungerichtet = nx.Graph()
        self.zugsortierung: List[int] = []
        self.zugstamm: Dict[int, Set[int]] = {}
        self.zielgraph = nx.DiGraph()
        self.zielsortierung: List[Tuple[str, int, str]] = []
        self.zielindex_plan: Dict[Tuple[int, str], Dict[str, ZugZielPlanung]] = {}
        self._haengige_folgekorrekturen: Dict[ZugZielNode, Dict] = {}
        self.auswertung: Optional[Auswertung] = None
        self.simzeit_minuten: int = 0
        self.params = PlanungParams()

    def zuege(self) -> Iterable[ZugDetailsPlanung]:
        """
        topologisch sortierter generator von zuegen

        die sortierung garantiert, dass folgezuege hinter ihren stammzuegen gelistet werden.

        :return: iteration von ZugDetailsPlanung-objekten
        """

        for zid in self.zugsortierung:
            try:
                zug = self.zugbaum.nodes[zid]['obj']
                yield zug
            except KeyError:
                pass

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
        """
        interne zugliste mit sim-daten aktualisieren.

        - neue züge übernehmen
        - bekannte züge aktualisieren
        - ausgefahrene züge markieren
        - links zu folgezügen aktualisieren
        - verspätungsmodell aktualisieren

        :param zuege:
        :return:
        """

        ausgefahrene_zuege = set(self.zugbaum.nodes)

        for zug in zuege:
            try:
                zug_planung = self.zugbaum.nodes[zug.zid]['obj']
            except KeyError:
                # neuer zug
                zug_planung = ZugDetailsPlanung()
                zug_planung.assign_zug_details(zug)
                zug_planung.update_zug_details(zug)
                ausgefahrene_zuege.discard(zug.zid)
            else:
                # bekannter zug
                zug_planung.update_zug_details(zug)
                ausgefahrene_zuege.discard(zug.zid)
            self.zugbaum.add_node(zug.zid, obj=zug_planung)

        for zid in ausgefahrene_zuege:
            try:
                zug = self.zugbaum.nodes[zid]['obj']
            except KeyError:
                pass
            else:
                if zug.sichtbar:
                    zug.sichtbar = zug.amgleis = False
                    zug.gleis = zug.plangleis = ""
                    zug.ausgefahren = True
                    for zeile in zug.fahrplan:
                        zeile.abgefahren = zeile.abgefahren or True

        self._zielgraph_erstellen()
        self._folgezuege_aufloesen()
        self._zugbaum_analysieren()
        self.korrekturen_definieren()

    def _zugbaum_analysieren(self) -> None:
        """
        aktualisiert von zugbaum abgeleitete objekte

        - zugbaum_ungerichtet
        - zugsortierung
        - zugstamm
        - zugliste

        muss jedesmal ausgeführt werden, wenn die zusammensetzung von self.zugbaum verändert wurde.

        für die analyse muss der zugbaum inklusive folgezug-verbindungen komplett sein.
        hierzu sollte die _zielgraph_erstellen-methode verwendet werden.

        :return: None
        """

        # der zugbaum kann zyklen enthalten, z.b. wenn ein zug fluegelt und spaeter wieder kuppelt.
        # damit die topologische sortierung trotzdem funktioniert, brechen wir die zyklen zuerst auf.
        # der gefluegelte zug wird nach dem stammzug sortiert.

        zb = self.zugbaum.copy()
        edges_to_remove = []
        for cycle in nx.simple_cycles(zb):
            for edge in zip(cycle, cycle[1:] + cycle[0:1]):
                if zb.edges[edge]['flag'] == 'K':
                    edges_to_remove.append(edge)
        zb.remove_edges_from(edges_to_remove)

        try:
            self.zugsortierung = list(nx.topological_sort(zb))
        except nx.NetworkXUnfeasible as e:
            logger.exception(e)
            self.zugsortierung = []

        self.zugbaum_ungerichtet = self.zugbaum.to_undirected(as_view=True)
        for stamm in nx.connected_components(self.zugbaum_ungerichtet):
            for zid in stamm:
                self.zugstamm[zid] = stamm

        self.zugliste = {zid: obj for zid, obj in self.zugbaum.nodes(data='obj') if obj is not None}

    def _folgezuege_aufloesen(self):
        """
        folgezüge aus den zugflags auflösen.

        setzt die ersatzzug/kuppelzug/fluegelzug-attribute gemäss verbindungsangaben im zugbaum.
        die verbindungsangaben werden von _zielgraph_erstellen gesetzt.

        :return: None
        """

        for zid1, zid2, d in self.zugbaum.edges(data=True):
            try:
                zug1: ZugDetailsPlanung = self.zugbaum.nodes[zid1]['obj']
                ziel1: ZugZielPlanung = zug1.find_fahrplan_zielnr(d['zielnr'])
            except KeyError:
                continue
            try:
                zug2: Optional[ZugDetailsPlanung] = self.zugbaum.nodes[zid2]['obj']
            except KeyError:
                zug2 = None

            if d['flag'] == 'E':
                ziel1.ersatzzug = zug2
            elif d['flag'] == 'K':
                ziel1.kuppelzug = zug2
            elif d['flag'] == 'F':
                ziel1.fluegelzug = zug2

    def _zielgraph_erstellen(self):
        """
        zielgraph erstellen/aktualisieren

        der zielgraph enthaelt die zielpunkte aller zuege.
        die punkte sind gemaess anordnung im fahrplan sowie planmaessigen und betrieblichen abghaengigkeiten verbunden.
        der zielbaum wird insbesondere verwendet, um eine topologische sortierung der fahrplanziele
        für die verspätungsberechnung zu erstellen.

        der zielbaum muss ein directed acyclic graph sein.
        modifikationen, die zyklen verursachen würden, müssen abgewiesen werden.

        diese methode fügt nur neue knoten und ihre kanten zum graphen hinzu.
        bestehende knoten werden nicht verändert.
        um den graphen neu aufzubauen, sollte er vorher gelöscht werden.

        node-attribute
        --------------

        obj: ZugZielPlanung-objekt
        zid: zug-id
        nr: zielnr
        plan: plangleis
        typ: zielpunkttyp:
            'H': planmaessiger halt
            'D': durchfahrt
            'E': einfahrt
            'A': ausfahrt
            'B': betriebshalt (vom fdl einfuegter halt)
            'S': signalhalt (ungeplanter halt zwischen zwei zielpunkten)   --- im moment nicht verwendet
        Van: ankunftsverspaetung in minuten
        Vab: abfahrtsverspaetung in minuten

        edge-attribute
        --------------

        typ: verbindungstyp
            'P': planmaessige fahrt
            'E': ersatzzug
            'F': fluegelung
            'K': kupplung
            'R': rangierfahrt (planmaessige fahrt im gleichen bahnhof)   --- von dieser methode nicht erkannt
            'A': ankunft/abfahrt abwarten
            'X': anschluss aufgeben
            'O': hilfskante für sortierordnung.
                 wird gebraucht, um die korrekte sortierung von kuppelnden zügen zu erhalten.
                 hat sonst keinen direkten einfluss auf die verspätungsberechnung.

        :return:
        """

        for zid2, zug in list(self.zugbaum.nodes(data='obj')):
            if zug is None:
                continue

            ziel1 = None
            zzid1 = None

            for ziel2 in zug.fahrplan:
                zzid2 = ZugZielNode.neu(ziel2)
                try:
                    if self.zielgraph.nodes[zzid2]['obj'] is not None:
                        ziel1 = ziel2
                        zzid1 = zzid2
                        continue
                except KeyError:
                    pass

                data = zzid2.init_zieldata(ziel2)
                self.zielgraph.add_node(zzid2, **data)

                d = weakref.WeakValueDictionary({zzid2[0]: ziel2})
                try:
                    self.zielindex_plan[(zid2, ziel2.plan)].update(d)
                except KeyError:
                    self.zielindex_plan[(zid2, ziel2.plan)] = d

                if ziel1:
                    if zzid1 == zzid2:
                        logger.warning("P edge", zzid1, zzid2)
                    else:
                        self.zielgraph.add_edge(zzid1, zzid2, typ='P')

                if zid := ziel2.ersatz_zid():
                    zzid = ZugZielNode.neu(ziel2, zid=zid, zielnr=0)
                    if zzid2 == zzid:
                        logger.warning("E edge", zzid2, zzid)
                    else:
                        self.zielgraph.add_edge(zzid2, zzid, typ='E')
                        self.zugbaum.add_edge(zid2, zid, flag='E', zielnr=ziel2.zielnr)
                if zid := ziel2.kuppel_zid():
                    try:
                        zug: ZugDetailsPlanung = self.zugbaum.nodes[zid]['obj']
                        ziel: ZugZielPlanung = zug.find_fahrplanzeile(plan=ziel2.plan)
                        zielnr = ziel.zielnr
                    except (KeyError, AttributeError):
                        logger.warning(f"kupplungsziel von {zzid2} nicht gefunden")
                    else:
                        zzid = ZugZielNode.neu(ziel2, zid=zid, zielnr=zielnr)
                        if zzid2 == zzid:
                            logger.warning("K edge", zzid2, zzid)
                        else:
                            self.zielgraph.add_edge(zzid2, zzid, typ='K')
                            self.zugbaum.add_edge(zid2, zid, flag='K', zielnr=ziel2.zielnr)
                if zid := ziel2.fluegel_zid():
                    zzid = ZugZielNode.neu(ziel2, zid=zid, zielnr=0)
                    if zzid2 == zzid:
                        logger.warning("F edge", zzid2, zzid)
                    else:
                        self.zielgraph.add_edge(zzid2, zzid, typ='F')
                        self.zugbaum.add_edge(zid2, zid, flag='F', zielnr=ziel2.zielnr)

                ziel1 = ziel2
                zzid1 = zzid2

        self._zielgraph_schleifen_aufbrechen()
        self._zielgraph_sortieren()

    def _zielgraph_schleifen_aufbrechen(self):
        """
        Schleifen im Zielgraph aufbrechen

        Der Zielgraph ist ein gerichteter Graph und darf eigentlich keine Schleifen enthalten.
        Beim Stellwerk Jenbach kommen aus noch ungeklärtem Grund trotzdem Schleifen vor.
        Diese Funktion bricht etwaige Schleifen an einem willkürlichen Punkt auf und gibt eine Warnung im Log aus.

        Die Verspätungsberechnung funktioniert nicht korrekt, wenn Schleifen vorhanden sind bzw. waren.
        Für dieses Problem muss noch eine Lösung gefunden werden.
        """

        while True:
            try:
                cycle = nx.find_cycle(self.zielgraph)
            except nx.NetworkXNoCycle:
                break

            msg = ", ".join((str(edge) for edge in cycle))
            logger.error("Schleife im Zielgraph gefunden: " + msg)
            for edge in cycle:
                if edge[0].zid != edge[1].zid:
                    break
            else:
                edge = cycle[-1]

            self.zielgraph.remove_edge(edge[0], edge[1])
            logger.warning(f"Verbindung {edge} entfernt.")

    def _zielgraph_sortieren(self):
        """
        Zielgraph topologisch sortieren.

        Der Zielgraph wird so sortiert, dass alle Abhängigkeiten eines Ziels weiter vorne in der Liste erscheinen.
        Der Zielgraph darf dazu keine Schleifen enthalten, ansonsten wird eine NetworkXUnfeasible Exception generiert.

        Die Sortierung wird als Liste von Nodes in self.zielsortierung abgelegt.
        """

        try:
            self.zielsortierung = list(nx.topological_sort(self.zielgraph))
        except nx.NetworkXUnfeasible as e:
            logger.error("Fehler beim Sortieren des Zielgraphen")
            logger.exception(e)
            raise

    def zielgraph_speichern(self, pfad: os.PathLike):
        d = dict(nx.node_link_data(self.zielgraph))
        with open(pfad, "w", encoding='utf-8') as fp:
            json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

    def einfahrten_korrigieren(self):
        """
        ein- und ausfahrtszeiten abschätzen.

        die ein- und ausfahrtszeiten werden vom sim nicht vorgegeben.
        wir schätzen sie die einfahrtszeit aus der ankunftszeit des anschliessenden wegpunkts
        und er kürzesten beobachteten fahrzeit zwischen der einfahrt und dem wegpunkt ab.
        die einfahrtszeit wird im ersten fahrplaneintrag eingetragen (an und ab).

        analog wird die ausfahrtszeit im letzten fahrplaneintrag abgeschätzt.

        :return:
        """

        for zug in self.zuege():
            try:
                einfahrt = zug.fahrplan[0]
                ziel1 = zug.fahrplan[1]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt and einfahrt.variable_zeit and einfahrt.gleis and ziel1.gleis:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, einfahrt.gleis, ziel1.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            einfahrt.an = einfahrt.ab = seconds_to_time(time_to_seconds(ziel1.an) - fahrzeit)
                            logger.debug(f"einfahrt {einfahrt.gleis} - {ziel1.gleis} korrigiert: {einfahrt.ab}")
                        except (AttributeError, ValueError):
                            pass

            try:
                ziel2 = zug.fahrplan[-2]
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.ausfahrt and ausfahrt.variable_zeit:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, ziel2.gleis, ausfahrt.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            ausfahrt.an = ausfahrt.ab = seconds_to_time(time_to_seconds(ziel2.ab) + fahrzeit)
                            logger.debug(f"ausfahrt {ziel2.gleis} - {ausfahrt.gleis} korrigiert: {ausfahrt.an}")
                        except (AttributeError, ValueError):
                            pass

    def verspaetungen_korrigieren(self):
        """
        verspätungsangaben aller züge nachführen

        :return: None
        """

        for node in self.zielsortierung:
            data = self.zielgraph.nodes[node]
            try:
                ziel: ZugZielPlanung = data['obj']
            except KeyError:
                # zug hat keinen fahrplan
                continue
            zug: ZugDetailsPlanung = ziel.zug

            if not ziel.angekommen:
                # beim aktuellen ziel verspaetung von zug uebernehmen
                if ziel.einfahrt or (zug.sichtbar and zug.plangleis == ziel.plan):
                    data['v_an'] = zug.verspaetung
                else:
                    data['v_an'] = 0

                # graph-daten aktualisieren
                try:
                    data['p_an'] = time_to_minutes(ziel.an)
                    data['p_ab'] = time_to_minutes(ziel.ab)
                except AttributeError:
                    pass
                data['d_min'] = ziel.mindestaufenthalt
                data['v_ab'] = data['v_an']
            else:
                data['v_an'] = ziel.verspaetung_an
                data['v_ab'] = ziel.verspaetung_ab

        for node in self.zielsortierung:
            data = self.zielgraph.nodes[node]
            try:
                ziel: ZugZielPlanung = data['obj']
                if data['p_an'] is None or data['p_ab'] is None:
                    continue
            except KeyError:
                continue

            if not ziel.angekommen:
                if ziel.auto_korrektur is not None:
                    try:
                        ziel.auto_korrektur.ankunft_berechnen(self.zielgraph, node, data)
                    except KeyError as e:
                        logger.exception(e)
                else:
                    logger.warning(f"keine autokorrektur fuer ziel {ziel}")

                for korr in ziel.fdl_korrektur.values():
                    try:
                        korr.ankunft_berechnen(self.zielgraph, node, data)
                    except KeyError as e:
                        logger.exception(e)

                ziel.verspaetung_an = data['v_an']

            # bei noch nicht abgefahrenen zielen verspaetung korrigieren
            if not ziel.abgefahren:
                if ziel.auto_korrektur is not None:
                    try:
                        ziel.auto_korrektur.abfahrt_berechnen(self.zielgraph, node, data)
                    except KeyError as e:
                        logger.exception(e)
                else:
                    data['v_ab'] = data['v_an']

                for korr in ziel.fdl_korrektur.values():
                    try:
                        korr.abfahrt_berechnen(self.zielgraph, node, data)
                    except KeyError as e:
                        logger.exception(e)

                ziel.verspaetung_ab = data['v_ab']

    def zugverspaetung_korrigieren(self, zug: ZugDetailsPlanung):
        """
        verspätungsangaben einer zugfamilie nachführen

        diese methode führt die verspätungsangaben des angegebenen zugs und der verknüpften züge nach.

        aktuell ist die methode nicht implementiert und ruft verspaetungen_korrigieren auf,
        die alle züge nachführt.
        es ist fraglich, ob es effizienter ist, die zugfamilien einzeln zu korrigieren,
        da die bestimmung der familien auch einen aufwand bedeutet.

        :param zug:
        :return:
        """

        self.verspaetungen_korrigieren()

    def korrekturen_definieren(self):
        for zug in self.zuege():
            if not zug.korrekturen_definiert:
                result = self.zug_korrekturen_definieren(zug)
                zug.korrekturen_definiert = zug.folgezuege_aufgeloest and result
        self._folgekorrekturen_setzen()

    def zug_korrekturen_definieren(self, zug: ZugDetailsPlanung) -> bool:
        for ziel in zug.fahrplan:
            result = self.ziel_korrekturen_definieren(ziel)
            if not result:
                return False

        return True

    def ziel_korrekturen_definieren(self, ziel: ZugZielPlanung) -> bool:
        """

        abfahrtszeiten von folgezug hier uebernehmen, ein fuer alle mal!

        :param ziel:
        :return:
        """

        result = True

        if ziel.richtungswechsel():
            ziel.mindestaufenthalt = self.params.mindestaufenthalt_richtungswechsel
        elif ziel.lokumlauf():
            ziel.mindestaufenthalt = self.params.mindestaufenthalt_lokumlauf
        elif ziel.lokwechsel():
            ziel.mindestaufenthalt = self.params.mindestaufenthalt_lokwechsel

        zid = None
        folge_korrektur = None
        if ziel.auto_korrektur is not None:
            # folgekorrektur nicht ueberschreiben
            pass
        elif zid := ziel.ersatz_zid():
            ziel.auto_korrektur = ErsatzUrsprung(self)
            folge_korrektur = ErsatzZiel(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, self.params.mindestaufenthalt_ersatz)
        elif zid := ziel.kuppel_zid():
            ziel.auto_korrektur = KupplungUrsprung(self)
            folge_korrektur = KupplungZiel(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, self.params.mindestaufenthalt_kupplung)
        elif zid := ziel.fluegel_zid():
            ziel.auto_korrektur = FluegelungUrsprung(self)
            folge_korrektur = FluegelungZiel(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, self.params.mindestaufenthalt_fluegelung)
        elif ziel.durchfahrt():
            ziel.auto_korrektur = Durchfahrt(self)
        elif ziel.einfahrt:
            ziel.auto_korrektur = Einfahrtszeit(self)
        elif ziel.ausfahrt:
            ziel.auto_korrektur = Durchfahrt(self)
        else:
            ziel.auto_korrektur = Planhalt(self)

        if zid is not None and folge_korrektur is not None:
            self._folgekorrektur_setzen(ziel, zid, folge_korrektur)

        return result

    def _folgekorrektur_setzen(self, stamm_ziel: ZugZielPlanung, folge_zid: int, folge_korrektur: FlagZiel,
                               stamm_zzid: Optional[ZugZielNode] = None):
        """
        folgekorrektur auf das folgeziel setzen wenn möglich

        es kommt bei langen zugketten vor, dass das folgeziel noch nicht aufgelöst werden kann.
        dann wird die korrektur in _haengige_folgekorrekturen abgelegt und muss gesetzt werden,
        sobald der zug in der planung auftaucht.

        achtung! die methode verändert _haengige_folgekorrekturen.
        sie darf deshalb nicht in einem generator davon aufgerufen werden!

        :param stamm_ziel: zielobjekt, das das zugfolgeflag enthält.
        :param folge_zid: zid des folgezuges
        :param folge_korrektur: korrektur-objekt
        :param stamm_zzid: zum stamm_ziel gehörender ZugZielNode.
            nicht notwendig, beschleunigt jedoch die funktion, wenn schon bekannt.
        :return: None
        """

        if stamm_zzid is None:
            stamm_zzid = ZugZielNode.neu(stamm_ziel)

        try:
            zug2: ZugDetailsPlanung = self.zugbaum.nodes[folge_zid]['obj']
            ziel2: ZugZielPlanung = zug2.find_fahrplanzeile(plan=stamm_ziel.plan)
            zzid2 = ZugZielNode.neu(ziel2)
        except (AttributeError, KeyError):
            self._haengige_folgekorrekturen[stamm_zzid] = {"stamm_ziel": stamm_ziel,
                                                           "stamm_zzid": stamm_zzid,
                                                           "folge_zid": folge_zid,
                                                           "folge_korrektur": folge_korrektur}
        else:
            typ = stamm_ziel.auto_korrektur.edge_typ
            self.zielgraph.add_edge(stamm_zzid, zzid2, typ=typ)
            stamm_ziel.auto_korrektur.folge = zzid2
            folge_korrektur.ursprung = stamm_zzid
            if ziel2.auto_korrektur is None or folge_korrektur.rang > ziel2.auto_korrektur.rang:
                ziel2.auto_korrektur = folge_korrektur
            if typ in {'E', 'K'}:
                if stamm_ziel.an:
                    an1 = minutes_to_time(time_to_minutes(stamm_ziel.an) + stamm_ziel.mindestaufenthalt)
                else:
                    an1 = minutes_to_time(0)
                if ziel2.an:
                    an2 = ziel2.an
                else:
                    an2 = minutes_to_time(0)
                ab1 = max(an1, an2)
                if ab1 > minutes_to_time(0):
                    stamm_ziel.ab = max(an2, an1)
            try:
                del self._haengige_folgekorrekturen[stamm_zzid]
            except KeyError:
                pass

    def _folgekorrekturen_setzen(self):
        """
        hängige folgekorrekturen setzen soweit möglich

        geht die _haengige_folgekorrekturen durch und versucht sie wo möglich zu setzen

        :return: None
        """

        for params in list(self._haengige_folgekorrekturen.values()):
            self._folgekorrektur_setzen(**params)

    def zug_finden(self, zug: Union[int, str, ZugDetails]) -> Optional[ZugDetailsPlanung]:
        """
        zug nach name oder nummer in zugliste suchen

        :param zug: nummer oder name des zuges oder ein beliebiges objekt mit einem zid attribut,
            z.b. ein ZugDetails vom PluginClient oder ein Ereignis.
        :return: entsprechendes ZugDetailsPlanung aus der zugliste dieser klasse.
            None, wenn kein passendes objekt gefunden wurde.
        """

        zid = None
        try:
            zid = zug.zid
        except AttributeError:
            for z in self.zuege():
                if z.nummer == zug or z.name == zug:
                    zid = z.zid
                    break

        try:
            return self.zugbaum[zid]['obj']
        except KeyError:
            return None

    def fdl_korrektur_setzen(self, korrektur: VerspaetungsKorrektur, ziel: Union[ZugZielPlanung, ZugZielNode]):
        """
        fahrdienstleiter-korrektur setzen

        mit dieser methode kann der fahrdienstleiter eine manuelle verspätungskorrektur auf eine fahrplanzeile anwenden,
        z.b. eine feste abgangsverspätung setzen oder eine abhängigkeit von einem kreuzenden zug festlegen.

        es kann nur eine korrektur pro relation (knoten und kanten im zielgraphen) definiert werden.
        eine bestehende korrektur wird überschrieben.

        :param korrektur: von VerspaetungsKorrektur abgeleitetes korrekturobjekt.
            in frage kommen normalerweise FesteVerspaetung, AnkunftAbwarten oder AbfahrtAbwarten.
        :param ziel: fahrplanziel, auf das die korrektur angewendet wird.
            dies kann ein ZugDetailsPlanung-objekt aus der zugliste
            oder ein ZugZielNode aus dem zielgraph sein.
        :return: None
        :raise ValueError: die gewünschte korrektur ist nicht möglich.
        """

        korrektur.node = ziel

        try:
            self.zielgraph.add_edge(*korrektur.relation, typ='A', obj=korrektur)
        except (AttributeError, TypeError) as e:
            logger.error(msg=f"Fehler beim Hinzufügen der Abhängigkeit {korrektur}", exc_info=e)
        else:
            try:
                self._zielgraph_sortieren()
            except nx.NetworkXUnfeasible:
                logger.error(f"Sortierfehler beim Hinzufügen der Abhängigkeit {korrektur}")
                self.zielgraph.remove_edge(*korrektur.relation)

        ziel.fdl_korrektur[korrektur.relation] = korrektur

    def fdl_korrektur_loeschen(self, ziel: Union[ZugZielPlanung, ZugZielNode],
                               ursprung: Optional[Union[ZugZielPlanung, ZugZielNode]] = None,
                               alle: bool = False):
        """
        fahrdienstleiter-korrekturen löschen

        entfernt eine oder alle fdl-korrekturen von einem fahrziel.
        das korrekturobjekt muss im fdl_korrektur-attribut des fahrziels enthalten sein.
        ggf. vorhandene weitere korrekturen werden nicht berührt.

        bei None werden alle korrekturen auf diesem ziel gelöscht.

        :param ziel: fahrplanziel, auf das die korrektur angewendet wird.
            dies kann ein ZugDetailsPlanung-objekt aus der zugliste
            oder ein ZugZielNode aus dem zielgraph sein.
        :param ursprung: referenz-fahrplanziel, von dem die korrektur abhängt.
            wenn dieser parameter None oder default ist,
            wird die feste verspätung auf dem ziel gelöscht,
            ansonsten (nur) die bezeichnete abhängigkeit.
        :param alle: bei True werden alle korrekturen auf ziel gelöscht,
            sonst nur diejenige, die durch ziel und ursprung bezeichnet wird.
            bei True hat der parameter ursprung keine bedeutung.
        :return: None
        """

        if isinstance(ziel, ZugZielNode):
            zzid2 = ziel
            ziel = self.zielgraph.nodes[zzid2]['obj']
        else:
            zzid2 = ZugZielNode.neu(ziel)

        if isinstance(ursprung, ZugZielNode):
            zzid1 = ursprung
            relation = (zzid1, zzid2)
        elif isinstance(ursprung, ZugZielPlanung):
            zzid1 = ZugZielNode.neu(ursprung)
            relation = (zzid1, zzid2)
        else:
            relation = (zzid2,)

        edges = []
        if alle:
            ziel.fdl_korrektur.clear()
            edges = [(u, v) for u, v, typ in self.zielgraph.in_edges(zzid2, data='typ', default='?')
                     if typ in {'A', 'X'}]
        else:
            try:
                del ziel.fdl_korrektur[relation]
            except KeyError as e:
                logger.exception(msg=f"KeyError in fdl_korrektur_loeschen: "
                                     f"relation {relation}, korrekturen {ziel.fdl_korrektur}", exc_info=e)
            if len(relation) == 2:
                edges = [relation]

        for u, v in edges:
            try:
                self.zielgraph.remove_edge(u, v)
            except nx.NetworkXError:
                pass

        try:
            self._zielgraph_sortieren()
        except nx.NetworkXUnfeasible:
            logger.error(f"Sortierfehler beim Löschen der Abhängigkeit {relation}")

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        daten von einem ereignis uebernehmen.

        aktualisiert die verspätung und angekommen/abgefahren-flags anhand eines ereignisses.

        :param ereignis: Ereignis-objekt vom PluginClient
        :return:
        """

        logger.debug(f"{ereignis.art} {ereignis.name} ({ereignis.verspaetung})")

        if not ereignis.sichtbar and ereignis.art not in {'einfahrt', 'ausfahrt'}:
            logger.warning(f"ereignis von unsichtbarem zug {ereignis}")
            return None

        try:
            zug = self.zugbaum.nodes[ereignis.zid]['obj']
        except KeyError:
            logger.warning(f"zug von ereignis {ereignis} nicht in zugliste")
            return None

        try:
            alter_index = zug.ziel_index
            altes_ziel = zug.fahrplan[zug.ziel_index]
        except IndexError:
            logger.warning(f"fehlendes vorheriges ziel bei {ereignis}")
            return

        if ereignis.plangleis:
            neuer_index = zug.find_fahrplan_index(plan=ereignis.plangleis)
        else:
            # ausfahrt
            neuer_index = len(zug.fahrplan) - 1
        if neuer_index is None:
            logger.warning(f"ereignisziel nicht in fahrplan bei {ereignis}")
            return
        elif neuer_index < alter_index:
            logger.warning(f"ignoriere veraltetes ereignis {ereignis}")
            return
        else:
            neues_ziel = zug.fahrplan[neuer_index]

        if ereignis.art == 'einfahrt':
            try:
                einfahrt = zug.fahrplan[0]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt:
                    einfahrt.verspaetung_ab = time_to_minutes(ereignis.zeit) - time_to_minutes(einfahrt.ab)
                    einfahrt.angekommen = einfahrt.abgefahren = ereignis.zeit

        elif ereignis.art == 'ausfahrt':
            try:
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.ausfahrt and not zug.ausgefahren:
                    ausfahrt.verspaetung_an = ausfahrt.verspaetung_ab = ereignis.verspaetung
                    ausfahrt.angekommen = ausfahrt.abgefahren = ereignis.zeit
                    zug.ausgefahren = True
                    # falls ereignisse vergessen gegangen sind
                    for ziel in zug.fahrplan:
                        ziel.angekommen = ziel.angekommen or True
                        ziel.abgefahren = ziel.abgefahren or True

        elif ereignis.art == 'ankunft':
            if not altes_ziel.angekommen:
                try:
                    altes_ziel.verspaetung_an = time_to_minutes(ereignis.zeit) - time_to_minutes(altes_ziel.an)
                except AttributeError:
                    altes_ziel.verspaetung_an = ereignis.verspaetung
                altes_ziel.angekommen = ereignis.zeit

                # durchfahrten melden nur ankunftsereignis. bei fdl_korrektur erwarten wir einen signalhalt.
                if altes_ziel.durchfahrt() and not altes_ziel.fdl_korrektur:
                    altes_ziel.verspaetung_ab = altes_ziel.verspaetung_an
                    altes_ziel.abgefahren = ereignis.zeit

                # falls ein ereignis vergessen gegangen ist:
                for ziel in zug.fahrplan[0:alter_index]:
                    ziel.angekommen = ziel.angekommen or True
                    ziel.abgefahren = ziel.abgefahren or True

        elif ereignis.art == 'abfahrt':
            if ereignis.amgleis:
                if ereignis.verspaetung > 0:
                    altes_ziel.auto_korrektur = Signalhalt(self)
                    altes_ziel.auto_korrektur.verspaetung = ereignis.verspaetung
            elif not altes_ziel.abgefahren:
                try:
                    altes_ziel.verspaetung_ab = time_to_minutes(ereignis.zeit) - time_to_minutes(altes_ziel.ab)
                except AttributeError:
                    pass
                altes_ziel.abgefahren = ereignis.zeit

        elif ereignis.art == 'rothalt' or ereignis.art == 'wurdegruen':
            zug.verspaetung = ereignis.verspaetung
            neues_ziel.verspaetung_an = ereignis.verspaetung


async def test() -> Planung:
    """
    Testprogramm

    Das Testprogramm fragt alle Daten einmalig vom Simulator ab und gibt ein Planungsobjekt zurück.

    Diese Coroutine muss über trio.run ausgeführt werden.

    :return: Planung-Instanz
    """

    client = PluginClient(name='stskit-planung', autor='tester', version='0.0', text='planungsobjekt abfragen')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
                await client.resolve_zugflags()

                _planung = Planung()
                _planung.zuege_uebernehmen(client.zugliste.values())
                _planung.simzeit_minuten = time_to_minutes(client.calc_simzeit())

                raise TaskDone()

    except TaskDone:
        pass

    return _planung


def main_test():
    """
    Testprogramm

    Das Testprogramm fragt alle Daten einmalig vom Simulator ab und gibt ein Planungsobjekt zurück.

    Diese Funktion wird in einer synchronen Umgebung aufgerufen.
    Sie kehrt erst zurück, wenn alle Daten eingetroffen sind.

    :return: Planung-Instanz
    """

    _planung = trio.run(test)
    return _planung


if __name__ == '__main__':
    planung_obj = main_test()
