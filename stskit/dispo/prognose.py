"""
Verspätungsprognose auf dem Zielgraph


Planhalt
--------

- Abfahrt frühestens um p_ab oder effektiver Ankunftszeit plus Mindestaufenthaltszeit.

Durchfahrt
----------

- Verspätung bleibt gleich

Vorzeitige Abfahrt
------------------

- Abfahrt um p_ab, effektiver Ankunftszeit plus Mindestaufenthalts, oder Fdl-Angabe
- Verspätung verringert sich

Betriebshalt
------------

- Ungeplanter Halt
- Abfahrt oder Wartezeit gemäss Fdl-Angabe

Nummernwechsel
--------------

- ???

Kupplung
--------

- ???

Flügelung
---------

- ???

Kreuzung/Anschluss abwarten
---------------------------

- Abfahrt sobald angegebenes Ziel erreicht ist (Ankunft) plus Wartezeit

Überholung
----------

- Abfahrt sobald angegebenes Ziel verlassen wird (Abfahrt abwarten) plus Wartezeit.

Folgen
------

- Ankunft frühestens wenn angegebenes Ziel erreicht ist (Ankunft) plus Wartezeit.

"""

import math

import networkx as nx
import numpy as np

from stskit.graphs.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode

docstring = """
    Verbindungstyp:
        'P': planmässige Fahrt,
        'E': Ersatzzug,
        'F': Flügelung,
        'K': Kupplung,
        'R': vom Fdl angeordnete Rangierfahrt, z.B. bei Lokwechsel,
        'A': vom Fdl angeordnete Abhängigkeit,
        'O': Hilfskante für Sortierordnung.
    """


def prognose(zg: ZielGraph):
    topo = nx.topological_sort(zg)
    for node in topo:
        node_data = zg.nodes[node]

        # todo : abgearbeitete ziele nicht mehr verändern

        # eingangsverarbeitung
        # todo : ankunfts- oder abfahrtsverspätung?
        v_an = -math.inf # oder t_an?
        v_ab = -math.inf # oder t_ab?
        for n1, n2, edge_data in zg.in_edges(node, data=True):
            if edge_data.typ in {'P'}:
                try:
                    v_an = max(v_an, edge_data.v)
                except AttributeError:
                    pass

        if not math.isinf(v_an):
            node_data.v_an = v_an

        # knotenverarbeitung
        # todo : verspätung an fahrplan ausrichten
        node_data.v_ab = node_data.v_an

        # ausgangsverarbeitung
        for n1, n2, out_data in zg.out_edges(node, data=True):
            out_data.v = node_data.v_ab

