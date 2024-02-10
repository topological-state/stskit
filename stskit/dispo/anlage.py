import collections
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx

from stskit.interface.stsgraph import GraphClient
from stskit.interface.stsobj import Knoten, AnlagenInfo
from stskit.graphs.signalgraph import SignalGraph
from stskit.graphs.bahnhofgraph import BahnhofGraph, BahnsteigGraph
from stskit.graphs.liniengraph import LinienGraph, LinienGraphEdge
from stskit.graphs.zielgraph import ZielGraph
from stskit.graphs.ereignisgraph import EreignisGraph
from stskit.utils.gleisnamen import default_anschlussname, default_bahnhofname, default_bahnsteigname
from stskit.utils.export import json_object_hook
from stskit.zugschema import Zugschema


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def bahnhofgraph_konfig_umdrehen(gleis_konfig, anschluss_konfig):
    """
    Konfiguration invertieren

    bahnhofgraph_konfigurien benoetigt eine bottom-up Struktur,
    waehrend die Konfigurationsdatei eine top-down Struktur hat.
    diese Methode wandelt top-down in bottom-up um.
    """

    result = {}

    for bf, bf_dict in gleis_konfig.items():
        for bft, bft_dict in bf_dict.items():
            for bs, bs_set in bft_dict.items():
                for gl in bs_set:
                    result[('Gl', gl)] = (bf, bft, bs)

    for anst, anst_set in anschluss_konfig.items():
        for agl in anst_set:
            result[('Agl', agl)] = (anst,)

    return result


class Anlage:
    def __init__(self):
        self.anlageninfo: Optional[AnlagenInfo] = None
        self.config: Dict[str, Any] = {}

        self.signalgraph = SignalGraph()
        self.bahnsteiggraph = BahnsteigGraph()
        self.bahnhofgraph = BahnhofGraph()
        self.liniengraph = LinienGraph()
        self.zielgraph = ZielGraph()
        self.ereignisgraph = EreignisGraph()

        self.strecken: Dict[str, List[Tuple[str, str]]] = {}
        self.hauptstrecke: Optional[str] = None
        self.streckenmarkierung: Dict[Tuple[Tuple[str, str], Tuple[str, str]], str] = {}
        self.gleissperrungen: Set[Tuple[str, str]] = set()

        self.zugschema = Zugschema()

    def update(self, client: GraphClient, config_path: os.PathLike):
        # todo : konfiguration speichern

        if self.anlageninfo is None:
            self.anlageninfo = client.anlageninfo

        if not self.config and config_path:
            config_path = Path(config_path)
            default_path = Path(__file__).parent.parent / "config"
            try:
                logger.info(f"Konfiguration laden von {config_path}")
                self.load_config(config_path)
            except OSError:
                logger.warning("Keine benutzerspezifische Anlagenkonfiguration gefunden")
                logger.info(f"Beispielkonfiguration laden von {default_path}")
                try:
                    self.load_config(default_path)
                except OSError:
                    logger.warning("Keine Beispielkonfiguration gefunden")
            except ValueError as e:
                logger.exception("Fehlerhafte Anlagenkonfiguration")

            Zugschema.find_schemas(default_path)
            Zugschema.find_schemas(config_path)
            self.zugschema.load_config(self.config.get('zugschema', ''), self.anlageninfo.region)

        if not self.signalgraph:
            self.signalgraph = client.signalgraph.copy(as_view=False)
        if not self.bahnsteiggraph:
            self.bahnsteiggraph = client.bahnsteiggraph.copy(as_view=False)
        if not self.bahnhofgraph and self.signalgraph and self.bahnsteiggraph:
            self.bahnhofgraph.import_anlageninfo(self.anlageninfo)
            self.bahnhofgraph.import_bahnsteiggraph(self.bahnsteiggraph, default_bahnsteigname, default_bahnhofname)
            self.bahnhofgraph.import_signalgraph(self.signalgraph, default_anschlussname)
            try:
                self.bahnhofgraph.konfigurieren(self.config['bahnhofgraph'])
            except KeyError:
                logger.warning("keine bahnhofkonfiguration gefunden")

        # todo : zielgraph kann sich zur laufzeit aendern
        self.zielgraph = client.zielgraph.copy(as_view=True)
        self.ereignisgraph.zielgraph_importieren(self.zielgraph)
        # todo : einfahrten korrigieren
        self.ereignisgraph.prognose()
        self.ereignisgraph.verspaetungen_nach_zielgraph(self.zielgraph)

        if not self.liniengraph and self.bahnhofgraph and self.zielgraph:
            self.liniengraph_konfigurieren()
            self.liniengraph_mit_signalgraph_abgleichen()

        if len(self.strecken) == 0 and self.liniengraph:
            strecken = self.liniengraph.strecken_vorschlagen(2, 3)
            for strecke in strecken:
                key = f"{strecke[0][1]}-{strecke[-1][1]}"
                self.strecken[key] = strecke
            self.strecken_konfigurieren()

    def label_aus_zielgleis(self, gleis: Union[int, str]) -> Tuple[str, str]:
        if isinstance(gleis, int):
            signal_node = self.signalgraph.nodes[gleis]
            return 'Agl', signal_node.name
        else:
            return 'Gl', gleis

    def liniengraph_konfigurieren(self):
        """
        Erstellt den Liniengraphen aus dem Zielgraphen.

        Jede Strecke aus dem Zielgraphen wird in eine Relation zwischen Bahnhöfen bzw. Anschlussstellen übersetzt
        und als Linie eingefügt.
        """

        for node1, node2, kante in self.zielgraph.edges(data=True):
            if kante.typ == 'P':
                ziel1_data = self.zielgraph.nodes[node1]
                ziel2_data = self.zielgraph.nodes[node2]
                bst1 = self.bahnhofgraph.find_superior(self.label_aus_zielgleis(ziel1_data.plan), {'Bf', 'Anst'})
                bst2 = self.bahnhofgraph.find_superior(self.label_aus_zielgleis(ziel2_data.plan), {'Bf', 'Anst'})
                if bst1 != bst2:
                    bst1_data = self.bahnhofgraph.nodes[bst1]
                    bst2_data = self.bahnhofgraph.nodes[bst2]
                    self.liniengraph.linie_eintragen(ziel1_data, bst1_data, ziel2_data, bst2_data)

        self.liniengraph.schleifen_aufloesen()

    def liniengraph_mit_signalgraph_abgleichen(self):
        """
        Liniengraph mittels Signalgraph vereinfachen.

        Die Methode trennt die Linien auf, die gemäss Signalgraphen über andere Haltestellen verlaufen.
        """
        mapping = {}
        for gleis, gleis_data in self.bahnhofgraph.nodes(data=True):
            if gleis[0] in {'Gl', 'Agl'}:
                bst = self.bahnhofgraph.find_superior(gleis, {'Bf', 'Anst'})
                if gleis[0] == 'Gl':
                    mapping[gleis_data.name] = bst
                elif gleis[0] == 'Agl':
                    mapping[gleis_data.enr] = bst
        signalgraph_einfach = nx.relabel_nodes(self.signalgraph, mapping)
        signalgraph_einfach.remove_edges_from(nx.selfloop_edges(signalgraph_einfach))
        
        bearbeiten = {(ziel1, ziel2): kante for ziel1, ziel2, kante in self.liniengraph.edges(data=True)}

        while bearbeiten:
            ziel1, ziel2 = next(iter(bearbeiten))
            kante = bearbeiten[(ziel1, ziel2)]
            del bearbeiten[(ziel1, ziel2)]

            try:
                signal_strecke = nx.shortest_path(signalgraph_einfach, ziel1, ziel2)
            except (nx.NodeNotFound, nx.NetworkXNoPath):
                continue

            for zwischenziel in signal_strecke[1:-1]:
                if isinstance(zwischenziel, collections.abc.Sequence) and zwischenziel[0] in {'Bf', 'Anst'}:
                    neue_kante = LinienGraphEdge()
                    neue_kante.update(kante)
                    neue_kante.fahrzeit_max = kante.fahrzeit_max / 2
                    neue_kante.fahrzeit_min = kante.fahrzeit_min / 2
                    neue_kante.fahrzeit_summe = kante.fahrzeit_summe / 2
                    neue_kante.fahrzeit_schnitt = kante.fahrzeit_schnitt / 2

                    if not self.liniengraph.has_edge(ziel1, zwischenziel):
                        self.liniengraph.add_edge(ziel1, zwischenziel, **neue_kante)
                        bearbeiten[(ziel1, zwischenziel)] = neue_kante

                    if not self.liniengraph.has_edge(zwischenziel, ziel2):
                        self.liniengraph.add_edge(zwischenziel, ziel2, **neue_kante)
                        bearbeiten[(zwischenziel, ziel2)] = neue_kante

                    try:
                        self.liniengraph.remove_edge(ziel1, ziel2)
                    except nx.NetworkXError:
                        pass

    def strecken_konfigurieren(self):
        """
        Streckendefinition aus der Konfiguration übernehmen
        """
        for titel, konfig in self.config['strecken'].items():
            strecke = []
            for name in konfig:
                if self.bahnhofgraph.has_node(node := ('Bf', name)):
                    strecke.append(node)
                elif self.bahnhofgraph.has_node(node := ('Anst', name)):
                    strecke.append(node)
            key = f"{strecke[0][1]}-{strecke[-1][1]}"
            self.strecken[key] = strecke

            if titel == self.config['hauptstrecke']:
                self.hauptstrecke = key

        for namen, markierung in self.config['streckenmarkierung'].items():
            node1 = self.bahnhofgraph.find_name(namen[0])
            node2 = self.bahnhofgraph.find_name(namen[1])
            if node1 is not None and node2 is not None:
                self.streckenmarkierung[(node1, node2)] = markierung

    def load_config(self, path: os.PathLike, load_graphs=False, ignore_version=False):
        """
        Konfiguration aus Konfigurationsdatei laden.

        :param path: Verzeichnis mit den Konfigurationsdaten.
            Der Dateiname wird aus der Anlagen-ID gebildet.
        :param load_graphs: Die Graphen werden normalerweise vom Simulator abgefragt und erstellt.
            Für die Offline-Auswertung können sie stattdessen aus dem Konfigurationsfile geladen werden.
        :return: None
        :raise: OSError, JSONDecodeError(ValueError)
        """
        if load_graphs:
            p = Path(path) / f"{self.anlageninfo.aid}diag.json"
        else:
            p = Path(path) / f"{self.anlageninfo.aid}.json"

        with open(p, encoding='utf-8') as fp:
            d = json.load(fp, object_hook=json_object_hook)

        if not ignore_version:
            assert d['_aid'] == self.anlageninfo.aid
            if self.anlageninfo.build != d['_build']:
                logger.warning(f"unterschiedliche build-nummern (file: {d['_build']}, sim: {self.anlageninfo.build})")
            if '_version' not in d:
                d['_version'] = 1
                logger.warning(f"konfigurationsdatei ohne versionsangabe. nehme 1 an.")
            if d['_version'] < 2:
                logger.error(f"inkompatible konfigurationsdatei - auto-konfiguration")
                return

        if d['_version'] == 2:
            self.set_config_v2(d)
        elif d['_version'] == 3:
            self.config = d

    def set_config_v2(self, d: Dict):
        """
        Konfigurationsdaten im Format der Version 2 laden.

        :param d:
        :return:
        """
        def _find_sektor(gleis: str, sektoren_gleise: Dict) -> Optional[str]:
            for bahnsteig, gleise in sektoren_gleise.items():
                if gleis in gleise:
                    return bahnsteig
            else:
                return None

        gleis_konfig = {}
        try:
            sektoren = d['sektoren']
        except KeyError:
            logger.info("Fehlende Sektoren-Konfiguration")
            sektoren = {}

        try:
            for bft, gleise in d['bahnsteiggruppen'].items():
                bf = bft + "?"
                for gl in gleise:
                    if bft not in gleis_konfig:
                        gleis_konfig[bf] = {bft: {}}
                    bs = _find_sektor(gl, sektoren)
                    if not bs:
                        bs = gl
                    try:
                        gleis_konfig[bf][bft][bs].add(gl)
                    except KeyError:
                        gleis_konfig[bf][bft][bs] = {gl}
        except KeyError:
            logger.info("Fehlende Bahnsteiggruppen-Konfiguration")

        try:
            anschluss_konfig = d['anschlussgruppen']
        except KeyError:
            logger.info("Fehlende Anschlussgruppen-Konfiguration")
            anschluss_konfig = {}

        self.config['bahnhofgraph'] = bahnhofgraph_konfig_umdrehen(gleis_konfig, anschluss_konfig)

        try:
            self.config['strecken'] = d['strecken']
        except KeyError:
            logger.info("Fehlende Streckenkonfiguration")
            self.config['strecken'] = {}
        try:
            self.config['hauptstrecke'] = d['hauptstrecke']
        except KeyError:
            logger.info("Keine Hauptstrecke konfiguriert")
            self.config['hauptstrecke'] = ""
        try:
            markierungen = d['streckenmarkierung']
        except KeyError:
            logger.info("keine streckenmarkierungen konfiguriert")
            markierungen = []

        streckenmarkierung = {}
        for markierung in markierungen:
            try:
                streckenmarkierung[(markierung[0], markierung[1])] = markierung[2]
            except IndexError:
                pass
        self.config['streckenmarkierung'] = streckenmarkierung

        try:
            self.config['zugschema'] = d['zugschema']
        except KeyError:
            self.config['zugschema'] = ''
