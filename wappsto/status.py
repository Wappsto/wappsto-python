"""
Status module for the wappsto module.

Status module to keep track of what the module status is.

Attributes:
    STARTING: Starting phase status.
    INSTANTIATING: Instantiating phase status.
    CONNECTING: Connecting phase status.
    RECONNECTING: Reconnecting phase status.
    CONNECTED: Connected phase status.
    INITIALIZING: Initializing phase status.
    STARTING_THREADS: Thread starting phase status.
    RUNNING: Running phase status.
    DISCONNECTING: Disconnecting phase status.

"""
import logging

from enum import Enum
from typing import Generic
from typing import Literal
from typing import Type
from typing import Optional
from typing import TypeVar
from typing import Callable

from wappsto.errors import wappsto_errors


# TODO(MBK): Deprecate it.
# import warnings
# warnings.warn("Property %s is deprecated" % attr)
STARTING = "Starting"
CONNECTING = "Connecting"
CONNECTED = "Connected"
INITIALIZING = "Initializing"
STARTING_THREADS = "Starting Threads"
RUNNING = "Running"
RECONNECTING = "Reconnecting"
DISCONNECTING = "Disconnecting"


class StatusType(str, Enum):
    """All the Wappsto Status type states, it can be in."""
    STARTING = "Starting"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    INITIALIZING = "Initializing"
    STARTING_THREADS = "Starting Threads"
    RUNNING = "Running"
    RECONNECTING = "Reconnecting"
    DISCONNECTING = "Disconnecting"


# TODO(MBK): Make use of the Event Enum.
class EventType(str, Enum):
    """All the Event types for modules."""
    REFRESH = 'refresh'
    REMOVE = 'remove'
    SET = 'set'


Status_cls = TypeVar('Status_cls', bound='Status')


class Status(Generic[Status_cls]):
    """
    Status tracking class.

    Tracks the status of the wappsto module through global variables that are
    changed at runtime.
    """

    def __init__(self):
        """
        Initialize the Status class.

        Initializes the Status class, which handles changing the program's
        status flag.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.callback: Optional[Callable[[Status_cls], None]] = None
        self.current_status: StatusType

    def set_callback(
        self,
        callback: Callable[[Status_cls], None]
    ) -> Literal[True]:
        """
        Set the callback.

        Sets the callback attribute.

        Args:
            callback: Callback reference.

        Raises:
            CallbackNotCallableException: Custom exception to signify invalid
            callback.

        """
        if not callable(callback):
            msg = "Callback method should be a method"
            self.wapp_log.error("Error setting callback: {}".format(msg))
            raise wappsto_errors.CallbackNotCallableException
        self.callback = callback
        self.wapp_log.debug("Callback {} has been set.".format(callback))
        return True

    def get_status(self) -> StatusType:
        """
        Retrieve current status.

        Retrieves the class' current_status attribute.

        Returns:
            Current status attribute.

        """
        return self.current_status

    def set_status(self, status: StatusType) -> None:
        """
        Set the current status.

        Sets the current status from the global attribute states.

        Args:
            status: Status global attribute.

        """
        self.current_status = status
        if self.callback is not None:
            self.callback(self)
