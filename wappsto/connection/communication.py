"""
The server communication module.

Stores the server communication functionality for Wappsto as well as the
sending and receiving threads.
"""

import os
import socket
import threading
import time
import json
import queue
import ssl
# REPLACED request WITH NATIVE MODULE
import urllib.request as request
import logging
from . import message_data
from . import initialize
from . import handlers
from ..object_instantiation import status

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

t_url = 'https://tracer.iot.seluxit.com/trace?id={}&parent={}&name={}&status={}'  # noqa: E501


class ClientSocket:
    """
    The ClientSocket class that handles sending and receiving.

    Stores the sending and receiving threads, certificates, connection
    information as well as the related methods for handling communication
    between the client and the server.
    """

    def __init__(self, rpc, instance, address, port, path_to_calling_file,
                 wappsto_status):
        """
        Create a client socket.

        Creates a socket instance for the given address and port. Hhandles
        transfer of data from the instance attributes and methods to the
        specified server. Connection to the server is based on the specified
        address and port.

        Args:
            rpc: Sending/receiving queue processing instance.
            instance: Instance of network, devices, values and states.
            address: Server address.
            port: Server port.
            path_to_calling_file: path to OS directory of calling file.
            wappsto_status: status object.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.network = instance.network_cl
        self.instance = instance
        self.path_to_calling_file = path_to_calling_file
        self.ssl_server_cert = os.path.join(path_to_calling_file,
                                            "certificates/ca.crt")
        self.ssl_client_cert = os.path.join(path_to_calling_file,
                                            "certificates/client.crt")
        self.ssl_key = os.path.join(path_to_calling_file,
                                    "certificates/client.key")
        self.address = address
        self.port = port
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.ssl_context.load_cert_chain(self.ssl_client_cert, self.ssl_key)
        self.ssl_context.load_verify_locations(self.ssl_server_cert)
        self.wappsto_status = wappsto_status
        self.receiving_thread = threading.Thread(target=self.receive_thread)
        self.receiving_thread.setDaemon(True)
        self.connected = False
        self.message_received = True
        self.sending_queue = queue.Queue(maxsize=0)
        self.sending_thread = threading.Thread(target=self.send_thread)
        self.sending_thread.setDaemon(True)
        self.rpc = rpc
        self.handlers = handlers.Handlers(self.instance)
        self.initialize_code = initialize.Initialize(self.rpc)
        self.packet_awaiting_confirm = {}
        self.add_trace_to_report_list = {}
        self.bulk_send_list = []
        self.lock_await = threading.Lock()
        self.set_sockets()
        self.set_report_states()

    def set_report_states(self):
        """
        Set the reference to the queue and connection.

        Provides value classes with a referece to the queue and socket
        instances to enable report sending.
        """
        for device in self.instance.device_list:
            for value in device.value_list:
                value.rpc = self.rpc
                value.conn = self

    def set_sockets(self):
        """
        Create socket to communicate with server.

        Creates a socket instance and sets the options for communication.
        Passes the socket to the ssl_wrap method
        """
        self.my_raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_raw_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_KEEPALIVE,
            1
        )
        if (hasattr(socket, "TCP_KEEPIDLE")
                and hasattr(socket, "TCP_KEEPINTVL")
                and hasattr(socket, "TCP_KEEPCNT")):
            # After 5 idle minutes, start sending keepalives every 1 minutes.
            # Drop connection after 2 failed keepalives
            self.my_raw_socket.setsockopt(
                socket.SOL_TCP,
                socket.TCP_KEEPIDLE,
                5 * 60
            )
            self.my_raw_socket.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_KEEPIDLE,
                5 * 60
            )
            self.my_raw_socket.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_KEEPINTVL,
                60
            )
            self.my_raw_socket.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_KEEPCNT,
                2
            )
            # self.my_raw_socket.setsockopt(
            #     socket.IPPROTO_TCP,
            #     socket.TCP_USER_TIMEOUT,
            #     30000
            # )
        self.my_socket = self.ssl_wrap()

    def ssl_wrap(self):
        """
        Wrap socket.

        Wraps the socket using the SSL protocol as configured in the SSL
        context, with hostname verification enabled.

        Returns:
        An SSL wrapped socket.

        """
        return self.ssl_context.wrap_socket(
            self.my_raw_socket,
            server_hostname=self.address
        )

    def connect(self):
        """
        Connect to the server.

        Attempts a connection to the server on the provided addres and port.

        Returns:
            A connection flag to denote if the connection was successful or
            not.

        """
        self.connected = False
        try:
            self.my_socket.settimeout(10)
            self.my_socket.connect((self.address, self.port))
            self.connected = True
            self.my_socket.settimeout(None)
            return True

        except Exception as e:
            self.wapp_log.error("Failed to connect: {}".format(e))
            return False

    def initialize_all(self):
        """
        Call initialize_all method in initialize_code module.

        Initializes the object instances on the sending/receiving queue.
        """
        self.initialize_code.initialize_all(self, self.instance)
        self.confirm_initialize_all()

    def add_id_to_confirm_list(self, data):
        """
        Add the message ID to the confirm list.

        Adds the ID of the decoded JSON message to the list of confirmed
        packets. Uses locks to ensure atomicity.

        Args:
            data: JSON communication message data.

        """
        self.lock_await.acquire()
        self.packet_awaiting_confirm[data.get('id')] = data
        self.lock_await.release()

    def remove_id_from_confirm_list(self, _id):
        """
        Remove the ID from the confirm list.

        Removes the ID of the decoded JSON message from the list of confirmed
        packets. Uses locks to ensure atomicity.

        Args:
            _id: ID to remove from the confirm list.

        """
        self.lock_await.acquire()
        if _id in self.packet_awaiting_confirm:
            del self.packet_awaiting_confirm[_id]
        self.lock_await.release()

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
            self.send_error(error, return_id)
            return
        try:
            trace_id = data.get('params').get('meta').get('trace')
            if trace_id:
                self.wapp_log.debug("Control found trace id: " + trace_id)
        except AttributeError:
            # ignore
            trace_id = None

        if self.handlers.handle_incoming_put(
                control_id,
                local_data,
                self.sending_queue,
                trace_id
        ):
            self.send_success_reply(return_id)
        else:
            error = 'Invalid value range or non-existing ID'
            self.send_error(error, return_id)

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

    def send_success_reply(self, return_id):
        """
        Handle successful replies on the receive thread.

        Send back a success message based on the message return ID.

        Args:
            return_id: ID of the success message.

        """
        success_reply = message_data.MessageData(
            message_data.SEND_SUCCESS,
            rpc_id=return_id
        )
        self.sending_queue.put(success_reply)

    def send_error(self, error_str, return_id):
        """
        Send error message.

        Sends back an error message based on the message return ID.

        Args:
            error_str: Error message contents.
            return_id: ID of the error message.

        """
        error_reply = message_data.MessageData(
            message_data.SEND_FAILED,
            rpc_id=return_id,
            text=error_str
        )
        self.sending_queue.put(error_reply)

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

        if self.handlers.handle_incoming_get(
                get_url_id,
                self.sending_queue,
                trace_id
        ):
            self.send_success_reply(return_id)
        else:
            error = 'Non-existing ID for get'
            self.send_error(error, return_id)

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

        if self.handlers.handle_incoming_delete(
                get_url_id,
                self.sending_queue,
                trace_id
        ):
            self.send_success_reply(return_id)
        else:
            error = 'Delete failed'
            self.send_error(error, return_id)

    def receive_thread(self):
        """
        Create the receive thread.

        Starts a while True loop checking if something is received.
        """
        self.wapp_log.debug("ReceiveThread Started!")
        while True:
            self.receive_message()

    def reconnect(self):
        """
        Attempt to reconnect.

        Reconnection attemps in the instance of a connection being interrupted.
        """
        self.wapp_log.info("Server Disconnect")
        self.wappsto_status.set_status(status.RECONNECTING)
        self.connected = False
        while not self.connected:
            self.wapp_log.info("Trying to reconnect in 5 seconds")
            time.sleep(5)
            self.close()
            try:
                self.set_sockets()
                self.my_socket.connect((self.address, self.port))
                self.wapp_log.info("Reconnected")
                self.connected = True
                self.wappsto_status.set_status(status.CONNECTED)
                reconnect_reply = message_data.MessageData(
                    message_data.SEND_RECONNECT)
                self.sending_queue.put(reconnect_reply)
            except Exception as e:
                msg = "Failed to reconnect {}".format(e)
                self.wapp_log.error(msg, exc_info=True)

    def create_bulk(self, data):
        """
        Creates bulk message.

        Accomulates all messages in one and once sending_queue is empty it is
        sent.

        Args:
            data: JSON communication message data.

        """
        self.bulk_send_list.append(data)
        if self.sending_queue.qsize() < 1 and self.message_received:
            self.send_data(self.bulk_send_list)
            self.bulk_send_list.clear()
            self.message_received = False

    def send_data(self, data):
        """
        Send JSON data.

        Sends the encoded JSON message through the socket.

        Args:
            data: JSON communication message data.

        """
        if self.connected:
            for data_element in data:
                self.get_object_without_none_values(data_element)
            data = json.dumps(data)
            data = data.encode('utf-8')
            self.wapp_log.debug('Raw Send Json: {}'.format(data))
            self.my_socket.send(data)
        else:
            self.wapp_log.error('Sending while not connected')

    def get_object_without_none_values(self, encoded_object):
        """
        Get object without None values.

        Gets objects and removes any keys where value is None or empty.

        Args:
            encoded_object: dictionary object.

        """
        for key, val in list(encoded_object.items()):
            if val is None or val == []:
                del encoded_object[key]
            elif isinstance(val, dict):
                self.get_object_without_none_values(val)
            elif isinstance(val, list):
                for val_element in val:
                    self.get_object_without_none_values(val_element)

    def send_thread(self):
        """
        Create a send thread.

        Retrieves packages from the sending queue to
        send data.
        """
        self.wapp_log.debug("SendingThread Started!")

        while True:
            package = self.sending_queue.get()
            if self.connected:
                if package.msg_id == message_data.SEND_SUCCESS:
                    self.send_success(package)

                elif package.msg_id == message_data.SEND_REPORT:
                    self.send_report(package)

                elif package.msg_id == message_data.SEND_FAILED:
                    self.send_failed(package)

                elif package.msg_id == message_data.SEND_RECONNECT:
                    self.send_reconnect()

                elif package.msg_id == message_data.SEND_CONTROL:
                    self.send_control(package)

                elif package.msg_id == message_data.SEND_TRACE:
                    self.send_trace(package)

                else:
                    self.wapp_log.warning("Unhandled send")

            self.sending_queue.task_done()

    def send_trace(self, package):
        """
        Send data trace.

        Provides a trace URL for debugging purposes.

        Args:
            package: Sending queue item.

        """
        if package.control_value_id:
            control_value_id = package.control_value_id
            self.add_trace_to_report_list[control_value_id] = package.trace_id

        attempt = str(t_url).format(
            package.trace_id,
            package.parent,
            package.data,
            package.text
        )

        context = ssl._create_unverified_context()
        trace_req = request.urlopen(attempt, context=context)
        msg = "Sending tracer https message {} response {}".format(
            attempt,
            trace_req.getcode()
        )
        self.wapp_log.debug(msg)

    def send_control(self, package):
        """
        Send data handler.

        Sends the data from outgoing control messages to the appropriate
        handler method.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending control message")
        try:
            local_data = self.rpc.get_rpc_state(
                package.data,
                package.network_id,
                package.device_id,
                package.value_id,
                package.state_id,
                'control',
                trace_id=package.trace_id
            )
            self.add_id_to_confirm_list(local_data)
            self.create_bulk(local_data)
        except OSError as e:
            self.connected = False
            msg = "Error sending control: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def receive_data(self):
        """
        Socket receive method.

        Method that handles receiving data from a socket. Capable of handling
        data chunks.

        Returns:
            The decoded message from the socket.

        """
        total_decoded = []
        decoded = None
        while True:
            if self.connected:
                data = self.my_socket.recv(2000)
                decoded_data = data.decode('utf-8')
                total_decoded.append(decoded_data)
            else:
                break

            try:
                decoded = json.loads(''.join(total_decoded))
            except JSONDecodeError:
                if data == b'':
                    self.reconnect()
                else:
                    self.wapp_log.error("Value error: {}".format(data))
            else:
                break
        return decoded

    def send_reconnect(self):
        """
        Send a reconnect attempt.

        Sends a request to attempt to reconnect to the server.
        """
        self.wapp_log.info("Sending reconnect data")
        try:
            rpc_network = self.rpc.get_rpc_network(
                self.network.uuid,
                self.network.name,
                put=False
            )
            self.create_bulk(rpc_network)
            for element in self.packet_awaiting_confirm:
                self.create_bulk(self.packet_awaiting_confirm[element])
            self.wappsto_status.set_status(status.RUNNING)
        except OSError as e:
            self.connected = False
            msg = "Error sending reconnect: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def send_failed(self, package):
        """
        Send a fail message.

        Sends a message to notify about a sending failure.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending failed")
        rpc_fail_response = self.rpc.get_rpc_fail_response(
            package.rpc_id,
            package.text
        )
        self.wapp_log.debug(rpc_fail_response)
        try:
            self.create_bulk(rpc_fail_response)
        except OSError as e:
            self.connected = False
            msg = "Error sending failed response: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def send_report(self, package):
        """
        Send a report.

        Sends a report message from the package.

        Args:
            package: A sending queue item.

        """
        try:
            if not package.trace_id:
                if package.value_id in self.add_trace_to_report_list.keys():
                    package.trace_id = (
                        self.add_trace_to_report_list.pop(package.value_id)
                    )
            local_data = self.rpc.get_rpc_state(
                package.data,
                package.network_id,
                package.device_id,
                package.value_id,
                package.state_id,
                'report',
                trace_id=package.trace_id
            )
            self.add_id_to_confirm_list(local_data)
            self.create_bulk(local_data)
            data_decoded = local_data.get('params').get('data').get('data')
            self.wapp_log.info('Sending report value: {}'.format(data_decoded))
        except OSError as e:
            self.connected = False
            msg = "Error sending report: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def send_success(self, package):
        """
        Send a success message.

        Sends a message to notify of a successful.

        Args:
            package: A sending queue item.

        """
        try:
            rpc_success_response = self.rpc.get_rpc_success_response(
                package.rpc_id
            )
            self.create_bulk(rpc_success_response)

        except OSError as e:
            self.connected = False
            msg = "Error sending response: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def close(self):
        """
        Close the connection.

        Closes the socket object connection.
        """
        self.wapp_log.info("Closing connection...")
        self.connected = False
        if self.my_socket:
            self.my_socket.close()
            self.my_socket = None
        if self.my_raw_socket:
            self.my_raw_socket.close()
            self.my_raw_socket = None

    def confirm_initialize_all(self):
        """
        Confirms that all responses are received.

        Goes through the list saving expected responses and checks if they are
        received.
        """
        while len(self.packet_awaiting_confirm) > 0:
            self.receive_message()

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

            if len(self.packet_awaiting_confirm) == 0:
                self.message_received = True

        except JSONDecodeError:
            self.wapp_log.error("Json error: {}".format(decoded))
            # TODO send json rpc error, parse error

        except ConnectionResetError as e:
            msg = "Received Reset: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)
            self.reconnect()

        except OSError as oe:
            msg = "Received OS Error: {}".format(oe)
            self.wapp_log.error(msg, exc_info=True)
            self.reconnect()

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
                    self.remove_id_from_confirm_list(decoded_id)

                elif decoded.get('result', False):
                    self.remove_id_from_confirm_list(decoded_id)

                else:
                    self.wapp_log.warning("Unhandled method")
                    error_str = 'Unknown method'
                    self.send_error(error_str, decoded_id)

            except ValueError:
                error_str = 'Value error'
                self.wapp_log.error("{} [{}]: {}".format(error_str,
                                                         decoded_id,
                                                         decoded))
                self.send_error(error_str, decoded_id)
