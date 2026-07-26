import logging
from typing import TypeVar


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


T = TypeVar('T')


def dict_property(
        name: str,
        type_: type[T],
        docstring: str | None = None,
    ) -> property:
    """
    Generic factory function for a property that corresponds to a dictionary value.

    The owning class must be a subclass of dict.

    Args:
        name: The name of the property.
        type_: The type of the property.
        docstring: The docstring of the property.
    """

    def getter(self) -> T:
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(f"Attribut {name} hat keinen definierten Wert.\n{str(self)}") from e

    def setter(self, value: T):
        self[name] = value

    def deleter(self):
        try:
            del self[name]
        except KeyError:
            pass

    return property(getter, setter, deleter, doc=docstring)
