import collections
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx

from stskit.dispo.anlage import Anlage
from stskit.interface.stsgraph import GraphClient
from stskit.interface.stsobj import Ereignis
from stskit.graphs.ereignisgraph import EreignisGraph
from stskit.graphs.zielgraph import ZielGraph
from stskit.graphs.zuggraph import ZugGraph
from stskit.zugschema import Zugschema

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Betrieb:
    def __init__(self):
        self.config: Dict[str, Any] = {}

        self.zuggraph = ZugGraph()
        self.zielgraph = ZielGraph()
        self.ereignisgraph = EreignisGraph()

        self.zugschema = Zugschema()

    def update(self, client: GraphClient, anlage: Anlage, config_path: os.PathLike):
        self.zielgraph = client.zielgraph.copy(as_view=True)
        self.zielgraph.einfahrtszeiten_korrigieren(anlage.liniengraph, anlage.bahnhofgraph)
        self.ereignisgraph.zielgraph_importieren(self.zielgraph)
        self.ereignisgraph.prognose()
        if logger.isEnabledFor(logging.DEBUG):
            nx.write_gml(self.zielgraph, "zielgraph.gml", stringizer=str)
            nx.write_gml(self.ereignisgraph, "ereignisgraph.gml", stringizer=str)
        self.ereignisgraph.verspaetungen_nach_zielgraph(self.zielgraph)

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        pass
