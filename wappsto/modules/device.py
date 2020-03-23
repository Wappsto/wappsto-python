"""
The device module.

Stores attributes for the device instance and handles device-related
methods.
"""
import logging
import warnings
from ..connection import message_data
from ..errors import wappsto_errors


class Device:
    """
    Device instance class.

    Stores attributes for the device instance and handles device-related
    methods.
    """

    def __init__(
        self,
        parent,
        uuid,
        name,
        product,
        protocol,
        serial_number,
        version,
        manufacturer,
        communication,
        description
    ):
        """
        Initialize the Device class.

        Initializes an object of device class by passing required parameters.

        Args:
            parent: Reference to an object of network class
            uuid: Unique identifier of a device
            name: Name of a device
            product: Defines what a product is
            protocol: Protocol device communicates by
            serial_number: Serial number of a device
            version: Version of a device
            manufacturer: Defines who made a product
            communication: The way a device communicates
            description: Description of a device

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent = parent
        self.uuid = uuid
        self.name = name
        self.product = product
        self.serial_number = serial_number
        self.version = version
        self.manufacturer = manufacturer
        self.communication = communication
        self.protocol = protocol
        self.description = description
        self.values = []
        self.callback = None
        msg = "Device {} Debug: \n {}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

    def __getattr__(self, attr):  # pragma: no cover
        """
        Get attribute value.

        When trying to get value from value_list warning is raised about
        it being deprecated and calls values instead.

        Returns:
            values

        """
        if attr in ["value_list"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.values

    def get_parent_network(self):  # pragma: no cover
        """
        Retrieve parent network reference.

        Gets a reference to the network that owns this device.

        Returns:
            Reference to instance of Network class that owns this Device.

        """
        return self.parent

    def add_value(self, value):
        """
        Append value reference to the value list.

        Adds a value reference to the list of value references
        ("owned" values).

        Args:
            value: Reference to instance of Value class.

        """
        self.values.append(value)
        self.wapp_log.debug("Value {} has been added.".format(value))

    def get_value(self, value_name):
        """
        Retrieve child value reference.

        Gets a child Value class reference by the given name string.

        Args:
            value_name: String to search by in the list of values.

        Returns:
            Reference to instance of Value class.

        """
        for value in self.values:
            if value_name == value.name:
                return value
        else:
            msg = "Value {} not found".format(value_name)
            raise wappsto_errors.ValueNotFoundException(msg)

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
            network_id=self.parent.uuid,
            device_id=self.uuid
        )
        self.parent.conn.sending_queue.put(message)
        self.parent.devices.remove(self)
        self.wapp_log.info("Device removed")

    def __call_callback(self, event):
        if self.callback is not None:
            self.callback(self, event)
