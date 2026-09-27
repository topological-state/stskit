import unittest

from stskit.model.bahnhofgraph import BahnhofElement, BahnsteigGraphNode, BahnhofGraph

BLT = BahnhofElement
Typ = BahnhofElement.Typ

class TestBahnhofGraph(unittest.TestCase):
    def setUp(self):
        self.graph = BahnhofGraph()
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A1a'), typ=Typ('Gl'), name='A1a', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A1b'), typ=Typ('Gl'), name='A1b', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A2a'), typ=Typ('Gl'), name='A2a', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A2b'), typ=Typ('Gl'), name='A2b', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A100'), typ=Typ('Gl'), name='A100', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'A101'), typ=Typ('Gl'), name='A101', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B1a'), typ=Typ('Gl'), name='B1a', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B1b'), typ=Typ('Gl'), name='B1b', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B2a'), typ=Typ('Gl'), name='B2a', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B2b'), typ=Typ('Gl'), name='B2b', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B100'), typ=Typ('Gl'), name='B100', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Gl'), 'B101'), typ=Typ('Gl'), name='B101', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'A1'), typ=Typ('Bs'), name='A1', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'A2'), typ=Typ('Bs'), name='A2', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'A100'), typ=Typ('Bs'), name='A100', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'A101'), typ=Typ('Bs'), name='A101', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'B1'), typ=Typ('Bs'), name='B1', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'B2'), typ=Typ('Bs'), name='B2', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'B100'), typ=Typ('Bs'), name='B100', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bs'), 'B101'), typ=Typ('Bs'), name='B101', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bft'), 'AHalle'), typ=Typ('Bft'), name='AHalle', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bft'), 'AFeld'), typ=Typ('Bft'), name='AFeld', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bft'), 'BHalle'), typ=Typ('Bft'), name='BHalle', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bft'), 'BFeld'), typ=Typ('Bft'), name='BFeld', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bf'), 'A'), typ=Typ('Bf'), name='A', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bf'), 'B'), typ=Typ('Bf'), name='B', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Bst'), 'Bf'), typ=Typ('Bst'), name='Bf', auto=True)
        self.graph.add_node(BahnhofElement(Typ('Stw'), 'Testwerk'), typ=Typ('Stw'), name='Testwerk', auto=True)

        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A1'), BahnhofElement(Typ('Gl'), 'A1a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A1'), BahnhofElement(Typ('Gl'), 'A1b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A2'), BahnhofElement(Typ('Gl'), 'A2a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A2'), BahnhofElement(Typ('Gl'), 'A2b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A100'), BahnhofElement(Typ('Gl'), 'A100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'A101'), BahnhofElement(Typ('Gl'), 'A101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B1'), BahnhofElement(Typ('Gl'), 'B1a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B1'), BahnhofElement(Typ('Gl'), 'B1b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B2'), BahnhofElement(Typ('Gl'), 'B2a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B2'), BahnhofElement(Typ('Gl'), 'B2b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B100'), BahnhofElement(Typ('Gl'), 'B100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bs'), 'B101'), BahnhofElement(Typ('Gl'), 'B101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'AHalle'), BahnhofElement(Typ('Bs'), 'A1'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'AHalle'), BahnhofElement(Typ('Bs'), 'A2'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'AFeld'), BahnhofElement(Typ('Bs'), 'A100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'AFeld'), BahnhofElement(Typ('Bs'), 'A101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'BHalle'), BahnhofElement(Typ('Bs'), 'B1'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'BHalle'), BahnhofElement(Typ('Bs'), 'B2'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'BFeld'), BahnhofElement(Typ('Bs'), 'B100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bft'), 'BFeld'), BahnhofElement(Typ('Bs'), 'B101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bf'), 'A'), BahnhofElement(Typ('Bft'), 'AHalle'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bf'), 'A'), BahnhofElement(Typ('Bft'), 'AFeld'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bf'), 'B'), BahnhofElement(Typ('Bft'), 'BHalle'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bf'), 'B'), BahnhofElement(Typ('Bft'), 'BFeld'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bst'), 'Bf'), BahnhofElement(Typ('Bf'), 'A'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Bst'), 'Bf'), BahnhofElement(Typ('Bf'), 'B'), typ='Hierarchie')
        self.graph.add_edge(BahnhofElement(Typ('Stw'), 'Testwerk'), BahnhofElement(Typ('Bst'), 'Bf'), typ='Hierarchie')

    def test_import_konfiguration_1(self):
        """
        Test: Bft AFeld Bahnhof B zuordnen
        """

        elemente = [
            {"name": "A101", "typ": Typ("Gl"), "stamm": "A101"},
            {"name": "A101", "typ": Typ("Bs"), "stamm": "AFeld"},
            {"name": "AFeld", "typ": Typ("Bft"), "stamm": "B", "auto": False},
            {"name": "B", "typ": "Bf"},
        ]
        self.graph.import_konfiguration(elemente)

        self.assertTrue(self.graph.has_edge(BLT(Typ("Bf"), "B"), BLT(Typ("Bft"), "AFeld")), "B -> AFeld")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bft"), "AFeld"), BLT(Typ("Bs"), "A101")), "AFeld -> A101")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bs"), "A101"), BLT(Typ("Gl"), "A101")), "A101 -> A101")
        self.assertFalse(self.graph.has_edge(BLT(Typ("Bf"), "A"), BLT(Typ("Bft"), "AFeld")), "A -> AFeld")

        self.assertFalse(self.graph.nodes[BLT(Typ("Bft"), "AFeld")]["auto"], "AFeld.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Bf"), "A")]["auto"], "A.auto")  # this fails but shouldn't
        self.assertTrue(self.graph.nodes[BLT(Typ("Bf"), "B")]["auto"], "B.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Bs"), "A101")]["auto"], "A101.auto")

    def test_import_konfiguration_2(self):
        """
        Test: Bft AHalle in Bft ANeu umbenennen
        """

        elemente = [
            {"name": "A1a", "typ": Typ("Gl"), "stamm": "A1"},
            {"name": "A1b", "typ": Typ("Gl"), "stamm": "A1"},
            {"name": "A2a", "typ": Typ("Gl"), "stamm": "A2"},
            {"name": "A2b", "typ": Typ("Gl"), "stamm": "A2"},
            {"name": "A1", "typ": Typ("Bs"), "stamm": "ANeu", "auto": False},
            {"name": "A2", "typ": Typ("Bs"), "stamm": "ANeu", "auto": False},
            {"name": "ANeu", "typ": Typ("Bft"), "stamm": "A", "auto": False},
            {"name": "A", "typ": Typ("Bf"), },
        ]
        self.graph.import_konfiguration(elemente)

        self.assertTrue(self.graph.has_node(BLT(Typ("Bft"), "ANeu")), "ANeu")
        self.assertFalse(self.graph.has_node(BLT(Typ("Bft"), "AHalle")), "AHalle")

        self.assertTrue(self.graph.has_edge(BLT(Typ("Bf"), "A"), BLT(Typ("Bft"), "ANeu")), "A -> ANeu")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bft"), "ANeu"), BLT(Typ("Bs"), "A1")), "ANeu -> A1")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bft"), "ANeu"), BLT(Typ("Bs"), "A2")), "ANeu -> A2")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bs"), "A1"), BLT(Typ("Gl"), "A1a")), "A1 -> A1a")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bs"), "A1"), BLT(Typ("Gl"), "A1b")), "A1 -> A1b")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bs"), "A2"), BLT(Typ("Gl"), "A2a")), "A2 -> A2a")
        self.assertTrue(self.graph.has_edge(BLT(Typ("Bs"), "A2"), BLT(Typ("Gl"), "A2b")), "A2 -> A2b")

        self.assertTrue(self.graph.nodes[BLT(Typ("Bf"), "A")]["auto"], "A.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Bf"), "B")]["auto"], "B.auto")
        self.assertFalse(self.graph.nodes[BLT(Typ("Bft"), "ANeu")]["auto"], "ANeu.auto")
        self.assertFalse(self.graph.nodes[BLT(Typ("Bs"), "A1")]["auto"], "A1.auto")
        self.assertFalse(self.graph.nodes[BLT(Typ("Bs"), "A2")]["auto"], "A2.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Gl"), "A1a")]["auto"], "A1a.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Gl"), "A1b")]["auto"], "A1b.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Gl"), "A2a")]["auto"], "A2a.auto")
        self.assertTrue(self.graph.nodes[BLT(Typ("Gl"), "A2b")]["auto"], "A2b.auto")

    def test_export_konfiguration(self):
        results = self.graph.export_konfiguration()
        elements = {BLT(Typ(e['typ']), e['name']): e for e in results}
        expected = {BLT(Typ('Gl'), 'A1a'),
                    BLT(Typ('Gl'), 'A1b'),
                    BLT(Typ('Gl'), 'A2a'),
                    BLT(Typ('Gl'), 'A2b'),
                    BLT(Typ('Gl'), 'A100'),
                    BLT(Typ('Gl'), 'A101'),
                    BLT(Typ('Gl'), 'B1a'),
                    BLT(Typ('Gl'), 'B1b'),
                    BLT(Typ('Gl'), 'B2a'),
                    BLT(Typ('Gl'), 'B2b'),
                    BLT(Typ('Gl'), 'B100'),
                    BLT(Typ('Gl'), 'B101'),
                    BLT(Typ('Bs'), 'A1'),
                    BLT(Typ('Bs'), 'A2'),
                    BLT(Typ('Bs'), 'A100'),
                    BLT(Typ('Bs'), 'A101'),
                    BLT(Typ('Bs'), 'B1'),
                    BLT(Typ('Bs'), 'B2'),
                    BLT(Typ('Bs'), 'B100'),
                    BLT(Typ('Bs'), 'B101'),
                    BLT(Typ('Bft'), 'AHalle'),
                    BLT(Typ('Bft'), 'AFeld'),
                    BLT(Typ('Bft'), 'BHalle'),
                    BLT(Typ('Bft'), 'BFeld'),
                    BLT(Typ('Bf'), 'A'),
                    BLT(Typ('Bf'), 'B')}
        self.assertEqual(set(elements.keys()), expected)

    def test_list_parents_no_ancestors(self):
        label = BahnhofElement(Typ("Stw"), "Testwerk")
        ancestors = list(self.graph.list_parents(label))
        self.assertListEqual(ancestors, [])

    def test_list_parents_one_ancestor(self):
        parent = BahnhofElement(Typ("Stw"), "Testwerk")
        gleis = BahnhofElement(Typ("Bst"), "Bf")
        ancestors = list(self.graph.list_parents(gleis))
        self.assertListEqual(ancestors, [parent])

    def test_list_parents_multiple_ancestors(self):
        gleis = BahnhofElement(Typ("Gl"), "A1a")
        expected = [ BahnhofElement(Typ('Bs'), 'A1'), BahnhofElement(Typ('Bft'), 'AHalle'), BahnhofElement(Typ('Bf'), 'A'), BahnhofElement(Typ('Bst'), 'Bf'), BahnhofElement(Typ('Stw'), 'Testwerk')]

        ancestors = list(self.graph.list_parents(gleis))
        self.assertListEqual(ancestors, expected)

    def test_list_parents_nonexistent_element(self):
        with self.assertRaises(KeyError) as context:
            _ = list(self.graph.list_parents(BahnhofElement(Typ("Gl"), "A3c")))

    def test_gleis_parents(self):
        expected = {
            BahnhofElement(Typ('Gl'), 'A1a'):  {'Bs': BahnhofElement(Typ('Bs'), 'A1'), 'Bft': BahnhofElement(Typ('Bft'), 'AHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'A1b'):  {'Bs': BahnhofElement(Typ('Bs'), 'A1'), 'Bft': BahnhofElement(Typ('Bft'), 'AHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'A2a'):  {'Bs': BahnhofElement(Typ('Bs'), 'A2'), 'Bft': BahnhofElement(Typ('Bft'), 'AHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'A2b'):  {'Bs': BahnhofElement(Typ('Bs'), 'A2'), 'Bft': BahnhofElement(Typ('Bft'), 'AHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'A100'): {'Bs': BahnhofElement(Typ('Bs'), 'A100'), 'Bft': BahnhofElement(Typ('Bft'), 'AFeld'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'A101'): {'Bs': BahnhofElement(Typ('Bs'), 'A101'), 'Bft': BahnhofElement(Typ('Bft'), 'AFeld'), 'Bf': BahnhofElement(Typ('Bf'), 'A'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B1a'):  {'Bs': BahnhofElement(Typ('Bs'), 'B1'), 'Bft': BahnhofElement(Typ('Bft'), 'BHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B1b'):  {'Bs': BahnhofElement(Typ('Bs'), 'B1'), 'Bft': BahnhofElement(Typ('Bft'), 'BHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B2a'):  {'Bs': BahnhofElement(Typ('Bs'), 'B2'), 'Bft': BahnhofElement(Typ('Bft'), 'BHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B2b'):  {'Bs': BahnhofElement(Typ('Bs'), 'B2'), 'Bft': BahnhofElement(Typ('Bft'), 'BHalle'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B100'): {'Bs': BahnhofElement(Typ('Bs'), 'B100'), 'Bft': BahnhofElement(Typ('Bft'), 'BFeld'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
            BahnhofElement(Typ('Gl'), 'B101'): {'Bs': BahnhofElement(Typ('Bs'), 'B101'), 'Bft': BahnhofElement(Typ('Bft'), 'BFeld'), 'Bf': BahnhofElement(Typ('Bf'), 'B'), 'Bst': BahnhofElement(Typ('Bst'), 'Bf'), 'Stw': BahnhofElement(Typ('Stw'), 'Testwerk')},
        }
        result = self.graph.gleis_parents()
        self.assertEqual(result, expected)

    def test_replace_parent(self):
        gleis = BahnhofElement(Typ('Gl'), 'A2a')
        old_parent = BahnhofElement(Typ('Bs'), 'A2')
        old_edge_data = self.graph.get_edge_data(old_parent, gleis)
        new_parent = BahnhofElement(Typ('Bs'), 'A1')
        grand_parent = BahnhofElement(Typ('Bft'), 'AHalle')

        # Verify original graph structure
        self.assertTrue(self.graph.has_node(old_parent))
        self.assertIn(gleis, self.graph.successors(old_parent))
        self.assertIn(old_parent, self.graph.predecessors(gleis))
        self.assertIn(old_parent, self.graph.successors(grand_parent))

        result = self.graph.replace_parent(gleis, new_parent, del_old_parent=True)

        # Verify that the new parent node exists and is connected to gleis
        self.assertTrue(self.graph.has_node(new_parent))
        self.assertIn(gleis, self.graph.successors(new_parent))
        self.assertIn(new_parent, self.graph.predecessors(gleis))
        self.assertIn(new_parent, self.graph.successors(grand_parent))

        # Verify that the edge data has been transferred correctly
        new_edge_data = self.graph.get_edge_data(new_parent, gleis)
        self.assertEqual(new_edge_data, old_edge_data)

        # Verify that the old parent node still exists
        self.assertTrue(self.graph.has_node(old_parent))

        # Verify that the result indicates success
        self.assertTrue(result)

        gleis = BahnhofElement(Typ('Gl'), 'A2b')
        old_parent = BahnhofElement(Typ('Bs'), 'A2')
        old_edge_data = self.graph.get_edge_data(old_parent, gleis)
        new_parent = BahnhofElement(Typ('Bs'), 'A1')
        result = self.graph.replace_parent(gleis, new_parent, del_old_parent=True)

        # Verify that the old parent node was removed
        self.assertFalse(self.graph.has_node(old_parent))

        # Verify that the result indicates success
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
