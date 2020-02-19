"""
The device module.

Stores attributes for the device instance and handles device-related
methods.
"""
import logging
from .errors import wappsto_errors


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
        self.value_list = []
        self.callback = None
        msg = "Device {} Debug: \n {}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

    def get_parent_network(self):
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
        self.value_list.append(value)
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
        for value in self.value_list:
            if value_name in list(value.__dict__.values()):
                return value
            else:
                msg = "Value {} not found".format(value_name)
                wappsto_errors.ValueNotFoundException(msg)

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
