import datetime
import unittest

import planung
from stsobj import ZugDetails, FahrplanZeile


class TestPlanung(unittest.TestCase):
    def test_verspaetungen_korrigieren_1(self):
        zug1 = ZugDetails()
        zug1.zid = 1
        zug1.name = "Zug 1"
        zug1.von = "A"
        zug1.nach = "B"
        zug1.gleis = zug1.plangleis = "1"
        zug1.verspaetung = 3

        zug2 = ZugDetails()
        zug2.zid = 2
        zug2.name = "Zug 2"
        zug2.von = "B"
        zug2.nach = "C"
        zug2.gleis = zug2.plangleis = "1"
        zug2.verspaetung = 3
        zug2.stammzug = zug1

        fpz1 = FahrplanZeile(zug1)
        fpz1.gleis = fpz1.plan = "1"
        fpz1.an = datetime.time(hour=9, minute=10)
        fpz1.flags = f"E({zug2.zid})"
        fpz1.ersatzzug = zug2
        zug1.fahrplan.append(fpz1)

        fpz2 = FahrplanZeile(zug2)
        fpz2.gleis = fpz2.plan = "1"
        fpz2.an = datetime.time(hour=9, minute=15)
        fpz2.ab = datetime.time(hour=9, minute=15)
        zug2.fahrplan.append(fpz2)

        zugliste = [zug1, zug2]

        plg = planung.Planung()
        plg.zuege_uebernehmen(zugliste)
        plg.verspaetungen_korrigieren()

        self.assertEqual(plg.zugliste[zug1.zid].verspaetung, 3)
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].verspaetung, 0)
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].an, datetime.time(hour=9, minute=10))
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].ab, datetime.time(hour=9, minute=15))
        self.assertEqual(plg.zugliste[zug2.zid].verspaetung, 0)
        self.assertEqual(plg.zugliste[zug2.zid].fahrplan[1].verspaetung, 0)
        self.assertEqual(plg.zugliste[zug2.zid].fahrplan[1].an, datetime.time(hour=9, minute=15))
        self.assertEqual(plg.zugliste[zug2.zid].fahrplan[1].ab, datetime.time(hour=9, minute=15))

    def test_verspaetungen_korrigieren_2(self):
        zug1 = ZugDetails()
        zug1.zid = 1
        zug1.name = "Zug 1"
        zug1.von = "A"
        zug1.nach = "B"
        zug1.gleis = "1"
        zug1.verspaetung = 10

        zug2 = ZugDetails()
        zug2.zid = 2
        zug2.name = "Zug 2"
        zug2.von = "B"
        zug2.nach = "C"
        zug2.gleis = "1"
        zug2.verspaetung = 10
        zug2.stammzug = zug1

        fpz1 = FahrplanZeile(zug1)
        fpz1.an = datetime.time(hour=9, minute=10)
        fpz1.flags = f"E({zug2.zid})"
        fpz1.ersatzzug = zug2
        zug1.fahrplan.append(fpz1)

        fpz2 = FahrplanZeile(zug2)
        fpz2.an = datetime.time(hour=9, minute=15)
        fpz2.ab = datetime.time(hour=9, minute=15)
        zug2.fahrplan.append(fpz2)

        zugliste = [zug1, zug2]
        plg = planung.Planung()
        plg.zuege_uebernehmen(zugliste)
        plg.verspaetungen_korrigieren()

        self.assertEqual(10, plg.zugliste[zug1.zid].verspaetung)
        self.assertEqual(5, plg.zugliste[zug1.zid].fahrplan[1].verspaetung)
        self.assertEqual(datetime.time(hour=9, minute=10), plg.zugliste[zug1.zid].fahrplan[1].an)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug1.zid].fahrplan[1].ab)
        self.assertEqual(5, plg.zugliste[zug2.zid].verspaetung)
        self.assertEqual(5, plg.zugliste[zug2.zid].fahrplan[1].verspaetung)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug2.zid].fahrplan[1].an)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug2.zid].fahrplan[1].ab)
