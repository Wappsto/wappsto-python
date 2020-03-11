"""
The raspberrypi object instantiation module.

Represents raspberrypi components from JSON to class instances.
"""
import os
import json
import logging
import warnings
from . import encoder
from . import decoder


class DataManager:
    """
    Create class instances from JSON file.

    Creates instances of network, devices, values and states by parsing a
    given JSON file.
    """

    def __init__(
            self,
            json_file_name,
            load_from_state_file,
            path_to_calling_file):#
        """
        Initialize the Instantiator class.

        Initializes the Instatiator class which creates and holds instances of
        the network, devices, values and their states.

        Args:
            json_file_name: The name of the JSON file to parse.
            load_from_state_file: A True/False flag to denote whether to load
                from the saved files directory.
            path_to_calling_file: The path to files location.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.wappsto_encoder = encoder.WappstoEncoder()
        self.wappsto_decoder = decoder.WappstoDecoder()

        self.path_to_calling_file = path_to_calling_file
        self.json_file_name = json_file_name

        if load_from_state_file:
            json_file_name = self.load_latest_instance()
            if json_file_name is not None:
                self.json_file_name = json_file_name
        self.read_file()

    def __getattr__(self, attr):
        """
        Get attribute value.

        When trying to get value from outdated attribute warning is raised about
        it being deprecated and calls newest information instead.

        Returns:
            data stored in the new location

        """
        if attr in ["device_list"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network.devices
        if attr in ["network_cl"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network

    def load_latest_instance(self):
        path = os.path.join(self.path_to_calling_file, 'saved_instances/')

        file_paths = []
        for file_name in os.listdir(path):
            file_paths.append(os.path.join(path, file_name))

        latest_file = None
        if len(file_paths) > 0:
            latest_file = str(max(file_paths, key=os.path.getctime))
            self.wapp_log.debug('Latest file: {}'.format(latest_file))

        return latest_file

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
        except json.JSONDecodeError as jde:
            self.wapp_log.error("Error decoding: {}".format(jde))
            raise jde

        self.wapp_log.debug("RAW JSON DATA:\n\n{}\n\n".format(json_container))

        self.network = self.wappsto_decoder.decode_network(json_container, self)

    def save_instance(self):
        encoded_string = str(self.get_encoded_network())
        encoded_string = encoded_string.replace("\'", "\\\"")
        encoded_string = '{"data":"' + encoded_string + '"}'

        path = os.path.join(self.path_to_calling_file, 'saved_instances/')
        os.makedirs(path, exist_ok=True)
        path_open = os.path.join(path, '{}.json'.format(self.json_file_name))

        with open(path_open, "w+") as network_file:
            network_file.write(encoded_string)

        msg = "Saved {} to {}".format(encoded_string, network_file)
        self.wapp_log.debug(msg)

    def get_encoded_network(self):
        return self.wappsto_encoder.encode_network(self.network)
