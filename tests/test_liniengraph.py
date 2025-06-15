import unittest
from typing import List, Tuple, Union

from stskit.model.liniengraph import LinienGraph, LinienLabelType


class TestStreckenZeitachse(unittest.TestCase):
    def setUp(self):
        self.graph = LinienGraph()
        self.bf_A = LinienLabelType('Bf', 'A')
        self.bf_B = LinienLabelType('Bf', 'B')
        self.bf_C = LinienLabelType('Bf', 'C')
        self.bf_D = LinienLabelType('Bf', 'D')
        self.graph.add_edge(self.bf_A, self.bf_B, fahrzeit_manuell=5)
        self.graph.add_edge(self.bf_B, self.bf_C, fahrzeit_schnitt=10, fahrzeit_min=2)

    def test_strecken_zeitachse_basic(self):
        result = self.graph.strecken_zeitachse([self.bf_A, self.bf_B, self.bf_C])
        expected_result = [0.0, 5.0, 7.0]
        self.assertEqual(expected_result, result)

    def test_strecken_zeitachse_missing_attribute(self):
        result = self.graph.strecken_zeitachse([self.bf_A, self.bf_B, self.bf_C], parameter='fahrzeit_max')
        expected_result = [0.0, 5.0, 6.0]
        self.assertEqual(expected_result, result)

    def test_strecken_zeitachse_default_value(self):
        result = self.graph.strecken_zeitachse([self.bf_A, self.bf_B, self.bf_C])
        expected_result = [0.0, 5.0, 7.0]
        self.assertEqual(expected_result, result)

    def test_strecken_zeitachse_no_edges(self):
        result = self.graph.strecken_zeitachse([])
        expected_result = [0.0]
        self.assertEqual(expected_result, result)

    def test_strecken_zeitachse_missing_edge(self):
        result = self.graph.strecken_zeitachse([self.bf_A, self.bf_B, self.bf_D])
        expected_result = [0.0, 5.0, 6.0]
        self.assertEqual(expected_result, result)


if __name__ == '__main__':
    unittest.main()
