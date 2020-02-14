"""
The __init__ method for the wappsto module.

Stores the Wappsto class functionality.
"""

import os
import time
import logging
import inspect
from .connection import seluxit_rpc
from .connection import communication
from .connection.network_classes.errors import wappsto_errors
from .object_instantiation import status
from .object_instantiation import instantiate
from .object_instantiation import save_objects

RETRY_LIMIT = 5


class Wappsto:
    """
    The main package classs.

    Establishes a connection to the wappsto server, initializes the classes,
    starts a sending/receiving thread.
    """

    __version__ = "1.1.0"

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
            load_from_state_file: Defines if the data should be loaded from
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
        self.connected = False
        self.status = status.Status()
        self.object_saver = save_objects.SaveObjects(self.path_to_calling_file)
        # Instantiate the objects from JSON
        try:
            self.instance = instantiate.Instantiator(
                json_file_name=json_file_name,
                load_from_state_file=load_from_state_file,
                status=self.status,
                path_to_calling_file=self.path_to_calling_file
            )
        # When the file fails to open a FileNotFoundError is raised and
        # the service is stopped
        except FileNotFoundError as fnfe:
            self.wapp_log.error("Failed to open file: {}".format(fnfe))
            self.stop(False)
            raise fnfe

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
        """
        Wappsto network.

        Retrieves the network class instance.

        Returns:
            A reference to the network object instance.

        """
        return self.instance.network_cl

    def get_devices(self):
        """
        Wappsto devices.

        Retrieves the devices list containing instances of devices

        Returns:
            A list of devices.

        """
        return self.instance.device_list

    def get_by_id(self, id):
        """
        Wappsto get by id.

        Retrieves the instance of a class if its id matches the provided one

        Args:
            id: unique identifier used for searching

        Returns:
            A reference to the network/device/value object instance.

        """
        if self.instance.network_cl.uuid == id:
            return self.instance.network_cl

        for device in self.get_devices():
            if device.uuid == id:
                return device

            for value in device.value_list:
                if value.uuid == id:
                    return value

        self.wapp_log.warning("Failed to find object with id: {}".format(id))

    def get_device(self, name):
        """
        Device reference.

        Finds the device with a specific name attribute based on a given
        string

        Args:
            name: String containing the name attribute to search for.

        Returns:
            A reference to the device object instance.

        Raises:
            DeviceNotFoundException: Device {name} not found in {instance}.

        """
        for device in self.instance.device_list:
            if name == device.name:
                return device
        else:
            msg = "Device {} not found in {}".format(name, self.instance)
            self.wapp_log.warning(msg, exc_info=True)
            self.stop(False)
            raise wappsto_errors.DeviceNotFoundException(msg)

    def start(self, address="wappsto.com", port=11006):
        """
        Start the server connection.

        Creates a socket object instance and passes the address and port to it.

        Args:
            address: Address to connect the service to.
                (default: {"wappsto.com"})
            port: Port to connect the address to. (default: {11006})

        Raises:
            ServerConnectionException: "Unable to connect to the server.

        """
        self.status.set_status(status.STARTING)
        # TODO(Dimitar): Change try except wrap to not encompass whole block.
        try:
            # Instance the socket class.
            reconnect_attempt_counter = 0
            self.status.set_status(status.CONNECTING)

            while (not self.connected
                    and reconnect_attempt_counter
                    < RETRY_LIMIT):
                self.socket = communication.ClientSocket(
                    rpc=self.rpc,
                    instance=self.instance,
                    address=address,
                    port=port,
                    path_to_calling_file=self.path_to_calling_file,
                    wappsto_status=self.status
                )

                # Attempts to connect to the server.
                self.connected = self.socket.connect()
                if self.connected:
                    self.status.set_status(status.CONNECTED)
                    break
                # If it cannot connect it begins attempting the connection
                # until the retry limit is reached

                self.status.set_status(status.RECONNECTING)
                msg = "Cannot connect, attempting again in 5 seconds ..."
                self.wapp_log.info(msg)
                time.sleep(5)
                reconnect_attempt_counter += 1
                self.socket.close()

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
        # Closes the socket connection, if one is established.
        if self.socket:
            self.socket.close()
        if save:
            self.object_saver.save_instance(self.instance)
        self.wapp_log.info("Exiting...")
