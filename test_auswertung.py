import unittest
from auswertung import FahrzeitAuswertung


class TestFahrzeitAuswertung(unittest.TestCase):
    test_anlage = {'Bahnhof A': ['A1', 'A2'],
                   'Bahnhof B': ['B1', 'B2']}

    test_daten = {'von': ['A1', 'A1', 'B1'],
                  'nach': ['B1', 'B2', 'A1'],
                  'zeit': [11, 22, 12]}

    def test_add_fahrzeit(self):
        fa = FahrzeitAuswertung()
        fa.set_koordinaten(self.test_anlage)
        fa.add_fahrzeit("A1", "B1", 25)

        self.assertEqual(fa.fahrten.at["A1", "B1"], 1)
        self.assertEqual(fa.fahrten.at["A1", "B2"], 0)
        self.assertEqual(fa.fahrten.at["A2", "B1"], 0)
        self.assertEqual(fa.fahrten.at["A2", "B2"], 0)

        self.assertAlmostEqual(fa.summe.at["A1", "B1"], 25)
        self.assertAlmostEqual(fa.summe.at["A1", "B2"], 0)
        self.assertAlmostEqual(fa.summe.at["A2", "B1"], 0)
        self.assertAlmostEqual(fa.summe.at["A2", "B2"], 0)


if __name__ == '__main__':
    unittest.main()
