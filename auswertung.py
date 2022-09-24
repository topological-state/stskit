import datetime
import logging
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

import networkx as nx
import numpy as np

from stsobj import ZugDetails, FahrplanZeile, Ereignis, time_to_minutes, time_to_seconds, minutes_to_time
from anlage import Anlage, JSONEncoder


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class FahrzeitAuswertung:
    """
    auswertungsklasse für fahrzeiten zwischen gleisen.

    messdaten werden per gleis hinzugefügt, können aber auch per gruppe ausgewertet werden.
    die gruppenzuordnung muss vor den daten definiert werden.
    """

    def __init__(self):
        self.gleis_zeiten = nx.DiGraph()
        self.bahnhof_zeiten = nx.DiGraph()
        self.gruppen: Dict[str, str] = {}

    def set_koordinaten(self, koordinaten: Mapping[str, Iterable[str]]) -> None:
        self.gruppen = {}
        for gruppe, gleise in koordinaten.items():
            for gleis in gleise:
                self.gruppen[gleis] = gruppe

    def add_fahrzeit(self, zug: ZugDetails, start: str, ziel: str, fahrzeit: float) -> None:
        """
        fahrzeit-messpunkt zur statistik hinzufügen.

        :param zug: ZugDetails objekt
        :param start: name eines bahnsteig- oder einfahrtsgleises
        :param ziel: name eines bahnsteig- oder ausfahrtsgleises
        :param fahrzeit in sekunden
        :return: None
        """

        logger.debug(f"add_fahrzeit({zug.name}, {start}, {ziel}, {fahrzeit})")

        self._add_edge_stats(self.gleis_zeiten, start, ziel, fahrzeit)
        try:
            self._add_edge_stats(self.bahnhof_zeiten, self.gruppen[start], self.gruppen[ziel], fahrzeit)
        except KeyError:
            logger.debug(f"add_fahrzeit: fehlende gruppendzuordnung für {start} oder {ziel}")

    @staticmethod
    def _add_edge_stats(g: nx.Graph, u: Any, v: Any, wert: float) -> Dict[str, Any]:
        """
        neue messung zu statistikattributen einer kante addieren

        :param g: graph
        :param u: startknoten
        :param v: zielknoten
        :param wert: messwert
        :return: aktualisierter attribut-dict
        """
        try:
            d = g.edges[u, v]
        except KeyError:
            d = {'min': wert, 'max': wert, 'sum': wert, 'sum2': wert**2, 'count': 1}
        else:
            d['min'] = min(d['min'], wert)
            d['max'] = max(d['max'], wert)
            d['sum'] = d['sum'] + wert
            d['sum2'] = d['sum2'] + wert ** 2
            d['count'] = d['count'] + 1

        d['avg'] = d['sum'] / d['count']
        d['sdev'] = np.sqrt(d['sum2'] / d['count'] - d['avg'] ** 2)

        g.add_edge(u, v, **d)
        return d

    def report(self):
        if logger.isEnabledFor(logging.INFO):
            try:
                d = {'gleis_zeiten': dict(nx.node_link_data(self.gleis_zeiten)),
                     'bahnhof_zeiten': dict(nx.node_link_data(self.bahnhof_zeiten))}
                p = Path.home() / r".stskit" / f"auswertung.json"
                with open(p, "w") as fp:
                    json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)
            except AttributeError:
                pass

    def get_fahrzeit(self, start: str, ziel: str) -> float:
        """
        durchschnittliche fahrzeit zwischen zwei gleisen oder gruppen auslesen

        die fahrzeit wird als mittelwert der über add_fahrzeit erfassten einzelmessungen ermittelt.

        wenn entsprechende daten vorhanden sind, wird die fahrzeit zwischen gleisen ausgegeben.
        ansonsten wird die fahrzeit zwischen den entsprechenden gruppen ausgegeben.
        gleisnamen werden dabei anhand self.gruppen übersetzt.

        start und ziel müssen nicht nebeneinander liegen.
        jedoch müssen die teilstrecken lückenlos erfasst worden sein.

        :param start: gleis- oder gruppenname
        :param ziel: gleis- oder gruppenname
        :return: mittlere gemessene fahrzeit zwischen start und ziel in sekunden.
            numpy.nan, wenn keine passende verbindung gefunden wurde.
        """

        try:
            z = self._get_graph_fahrzeit(self.gleis_zeiten, start, ziel)
        except (KeyError, nx.NetworkXException):
            try:
                start = self.gruppen[start]
                ziel = self.gruppen[ziel]
            except KeyError:
                pass
        else:
            return z

        try:
            z = self._get_graph_fahrzeit(self.bahnhof_zeiten, start, ziel)
        except (KeyError, nx.NetworkXException):
            pass
        else:
            return z

        return np.nan

    @staticmethod
    def _get_graph_fahrzeit(graph, start, ziel):
        try:
            return graph[start][ziel]['avg']
        except KeyError:
            pass

        p = nx.shortest_path(graph, start, ziel, 'avg')
        s = 0
        for u, v in zip(p[:-1], p[1:]):
            s = s + graph[u][v]['avg']
        return s


class ZugAuswertung:
    """
    zugdaten für die auswertung.

    das objekt verwaltet den aktuellen status der züge
    anhand einer periodischen abfrage und von ereignismeldungen.

    die attribute verspaetung, sichtbar, amgleis entsprechen dem letzten bekannten zustand.
    die attribute gleis und plangleis zeigen das nächste ziel oder sind leer,
    wenn der zug auf die ausfahrt zufährt.

    im "fahrplan" der züge wird nicht der plan,
    sondern die effektiv gefahrene strecke mit den ankunfts- und abfahrtszeiten,
    den effektiven ein- und ausfahrten,
    sowie von signalhalten geführt.
    der grund (ereignisart) für einen fahrplaneintrag steht im hinweistext-feld.

    bemerkungen:
    - züge, die den namen wechseln haben entweder keine einfahrt oder keine ausfahrt.
      der namenswechsel wird durch das "E"-flag angezeigt.
    """
    def __init__(self):
        self.zugliste: Dict[int, ZugDetails] = dict()

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
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
                mein_zug.von = zug.von.replace("Gleis ", "") if zug.von else ""
                mein_zug.nach = zug.nach.replace("Gleis ", "") if zug.nach else ""
                self.zugliste[mein_zug.zid] = mein_zug

            mein_zug.gleis = zug.gleis
            mein_zug.plangleis = zug.plangleis
            mein_zug.verspaetung = zug.verspaetung
            mein_zug.amgleis = zug.amgleis
            mein_zug.sichtbar = zug.sichtbar

    def ereignis_uebernehmen(self, ereignis: Ereignis) -> None:
        """
        ereignis verarbeiten.

        wenn der zug in der zugliste steht,
        wird das ereignis zuerst an eine der speziellen ereignismethoden übergeben
        und dann der zug-status (verspaetung, sichtbar, gleis, plangleis, amgleis)
        anhand der ereignisdaten aktualisiert.

        :param ereignis:
        :return:
        """
        try:
            zug = self.zugliste[ereignis.zid]
        except KeyError:
            pass
        else:
            zug.verspaetung = ereignis.verspaetung
            zug.sichtbar = ereignis.sichtbar
            try:
                getattr(self, ereignis.art)(zug, ereignis)
            except AttributeError:
                pass
            zug.gleis = ereignis.gleis
            zug.plangleis = ereignis.plangleis
            zug.amgleis = ereignis.amgleis

    def einfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        """
        einfahrt verarbeiten.

        fügt eine neue zeile mit dem einfahrtsgleis (zug.von) und der ereigniszeit in den fahrplan.

        :param zug:
        :param ereignis:
        :return:
        """
        fpz = FahrplanZeile(zug)
        fpz.gleis = zug.von
        fpz.plan = zug.von
        fpz.flags = "D"
        fpz.hinweistext = "einfahrt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def ausfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        """
        ausfahrt verarbeiten.

        fügt eine neue zeile mit dem ausfahrtsgleis (zug.nach) und der ereigniszeit in den fahrplan.

        :param zug:
        :param ereignis:
        :return:
        """
        fpz = FahrplanZeile(zug)
        fpz.gleis = zug.nach
        fpz.plan = zug.nach
        fpz.flags = "D"
        fpz.hinweistext = "ausfahrt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)
        zug.sichtbar = False

    def ankunft(self, zug: ZugDetails, ereignis: Ereignis):
        """
        ankunft verarbeiten.

        fügt eine neue zeile mit dem letzten zugziel und der ereigniszeit in den fahrplan.

        bemerkungen:

        - durchfahrten erzeugen nur ein ankunftsereignis. das ereignis.gleis zeigt dann schon das nächste ziel.
          wir müssen das gleis deshalb aus dem zug-objekt auslesen.
        - züge, die den namen wechseln werden daran erkannt, dass das zielgleis gleich heisst wie das "nach".
          das "E"-flag wird gesetzt, und "sichtbar" wird falsch.

        :param zug:
        :param ereignis:
        :return:
        """
        fpz = FahrplanZeile(zug)
        fpz.gleis = zug.gleis
        fpz.plan = zug.gleis
        if zug.gleis == zug.nach:
            fpz.flags = "E"
            zug.sichtbar = False
        else:
            fpz.flags = ""
        fpz.hinweistext = "ankunft"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def abfahrt(self, zug: ZugDetails, ereignis: Ereignis):
        """
        abfahrt verarbeiten.

        aktualisiert die abfahrtszeit der letzten fahrplanzeile.

        bemerkungen:

        - abfahrtsereignisse entstehen, sobald der zug abfahrbereit (amgleis) ist.
          bei abfahrt ist amgleis falsch, und gleis zeigt das nächste ziel an.
        - durchfahrten erzeugen nur ein ankunfts- aber kein abfahrtsereignis!
        - züge, die den namen gewechselt haben, haben ein leeres "von".
          diese koennen im moment nicht verarbeitet werden.

        :param zug:
        :param ereignis:
        :return:
        """
        try:
            fpz = zug.fahrplan[-1]
        except IndexError:
            # todo: zug hat namen gewechselt
            # problem: die ereignismeldung zeigt das "von"-gleis nicht an.
            pass
        else:
            if fpz.gleis == zug.gleis:
                fpz.hinweistext = "abfahrt"
                fpz.ab = ereignis.zeit.time()

    def rothalt(self, zug: ZugDetails, ereignis: Ereignis):
        """
        rothalt verarbeiten.

        fügt eine neue zeile ohne zugziel in den fahrplan.

        bemerkungen:

        - wir können nicht wissen, wo der zug genau steht.
        - das ereignis.gleis zeigt das nächste ziel.

        :param zug:
        :param ereignis:
        :return:
        """
        fpz = FahrplanZeile(zug)
        fpz.gleis = ""
        fpz.plan = ""
        fpz.flags = ""
        fpz.hinweistext = "rothalt"
        fpz.an = fpz.ab = ereignis.zeit.time()
        zug.fahrplan.append(fpz)

    def wurdegruen(self, zug: ZugDetails, ereignis: Ereignis):
        """
        wurdegruen verarbeiten.

        trägt die abfahrtszeit in die letzte fahrplanzeile ein (wenn diese ein rothalt ist).

        :param zug:
        :param ereignis:
        :return:
        """
        try:
            fpz = zug.fahrplan[-1]
            if fpz.hinweistext == 'rothalt':
                fpz.ab = ereignis.zeit.time()
        except IndexError:
            pass


class Auswertung:
    def __init__(self, config: Anlage):
        self.config: Anlage = config
        self.fahrzeiten: FahrzeitAuswertung = FahrzeitAuswertung()
        self.zuege: ZugAuswertung = ZugAuswertung()
        self._update_koordinaten()

    def _update_koordinaten(self):
        wegpunkte = {**self.config.bahnsteiggruppen,
                     **self.config.anschlussgruppen}
        self.fahrzeiten.set_koordinaten(wegpunkte)

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
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

        diese funktion berechnet die fahrzeit zum letzten ankunftsereignis.

        etwaige haltezeiten (auch ausserplanmässige) werden nicht eingerechnet.

        :param zug:
        :return:
        """

        try:
            ziel = zug.fahrplan[-1]
            start = zug.fahrplan[-2]
        except IndexError:
            pass
        else:
            ab = time_to_seconds(start.ab)
            an = time_to_seconds(ziel.an)
            strecke = an - ab
            if strecke < 0:
                strecke += 24 * 60 * 60
            if not zug.ist_rangierfahrt:
                self.fahrzeiten.add_fahrzeit(zug, start.gleis, ziel.gleis, strecke)

    def fahrzeit_schaetzen(self, zug: str, start: str, ziel: str) -> Optional[int]:
        """
        fahrzeit eines zuges von start zu ziel abschätzen.

        :param zug: zugname
        :param start: name des startpunkts (einfahrt oder bahnsteig)
        :param ziel: name des zielpunkts (ausfahrt oder bahnsteig)
        :return: geschätzte fahrzeit in sekunden, oder None, falls eine schätzung unmöglich ist.
        """

        return self.fahrzeiten.get_fahrzeit(start, ziel)

    def rotzeit_auswerten(self, zug: ZugDetails):
        """
        rotzeit berechnen.

        berechnet die gesamte zeit, die der zug vor einem roten signal gestanden ist.

        das resultat wird als timedelta in das extra hinzugefügte attribut 'rotzeit' des ZugDetails geschrieben.
        ausserdem wird die zeit in sekunden als funktionsergebnis zurückgegeben.

        :param zug:
        :return: rotzeit in sekunden
        """
        gesamt = 0
        for fpz in zug.fahrplan:
            if fpz.hinweistext == "rothalt":
                zeit = time_to_seconds(fpz.ab) - time_to_seconds(fpz.an)
                if zeit < 0:
                    zeit += 24 * 60 * 60
                gesamt += zeit

        setattr(zug, 'rotzeit', datetime.timedelta(seconds=gesamt))
        return gesamt
