import datetime

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Set, Union

from model import AnlagenInfo, BahnsteigInfo, Knoten, ZugDetails, FahrplanZeile, Ereignis, time_to_seconds
from database import StsConfig


class FahrzeitAuswertung:
    """
    auswertungsklasse für fahrzeiten zwischen gleisen.

    die pandas-dataframes werden mit einem multiindex indiziert,
    wo der erste level der gleisname und der zweite level der gruppenname ist.
    messdaten werden per gleis hinzugefügt, können aber auch per gruppe ausgewertet werden.

    spalten: zielgleise
    zeilen: startgleise
    df.loc[start, ziel]
    df[ziel]
    df.loc[start]
    """
    def __init__(self):
        self.summe: Optional[pd.DataFrame] = None
        self.fahrten: Optional[pd.DataFrame] = None
        self.maximum: Optional[pd.DataFrame] = None
        self.minimum: Optional[pd.DataFrame] = None

    def set_koordinaten(self, koordinaten: Dict) -> None:
        tuples = []
        for gruppe, gleise in koordinaten.items():
            for gleis in gleise:
                tuples.append((gleis, gruppe))
        index = pd.MultiIndex.from_tuples(tuples, names=['Gleis', 'Gruppe'])

        self.summe = pd.DataFrame(data=0., index=index, columns=index, dtype=float)
        self.fahrten = pd.DataFrame(data=0, index=index, columns=index, dtype=int)
        self.maximum = pd.DataFrame(data=0, index=index, columns=index, dtype=float)
        self.minimum = pd.DataFrame(data=24*60, index=index, columns=index, dtype=float)

    def add_fahrzeit(self, start: str, ziel: str, fahrzeit: int) -> None:
        """
        fahrzeit-messpunkt zur statistik hinzufügen.

        :param start: name eines bahnsteig- oder einfahrtsgleises
        :param ziel: name eines bahnsteig- oder ausfahrtsgleises
        :param fahrzeit: minuten
        :return: None
        :raise KeyError wenn die relation nicht existiert.
        """
        self.summe.loc[start, ziel] += fahrzeit
        self.fahrten.loc[start, ziel] += 1
        if fahrzeit > self.maximum.loc[start, ziel]:
            self.maximum.loc[start, ziel] = fahrzeit
        if fahrzeit < self.minimum.loc[start, ziel]:
            self.minimum.loc[start, ziel] = fahrzeit

    def get_fahrzeit(self, start: str, ziel: str) -> Optional[int]:
        return round(self.summe.loc[start, ziel] / self.fahrten.loc[start, ziel])


class ZugAuswertung:
    def __init__(self):
        self.zugliste: Dict[int, ZugDetails] = dict()

    def zuege_uebernehmen(self, zuege: List[ZugDetails]):
        """
        züge in interne liste kopieren.

        bereits vorhandene züge werden aktualisiert,
        unbekannte werde in die liste aufgenommen.
        der fahrplan wird nicht übernommen.

        :param zuege:
        :return:
        """
        for zug in zuege:
            try:
                mein_zug = self.zugliste[zug.zid]
            except KeyError:
                mein_zug = ZugDetails()
                mein_zug.zid = zug.zid
                mein_zug.name = zug.name
                mein_zug.von = zug.von
                mein_zug.nach = zug.nach
                self.zugliste[mein_zug.zid] = mein_zug
            else:
                mein_zug.gleis = zug.gleis
                mein_zug.verspaetung = zug.verspaetung
                mein_zug.amgleis = zug.amgleis
                mein_zug.sichtbar = zug.sichtbar

    def ereignis_uebernehmen(self, ereignis: Ereignis) -> None:
        try:
            zug = self.zugliste[ereignis.zid]
        except KeyError:
            pass
        else:
            zug.verspaetung = ereignis.verspaetung
            zug.sichtbar = ereignis.sichtbar
            zug.gleis = ereignis.gleis
            zug.plangleis = ereignis.plangleis
            zug.amgleis = ereignis.amgleis
            getattr(self, ereignis.art)(zug, ereignis)

    def einfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        fpz = FahrplanZeile(zug)
        fpz.gleis = zug.von
        fpz.plan = zug.von
        fpz.flags = ""
        fpz.hinweistext = "einfahrt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def ausfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        fpz = FahrplanZeile(zug)
        fpz.gleis = zug.nach
        fpz.plan = zug.nach
        fpz.flags = ""
        fpz.hinweistext = "ausfahrt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def ankunft(self, zug: ZugDetails, ereignis: Ereignis):
        fpz = FahrplanZeile(zug)
        fpz.gleis = ereignis.gleis
        fpz.plan = ereignis.gleis
        fpz.flags = ""
        fpz.hinweistext = "ankunft"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def abfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        fpz = zug.find_fahrplanzeile(ereignis.gleis)
        if fpz:
            fpz.hinweistext = "abfahrt"
            fpz.ab = ereignis.zeit.time()

    def rothalt(self, zug: ZugDetails, ereignis: Ereignis):
        fpz = FahrplanZeile(zug)
        fpz.gleis = ""
        fpz.plan = ereignis.gleis
        fpz.flags = ""
        fpz.hinweistext = "rothalt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def wurdegruen(self, zug: ZugDetails, ereignis: Ereignis):
        try:
            fpz = zug.fahrplan[-1]
            if fpz.hinweistext == 'rothalt':
                fpz.hinweistext = "wurdegruen"
                fpz.ab = ereignis.zeit.time()
        except IndexError:
            pass


class StsAuswertung:
    def __init__(self, config: StsConfig):
        self.config: StsConfig = config
        self.fahrzeiten: FahrzeitAuswertung = FahrzeitAuswertung()
        self.zuege: ZugAuswertung = ZugAuswertung()
        self._update_koordinaten()

    def _update_koordinaten(self):
        wegpunkte = {**self.config.bahnsteigsgruppen,
                     **self.config.einfahrtsgruppen,
                     **self.config.ausfahrtsgruppen}
        self.fahrzeiten.set_koordinaten(wegpunkte)

    def zuege_uebernehmen(self, zuege: List[ZugDetails]):
        """
        neue zugdaten und fahrpläne übernehmen.

        kann mehrmals aufgerufen werden. nur neue züge werden übernommen.

        :param zuege:
        :return:
        """

        self.zuege.zuege_uebernehmen(zuege)

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        daten von einem ereignis in die datenbank aufnehmen.

        ereignisarten:
        {'einfahrt', 'ankunft', 'abfahrt', 'ausfahrt', 'rothalt', 'wurdegruen', 'kuppeln', 'fluegeln'}

        :param ereignis:
        :return:
        """

        self.zuege.ereignis_uebernehmen(ereignis)

        if ereignis.art in {'ankunft', 'ausfahrt'}:
            try:
                zug = self.zuege.zugliste[ereignis.zid]
            except KeyError:
                pass
            else:
                self.fahrzeit_auswerten(zug)
                self.rotzeit_auswerten(zug)

    def fahrzeit_auswerten(self, zug: ZugDetails):
        """
        fahrzeit zum letzten halt auswerten.

        diese funktion berechnet die fahrzeiten von jedem registrierten ankunftsereignis zum letzten.
        im fall von 3 ereignissen also:
        - einfahrt -> ankunft 3
        - ankunft 1 -> ankunft 3
        - ankunft 2 -> ankunft 3

        etwaige haltezeiten (auch ausserplanmässige) werden nicht eingerechnet.

        :param zug:
        :return:
        """
        ziel = None
        gesamt = 0
        an = 0
        for fpz in reversed(zug.fahrplan):
            if fpz.hinweistext == "rothalt" or fpz.hinweistext == "ankunft":
                # abfahrt oder wurdegruen fehlt - messung unbrauchbar
                break
            if ziel:
                start = fpz.gleis
                ab = time_to_seconds(fpz.ab)
                strecke = an - ab
                if strecke < 0:
                    strecke += 24 * 60 * 60
                gesamt = gesamt + strecke
                if start:
                    self.fahrzeiten.add_fahrzeit(start, ziel, gesamt)
            else:
                ziel = fpz.gleis
            an = time_to_seconds(fpz.an)

    def fahrzeit_schaetzen(self, zug: str, start: str, ziel: str) -> Optional[int]:
        """
        fahrzeit eines zuges von start zu ziel abschätzen.

        :param zug: zugname
        :param start: name des startpunkts (einfahrt oder bahnsteig)
        :param ziel: name des zielpunkts (ausfahrt oder bahnsteig)
        :return: geschätzte fahrzeit in minuten, oder None, falls eine schätzung unmöglich ist.
        """

        return self.fahrzeiten.get_fahrzeit(start, ziel)

    def rotzeit_auswerten(self, zug: ZugDetails):
        gesamt = 0
        for fpz in zug.fahrplan:
            if fpz.hinweistext == "wurdegruen":
                zeit = time_to_seconds(fpz.ab) - time_to_seconds(fpz.an)
                if zeit < 0:
                    zeit += 24 * 60 * 60
                gesamt += zeit

        setattr(zug, 'rotzeit', datetime.timedelta(seconds=gesamt))
