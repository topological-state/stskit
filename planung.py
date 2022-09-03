import datetime
import logging
import numpy as np
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

from stsobj import ZugDetails, FahrplanZeile, Ereignis
from stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from auswertung import Auswertung


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class VerspaetungsKorrektur:
    """
    basisklasse für die anpassung der verspätungszeit eines fahrplanziels

    eine VerspaetungsKorrektur-klasse besteht im wesentlichen aus der anwenden-methode.
    diese berechnet für das gegebene ziel die abfahrtsverspätung aus der ankunftsverspätung
    und ggf. weiteren ziel- bzw. zugdaten.

    über das _planung-attribut hat die klasse zugriff auf die ganze zugliste.
    sie darf jedoch nur das angegebene ziel sowie allfällige verknüpfte züge direkt ändern.

    wenn ein fahrplanziel abgearbeitet wurde, wird statt `anwenden` die `weiterleiten`-methode aufgerufen,
    um die verspätungskorrektur von folgezügen durchzuführen.
    """
    def __init__(self, planung: 'Planung'):
        super().__init__()
        self._planung = planung

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        """
        verspätungskorrektur anwenden

        :param zug:
        :param ziel:
        :return:
        """

        ziel.verspaetung_ab = ziel.verspaetung_an

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        """
        verspätungskorrektur von folgezügen aufrufen wenn nötig

        :param zug:
        :param ziel:
        :return:
        """
        pass


class FesteVerspaetung(VerspaetungsKorrektur):
    """
    verspätung auf einen festen wert setzen.

    kann bei vorzeitiger abfahrt auch negativ sein.

    diese klasse ist für manuelle eingriffe des fahrdienstleiters gedacht.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.verspaetung: int = 0

    def __str__(self):
        return f"Fix({self.verspaetung})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        ziel.verspaetung_ab = self.verspaetung


class Signalhalt(FesteVerspaetung):
    """
    verspätung durch signalhalt

    diese klasse wird in der verarbeitung des Abfahrt-ereignisses eingesetzt,
    wenn der zug an einem bahnsteig steht, auf ein offenes signal wartet und dadurch verspätet wird.
    die wirkung auf den fahrplan ist dieselbe wie von FesteVerspaetung.
    der andere name und objekt-string dient der unterscheidung.
    """
    def __str__(self):
        return f"Signal({self.verspaetung})"


class Einfahrtszeit(VerspaetungsKorrektur):
    """
    verspätete einfahrt

    die vom simulator gemeldete einfahrtszeit (inkl. verspätung) ist manchmal kleiner als die aktuelle sim-zeit.
    in diesem fall erhöht diese korrektur die verspätung, so dass die einfahrtszeit der aktuellen uhrzeit entspricht.
    """

    def __str__(self):
        return f"Einfahrt"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an

        ankunft = plan_an + ziel.verspaetung_an
        abfahrt = max(ankunft, self._planung.simzeit_minuten)
        ziel.verspaetung_ab = abfahrt - plan_ab


class PlanmaessigeAbfahrt(VerspaetungsKorrektur):
    """
    planmässige abfahrt oder verspätung aufholen wenn möglich

    dies ist die normale abfertigung, soweit kein anderer zug involviert ist.
    die verspätung wird soweit möglich reduziert, ohne die mindestaufenthaltsdauer zu unterschreiten.
    """

    def __str__(self):
        return f"Plan"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab


class AnkunftAbwarten(VerspaetungsKorrektur):
    """
    wartet auf einen anderen zug.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der effektiven ankunftszeit des anderen zuges
    oder der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei ersatzzügen, kupplungen und flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.ursprung: Optional[ZugZielPlanung] = None
        self.wartezeit: int = 0

    def __str__(self):
        return f"Ankunft({self.ursprung.zug.name}, {self.wartezeit})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            plan_an = None

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        if plan_an is None:
            plan_an = plan_ab

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        anschluss_an = time_to_minutes(self.ursprung.an) + self.ursprung.verspaetung_an
        anschluss_ab = anschluss_an + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        ziel.verspaetung_ab = abfahrt - plan_ab


class AbfahrtAbwarten(VerspaetungsKorrektur):
    """
    wartet, bis ein anderer zug abgefahren ist.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der abfahrtszeit des anderen zuges und der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.ursprung: Optional[ZugZielPlanung] = None
        self.wartezeit: int = 0

    def __str__(self):
        return f"Abfahrt({self.ursprung.zug.name}, {self.wartezeit})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            plan_an = None

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        if plan_an is None:
            plan_an = plan_ab

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        anschluss_ab = time_to_minutes(self.ursprung.ab) + self.ursprung.verspaetung_ab
        anschluss_ab = anschluss_ab + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        ziel.verspaetung_ab = abfahrt - plan_ab


class Ersatzzug(VerspaetungsKorrektur):
    """
    abfahrt frühestens wenn nummernwechsel abgeschlossen ist

    das erste fahrplanziel des ersatzzuges muss it einer AnschlussAbwarten-korrektur markiert sein.
    """

    def __str__(self):
        return f"Ersatz"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ersatzzug.fahrplan[0].an)
        except (AttributeError, IndexError):
            try:
                plan_ab = time_to_minutes(ziel.ab)
            except AttributeError:
                plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab
        ziel.ab = minutes_to_time(abfahrt - ziel.verspaetung_ab)

        if ziel.ersatzzug:
            ziel.ersatzzug.verspaetung = ziel.verspaetung_ab
            self._planung.zugverspaetung_korrigieren(ziel.ersatzzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.ersatzzug:
            self._planung.zugverspaetung_korrigieren(ziel.ersatzzug)


class Kupplung(VerspaetungsKorrektur):
    """
    zwei züge kuppeln

    gekuppelter zug kann erst abfahren, wenn beide züge angekommen sind.

    bemerkung: der zug mit dem kuppel-flag verschwindet. der verlinkte zug fährt weiter.
    """

    def __str__(self):
        return f"Kupplung"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.warning(f"zug {zug} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except (AttributeError, IndexError):
            plan_ab = plan_an + ziel.mindestaufenthalt

        # zuerst die verspaetung des kuppelnden zuges berechnen
        try:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)
            kuppel_index = ziel.kuppelzug.find_fahrplan_index(plan=ziel.plan)
            kuppel_ziel = ziel.kuppelzug.fahrplan[kuppel_index]
            kuppel_verspaetung = kuppel_ziel.verspaetung_an
            kuppel_an = time_to_minutes(kuppel_ziel.an) + kuppel_verspaetung
        except (AttributeError, IndexError):
            kuppel_an = 0

        while abs(kuppel_an - (plan_an + ziel.verspaetung_an)) < 2:
            ziel.verspaetung_an += 1

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = max(ankunft + aufenthalt, kuppel_an)
        ziel.verspaetung_ab = abfahrt - plan_ab

        if ziel.kuppelzug:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.kuppelzug:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)


class Fluegelung(VerspaetungsKorrektur):
    def __str__(self):
        return f"Flügelung"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.warning(f"zug {zug} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except (AttributeError, IndexError):
            plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab

        if ziel.fluegelzug:
            ziel.fluegelzug.verspaetung = ziel.verspaetung_an
            ziel.fluegelzug.fahrplan[0].verspaetung_an = ziel.verspaetung_an
            self._planung.zugverspaetung_korrigieren(ziel.fluegelzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.fluegelzug:
            self._planung.zugverspaetung_korrigieren(ziel.fluegelzug)


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
        self.ausgefahren: bool = False
        self.folgezuege_aufgeloest: bool = False
        self.korrekturen_definiert: bool = False

    @property
    def einfahrtszeit(self) -> datetime.time:
        """
        planmässige einfahrtszeit (ohne verspätung)

        dies entspricht der abfahrtszeit des ersten fahrplaneintrags (einfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[0].ab

    @property
    def ausfahrtszeit(self) -> datetime.time:
        """
        planmässige ausfahrtszeit (ohne verspätung)

        dies enstspricht der ankunftszeit des letzten fahrplaneintrags (ausfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[-1].an

    def route(self, plan: bool = False) -> Iterable[str]:
        """
        route (reihe von stationen) des zuges als generator

        die route ist eine liste von stationen (gleisen, ein- und ausfahrt) in der reihenfolge des fahrplans.
        ein- und ausfahrten können bei ersatzzügen o.ä. fehlen.
        durchfahrtsgleise sind auch enthalten.

        die methode liefert das gleiche ergebnis wie die überschriebene methode.
        aber da in der planung die ein- und ausfahrten im fahrplan enthalten sind,
        ist die implementierung etwas einfacher.

        :param plan: plangleise statt effektive gleise melden
        :return: generator
        """
        for fpz in self.fahrplan:
            if plan:
                yield fpz.plan
            else:
                yield fpz.gleis

    def assign_zug_details(self, zug: ZugDetails):
        """
        objekt mit stammdaten vom PluginClient initialisieren.

        unterschiede zum original-ZugDetails:
        - ein- und ausfahrtsgleise werden als separate fahrplanzeile am anfang bzw. ende der liste eingefügt
          und mit den attributen einfahrt bzw. ausfahrt markiert.
          ankunfts- und abfahrtszeiten werden dem benachbarten fahrplanziel gleichgesetzt.
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
        if not zug.sichtbar and self.von and not zug.von.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            ziel.plan = ziel.gleis = self.von
            try:
                ziel.ab = ziel.an = zug.fahrplan[0].an
            except IndexError:
                pass
            ziel.einfahrt = True
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
            ziel.ausfahrt = True
            self.fahrplan.append(ziel)

        for n, z in enumerate(self.fahrplan):
            z.zielnr = n * 1000

        # zug ist neu in liste und schon im stellwerk -> startaufstellung
        if zug.sichtbar:
            ziel_index = self.find_fahrplan_index(plan=zug.plangleis)
            if ziel_index is None:
                # ziel ist ausfahrt
                ziel_index = -1
            for ziel in self.fahrplan[0:ziel_index]:
                ziel.abgefahren = ziel.angekommen = True
                ziel.verspaetung_ab = ziel.verspaetung_an = zug.verspaetung
            if zug.amgleis:
                ziel = self.fahrplan[ziel_index]
                ziel.angekommen = True
                ziel.verspaetung_an = zug.verspaetung

    def update_zug_details(self, zug: ZugDetails):
        """
        aktualisiert die veränderlichen attribute eines zuges

        die folgenden attribute werden aktualisert, alle anderen bleiben unverändert.
        gleis, plangleis, amgleis, sichtbar, verspaetung, usertext, usertextsender, fahrplanzeile.
        wenn der zug ausfährt, wird das gleis dem nach-attribut gleichgesetzt.

        im fahrplan werden die gleisänderungen aktualisiert.

        anstelle des zuges kann auch ein ereignis übergeben werden.
        Ereignis-objekte entsprechen weitgehend den ZugDetails-objekten,
        enthalten jedoch keinen usertext und keinen fahrplan.

        :param zug: ZugDetails- oder Ereignis-objekt vom PluginClient.
        :return: None
        """

        if zug.gleis:
            self.gleis = zug.gleis
            self.plangleis = zug.plangleis
        else:
            self.gleis = self.plangleis = self.nach

        self.verspaetung = zug.verspaetung
        self.amgleis = zug.amgleis
        self.sichtbar = zug.sichtbar

        if not isinstance(zug, Ereignis):
            self.usertext = zug.usertext
            self.usertextsender = zug.usertextsender

        for zeile in zug.fahrplan:
            ziel = self.find_fahrplanzeile(plan=zeile.plan)
            try:
                ziel.update_fahrplan_zeile(zeile)
            except AttributeError:
                pass

        route = list(self.route(plan=True))
        try:
            self.ziel_index = route.index(zug.plangleis)
        except ValueError:
            # zug faehrt aus
            if not zug.plangleis:
                self.ziel_index = -1


class ZugZielPlanung(FahrplanZeile):
    """
    fahrplanzeile im planungsmodul

    in ergänzung zum originalen FahrplanZeile objekt, führt diese klasse:
    - nach ziel aufgelöste ankunfts- und abfahrtsverspätung.
    - daten zur verspätungsanpassung.
    - status des fahrplanziels.
      nach ankunft/abfahrt sind die entsprechenden verspätungsangaben effektiv, vorher schätzwerte.

    attribute
    ---------

    - zielnr: definiert die reihenfolge von fahrzielen.
              bei originalen fahrzielen entspricht sie fahrplan-index multipliziert mit 1000.
              bei eingefügten betriebshalten ist sie nicht durch 1000 teilbar.
              die zielnummer wird als schlüssel in der gleisbelegung verwendet.
              sie wird vom ZugDetailsPlanung-objekt gesetzt
              und ändert sich über die lebensdauer des zugobjekts nicht.
    """

    def __init__(self, zug: ZugDetails):
        super().__init__(zug)

        self.zielnr: Optional[int] = None
        self.einfahrt: bool = False
        self.ausfahrt: bool = False
        self.verspaetung_an: int = 0
        self.verspaetung_ab: int = 0
        self.mindestaufenthalt: int = 0
        self.auto_korrektur: Optional[VerspaetungsKorrektur] = None
        self.fdl_korrektur: Optional[VerspaetungsKorrektur] = None
        self.angekommen: bool = False
        self.abgefahren: bool = False

    def assign_fahrplan_zeile(self, zeile: FahrplanZeile):
        """
        objekt aus fahrplanzeile initialisieren.

        die gemeinsamen attribute werden übernommen.
        folgezüge bleiben leer.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
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
        """
        objekt aus fahrplanzeile aktualisieren.

        aktualisiert werden nur:
        - gleis: weil möglicherweise eine gleisänderung vorgenommen wurde.

        alle anderen attribute sind statisch oder werden vom Planung objekt aktualisiert.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
        self.gleis = zeile.gleis

    @property
    def ankunft_minute(self) -> Optional[int]:
        """
        ankunftszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.an) + self.verspaetung_an
        except AttributeError:
            return None

    @property
    def abfahrt_minute(self) -> Optional[int]:
        """
        abfahrtszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.ab) + self.verspaetung_ab
        except AttributeError:
            return None

    @property
    def verspaetung(self) -> int:
        """
        abfahrtsverspaetung

        dies ist ein alias von verspaetung_ab und sollte in neuem code nicht mehr verwendet werden.

        :return: verspaetung in minuten
        """
        return self.verspaetung_ab

    @property
    def gleistyp(self) -> str:
        if self.einfahrt:
            return 'Einfahrt'
        elif self.ausfahrt:
            return 'Ausfahrt'
        else:
            return 'Gleis'


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
        self.simzeit_minuten: int = 0

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
        """
        interne zugliste mit sim-daten aktualisieren.

        - neue züge übernehmen
        - bekannte züge aktualisieren
        - ausgefahrene züge markieren
        - links zu folgezügen aktualisieren
        - verspätungsmodell aktualisieren

        :param zuege:
        :return:
        """
        ausgefahrene_zuege = set(self.zugliste.keys())

        for zug in zuege:
            try:
                zug_planung = self.zugliste[zug.zid]
            except KeyError:
                # neuer zug
                zug_planung = ZugDetailsPlanung()
                zug_planung.assign_zug_details(zug)
                zug_planung.update_zug_details(zug)
                self.zugliste[zug_planung.zid] = zug_planung
                ausgefahrene_zuege.discard(zug.zid)
            else:
                # bekannter zug
                zug_planung.update_zug_details(zug)
                ausgefahrene_zuege.discard(zug.zid)

        for zid in ausgefahrene_zuege:
            zug = self.zugliste[zid]
            if zug.sichtbar:
                zug.sichtbar = zug.amgleis = False
                zug.gleis = zug.plangleis = ""
                zug.ausgefahren = True
                for zeile in zug.fahrplan:
                    zeile.abgefahren = True

        self.folgezuege_aufloesen()
        self.korrekturen_definieren()

    def folgezuege_aufloesen(self):
        """
        folgezüge aus den zugflags auflösen.

        folgezüge werden im stammzug referenziert.
        die funktion arbeitet iterativ, bis alle folgezüge aufgelöst sind.

        :return: None
        """

        zids = list(self.zugliste.keys())

        while zids:
            zid = zids.pop(0)
            try:
                zug = self.zugliste[zid]
            except KeyError:
                continue

            if zug.folgezuege_aufgeloest:
                continue
            folgezuege_aufgeloest = True

            for planzeile in zug.fahrplan:
                if set(planzeile.flags).intersection({'E', 'F', 'K'}):
                    if zid2 := planzeile.ersatz_zid():
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            planzeile.ersatzzug = None
                            folgezuege_aufgeloest = False
                        else:
                            planzeile.ersatzzug = zug2
                            zug2.stammzug = zug
                            zids.append(zid2)

                    if zid2 := planzeile.fluegel_zid():
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            planzeile.fluegelzug = None
                            folgezuege_aufgeloest = False
                        else:
                            planzeile.fluegelzug = zug2
                            zug2.stammzug = zug
                            zids.append(zid2)

                    if zid2 := planzeile.kuppel_zid():
                        try:
                            zug2 = self.zugliste[zid2]
                        except KeyError:
                            planzeile.kuppelzug = None
                            folgezuege_aufgeloest = False
                        else:
                            planzeile.kuppelzug = zug2
                            zug2.stammzug = zug
                            zids.append(zid2)

            zug.folgezuege_aufgeloest = folgezuege_aufgeloest

    def einfahrten_korrigieren(self):
        """
        ein- und ausfahrtszeiten abschätzen.

        die ein- und ausfahrtszeiten werden vom sim nicht vorgegeben.
        wir schätzen sie die einfahrtszeit aus der ankunftszeit des anschliessenden wegpunkts
        und er kürzesten beobachteten fahrzeit zwischen der einfahrt und dem wegpunkt ab.
        die einfahrtszeit wird im ersten fahrplaneintrag eingetragen (an und ab).

        analog wird die ausfahrtszeit im letzten fahrplaneintrag abgeschätzt.

        :return:
        """
        for zug in self.zugliste.values():
            try:
                einfahrt = zug.fahrplan[0]
                ziel1 = zug.fahrplan[1]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt and einfahrt.gleis and ziel1.gleis:
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
                if ausfahrt.ausfahrt:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, ziel2.gleis, ausfahrt.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            ausfahrt.an = ausfahrt.ab = seconds_to_time(time_to_seconds(ziel2.ab) + fahrzeit)
                            logger.debug(f"ausfahrt {ziel2.gleis} - {ausfahrt.gleis} korrigiert: {ausfahrt.an}")
                        except (AttributeError, ValueError):
                            pass

    def verspaetungen_korrigieren(self, simzeit_minuten: int):
        """
        verspätungsangaben aller züge nachführen

        die methode ruft die zugverspaetung_korrigieren methode für jeden stammzug (zug ohne vorgänger) auf.
        folgezüge werden rekursiv durch die autokorrektur behandelt.

        :return:
        """

        self.simzeit_minuten = simzeit_minuten

        zids = list(filter(lambda z: self.zugliste[z].stammzug is None, self.zugliste.keys()))
        while zids:
            zid = zids.pop(0)
            try:
                zug = self.zugliste[zid]
            except KeyError:
                continue
            else:
                self.zugverspaetung_korrigieren(zug)

    def zugverspaetung_korrigieren(self, zug: ZugDetailsPlanung):
        """
        geschätzte verspätung an jedem punkt im fahrplan berechnen

        passierte wegpunkte werden nicht mehr verändert.
        am aktuellen ziel wird die aktuelle verspätung eingetragen
        (ankunftsverspätung, wenn das ziel noch nicht erreicht wurde, sonst die abfahrtsverspätung).

        die verspätungen an den folgenden wegpunkten werden nach auto- und fdl-korrektur geschätzt.

        :param zug: ZugDetailsPlanung mit aktuellem fahrplan und aktueller zielangabe.
            es ist wichtig, dass die angekommen- und abgefahren-attribute korrekt gesetzt sind!
        :return:
        """

        verspaetung = zug.verspaetung
        logger.debug(f"korrektur {zug.name} ({zug.verspaetung})")

        for ziel in zug.fahrplan:
            if not ziel.angekommen:
                ziel.verspaetung_an = verspaetung

            if not ziel.abgefahren:
                if ziel.fdl_korrektur is not None:
                    ziel.fdl_korrektur.anwenden(zug, ziel)
                elif ziel.auto_korrektur is not None:
                    ziel.auto_korrektur.anwenden(zug, ziel)
                else:
                    ziel.verspaetung_ab = ziel.verspaetung_an
                verspaetung = ziel.verspaetung_ab
            else:
                try:
                    ziel.auto_korrektur.weiterleiten(zug, ziel)
                except AttributeError:
                    pass

    def korrekturen_definieren(self):
        for zug in self.zugliste.values():
            if not zug.korrekturen_definiert:
                result = self.zug_korrekturen_definieren(zug)
                zug.korrekturen_definiert = zug.folgezuege_aufgeloest and result

    def zug_korrekturen_definieren(self, zug: ZugDetailsPlanung) -> bool:
        result = True
        for ziel in zug.fahrplan:
            ziel_result = self.ziel_korrekturen_definieren(ziel)
            result = result and ziel_result
        return result

    def ziel_korrekturen_definieren(self, ziel: ZugZielPlanung) -> bool:
        result = True

        if ziel.richtungswechsel():
            ziel.mindestaufenthalt = 2
        elif ziel.lokumlauf():
            ziel.mindestaufenthalt = 2
        elif ziel.lokwechsel():
            ziel.mindestaufenthalt = 5

        if ziel.einfahrt:
            ziel.auto_korrektur = Einfahrtszeit(self)
        elif ziel.ausfahrt:
            pass
        elif ziel.durchfahrt():
            pass
        elif ziel.ersatz_zid():
            ziel.auto_korrektur = Ersatzzug(self)
            anschluss = AnkunftAbwarten(self)
            anschluss.ursprung = ziel
            try:
                ziel.ersatzzug.fahrplan[0].auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.kuppel_zid():
            ziel.auto_korrektur = Kupplung(self)
            anschluss = AnkunftAbwarten(self)
            anschluss.ursprung = ziel
            try:
                kuppel_ziel = ziel.kuppelzug.find_fahrplanzeile(plan=ziel.plan)
                kuppel_ziel.auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.fluegel_zid():
            ziel.auto_korrektur = Fluegelung(self)
            ziel.mindestaufenthalt = 1
            anschluss = AbfahrtAbwarten(self)
            anschluss.ursprung = ziel
            anschluss.wartezeit = 2
            try:
                ziel.fluegelzug.fahrplan[0].auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.auto_korrektur is None:
            ziel.auto_korrektur = PlanmaessigeAbfahrt(self)

        return result

    def zug_finden(self, zug: Union[int, str, ZugDetails]) -> Optional[ZugDetailsPlanung]:
        """
        zug nach name oder nummer in zugliste suchen

        :param zug: nummer oder name des zuges oder ein beliebiges objekt mit einem zid attribut,
            z.b. ein ZugDetails vom PluginClient oder ein Ereignis.
        :return: entsprechendes ZugDetailsPlanung aus der zugliste dieser klasse.
            None, wenn kein passendes objekt gefunden wurde.
        """

        zid = None
        try:
            zid = zug.zid
        except AttributeError:
            for z in self.zugliste.values():
                if z.nummer == zug or z.name == zug:
                    zid = z.zid
                    break

        try:
            return self.zugliste[zid]
        except KeyError:
            return None

    def fdl_korrektur_setzen(self, korrektur: Optional[VerspaetungsKorrektur], ziel: Union[int, str, ZugZielPlanung]):
        """
        fahrdienstleiter-korrektur setzen

        mit dieser methode kann der fahrdienstleiter eine manuelle verspätungskorrektur auf eine fahrplanzeile anwenden,
        z.b. eine feste abgangsverspätung setzen oder eine abhängigkeit von einem kreuzenden zug festlegen.

        beim setzen einer fdl-korrektur werden alle nachfolgenden gelöscht!
        beim löschen (auf None setzen) bleiben sie erhalten.

        :param korrektur: von VerspaetungsKorrektur abgeleitetes korrekturobjekt.
            in frage kommen normalerweise FesteVerspaetung, AnkunftAbwarten oder AbfahrtAbwarten.
            bei None wird die korrektur gelöscht.
        :param ziel: fahrplanziel auf die die korrektur angewendet wird.
            dies kann ein ZugDetailsPlanung-objekt aus der zugliste dieser klasse sein
            oder ein gleisname oder fahrplan-index.
            in den letzteren beiden fällen, muss auch der zug oder zid angegeben werden.
        :return: None
        """

        zug = ziel.zug
        ziel_index = zug.find_fahrplan_index(plan=ziel.plan)

        ziel.fdl_korrektur = korrektur
        if korrektur:
            for z in zug.fahrplan[ziel_index + 1:]:
                z.fdl_korrektur = None

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        daten von einem ereignis uebernehmen.

        aktualisiert die verspätung und angekommen/abgefahren-flags anhand eines ereignisses.

        :param ereignis: Ereignis-objekt vom PluginClient
        :return:
        """

        logger.debug(f"{ereignis.art} {ereignis.name} ({ereignis.verspaetung})")

        try:
            zug = self.zugliste[ereignis.zid]
        except KeyError:
            logger.warning(f"zug von ereignis {ereignis} nicht in zugliste")
            return None

        try:
            alter_index = zug.ziel_index
            altes_ziel = zug.fahrplan[zug.ziel_index]
        except IndexError:
            alter_index = None
            altes_ziel = None

        # veraltetes ereignis? - kommt vor!!!
        neuer_index = zug.find_fahrplan_index(plan=ereignis.plangleis)
        if neuer_index is None or alter_index is None or (neuer_index < alter_index):
            logger.debug(f"ignoriere veraltetes ereignis {ereignis}")
            return
        else:
            neues_ziel = zug.fahrplan[neuer_index]

        if ereignis.art == 'einfahrt':
            try:
                einfahrt = zug.fahrplan[0]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt:
                    einfahrt.verspaetung_ab = time_to_minutes(ereignis.zeit) - time_to_minutes(einfahrt.ab)
                    einfahrt.angekommen = einfahrt.abgefahren = True

        elif ereignis.art == 'ausfahrt':
            try:
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.ausfahrt:
                    ausfahrt.verspaetung_an = ausfahrt.verspaetung_ab = ereignis.verspaetung
                    ausfahrt.angekommen = ausfahrt.abgefahren = True
                    zug.ausgefahren = True

        elif ereignis.art == 'ankunft':
            altes_ziel.verspaetung_an = time_to_minutes(ereignis.zeit) - time_to_minutes(altes_ziel.an)
            altes_ziel.angekommen = True
            if altes_ziel.durchfahrt():
                altes_ziel.verspaetung_ab = altes_ziel.verspaetung_an
                altes_ziel.abgefahren = True
            # falls ein ereignis vergessen gegangen ist:
            for ziel in zug.fahrplan[0:alter_index]:
                ziel.angekommen = True
                ziel.abgefahren = True

        elif ereignis.art == 'abfahrt':
            if ereignis.amgleis:
                if ereignis.verspaetung > 0:
                    altes_ziel.auto_korrektur = Signalhalt(self)
                    altes_ziel.auto_korrektur.verspaetung = ereignis.verspaetung
            else:
                altes_ziel.fdl_korrektur = None
                altes_ziel.verspaetung_ab = ereignis.verspaetung
                altes_ziel.abgefahren = True

        elif ereignis.art == 'rothalt' or ereignis.art == 'wurdegruen':
            zug.verspaetung = ereignis.verspaetung
            neues_ziel.verspaetung_an = ereignis.verspaetung
