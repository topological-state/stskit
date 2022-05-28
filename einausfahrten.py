"""
slot-grafikfenster für einfahrten und ausfahrten.
"""

import logging
import numpy as np
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import time_to_minutes
from slotgrafik import Slot, SlotWindow
from planung import ZugDetailsPlanung, ZugZielPlanung

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class EinAusWindow(SlotWindow):
    """
    gemeinsamer vorfahr von EinfahrtenWindow und AusfahrtenWindow.
    """
    def __init__(self):
        super().__init__()
        self.zeitfenster_voraus = 30
        self.zeitfenster_zurueck = 0

    def slots_erstellen(self) -> Iterable[Slot]:
        for zug in self.planung.zugliste.values():
            try:
                slot = self.get_slot(zug)
            except KeyError:
                slot = None
            if slot is not None:
                yield slot

    def get_slot(self, zug: ZugDetailsPlanung) -> Optional[Slot]:
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


class EinfahrtenWindow(EinAusWindow):
    """
    fenster mit einer slot-darstellung der geplanten einfahrten.

    für die einfahrten werden die daten aus dem planung-modul verwendet.
    die einfahrtszeit steht im ersten fahrplaneintrag, wenn dieser den "einfahrt"-hinweis enthält.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("einfahrten")

    def get_slot(self, zug: ZugDetailsPlanung) -> Optional[Slot]:
        try:
            planzeile = zug.fahrplan[0]
            if planzeile.hinweistext == "einfahrt" and not zug.amgleis:
                slot = Slot(zug, planzeile, zug.von)
                slot.zeit = time_to_minutes(planzeile.an) + zug.verspaetung
                slot.dauer = 1
            else:
                slot = None
        except (AttributeError, IndexError):
            slot = None

        return slot


class AusfahrtenWindow(EinAusWindow):
    """
    fenster mit einer slot-darstellung der geplanten ausfahrten.

    für die ausfahrten werden die daten aus dem planung-modul verwendet.
    die ausfahrtszeit steht im letzten fahrplaneintrag, wenn dieser den "ausfahrt"-hinweis enthält.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ausfahrten")

    def get_slot(self, zug: ZugDetailsPlanung) -> Optional[Slot]:
        try:
            planzeile = zug.fahrplan[-1]
            if planzeile.hinweistext == "ausfahrt":
                slot = Slot(zug, planzeile, zug.nach)
                slot.zeit = time_to_minutes(planzeile.ab) + zug.verspaetung
                slot.dauer = 1
            else:
                slot = None
        except (AttributeError, IndexError):
            slot = None

        return slot
