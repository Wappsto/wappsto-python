"""
Rapid Prototyping Python module for wappsto.com

Stores the Wappsto class functionality.
"""

import inspect
import logging
import os
import signal

from threading import Event

from .connection import communication
from .errors import wappsto_errors
from .connection import event_storage
from . import status
from .data_operation import data_manager


RETRY_LIMIT = 5


class Object_instantiation:
    """For backward compability. (Deprecated)"""
    def __init__(self):
        """Initialize Object_instantiation."""
        self.status = status


object_instantiation = Object_instantiation()


class Wappsto:
    """
    The main package classs.

    Establishes a connection to the wappsto server, initializes the classes,
    starts a sending/receiving thread.
    """
    __version__ = "1.2.8"

    def __init__(self, json_file_name=None, load_from_state_file=False,
                 log_offline=False, log_location="logs",
                 log_data_limit=10, limit_action=event_storage.REMOVE_OLD,
                 compression_period=event_storage.DAY_PERIOD):
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
            log_offline: boolean indicating if data should be logged (default: {False})
            log_location: location of the logs (default: {"logs"})
            log_data_limit: limit of data to be saved in log [in Megabytes] (default: {10})
            limit_action: action to take when limit is reached (default: {REMOVE_OLD})
            compression_period: period for compressing data [day, hour] (default: {DAY_PERIOD})

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        # TODO(Dimitar): Comment on this later.
        stack = inspect.stack()[1][1]
        self.path_to_calling_file = os.path.dirname(os.path.abspath(stack))

        self.connecting = True
        self.event_storage = event_storage.OfflineEventStorage(
            log_offline,
            log_location,
            log_data_limit,
            limit_action,
            compression_period
        )
        self.socket = None
        self.receive_thread = None
        self.send_thread = None
        self.status = status.Status()
        try:
            self.data_manager = data_manager.DataManager(
                json_file_name=json_file_name,
                load_from_state_file=load_from_state_file,
                path_to_calling_file=self.path_to_calling_file
            )
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
        return self.data_manager.network

    def get_devices(self):
        """
        Wappsto devices.

        Retrieves the devices list containing instances of devices

        Returns:
            A list of devices.

        """
        return self.data_manager.network.devices

    def get_by_id(self, id):
        """
        Wappsto get by id.

        Retrieves the instance of a class if its id matches the provided one

        Args:
            id: unique identifier used for searching

        Returns:
            A reference to the network/device/value/state object instance.

        """
        return self.data_manager.get_by_id(id)

    def set_status_callback(self, callback):
        """
        Sets callback for status.

        Sets the provided callback to the instance of status.

        Args:
            callback: reference to callback

        """
        self.status.set_callback(callback)

    def set_network_callback(self, callback):
        """
        Sets callback for network.

        Sets the provided callback to the instance of network.

        Args:
            callback: reference to callback

        """
        self.data_manager.network.set_callback(callback)

    def set_value_callback(self, callback):
        """
        Sets callback for values.

        Sets the provided callback to all instances of value.

        Args:
            callback: reference to callback

        """
        for device in self.data_manager.network.devices:
            for value in device.values:
                value.set_callback(callback)

    def get_device(self, name):
        """
        Device reference.

        Finds the device with a specific name attribute based on a given
        string

        Args:
            name: String containing the name attribute to search for.

        Returns:
            A reference to the device object instance.

        """
        for device in self.data_manager.network.devices:
            if name == device.name:
                return device
        else:
            msg = "Device {} not found in {}".format(name, self.data_manager)
            self.wapp_log.warning(msg, exc_info=True)
            self.stop(False)
            raise wappsto_errors.DeviceNotFoundException(msg)

    def start(self, address="wappsto.com", port=11006, automatic_trace=False, blocking=False):
        """
        Start the server connection.

        Creates a socket object instance and passes the address and port to it.

        Args:
            address: Address to connect the service to.
                     (default: "wappsto.com")
            port: Port to connect the address to.
                  (default: 11006)
            automatic_trace: indicates if all messages automaticaly send trace.
            blocking: Wheather or not this call should be a block call.
                      (default: False)
                      If sat to True, it will listen for a SIGTERM or SIGINT,
                      and terminate if those was received.
                      If this option are set, it is not needed to call stop.

        """
        self.status.set_status(status.STARTING)

        self.socket = communication.ClientSocket(
            data_manager=self.data_manager,
            address=address,
            port=port,
            path_to_calling_file=self.path_to_calling_file,
            wappsto_status=self.status,
            automatic_trace=automatic_trace,
            event_storage=self.event_storage
        )

        self.status.set_status(status.CONNECTING)
        try:
            if not self.socket.connect():
                self.socket.reconnect(RETRY_LIMIT, send_reconnect=False)
        except wappsto_errors.ServerConnectionException as ce:
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

        if blocking:
            self.keep_running()

    def keep_running(self):
        """
        Keeps wappsto running.

        Waiting for a SIGTERM or SIGINT, or self.terminated to be set,
        before it will exits.

        """
        self.terminated = Event()

        signal.signal(signal.SIGINT, lambda *args: self.terminated.set())
        signal.signal(signal.SIGTERM, lambda *args: self.terminated.set())
        self.wapp_log.info("Waiting terminate request.")

        self.terminated.wait()
        self.wapp_log.info("Terminate request received.")
        self.stop()

    def stop(self, save=True):
        """
        Stop the Wappsto service.

        Closes the connection socket to the server and, if the boolean is set
        to True it saves an instance of the current state.

        Args:
            save: Flag to determine whether runtime instances should be saved.
                (default: {True})

        """
        self.connecting = False
        self.status.set_status(status.DISCONNECTING)
        # Closes the socket connection, if one is established.
        if self.socket:
            self.socket.close()
        if save:
            self.data_manager.save_instance()
        self.wapp_log.info("Exiting...")
