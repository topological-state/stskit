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
        pass

    def update(self, anlage: Anlage, config_path: os.PathLike):
        pass
