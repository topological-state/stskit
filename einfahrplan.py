import numpy as np
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import time_to_minutes, Knoten
from slotgrafik import Slot, SlotWindow


class EinfahrtenWindow(SlotWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("einfahrten")
        self.zeitfenster_voraus = 30
        self.zeitfenster_zurueck = 0

    def slots_erstellen(self) -> Generator[Slot, None, None]:
        for knoten in self.client.wege_nach_typ[Knoten.TYP_NUMMER['Einfahrt']]:
            gleis = knoten.name
            if not gleis:
                continue

            for zug in knoten.zuege:
                if not zug.sichtbar:
                    try:
                        planzeile = zug.fahrplan[0]
                        slot = Slot(zug, planzeile, zug.von)
                        slot.zeit = time_to_minutes(planzeile.an) + zug.verspaetung
                        slot.dauer = 1
                        korrektur = self.auswertung.fahrzeiten.get_fahrzeit(zug.von, planzeile.gleis) / 60
                        if not np.isnan(korrektur):
                            slot.zeit = slot.zeit - round(korrektur)
                    except (AttributeError, IndexError):
                        pass
                    else:
                        yield slot

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
