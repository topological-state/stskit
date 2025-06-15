"""
Aktuelle Stellwerk- und Fahrplandaten

Das Anlageobjekt hält die aktuellen Stellwerk- und Fahrplandaten in graphbasierten Datenstrukturen.
Alle Daten können jederzeit ausgelesen werden,
dürfen jedoch nur von Modulen aus dem dispo-Package direkt verändert werden.
"""

import collections
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from stskit.dispo.config import Config
from stskit.model.journal import JournalCollection, JournalIDType, GraphJournal
from stskit.plugin.stsgraph import GraphClient
from stskit.plugin.stsobj import Ereignis, AnlagenInfo, time_to_minutes
from stskit.model.signalgraph import SignalGraph
from stskit.model.bahnhofgraph import BahnhofGraph, BahnsteigGraph
from stskit.model.liniengraph import LinienGraph, LinienGraphEdge, Strecken
from stskit.model.zuggraph import ZugGraph
from stskit.model.zielgraph import ZielGraph
from stskit.model.ereignisgraph import EreignisGraph
from stskit.utils.export import write_gml
from stskit.model.gleisschema import Gleisschema
from stskit.model.zugschema import Zugschema


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ConfigurationError(Exception):
    pass


class Anlage:
    def __init__(self):
        self.anlageninfo: Optional[AnlagenInfo] = None
        self.simzeit_minuten: int = 0
        self.config: Optional[Config] = None
        self.default_config:Optional[Config] = None
        self.aenderungen: Set[str] = set()

        self.signalgraph = SignalGraph()
        self.bahnsteiggraph = BahnsteigGraph()
        self.bahnhofgraph = BahnhofGraph()
        self.liniengraph = LinienGraph()
        self.zuggraph = ZugGraph()
        self.zielgraph = ZielGraph()
        self.ereignisgraph = EreignisGraph()

        self.fdl_korrekturen = JournalCollection()

        self.strecken = Strecken()
        self.strecken.liniengraph = self.liniengraph

        self.gleisschema = Gleisschema()
        self.zugschema = Zugschema()

    def update(self, client: GraphClient, config_path: os.PathLike) -> Set[str]:
        """
        Main update method of Anlage.

        Called at every poll cycle.
        Conditionally performs initialization and configuration if necessary.
        """

        config_path = Path(config_path)
        debug_path = config_path / "debug"

        self._update_client(client, debug_path)

        for _ in range(2):
            try:
                self._load_config(config_path)
                self._init_anlage(debug_path)
                self._init_linien()
                self._init_strecken()
            except ConfigurationError:
                logger.warning("Fehler beim Laden der Konfiguration, versuche Autokonfiguration.")
                self.config = None
                self.default_config = None
                config_path = None
            else:
                break

        self.zielgraph.einfahrtszeiten_korrigieren(self.liniengraph, self.bahnhofgraph)
        self.ereignisgraph.zielgraph_importieren(self.zielgraph)
        self.fdl_korrekturen.replay()
        self.ereignisgraph.prognose()
        self.ereignisgraph.verspaetungen_nach_zielgraph(self.zielgraph)

        if logger.isEnabledFor(logging.DEBUG):
            write_gml(self.zielgraph, debug_path / f"{self.anlageninfo.aid}.zielgraph.gml")
            write_gml(self.ereignisgraph, debug_path / f"{self.anlageninfo.aid}.ereignisgraph.gml")
            # with open(debug_path / f"{self.anlageninfo.aid}.strecken.json", "w") as f:
            #     json.dump(self.strecken.strecken, f)

        aenderungen = self.aenderungen
        self.aenderungen = set()
        return aenderungen

    def _update_client(self, client, debug_path):
        """
        Update the graphs with the current state of the simulation.

        This method updates objects that are direct copies of client objects:
        - `simzeit_minuten`
        - `anlageninfo`
        - `signalgraph`
        - `bahnsteiggraph`
        - `zuggraph`
        - `zielgraph`
        """

        self.simzeit_minuten = time_to_minutes(client.calc_simzeit())

        if self.anlageninfo is None:
            self.anlageninfo = client.anlageninfo
            self.aenderungen.add('anlageninfo')
            self.gleisschema = Gleisschema.regionsschema(self.anlageninfo.region)
            self.aenderungen.add('gleisschema')

        if not self.signalgraph or 'anlageninfo' in self.aenderungen:
            self.signalgraph = client.signalgraph.copy(as_view=False)
            self.aenderungen.add('signalgraph')
            if logger.isEnabledFor(logging.DEBUG):
                debug_path.mkdir(exist_ok=True)
                write_gml(self.signalgraph, debug_path / f"{self.anlageninfo.aid}.signalgraph.gml")

        if not self.bahnsteiggraph or {'anlageninfo', 'signalgraph'} & self.aenderungen:
            self.bahnsteiggraph = client.bahnsteiggraph.copy(as_view=False)
            self.aenderungen.add('bahnsteiggraph')
            if logger.isEnabledFor(logging.DEBUG):
                write_gml(self.bahnsteiggraph, debug_path / f"{self.anlageninfo.aid}.bahnsteiggraph.gml")

        self.zuggraph = client.zuggraph.copy(as_view=True)
        self.aenderungen.add('zuggraph')
        self.zielgraph = client.zielgraph.copy(as_view=False)
        self.aenderungen.add('zielgraph')

    def _load_config(self, config_path):
        if self.config is None:
            if config_path:
                self.load_config(config_path)
            else:
                self.config = Config()
                self.config['default'] = True
            self.aenderungen.add('config')

    def _init_anlage(self, debug_path):
        # abhängigkeiten
        if self.bahnhofgraph:
            aenderungen = self.aenderungen.copy()
        else:
            aenderungen = {'config'}
        if 'config' in aenderungen:
            aenderungen.add('anlageninfo')
        if 'anlageninfo' in aenderungen:
            aenderungen.add('bahnsteiggraph')
        if 'bahnsteiggraph' in aenderungen:
            aenderungen.add('signalgraph')
        if 'signalgraph' in aenderungen:
            aenderungen.add('config')
        if 'gleisschema' in aenderungen:
            aenderungen.add('bahnsteiggraph')
            aenderungen.add('signalgraph')

        if aenderungen:
            if 'anlageninfo' in aenderungen:
                logger.debug("_init_anlage: import_anlageninfo")
                self.bahnhofgraph.import_anlageninfo(self.anlageninfo)
                self.aenderungen.add('bahnhofgraph')
            if 'bahnsteiggraph' in aenderungen:
                if self.bahnsteiggraph:
                    logger.debug("_init_anlage: import_bahnsteiggraph")
                    self.bahnhofgraph.import_bahnsteiggraph(self.bahnsteiggraph, self.gleisschema)
                    self.aenderungen.add('bahnhofgraph')
            if 'signalgraph' in aenderungen:
                if self.signalgraph:
                    logger.debug("_init_anlage: import_signalgraph")
                    self.bahnhofgraph.import_signalgraph(self.signalgraph, self.gleisschema)
                    self.aenderungen.add('bahnhofgraph')
            if 'config' in aenderungen:
                try:
                    logger.debug("_init_anlage: import_konfiguration")
                    self.bahnhofgraph.import_konfiguration(self.config['elemente'])
                    self.aenderungen.add('bahnhofgraph')
                except KeyError:
                    logger.warning("Fehler in Bahnhofkonfiguration")

        if 'bahnhofgraph' in self.aenderungen:
            if logger.isEnabledFor(logging.DEBUG):
                write_gml(self.bahnhofgraph, debug_path / f"{self.anlageninfo.aid}.bahnhofgraph.gml")

    def _init_linien(self):
        """
        Liniengraph konfigurieren

        Benoetigt: bahnhofgraph, liniengraph, zielgraph, signalgraph
        """

        # abhängigkeiten
        if self.liniengraph:
            aenderungen = self.aenderungen.copy()
        elif self.bahnhofgraph and self.zielgraph:
            aenderungen = {'bahnhofgraph', 'zielgraph'}
        else:
            aenderungen = set()

        if 'config' in aenderungen:
            aenderungen.add('bahnhofgraph')
        if 'zielgraph' in aenderungen:
            aenderungen.add('bahnhofgraph')
        if 'bahnhofgraph' in aenderungen:
            aenderungen.add('signalgraph')
        if 'signalgraph' in aenderungen:
            aenderungen.add('config')
        if 'streckenmarkierung' in aenderungen:
            aenderungen.add('config')

        if 'bahnhofgraph' in aenderungen:
            try:
                logger.debug("Liniengraph konfigurieren.")
                self.liniengraph_konfigurieren()
                self.aenderungen.add('liniengraph')
            except KeyError as e:
                logger.error(e)
                raise ConfigurationError()

        if 'signalgraph' in aenderungen:
            try:
                logger.debug("Liniengraph mit Signalgraph abgleichen.")
                self.liniengraph_mit_signalgraph_abgleichen()
                self.aenderungen.add('liniengraph')
            except KeyError as e:
                logger.error(e)
                raise ConfigurationError()

        if 'config' in aenderungen:
            try:
                self.liniengraph.import_konfiguration(self.config['streckenmarkierung'], self.bahnhofgraph)
                self.aenderungen.add('liniengraph')
                logger.debug("Liniengraph konfiguriert.")
            except KeyError:
                logger.info("Keine Streckenmarkierungskonfiguration gefunden")


    def _init_strecken(self):
        """
        Strecken konfigurieren

        Benoetigt: bahnhofgraph, liniengraph
        """

        # abhängigkeiten
        if self.strecken.strecken:
            aenderungen = self.aenderungen.copy()
        elif self.liniengraph:
            aenderungen = {'bahnhofgraph', 'config'}
        else:
            aenderungen = set()

        if 'config' in aenderungen:
            aenderungen.add('bahnhofgraph')
        if 'liniengraph' in aenderungen:
            aenderungen.add('bahnhofgraph')

        any_auto = False
        create_auto = False

        if 'config' in aenderungen:
            try:
                self.strecken.import_konfiguration(self.config['strecken'], self.bahnhofgraph)
                self.aenderungen.add('strecken')
            except KeyError:
                logger.warning("Keine Streckenkonfiguration gefunden")

            # bestehende automatische strecken aktualisieren
            # neue auto-strecken nur erstellen, wenn die liste leer ist
            any_auto = any_auto or any(self.strecken.auto.values())
            create_auto = create_auto or len(self.strecken.strecken) == 0

        if 'bahnhofgraph' in aenderungen:
            # strecken korrigieren
            self.strecken.validate(self.bahnhofgraph)
            any_auto = any_auto or any(self.strecken.auto.values())
            create_auto = create_auto or len(self.strecken.strecken) == 0

        if any_auto or create_auto:
            strecken = self.liniengraph.strecken_vorschlagen(2, 3)
            strecken = {f"{strecke[0][1]}-{strecke[-1][1]}": strecke for strecke in strecken}
            for index, name in enumerate(sorted(strecken.keys())):
                if self.strecken.auto.get(name, create_auto):
                    self.strecken.add_strecke(name, strecken[name], 100 + index, True)
                    self.aenderungen.add('strecken')

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
                try:
                    bst1 = self.bahnhofgraph.find_superior(ziel1_data.plan_bst, {'Bf', 'Anst'})
                    bst2 = self.bahnhofgraph.find_superior(ziel2_data.plan_bst, {'Bf', 'Anst'})
                except KeyError:
                    continue
                if bst1 != bst2:
                    bst1_data = self.bahnhofgraph.nodes[bst1]
                    bst2_data = self.bahnhofgraph.nodes[bst2]
                    self.liniengraph.linie_eintragen(ziel1_data, bst1_data, ziel2_data, bst2_data)
                    self.aenderungen.add('liniengraph')

        if 'liniengraph' in self.aenderungen:
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

        self.aenderungen.add('liniengraph')

    def load_config(self, config_path: os.PathLike):
        """
        Konfiguration aus Konfigurationsdatei laden.

        :param config_path: Verzeichnis mit den Konfigurationsdaten.
            Der Dateiname wird aus der Anlagen-ID gebildet.
        :return: None
        :raise: OSError, JSONDecodeError(ValueError)
        """

        default_path = Path(__file__).parent.parent / "config"

        Zugschema.find_schemas(default_path)
        Zugschema.find_schemas(config_path)

        if self.default_config is None:
            self.aenderungen.add('default_config')
            self.default_config = Config()
            p = Path(default_path) / f"{self.anlageninfo.aid}.json"
            try:
                logger.info(f"Beispielkonfiguration laden von {p}")
                self.default_config.load(p, aid=self.anlageninfo.aid)
                self.default_config["default"] = True
            except OSError:
                logger.warning(f"Keine Beispielkonfiguration gefunden")

        if self.config is None:
            self.aenderungen.add('config')
            self.config = Config()
            self.config["default"] = True
            p = Path(config_path) / f"{self.anlageninfo.aid}.json"
            try:
                logger.info(f"Konfiguration laden von {p}")
                self.config.load(p, aid=self.anlageninfo.aid)
            except OSError:
                logger.warning(f"Benutzerkonfiguration {p} nicht gefunden")

            # elemente, strecken, streckenmarkierung, zugschema
            if 'elemente' not in self.config:
                self.config['elemente'] = self.default_config.get('elemente', {})
            if 'strecken' not in self.config:
                self.config['strecken'] = self.default_config.get('strecken', {})
            if 'streckenmarkierung' not in self.config:
                self.config['streckenmarkierung'] = self.default_config.get('streckenmarkierung', {})
            if 'zugschema' not in self.config:
                self.config['zugschema'] = self.default_config.get('zugschema', {})

        self.zugschema.load_config(self.config.get('zugschema', ''), self.anlageninfo.region)
        self.aenderungen.add('zugschema')

    def save_config(self, path: os.PathLike):
        self.config["_aid"] = self.anlageninfo.aid
        self.config["_build"] = self.anlageninfo.build
        self.config["_name"] = self.anlageninfo.name
        self.config["_region"] = self.anlageninfo.region

        self.config['elemente'] = self.bahnhofgraph.export_konfiguration()
        self.config['strecken'] = self.strecken.export_konfiguration()
        self.config['streckenmarkierung'] = self.liniengraph.export_konfiguration()
        self.config['zugschema'] = self.zugschema.name

        p = Path(path) / f"{self.anlageninfo.aid}.json"
        self.config.save(p)

    def sim_ereignis_uebernehmen(self, ereignis: Ereignis):
        self.ereignisgraph.sim_ereignis_uebernehmen(ereignis)
