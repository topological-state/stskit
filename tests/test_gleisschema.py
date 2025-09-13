import unittest
from stskit.model.gleisschema import Gleisschema


class TestAnlage(unittest.TestCase):
    def test_default_bahnhofname(self):
        """
        Test von stskit.utils.gleisnamen.default_bahnhofname anhand von Beispielen
        """

        tests = {'FSP503': 'FSP',
                 'NAH423b': 'NAH',
                 '6': 'Hbf',
                 '10C-D': 'Hbf',
                 'BSGB D73': 'BSGB',
                 'ZUE 12': 'ZUE',
                 'BR 1b': 'BR',
                 'Lie W10': 'Lie',
                 'Muntelier-L.': 'Muntelier-L.',
                 'VU3-5': 'VU',
                 'Isola della Scala 3G': 'Isola della Scala',
                 'Ma Wende R': 'Ma',
                 'Lie A1': 'Lie A1',
                 # unerwünschte Resultate
                 'R3': 'R',
                 'N': 'N'
                 }

        gleisschema = Gleisschema()
        gleisschema.stellwerk = 'Hbf'

        for gleis, bahnhof in tests.items():
            self.assertEqual(bahnhof, gleisschema.bahnhofname(gleis))

    def test_default_anschlussname(self):
        """
        Test von stskit.utils.gleisnamen.default_anschlussname anhand von Beispielen
        """

        tests = {'1-4 S': '1-4 S',
                 'BSRB 602': 'BSRB',
                 'B-Ost': 'B-Ost',
                 'BNBS Abst.': 'BNBS Abst.',
                 'Abst.2': 'Abst.',
                 'Gl. 18': 'Gl. 18',
                 '791': '791',
                 '308 A': '308 A',
                 '1Li': '1Li',
                 '307-309': '307-309',
                 'Chiasso SMN 304': 'Chiasso SMN',
                 'ZUE P11': 'ZUE P',
                 'BO124': 'BO',
                 'Villach Süd Gvbf 4': 'Villach Süd Gvbf',
                 'Leinde Fern': 'Leinde Fern'
                 }

        gleisschema = Gleisschema()

        for gleis, bahnhof in tests.items():
            self.assertEqual(bahnhof, gleisschema.anschlussname(gleis))

    
if __name__ == '__main__':
    unittest.main()
