"""
The object instance initialization module.

Stores the initialization functionality for the object instances of the
network, devices, values and states.
"""
import logging


class Initialize:
    """
    The initialize class handles initializing object instances.

    Using references to the RPC, socket and object instances, it sends
    activation messages to the server and enables sending/receiving for the
    network, device, value and state instances.
    """

    def __init__(self, rpc):
        """
        Create an initialization instance.

        The initialize instance contains the initialize_all method that is used
        to activate the object instances so that they can send/receive to the
        server.

        Args:
            rpc: Reference to the RPC instance.

        """
        self.rpc = rpc

    def initialize_all(self, conn, instance):
        """
        Initialize all of the devices on the sending and receiving queue.

        Adds all the devices to the send receive queue by pinging the server
        with their information in order to initialize them.

        Args:
            conn: A reference to the socket instance.
            instance: A reference to the network and device instances.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.rpc.add_whole_json(conn, instance.build_json())

        msg = "The whole network {} added to Sending queue {}.".format(
            instance.network_cl.name,
            self.rpc
        )
        # All of the debug logs may need relocation to the RPC class.
        self.wapp_log.debug(msg)
