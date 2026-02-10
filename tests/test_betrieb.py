import unittest
from mock import Mock

from stskit.dispo.betrieb import Betrieb
from stskit.model.ereignisgraph import EreignisLabelType, EreignisGraphNode


class TestEreignisGraph(unittest.TestCase):
    def test_ereignis_label_finden(self):
        betrieb = Betrieb()
        betrieb.anlage = Mock()
        test_label = EreignisLabelType(zid=15, zeit=120, typ='An')
        test_data = EreignisGraphNode(zid=15, zeit=120, typ='An')
        label = betrieb._ereignis_label_finden(test_label, {'An', 'Ab'})
        self.assertEqual(label, test_label)
        label = betrieb._ereignis_label_finden(test_label, {'Ab'})
        self.assertIsNone(label)
        label = betrieb._ereignis_label_finden(test_data, {'An', 'Ab'})
        self.assertEqual(label, test_label)
