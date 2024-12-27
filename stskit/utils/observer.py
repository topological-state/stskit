import logging
from typing import Any, Optional
import weakref

logger = logging.getLogger(__name__)

class Observable:
    """
    Notify observers of events.

    - Observers are bound methods of object instances.
    - The object keeps weak references - observers don't need to unregister.
    - The triggered attribute can be used to defer the notification call to a separate processing loop.
    """

    def __init__(self, owner: Any):
        self.owner = owner
        self.triggered = False
        self._observers = weakref.WeakKeyDictionary()

    def register(self, observer):
        """
        Register an observer

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

    def trigger(self):
        """
        Set the triggered attribute.

        This can be used to signal to the main loop that the observers should be notified.
        The triggered flag is reset when the notify method is called.
        """

        self.triggered = True

    def notify(self, *args, **kwargs):
        """
        Notify observers

        The first two positional arguments sent to the observers are the instance of observable and the owner.
        The remaining arguments are copied from the call arguments.

        :param args: Positional arguments to be passed to the observers.
        :param kwargs: Keyword arguments to be passed to the observers
        :return: None
        """

        self.triggered = False
        for obs, name in self._observers.items():
            meth = getattr(obs, name)  # bound method
            meth(self, *args, **kwargs)
