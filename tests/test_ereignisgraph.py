import unittest

import networkx as nx

from stskit.graphs.ereignisgraph import EreignisGraph, EreignisGraphEdge, EreignisGraphNode
from stskit.graphs.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode, PlanungParams


class TestEreignisPrognose(unittest.TestCase):
    """
    Prognose testen in einem Beispielgraph
    """
    def setUp(self):
        self.zielgraph = ZielGraph()

        nodes = [
            ZielGraphNode(
                fid=(11, 0, 1),
                zid=11,
                typ='E',
                flags='',
                status='',
                p_an=300,
                p_ab=300,
                v_an=0,
                v_ab=0
            ), # 0
            # P
            ZielGraphNode(
                fid=(11, 0, "A 1"),
                zid=11,
                typ='D',
                flags='D',
                mindestaufenthalt=0,
                status='',
                p_an=322,
                p_ab=322,
                v_an=0,
                v_ab=0
            ), # 1
            # P
            ZielGraphNode(
                fid=(11, 0, "B 1"),
                zid=11,
                typ='H',
                flags='E(12)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_ersatz,
                status='',
                p_an=332,
                v_an=0,
                v_ab=0
            ), # 2
            # E
            ZielGraphNode(
                fid=(12, 0, "B 1"),
                zid=12,
                typ='H',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=336,
                p_ab=336,
                v_an=0,
                v_ab=0
            ), # 3
            # P
            ZielGraphNode(
                fid=(12, 0, "C 1"),
                zid=12,
                typ='H',
                flags='K(13)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_kupplung,
                status='',
                p_an=345,
                v_an=0,
                v_ab=0
            ), # 4
            # K -> 13 C 1
            ZielGraphNode(
                fid=(13, 0, 2),
                zid=13,
                typ='E',
                flags='K(13)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_kupplung,
                status='',
                p_an=330,
                p_ab=330,
                v_an=0,
                v_ab=0
            ), # 5
            # P
            ZielGraphNode(
                fid=(13, 0, "C 1"),
                zid=13,
                typ='H',
                flags='',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_planhalt,
                status='',
                p_an=340,
                p_ab=350,
                v_an=0,
                v_ab=0
            ), # 6
            # P, F -> 14
            ZielGraphNode(
                fid=(13, 0, "D 1"),
                zid=13,
                typ='H',
                flags='F(14)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_fluegelung,
                status='',
                p_an=360,
                p_ab=365,
                v_an=0,
                v_ab=0
            ), # 7
            #P
            ZielGraphNode(
                fid=(13, 0, 3),
                zid=13,
                typ='A',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=370,
                v_an=0,
                v_ab=0
            ), # 8

            ZielGraphNode(
                fid=(14, 0, "D 1"),
                zid=14,
                typ='H',
                flags='',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_planhalt,
                status='',
                p_an=360,
                p_ab=367,
                v_an=0,
                v_ab=0
            ), # 9
            # P
            ZielGraphNode(
                fid=(14, 0, 3),
                zid=14,
                typ='A',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=377,
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
        Import aus Zielgraph überprüfen.

        Wir testen summarisch:
        - Isomorphie mit Referenzgraph
        - Anzahl Knoten nach Typen
        - Anzahl Kanten nach Typen
        """

        # nx.write_gml(self.ereignisgraph, "ereignisgraph.gml", stringizer=str)
        self.assertGreaterEqual(len(self.ereignisgraph.nodes), 16)
        self.assertGreaterEqual(len(self.ereignisgraph.edges), 15)

        iso_edges = [
            (1, 3, 'P'),
            (3, 4, 'P'),
            (4, 5, 'E'),
            (5, 6, 'H'),
            (6, 7, 'P'),
            (7, 12, 'K'),

            (10, 11, 'P'),
            (11, 12, 'H'),
            (12, 13, 'H'),
            (13, 14, 'P'),
            (14, 15, 'F'),
            (15, 16, 'H'),
            (16, 17, 'P'),

            (15, 18, 'H'),
            (18, 19, 'P')
        ]
        iso_graph = nx.DiGraph()
        for edge in iso_edges:
            iso_graph.add_edge(edge[0], edge[1], typ=edge[2])

        self.assertTrue(nx.is_isomorphic(self.ereignisgraph, iso_graph), 'isomorphic graph')

        types = {'Ab': 0, 'An': 0, 'E': 0, 'K': 0, 'F': 0}
        expected_types = {'Ab': 6, 'An': 7, 'E': 1, 'K': 1, 'F': 1}
        for node, typ in self.ereignisgraph.nodes(data='typ'):
            types[typ] += 1
        self.assertDictEqual(types, expected_types, "Knotentypen")

        types = {'P': 0, 'H': 0, 'E': 0, 'K': 0, 'F': 0}
        expected_types = {'P': 7, 'H': 5, 'E': 1, 'K': 1, 'F': 1}
        for u, v, typ in self.ereignisgraph.edges(data='typ'):
            types[typ] += 1
        self.assertDictEqual(types, expected_types, "Kantentypen")

    def test_zugpfad(self):
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(11)]
        exp = [(11, 'Ab'), (11, 'An'), (11, 'An'), (11, 'E')]
        self.assertListEqual(act, exp, "Zug 11")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(12)]
        exp = [(12, 'Ab'), (12, 'An')]
        self.assertListEqual(act, exp, "Zug 12")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(13)]
        exp = [(13, 'Ab'), (13, 'An'), (13, 'K'), (13, 'Ab'), (13, 'An'), (13, 'F'), (13, 'Ab'), (13, 'An')]
        self.assertListEqual(act, exp, "Zug 13")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(14)]
        exp = [(14, 'Ab'), (14, 'An')]
        self.assertListEqual(act, exp, "Zug 14")

    def test_prognose_1(self):
        """
        Prognose testen: keine Verspätungen
        """
        self.ereignisgraph.prognose()
        act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(11)]
        exp = [300, 322, 332, 332 + PlanungParams.mindestaufenthalt_ersatz]
        self.assertListEqual(act, exp, "Zug 11")
        act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(12)]
        exp = [336, 345]
        self.assertListEqual(act, exp, "Zug 12")
        act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(13)]
        exp = [330, 340, 345 + PlanungParams.mindestaufenthalt_kupplung, 350, 360, 361, 365, 370]
        self.assertListEqual(act, exp, "Zug 13")
        act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(14)]
        exp = [367, 377]
        self.assertListEqual(act, exp, "Zug 14")

    def test_prognose_11(self):
        """
        Prognose testen: Eingangsverspätung Zug 11
        """

        def _test(v):
            start_node = self.ereignisgraph.nodes[(11, 0)]
            start_node.t = start_node.p + v
            start_node.fix = True
            self.ereignisgraph.prognose()
            exp = [300 + v, 322 + v, 332 + v]
            e_zeit = 332 + v + PlanungParams.mindestaufenthalt_ersatz
            exp.append(e_zeit)
            act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(11)]
            self.assertListEqual(act, exp, f"Zug 11, v = {v}")
            exp = [max(e_zeit, 336)]
            exp.append(exp[0] + 9)
            act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(12)]
            self.assertListEqual(act, exp, f"Zug 12, v = {v}")
            k_zeit = exp[-1] + PlanungParams.mindestaufenthalt_kupplung
            exp = [330, 340, k_zeit]
            exp.append(max(k_zeit, 350))
            exp.append(exp[-1] + 10)
            f_zeit = exp[-1] + PlanungParams.mindestaufenthalt_fluegelung
            exp.append(f_zeit)
            exp.append(max(365, f_zeit))
            exp.append(max(370, f_zeit + 5))
            act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(13)]
            self.assertListEqual(act, exp, f"Zug 13, v = {v}")
            exp = [max(367, f_zeit), max(377, f_zeit + 10)]
            act = [self.ereignisgraph.nodes(data='t', default='?')[n] for n in self.ereignisgraph.zugpfad(14)]
            self.assertListEqual(act, exp, f"Zug 14, v = {v}")

        _test(5)
        _test(10)
        _test(20)
        _test(-5)


if __name__ == '__main__':
    unittest.main()
