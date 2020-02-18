"""
The state module.

Stores attributes for the state instance and handles device-related
"""
import logging
from .errors import wappsto_errors


class State:
    """
    State instance class.

    Stores attributes for the state instance and handles device-related
    """

    def __init__(self, parent_value, uuid, state_type, timestamp, init_value):
        """
        Initialize the State class.

        Initializes an object of network class by passing required parameters.

        Args:
            parent_value: reference to a value object to which a state
                belongs to
            uuid: unique identifier of a state
            state_type: determines if the state is report or control
            timestamp: time of last update
            init_value: Initial value after creation of an object

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent_value = parent_value
        self.uuid = uuid
        self.state_type = state_type
        self.timestamp = timestamp
        self.callback = None

        self.init_value = init_value
        self.data = init_value

        msg = "State {} Debug: \n{}".format(uuid, str(self.__dict__))
        self.wapp_log.debug(msg)

    def set_callback(self, callback):
        """
        Set the callback.

        Sets the callback attribute. It will be called by the __send_logic
        method.

        Args:
            callback: Callback reference.

        Raises:
            CallbackNotCallableException: Custom exception to signify invalid
            callback.

        """
        try:
            if not callable(callback):
                msg = "Callback method should be a method"
                raise wappsto_errors.CallbackNotCallableException(msg)
            self.callback = callback
            self.wapp_log.debug("Callback {} has been set.".format(callback))
            return True
        except wappsto_errors.CallbackNotCallableException as e:
            self.wapp_log.error("Error setting callback: {}".format(e))
            raise

    def handle_delete(self):
        """
        Handle delete.

        Calls the __call_callback method with initial input of "remove".

        Returns:
            result of __call_callback method.

        """
        return self.__call_callback('remove')

    def __call_callback(self, event):
        if self.callback is not None:
            return self.callback(self, event)
        return True
