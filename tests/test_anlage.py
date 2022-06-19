import unittest
import networkx as nx
import anlage


class TestAnlage(unittest.TestCase):
    def make_demo_graph(self):
        g = nx.Graph()

        g.add_node('E1', typ=6)
        g.add_node('A1', typ=7)
        g.add_node('H1', typ=5)
        g.add_node('B1', typ=5)
        g.add_node('B2', typ=5)
        g.add_node('B3', typ=5)
        g.add_node('E2', typ=6)
        g.add_node('A2', typ=7)

        g.add_node('S1', typ=2)
        g.add_node('S2', typ=2)
        g.add_node('S3', typ=2)
        g.add_node('S4', typ=2)
        g.add_node('S5', typ=2)
        g.add_node('S6', typ=2)
        g.add_node('S7', typ=2)
        g.add_node('S8', typ=2)
        g.add_node('S9', typ=2)
        g.add_node('S10', typ=2)

        g.add_edge('E1', 'S1', typ='gleis', distanz=1)
        g.add_edge('S1', 'H1', typ='gleis', distanz=1)
        g.add_edge('H1', 'S2', typ='gleis', distanz=1)
        g.add_edge('S2', 'S3', typ='gleis', distanz=1)
        g.add_edge('S3', 'B1', typ='gleis', distanz=1)
        g.add_edge('S3', 'B2', typ='gleis', distanz=1)

        g.add_edge('A1', 'S4', typ='gleis', distanz=1)
        g.add_edge('S4', 'H1', typ='gleis', distanz=1)
        g.add_edge('H1', 'S5', typ='gleis', distanz=1)
        g.add_edge('S5', 'B2', typ='gleis', distanz=1)
        g.add_edge('S5', 'B3', typ='gleis', distanz=1)

        g.add_edge('B1', 'B2', typ='bahnhof', distanz=0)
        g.add_edge('B1', 'B3', typ='bahnhof', distanz=0)
        g.add_edge('B2', 'B3', typ='bahnhof', distanz=0)

        g.add_edge('B1', 'S6', typ='gleis', distanz=1)
        g.add_edge('S6', 'S7', typ='gleis', distanz=1)
        g.add_edge('S7', 'A2', typ='gleis', distanz=1)
        g.add_edge('B2', 'S8', typ='gleis', distanz=1)
        g.add_edge('S8', 'S7', typ='gleis', distanz=1)

        g.add_edge('B3', 'S9', typ='gleis', distanz=1)
        g.add_edge('S9', 'S7', typ='gleis', distanz=1)
        g.add_edge('S9', 'S10', typ='gleis', distanz=1)
        g.add_edge('S10', 'E2', typ='gleis', distanz=1)

        return g

    def test_gleise_gruppieren(self):
        _anlage = anlage.Anlage(None)
        sg = self.make_demo_graph()
        bg = nx.subgraph(sg, ['H1', 'B1', 'B2', 'B3'])
        _anlage.signal_graph = sg
        _anlage.bahnsteig_graph = bg
        _anlage.gleise_gruppieren()
        ag = {'E1': {'E1'}, 'A1': {'A1'}, 'E2': {'E2'}, 'A2': {'A2'}}
        bg = {'H1': {'H1'}, 'B': {'B1', 'B2', 'B3'}}
        self.assertDictEqual(_anlage.anschlussgruppen, ag)
        self.assertDictEqual(_anlage.bahnsteiggruppen, bg)

    def test_update_gruppen_dict(self):
        _anlage = anlage.Anlage(None)
        _anlage.anschlussgruppen = {'A': {'A1', 'A2'}, 'B': {'B1', 'B2', 'B3'}}
        _anlage.bahnsteiggruppen = {'C': {'C1', 'C2'}, 'D': {'D1', 'D2', 'D3'}}
        _anlage._update_gruppen_dict()

        az = {'A1': 'A', 'A2': 'A', 'B1': 'B', 'B2': 'B', 'B3': 'B'}
        bz = {'C1': 'C', 'C2': 'C', 'D1': 'D', 'D2': 'D', 'D3': 'D'}
        gz = {**az, **bz}
        gg = {**_anlage.anschlussgruppen, **_anlage.bahnsteiggruppen}
        self.assertDictEqual(_anlage.anschlusszuordnung, az)
        self.assertDictEqual(_anlage.bahnsteigzuordnung, bz)
        self.assertDictEqual(_anlage.gleiszuordnung, gz)
        self.assertDictEqual(_anlage.gleisgruppen, gg)


if __name__ == '__main__':
    unittest.main()
