import logging
import os
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union
import weakref

from stskit.stsobj import Ereignis, time_to_minutes
from stskit.stsplugin import PluginClient
from stskit.anlage import Anlage
from stskit.auswertung import Auswertung
from stskit.planung import Planung

logger = logging.getLogger(__name__)


class Observable:
    """
    notify observers of events

    - observers are bound methods of object instances.
    - the object keeps weak references - observers don't need to unregister.
    """

    def __init__(self, owner: Any):
        self.owner = owner
        self._observers = weakref.WeakKeyDictionary()

    def register(self, observer):
        """
        register an observer

        :param observer: must be a bound method.

        :return: None
        """

        try:
            obj = observer.__self__
            func = observer.__func__
            name = observer.__name__
        except AttributeError:
            raise
        else:
            self._observers[obj] = name

    def notify(self, *args, **kwargs):
        """
        notify observers

        the first two positional arguments sent to the observers are the instance of observable and the owner.
        the remaining arguments are copied from the call arguments.

        :param args: positional arguments to be passed to the observers.
        :param kwargs: keyword arguments to be passed to the observers
        :return: None
        """

        for obs, name in self._observers.items():
            meth = getattr(obs, name)  # bound method
            meth(self, *args, **kwargs)


class DatenZentrale:
    """
    zentrale datenschnittstelle zu simulator, planung und auswertung

    die datenzentrale ist unterteilt in:
    - die plugin-schnittstelle hält die daten vom simulator bereit, s. stsplugin-modul.
    - die anlage beschreibt das stellwerk, s. anlage-modul.
    - die planung enthält die aktuellen fahrplandaten, s. planung-modul.
    - die auswertung führt statistik über die zugbewegungen, s. auswertung-modul.

    die klasse implementiert methoden, die die plugin-schnittstelle abfragen
    und ereignisse vom simulator weiterleiten.
    die kommunikationsschleifen liegen jedoch ausserhalb dieser klasse.

    die klasse stellt für jedes modul eine observer-schnittstelle bereit,
    die registrierte beobachter nach einer aktualisierung benachrichtigen.
    """

    def __init__(self, config_path: Optional[os.PathLike] = None):
        self.config_path: os.PathLike = config_path
        self.client: Optional[PluginClient] = None
        self.anlage: Optional[Anlage] = None
        self.planung: Optional[Planung] = None
        self.auswertung: Optional[Auswertung] = None
        self.planung_update = Observable(self)
        self.anlage_update = Observable(self)
        self.auswertung_update = Observable(self)
        self.plugin_ereignis = Observable(self)

    async def update(self):
        """
        aktuelle daten von der plugin-schnittstelle abfragen und datenmodule aktualisieren.

        :return: None
        """

        await self._get_sts_data()
        for art in Ereignis.arten:
            await self.client.request_ereignis(art, self.client.zugliste.keys())

        if not self.anlage:
            self.anlage = Anlage(self.client.anlageninfo)
        self.anlage.update(self.client, self.config_path)

        if not self.planung:
            self.planung = Planung()

        if not self.auswertung:
            self.auswertung = Auswertung(self.anlage)
            self.planung.auswertung = self.auswertung

        self.planung.simzeit_minuten = time_to_minutes(self.client.calc_simzeit())
        self.planung.zuege_uebernehmen(self.client.zugliste.values())
        self.planung.einfahrten_korrigieren()
        self.planung.verspaetungen_korrigieren()

        self.auswertung.zuege_uebernehmen(self.client.zugliste.values())

        self.anlage_update.notify()
        self.planung_update.notify()
        self.auswertung_update.notify()

    async def _get_sts_data(self, alles=False):
        if alles or not self.client.anlageninfo:
            await self.client.request_anlageninfo()
        if alles or not self.client.bahnsteigliste:
            await self.client.request_bahnsteigliste()
        if alles or not self.client.wege:
            await self.client.request_wege()

        await self.client.request_zugliste()
        await self.client.request_zugdetails()
        await self.client.request_zugfahrplan()
        await self.client.resolve_zugflags()

        self.client.update_bahnsteig_zuege()
        self.client.update_wege_zuege()

    async def ereignis(self, ereignis):
        """
        ereignisdaten übernehmen.

        :param ereignis:
        :return:
        """

        if self.planung:
            self.planung.ereignis_uebernehmen(ereignis)
        if self.auswertung:
            self.auswertung.ereignis_uebernehmen(ereignis)

        self.plugin_ereignis.notify(ereignis=ereignis)
