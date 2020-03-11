import logging
from ..modules import network as network_module
from ..modules import device as device_module
from ..modules import value as value_module
from ..modules import state as state_module


class WappstoDecoder:

    def __init__(self):
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

    def decode_network(self, json_container, data_manager):
        network = network_module.Network(
            uuid=json_container.get('meta').get('id'),
            version=json_container.get('meta').get('version'),
            name=json_container.get('name'),
            devices=[],
            data_manager=data_manager
        )
        network.devices = self.decode_device(json_container, network)

        self.wapp_log.debug("Network {} built.".format(network))
        return network

    def decode_device(self, json_container, network):
        devices = []
        for device_iterator in json_container.get('device', []):
            device = device_module.Device(
                parent=network,
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

    def decode_value(self, device_iterator, device):
        values = []
        for value_iterator in device_iterator.get('value', []):
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
                parent=device,
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

    def decode_state(self, value_iterator, value):
        states = []
        for state_iterator in value_iterator.get('state', []):
            state = state_module.State(
                parent=value,
                uuid=state_iterator.get('meta').get('id'),
                state_type=state_iterator.get('type'),
                timestamp=state_iterator.get('timestamp'),
                init_value=state_iterator.get('data')
            )
            states.append(state)
        return states
