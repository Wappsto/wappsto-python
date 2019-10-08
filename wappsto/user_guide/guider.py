"""
The guider module.

Handles first time guide messages.
"""


class Guider:
    """
    The Guider class.

    Prints the first time guide messages at each step of the program's
    execution and uses input() to block execution while the user reads the
    messages.
    """

    @staticmethod
    def starting_server():
        """
        Socket and RPC (Remote Procedure Call) setup message.

        A message that describes instancing a connection socket to the server
        and the RPC class.
        """
        input("We will try to connect to the server using fixed address and "
              "port. If we will not connect successfully the program will "
              "attemp to reconnect five times. After fifth failure the "
              "program will stop. To continue click [ENTER].")

    @staticmethod
    def instantiating_objects():
        """
        Object instantiation message.

        A message that describes instantiating the network, device, value and
        state objects from the given JSON file.
        """
        input("Now data from json file will be initialized into list "
              "of devices and each of the device will include own list of "
              "values containing their states. Moreover callbacks will be"
              "added to value objects. To continue click [ENTER].")

    @staticmethod
    def connecting_to_server():
        """
        Connect to the server message.

        A message that preceeds the attempt to connect to the server.
        """
        input("Click anything to connect to the server. To continue click"
              " [ENTER].")

    @staticmethod
    def reconnecting_to_server():
        """
        Reconnect attempt message.

        A message that preceeds a reconnection attempt to the server.
        """
        input("Click [ENTER] to start another attempt to connect to the "
              "server.")

    @staticmethod
    def connected_to_server():
        """
        Establish connection message.

        A message to notify the user that they have successfully established a
        connection to the server.
        """
        input("You have successfully connected to the server. To continue "
              "click [ENTER].")

    @staticmethod
    def initializing():
        """
        Initialize object instances on the send and receive queue.

        A message that describes the initialization of the instanced objects by
        adding them to the sending and receiving queue.
        """
        input("The objects instances will be added to sending and "
              "receiving queues by getting their attributes. To continue "
              "click [ENTER].")

    @staticmethod
    def starting_threads():
        """
        Thread start message.

        A message that decribres the start of the sending and receiving
        threads.
        """
        input("Starting sending and receiving threads that will exchange "
              "information with server. To continue click [ENTER].")

    @staticmethod
    def running():
        """
        Thread run message.

        A message that notifies the user that the threads have began running
        and can accept sending and receiving data.
        """
        input("The threads are running. To continue click [ENTER].")

    @staticmethod
    def disconnecting():
        """
        Disconnect message.

        A message that notifies the user that the program is disconnecting from
        the server.
        """
        input("Disconnecting from server and stopping the program. "
              "To continue click [ENTER].")
