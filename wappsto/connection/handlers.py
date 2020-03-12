"""
Receive and send handling module.

Handles building sending and receiving data messages and adding them to the
sending queue.
"""
import logging

class Handlers:
    """
    Message data handlers.

    Processes incoming and outgoing PUT, POST and GET messages.
    """

    def __init__(self, instance):
        """
        Initialize the Handler class.

        Create an instance of the Handlers class to handle incoming and
        outgoing communication with the server.

        Args:
            instance: Reference to the object instance class.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.instance = instance

    def get_by_id(self, id):
        """
        Wappsto get by id.

        Retrieves the instance of a class if its id matches the provided one

        Args:
            id: unique identifier used for searching

        Returns:
            A reference to the network/device/value/state object instance.

        """
        message = "Found instance of {} object with id: {}"
        if self.instance.network is not None:
            if self.instance.network.uuid == id:
                self.wapp_log.debug(message.format("network", id))
                return self.instance.network

            for device in self.instance.network.devices:
                if device.uuid == id:
                    self.wapp_log.debug(message.format("device", id))
                    return device

                for value in device.values:
                    if value.uuid == id:
                        self.wapp_log.debug(message.format("value", id))
                        return value

                    if value.control_state is not None and value.control_state.uuid == id:
                        self.wapp_log.debug(message.format("control state", id))
                        return value.control_state

                    if value.report_state is not None and value.report_state.uuid == id:
                        self.wapp_log.debug(message.format("report state", id))
                        return value.report_state

        self.wapp_log.warning("Failed to find object with id: {}".format(id))
