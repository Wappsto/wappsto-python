"""
The state module.

Stores attributes for the state instance and handles device-related
"""
import logging
from ..connection import message_data
from ..errors import wappsto_errors


class State:
    """
    State instance class.

    Stores attributes for the state instance and handles device-related
    """

    def __init__(self, parent, uuid, state_type, timestamp, init_value):
        """
        Initialize the State class.

        Initializes an object of network class by passing required parameters.

        Args:
            parent: reference to a value object to which a state
                belongs to
            uuid: unique identifier of a state
            state_type: determines if the state is report or control
            timestamp: time of last update
            init_value: Initial value after creation of an object

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent = parent
        self.uuid = uuid
        self.state_type = state_type
        self.timestamp = timestamp
        self.callback = None

        self.init_value = init_value
        self.data = init_value

        msg = "State {} Debug: \n{}".format(uuid, str(self.__dict__))
        self.wapp_log.debug(msg)

    def get_parent_value(self):  # pragma: no cover
        """
        Retrieve parent value reference.

        Gets a reference to the value that owns this state.

        Returns:
            Reference to instance of value class that owns this state.

        """
        return self.parent

    def set_callback(self, callback):
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

    def handle_delete(self):
        """
        Handle delete.

        Calls the __call_callback method with initial input of "remove".

        Returns:
            result of __call_callback method.

        """
        self.__call_callback('remove')

    def delete(self):
        """
        Delete this object.

        Sends delete request for this object and removes its reference
        from parent.

        """
        message = message_data.MessageData(
            message_data.SEND_DELETE,
            network_id=self.parent.parent.parent.uuid,
            device_id=self.parent.parent.uuid,
            value_id=self.parent.uuid,
            state_id=self.uuid
        )
        self.parent.parent.parent.conn.sending_queue.put(message)
        if self == self.parent.report_state:
            self.parent.report_state = None
            self.wapp_log.info("Report state removed")
        elif self == self.parent.control_state:
            self.parent.control_state = None
            self.wapp_log.info("Control state removed")

    def __call_callback(self, event):
        if self.callback is not None:
            self.callback(self, event)
