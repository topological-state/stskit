import logging
import os
from typing import Any, Dict

import networkx as nx

from stskit.dispo.anlage import Anlage
from stskit.plugin.stsgraph import GraphClient
from stskit.plugin.stsobj import Ereignis
from stskit.model.ereignisgraph import EreignisGraph
from stskit.model.zielgraph import ZielGraph
from stskit.model.zuggraph import ZugGraph
from stskit.model.zugschema import Zugschema

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
