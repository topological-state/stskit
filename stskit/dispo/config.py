from collections import UserDict
import json
from jsonschema import validate, ValidationError
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from stskit.model.bahnhofgraph import BahnhofGraph, BahnhofElement
from stskit.utils.export import json_object_hook

logger = logging.getLogger(__name__)


class Config(UserDict):
    """
    Konfiguration

    Das Konfigurationsobjekt ist im wesentlichen ein Dictionary mit dem gleichen Schema wie die JSON-Datei, Version 3.
    Es stellt zudem Methoden und Properties bereit, die den Umgang mit den Daten vereinfachen,
    insbesondere einen Import aus Version 2.
    """

    def __init__(self, dict=None, /, **kwargs):
        super().__init__(dict=dict, **kwargs)
        self.loaded_from: Optional[Path] = None
        self._bahnhofelemente = {}
        self.schema_path: Optional[Path] = None
        self.schema: Optional[Dict] = None

    def load(self, path: Path, aid: int = None):
        """
        Konfigurationsdatei laden.

        Die Methode kann Konfigurationsdateien in den Versionen 2 und 3 laden.

        :param path: Pfad der Konfigurationsdatei.
        :return: None
        :raise: OSError, JSONDecodeError(ValueError)
        """

        with open(path, 'r', encoding='utf-8') as fp:
            d = json.load(fp)

        if '_version' not in d:
            d['_version'] = 1
            logger.warning(f"Konfigurationsdatei {path} ohne Versionsangabe, nehme 1 an.")

        if aid is not None and d['_aid'] != aid:
            logger.error(f"Inkompatible Anlangen-ID {d['_aid']} statt {aid}.")
            return

        if d['_version'] == 2:
            self.load_v2(path)
        elif d['_version'] == 3:
            self.load_v3(path)
        else:
            logger.error(f"Inkompatible Konfigurationsdatei {path}, wird ignoriert.")

    def save(self, path: Path):
        self.save_v3(path)

    def load_v2(self, path: Path):
        with open(path, 'r', encoding='utf-8') as fp:
            d = json.load(fp, object_hook=json_object_hook)

        self.import_v2(d)
        self.loaded_from = path
        logger.info(f"Konfiguration geladen. Version 2.")

    def load_v3(self, path: Path):
        if not self.schema_path:
            self.schema_path = Path(__file__).parent.parent / 'schema' / 'config.schema3.json'
        with open(self.schema_path, 'r', encoding='utf-8') as fp:
            self.schema = json.load(fp)
        with open(path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)

        try:
            validate(data, schema=self.schema)
        except ValidationError as e:
            logger.error(e)
            print(f"Fehlerhafte Konfigurationsdatei {path}: {e}", file=sys.stderr)
        else:
            self.clear()
            self.update(data)
            self.loaded_from = path
            logger.info(f"Konfiguration geladen. "
                        f"Version {self.get('_version')}, "
                        f"Anlage {self.get('_aid')}, "
                        f"Build {self.get('_build')}, "
                        f"Name {self.get('_name')}, "
                        f"Region {self.get('_region')}")

    def save_v3(self, path: Path):
        self.data['_version'] = 3
        data = dict(self.data)
        if 'dict' in data:
            logger.debug("'dict' Element in Konfiguration.")
            del data['dict']
        with open(path, "w", encoding='utf-8') as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)

    def import_v2(self, d: Dict):
        """
        Konfigurationsdaten im Format der Version 2 laden.

        :param d:
        :return:
        """

        def _find_sektor(gleis: str, sektoren_gleise: Dict) -> Optional[str]:
            for bahnsteig, gleise in sektoren_gleise.items():
                if gleis in gleise:
                    return bahnsteig
            else:
                return None

        def _find_bahnhofelement(_name: str) -> Optional[BahnhofElement]:
            if (_be := BahnhofElement('Anst', _name)) in elemente:
                return _be
            elif (_be := BahnhofElement('Bf', _name)) in elemente:
                return _be

        gleis_konfig = {}
        try:
            sektoren = d['sektoren']
        except KeyError:
            logger.info("Fehlende Sektoren-Konfiguration")
            sektoren = {}

        try:
            for bft, gleise in d['bahnsteiggruppen'].items():
                bf = bft
                for gl in gleise:
                    if bf not in gleis_konfig:
                        gleis_konfig[bf] = {bft: {}}
                    bs = _find_sektor(gl, sektoren)
                    if not bs:
                        bs = gl
                    try:
                        gleis_konfig[bf][bft][bs].add(gl)
                    except KeyError:
                        gleis_konfig[bf][bft][bs] = {gl}
        except KeyError:
            logger.info("Fehlende Bahnsteiggruppen-Konfiguration")

        try:
            anschluss_konfig = d['anschlussgruppen']
        except KeyError:
            logger.info("Fehlende Anschlussgruppen-Konfiguration")
            anschluss_konfig = {}

        self.clear()
        self.data["default"] = False

        elemente = {}
        for bf, bf_dict in gleis_konfig.items():
            for bft, bft_dict in bf_dict.items():
                for bs, bs_set in bft_dict.items():
                    for gl in bs_set:
                        elemente[BahnhofElement('Bf', bf)] = {"name": bf, "typ": "Bf", "sichtbar": True, "flags": "", "auto": False}
                        elemente[BahnhofElement('Bft', bft)] = {"name": bft, "typ": "Bft", "stamm": bf, "sichtbar": True, "flags": "", "auto": False}
                        elemente[BahnhofElement('Bs', bs)] = {"name": bs, "typ": "Bs", "stamm": bft, "sichtbar": True, "flags": "", "auto": False}
                        elemente[BahnhofElement('Gl', gl)] = {"name": gl, "typ": "Gl", "stamm": bs, "sichtbar": True, "flags": "", "auto": False}

        for anst, anst_set in anschluss_konfig.items():
            for agl in anst_set:
                elemente[BahnhofElement("Anst", anst)] = {"name": anst, "typ": "Anst", "sichtbar": True, "flags": "", "auto": False}
                elemente[BahnhofElement("Agl", agl)] = {"name": agl, "typ": "Agl", "stamm": anst, "sichtbar": True, "flags": "", "auto": False}

        self.data['elemente'] = elemente.values()

        strecken = {}
        try:
            hauptstrecke = d['hauptstrecke']
        except KeyError:
            logger.info("Keine Hauptstrecke konfiguriert")
            hauptstrecke = ""

        try:
            for name, strecke in d['strecken'].items():
                if not name:
                    continue
                stations = []
                for st in strecke:
                    if be := _find_bahnhofelement(st):
                        stations.append(str(be))
                strecken[name] = {"name": name, "ordnung": 1 if name == hauptstrecke else 9, "stationen": stations}
        except KeyError:
            logger.info("Fehlende Streckenkonfiguration")
        else:
            self.data['strecken'] = strecken.values()

        try:
            markierungen = d['streckenmarkierung']
        except KeyError:
            logger.info("Keine Streckenmarkierungen konfiguriert")
            markierungen = []

        streckenmarkierung = {}
        for markierung in markierungen:
            try:
                station1 = _find_bahnhofelement(markierung[0])
                station2 = _find_bahnhofelement(markierung[1])
                flags = markierung[2]
            except IndexError:
                pass
            else:
                if station1 and station2 and flags:
                    streckenmarkierung[(station1, station2)] = {"station1": str(station1), "station2": str(station2), "flags": flags}
        self.data['streckenmarkierung'] = streckenmarkierung.values()

        try:
            self.data['zugschema'] = d['zugschema']
        except KeyError:
            logger.info("Keine Zugschema konfiguriert")
