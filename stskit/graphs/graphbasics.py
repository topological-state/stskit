import logging
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, TypeVar, Union


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


T = TypeVar('T')


def dict_property(name: str, T, docstring: str = None):
    """
    Generic factory function for a property that corresponds to a dictionary value.

    The owning class must be a subclass of dict.

    :param name: The name of the property.
    :param T: The type of the property.
    :param docstring: The docstring of the property.
    """
    def getter(self) -> T:
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(f"Attribut {name} hat keinen definierten Wert.") from e

    def setter(self, value: T):
        self[name] = value

    def deleter(self):
        try:
            del self[name]
        except KeyError:
            pass

    return property(getter, setter, deleter, doc=docstring)
