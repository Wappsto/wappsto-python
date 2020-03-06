"""
The network module.

Stores attributes for the network instance.
"""
import logging
from .. import message_data
from .errors import wappsto_errors


class Network:
    """
    Network instance class.

    Stores attributes for the network instance.
    """

    def __init__(self, uuid, version, name, devices, instance):
        """
        Initialize the Network class.

        Initializes an object of network class by passing required parameters.

        Args:
            uuid: Unique identifier of a network
            version: Version of a network
            name: Name of a network
            devices: list of devices in network
            instance: Instance of Instantiator

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.uuid = uuid
        self.version = version
        self.name = name
        self.devices = devices
        self.instance = instance
        self.rpc = None
        self.conn = None
        self.callback = None
        msg = "Network {} Debug \n{}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

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
        return self.__call_callback('remove')

    def delete(self):
        """
        Delete this object.

        Sends delete request for this object and removes its reference
        from parent.

        """
        message = message_data.MessageData(
            message_data.SEND_DELETE,
            network_id=self.uuid,
        )
        self.conn.sending_queue.put(message)
        self.instance.network = None
        self.wapp_log.info("Network removed")

    def __call_callback(self, event):
        if self.callback is not None:
            return self.callback(self, event)
        return True
