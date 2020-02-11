"""
The wappsto Encoding module.

Handles encoding object instances to a JSON file for the purpose of saving
them and any modifications made to them.
"""
import logging
from ..connection.seluxit_rpc import SeluxitRpc


class WappstoEncoder:
    """
    The wappsto encoding class.

    Handles encoding the current runtime object instances into JSON. This
    allows the system to be saved as a parsable JSON file similar to the one
    used to start the package.
    """

    def __init__(self):
        """
        Initialize WappstoEncoding.

        Initializes the WappstoEncoding class, which handles encoding the
        various parts of the system into a JSON file.
        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

    def encode(self, instance):
        """
        Encode instance.

        Encodes objects from the runtime instances and returns the result so
        it can be saved.

        Args:
            instance: Reference to the instance class that holds the object
                instances.

        Returns:
            An encoded JSON result.

        """
        encoded_devices = []
        for device in instance.device_list:
            encoded_device = self.encode_device(device)
            encoded_devices.append(encoded_device)

        encoded_network = {
            'name': instance.network_cl.name,
            'device': encoded_devices,
            'meta': {
                'id': instance.network_cl.uuid,
                'version': '2.0',
                'type': 'network'
            }
        }

        if SeluxitRpc.is_upgradable():
            encoded_network.get('meta').update({'upgradable': True})

        self.wapp_log.debug("Network JSON: {}".format(encoded_network))

        return encoded_network

    def encode_device(self, device):
        """
        Encode instance of Device class.

        Handles the encondoing of the device instance, contains a template to
        encode the device with.

        Args:
            device: Reference to the instance of the Device class.

        Returns:
            The encoded JSON result.

        """
        encoded_values = []
        for value in device.value_list:
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

        Handles the encodoing of the value instance, contains a template to
        encode the value with.

        Args:
            value: Reference to the instance of the Value class.

        Returns:
            The encoded JSON result.

        """
        states = []
        if value.report_state:
            encoded_state = self.encode_state(
                value.report_state,
                value.init_value
            )
            states.append(encoded_state)

        if value.control_state:
            encoded_state = self.encode_state(
                value.control_state,
                value.init_value
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
                'max': value.string_max
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

    def encode_state(self, state, last_controlled):
        """
        Encode instance of State class.

        Handles the encodoing of the value instance, contains a template to
        encode the value with.

        Args:
            state: Reference to the instance of the State class.
            last_controlled: The data in the State.

        Returns:
            The encoded JSON result.

        """
        encoded_state = {
            'data': last_controlled,
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
