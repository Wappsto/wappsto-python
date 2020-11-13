"""
Message data module.

Saves message data packages to be sent the server and stores
global state flags.

Attributes:
    SEND_SUCCESS: Successful sending response global flag.
    SEND_FAILED: Failed sending response global flag.
    SEND_REPORT: Report message global flag.
    SEND_RECONNECT: Reconnection attempt global flag.
    SEND_CONTROL: Control message global flag.
    SEND_TRACE: Trace sending global flag.

    GET: Get message global flag
    PUT: Put message global flag
    POST: Post message global flag
    DELETE: Delete message global flag

"""
SEND_SUCCESS = 1
SEND_FAILED = 2
SEND_REPORT = 3
SEND_RECONNECT = 4
SEND_CONTROL = 5
SEND_TRACE = 6
SEND_DELETE = 7
POKE = 999

GET = "GET"
PUT = "PUT"
POST = "POST"
DELETE = "DELETE"


class MessageData:
    """
    Message data class.

    Stores data package attributes to send to the server.
    """

    def __init__(
            self,
            msg_id,
            rpc_id=None,
            data=None,
            network_id=None,
            device_id=None,
            value_id=None,
            state_id=None,
            text=None,
            parent=None,
            trace_id=None,
            control_value_id=None,
            verb=POST
    ):
        """
        Initialize the MessageData class.

        Holds the message values so they can be accessed from the RPC
        and socket.

        Args:
            msg_id: The ID of the message.
            rpc_id: The ID of the RPC instance. (default: {None})
            data: The data to send. (default: {None})
            network_id: The ID of the network to interact with. (default: {None})
            device_id: The ID of the device to interact with. (default: {None})
            value_id: The ID of the value to interact with. (default: {None})
            state_id: The ID of the state to interact with. (default: {None})
            text: The message to send. (default: {None})
            parent: The parent object. (default: {None})
            trace_id: The trace ID used to debug. (default: {None})
            control_value_id: The control data ID. (default: {None})
            verb: indicates what verb should be used. (default: {POST})

        """
        self.msg_id = msg_id
        self.rpc_id = rpc_id
        self.data = data
        self.network_id = network_id
        self.device_id = device_id
        self.value_id = value_id
        self.state_id = state_id
        self.text = text
        self.parent = parent
        self.trace_id = trace_id
        self.control_value_id = control_value_id
        self.verb = verb
