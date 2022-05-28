import datetime
import logging
import numpy as np
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import ZugDetails, FahrplanZeile, Ereignis
from stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from auswertung import Auswertung


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZeitKorrektur():
    def __init__(self, planung: 'Planung'):
        super(self).__init__()
        self._planung = planung

    def anwenden(self, zug: 'ZugDetailsPlanung', plan: 'ZugZielPlanung', verspaetung: int):
        pass


class ManuelleVerspaetung(ZeitKorrektur):
    def __init__(self, planung: 'Planung'):
        super(self).__init__(planung)
        self.verspaetung: Optional[int] = None

    def anwenden(self, zug: 'ZugDetailsPlanung', plan: 'ZugZielPlanung', verspaetung: int):
        if self.verspaetung is not None:
            plan.verspaetung = self.verspaetung


class ZugAbwarten(ZeitKorrektur):
    def __init__(self, planung: 'Planung'):
        super(self).__init__(planung)
        self.referenz_zug: Optional['ZugDetailsPlanung'] = None
        self.referenz_plangleis: Optional[str] = None
        self.wartezeit: int = 0

    def anwenden(self, zug: 'ZugDetailsPlanung', plan: 'ZugZielPlanung', verspaetung: int):
        if self.referenz_zug is not None:
            ref_plan = self.referenz_zug.find_fahrplanzeile(plan=self.referenz_plangleis)
            ref_ab = ref_plan.ab + ref_plan.verspaetung
            plan.verspaetung = ref_ab - plan.ab + self.wartezeit


class ZugDetailsPlanung(ZugDetails):
    """
    ZugDetails für das planungsmodul

    dies ist eine unterklasse von ZugDetails, wie sie vom planungsmodul verwendet wird.
    im planungsmodul haben einige attribute eine geänderte bedeutung.
    insbesondere bleibt der fahrplan vollständig (abgefahrene ziele werden nicht gelöscht)
    und enthält auch die ein- und ausfahrten als erste/letzte zeile
    (ausser der zug beginnt oder endet im stellwerk).

    wenn der zug neu angelegt wird, übernimmt die assign_zug_details-methode die daten vom PluginClient.
    die update_zug_details-methode aktualisert die veränderlichen attribute, z.b. gleis, verspätung etc.
    """
    def __init__(self):
        super().__init__()

    @property
    def einfahrtszeit(self) -> datetime.time:
        return self.fahrplan[0].ab

    @property
    def ausfahrtszeit(self) -> datetime.time:
        return self.fahrplan[-1].an

    def assign_zug_details(self, zug: ZugDetails):
        """
        objekt mit stammdaten vom PluginClient initialisieren.

        unterschiede zum original-ZugDetails:
        - ein- und ausfahrtsgleise werden als separate fahrplanzeile am anfang bzw. ende der liste eingefügt
          und mit dem hinweistext 'einfahrt' bzw. 'ausfahrt' markiert.
          ankunfts- und abfahrtszeiten werden dem benachbarten fahrplanziel gleichgesetzt
          (um später vom planungsmodul korrigiert zu werden).
        - der text 'Gleis', wenn der zug im stellwerk beginnt oder endet, wird aus dem von/nach entfernt.
          das gleis befindet sich bereits im fahrplan, es wird keine zusätzliche ein-/ausfahrt-zeile eingefügt.

        :param zug: original-ZugDetails-objekt vom PluginClient.zugliste.
        :return: None
        """
        self.zid = zug.zid
        self.name = zug.name
        self.von = zug.von.replace("Gleis ", "") if zug.von else ""
        self.nach = zug.nach.replace("Gleis ", "") if zug.nach else ""
        self.hinweistext = zug.hinweistext

        self.fahrplan = []
        if not self.sichtbar and self.von and not zug.von.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            ziel.plan = ziel.gleis = self.von
            try:
                ziel.ab = ziel.an = zug.fahrplan[0].an
            except IndexError:
                pass
            ziel.hinweistext = "einfahrt"
            self.fahrplan.append(ziel)
        for zeile in zug.fahrplan:
            ziel = ZugZielPlanung(self)
            ziel.assign_fahrplan_zeile(zeile)
            self.fahrplan.append(ziel)
        if self.nach and not zug.nach.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            ziel.plan = ziel.gleis = self.nach
            try:
                ziel.ab = ziel.an = zug.fahrplan[-1].ab
            except IndexError:
                pass
            ziel.hinweistext = "ausfahrt"
            self.fahrplan.append(ziel)

    def update_zug_details(self, zug: ZugDetails):
        """
        aktualisiert die veränderlichen attribute vom PluginClient

        die folgenden attribute werden aktualisert, alle anderen bleiben unverändert.
        gleis, plangleis, amgleis, sichtbar, verspaetung, usertext, usertextsender, fahrplanzeile.
        wenn der zug ausfährt, wird das gleis dem nach-attribut gleichgesetzt.

        im fahrplan werden die gleisänderungen aktualisiert.

        :param zug: original-ZugDetails-objekt vom PluginClient.zugliste.
        :return: None
        """
        self.gleis = zug.gleis
        self.plangleis = zug.plangleis
        self.verspaetung = zug.verspaetung
        self.amgleis = zug.amgleis
        self.sichtbar = zug.sichtbar
        self.usertext = zug.usertext
        self.usertextsender = zug.usertextsender
        self.fahrplanzeile = self.find_fahrplanzeile(plan=zug.plangleis)

        for zeile in zug.fahrplan:
            ziel = self.find_fahrplanzeile(plan=zeile.plan)
            try:
                ziel.update_fahrplan_zeile(zeile)
            except AttributeError:
                pass
        if len(zug.fahrplan) == 0:
            self.gleis = self.plangleis = self.nach


class ZugZielPlanung(FahrplanZeile):
    """
    fahrplanzeile im planungsmodul

    """

    def __init__(self, zug: ZugDetails):
        super().__init__(zug)

        # verspaetung ist die geschätzte verspätung bei der abfahrt von diesem wegpunkt.
        # solange der zug noch nicht am gleis angekommen ist,
        # kann z.b. das auswertungsmodul oder der fahrdienstleiter die geschätzte verspätung anpassen.
        # wenn None, wird hier kein von der aktuellen verspätung abweichender wert festgelegt.
        self.verspaetung: Optional[int] = None

    def assign_fahrplan_zeile(self, zeile: FahrplanZeile):
        self.gleis = zeile.gleis
        self.plan = zeile.plan
        self.an = zeile.an
        self.ab = zeile.ab
        self.flags = zeile.flags
        self.hinweistext = zeile.hinweistext

        # die nächsten drei attribute werden separat anhand der flags aufgelöst.
        self.ersatzzug = None
        self.fluegelzug = None
        self.kuppelzug = None

    def update_fahrplan_zeile(self, zeile: FahrplanZeile):
        self.gleis = zeile.gleis


class Planung:
    """
    zug-planung und disposition

    diese klasse führt eine zugliste ähnlich zu der vom PluginClient.
    sie unterscheidet sich jedoch in einigen merkmalen:

    - die liste enthält ZugDetailsPlanung-objekte statt ZugDetails.
    - züge werden bei ihrem ersten auftreten in den quelldaten übernommen und bleiben in der liste,
      bis sie explizit entfernt werden.
    - bei folgenden quelldatenübernahmen, werden nur noch die zielattribute nachgeführt,
      der fahrplan bleibt jedoch bestehen (im PluginClient werden abgefahrene ziele entfernt).
    - die fahrpläne der züge haben auch einträge zur einfahrt und ausfahrt.
    """
    def __init__(self):
        self.zugliste: Dict[int, ZugDetailsPlanung] = dict()
        self.auswertung: Optional[Auswertung] = None

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
        """
        neue züge in interne liste übernehmen.

        :param zuege:
        :return:
        """
        verarbeitete_zuege = set(self.zugliste.keys())

        for zug in sorted(zuege, key=lambda z: z.zid):
            try:
                zug_planung = self.zugliste[zug.zid]
            except KeyError:
                zug_planung = ZugDetailsPlanung()
                zug_planung.assign_zug_details(zug)
                self.zugliste[zug_planung.zid] = zug_planung
            else:
                zug_planung.update_zug_details(zug)
                verarbeitete_zuege.remove(zug.zid)

        for zid in verarbeitete_zuege:
            zug = self.zugliste[zid]
            if zug.sichtbar:
                zug.sichtbar = zug.amgleis = False
                zug.gleis = zug.plangleis = ""
                zug.hinweistext = "verarbeitet"

        self.folgezuege_aufloesen()

    def folgezuege_aufloesen(self):
        """
        folgezüge aus den zugflags auflösen.

        folgezüge werden im stammzug referenziert.
        die funktion arbeitet iterativ, bis alle folgezüge aufgelöst sind.

        :return: None
        """

        zids = set(self.zugliste.keys())

        while zids:
            zid = zids.pop()
            try:
                zug = self.zugliste[zid]
            except KeyError:
                continue

            for planzeile in zug.fahrplan:
                if set(planzeile.flags).intersection({'E', 'F', 'K'}):
                    if planzeile.ersatzzug is None and (zid2 := planzeile.ersatz_zid()):
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            pass
                        else:
                            planzeile.ersatzzug = zug2
                            zug2.stammzug = zug
                            zids.add(zid2)

                    if planzeile.fluegelzug is None and (zid2 := planzeile.fluegel_zid()):
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            pass
                        else:
                            planzeile.fluegelzug = zug2
                            zug2.stammzug = zug
                            zids.add(zid2)

                    if planzeile.kuppelzug is None and (zid2 := planzeile.kuppel_zid()):
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            pass
                        else:
                            planzeile.kuppelzug = zug2
                            zug2.stammzug = zug
                            zids.add(zid2)

    def einfahrten_korrigieren(self):
        for zug in self.zugliste.values():
            try:
                einfahrt = zug.fahrplan[0]
                ziel1 = zug.fahrplan[1]
            except IndexError:
                pass
            else:
                if einfahrt.hinweistext == "einfahrt" and einfahrt.gleis and ziel1.gleis:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, einfahrt.gleis, ziel1.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            einfahrt.an = einfahrt.ab = seconds_to_time(time_to_seconds(ziel1.an) - fahrzeit)
                            logger.debug(f"einfahrt {einfahrt.gleis} - {ziel1.gleis} korrigiert: {einfahrt.ab}")
                        except (AttributeError, ValueError):
                            pass

            try:
                ziel2 = zug.fahrplan[-2]
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.hinweistext == "ausfahrt":
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, ziel2.gleis, ausfahrt.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            ausfahrt.an = ausfahrt.ab = seconds_to_time(time_to_seconds(ziel2.ab) + fahrzeit)
                            logger.debug(f"ausfahrt {ziel2.gleis} - {ausfahrt.gleis} korrigiert: {ausfahrt.an}")
                        except (AttributeError, ValueError):
                            pass

    def verspaetungen_korrigieren(self):
        """
        entwicklung der verspätung im zuglauf abschätzen.

        die vom sim gemeldete verspätung bezieht sich auf den aktuellen ort des zuges.
        diese methode extrapoliert die verspätung auf nachfolgende halte.
        an längeren aufenthalten wird verspätung abgebaut.
        beim kuppeln mit einem anderen zug wird dessen verspätung berücksichtigt.

        :return: None
        """
        # wir muessen sicherstellen, dass folgezuege erst nach dem stammzug bearbeitet werden
        # die zid sind nicht chronologisch
        zids = list(filter(lambda z: self.zugliste[z].stammzug is None, self.zugliste.keys()))
        while zids:
            zid = zids.pop()
            try:
                zug = self.zugliste[zid]
            except KeyError:
                continue

            verspaetung = zug.verspaetung
            ifpz0 = 0
            if zug.sichtbar:
                for ifpz, fpz in enumerate(zug.fahrplan):
                    if fpz.gleis == zug.gleis:
                        ifpz0 = ifpz
            elif not zug.gleis:
                continue

            for ifpz, plan in enumerate(zug.fahrplan):
                if ifpz < ifpz0:
                    if plan.verspaetung is None:
                        plan.verspaetung = verspaetung
                    continue
                if plan.hinweistext == "einfahrt" or plan.hinweistext == "ausfahrt":
                    plan.verspaetung = verspaetung
                    continue
                if plan.durchfahrt():
                    plan.verspaetung = verspaetung
                    continue

                # mindestaufenthaltsdauer kann von einer reihe von faktoren abhaengen:
                if plan.richtungswechsel():
                    min_aufenthalt = 2
                elif plan.lokumlauf():
                    min_aufenthalt = 5
                elif plan.lokwechsel():
                    min_aufenthalt = 5
                else:
                    min_aufenthalt = 0

                try:
                    plan_an = time_to_minutes(plan.an)
                except AttributeError:
                    logger.warning(f"zug {zug} hat keine ankunft in zeile {plan}")
                    break

                # abfahrt fruehestens wenn nummernwechsel abgeschlossen ist
                try:
                    if plan.ersatzzug:
                        zids.append(plan.ersatzzug.zid)
                        plan_ab = time_to_minutes(plan.ersatzzug.fahrplan[0].an)
                    else:
                        plan_ab = time_to_minutes(plan.ab)
                except (AttributeError, IndexError):
                    plan_ab = plan_an + min_aufenthalt

                # abfahrt fruehestens wenn kuppelnder zug angekommen ist
                if plan.kuppelzug:
                    zids.append(plan.kuppelzug.zid)
                    kuppel_verspaetung = plan.kuppelzug.verspaetung
                    try:
                        kuppel_plan = plan.kuppelzug.fahrplan[-1]
                        if kuppel_plan.verspaetung is not None:
                            kuppel_verspaetung = kuppel_plan.verspaetung
                        plan_ab = max(plan_ab, time_to_minutes(kuppel_plan.an) + kuppel_verspaetung)
                    except (AttributeError, IndexError):
                        plan_ab = max(plan_ab, plan_ab + kuppel_verspaetung)

                # bei fluegelnden zuegen stimmt die angabe vom sim
                if plan.fluegelzug:
                    zids.append(plan.fluegelzug.zid)

                # neue verspaetung berechnen
                ankunft = plan_an + verspaetung
                aufenthalt = max(plan_ab - ankunft, min_aufenthalt)
                abfahrt = ankunft + aufenthalt
                verspaetung = abfahrt - plan_ab
                plan.verspaetung = verspaetung
                neu_ab = minutes_to_time(abfahrt - verspaetung)
                plan.ab = neu_ab

                # verspaetung des folgezugs anpassen
                if plan.ersatzzug:
                    plan.ersatzzug.verspaetung = verspaetung
                    plan.ersatzzug.fahrplan[0].an = neu_ab
                elif plan.fluegelzug:
                    plan.fluegelzug.verspaetung = verspaetung

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        daten von einem ereignis uebernehmen.

        noch nicht implementiert.

        :param ereignis:
        :return:
        """
        try:
            zug = self.zugliste[ereignis.zid]
        except KeyError:
            return None

        if ereignis.art == 'xxx':
            zug.sichtbar = False
            zug.amgleis = False
            zug.gleis = ""
            zug.plangleis = ""
            zug.hinweistext = "ausgefahren"
