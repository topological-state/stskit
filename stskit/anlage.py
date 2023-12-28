"""
OBSOLET

Dieses Modul wird durch stskit.dispo.anlage ersetzt und funktioniert nicht mehr!
Das Modul enthält noch Code, der nicht migriert wurde.
"""

import collections
import itertools
import os
import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Set, Tuple

import networkx as nx
import numpy as np
import trio

from stskit.interface.stsobj import AnlagenInfo, Knoten, ZugDetails, time_to_seconds
from stskit.interface.stsplugin import PluginClient, TaskDone
from stskit.utils.gleisnamen import default_bahnhofname, default_anschlussname, alpha_prefix
from stskit.zugschema import Zugschema

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def dict_union(*gr: Dict[str, Set[Any]]) -> Dict[str, Set[Any]]:
    """
    merge dictionaries of sets.

    the given dictionaries are merged.
    if two dictionaries contain the same key, the union of their values is stored.

    :param gr: any number of dictionaries containing sets as values
    :return: merged dictionary
    """
    d = dict()
    for g in gr:
        for k, v in g.items():
            if k in d:
                d[k] = d[k].union(v)
            else:
                d[k] = v
    return d


def find_set_item_in_dict(item: Any, mapping: Mapping[Any, Set[Any]]) -> Any:
    """
    look up a set member in a key->set mapping.

    :param item: item to find in one of the sets in the dictonary.
    :param mapping: mapping->set
    :return: key
    :raise ValueError if not found
    """
    for k, s in mapping.items():
        if item in s:
            return k
    else:
        raise ValueError(f"item {item} not found in dictionary.")


anschluss_name_funktionen = {}
    # "Bern - Lötschberg": alpha_prefix,
    # "Ostschweiz": alpha_prefix,
    # "Tessin": alpha_prefix,
    # "Westschweiz": alpha_prefix,
    # "Zentralschweiz": alpha_prefix,
    # "Zürich und Umgebung": alpha_prefix}

bahnhof_name_funktionen = {}


class Anlage:
    """
    netzwerk-darstellungen der bahnanlage

    diese klasse verwaltet folgende graphen als darstellung der bahnanlage:

    :var self.signal_graph original "wege"-graph vom simulator
        mit bahnsteigen, haltepunkten, signalen, einfahrten und ausfahrten.
        dieser graph dient als basis und wird nicht speziell bearbeitet.
        der graph ist ungerichtet, weil die richtung vom simulator nicht konsistent angegeben wird:
        entgegengesetzte signale sind verbunden, einfahrten sind mit ausfahrsignalen verbunden.

    :var self.bahnsteig_graph graph mit den bahnsteigen von der "bahnsteigliste".
        vom simulator als nachbarn bezeichnete bahnsteige sind durch kanten verbunden.
        der bahnsteig-graph zerfällt dadurch in bahnhof-teile.
        es ist für den gebrauch in den charts in einigen fällen wünschbar,
        dass bahnhof-teile zu einem ganzen bahnhof zusammengefasst werden,
        z.b. bahnsteige und abstellgleise.
        die zuordnung kann jedoch nicht aus dem graphen selber abgelesen werden
        und muss separat (user, konfiguration, empirische auswertung) gemacht werden.

        vorsicht: bahnsteige aus der bahnsteigliste sind teilweise im wege-graph nicht enthalten!

    :var self.bahnhof_graph netz-graph mit bahnsteiggruppen, einfahrtgruppen und ausfahrtgruppen.
        vom bahnsteig-graph abgeleiteter graph, der die ganzen zugeordneten gruppen enthält.


    :var self.anschlussgruppen gruppierung von einfahrten und ausfahrten

        mehrere ein- und ausfahrten können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen auf sets von knotennamen ab.

    :var self.bahnsteiggruppen gruppierung von bahnsteigen

        mehrere bahnsteige (typischerweise alle zu einem bahnhof gehörigen)
        können zu einer gruppe zusammengefasst werden.
        dieser dictionary bildet gruppennamen (bahnhofnamen) auf sets von bahnsteignamen ab.
    """

    def strecken_aus_bahnhofgraph(self, nur_benutzte: bool = False):
        """
        strecken aus bahnhofgraph ableiten

        diese funktion bestimmt die kürzesten strecken zwischen allen anschlusskombinationen.
        die strecken werden in self.strecken abgelegt.

        eine strecke besteht aus einer liste von bahnhöfen inklusive einfahrt am anfang und ausfahrt am ende.
        die namen der elemente sind gruppennamen, d.h. die schlüssel aus self.gleisgruppen.
        der streckenname (schlüssel von self.strecken) wird aus dem ersten und letzten wegpunkt gebildet,
        die mit einem bindestrich aneinandergefügt werden.

        :param: nur_benutzte: nur anschlüsse, die von mindestens einem zug benutzt werden, inkludieren.
            per default, werden auch strecken zwischen unbenutzten anschlüssen erstellt.
            zum konfigurationszeitpunkt, steht die zugliste jedoch nicht zur verfügung oder ist unvollständig,
            da noch nicht alle verbindungen im fahrplan erscheinen.

        :return: das result wird in self.strecken abgelegt.
        """

        anschlussgleise = list(self.anschlussgruppen.keys())
        strecken = []

        for ein, aus in itertools.permutations(anschlussgleise, 2):
            try:
                zuege = min(self.bahnhof_graph.nodes[ein]['zug_count'], self.bahnhof_graph.nodes[aus]['zug_count'])
            except KeyError:
                zuege = -1

            if ein != aus and (not nur_benutzte or zuege > 0):
                strecke = self.verbindungsstrecke(ein, aus)
                if len(strecke) >= 1:
                    strecken.append(strecke)

        self.strecken = {f"{s[0]}-{s[-1]}": s for s in strecken}

    def verbindungsstrecke(self, start_gleis: str, ziel_gleis: str) -> List[str]:
        """
        kürzeste verbindung zwischen zwei gleisen bestimmen

        die kürzeste verbindung wird aus dem bahnhofgraphen bestimmt.
        start und ziel müssen knoten im bahnhofgraphen sein, also gruppennamen (bahnhöfe oder anschlüsse).
        die berechnete strecke ist eine geordnete liste von gruppennamen.

        da die streckenberechnung aufwändig sein kann, werden die resultate im self._verbindungsstrecke_cache
        gespeichert. der cache muss gelöscht werden, wenn sich der bahnhofgraph oder die bahnsteigzuordnung ändert.

        :param start_gleis: bahnhof- oder anschlussname
        :param ziel_gleis: bahnhof- oder anschlussname
        :return: liste von befahrenen gleisgruppen vom start zum ziel.
            die liste kann leer sein, wenn kein pfad gefunden wurde!
        """

        try:
            return self._verbindungsstrecke_cache[(start_gleis, ziel_gleis)]
        except KeyError:
            pass

        try:
            strecke = nx.shortest_path(self.bahnhof_graph, start_gleis, ziel_gleis)
        except nx.NetworkXException:
            return []

        self._verbindungsstrecke_cache[(start_gleis, ziel_gleis)] = strecke
        return strecke

    def get_strecken_distanzen(self, strecke: List[str]) -> List[float]:
        """
        distanzen (minimale fahrzeit) entlang einer strecke berechnen

        distanzen der bahnhöfe zum ersten punkt der strecke berechnen.
        die distanz wird als minimale fahrzeit in sekunden angegeben.

        :param strecke: liste von gleisgruppen-namen
        :return: distanz = minimale fahrzeit in sekunden.
            die liste enthält die gleiche anzahl elemente wie die strecke.
            das erste element ist 0.
        """
        kanten = zip(strecke[:-1], strecke[1:])
        distanz = 0.
        result = [distanz]
        for u, v in kanten:
            try:
                zeit = self.bahnhof_graph[u][v]['fahrzeit_min']
                if not np.isnan(zeit):
                    distanz += zeit
                else:
                    distanz += 60.
            except KeyError:
                logger.warning(f"verbindung {u}-{v} nicht im netzplan.")
                distanz += 60.

            result.append(float(distanz))

        return result

    @staticmethod
    def _gruppen_abgleichen(anlage_gruppe: Dict[str, Set[str]], config_gruppe: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        """
        konfiguration von bahnsteig- oder anschlussgruppen abgleichen

        idealerweise enthält die konfiguration alle in der anlage vorkommenden bahnsteige bzw. anschlüsse.
        wenn es unterschiede gibt, versucht diese funktion die gruppen abzugleichen,
        so dass die konfiguration nach möglichkeit trotzdem verwendet werden kann.
        dadurch entstehende probleme nimmt man gegenüber den unzulänglichkeiten einer vollständigen neukonfiguration in kauf.

        konkret entfernt diese funktion gleise/anschlüsse aus der konfiguration, die in der anlage nicht vorkommen.
        wenn die anlage gleise/anschlüsse enthält, die nicht konfiguriert sind, wird eine exception ausgelöst.
        in diesem fall muss die konfiguration überarbeitet werden.

        :param anlage_gruppe: gleis- bzw. anschlussgruppen gemäss anlagendefinition
        :param config_gruppe: gleis- bzw. anschlussgruppen aus der konfiguration
        :return:
        """

        anlage_elemente = set().union(*anlage_gruppe.values())
        conf_elemente = set().union(*config_gruppe.values())
        nicht_in_conf = anlage_elemente.difference(conf_elemente)
        nicht_in_anlage = conf_elemente.difference(anlage_elemente)
        if len(nicht_in_conf):
            logger.error("die folgenden anlagenelemente sind nicht konfiguriert: " +
                         ", ".join(nicht_in_conf))
            raise ValueError("anlage enthält unkonfigurierte elemente")
        if len(nicht_in_anlage):
            logger.warning("die folgenden konfigurationselemente sind in der anlage nicht vorhanden: " +
                           ", ".join(nicht_in_anlage))
        config_gruppe = {k: s for k, v in config_gruppe.items() if len(s := v.difference(nicht_in_anlage))}
        return config_gruppe

    def konfiguration_abgleichen(self, config_dict: Dict):
        """
        konfiguration mit der anlage abgleichen

        prüft, ob eine gegebene anlagenkonfiguration kompatibel mit der aktuellen anlage ist.
        die konfiguration wird als kompatibel bewertet,
        wenn alle gleise und anschlüsse der anlage in der konfiguration vorkommen.
        andernfalls löst die funktion eine ValueError-exception aus.

        konfigurierte gleise, die in der anlage nicht vorkommen, werden entfernt.

        :param config_dict: dictionary mit der gesamten anlagekonfiguration.
        """

        config_dict['anschlussgruppen'] = self._gruppen_abgleichen(self.anschlussgruppen, config_dict['anschlussgruppen'])
        config_dict['bahnsteiggruppen'] = self._gruppen_abgleichen(self.bahnsteiggruppen, config_dict['bahnsteiggruppen'])


    def save_config(self, path: os.PathLike):
        d = self.get_config(graphs=False)
        p = Path(path) / f"{self.anlage.aid}.json"
        with open(p, "w", encoding='utf-8') as fp:
            json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

        if logger.isEnabledFor(logging.DEBUG):
            d = self.get_config(graphs=True)
            p = Path(path) / f"{self.anlage.aid}diag.json"
            with open(p, "w", encoding='utf-8') as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)

    def get_config(self, graphs=False) -> Dict:
        """
        aktuelle konfiguration im dict-format auslesen

        das dictionary kann dann im json-format abgespeichert und als konfigurationsdatei verwendet werden.

        :param graphs: gibt an, ob die graphen (im networkx node-link format mitgeliefert werden sollen.
        :return: dictionary mit konfiguration- und diagnostik-daten.
        """

        streckenmarkierung = [[b[0], b[1], m] for b, m in self.streckenmarkierung.items()]

        d = {'_aid': self.anlage.aid,
             '_region': self.anlage.region,
             '_name': self.anlage.name,
             '_build': self.anlage.build,
             '_version': 2,
             'bahnsteiggruppen': self.bahnsteiggruppen,
             'anschlussgruppen': self.anschlussgruppen,
             'sektoren': self.sektoren.get_config(),
             'anschlusslage': self.anschlusslage,
             'strecken': self.strecken,
             'hauptstrecke': self.hauptstrecke,
             'streckenmarkierung': streckenmarkierung}
        if self.zugschema.name:
            d['zugschema'] = self.zugschema.name

        if graphs:
            if self.signal_graph:
                d['signal_graph'] = dict(nx.node_link_data(self.signal_graph))
            if self.bahnsteig_graph:
                d['bahnsteig_graph'] = dict(nx.node_link_data(self.bahnsteig_graph))
            # bahnhofgraph kann im moment wegen kontraktionen nicht codiert werden
            # if self.bahnhof_graph:
            #     d['bahnhof_graph'] = dict(nx.node_link_data(self.bahnhof_graph))

        return d
