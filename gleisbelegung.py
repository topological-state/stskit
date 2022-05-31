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
        for zug in self.planung.zugliste.values():
            try:
                verspaetung = zug.fahrplan[0].verspaetung
            except IndexError:
                continue
            if verspaetung is None:
                verspaetung = zug.verspaetung
                logger.warning(f"zug {zug.name} (zid {zug.zid}) hat keine detaillierten verspätungsangaben.")

            for planzeile in zug.fahrplan:
                try:
                    plan_an = time_to_minutes(planzeile.an)
                except AttributeError:
                    break
                try:
                    plan_ab = time_to_minutes(planzeile.ab)
                except AttributeError:
                    plan_ab = plan_an + 1
                verspaetung_neu = planzeile.verspaetung if planzeile.verspaetung is not None else verspaetung

                if planzeile.gleis and planzeile.hinweistext != "einfahrt" and planzeile.hinweistext != "ausfahrt":
                    slot = Slot(zug, planzeile, planzeile.gleis)
                    slot.zeit = plan_an + verspaetung
                    slot.dauer = max(1, plan_ab + verspaetung_neu - plan_an - verspaetung)

                    if planzeile.ersatzzug:
                        slot.verbindung = planzeile.ersatzzug
                        slot.verbindungsart = "E"
                    elif planzeile.kuppelzug:
                        slot.verbindung = planzeile.kuppelzug
                        slot.verbindungsart = "K"
                    elif planzeile.fluegelzug:
                        slot.verbindung = planzeile.fluegelzug
                        slot.verbindungsart = "F"

                    yield slot

                verspaetung = verspaetung_neu

    def konflikte_loesen(self, gleis: str, slots: List[Slot]) -> List[Slot]:
        for s1, s2 in itertools.permutations(slots, 2):
            if s1.verbindung is not None and s1.verbindung == s2.zug:
                self.verbinden(s1, s2)
            elif s2.verbindung is not None and s2.verbindung == s1.zug:
                self.verbinden(s2, s1)
            elif s1.zeit <= s2.zeit < s1.zeit + s1.dauer:
                s1.konflikte.append(s2)
                s2.konflikte.append(s1)

        return slots

    @staticmethod
    def verbinden(s1: Slot, s2: Slot) -> None:
        s2.verbindung = s1.zug
        s2.verbindungsart = s1.verbindungsart
        try:
            s2_zeile = s2.zug.find_fahrplanzeile(gleis=s1.gleis)
            s2_an = time_to_minutes(s2_zeile.an) + s2.zug.verspaetung
            if s2_an > s1.zeit:
                s1.dauer = s2_an - s1.zeit
            elif s1.zeit > s2_an:
                s2.dauer = s1.zeit - s2_an
        except AttributeError:
            pass
