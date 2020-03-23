"""
The wappsto decoding module.

Handles decoding object instances from a JSON file.
"""
import logging
from ..modules import network as network_module
from ..modules import device as device_module
from ..modules import value as value_module
from ..modules import state as state_module


class WappstoDecoder:
    """
    The wappsto decoding class.

    Handles decoding JSON information into object instances. This
    allows the system to use the provided information.
    """

    def __init__(self):
        """
        Initialize WappstoDecoder.

        Initializes the WappstoDecoder class.
        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

    def decode_network(self, json_data, data_manager):
        """
        Decode instance of Network class.

        Handles the decoding of the network instance, contains a template to
        decode the network with.

        Args:
            json_data: Dictionary object from what data must be extracted.
            data_manager: Reference to the instance of the DataManager class.

        Returns:
            Network object.

        """
        network = network_module.Network(
            uuid=json_data.get('meta').get('id'),
            version=json_data.get('meta').get('version'),
            name=json_data.get('name'),
            devices=[],
            data_manager=data_manager
        )
        network.devices = self.decode_device(json_data, network)

        self.wapp_log.debug("Network {} built.".format(network))
        return network

    def decode_device(self, json_data, parent):
        """
        Decode instance of Device class.

        Handles the decoding of the device instance, contains a template to
        decode the device with.

        Args:
            json_data: Dictionary object used for data extraction.
            parent: Reference to the instance of the Network class.

        Returns:
            List of devices.

        """
        devices = []
        for device_iterator in json_data.get('device', []):
            device = device_module.Device(
                parent=parent,
                uuid=device_iterator.get('meta').get('id'),
                name=device_iterator.get('name'),
                product=device_iterator.get('product'),
                protocol=device_iterator.get('protocol'),
                serial_number=device_iterator.get('serial'),
                version=device_iterator.get('meta').get('version'),
                manufacturer=device_iterator.get('manufacturer'),
                communication=device_iterator.get('communication'),
                description=device_iterator.get('description')
            )
            device.values = self.decode_value(device_iterator, device)
            devices.append(device)

            self.wapp_log.debug("Device {} appended to {}".format(device, devices))
        return devices

    def decode_value(self, json_data, parent):
        """
        Decode instance of Value class.

        Handles the decoding of the value instance, contains a template to
        decode the value with.

        Args:
            json_data: Dictionary object used for data extraction.
            parent: Reference to the instance of the Device class.

        Returns:
            List of values.

        """
        values = []
        for value_iterator in json_data.get('value', []):
            data_type = None
            number_min = None
            number_max = None
            number_step = None
            number_unit = None
            string_encoding = None
            string_max = None
            blob_encoding = None
            blob_max = None

            if 'string' in value_iterator:
                data_type = 'string'
                string_encoding = value_iterator.get('string').get('encoding')
                string_max = value_iterator.get('string').get('max')
            elif 'blob' in value_iterator:
                data_type = 'blob'
                blob_encoding = value_iterator.get('blob').get('encoding')
                blob_max = value_iterator.get('blob').get('max')
            elif 'number' in value_iterator:
                data_type = 'number'
                number_min = value_iterator.get('number').get('min')
                number_max = value_iterator.get('number').get('max')
                number_step = value_iterator.get('number').get('step')
                number_unit = value_iterator.get('number').get('unit')

            value = value_module.Value(
                parent=parent,
                uuid=value_iterator.get('meta').get('id'),
                name=value_iterator.get('name'),
                type_of_value=value_iterator.get('type'),
                data_type=data_type,
                permission=value_iterator.get('permission'),
                number_max=number_max,
                number_min=number_min,
                number_step=number_step,
                number_unit=number_unit,
                string_encoding=string_encoding,
                string_max=string_max,
                blob_encoding=blob_encoding,
                blob_max=blob_max,
                period=value_iterator.get('period', None),
                delta=value_iterator.get('delta', None)
            )
            for state in self.decode_state(value_iterator, value):
                if state.state_type == 'Report':
                    value.add_report_state(state)
                elif state.state_type == 'Control':
                    value.add_control_state(state)
            values.append(value)

            self.wapp_log.debug("Value {} appended to {}".format(value, values))
        return values

    def decode_state(self, json_data, parent):
        """
        Decode instance of State class.

        Handles the decoding of the state instance, contains a template to
        decode the state with.

        Args:
            json_data: Dictionary object used for data extraction.
            parent: Reference to the instance of the Value class.

        Returns:
            List of states.

        """
        states = []
        for state_iterator in json_data.get('state', []):
            state = state_module.State(
                parent=parent,
                uuid=state_iterator.get('meta').get('id'),
                state_type=state_iterator.get('type'),
                timestamp=state_iterator.get('timestamp'),
                init_value=state_iterator.get('data')
            )
            states.append(state)
        return states
