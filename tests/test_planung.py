import datetime
import unittest
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

import planung
from stsobj import ZugDetails, FahrplanZeile


def beispiel_zugliste(_planung: planung.Planung) -> Dict[int, planung.ZugDetailsPlanung]:
    zugliste = {}

    # gewoehnlicher zug mit halt an einer station.
    # befindet sich zwischen einfahrt A und erstem halt an gleis 1.
    zug = planung.ZugDetailsPlanung()
    zug.zid = 1
    zug.name = "Zug 1"
    zug.von = "A"
    zug.nach = "B"
    zug.gleis = zug.plangleis = "1"
    zug.sichtbar = True
    zugliste[zug.zid] = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "A"
    ziel.an = datetime.time(hour=9, minute=5)
    ziel.ab = datetime.time(hour=9, minute=5)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "1"
    ziel.mindestaufenthalt = 1
    ziel.an = datetime.time(hour=9, minute=10)
    ziel.ab = datetime.time(hour=9, minute=11)
    zug.fahrplan.append(ziel)
    zk = planung.PlanmaessigeAbfahrt(_planung)
    ziel.auto_korrektur = zk

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "B"
    ziel.an = datetime.time(hour=9, minute=17)
    ziel.ab = datetime.time(hour=9, minute=17)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug mit nummernwechsel an gleis 2. noch nicht eingefahren.
    zug = planung.ZugDetailsPlanung()
    zug.zid = 2
    zug.name = "Zug 2"
    zug.von = "A"
    zug.nach = "2"
    zug.gleis = zug.plangleis = "2"
    zug.sichtbar = False
    zugliste[zug.zid] = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "A"
    ziel.an = datetime.time(hour=10, minute=5)
    ziel.ab = datetime.time(hour=10, minute=5)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "2"
    ziel.mindestaufenthalt = 2  # richtungswechsel
    ziel.an = datetime.time(hour=10, minute=10)
    ziel.flags = "RE(3)"
    zug.fahrplan.append(ziel)
    zk = planung.Ersatzzug(_planung)
    ziel.auto_korrektur = zk
    anschluss = ziel

    # zug 3: ersatzzug von zug 2
    zug = planung.ZugDetailsPlanung()
    zug.zid = 3
    zug.name = "Zug 3"
    zug.von = "2"
    zug.nach = "B"
    zug.gleis = zug.plangleis = "2"
    zug.sichtbar = False
    zugliste[zug.zid] = zug
    ziel.ersatzzug = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "2"
    ziel.mindestaufenthalt = 0
    ziel.an = datetime.time(hour=10, minute=15)
    ziel.ab = datetime.time(hour=10, minute=16)
    zug.fahrplan.append(ziel)
    zk = planung.AnkunftAbwarten(_planung)
    zk.ursprung = anschluss
    ziel.auto_korrektur = zk

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "B"
    ziel.an = datetime.time(hour=10, minute=22)
    ziel.ab = datetime.time(hour=10, minute=22)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug 4 kuppelt mit zug 5
    zug = planung.ZugDetailsPlanung()
    zug.zid = 4
    zug.name = "Zug 4"
    zug.von = "A"
    zug.nach = "3"
    zug.gleis = zug.plangleis = "3"
    zug.sichtbar = False
    zugliste[zug.zid] = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "A"
    ziel.an = datetime.time(hour=11, minute=5)
    ziel.ab = datetime.time(hour=11, minute=5)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "3"
    ziel.mindestaufenthalt = 0
    ziel.an = datetime.time(hour=11, minute=10)
    ziel.flags = "K(5)"
    zug.fahrplan.append(ziel)
    zk = planung.Kupplung(_planung)
    ziel.auto_korrektur = zk
    anschluss = ziel

    # zug 5: kuppelt an zug 4 und faehrt dann weiter
    zug = planung.ZugDetailsPlanung()
    zug.zid = 5
    zug.name = "Zug 5"
    zug.von = "C"
    zug.nach = "B"
    zug.gleis = zug.plangleis = "3"
    zug.sichtbar = False
    zugliste[zug.zid] = zug
    ziel.kuppelzug = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "C"
    ziel.an = datetime.time(hour=11, minute=8)
    ziel.ab = datetime.time(hour=11, minute=8)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "3"
    ziel.mindestaufenthalt = 0
    ziel.an = datetime.time(hour=11, minute=14)
    ziel.ab = datetime.time(hour=11, minute=16)
    zug.fahrplan.append(ziel)
    zk = planung.AnkunftAbwarten(_planung)
    zk.ursprung = anschluss
    ziel.auto_korrektur = zk

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "B"
    ziel.an = datetime.time(hour=11, minute=21)
    ziel.ab = datetime.time(hour=11, minute=21)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug 6: fluegelt zug 7
    zug = planung.ZugDetailsPlanung()
    zug.zid = 6
    zug.name = "Zug 6"
    zug.von = "A"
    zug.nach = "B"
    zug.gleis = zug.plangleis = "4"
    zug.sichtbar = False
    zugliste[zug.zid] = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "A"
    ziel.an = datetime.time(hour=12, minute=8)
    ziel.ab = datetime.time(hour=12, minute=8)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "4"
    ziel.mindestaufenthalt = 0
    ziel.flags = "F(7)"
    ziel.an = datetime.time(hour=12, minute=14)
    ziel.ab = datetime.time(hour=12, minute=16)
    zug.fahrplan.append(ziel)
    zk = planung.Fluegelung(_planung)
    ziel.auto_korrektur = zk
    anschluss = ziel

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "B"
    ziel.an = datetime.time(hour=12, minute=21)
    ziel.ab = datetime.time(hour=12, minute=21)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug 7 fluegelt von zug 6
    zug = planung.ZugDetailsPlanung()
    zug.zid = 7
    zug.name = "Zug 7"
    zug.von = "4"
    zug.nach = "C"
    zug.gleis = zug.plangleis = "4"
    zug.sichtbar = False
    zugliste[zug.zid] = zug
    anschluss.fluegelzug = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "4"
    ziel.mindestaufenthalt = 0
    ziel.an = datetime.time(hour=12, minute=14)
    ziel.ab = datetime.time(hour=12, minute=18)
    zug.fahrplan.append(ziel)
    zk = planung.AbfahrtAbwarten(_planung)
    zk.ursprung = anschluss
    zk.wartezeit = 2
    ziel.auto_korrektur = zk

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "C"
    ziel.an = datetime.time(hour=12, minute=22)
    ziel.ab = datetime.time(hour=12, minute=22)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug 8: fluegelt zug 9. bispiel aus hamm
    zug = planung.ZugDetailsPlanung()
    zug.zid = 8
    zug.name = "ICE 940"
    zug.von = "Neubeckum"
    zug.nach = "Kamen"
    zug.gleis = zug.plangleis = "10"
    zug.sichtbar = False
    zugliste[zug.zid] = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "Neubeckum"
    ziel.an = datetime.time(hour=14, minute=48)
    ziel.ab = datetime.time(hour=14, minute=48)
    ziel.einfahrt = True
    zug.fahrplan.append(ziel)

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "10"
    ziel.mindestaufenthalt = 0
    ziel.flags = "F(9)"
    ziel.an = datetime.time(hour=14, minute=48)
    ziel.ab = datetime.time(hour=14, minute=52)
    zug.fahrplan.append(ziel)
    zk = planung.Fluegelung(_planung)
    ziel.auto_korrektur = zk
    anschluss = ziel

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "Kamen"
    ziel.an = datetime.time(hour=14, minute=52)
    ziel.ab = datetime.time(hour=14, minute=52)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    # zug 9 fluegelt von zug 8
    zug = planung.ZugDetailsPlanung()
    zug.zid = 9
    zug.name = "ICE 950"
    zug.von = ""
    zug.nach = "Unna"
    zug.gleis = zug.plangleis = "10"
    zug.sichtbar = False
    zugliste[zug.zid] = zug
    anschluss.fluegelzug = zug

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "10"
    ziel.mindestaufenthalt = 0
    ziel.an = datetime.time(hour=14, minute=48)
    ziel.ab = datetime.time(hour=14, minute=54)
    zug.fahrplan.append(ziel)
    zk = planung.AbfahrtAbwarten(_planung)
    zk.ursprung = anschluss
    zk.wartezeit = 2
    ziel.auto_korrektur = zk

    ziel = planung.ZugZielPlanung(zug)
    ziel.gleis = ziel.plan = "Unna"
    ziel.an = datetime.time(hour=14, minute=54)
    ziel.ab = datetime.time(hour=14, minute=54)
    ziel.ausfahrt = True
    zug.fahrplan.append(ziel)

    return zugliste


class TestZeitKorrektur(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.planung = planung.Planung()
        self.zugliste = beispiel_zugliste(self.planung)

    def test_planmaessige_abfahrt(self):
        zug = self.zugliste[1]
        ziel = zug.fahrplan[1]

        ziel.verspaetung_an = 0
        ziel.auto_korrektur.anwenden(zug, ziel)
        self.assertEqual(ziel.verspaetung_ab, 0)

        ziel.verspaetung_an = 3
        ziel.auto_korrektur.anwenden(zug, ziel)
        self.assertEqual(ziel.verspaetung_ab, 3)

        ziel.verspaetung_an = 3
        ziel.ab = datetime.time(hour=9, minute=13)
        ziel.auto_korrektur.anwenden(zug, ziel)
        self.assertEqual(ziel.verspaetung_ab, 1)

        ziel.verspaetung_an = 3
        ziel.ab = datetime.time(hour=9, minute=16)
        ziel.auto_korrektur.anwenden(zug, ziel)
        self.assertEqual(ziel.verspaetung_ab, 0)

    def test_ersatzzug(self):
        zug1 = self.zugliste[2]
        ziel1 = zug1.fahrplan[-1]
        zug2 = self.zugliste[3]
        ziel2 = zug2.fahrplan[0]

        ziel1.verspaetung_an = 0
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 0)
        self.assertEqual(ziel1.ersatzzug.verspaetung, 0)
        self.assertEqual(ziel2.verspaetung_an, 0)
        self.assertEqual(ziel2.verspaetung_ab, 0)

        ziel1.verspaetung_an = 2
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 0)
        self.assertEqual(ziel1.ersatzzug.verspaetung, 0)
        self.assertEqual(ziel2.verspaetung_an, 0)
        self.assertEqual(ziel2.verspaetung_ab, 0)

        ziel1.verspaetung_an = 10
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 7)
        self.assertEqual(ziel1.ersatzzug.verspaetung, 7)
        self.assertEqual(ziel1.ersatzzug.fahrplan[0].verspaetung_an, 7)
        self.assertEqual(ziel1.ersatzzug.fahrplan[0].verspaetung_ab, 6)

    def test_kuppeln(self):
        zug1 = self.zugliste[4]
        zug2 = self.zugliste[5]
        ziel1 = zug1.fahrplan[-1]

        zug1.verspaetung = 5
        ziel1.verspaetung_an = 5
        zug2.verspaetung = 0
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(zug2.verspaetung, 0)
        self.assertEqual(zug2.fahrplan[0].verspaetung_an, 0)
        self.assertEqual(zug2.fahrplan[0].verspaetung_ab, 0)

        zug1.verspaetung = 10
        ziel1.verspaetung_an = 10
        zug2.verspaetung = 0
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(zug2.verspaetung, 0)
        self.assertEqual(zug2.fahrplan[1].verspaetung_an, 0)
        self.assertEqual(zug2.fahrplan[1].verspaetung_ab, 4)
        self.assertEqual(zug2.fahrplan[2].verspaetung_an, 4)

        zug1.verspaetung = 0
        ziel1.verspaetung_an = 0
        zug2.verspaetung = 8
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(zug2.verspaetung, 8)
        self.assertEqual(zug2.fahrplan[0].verspaetung_an, 8)
        self.assertEqual(zug2.fahrplan[0].verspaetung_ab, 8)
        self.assertEqual(zug2.fahrplan[1].verspaetung_an, 8)
        self.assertEqual(zug2.fahrplan[1].verspaetung_ab, 6)
        self.assertEqual(zug2.fahrplan[2].verspaetung_an, 6)

    def test_fluegeln(self):
        # ankunft zug 6: 12:14, abfahrt zug 6: 12:16, abfahrt zug 7: 12:18
        zug1 = self.zugliste[6]
        zug2 = self.zugliste[7]
        ziel1 = zug1.fahrplan[1]
        ziel2 = zug2.fahrplan[0]

        zug1.verspaetung = 10
        ziel1.verspaetung_an = 10
        zug2.verspaetung = 10
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 8)
        self.assertEqual(ziel2.verspaetung_an, 10)
        self.assertEqual(ziel2.verspaetung_ab, 8)
        self.assertEqual(zug2.verspaetung, 10)

        zug1.verspaetung = 1
        ziel1.verspaetung_an = 1
        zug2.verspaetung = 1
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 0)
        self.assertEqual(ziel2.verspaetung_an, 1)
        self.assertEqual(ziel2.verspaetung_ab, 0)
        self.assertEqual(zug2.verspaetung, 1)

    def test_fluegeln_hamm(self):
        zug1 = self.zugliste[8]
        zug2 = self.zugliste[9]
        ziel1 = zug1.fahrplan[1]
        ziel2 = zug2.fahrplan[0]

        zug1.verspaetung = 20
        zug2.verspaetung = 20
        ziel1.verspaetung_an = 20
        ziel1.auto_korrektur.anwenden(zug1, ziel1)
        self.assertEqual(ziel1.verspaetung_ab, 16)
        self.assertEqual(ziel2.verspaetung_an, 20)
        self.assertEqual(ziel2.verspaetung_ab, 16)
        self.assertEqual(zug2.verspaetung, 20)


class TestPlanung(unittest.TestCase):
    def test_zugverspaetung_korrigieren(self):
        self.planung = planung.Planung()
        # bemerkung: die zugliste von self.planung wird nicht benoetigt!
        self.zugliste = beispiel_zugliste(self.planung)
        zug = self.zugliste[3]
        zug.ziel_index = 0
        zug.verspaetung = 3
        self.planung.zugverspaetung_korrigieren(zug)

        self.assertEqual(zug.fahrplan[0].verspaetung_an, 3)
        self.assertEqual(zug.fahrplan[0].verspaetung_ab, 3)
        self.assertEqual(zug.fahrplan[1].verspaetung_an, 3)
        self.assertEqual(zug.fahrplan[1].verspaetung_ab, 3)

        self.zugliste = beispiel_zugliste(self.planung)
        zug = self.zugliste[3]
        zug.ziel_index = 1
        zug.verspaetung = 5
        zug.sichtbar = True
        self.planung.zugverspaetung_korrigieren(zug)

        self.assertEqual(zug.fahrplan[0].verspaetung_an, 0)
        self.assertEqual(zug.fahrplan[0].verspaetung_ab, 5)
        self.assertEqual(zug.fahrplan[1].verspaetung_an, 5)
        self.assertEqual(zug.fahrplan[1].verspaetung_ab, 5)

    def test_verspaetungen_korrigieren_1(self):
        plg = planung.Planung()

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
        fpz1.auto_korrektur = planung.Ersatzzug(plg)
        zug1.fahrplan.append(fpz1)

        fpz2 = FahrplanZeile(zug2)
        fpz2.gleis = fpz2.plan = "1"
        fpz2.an = datetime.time(hour=9, minute=15)
        fpz2.ab = datetime.time(hour=9, minute=15)
        fpz2.auto_korrektur = planung.PlanmaessigeAbfahrt(plg)
        zug2.fahrplan.append(fpz2)

        zugliste = [zug1, zug2]
        plg.zuege_uebernehmen(zugliste)
        plg.verspaetungen_korrigieren()

        self.assertEqual(plg.zugliste[zug1.zid].verspaetung, 3)
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].verspaetung_ab, 0)
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].an, datetime.time(hour=9, minute=10))
        self.assertEqual(plg.zugliste[zug1.zid].fahrplan[1].ab, datetime.time(hour=9, minute=15))
        self.assertEqual(plg.zugliste[zug2.zid].verspaetung, 0)
        self.assertEqual(plg.zugliste[zug2.zid].fahrplan[1].verspaetung_ab, 0)
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
        self.assertEqual(5, plg.zugliste[zug1.zid].fahrplan[1].verspaetung_ab)
        self.assertEqual(datetime.time(hour=9, minute=10), plg.zugliste[zug1.zid].fahrplan[1].an)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug1.zid].fahrplan[1].ab)
        self.assertEqual(5, plg.zugliste[zug2.zid].verspaetung)
        self.assertEqual(5, plg.zugliste[zug2.zid].fahrplan[1].verspaetung_ab)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug2.zid].fahrplan[1].an)
        self.assertEqual(datetime.time(hour=9, minute=15), plg.zugliste[zug2.zid].fahrplan[1].ab)
