import unittest

import networkx as nx

from stskit.model.ereignisgraph import EreignisGraph, EreignisGraphEdge, EreignisGraphNode, EreignisLabelType
from stskit.model.zielgraph import ZielGraph, ZielGraphEdge, ZielGraphNode, PlanungParams, ZielLabelType


class TestEreignisPrognose(unittest.TestCase):
    """
    Prognose testen in einem Beispielgraph
    """
    def szenario1(self):
        self.zielgraph = ZielGraph()

        nodes = [
            ZielGraphNode(
                fid=ZielLabelType(11, 300, 1),
                zid=11,
                typ='E',
                plan='Agl 1',
                gleis='Agl 1',
                flags='',
                status='',
                p_an=300,
                p_ab=300,
                v_an=0,
                v_ab=0
            ), # 0
            # P
            ZielGraphNode(
                fid=ZielLabelType(11, 322, "A 1"),
                zid=11,
                typ='D',
                plan='A 1',
                gleis='A 1',
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
                fid=ZielLabelType(11, 332, "B 1"),
                zid=11,
                typ='H',
                plan='B 1',
                gleis='B 1',
                flags='E(12)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_ersatz,
                status='',
                p_an=332,
                v_an=0,
                v_ab=0
            ), # 2
            # E
            ZielGraphNode(
                fid=ZielLabelType(12, 336, "B 1"),
                zid=12,
                typ='H',
                plan='B 1',
                gleis='B 1',
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
                fid=ZielLabelType(12, 345, "C 1"),
                zid=12,
                typ='H',
                plan='C 1',
                gleis='C 1',
                flags='K(13)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_kupplung,
                status='',
                p_an=345,
                v_an=0,
                v_ab=0
            ), # 4
            # K -> 13 C 1
            ZielGraphNode(
                fid=ZielLabelType(13, 330, 2),
                zid=13,
                typ='E',
                plan='Agl 2',
                gleis='Agl 2',
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
                fid=ZielLabelType(13, 340, "C 1"),
                zid=13,
                typ='H',
                plan='C 1',
                gleis='C 1',
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
                fid=ZielLabelType(13, 360, "D 1"),
                zid=13,
                typ='H',
                plan='D 1',
                gleis='D 1',
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
                fid=ZielLabelType(13, 370, 3),
                zid=13,
                typ='A',
                plan='Agl 3',
                gleis='Agl 3',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=370,
                v_an=0,
                v_ab=0
            ), # 8

            ZielGraphNode(
                fid=ZielLabelType(14, 360, "D 1"),
                zid=14,
                typ='H',
                plan='D 1',
                gleis='D 1',
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
                fid=ZielLabelType(14, 377, 3),
                zid=14,
                typ='A',
                plan='Agl 3',
                gleis='Agl 3',
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

        self.szenario1()

        # nx.write_gml(self.ereignisgraph, "ereignisgraph-szenario1.gml", stringizer=str)
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
        self.szenario1()
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

        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(11, kuppeln=True)]
        exp = [(11, 'Ab'), (11, 'An'), (11, 'An'), (11, 'E'), (12, 'Ab'), (12, 'An'),
               (13, 'K'), (13, 'Ab'), (13, 'An'), (13, 'F'), (13, 'Ab'), (13, 'An')]
        self.assertListEqual(act, exp, "Zug 11 gekuppelt")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(12, kuppeln=True)]
        exp = [(12, 'Ab'), (12, 'An'), (13, 'K'), (13, 'Ab'), (13, 'An'), (13, 'F'), (13, 'Ab'), (13, 'An')]
        self.assertListEqual(act, exp, "Zug 12 gekuppelt")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(13, kuppeln=True)]
        exp = [(13, 'Ab'), (13, 'An'), (13, 'K'), (13, 'Ab'), (13, 'An'), (13, 'F'), (13, 'Ab'), (13, 'An')]
        self.assertListEqual(act, exp, "Zug 13")
        act = [(n[0], self.ereignisgraph.nodes[n]['typ']) for n in self.ereignisgraph.zugpfad(14, kuppeln=True)]
        exp = [(14, 'Ab'), (14, 'An')]
        self.assertListEqual(act, exp, "Zug 14")

    def test_prognose_1(self):
        """
        Prognose testen: keine Verspätungen
        """
        self.szenario1()
        self.ereignisgraph.prognose()
        act = [self.ereignisgraph.nodes(data='t_prog', default='?')[n] for n in self.ereignisgraph.zugpfad(11)]
        exp = [300, 322, 332, 332 + PlanungParams.mindestaufenthalt_ersatz]
        self.assertListEqual(act, exp, "Zug 11")
        act = [self.ereignisgraph.nodes(data='t_prog', default='?')[n] for n in self.ereignisgraph.zugpfad(12)]
        exp = [336, 345]
        self.assertListEqual(act, exp, "Zug 12")
        act = [self.ereignisgraph.nodes(data='t_prog', default='?')[n] for n in self.ereignisgraph.zugpfad(13)]
        exp = [330, 340, 345 + PlanungParams.mindestaufenthalt_kupplung, 350, 360, 361, 365, 370]
        self.assertListEqual(act, exp, "Zug 13")
        act = [self.ereignisgraph.nodes(data='t_prog', default='?')[n] for n in self.ereignisgraph.zugpfad(14)]
        exp = [367, 377]
        self.assertListEqual(act, exp, "Zug 14")

    def test_prognose_11(self):
        """
        Prognose testen: Eingangsverspätung Zug 11
        """

        def _test(v):
            start_node = self.ereignisgraph.nodes[self.ereignisgraph.zuganfaenge[11]]
            start_node.t_mess = start_node.t_plan + v
            self.ereignisgraph.prognose()
            exp = [300 + v, 322 + v, 332 + v]
            e_zeit = 332 + v + PlanungParams.mindestaufenthalt_ersatz
            exp.append(e_zeit)
            act = [self.ereignisgraph.nodes[n].t_eff for n in self.ereignisgraph.zugpfad(11)]
            self.assertListEqual(act, exp, f"Zug 11, v = {v}")
            exp = [max(e_zeit, 336)]
            exp.append(exp[0] + 9)
            act = [self.ereignisgraph.nodes[n].t_eff for n in self.ereignisgraph.zugpfad(12)]
            self.assertListEqual(act, exp, f"Zug 12, v = {v}")
            k_zeit = exp[-1] + PlanungParams.mindestaufenthalt_kupplung
            exp = [330, 340, k_zeit]
            exp.append(max(k_zeit, 350))
            exp.append(exp[-1] + 10)
            f_zeit = exp[-1] + PlanungParams.mindestaufenthalt_fluegelung
            exp.append(f_zeit)
            exp.append(max(365, f_zeit))
            exp.append(max(370, f_zeit + 5))
            act = [self.ereignisgraph.nodes[n].t_eff for n in self.ereignisgraph.zugpfad(13)]
            self.assertListEqual(act, exp, f"Zug 13, v = {v}")
            exp = [max(367, f_zeit), max(377, f_zeit + 10)]
            act = [self.ereignisgraph.nodes[n].t_eff for n in self.ereignisgraph.zugpfad(14)]
            self.assertListEqual(act, exp, f"Zug 14, v = {v}")

        self.szenario1()
        _test(5)
        _test(10)
        _test(20)
        _test(-5)

    def szenario2(self):
        """
        Loktausch zwischen 2 Zuegen (Stw Jenbach)
        """
        self.zielgraph = ZielGraph()

        nodes = [
            ZielGraphNode(
                fid=ZielLabelType(1, 340, 1),
                zid=1,
                typ='E',
                plan='Agl 1',
                gleis='Agl 1',
                flags='',
                status='',
                p_an=340,
                p_ab=340,
                v_an=0,
                v_ab=0
            ), # 0
            ZielGraphNode(
                fid=ZielLabelType(1, 350, "A"),
                zid=1,
                typ='H',
                plan='A',
                gleis='A',
                flags='F(3)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_fluegelung,
                status='',
                p_an=350,
                p_ab=374,
                v_an=0,
                v_ab=0
            ), # 1
            ZielGraphNode(
                fid=ZielLabelType(1, 384, 2),
                zid=1,
                typ='A',
                plan='Agl 2',
                gleis='Agl 2',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=384,
                v_an=0,
                v_ab=0
            ), # 2

            ZielGraphNode(
                fid=ZielLabelType(2, 357, 2),
                zid=2,
                typ='E',
                plan='Agl 2',
                gleis='Agl 2',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=357,
                p_ab=357,
                v_an=0,
                v_ab=0
            ), # 3
            ZielGraphNode(
                fid=ZielLabelType(2, 367, "B"),
                zid=2,
                typ='H',
                plan='B',
                gleis='B',
                flags='F(4)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_fluegelung,
                status='',
                p_an=367,
                p_ab=400,
                v_an=0,
                v_ab=0
            ), # 4
            ZielGraphNode(
                fid=ZielLabelType(2, 410, 1),
                zid=2,
                typ='A',
                plan='Agl 1',
                gleis='Agl 1',
                flags='',
                mindestaufenthalt=0,
                status='',
                p_an=410,
                p_ab=410,
                v_an=0,
                v_ab=0
            ), # 5

            ZielGraphNode(
                fid=ZielLabelType(3, 350, "A"),
                zid=3,
                typ='H',
                plan='A',
                gleis='A',
                flags='',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_planhalt,
                status='',
                p_an=350,
                p_ab=355,
                v_an=0,
                v_ab=0
            ), # 6
            ZielGraphNode(
                fid=ZielLabelType(3, 361, "B"),
                zid=3,
                typ='H',
                plan='B',
                gleis='B',
                flags='K(2)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_kupplung,
                status='',
                p_an=361,
                v_an=0,
                v_ab=0
            ), # 7

            ZielGraphNode(
                fid=ZielLabelType(4, 367, "B"),
                zid=4,
                typ='H',
                plan='B',
                gleis='B',
                flags='',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_planhalt,
                status='',
                p_an=367,
                p_ab=368,
                v_an=0,
                v_ab=0
            ), # 8
            ZielGraphNode(
                fid=ZielLabelType(4, 372, "A"),
                zid=4,
                typ='H',
                plan='A',
                gleis='A',
                flags='K(1)',
                mindestaufenthalt=PlanungParams.mindestaufenthalt_kupplung,
                status='',
                p_an=372,
                v_an=0,
                v_ab=0
            ) # 9
        ]

        edges = [
            (0, 1, 'P'),
            (1, 2, 'P'),
            (1, 6, 'F'),
            (6, 7, 'P'),
            (7, 4, 'K'),
            (3, 4, 'P'),
            (4, 5, 'P'),
            (4, 8, 'F'),
            (8, 9, 'P'),
            (9, 1, 'K')
        ]

        for node in nodes:
            self.zielgraph.add_node(node.fid, **node)

        for edge in edges:
            self.zielgraph.add_edge(nodes[edge[0]].fid, nodes[edge[1]].fid, typ=edge[2])

        self.ereignisgraph = EreignisGraph()
        self.ereignisgraph.zielgraph_importieren(self.zielgraph)

    def test_import_szenario2(self):
        """
        Import aus Zielgraph im Szenario 2 überprüfen.

        Wir testen summarisch:
        - Isomorphie mit Referenzgraph
        - Anzahl Knoten nach Typen
        - Anzahl Kanten nach Typen
        """

        self.szenario2()

        # nx.write_gml(self.ereignisgraph, "ereignisgraph-szenario2.gml", stringizer=str)
        self.assertGreaterEqual(len(self.ereignisgraph.nodes), 16)
        self.assertGreaterEqual(len(self.ereignisgraph.edges), 16)

        iso_edges = [
            (11, 12, 'P'),
            (12, 13, 'F'),
            (13, 14, 'H'),
            (14, 15, 'H'),
            (15, 16, 'P'),
            (21, 22, 'P'),
            (22, 23, 'F'),
            (23, 24, 'H'),
            (24, 25, 'H'),
            (25, 26, 'P'),
            (13, 31, 'H'),
            (31, 32, 'P'),
            (32, 24, 'K'),
            (23, 41, 'H'),
            (41, 42, 'P'),
            (42, 14, 'K')
        ]
        iso_graph = nx.DiGraph()
        for edge in iso_edges:
            iso_graph.add_edge(edge[0], edge[1], typ=edge[2])

        self.assertTrue(nx.is_isomorphic(self.ereignisgraph, iso_graph), 'isomorphic graph')

        types = {'Ab': 0, 'An': 0, 'E': 0, 'K': 0, 'F': 0}
        expected_types = {'Ab': 6, 'An': 6, 'E': 0, 'K': 2, 'F': 2}
        for node, typ in self.ereignisgraph.nodes(data='typ'):
            types[typ] += 1
        self.assertDictEqual(types, expected_types, "Knotentypen")

        types = {'P': 0, 'H': 0, 'E': 0, 'K': 0, 'F': 0}
        expected_types = {'P': 6, 'H': 6, 'E': 0, 'K': 2, 'F': 2}
        for u, v, typ in self.ereignisgraph.edges(data='typ'):
            types[typ] += 1
        self.assertDictEqual(types, expected_types, "Kantentypen")


if __name__ == '__main__':
    unittest.main()
