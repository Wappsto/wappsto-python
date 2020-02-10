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


STARTING = "Starting"
INSTANTIATING = "Instantiating"
CONNECTING = "Connecting"
RECONNECTING = "Reconnecting"
CONNECTED = "Connected"
INITIALIZING = "Initializing"
STARTING_THREADS = "Starting Threads"
RUNNING = "Running"
DISCONNECTING = "Disconnecting"


class Status:
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
        self.callback = None
        self.current_status = None

    def set_callback(self, callback):
        """
        Set callback reference.

        Sets the reference to the method to the balled whenever the status
        is changed.

        Args:
            callback: Function callback reference.

        """
        self.callback = callback
        self.wapp_log.debug("Callback {} has been set.".format(callback))

    def get_status(self):
        """
        Retrieve current status.

        Retrieves the class' current_status attribute.

        Returns:
            Current status attribute.

        """
        return self.current_status

    def set_status(self, status):
        """
        Set the current status.

        Sets the current status from the global attribute states.

        Args:
            status: Status global attribute.

        """
        self.current_status = status
        if self.callback is not None:
            self.callback(self)
