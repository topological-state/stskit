import unittest
import networkx as nx
import stskit.dispo.anlage as anlage


class TestBahnhofGraph(unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.maxDiff = None

        self.gleis_konfig = {
            'A': {
                'Aa': {
                    'Aa1': {'Aa1a', 'Aa1b'},
                    'Aa2': {'Aa2a', 'Aa2b'}
                },
                'Ab': {
                    'Ab1': {'Ab1a'}
                }
            },
            'B': {
                'Ba': {
                    'Ba1': {'Ba1a', 'Ba1b'}
                }
            }
        }

        self.anschluss_konfig = {
            'A': {'A1', 'A2'},
            'B': {'B1'}
        }

        self.bahnhof_konfig = {
            ('Gl', 'Aa1a'): ('A', 'Aa', 'Aa1'),
            ('Gl', 'Aa1b'): ('A', 'Aa', 'Aa1'),
            ('Gl', 'Aa2a'): ('A', 'Aa', 'Aa2'),
            ('Gl', 'Aa2b'): ('A', 'Aa', 'Aa2'),
            ('Gl', 'Ab1a'): ('A', 'Ab', 'Ab1'),
            ('Gl', 'Ba1a'): ('B', 'Ba', 'Ba1'),
            ('Gl', 'Ba1b'): ('B', 'Ba', 'Ba1'),
            ('Agl', 'A1'): ('A',),
            ('Agl', 'A2'): ('A',),
            ('Agl', 'B1'): ('B',)
        }

        alg = anlage.Anlage()

        # original bahnsteiggraph

        alg.bahnsteiggraph.add_node('Aa1a', typ='Gl', name='Aa1a')
        alg.bahnsteiggraph.add_node('Aa1b', typ='Gl', name='Aa1b')
        alg.bahnsteiggraph.add_node('Aa2a', typ='Gl', name='Aa2a')
        alg.bahnsteiggraph.add_node('Aa2b', typ='Gl', name='Aa2b')
        alg.bahnsteiggraph.add_node('Ab1a', typ='Gl', name='Ab1a')
        alg.bahnsteiggraph.add_node('Ba1a', typ='Gl', name='Ba1a')
        alg.bahnsteiggraph.add_node('Ba1b', typ='Gl', name='Ba1b')

        alg.bahnsteiggraph.add_edge('Aa1a', 'Aa1b', typ='Nachbar', distanz=0)
        alg.bahnsteiggraph.add_edge('Aa1a', 'Aa2a', typ='Nachbar', distanz=0)
        alg.bahnsteiggraph.add_edge('Aa1a', 'Aa2b', typ='Nachbar', distanz=0)
        alg.bahnsteiggraph.add_edge('Ba1a', 'Ba1b', typ='Nachbar', distanz=0)

        # original signalgraph (minimal)
        alg.signalgraph.add_node('A1', typ=6, name='A1', enr=21)
        alg.signalgraph.add_node('A2', typ=7, name='A2', enr=22)
        alg.signalgraph.add_node('B1', typ=6, name='B1', enr=31)
        alg.signalgraph.add_node('B1', typ=7, name='B1', enr=32)

        # bahnhofgraph aus original bahnsteig- und signalgraphen
        alg.bahnhofgraph.add_node(('Gl', 'Aa1a'), typ='Gl', name='Aa1a', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Aa1b'), typ='Gl', name='Aa1b', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Aa2a'), typ='Gl', name='Aa2a', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Aa2b'), typ='Gl', name='Aa2b', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Ab1a'), typ='Gl', name='Ab1a', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Ba1a'), typ='Gl', name='Ba1a', auto=True)
        alg.bahnhofgraph.add_node(('Gl', 'Ba1b'), typ='Gl', name='Ba1b', auto=True)

        alg.bahnhofgraph.add_node(('Bs', 'Aa1'), typ='Bs', name='Aa1', auto=True)
        alg.bahnhofgraph.add_node(('Bs', 'Aa2'), typ='Bs', name='Aa2', auto=True)
        alg.bahnhofgraph.add_node(('Bs', 'Ab1'), typ='Bs', name='Ab1', auto=True)
        alg.bahnhofgraph.add_node(('Bs', 'Ba1'), typ='Bs', name='Ba1', auto=True)
        alg.bahnhofgraph.add_node(('Bft', 'Aa1'), typ='Bft', name='Aa1', auto=True)
        alg.bahnhofgraph.add_node(('Bft', 'Ab1'), typ='Bft', name='Ab1', auto=True)
        alg.bahnhofgraph.add_node(('Bft', 'Ba1'), typ='Bft', name='Ba1', auto=True)
        alg.bahnhofgraph.add_node(('Bf', 'Aa'), typ='Bf', name='Aa', auto=True)
        alg.bahnhofgraph.add_node(('Bf', 'Ab'), typ='Bf', name='Ab', auto=True)
        alg.bahnhofgraph.add_node(('Bf', 'Ba'), typ='Bf', name='Ba', auto=True)

        alg.bahnhofgraph.add_edge(('Bf', 'Aa'), ('Bft', 'Aa1'), typ='Bf', auto=True)
        alg.bahnhofgraph.add_edge(('Bf', 'Ab'), ('Bft', 'Ab1'), typ='Bf', auto=True)
        alg.bahnhofgraph.add_edge(('Bf', 'Ba'), ('Bft', 'Ba1'), typ='Bf', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Aa1'), ('Bs', 'Aa1'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Aa1'), ('Bs', 'Aa1'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Aa1'), ('Bs', 'Aa2'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Aa1'), ('Bs', 'Aa2'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Ab1'), ('Bs', 'Ab1'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Ba1'), ('Bs', 'Ba1'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bft', 'Ba1'), ('Bs', 'Ba1'), typ='Bft', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Aa1'), ('Gl', 'Aa1a'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Aa1'), ('Gl', 'Aa1b'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Aa2'), ('Gl', 'Aa2a'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Aa2'), ('Gl', 'Aa2b'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Ab1'), ('Gl', 'Ab1a'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Ba1'), ('Gl', 'Ba1a'), typ='Bs', auto=True)
        alg.bahnhofgraph.add_edge(('Bs', 'Ba1'), ('Gl', 'Ba1b'), typ='Bs', auto=True)

        alg.bahnhofgraph.add_node(('Agl', 'A1'), typ='Agl', name='A1', auto=True, einfahrt=True, ausfahrt=False)
        alg.bahnhofgraph.add_node(('Agl', 'A2'), typ='Agl', name='A2', auto=True, einfahrt=False, ausfahrt=True)
        alg.bahnhofgraph.add_node(('Agl', 'B1'), typ='Agl', name='B1', auto=True, einfahrt=True, ausfahrt=True)

        alg.bahnhofgraph.add_node(('Anst', 'A'), typ='Anst', name='A', auto=True)
        alg.bahnhofgraph.add_node(('Anst', 'A'), typ='Anst', name='A', auto=True)
        alg.bahnhofgraph.add_node(('Anst', 'B'), typ='Anst', name='B', auto=True)

        alg.bahnhofgraph.add_edge(('Anst', 'A'), ('Agl', 'A1'), typ='Anst', auto=True)
        alg.bahnhofgraph.add_edge(('Anst', 'A'), ('Agl', 'A2'), typ='Anst', auto=True)
        alg.bahnhofgraph.add_edge(('Anst', 'B'), ('Agl', 'B1'), typ='Anst', auto=True)

        self.anlage = alg

    def test_bahnhofgraph_erstellen(self):
        expectedgraph = self.anlage.bahnhofgraph.copy()
        self.anlage.bahnhofgraph.clear()
        self.anlage.bahnhofgraph_erstellen()
        resultgraph = self.anlage.bahnhofgraph

        self.assertListEqual(sorted(expectedgraph.nodes), sorted(resultgraph.nodes))
        expected_edges = sorted([tuple(sorted([t[0], t[1]])) for t in nx.to_edgelist(expectedgraph)])
        result_edges = sorted([tuple(sorted([t[0], t[1]])) for t in nx.to_edgelist(resultgraph)])
        self.assertListEqual(result_edges, expected_edges)

        result_dict = dict(resultgraph.nodes(data='name', default='???'))
        expected_dict = dict(expectedgraph.nodes(data='name', default='???'))
        self.assertDictEqual(result_dict, expected_dict)

        result_dict = dict(resultgraph.nodes(data='typ', default='???'))
        expected_dict = dict(expectedgraph.nodes(data='typ', default='???'))
        self.assertDictEqual(result_dict, expected_dict)

    def test_bahnhofgraph_konfigurieren_1(self):
        """
        bahnhofgraph konfigurieren im idealfall: alle gleise sind korrekt konfiguriert
        """

        expected = [
            (('Bs', 'Aa1'), ('Gl', 'Aa1a')),
            (('Bs', 'Aa1'), ('Gl', 'Aa1b')),
            (('Bs', 'Aa2'), ('Gl', 'Aa2a')),
            (('Bs', 'Aa2'), ('Gl', 'Aa2b')),
            (('Bs', 'Ab1'), ('Gl', 'Ab1a')),
            (('Bs', 'Ba1'), ('Gl', 'Ba1a')),
            (('Bs', 'Ba1'), ('Gl', 'Ba1b')),

            (('Bft', 'Aa'), ('Bs', 'Aa1')),
            (('Bft', 'Aa'), ('Bs', 'Aa2')),
            (('Bft', 'Ab'), ('Bs', 'Ab1')),
            (('Bft', 'Ba'), ('Bs', 'Ba1')),

            (('Bf', 'A'), ('Bft', 'Aa')),
            (('Bf', 'A'), ('Bft', 'Ab')),
            (('Bf', 'B'), ('Bft', 'Ba')),

            (('Anst', 'A'), ('Agl', 'A1')),
            (('Anst', 'A'), ('Agl', 'A2')),
            (('Anst', 'B'), ('Agl', 'B1'))
        ]

        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = nx.to_edgelist(self.anlage.bahnhofgraph)

        result_edges = [tuple(sorted([t[0], t[1]])) for t in result]
        expected_edges = [tuple(sorted([t[0], t[1]])) for t in expected]
        self.assertListEqual(sorted(result_edges), sorted(expected_edges))

    def test_bahnhofgraph_konfigurieren_2(self):
        """
        bahnhofgraph konfigurieren, wenn sich die anlage geaendert hat

        gleise Aa2b, Ba1a und A1 sind nicht mehr vorhanden.
        gleise Ab1a und B1 sind neu.
        """

        expected = [
            (('Bs', 'Aa1'), ('Gl', 'Aa1a')),
            (('Bs', 'Aa1'), ('Gl', 'Aa1b')),
            (('Bs', 'Aa2'), ('Gl', 'Aa2a')),
            (('Bs', 'Ab1'), ('Gl', 'Ab1a')),
            (('Bs', 'Ba1'), ('Gl', 'Ba1b')),

            (('Bft', 'Aa'), ('Bs', 'Aa1')),
            (('Bft', 'Aa'), ('Bs', 'Aa2')),
            (('Bft', 'Ab1'), ('Bs', 'Ab1')),
            (('Bft', 'Ba'), ('Bs', 'Ba1')),

            (('Bf', 'A'), ('Bft', 'Aa')),
            (('Bf', 'Ab'), ('Bft', 'Ab1')),
            (('Bf', 'B'), ('Bft', 'Ba')),

            (('Anst', 'A'), ('Agl', 'A2')),
            (('Anst', 'B'), ('Agl', 'B1'))
        ]

        # konfigurierte gleise, die in der anlage nicht mehr vorhanden sind
        self.anlage.bahnhofgraph.remove_nodes_from(
            [
                ('Gl', 'Aa2b'),
                ('Gl', 'Ba1a'),
                ('Agl', 'A1')
            ]
        )

        # neue gleise in der anlage, die noch nicht konfiguriert sind
        del self.bahnhof_konfig[('Agl', 'B1')]
        del self.bahnhof_konfig[('Gl', 'Ab1a')]

        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = nx.to_edgelist(self.anlage.bahnhofgraph)

        result_edges = [tuple(sorted([t[0], t[1]])) for t in result]
        expected_edges = [tuple(sorted([t[0], t[1]])) for t in expected]
        self.assertListEqual(sorted(result_edges), sorted(expected_edges))

    def test_bahnhofgraph_konfig_umdrehen(self):
        result = anlage.bahnhofgraph_konfig_umdrehen(self.gleis_konfig, self.anschluss_konfig)
        self.assertDictEqual(result, self.bahnhof_konfig)

    def test_bahnhofgleise(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = sorted((gl for gl in self.anlage.bahnhofgraph.bahnhofgleise("A")))
        expected = sorted(['Aa1a', 'Aa1b', 'Aa2a', 'Aa2b', 'Ab1a'])
        self.assertListEqual(result, expected)

    def test_bahnhofteilgleise(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = sorted(self.anlage.bahnhofgraph.bahnhofteilgleise("Aa"))
        expected = sorted(['Aa1a', 'Aa1b', 'Aa2a', 'Aa2b'])
        self.assertListEqual(result, expected)

    def test_gleis_bahnhof(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = self.anlage.bahnhofgraph.gleis_bahnhof("Ab1a")
        expected = "A"
        self.assertEqual(result, expected)

    def test_gleis_bahnhofteil(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = self.anlage.bahnhofgraph.gleis_bahnhofteil("Ab1a")
        expected = "Ab"
        self.assertEqual(result, expected)

    def test_gleis_bahnsteig(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = self.anlage.bahnhofgraph.gleis_bahnsteig("Aa1b")
        expected = "Aa1"
        self.assertEqual(result, expected)

    def test_bahnhoefe(self):
        self.anlage.bahnhofgraph_konfigurieren(self.bahnhof_konfig)
        result = sorted(self.anlage.bahnhofgraph.bahnhoefe())
        expected = sorted(['A', 'B'])
        self.assertListEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
