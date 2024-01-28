import unittest

import networkx as nx

from stskit.graphs.ereignisgraph import EreignisGraph, EreignisGraphEdge, EreignisGraphNode
from stskit.graphs.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode


def z(hh, mm):
    return hh * 60 + mm


class TestEreignisPrognose(unittest.TestCase):
    """
    Prognose testen in einem Beispielgraph
    """
    def setUp(self):
        self.zielgraph = ZielGraph()

        nodes = [
            ZielGraphNode(
                fid=(11, 0, 0, 1),
                zid=11,
                typ='E',
                flags='',
                status='',
                p_an = z(5, 0),
                p_ab = z(5, 0),
                v_an=0,
                v_ab=0
            ), # 0
            # P
            ZielGraphNode(
                fid=(11, 0, 0, "A 1"),
                zid=11,
                typ='D',
                flags='D',
                mindestaufenthalt=0,
                status='',
                p_an=z(5, 22),
                p_ab=z(5, 22),
                v_an=0,
                v_ab=0
            ), # 1
            # P
            ZielGraphNode(
                fid=(11, 0, 0, "B 1"),
                zid=11,
                typ='H',
                flags='E(12)',
                mindestaufenthalt=0,
                status='',
                p_an=z(5, 32),
                v_an=0,
                v_ab=0
            ), # 2
            # E
            ZielGraphNode(
                fid=(12, 0, 0, "B 1"),
                zid=12,
                typ='H',
                flags='',
                mindestaufenthalt=2,
                status='',
                p_an=z(5, 36),
                p_ab=z(5, 36),
                v_an=0,
                v_ab=0
            ), # 3
            # P
            ZielGraphNode(
                fid=(12, 0, 0, "C 1"),
                zid=12,
                typ='H',
                flags='K(13)',
                mindestaufenthalt=4,
                status='',
                p_an=z(5, 45),
                v_an=0,
                v_ab=0
            ), # 4
            # K -> 13 C 1
            ZielGraphNode(
                fid=(13, 0, 0, 2),
                zid=13,
                typ='E',
                flags='K(13)',
                mindestaufenthalt=4,
                status='',
                p_an=z(5, 30),
                v_an=0,
                v_ab=0
            ), # 5
            # P
            ZielGraphNode(
                fid=(13, 0, 0, "C 1"),
                zid=13,
                typ='H',
                flags='',
                mindestaufenthalt=1,
                status='',
                p_an=z(5, 40),
                p_ab=z(5, 45),
                v_an=0,
                v_ab=0
            ), # 6
            # P, F -> 14
            ZielGraphNode(
                fid=(13, 0, 0, "D 1"),
                zid=13,
                typ='H',
                flags='F(14)',
                mindestaufenthalt=1,
                status='',
                p_an=z(6, 0),
                p_ab=z(6, 5),
                v_an=0,
                v_ab=0
            ), # 7
            #P
            ZielGraphNode(
                fid=(13, 0, 0, 3),
                zid=13,
                typ='A',
                flags='',
                mindestaufenthalt=1,
                status='',
                p_an=z(6, 10),
                v_an=0,
                v_ab=0
            ), # 8

            ZielGraphNode(
                fid=(14, 0, 0, "D 1"),
                zid=14,
                typ='H',
                flags='',
                mindestaufenthalt=1,
                status='',
                p_an=z(6, 0),
                p_ab=z(6, 7),
                v_an=0,
                v_ab=0
            ), # 9
            # P
            ZielGraphNode(
                fid=(14, 0, 0, 3),
                zid=14,
                typ='A',
                flags='',
                status='',
                p_an=z(6, 17),
                v_an=0,
                v_ab=0
            ) # 10
        ]

        edges = [
            (0, 1, 'P'),
            (1, 2, 'P'),
            (2, 3, 'E'),
            (3, 4, 'P'),
            (5, 6, 'P'),
            (4, 6, 'K'),
            (6, 7, 'P'),
            (7, 8, 'P'),
            (7, 9, 'F'),
            (9, 10, 'P')
        ]

        for node in nodes:
            self.zielgraph.add_node(node.fid, **node)

        for edge in edges:
            self.zielgraph.add_edge(nodes[edge[0]].fid, nodes[edge[1]].fid, typ=edge[2])

        self.ereignisgraph = EreignisGraph()
        self.ereignisgraph.zielgraph_importieren(self.zielgraph)

    def test_import(self):
        """
        expected

        """

        self.assertGreaterEqual(len(self.ereignisgraph.nodes), 17)
        nx.write_gml(self.ereignisgraph, "ereignisgraph.gml", stringizer=str)


if __name__ == '__main__':
    unittest.main()
