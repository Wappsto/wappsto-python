"""
The raspberrypi object instantiation module.

Represents raspberrypi components from JSON to class instances.
"""
import json
import logging
from . import save_objects
from ..connection.network_classes import network
from ..connection.network_classes import device
from ..connection.network_classes import value
from ..connection.network_classes import state
from . import status


class Instantiator:
    """
    Create class instances from JSON file.

    Creates instances of network, devices, values and states by parsing a
    given JSON file.
    """

    def __init__(
            self,
            json_file_name,
            load_from_state_file,
            status,
            path_to_calling_file):
        """
        Initialize the Instantiator class.

        Initializes the Instatiator class which creates and holds instances of
        the network, devices, values and their states.

        Args:
            json_file_name: The name of the JSON file to parse.
            load_from_state_files: A True/False flag to denote whether to load
                from the saved files directory.
            status: Reference to the Status instance to update the program's
                status flag.

        Raises:
            JSONDecodeError: Exception when trying to parse the JSON file.
            FileNotFoundError: Exception when trying to find the file's
                location.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.path_to_calling_file = path_to_calling_file
        self.network_cl = None
        self.device_list = []
        self.status = status
        self.load_from_state_file = load_from_state_file
        self.json_file_name = json_file_name

        if self.load_from_state_file:
            object_saver = save_objects.SaveObjects(path_to_calling_file)
            self.json_file_name = object_saver.load_instance()
        try:
            with open(self.json_file_name) as data_file:
                self.decoded = json.loads(data_file.read())
            self.parse_json_file()
            msg = "Classes instantiated from: {}".format(json_file_name)
            self.wapp_log.debug(msg)
        except FileNotFoundError as fnfe:
            self.wapp_log.error("Error finding file: {}".format(fnfe))
            raise fnfe

    def parse_json_file(self):
        """
        Parse JSON file.

        Opens the JSON file from the location attribute and parses the data
        inside of it to a class attribute.

        Raises:
            Exception: JSONDecodeError

        """
        self.wapp_log.debug("Opening file: {}".format(self.json_file_name))

        try:
            self.json_container = self.decoded.get('data')
            self.json_container.get('meta')
        except Exception:
            try:
                self.json_container = json.loads(self.decoded.get('data'))
            except Exception as jde:
                self.wapp_log.error("Error decoding: {}".format(jde))
                raise jde

        self.wapp_log.debug("RAW JSON DATA:\n\n{}\n\n".format(
            self.json_container)
        )
        self.network_cl = self.build_network(self.decoded)
        self.status.set_status(status.INSTANTIATING)
        self.device_list = self.build_device_list()

    def build_device_list(self):
        # TODO(Dimitar): Fill in exception
        """
        Build list of device instances.

        Builds a list of instances of devices that contain instances of values.
        The instances of values also contain instances of states. All are built
        from the decoded JSON file.

        Returns:
            A list of devices instances.

        """
        for device_iterator in self.json_container.get('device', []):
            uuid = device_iterator.get('meta').get('id')
            name = device_iterator.get('name')
            product = device_iterator.get('product')
            protocol = device_iterator.get('protocol')
            serial_number = device_iterator.get('serial')
            version = device_iterator.get('meta').get('version')
            manufacturer = device_iterator.get('manufacturer')
            communication = device_iterator.get('communication')
            description = device_iterator.get('description')

            # CHANGE THIS LATER
            device_cl = device.Device(
                parent_network=self.network_cl,
                uuid=uuid,
                name=name,
                product=product,
                protocol=protocol,
                serial_number=serial_number,
                version=version,
                manufacturer=manufacturer,
                communication=communication,
                description=description
            )
            self.device_list.append(device_cl)
            self.wapp_log.debug("Device {} appended to {}"
                                .format(device_cl, self.device_list)
                                )

            for value_iterator in device_iterator.get('value', []):
                uuid = value_iterator.get('meta').get('id')
                name = value_iterator.get('name')
                type_of_value = value_iterator.get('type')
                permission = value_iterator.get('permission')
                states = value_iterator.get('state', [])
                try:
                    init_value = states[0].get('data', None)
                except IndexError:
                    init_value = None
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
                    get_string = value_iterator.get('string')
                    string_encoding = get_string.get('encoding')
                    string_max = value_iterator.get('string').get('max')
                elif 'blob' in value_iterator:
                    data_type = 'blob'
                    get_bolb = value_iterator.get('blob')
                    blob_encoding = get_bolb.get('encoding')
                    blob_max = value_iterator.get('blob').get('max')
                elif 'number' in value_iterator:
                    data_type = 'number'
                    get_number = value_iterator.get('number')
                    number_min = get_number.get('min')
                    number_max = get_number.get('max')
                    number_step = get_number.get('step')
                    number_unit = get_number.get('unit')

                # CHANGE THIS LATER
                value_cl = value.Value(
                    parent_device=device_cl,
                    uuid=uuid,
                    name=name,
                    type_of_value=type_of_value,
                    data_type=data_type,
                    permission=permission,
                    init_value=init_value,
                    number_max=number_max,
                    number_min=number_min,
                    number_step=number_step,
                    number_unit=number_unit,
                    string_encoding=string_encoding,
                    string_max=string_max,
                    blob_encoding=blob_encoding,
                    blob_max=blob_max
                )

                device_cl.add_value(value_cl)
                self.wapp_log.debug("Value {} appended to {}"
                                    .format(value_cl, device_cl.value_list)
                                    )

                for state_iterator in states:
                    uuid = state_iterator.get('meta').get('id')
                    state_type = state_iterator.get('type')
                    # data = state_iterator.get('data')
                    timestamp = state_iterator.get('timestamp')
                    state_cl = state.State(
                        parent_value=value_cl,
                        uuid=uuid,
                        state_type=state_type,
                        timestamp=timestamp
                    )
                    if state_type == 'Report':
                        value_cl.add_report_state(state_cl)
                        msg = "Report state {} appended to {}"
                        self.wapp_log.debug(msg.format(state_cl, value_cl))
                    elif state_type == 'Control':
                        value_cl.add_control_state(state_cl)
                        msg = "Control state {} appended to {}"
                        self.wapp_log.debug(msg.format(state_cl, value_cl))

        return self.device_list

    def build_network(self, decoded):
        """
        Create network instance.

        Builds a Network class instance by setting the attributes from the
        decoded JSON file.

        Args:
            decoded: Decoded JSON message data.

        Returns:
            A Network class instance.

        """
        try:
            decoded_data = decoded.get('data')
            decoded_meta = decoded_data.get('meta')
        except Exception:
            decoded_data = json.loads(decoded.get('data'))
            decoded_meta = decoded_data.get('meta')

        self.uuid = decoded_meta.get('id')
        self.version = decoded_meta.get('version')
        self.name = decoded_data.get('name', '')

        network_cl = network.Network(
            uuid=self.uuid,
            version=self.version,
            name=self.name
        )

        self.wapp_log.debug("Network {} built.".format(network_cl))

        return network_cl

    def build_json(self):
        """
        Create json object.

        Builds a json object using existing information saved in
        network/device/value/state objects.

        Returns:
            JSON object.

        """
        devices = []
        for device_iterator in self.device_list:
            values = []
            for value_iterator in device_iterator.value_list:
                states = []
                for state_iterator in value_iterator.state_list:
                    state = {
                        'data': value_iterator.init_value,
                        'type': state_iterator.state_type,
                        'timestamp': state_iterator.timestamp,
                        'meta':
                        {
                            'id': state_iterator.uuid,
                            'type': 'state',
                            'version': '2.0'
                        }
                    }

                    state = self.get_object_without_none_values(state)
                    state['meta'] = self.get_object_without_none_values(
                        state['meta'])
                    states.append(state)

                if value_iterator.data_type == 'string':
                    details = {
                        'encoding': value_iterator.string_encoding,
                        'max': value_iterator.string_max
                    }
                elif value_iterator.data_type == 'blob':
                    details = {
                        'encoding': value_iterator.blob_encoding,
                        'max': value_iterator.string_max
                    }
                elif value_iterator.data_type == 'number':
                    details = {
                        'min': value_iterator.number_min,
                        'max': value_iterator.number_max,
                        'step': value_iterator.number_step,
                        'unit': value_iterator.number_unit
                    }

                value = {
                    'name': value_iterator.name,
                    'type': value_iterator.type_of_value,
                    'permission': value_iterator.permission,
                    'state': states,
                    value_iterator.data_type: details,
                    'meta':
                    {
                        'id': value_iterator.uuid,
                        'type': 'value',
                        'version': '2.0'
                    }
                }

                value = self.get_object_without_none_values(value)
                value['meta'] = self.get_object_without_none_values(
                    value['meta'])
                values.append(value)

            device = {
                'name': device_iterator.name,
                'product': device_iterator.product,
                'protocol': device_iterator.protocol,
                'serial': device_iterator.serial_number,
                'manufacturer': device_iterator.manufacturer,
                'communication': device_iterator.communication,
                'description': device_iterator.description,
                'value': values,
                'version': '2.0',
                'meta':
                {
                    'id': device_iterator.uuid,
                    'version': '2.0',
                    'type': 'device'
                }
            }

            device = self.get_object_without_none_values(device)
            device['meta'] = self.get_object_without_none_values(
                device['meta'])
            devices.append(device)

        network = {
            'name': self.network_cl.name,
            'device': devices,
            'meta':
            {
                'id': self.network_cl.uuid,
                'version': '2.0',
                'type': 'network'
            }
        }

        network = self.get_object_without_none_values(network)
        network['meta'] = self.get_object_without_none_values(network['meta'])
        return network

    def get_object_without_none_values(self, obj):
        """
        Get object without None values.

        Gets objects and returns different object not containing any keys,
        where value is None.

        Args:
            obj: dictionary object.

        Returns:
            Dictionary object without None values.

        """
        return dict([(key, value) for key, value in obj.items()
                     if value is not None])
