"""
The network module.

Stores attributes for the network instance.
"""
import logging

from typing import Callable
from typing import Generic
from typing import Literal
from typing import Optional
from typing import Type
from typing import TypeVar
from typing import Union

import wappsto.modules
from wappsto.status import EventType

from wappsto.connection import message_data
from wappsto.errors import wappsto_errors

Network_cls = TypeVar('Network_cls', bound='Network')


class Network(Generic[Network_cls]):
    """
    Network instance class.

    Stores attributes for the network instance.
    """

    def __init__(self, uuid, version, name, devices, data_manager):
        """
        Initialize the Network class.

        Initializes an object of network class by passing required parameters.

        Args:
            uuid: Unique identifier of a network
            version: Version of a network
            name: Name of a network
            devices: list of devices in network
            data_manager: Instance of DataManager

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.uuid = uuid
        self.version = version
        self.name = name
        self.devices = devices
        self.data_manager = data_manager
        self.rpc = None
        self.conn = None
        self.callback: Optional[Callable[[Type[Network_cls], str], None]] = None
        msg = "Network {} Debug \n{}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

    def set_callback(
        self,
        callback: Callable[[Type[Network_cls], str], None]
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

    def get_device(self, name: str) -> wappsto.modules.device.Device:
        """
        Device reference.

        Finds the device with a specific name attribute based on a given
        string

        Args:
            name: String containing the name attribute to search for.

        Returns:
            A reference to the device object instance.

        Raises:
            DeviceNotFoundException: Device {name} not found.

        """
        for device in self.devices:
            if name == device.name:
                return device
        else:
            msg = "Device {} not found".format(name)
            raise wappsto_errors.DeviceNotFoundException(msg)

    def handle_delete(self) -> None:
        """
        Handle delete.

        Calls the __call_callback method with initial input of "remove".

        Returns:
            result of __call_callback method.

        """
        self.__call_callback(EventType.REMOVE)

    def delete(self) -> None:
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
        self.data_manager.network = None
        self.wapp_log.info("Network removed")

    def __call_callback(self, event: EventType) -> None:
        """Callingt the callback function, if needed."""
        if self.callback is not None:
            self.callback(self, event)
