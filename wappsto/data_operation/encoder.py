"""
The wappsto encoding module.

Handles encoding object instances to a JSON file.
"""
import logging
from ..connection import seluxit_rpc


class WappstoEncoder:
    """
    The wappsto encoding class.

    Handles encoding the current runtime object instances into JSON. This
    allows the system to be saved as a parsable JSON file similar to the one
    used to start the package.
    """

    def __init__(self):
        """
        Initialize WappstoEncoder.

        Initializes the WappstoEncoder class.
        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

    def encode_network(self, network):
        """
        Encode instance of Network class.

        Handles the encoding of the network instance, contains a template to
        encode the network with.

        Args:
            network: Reference to the instance of the Network class.

        Returns:
            The dictionary.

        """
        encoded_devices = []
        for device in network.devices:
            encoded_device = self.encode_device(device)
            encoded_devices.append(encoded_device)

        encoded_network = {
            'name': network.name,
            'device': encoded_devices,
            'meta': {
                'id': network.uuid,
                'version': '2.0',
                'type': 'network'
            }
        }

        if seluxit_rpc.is_upgradable():
            encoded_network.get('meta').update({'upgradable': True})

        self.wapp_log.debug("Network JSON: {}".format(encoded_network))
        return encoded_network

    def encode_device(self, device):
        """
        Encode instance of Device class.

        Handles the encoding of the device instance, contains a template to
        encode the device with.

        Args:
            device: Reference to the instance of the Device class.

        Returns:
            The dictionary.

        """
        encoded_values = []
        for value in device.values:
            encoded_value = self.encode_value(value)
            encoded_values.append(encoded_value)

        encoded_device = {
            'name': device.name,
            'product': device.product,
            'protocol': device.protocol,
            'serial': device.serial_number,
            'manufacturer': device.manufacturer,
            'communication': device.communication,
            'description': device.description,
            'version': device.version,
            'value': encoded_values,
            'meta':
            {
                'id': device.uuid,
                'version': '2.0',
                'type': 'device'
            }
        }

        self.wapp_log.debug("Device JSON: {}".format(encoded_device))
        return encoded_device

    def encode_value(self, value):
        """
        Encode instance of Value class.

        Handles the encoding of the value instance, contains a template to
        encode the value with.

        Args:
            value: Reference to the instance of the Value class.

        Returns:
            The dictionary.

        """
        states = []
        if value.report_state:
            encoded_state = self.encode_state(
                value.report_state
            )
            states.append(encoded_state)

        if value.control_state:
            encoded_state = self.encode_state(
                value.control_state
            )
            states.append(encoded_state)

        if value.data_type == 'string':
            details = {
                'encoding': value.string_encoding,
                'max': value.string_max
            }
        elif value.data_type == 'blob':
            details = {
                'encoding': value.blob_encoding,
                'max': value.blob_max
            }
        elif value.data_type == 'number':
            details = {
                'min': value.number_min,
                'max': value.number_max,
                'step': value.number_step,
                'unit': value.number_unit
            }

        encoded_value = {
            'name': value.name,
            'type': value.type_of_value,
            'permission': value.permission,
            'state': states,
            value.data_type: details,
            'meta':
            {
                'id': value.uuid,
                'type': 'value',
                'version': '2.0'
            }
        }

        self.wapp_log.debug("Value JSON: {}".format(encoded_value))
        return encoded_value

    def encode_state(self, state):
        """
        Encode instance of State class.

        Handles the encoding of the state instance, contains a template to
        encode the state with.

        Args:
            state: Reference to the instance of the State class.

        Returns:
            The dictionary.

        """
        encoded_state = {
            'data': state.data,
            'type': state.state_type,
            'timestamp': state.timestamp,
            'meta':
            {
                'id': state.uuid,
                'type': 'state',
                'version': '2.0',
                'contract': []
            }
        }

        self.wapp_log.debug("State JSON: {}".format(encoded_state))
        return encoded_state
