import unittest

from stskit.model.bahnhofgraph import BahnhofLabelType, BahnsteigGraphNode, BahnhofGraph

class TestBahnhofGraph(unittest.TestCase):
    def setUp(self):
        self.graph = BahnhofGraph()
        self.graph.add_node(BahnhofLabelType('Gl', 'A1a'), typ='Gl', name='A1a', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'A1b'), typ='Gl', name='A1b', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'A2a'), typ='Gl', name='A2a', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'A2b'), typ='Gl', name='A2b', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'A100'), typ='Gl', name='A100', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'A101'), typ='Gl', name='A101', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B1a'), typ='Gl', name='B1a', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B1b'), typ='Gl', name='B1b', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B2a'), typ='Gl', name='B2a', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B2b'), typ='Gl', name='B2b', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B100'), typ='Gl', name='B100', auto=True)
        self.graph.add_node(BahnhofLabelType('Gl', 'B101'), typ='Gl', name='B101', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'A1'), typ='Bs', name='A1', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'A2'), typ='Bs', name='A2', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'A100'), typ='Bs', name='A100', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'A101'), typ='Bs', name='A101', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'B1'), typ='Bs', name='B1', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'B2'), typ='Bs', name='B2', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'B100'), typ='Bs', name='B100', auto=True)
        self.graph.add_node(BahnhofLabelType('Bs', 'B101'), typ='Bs', name='B101', auto=True)
        self.graph.add_node(BahnhofLabelType('Bft', 'AHalle'), typ='Bft', name='AHalle', auto=True)
        self.graph.add_node(BahnhofLabelType('Bft', 'AFeld'), typ='Bft', name='AFeld', auto=True)
        self.graph.add_node(BahnhofLabelType('Bft', 'BHalle'), typ='Bft', name='BHalle', auto=True)
        self.graph.add_node(BahnhofLabelType('Bft', 'BFeld'), typ='Bft', name='BFeld', auto=True)
        self.graph.add_node(BahnhofLabelType('Bf', 'A'), typ='Bf', name='A', auto=True)
        self.graph.add_node(BahnhofLabelType('Bf', 'B'), typ='Bf', name='B', auto=True)
        self.graph.add_node(BahnhofLabelType('Bst', 'Bf'), typ='Bst', name='Bf', auto=True)
        self.graph.add_node(BahnhofLabelType('Stw', 'Testwerk'), typ='Stw', name='Testwerk', auto=True)

        self.graph.add_edge(BahnhofLabelType('Bs', 'A1'), BahnhofLabelType('Gl', 'A1a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'A1'), BahnhofLabelType('Gl', 'A1b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'A2'), BahnhofLabelType('Gl', 'A2a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'A2'), BahnhofLabelType('Gl', 'A2b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'A100'), BahnhofLabelType('Gl', 'A100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'A101'), BahnhofLabelType('Gl', 'A101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B1'), BahnhofLabelType('Gl', 'B1a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B1'), BahnhofLabelType('Gl', 'B1b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B2'), BahnhofLabelType('Gl', 'B2a'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B2'), BahnhofLabelType('Gl', 'B2b'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B100'), BahnhofLabelType('Gl', 'B100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bs', 'B101'), BahnhofLabelType('Gl', 'B101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'AHalle'), BahnhofLabelType('Bs', 'A1'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'AHalle'), BahnhofLabelType('Bs', 'A2'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'AFeld'), BahnhofLabelType('Bs', 'A100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'AFeld'), BahnhofLabelType('Bs', 'A101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'BHalle'), BahnhofLabelType('Bs', 'B1'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'BHalle'), BahnhofLabelType('Bs', 'B2'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'BFeld'), BahnhofLabelType('Bs', 'B100'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bft', 'BFeld'), BahnhofLabelType('Bs', 'B101'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bf', 'A'), BahnhofLabelType('Bft', 'AHalle'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bf', 'A'), BahnhofLabelType('Bft', 'AFeld'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bf', 'B'), BahnhofLabelType('Bft', 'BHalle'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bf', 'B'), BahnhofLabelType('Bft', 'BFeld'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bst', 'Bf'), BahnhofLabelType('Bf', 'A'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Bst', 'Bf'), BahnhofLabelType('Bf', 'B'), typ='Hierarchie')
        self.graph.add_edge(BahnhofLabelType('Stw', 'Testwerk'), BahnhofLabelType('Bst', 'Bf'), typ='Hierarchie')

    def test_list_parents_no_ancestors(self):
        label = BahnhofLabelType("Stw", "Testwerk")
        ancestors = list(self.graph.list_parents(label))
        self.assertListEqual(ancestors, [])

    def test_list_parents_one_ancestor(self):
        parent = BahnhofLabelType("Stw", "Testwerk")
        gleis = BahnhofLabelType("Bst", "Bf")
        ancestors = list(self.graph.list_parents(gleis))
        self.assertListEqual(ancestors, [parent])

    def test_list_parents_multiple_ancestors(self):
        gleis = BahnhofLabelType("Gl", "A1a")
        expected = [ BahnhofLabelType('Bs', 'A1'), BahnhofLabelType('Bft', 'AHalle'), BahnhofLabelType('Bf', 'A'), BahnhofLabelType('Bst', 'Bf'), BahnhofLabelType('Stw', 'Testwerk')]

        ancestors = list(self.graph.list_parents(gleis))
        self.assertListEqual(ancestors, expected)

    def test_list_parents_nonexistent_element(self):
        with self.assertRaises(KeyError) as context:
            _ = list(self.graph.list_parents(BahnhofLabelType("Gl", "A3c")))

    def test_replace_parent(self):
        gleis = BahnhofLabelType('Gl', 'A2a')
        old_parent = BahnhofLabelType('Bs', 'A2')
        old_edge_data = self.graph.get_edge_data(old_parent, gleis)
        new_parent = BahnhofLabelType('Bs', 'A1')
        grand_parent = BahnhofLabelType('Bft', 'AHalle')

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

        # Verify that the old label is returned
        self.assertEqual(result, old_parent)

        gleis = BahnhofLabelType('Gl', 'A2b')
        old_parent = BahnhofLabelType('Bs', 'A2')
        old_edge_data = self.graph.get_edge_data(old_parent, gleis)
        new_parent = BahnhofLabelType('Bs', 'A1')
        result = self.graph.replace_parent(gleis, new_parent, del_old_parent=True)

        # Verify that the old parent node was removed
        self.assertFalse(self.graph.has_node(old_parent))

if __name__ == '__main__':
    unittest.main()