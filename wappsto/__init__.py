"""
The __init__ method for the wappsto module.

Stores the Wappsto class functionality.
"""

import os
import json
import time
import logging
import inspect
from .connection import seluxit_rpc
from .connection import communication
from .connection.network_classes.errors import wappsto_errors
from .object_instantiation import status
from .object_instantiation import instantiate
from .object_instantiation import save_objects
from .user_guide.guider import Guider
RETRY_LIMIT = 5


class Wappsto:
    """
    The main package classs.

    Establishes a connection to the wappsto server, initializes the classes,
    starts a sending/receiving thread.
    """

    def __init__(self, json_file_name=None, load_from_state_file=False,
                 save_init=False):
        # TODO(Dimitar): Come up with a better description.
        """
        Initialize wappsto class.

        Creates a wappsto object which methods are exposed for users to use.
        These are: starting and stopping connection with a server and
        retrieving devices. These methods are enough for users to make
        operations on their network.

        Args:
            json_file_name: name of a json file containing all information
                about a network (default: {None})
            load_from_state_files: Defines if the data should be loaded from
                saved files (default: {False})
            save_init: Determines whether or not save json data
                (default: {False})

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        # TODO(Dimitar): Comment on this later.
        stack = inspect.stack()[1][1]
        self.path_to_calling_file = os.path.dirname(os.path.abspath(stack))

        self.connecting = True
        self.rpc = seluxit_rpc.SeluxitRpc(save_init)
        self.socket = None
        self.receive_thread = None
        self.send_thread = None
        self.status = status.Status()
        self.object_saver = save_objects.SaveObjects(self.path_to_calling_file)
        self.guide = self.check_if_guide(self.path_to_calling_file)
        # Instantiate the objects from JSON
        try:
            self.instance = instantiate.Instantiator(
                json_file_name=json_file_name,
                load_from_state_file=load_from_state_file,
                status=self.status,
                guide=self.guide,
                path_to_calling_file=self.path_to_calling_file
            )
        # When the file fails to open a FileNotFoundError is raised and
        # the service is stopped
        except FileNotFoundError as fnfe:
            self.wapp_log.error("Failed to open file: {}".format(fnfe))
            self.stop(False)
            raise fnfe

    def check_if_guide(self, file_path):
        """
        Guide handler method.

        Checks if this is the user's first time using the package, then starts
        up a guide module to explain the various steps to the user.

        Returns:
            A boolean flag to designate if this is the first time launching the
            program.

        """
        try:
            path = os.path.join(file_path, 'config.txt')
            with open(path, 'r+') as json_file:
                data = json.load(json_file)
                guide = data['guide']
                if guide == "True":
                    data['guide'] = "False"
                    json_file.seek(0)
                    json.dump(data, json_file)
                    json_file.truncate()
                    return True
        except FileNotFoundError:
            pass
        return False

    def get_status(self):
        """
        Wappsto status.

        Retrieves the status class instance which is set to different statuses
        throughout the program execution.

        Returns:
            A reference to the status object instance.

        """
        return self.status

    def get_network(self):
        return self.instance.network_cl

    def get_devices(self):
        return self.instance.device_list

    def get_by_id(self, id):
        if self.instance.network_cl.uuid == id:
            return self.instance.network_cl

        for device in self.get_devices():
            if device.uuid == id:
                return device

            for value in device.value_list:
                if value.uuid == id:
                    return value

    def get_device(self, name):
        """
        Device reference.

        Finds the device with a specific name attribute based on a given
        string

        Args:
            name: String containing the name attribute to search for.

        Returns:
            A reference to the device object instance.
            device

        Raises:
            DeviceNotFoundException: Device {name} not found in {instance}.

        """
        try:
            for device in self.instance.device_list:
                if name == device.name:
                    return device
            else:
                msg = "Device {} not found in {}".format(name, self.instance)
                raise wappsto_errors.DeviceNotFoundException(msg)
        except wappsto_errors.DeviceNotFoundException as device_not_found:
            msg = "Device not found {}".format(device_not_found)
            self.wapp_log.error(msg, exc_info=True)
            self.stop(False)
            raise device_not_found

    def start(self, address="wappsto.com", port=21005):
        """
        Start the server connection.

        Creates a socket object instance and passes the address and port to it.

        Args:
            address: Address to connect the service to.
                (default: {"qa.wappsto.com"})
            port: Port to connect the address to. (default: {31006})

        Raises:
            ServerConnectionException: "Unable to connect to the server.

        """
        self.status.set_status(status.STARTING)
        if self.guide:
            Guider.starting_server()
        # TODO(Dimitar): Change try except wrap to not encompass whole block.
        try:
            # Instance the socket class.
            reconnect_attempt_counter = 0
            self.socket = communication.ClientSocket(
                rpc=self.rpc,
                instance=self.instance,
                address=address,
                port=port,
                path_to_calling_file=self.path_to_calling_file
            )
            self.status.set_status(status.CONNECTING)
            if self.guide:
                Guider.connecting_to_server()

            # Attempts to connect to the server.
            self.connected = self.socket.connect()
            if self.connected:
                self.status.set_status(status.CONNECTED)
                if self.guide:
                    Guider.connected_to_server()
            # If it cannot connect it begins attempting the connection
            # until the retry limit is reached
            while (not self.connected
                    and reconnect_attempt_counter
                    < RETRY_LIMIT):
                self.status.set_status(status.RECONNECTING)
                if self.guide:
                    Guider.reconnecting_to_server()
                msg = "Cannot connect, attempting again in 5 seconds ..."
                self.wapp_log.info(msg)
                time.sleep(5)
                reconnect_attempt_counter += 1
                self.connected = self.socket.connect()

            # If the connection is not established,
            # a custom ServerConnectionException is raised.
            if reconnect_attempt_counter == RETRY_LIMIT:
                msg = ("Unable to connect to the server[IP: {}, Port: {}]"
                       .format(self.socket.address, self.socket.port)
                       )
                raise wappsto_errors.ServerConnectionException(msg)
        except wappsto_errors.ServerConnectionException as ce:
            msg = "Could not connect: {}".format(ce)
            self.wapp_log.error(msg, exc_info=True)
            self.stop(False)
            raise ce

        self.status.set_status(status.INITIALIZING)
        if self.guide:
            Guider.initializing()
        # Initializes the network, and all the subsequent devices, values and
        # states.
        # TODO(Dimitar): Change from generic Exception
        try:
            self.socket.initialize_all()
        except Exception as e:
            self.wapp_log.error("Error initializing: {}".format(e))
            self.stop(False)
            raise e

        self.status.set_status(status.STARTING_THREADS)
        if self.guide:
            Guider.starting_threads()
        # Starts the sending & receiving threads.
        try:
            self.receive_thread = self.socket.receiving_thread.start()
            self.send_thread = self.socket.sending_thread.start()
        except Exception as e:
            msg = "Error starting threads: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)
            self.stop(False)
            raise e

        self.status.set_status(status.RUNNING)
        if self.guide:
            Guider.running()

    def stop(self, save=True):
        """
        Stop the Wappsto service.

        Closes the connection socket to the server and, if the boolean is set
        to True it saves an instance of the current state.

        Args:
            save: Flag to determine whether runtime instances should be saved.
                (default: {True})

        """
        # TODO(Dimitar): Add Exception checking if necessary.
        self.connecting = False
        self.status.set_status(status.DISCONNECTING)
        if self.guide:
            Guider.disconnecting()
        # Closes the socket connection, if one is established.
        if self.socket:
            self.socket.close()
        if save:
            self.object_saver.save_instance(self.instance)
        self.wapp_log.info("Exiting...")
