"""
The raspberrypi object instantiation module.

Represents raspberrypi components from JSON to class instances.
"""
import json
import logging
import warnings
from . import save_objects
from . import encoder
from . import decoder


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
        self.json_file_name = json_file_name

        if load_from_state_file:
            object_saver = save_objects.SaveObjects(path_to_calling_file)
            self.json_file_name = object_saver.load_instance()
        else:
            self.read_file()

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

    def read_file(self):
        try:
            with open(self.json_file_name) as data_file:
                file_data = data_file.read()
                self.parse_json_file(file_data)
            self.wapp_log.debug("Opening file: {}".format(self.json_file_name))
        except FileNotFoundError as fnfe:
            self.wapp_log.error("Error finding file: {}".format(fnfe))
            raise fnfe

    def parse_json_file(self, file_data):
        try:
            self.decoded = json.loads(file_data)
            json_container = json.loads(self.decoded.get('data'))
        except json.JSONDecodeError:
            self.wapp_log.error("Error decoding: {}".format(jde))
            raise jde

        self.wapp_log.debug("RAW JSON DATA:\n\n{}\n\n".format(json_container))

        wappsto_decoder = decoder.WappstoDecoder()
        self.network = wappsto_decoder.decode_network(json_container, self)

    def build_json(self):
        """
        Create json object.

        Builds a json object using existing information saved in
        network/device/value/state objects.

        Returns:
            JSON object.

        """
        wappsto_encoder = encoder.WappstoEncoder()
        encoded_object = wappsto_encoder.encode_network(self.network)
        return encoded_object
