"""
The json data managing module.

Saves and loads data from json files.
"""
import os
import json
import logging
import warnings
from . import encoder
from . import decoder


class DataManager:
    """
    The data manager class.

    Reads data from Json file and saves current state of the whole network.
    """

    def __init__(
            self,
            json_file_name,
            load_from_state_file,
            path_to_calling_file):
        """
        Initialize the DataManager class.

        Initializes the DataManager class which reads data from Json file and
        saves the state of the whole network.

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
            json_file_name = self.get_latest_instance()
            if json_file_name is not None:
                self.json_file_name = json_file_name
        self.read_file()

    def __getattr__(self, attr):
        """
        Get attribute value.

        When trying to get value from outdated attribute warning is raised about
        it being deprecated and the new variable is used instead.

        Returns:
            data stored in the new location

        """
        if attr in ["device_list"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network.devices
        if attr in ["network_cl"]:
            warnings.warn("Property %s is deprecated" % attr)
            return self.network

    def get_latest_instance(self):
        """
        Gets latest saved instance.

        Gets all files from instance folder and returns the most recently changed.

        Returns:
            name of the most recently changed file

        """
        path = os.path.join(self.path_to_calling_file, 'saved_instances')
        os.makedirs(path, exist_ok=True)

        file_paths = []
        for file_name in os.listdir(path):
            file_paths.append(os.path.join(path, file_name))

        latest_file = None
        if len(file_paths) > 0:
            latest_file = str(max(file_paths, key=os.path.getctime))
            self.wapp_log.debug('Latest file: {}'.format(latest_file))

        return latest_file

    def read_file(self):
        """
        Reads file.

        Reads file with the provided name and calls method which parses it.

        """
        try:
            with open(self.json_file_name) as data_file:
                file_data = data_file.read()
                self.parse_json_file(file_data)
            self.wapp_log.debug("Opening file: {}".format(self.json_file_name))
        except FileNotFoundError as fnfe:
            self.wapp_log.error("Error finding file: {}".format(fnfe))
            raise fnfe

    def parse_json_file(self, file_data):
        """
        Parses json file.

        Retrieves the necessary data from the file and calls decode_network,
        results of which are saved in network variable.

        Args:
            file_data: string data read from the file.

        """
        try:
            self.decoded = json.loads(file_data)
            json_container = self.decoded.get('data')
            if not isinstance(json_container, dict):
                json_container = json.loads(json_container)
        except json.JSONDecodeError as jde:
            self.wapp_log.error("Error decoding: {}".format(jde))
            raise jde

        self.wapp_log.debug("RAW JSON DATA:\n\n{}\n\n".format(json_container))

        self.network = self.wappsto_decoder.decode_network(json_container, self)

    def save_instance(self):
        """
        Saves current instance of the whole network.

        Encodes the whole network and saves it in the saved instance folder.

        """
        encoded_string = str(self.get_encoded_network())
        encoded_string = encoded_string.replace("\'", "\\\"")
        encoded_string = '{"data":"' + encoded_string + '"}'

        path = os.path.join(self.path_to_calling_file, 'saved_instances')
        os.makedirs(path, exist_ok=True)
        path_open = os.path.join(path, self.json_file_name)

        with open(path_open, "w+") as network_file:
            network_file.write(encoded_string)

        msg = "Saved {} to {}".format(encoded_string, network_file)
        self.wapp_log.debug(msg)

    def get_by_id(self, id):
        """
        Wappsto get by id.

        Retrieves the instance of a class if its id matches the provided one.

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

    def get_encoded_network(self):
        """
        Gets encoded network.

        Gets dictionary representing current state of the whole network.

        """
        return self.wappsto_encoder.encode_network(self.network)
