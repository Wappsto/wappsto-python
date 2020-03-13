"""
The raspberrypi object instantiation module.

Represents raspberrypi components from JSON to class instances.
"""
import json
import logging
import warnings
from . import save_objects
from ..connection.network_classes import network as network_module
from ..connection.network_classes import device as device_module
from ..connection.network_classes import value as value_module
from ..connection.network_classes import state as state_module
from . import encoder


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
            path_to_calling_file):
        """
        Initialize the Instantiator class.

        Initializes the Instatiator class which creates and holds instances of
        the network, devices, values and their states.

        Args:
            json_file_name: The name of the JSON file to parse.
            load_from_state_files: A True/False flag to denote whether to load
                from the saved files directory.

        Raises:
            JSONDecodeError: Exception when trying to parse the JSON file.
            FileNotFoundError: Exception when trying to find the file's
                location.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.path_to_calling_file = path_to_calling_file
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

    def __getattr__(self, attr):
        """
        Get attribute value.

        When trying to get value from device_list warning is raised about
        it being deprecated and calls network.devices instead.

        Returns:
            value of get_data

        """
        if attr in ["device_list"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network.devices
        if attr in ["network_cl"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network

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
        self.build_network()

    def build_network(self):
        """
        Create network instance.

        Builds a Network and the underlying classes by setting the attributes
        from the decoded JSON file.

        """
        try:
            decoded_data = self.decoded.get('data')
            decoded_meta = decoded_data.get('meta')
        except Exception:
            decoded_data = json.loads(self.decoded.get('data'))
            decoded_meta = decoded_data.get('meta')

        self.uuid = decoded_meta.get('id')
        self.version = decoded_meta.get('version')
        self.name = decoded_data.get('name')

        self.network = network_module.Network(
            uuid=self.uuid,
            version=self.version,
            name=self.name,
            devices=[],
            instance=self
        )

        self.wapp_log.debug("Network {} built.".format(self.network))

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
            device = device_module.Device(
                parent=self.network,
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
            self.network.devices.append(device)
            self.wapp_log.debug("Device {} appended to {}"
                                .format(device, self.network.devices)
                                )

            for value_iterator in device_iterator.get('value', []):
                uuid = value_iterator.get('meta').get('id')
                name = value_iterator.get('name')
                type_of_value = value_iterator.get('type')
                permission = value_iterator.get('permission')
                period = value_iterator.get('period', None)
                delta = value_iterator.get('delta', None)
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
                value = value_module.Value(
                    parent=device,
                    uuid=uuid,
                    name=name,
                    type_of_value=type_of_value,
                    data_type=data_type,
                    permission=permission,
                    number_max=number_max,
                    number_min=number_min,
                    number_step=number_step,
                    number_unit=number_unit,
                    string_encoding=string_encoding,
                    string_max=string_max,
                    blob_encoding=blob_encoding,
                    blob_max=blob_max,
                    period=period,
                    delta=delta
                )

                device.add_value(value)
                self.wapp_log.debug("Value {} appended to {}"
                                    .format(value, device.values)
                                    )

                for state_iterator in value_iterator.get('state', []):
                    uuid = state_iterator.get('meta').get('id')
                    state_type = state_iterator.get('type')
                    init_value = state_iterator.get('data')
                    timestamp = state_iterator.get('timestamp')
                    state = state_module.State(
                        parent=value,
                        uuid=uuid,
                        state_type=state_type,
                        timestamp=timestamp,
                        init_value=init_value
                    )
                    if state_type == 'Report':
                        value.add_report_state(state)
                        msg = "Report state {} appended to {}"
                        self.wapp_log.debug(msg.format(state, value))
                    elif state_type == 'Control':
                        value.add_control_state(state)
                        msg = "Control state {} appended to {}"
                        self.wapp_log.debug(msg.format(state, value))

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
        if self.network is not None:
            if self.network.uuid == id:
                self.wapp_log.debug(message.format("network", id))
                return self.network

            for device in self.network.devices:
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

    def build_json(self):
        """
        Create json object.

        Builds a json object using existing information saved in
        network/device/value/state objects.

        Returns:
            JSON object.

        """
        wappsto_encoder = encoder.WappstoEncoder()
        encoded_object = wappsto_encoder.encode(self)
        return encoded_object
