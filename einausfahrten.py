"""
slot-grafikfenster für einfahrten und ausfahrten.
"""

import numpy as np
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import time_to_minutes, Knoten, ZugDetails, FahrplanZeile
from slotgrafik import Slot, SlotWindow


class KnotenWindow(SlotWindow):
    """
    gemeinsamer vorfahr von EinfahrtenWindow und AusfahrtenWindow.
    """
    def __init__(self):
        super().__init__()
        self.knoten_typ = ''
        self.zeitfenster_voraus = 30
        self.zeitfenster_zurueck = 0

    def slots_erstellen(self) -> Generator[Slot, None, None]:
        for knoten in self.client.wege_nach_typ[Knoten.TYP_NUMMER[self.knoten_typ]]:
            if not knoten.name:
                continue

            for zug in knoten.zuege:
                slot = self.get_slot(zug)
                if slot is not None:
                    yield slot

    def get_slot(self, zug: ZugDetails) -> Optional[Slot]:
        """
        slot-objekt für einen zug erstellen.

        :param zug:
        :return:
        """
        pass

    def konflikte_loesen(self, gleis: str, slots: List[Slot]) -> List[Slot]:
        slots.sort(key=lambda s: s.zeit)
        letzter = slots[0]
        frei = letzter.zeit + letzter.dauer
        for slot in slots[1:]:
            if slot.zeit < frei:
                slot.konflikte.append(letzter)
                letzter.konflikte.append(slot)
                slot.zeit = max(frei, slot.zeit)
                frei = slot.zeit + slot.dauer
                letzter = slot

        return slots


class EinfahrtenWindow(KnotenWindow):
    """
    fenster mit einer slot-darstellung der geplanten einfahrten.

    für die einfahrtszeit gibt es keine direkten plandaten vom simulator.
    die einfahrtszeit wird vom ersten fahrplaneintrag, der erwarteten fahrzeit dorthin sowie der aktuellen verspätung
    geschätzt, sofern erfahrungsdaten dazu vorhanden sind (siehe auswertungsmodul).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("einfahrten")
        self.knoten_typ = 'Einfahrt'

    def get_slot(self, zug: ZugDetails) -> Optional[Slot]:
        try:
            planzeile = zug.fahrplan[0]
            slot = Slot(zug, planzeile, zug.von)
            slot.zeit = time_to_minutes(planzeile.an) + zug.verspaetung
            slot.dauer = 1
            korrektur = self.auswertung.fahrzeiten.get_fahrzeit(zug.von, planzeile.gleis) / 60
            if not np.isnan(korrektur):
                slot.zeit = slot.zeit - round(korrektur)
        except (AttributeError, IndexError):
            slot = None

        return slot


class AusfahrtenWindow(KnotenWindow):
    """
    fenster mit einer slot-darstellung der geplanten ausfahrten.

    für die ausfahrtszeit gibt es keine direkten plandaten vom simulator.
    die ausfahrtszeit wird vom letzten fahrplaneintrag, der erwarteten fahrzeit dorthin sowie der aktuellen verspätung
    geschätzt, sofern erfahrungsdaten dazu vorhanden sind (siehe auswertungsmodul).

    achtung: sobald der zug seinen letzten fahrplanpunkt passiert hat,
    hat er keinen fahrplan mehr und verschwindet aus der grafik.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ausfahrten")
        self.knoten_typ = 'Ausfahrt'

    def get_slot(self, zug: ZugDetails) -> Optional[Slot]:
        try:
            planzeile = zug.fahrplan[-1]
            slot = Slot(zug, planzeile, zug.nach)
            slot.zeit = time_to_minutes(planzeile.ab) + zug.verspaetung
            slot.dauer = 1
            korrektur = self.auswertung.fahrzeiten.get_fahrzeit(planzeile.gleis, zug.nach) / 60
            if not np.isnan(korrektur):
                slot.zeit = slot.zeit - round(korrektur)
        except (AttributeError, IndexError):
            slot = None

        return slot
