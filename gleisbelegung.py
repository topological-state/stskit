import itertools
import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import time_to_minutes, Knoten
from slotgrafik import Slot, SlotWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GleisbelegungWindow(SlotWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("gleisbelegung")
        self.zeitfenster_voraus = 55
        self.zeitfenster_zurueck = 5

    def slots_erstellen(self) -> Iterable[Slot]:
        for zug in self.client.zugliste.values():
            for planzeile in zug.fahrplan:
                if not planzeile.gleis:
                    continue

                slot = Slot(zug, planzeile, planzeile.gleis)
                slot.zeit = time_to_minutes(slot.plan.an) + zug.verspaetung
                try:
                    slot.dauer = max(1, time_to_minutes(slot.plan.ab) - time_to_minutes(slot.plan.an))
                    if zug.verspaetung < 0 and not slot.plan.durchfahrt():
                        slot.dauer -= zug.verspaetung
                    elif zug.verspaetung > 0 and slot.dauer >= 5:
                        slot.dauer = max(5, slot.dauer - slot.zug.verspaetung)
                except AttributeError:
                    slot.dauer = 1

                # ersatzzug anhängen
                if ersatzzug := planzeile.ersatzzug:
                    try:
                        ersatzzeit = time_to_minutes(ersatzzug.fahrplan[0].an)
                        slot.dauer = max(slot.dauer, ersatzzeit - slot.zeit)
                        ersatzzug.verspaetung = slot.zeit + slot.dauer - ersatzzeit
                    except IndexError:
                        slot.dauer = 1
                elif kuppelzug := planzeile.kuppelzug:
                    slot.kuppelzug = kuppelzug
                elif fluegelzug := planzeile.fluegelzug:
                    slot.kuppelzug = fluegelzug

                yield slot

    def konflikte_loesen(self, gleis: str, slots: List[Slot]) -> List[Slot]:
        for s1, s2 in itertools.permutations(slots, 2):
            if s1.kuppelzug is not None and s1.kuppelzug == s2.zug:
                self.kuppeln(s1, s2)
            elif s2.kuppelzug is not None and s2.kuppelzug == s1.zug:
                self.kuppeln(s2, s1)
            elif s1.zeit <= s2.zeit < s1.zeit + s1.dauer:
                s1.konflikte.append(s2)
                s2.konflikte.append(s1)

        return slots

    def kuppeln(self, s1: Slot, s2: Slot) -> None:
        s2.kuppelzug = s1.zug
        try:
            s2_an = time_to_minutes(s2.zug.fahrplan[0].an) + s2.zug.verspaetung
            if s2_an > s1.zeit:
                s1.dauer = s2_an - s1.zeit
        except IndexError:
            s1.dauer = 1
