from collections.abc import Set
import json
from typing import Any, Dict, List, Optional, Set, Union

from stsobj import AnlagenInfo, BahnsteigInfo, Knoten


beispiel = {'Othmarsingen': {'Othmarsingen 502', 'Othmarsingen 602'},
            'Turgi': {'Turgi 1', 'Turgi 2'}}


class JSONEncoder(json.JSONEncoder):
    """
    translate non-standard objects to JSON objects.

    currently implemented: Set.

    ~~~~~~{.py}
    encoded = json.dumps(data, cls=JSONEncoder)
    decoded = json.loads(encoded, object_hook=json_object_hook)
    ~~~~~~
    """

    def default(self, obj):
        if isinstance(obj, Set):
            return dict(__class__='Set', data=list(obj))
        else:
            return super().default(obj)


def json_object_hook(d):
    if '__class__' in d and d['__class__'] == 'Set':
        return set(d['data'])
    else:
        return d


class StsConfig:
    def __init__(self, anlage: AnlagenInfo):
        self.anlage = anlage
        self.auto = True
        self._data = {'einfahrtsgruppen': dict(),
                      'ausfahrtsgruppen': dict(),
                      'bahnsteigsgruppen': dict()}

    @property
    def einfahrtsgruppen(self):
        """
        gruppierung von sts-einfahrten
        :return: dictionary gruppenname -> set of (knotenname)
        """
        return self._data['einfahrtsgruppen']

    @property
    def ausfahrtsgruppen(self):
        """
        gruppierung von sts-ausfahrten
        :return: dictionary gruppenname -> set of (knotenname)
        """
        return self._data['ausfahrtsgruppen']

    @property
    def bahnsteigsgruppen(self):
        """
        gruppierung von sts-einfahrten
        :return: dictionary gruppenname -> set of (knotenname)
        """
        return self._data['bahnsteigsgruppen']

    def suche_gleisgruppe(self, gleis: str, gruppen: Dict) -> Optional[str]:
        for name, gruppe in gruppen.items():
            if gleis in gruppe:
                return name
        return None

    def auto_config(self, sts_client):
        """
        bestimmt die gruppen basierend auf anlageninfo und ueblicher schreibweise der gleisnamen.

        einfahrten und ausfahrten werden nach dem ersten namensteil gruppiert.
        der erste namensteil wird zum gruppennamen.

        bahnsteige werden nach nachbarn gemäss anlageninfo gruppiert.
        da es keine einheitlichen muster für gleis- und gruppennamen gibt,
        erhalten die gruppen den namen eines ihrer gleise.

        :param sts_client:
        :return: None
        """
        self.anlage = sts_client.anlageninfo

        for k in sts_client.wege_nach_typ[Knoten.TYP_NUMMER['Einfahrt']]:
            try:
                gr = k.name.split(' ')[0]
            except IndexError:
                pass
            else:
                try:
                    self._data['einfahrtsgruppen'][gr].add(k.name)
                except KeyError:
                    self._data['einfahrtsgruppen'][gr] = {k.name}
                try:
                    self._data['ausfahrtsgruppen'][gr].add(k.name)
                except KeyError:
                    self._data['ausfahrtsgruppen'][gr] = {k.name}

        for k in sts_client.wege_nach_typ[Knoten.TYP_NUMMER['Ausfahrt']]:
            try:
                gr = k.name.split(' ')[0]
            except IndexError:
                pass
            else:
                try:
                    self._data['einfahrtsgruppen'][gr].add(k.name)
                except KeyError:
                    self._data['einfahrtsgruppen'][gr] = {k.name}
                try:
                    self._data['ausfahrtsgruppen'][gr].add(k.name)
                except KeyError:
                    self._data['ausfahrtsgruppen'][gr] = {k.name}

        def add_nachbarn(gruppe: Set, bahnsteig: BahnsteigInfo, bahnsteigliste: Dict) -> Set:
            gruppe.add(bahnsteig.name)
            del bahnsteigliste[bahnsteig.name]
            for n in bahnsteig.nachbarn:
                try:
                    gruppe = add_nachbarn(gruppe, bahnsteigliste[n], bahnsteigliste)
                except KeyError:
                    gruppe.add(n)

            return gruppe

        bsl = dict(sts_client.bahnsteigliste)
        while bsl:
            bs = bsl[next(iter(bsl))]
            gr = add_nachbarn(set(), bs, bsl)
            self._data['bahnsteigsgruppen'][bs.name] = gr

    def load(self, path):
        """

        :param path:
        :return:
        :raise: OSError, JSONDecodeError(ValueError)
        """
        with open(path) as fp:
            d = json.load(fp, object_hook=json_object_hook)
        try:
            self._data = d[str(self.anlage.aid)]
        except KeyError:
            pass
        else:
            self.auto = False

    def save(self, path):
        try:
            with open(path) as fp:
                d = json.load(fp, object_hook=json_object_hook)
        except (OSError, json.decoder.JSONDecodeError):
            d = dict()

        if self._data:
            aid = str(self.anlage.aid)
            d[aid] = self._data
            d[aid]['_region'] = self.anlage.region
            d[aid]['_name'] = self.anlage.name
            d[aid]['_build'] = self.anlage.build

            with open(path, "w") as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)
