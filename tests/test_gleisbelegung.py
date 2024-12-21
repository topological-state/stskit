"""
Unit tests for the gleisbelegung module.
"""

from mock import Mock, patch
from unittest import TestCase, main

from stskit.plots.gleisbelegung import Gleisbelegung, Slot, SlotWarnung


class GleisbelegungTest(TestCase):
    """
    Unit tests for the Gleisbelegung class.
    """

    def setup_zugfolgewarnung(self, s1_zeit, s1_dauer, s2_zeit, s2_dauer, verbindung):
        zentrale = Mock()
        s1 = Mock(Slot)
        s1.zeit = s1_zeit
        s1.dauer = s1_dauer
        s2 = Mock(Slot)
        s2.zeit = s2_zeit
        s2.dauer = s2_dauer
        g = Gleisbelegung(zentrale)._zugfolgewarnung(s1, s2, verbindung)
        w: SlotWarnung = next(g)
        self.assertIsInstance(w, SlotWarnung)
        return w, s1, s2

    def test_ersatz_warnung(self):
        """
        _zugfolgewarnung bei Ersatz testen

        Setup:
            Das E-Flag steht in S1, im Zielgraph führt die E-Kante von S1 nach S2.

        Normalfall:
            S1 kommt vor S2 an.

        Verfrühter Ersatz:
            S1 und S2 berühren sich nicht.
        """

        # Normalfall, keine Anpassungen
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 10, 1010, 1, "E")
        self.assertEqual(w.status, "ersatz", "Normalfall: w.status")
        self.assertEqual(s1.zeit, 1000, "Normalfall: s1.zeit")
        self.assertEqual(s1.dauer, 10, "Normalfall: s1.dauer")
        self.assertEqual(s2.zeit, 1010, "Normalfall: s2.zeit")
        self.assertEqual(s2.dauer, 1, "Normalfall: s2.dauer")
        self.assertEqual(w.zeit, 1000, "Normalfall: w.zeit")
        self.assertEqual(w.dauer, 11, "Normalfall: w.dauer")

        # Lücke zwischen S1 und S2
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 5, 1010, 1, "E")
        self.assertEqual(w.status, "ersatz", "Lücke: w.status")
        self.assertEqual(s1.zeit, 1000, "Lücke: s1.zeit")
        self.assertEqual(s1.dauer, 5, "Lücke: s1.dauer")
        self.assertEqual(s2.zeit, 1005, "Lücke: s2.zeit")
        self.assertEqual(s2.dauer, 6, "Lücke: s2.dauer")
        self.assertEqual(w.zeit, 1000, "Lücke: w.zeit")
        self.assertEqual(w.dauer, 11, "Lücke: w.dauer")

        # Fehlerhafte Reihenfolge
        w, s1, s2 = self.setup_zugfolgewarnung(1010, 5, 1000, 1, "E")
        self.assertEqual(w.status, "ersatz", "Reihenfolge: w.status")
        self.assertEqual(s1.zeit, 1010, "Reihenfolge: s1.zeit")
        self.assertEqual(s1.dauer, 1, "Reihenfolge: s1.dauer")
        self.assertEqual(s2.zeit, 1011, "Reihenfolge: s2.zeit")
        self.assertEqual(s2.dauer, 1, "Reihenfolge: s2.dauer")
        self.assertEqual(w.zeit, 1010, "Reihenfolge: w.zeit")
        self.assertEqual(w.dauer, 2, "Reihenfolge: w.dauer")

        # Gleichzeitige Ankunft
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 5, 1000, 1, "E")
        self.assertEqual(w.status, "ersatz", "gleichzeitig: w.status")
        self.assertEqual(s1.zeit, 1000, "gleichzeitig: s1.zeit")
        self.assertEqual(s1.dauer, 1, "gleichzeitig: s1.dauer")
        self.assertEqual(s2.zeit, 1001, "gleichzeitig: s2.zeit")
        self.assertEqual(s2.dauer, 1, "gleichzeitig: s2.dauer")
        self.assertEqual(w.zeit, 1000, "gleichzeitig: w.zeit")
        self.assertEqual(w.dauer, 2, "gleichzeitig: w.dauer")

    def test_fluegeln_warnung(self):
        """
        _zugfolgewarnung bei Flügelvorgang testen

        Setup:
            Das F-Flag steht in S1, im Zielgraph führt die F-Kante von S1 nach S2.

        Normalfall:
            S1 kommt vor S2 an.
            S1 fährt vor S2 ab.
            S1 und S2 überlappen sich entsprechend.

        Verfrühter Vorgang:
            S1 und S2 berühren sich nicht.
        """

        # Normalfall, keine Anpassungen
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 10, 1005, 10, "F")
        self.assertEqual(w.status, "flügeln", "Normalfall: w.status")
        self.assertEqual(s1.zeit, 1000, "Normalfall: s1.zeit")
        self.assertEqual(s1.dauer, 10, "Normalfall: s1.dauer")
        self.assertEqual(s2.zeit, 1005, "Normalfall: s2.zeit")
        self.assertEqual(s2.dauer, 10, "Normalfall: s2.dauer")
        self.assertEqual(w.zeit, 1000, "Normalfall: w.zeit")
        self.assertEqual(w.dauer, 15, "Normalfall: w.dauer")

        # Lücke zwischen S1 und S2
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 2, 1005, 10, "F")
        self.assertEqual(w.status, "flügeln", "Lücke: w.status")
        self.assertEqual(s1.zeit, 1000, "Lücke: s1.zeit")
        self.assertEqual(s1.dauer, 2, "Lücke: s1.dauer")
        self.assertEqual(s2.zeit, 1002, "Lücke: s2.zeit")
        self.assertEqual(s2.dauer, 13, "Lücke: s2.dauer")
        self.assertEqual(w.zeit, 1000, "Lücke: w.zeit")
        self.assertEqual(w.dauer, 15, "Lücke: w.dauer")

        # Fehlerhafte Reihenfolge
        w, s1, s2 = self.setup_zugfolgewarnung(1010, 10, 1005, 10, "F")
        self.assertEqual(w.status, "flügeln", "Reihenfolge: w.status")
        self.assertEqual(s1.zeit, 1010, "Reihenfolge: s1.zeit")
        self.assertEqual(s1.dauer, 10, "Reihenfolge: s1.dauer")
        self.assertEqual(s2.zeit, 1011, "Reihenfolge: s2.zeit")
        self.assertEqual(s2.dauer, 10, "Reihenfolge: s2.dauer")
        self.assertEqual(w.zeit, 1010, "Reihenfolge: w.zeit")
        self.assertEqual(w.dauer, 11, "Reihenfolge: w.dauer")

        # Gleichzeitige Ankunft
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 10, 1000, 10, "F")
        self.assertEqual(w.status, "flügeln", "gleichzeitig: w.status")
        self.assertEqual(s1.zeit, 1000, "gleichzeitig: s1.zeit")
        self.assertEqual(s1.dauer, 10, "gleichzeitig: s1.dauer")
        self.assertEqual(s2.zeit, 1001, "gleichzeitig: s2.zeit")
        self.assertEqual(s2.dauer, 10, "gleichzeitig: s2.dauer")
        self.assertEqual(w.zeit, 1000, "gleichzeitig: w.zeit")
        self.assertEqual(w.dauer, 11, "gleichzeitig: w.dauer")

    def test_kuppeln_warnung(self):
        """
        _zugfolgewarnung auf Kuppelvorgang testen

        Setup:
            Das K-Flag steht in S1, im Zielgraph führt die K-Kante von S1 nach S2.
            Planmässig kommt S2 vor S1 an.
            Zug S1 endet beim Kuppeln.

        Normalfall:
            S2 kommt vor S1 an.
            S1 endet spätestens bei Abfahrt.

        Verspätungsfall: S1 kommt vor S2 an.
        """

        # Normalfall, keine Anpassungen
        w, s1, s2 = self.setup_zugfolgewarnung(1005, 2, 1000, 10, "K")
        self.assertEqual(w.status, "kuppeln", "Normalfall: w.status")
        self.assertEqual(s1.zeit, 1005, "Normalfall: s1.zeit")
        self.assertEqual(s1.dauer, 2, "Normalfall: s1.dauer")
        self.assertEqual(s2.zeit, 1000, "Normalfall: s2.zeit")
        self.assertEqual(s2.dauer, 10, "Normalfall: s2.dauer")
        self.assertEqual(w.zeit, 1000, "Normalfall: w.zeit")
        self.assertEqual(w.dauer, 10, "Normalfall: w.dauer")

        # S1 verspätet
        w, s1, s2 = self.setup_zugfolgewarnung(1020, 2, 1000, 10, "K")
        self.assertEqual(w.status, "kuppeln", "S1 verspätet: w.status")
        self.assertEqual(s1.zeit, 1020, "S1 verspätet: s1.zeit")
        self.assertEqual(s1.dauer, 2, "S1 verspätet: s1.dauer")
        self.assertEqual(s2.zeit, 1000, "S1 verspätet: s2.zeit")
        self.assertEqual(s2.dauer, 22, "S1 verspätet: s2.dauer")
        self.assertEqual(w.zeit, 1000, "S1 verspätet: w.zeit")
        self.assertEqual(w.dauer, 22, "S1 verspätet: w.dauer")

        # S2 verspätet, falsche Reihenfolge
        w, s1, s2 = self.setup_zugfolgewarnung(1005, 2, 1010, 2, "K")
        self.assertEqual(w.status, "kuppeln-reihenfolge", "S2 verspätet: w.status")
        self.assertEqual(s1.zeit, 1005, "S2 verspätet: s1.zeit")
        self.assertEqual(s1.dauer, 5, "S2 verspätet: s1.dauer")
        self.assertEqual(s2.zeit, 1010, "S2 verspätet: s2.zeit")
        self.assertEqual(s2.dauer, 2, "S2 verspätet: s2.dauer")
        self.assertEqual(w.zeit, 1005, "S2 verspätet: w.zeit")
        self.assertEqual(w.dauer, 7, "S2 verspätet: w.dauer")

        # Grenzfall, gleichzeitige Ankunft
        w, s1, s2 = self.setup_zugfolgewarnung(1000, 2, 1000, 10, "K")
        self.assertEqual(w.status, "kuppeln-reihenfolge", "gleichzeitige Ankunft: w.status")
        self.assertEqual(s1.zeit, 1001, "gleichzeitige Ankunft: s1.zeit")
        self.assertEqual(s1.dauer, 2, "gleichzeitige Ankunft: s1.dauer")
        self.assertEqual(s2.zeit, 1000, "gleichzeitige Ankunft: s2.zeit")
        self.assertEqual(s2.dauer, 10, "gleichzeitige Ankunft: s2.dauer")
        self.assertEqual(w.zeit, 1000, "gleichzeitige Ankunft: w.zeit")
        self.assertEqual(w.dauer, 10, "gleichzeitige Ankunft: w.dauer")


if __name__ == '__main__':
    main()
