"""
The raspberry object saving module.

Saves the running instance of the raspberry objects to a file.
"""
import os
import logging
from . import encoder


class SaveObjects:
    """
    The SaveObjects class that handles saving the running state to a file.

    Saves and loads the running instance of the raspberrypi objects to a JSON
    file in the saving folder.
    """

    def __init__(self, path_to_calling_file):
        """
        Initialize the WappstoEncoder class.

        Initializes a reference to the WappstoEncoder class so that it can be
        used to encode the current running instance into a JSON file.
        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.wappsto_encoder = encoder.WappstoEncoder()
        self.path_to_calling_file = path_to_calling_file

    def save_instance(self, instance):
        """
        Save the current instance as a JSON file.

        Encodes the current instance into a JSON file that can later be passed
        to the Instantiator class in order to parse it and create a new
        instance.

        Args:
            instance: Reference to the instance object that holds the network,
            device, value and state instances.

        Raises:
            OSError: There was an error opening or writing to the file.

        """
        # Creates the path.
        path = os.path.join(self.path_to_calling_file, 'saved_instances/')
        if not os.path.exists(path):
            os.mkdir(path)

        encoded_string = str(self.wappsto_encoder.encode(instance))
        encoded_string = str(encoded_string).replace("\'", "\\\"")
        encoded_string = '{"data":"' + encoded_string + '"}'

        network_id = instance.network_cl.uuid

        path_open = os.path.join(path, '{}.json'.format(network_id))

        with open(path_open, "w+") as network_file:
            network_file.write(encoded_string)

        msg = "Saved {} to {}".format(encoded_string, network_file)
        self.wapp_log.debug(msg)

    def load_instance(self):
        """
        Load the instance from the JSON file.

        Passes the path of the latest saved JSON file to allow parsing it.

        Returns:
            Path string to load file from.

        Raises:
            ValueError: An error occured finding files in the saved_instances
            directory.

        """
        path = os.path.join(self.path_to_calling_file, 'saved_instances/')
        files = os.listdir(path)
        file_paths = []
        latest_file = None
        for file_name in files:
            file_paths.append(os.path.join(path, file_name))
        try:
            latest_file = str(max(file_paths, key=os.path.getctime))
        except ValueError as ve:
            self.wapp_log.error("Exception in finding latest file: {}"
                                .format(ve))
            raise ve
        self.wapp_log.debug('Latest file: {}'.format(latest_file))

        return latest_file
