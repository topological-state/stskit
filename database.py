from collections.abc import Set
import json
from model import AnlagenInfo, BahnsteigInfo, Knoten


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
    def __init__(self, aid):
        self.aid = aid
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

    def suche_gleisgruppe(self, gleis, gruppen):
        for name, gruppe in gruppen.items():
            if gleis in gruppe:
                return name
        return None

    def auto_config(self, sts_client):
        """
        bestimmt die gruppen basierend auf anlageninfo und ueblicher schreibweise der gleisnamen.

        einfahrten und ausfahrten werden nach dem ersten namensteil gruppiert.
        der erste namensteil wird zum gruppennanen.

        bahnsteige werden nach nachbarn gemaess anlageninfo gruppiert.
        da es keine einheitlichen regeln gibt, werden die gruppennamen durchnummeriert.

        :param sts_client:
        :return: None
        """
        self.aid = sts_client.anlageninfo.aid

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

        d = dict()
        for _, bs in sts_client.bahnsteigliste.items():
            key = ",".join(sorted(bs.nachbarn))
            try:
                d[key].add(bs.name)
            except KeyError:
                d[key] = {bs.name}
        for i, gr in enumerate(d.values()):
            self._data['bahnsteigsgruppen'][f'Gruppe {i}'] = gr

    def load(self, path):
        """

        :param path:
        :return:
        :raise: OSError, JSONDecodeError(ValueError)
        """
        with open(path) as fp:
            d = json.load(fp, object_hook=json_object_hook)
        try:
            self._data = d[self.aid]
        except KeyError:
            pass
        else:
            self.auto = False

    def save(self, path):
        try:
            with open(path) as fp:
                d = json.load(fp, object_hook=json_object_hook)
        except OSError:
            d = dict()

        if self._data:
            d[self.aid] = self._data
            with open(path, "w") as fp:
                json.dump(d, fp, sort_keys=True, indent=4, cls=JSONEncoder)


class StsDatenbank:
    def __init__(self, aid):
        self.aid = aid
        self.daten = None