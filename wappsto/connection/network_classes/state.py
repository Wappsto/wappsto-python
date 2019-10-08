"""
The state module.

Stores attributes for the state instance and handles device-related
"""
import logging


class State:
    """
    State instance class.

    Stores attributes for the state instance and handles device-related
    """

    def __init__(self, parent_value, uuid, state_type, timestamp):
        """
        Initialize the State class.

        Initializes an object of network class by passing required parameters.

        Args:
            parent_value: reference to a value object to which a state
                belongs to
            uuid: unique identifier of a state
            state_type: determines if the state is report or control
            timestamp: time of last update

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent_value = parent_value
        self.uuid = uuid
        self.state_type = state_type
        self.timestamp = timestamp
        msg = "State {} Debug: \n{}".format(uuid, str(self.__dict__))
        self.wapp_log.debug(msg)
