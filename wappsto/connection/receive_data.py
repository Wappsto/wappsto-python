"""
The receive_data module.

Handles incoming data from the server.

"""
import sys
import json
import logging
from json.decoder import JSONDecodeError

RECEIVE_SIZE = 1024
MESSAGE_SIZE_BYTES = 1000000


class Receive:
    """The Receive class that handles receiving information."""

    def __init__(self, client_socket):
        """
        Initialize the Receive class.

        Initializes an object of Receive class by passing required
        parameters. While initialization, wapp_log is created.

        Args:
            client_socket: reference to ClientSocket instance.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.client_socket = client_socket

    def incoming_control(self, data):
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
            control_id = data.get('params').get('data').get('meta').get('id')
        except AttributeError as e:
            error_str = 'Error received incorrect format in put'
            return self.handle_incoming_error(data, e, error_str, return_id)
        self.wapp_log.debug("Control Request from control id: " + control_id)

        try:
            local_data = data.get('params').get('data').get('data')
        except AttributeError:
            error = 'Error received incorrect format in put, data missing'
            self.client_socket.send_data.send_error(error, return_id)
            return
        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Control found trace id: " + trace_id)
        except AttributeError:
            trace_id = None

        if self.client_socket.handler.handle_incoming_put(
                control_id,
                local_data,
                self.client_socket.sending_queue,
                trace_id
        ):
            self.client_socket.send_data.send_success_reply(return_id)
        else:
            error = 'Invalid value range or non-existing ID'
            self.client_socket.send_data.send_error(error, return_id)

    def handle_incoming_error(self, data, error_str, return_id):
        """
        Handle errors on the receive thread.

        Receives an error message and delivers it to the appropriate method.

        Args:
            data: JSON communication message data.
            error_str: Error contents.
            return_id: ID of the error message.

        """
        self.wapp_log.error(data)
        self.wapp_log.error(error_str, exc_info=True)
        return

    def incoming_report_request(self, data):
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
            get_url_id = data.get('params').get('url').split('/')
            get_url_id = get_url_id[-1]
        except AttributeError as e:
            error_str = 'Error received incorrect format in get'
            msg = "Report Request from url ID: {}".format(get_url_id)
            self.wapp_log.error(msg)
            return self.handle_incoming_error(data, e, error_str, return_id)

        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Report GET found trace id: {}"
                                    .format(trace_id))
        except AttributeError:
            trace_id = None

        if self.client_socket.handler.handle_incoming_get(
                get_url_id,
                self.client_socket.sending_queue,
                trace_id
        ):
            self.client_socket.send_data.send_success_reply(return_id)
        else:
            error = 'Non-existing ID for get'
            self.client_socket.send_data.send_error(error, return_id)

    def incoming_delete_request(self, data):
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
            get_url_id = data.get('params').get('url').split('/')
            get_url_id = get_url_id[-1]
        except AttributeError as e:
            error_str = 'Error received incorrect format in delete'
            msg = "Report Request from url ID: {}".format(get_url_id)
            self.wapp_log.error(msg)
            return self.handle_incoming_error(data, e, error_str, return_id)

        try:
            trace_id = data.get('params').get('meta').get('trace')
            self.wapp_log.debug(
                "Report DELETE found trace id: {}".format(trace_id)
            )
        except AttributeError:
            trace_id = None

        if self.client_socket.handler.handle_incoming_delete(
                get_url_id,
                self.client_socket.sending_queue,
                trace_id
        ):
            self.client_socket.send_data.send_success_reply(return_id)
        else:
            error = 'Delete failed'
            self.client_socket.send_data.send_error(error, return_id)

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
                    self.client_socket.reconnect()
                    return None
                try:
                    decoded_data = data.decode('utf-8')
                except Exception:
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
        return decoded

    def receive_message(self):
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
                    self.receive(decoded_data)
            else:
                self.receive(decoded)

        except JSONDecodeError:
            self.wapp_log.error("Json error: {}".format(decoded))
            # TODO send json rpc error, parse error

        except ConnectionResetError as e:
            msg = "Received Reset: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)
            self.client_socket.reconnect()

        except OSError as oe:
            msg = "Received OS Error: {}".format(oe)
            self.wapp_log.error(msg, exc_info=True)
            self.client_socket.reconnect()

    def receive(self, decoded):
        """
        Performs acction on received message.

        Based on the type of message, directs the decoded data to the
        appropriate methods.

        Args:
            decoded: the received message

        """
        if decoded:
            decoded_id = decoded.get('id')
            try:
                self.wapp_log.debug('Raw received Json: {}'
                                    .format(decoded))
                if decoded.get('method', False) == 'PUT':
                    self.incoming_control(decoded)

                elif decoded.get('method', False) == 'GET':
                    self.incoming_report_request(decoded)

                elif decoded.get('method', False) == 'DELETE':
                    self.incoming_delete_request(decoded)

                elif decoded.get('error', False):
                    decoded_error = decoded.get('error')
                    msg = "Error: {}".format(decoded_error.get('message'))
                    self.wapp_log.error(msg)
                    self.client_socket.remove_id_from_confirm_list(decoded_id)

                elif decoded.get('result', False):
                    result_value = decoded['result'].get('value', True)
                    if result_value is not True:
                        uuid = result_value['meta']['id']
                        data = result_value['data']
                        object = self.client_socket.handler.get_by_id(uuid)
                        if object is not None and object.parent.control_state == object:
                            object.parent.handle_control(data_value=data)
                    self.client_socket.remove_id_from_confirm_list(decoded_id)

                else:
                    self.wapp_log.warning("Unhandled method")
                    error_str = 'Unknown method'
                    self.client_socket.send_data.send_error(error_str, decoded_id)

            except ValueError:
                error_str = 'Value error'
                self.wapp_log.error("{} [{}]: {}".format(error_str,
                                                         decoded_id,
                                                         decoded))
                self.client_socket.send_data.send_error(error_str, decoded_id)
