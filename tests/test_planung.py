import datetime
import unittest

import planung
from stsobj import ZugDetails, FahrplanZeile


class TestPlanung(unittest.TestCase):
    def test_verspaetungen_korrigieren_1(self):
        zug1 = ZugDetails()
        zug1.zid = 1
        zug1.name = "Zug 1"
        zug1.verspaetung = 3

        zug2 = ZugDetails()
        zug2.zid = 2
        zug2.name = "Zug 2"
        zug2.verspaetung = 3

        fpz1 = FahrplanZeile(zug1)
        fpz1.an = datetime.time(hour=9, minute=10)
        fpz1.ersatzzug = zug2
        zug1.fahrplan.append(fpz1)

        fpz2 = FahrplanZeile(zug2)
        fpz2.an = datetime.time(hour=9, minute=15)
        fpz2.ab = datetime.time(hour=9, minute=15)
        zug2.fahrplan.append(fpz2)

        zugliste = [zug1, zug2]
        planung.Planung.verspaetungen_korrigieren(zugliste)

        assert zug1.verspaetung == 3
        assert zug1.fahrplan[0].verspaetung == 0
        assert zug1.fahrplan[0].an == datetime.time(hour=9, minute=10)
        assert zug1.fahrplan[0].ab == datetime.time(hour=9, minute=15)
        assert zug2.verspaetung == 0
        assert zug2.fahrplan[0].verspaetung == 0
        assert zug2.fahrplan[0].an == datetime.time(hour=9, minute=15)
        assert zug2.fahrplan[0].ab == datetime.time(hour=9, minute=15)

    def test_verspaetungen_korrigieren_2(self):
        zug1 = ZugDetails()
        zug1.zid = 1
        zug1.name = "Zug 1"
        zug1.verspaetung = 10

        zug2 = ZugDetails()
        zug2.zid = 2
        zug2.name = "Zug 2"
        zug2.verspaetung = 10

        fpz1 = FahrplanZeile(zug1)
        fpz1.an = datetime.time(hour=9, minute=10)
        fpz1.ersatzzug = zug2
        zug1.fahrplan.append(fpz1)

        fpz2 = FahrplanZeile(zug2)
        fpz2.an = datetime.time(hour=9, minute=15)
        fpz2.ab = datetime.time(hour=9, minute=15)
        zug2.fahrplan.append(fpz2)

        zugliste = [zug1, zug2]
        planung.StsAuswertung.verspaetungen_korrigieren(zugliste)

        assert zug1.verspaetung == 10
        assert zug1.fahrplan[0].verspaetung == 5
        assert zug1.fahrplan[0].an == datetime.time(hour=9, minute=10)
        assert zug1.fahrplan[0].ab == datetime.time(hour=9, minute=15)
        assert zug2.verspaetung == 5
        assert zug2.fahrplan[0].verspaetung == 5
        assert zug2.fahrplan[0].an == datetime.time(hour=9, minute=15)
        assert zug2.fahrplan[0].ab == datetime.time(hour=9, minute=15)
