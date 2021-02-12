"""
The receive_data module.

Handles incoming data from the server.

"""
import sys
import json
import random
import logging
from . import message_data
from json.decoder import JSONDecodeError

# RECEIVE_SIZE = 1024
RECEIVE_SIZE = 2048
MESSAGE_SIZE_BYTES = 1000000


class ReceiveData:
    """The ReceiveData class that handles receiving information."""

    def __init__(self, client_socket):
        """
        Initialize the ReceiveData class.

        Initializes an object of ReceiveData class by passing required
        parameters. While initialization, wapp_log is created.

        Args:
            client_socket: reference to ClientSocket instance.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.client_socket = client_socket

    def __get_random_id(self):
        network_n = self.client_socket.data_manager.network.name
        random_int = random.randint(1, 25000)
        return "{}{}".format(network_n, random_int)

    def sending_queue_add_trace(self, parent, trace_id, data, control_value_id=None):
        """
        Add a trace to the sending queue.

        Adds a trace URL to the sending queue for debugging purposes.

        Args:
            parent: Owner of the trace URL.
            trace_id: ID of the trace message.
            data: Trace message data.
            control_value_id: ID of the control state of the value
                (default: {None})

        """
        if trace_id:
            trace = message_data.MessageData(
                message_data.SEND_TRACE,
                parent=parent,
                trace_id=trace_id,
                data=data,
                text="ok",
                control_value_id=control_value_id)
            self.client_socket.sending_queue.put(trace)

    def receive_thread(self):
        """
        Create the receive thread.

        Starts a while True loop checking if something is received.
        """
        self.wapp_log.debug("ReceiveThread Started!")
        while True:
            self.receive_message()

    def receive_data(self):
        """
        Socket receive method.

        Method that handles receiving data from a socket. Capable of handling
        data chunks.

        Returns:
            The decoded message from the socket.

        """
        total_decoded = ''
        decoded = None
        while True:
            if self.client_socket.connected:
                data = self.client_socket.my_socket.recv(RECEIVE_SIZE)
                if data == b'':
                    self.wapp_log.info("Received empty data from connection.")
                    self.client_socket.connected = False
                    self.client_socket.reconnect()
                    return None
                try:
                    decoded_data = data.decode('utf-8')
                except AttributeError:
                    continue
                total_decoded += decoded_data
                if sys.getsizeof(total_decoded) > MESSAGE_SIZE_BYTES:
                    error = "Received message exeeds size limit."
                    self.wapp_log.error(error)
                    return None
                try:
                    decoded = json.loads(total_decoded)
                except JSONDecodeError:
                    if len(decoded_data) < RECEIVE_SIZE:
                        error = "Json decoding error: {}".format(total_decoded)
                        self.wapp_log.error(error)
                        return None
                else:
                    break
            else:
                break
        self.wapp_log.debug('Received Json: {}'.format(decoded))
        return decoded

    def receive_message(self, fail_on_error=False):
        """
        Receives message.

        Receives message and passes it to receive method, and catches
        encountered exceptions.
        """
        try:
            decoded = self.receive_data()

            # if the received string is list
            if isinstance(decoded, list):
                for decoded_data in decoded:
                    self.receive(decoded_data, fail_on_error=fail_on_error)
            else:
                self.receive(decoded, fail_on_error=fail_on_error)

        except (ConnectionResetError, TimeoutError) as e:  # pragma: no cover
            msg = "Received Connection Error: {}".format(e)
            self.wapp_log.error(msg, exc_info=False)
            self.client_socket.connected = False
            self.client_socket.reconnect()

    def receive(self, decoded, fail_on_error=False):
        """
        Performs acction on received message.

        Based on the type of message, directs the decoded data to the
        appropriate methods.

        Args:
            decoded: the received message

        """
        if decoded:
            try:
                if decoded.get('method', False) == 'PUT':
                    self.incoming_put(decoded)

                elif decoded.get('method', False) == 'GET':
                    self.incoming_get(decoded)

                elif decoded.get('method', False) == 'DELETE':
                    self.incoming_delete(decoded)

                elif decoded.get('error', False):
                    self.incoming_error(decoded)
                    if fail_on_error:
                        msg = "POST Failed!!"
                        self.wapp_log.error(msg)
                        raise ConnectionAbortedError(msg)

                elif decoded.get('result', False):
                    self.incoming_result(decoded)

                else:
                    return_id = decoded.get('id')
                    self.wapp_log.warning("Unhandled method")
                    error_str = 'Unknown method'
                    self.error_reply(error_str, return_id)

            except ValueError:
                return_id = decoded.get('id')
                error_str = 'Value error'
                self.wapp_log.error("{} [{}]: {}".format(error_str, return_id, decoded))
                self.error_reply(error_str, return_id)

    def incoming_put(self, data):
        """
        Incoming data handler.

        Sends the data from incoming control messages to the appropriate
        handler method.

        Args:
            data: JSON communication message data.

        Returns:
            Results of the incoming control handling.

        """
        return_id = data.get('id')
        try:
            uuid = data.get('params').get('data').get('meta').get('id')
            meta_type = data.get('params').get('data').get('meta').get('type')
            self.wapp_log.debug("Put request from id: " + uuid)
        except AttributeError:
            error_str = 'Error received incorrect format in put: {}'.format(str(data))
            self.wapp_log.error(error_str, exc_info=True)
            return

        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Found trace id: " + trace_id)
        except AttributeError:
            trace_id = None  # NOTE(MBK): This should never happen.

        obj = self.client_socket.data_manager.get_by_id(uuid)
        if obj is None:
            self.error_reply('Non-existing uuid provided', return_id)
            return

        param_data = data.get('params').get('data')
        try:
            if meta_type == "value":
                period = param_data.get('period')
                if period:
                    obj.set_period(period)
                delta = param_data.get('delta')
                if delta:
                    obj.set_delta(delta)
                self.success_reply(return_id)
                self.sending_queue_add_trace(
                    obj.parent.uuid,
                    trace_id,
                    None,
                    control_value_id=self.__get_random_id()
                )
            elif meta_type == "state":
                local_data = param_data.get('data')
                if obj.state_type == "Control":
                    err_msg = []
                    valid = obj.parent._validate_value_data(data_value=local_data, err_msg=err_msg)
                    self.wapp_log.debug(f"validation was: '{valid}'")
                    self.wapp_log.debug(err_msg)
                    if err_msg:
                        self.error_reply(
                            error_str=err_msg[0],
                            return_id=return_id
                        )
                        return
                    self.success_reply(return_id)
                    obj.parent.handle_control(data_value=local_data)
                    self.sending_queue_add_trace(
                        obj.parent.uuid,
                        trace_id,
                        local_data,
                        control_value_id=self.__get_random_id()
                    )
                else:
                    self.error_reply('Element is not control state', return_id)
        except AttributeError:
            self.error_reply('Attribute error encountered', return_id)

    def incoming_get(self, data):
        """
        Incoming data handler.

        Sends the data from incoming report messages to the appropriate handler
        method.

        Args:
            data: JSON communication message data.

        Returns:
            Results of the incoming report handling.

        """
        return_id = data.get('id')
        try:
            uuid = data.get('params').get('url').split('/')[-1]
            self.wapp_log.debug("Get request from id: " + uuid)
        except AttributeError:
            error_str = 'Error received incorrect format in get: {}'.format(str(data))
            self.wapp_log.error(error_str, exc_info=True)
            return

        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Found trace id: " + trace_id)
        except AttributeError:
            trace_id = None

        obj = self.client_socket.data_manager.get_by_id(uuid)
        if obj is None:
            self.error_reply('Non-existing uuid provided', return_id)
            return

        try:
            if obj.state_type == "Report":
                self.success_reply(return_id)
                self.sending_queue_add_trace(
                    obj.parent.uuid,
                    trace_id,
                    obj.data,
                    control_value_id=self.__get_random_id()
                )
                obj.parent.handle_refresh()
            else:
                self.error_reply('Element is not control state', return_id)
        except AttributeError:
            self.error_reply('Attribute error encountered', return_id)

    def incoming_delete(self, data):
        """
        Incoming delete handler.

        Sends the event from incoming delete messages to the
        appropriate handler method.

        Args:
            data: JSON communication message data.

        Returns:
            Results of the incoming report handling.

        """
        return_id = data.get('id')
        try:
            uuid = data.get('params').get('url').split('/')[-1]
            self.wapp_log.debug("Delete request from id: " + uuid)
        except AttributeError:
            error_str = 'Error received incorrect format in delete: {}'.format(str(data))
            self.wapp_log.error(error_str, exc_info=True)
            return

        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Found trace id: " + trace_id)
        except AttributeError:
            trace_id = None

        obj = self.client_socket.data_manager.get_by_id(uuid)
        if obj is None:
            self.error_reply('Non-existing uuid provided', return_id)
            return

        try:
            self.success_reply(return_id)
            self.sending_queue_add_trace(
                obj.uuid,
                trace_id,
                None,
                control_value_id=self.__get_random_id()
            )
            obj.handle_delete()
        except AttributeError:
            self.error_reply('Attribute error encountered', return_id)

    def incoming_error(self, data):
        """
        Incoming error handler.

        Deals with incoming error message.

        Args:
            data: JSON communication message data.

        """
        return_id = data.get('id')
        msg = "Error: {}".format(data.get('error').get('message'))
        self.wapp_log.error(msg)
        self.client_socket.remove_id_from_confirm_list(return_id)

    def incoming_result(self, data):
        """
        Incoming result handler.

        Deals with incoming result message.

        Args:
            data: JSON communication message data.

        """
        return_id = data.get('id')
        result_value = data['result'].get('value', True)
        if result_value is not True:
            uuid = result_value['meta']['id']
            data = result_value['data']
            object = self.client_socket.data_manager.get_by_id(uuid)
            if object is not None and object.parent.control_state == object:
                object.parent.handle_control(data_value=data)
        self.client_socket.remove_id_from_confirm_list(return_id)

    def success_reply(self, return_id):
        """
        Handle successful replies on the receive thread.

        Adds success message to the sending_queue.

        Args:
            return_id: ID of the success message.

        """
        success_reply = message_data.MessageData(
            message_data.SEND_SUCCESS,
            rpc_id=return_id
        )
        self.client_socket.sending_queue.put(success_reply)

    def error_reply(self, error_str, return_id):
        """
        Handle error replies on the receive thread.

        Adds error message to the sending_queue.

        Args:
            error_str: Error message contents.
            return_id: ID of the error message.

        """
        error_reply = message_data.MessageData(
            message_data.SEND_FAILED,
            rpc_id=return_id,
            text=error_str
        )
        self.client_socket.sending_queue.put(error_reply)
