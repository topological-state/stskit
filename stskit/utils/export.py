import json
import logging

import networkx as nx

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
        if isinstance(obj, frozenset):
            return dict(__class__='frozenset', data=list(obj))
        if isinstance(obj, nx.Graph):
            return "networkx.Graph"
        else:
            return super().default(obj)


def json_object_hook(d):
    if '__class__' in d and d['__class__'] == 'Set':
        return set(d['data'])
    else:
        return d


def replace_non_ascii(text):
    """Replaces non-ASCII characters in the given text with their ASCII counterparts."""
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'é': 'e', 'É': 'E',
        'ç': 'c', 'Ç': 'C', 'ñ': 'n', 'Ñ': 'N',
        'ø': 'o', 'Ø': 'O', 'å': 'a', 'Å': 'A',
        'í': 'i', 'Í': 'I', 'ó': 'o', 'Ó': 'O',
        'à': 'a', 'À': 'A', 'è': 'e', 'È': 'E',
        'ò': 'o', 'Ò': 'O', 'ù': 'u', 'Ù': 'U',
        'ï': 'i', 'Ï': 'I', 'ë': 'e', 'Ë': 'E',
        'ß': 'ss'
    }

    # Create a translation table
    translation_table = str.maketrans(replacements)

    # Replace non-ASCII characters with ASCII counterparts
    ascii_text = text.translate(translation_table)

    return ascii_text


def write_gml(graph, filename, stringizer=str):
    """
    Writes a networkx graph to a gml file.

    Non-ASCII characters in node labels are replaced with ASCII counterparts.
    The file cannot be used to re-create the original graph!
    """

    graph = nx.relabel_nodes(graph, {node: replace_non_ascii(str(node)) for node in graph.nodes()}, copy=True)
    try:
        nx.write_gml(graph, filename, stringizer=stringizer)
    except UnicodeEncodeError as e:
        logger.error(f"Fehler beim Schreiben des GML-Files: {e}")
