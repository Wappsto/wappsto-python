"""
The network module.

Stores attributes for the network instance.
"""
import logging


class Network:
    """
    Network instance class.

    Stores attributes for the network instance.
    """

    def __init__(self, uuid, version, name):
        """
        Initialize the Network class.

        Initializes an object of network class by passing required parameters.

        Args:
            uuid: Unique identifier of a network
            version: Version of a network
            name: Name of a network

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.uuid = uuid
        self.version = version
        self.name = name
        msg = "Network {} Debug \n{}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)
