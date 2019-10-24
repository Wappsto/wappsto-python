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
from . import send_data
from . import initialize
from . import handlers

t_url = 'https://tracer.iot.seluxit.com/trace?id={}&parent={}&name={}&status={}'  # noqa: E501


class ClientSocket:
    """
    The ClientSocket class that handles sending and receiving.

    Stores the sending and receiving threads, certificates, connection
    information as well as the related methods for handling communication
    between the client and the server.
    """

    def __init__(self, rpc, instance, address, port, path_to_calling_file):
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
        self.receiving_thread = threading.Thread(target=self.receive_thread)
        self.receiving_thread.setDaemon(True)
        self.connected = False
        self.sending_queue = queue.Queue(maxsize=0)
        self.sending_thread = threading.Thread(target=self.send_thread)
        self.sending_thread.setDaemon(True)
        self.rpc = rpc
        self.handlers = handlers.Handlers(self.instance)
        self.initialize_code = initialize.Initialize(self.rpc)
        self.packet_awaiting_confirm = {}
        self.add_trace_to_report_list = {}
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

        Wraps the socket using the SSL protocol with the provided server and
        client certificates, as well as the SSL key.

        Returns:
        An SSL wrapped socket with the attached certificates/keys.

        """
        return ssl.wrap_socket(
            self.my_raw_socket,
            ca_certs=self.ssl_server_cert,
            certfile=self.ssl_client_cert,
            keyfile=self.ssl_key,
            cert_reqs=ssl.CERT_REQUIRED
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

    def add_id_to_confirm_list(self, data):
        """
        Add the message ID to the confirm list.

        Adds the ID of the decoded JSON message to the list of confirmed
        packets. Uses locks to ensure atomicity.

        Args:
            data: JSON communication message data.

        """
        self.lock_await.acquire()
        decoded = json.loads(data.decode('utf-8'))
        self.packet_awaiting_confirm[decoded.get('id')] = data
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
        success_reply = send_data.SendData(
            send_data.SEND_SUCCESS,
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
        error_reply = send_data.SendData(
            send_data.SEND_FAILED,
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

        Sends the event from incoming delete messages to the appropriate handler
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
            error_str = 'Error received incorrect format in delete'
            msg = "Report Request from url ID: {}".format(get_url_id)
            self.wapp_log.error(msg)
            return self.handle_incoming_error(data, e, error_str, return_id)

        try:
            trace_id = data.get('params').get('meta').get('trace')
            self.wapp_log.debug("Report DELETE found trace id: {}"
                               .format(trace_id))
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

        Starts a socket to receive data and decode it. Based on the type of
        request, directs the decoded data to the appropriate methods.
        """
        self.wapp_log.debug("ReceiveThread Started!")
        while True:
            try:
                decoded = self.receive_data()
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
                            msg = "Successful reply for id {}".format(decoded_id)
                            self.wapp_log.debug(msg)
                            self.remove_id_from_confirm_list(decoded_id)

                        else:
                            self.wapp_log.info("Unhandled method")
                            error_str = 'Unknown method'
                            self.send_error(error_str, decoded_id)

                    except ValueError:
                        self.wapp_log.info("Value error")
                        self.wapp_log.info(decoded)
                        error_str = 'Value error'
                        self.send_error(error_str, decoded_id)

            except ValueError:
                self.wapp_log.info("Value error")
                self.wapp_log.info(decoded)
                error_str = 'Value error'
                self.send_error(error_str, decoded_id)

            except ConnectionResetError as e:
                msg = "Received Reset: {}".format(e)
                self.wapp_log.error(msg, exc_info=True)
                self.reconnect()

            except OSError as oe:
                msg = "Received OS Error: {}".format(oe)
                self.wapp_log.error(msg, exc_info=True)
                self.reconnect()

    def reconnect(self):
        """
        Attempt to reconnect.

        Reconnection attemps in the instance of a connection being interrupted.
        """
        self.wapp_log.info("Server Disconnect")
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
                reconnect_reply = send_data.SendData(send_data.SEND_RECONNECT)
                self.sending_queue.put(reconnect_reply)
            except Exception as e:
                msg = "Failed to reconnect {}".format(e)
                self.wapp_log.error(msg, exc_info=True)

    def send_data(self, data):
        """
        Send JSON data.

        Sends the encoded JSON message through the socket.

        Args:
            data: JSON communication message data.

        """
        if self.connected:
            self.wapp_log.debug('Raw Send Json: {}'.format(data))
            self.my_socket.send(data)
        else:
            self.wapp_log.error('Sending while not connected')

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
                if package.msg_id == send_data.SEND_SUCCESS:
                    self.send_success(package)

                elif package.msg_id == send_data.SEND_REPORT:
                    self.send_report(package)

                elif package.msg_id == send_data.SEND_FAILED:
                    self.send_failed(package)

                elif package.msg_id == send_data.SEND_RECONNECT:
                    self.send_reconnect()

                elif package.msg_id == send_data.SEND_CONTROL:
                    self.send_control(package)

                elif package.msg_id == send_data.SEND_TRACE:
                    self.send_trace(package)

                else:
                    self.wapp_log.info("Unhandled send")

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

        trace_req = request.urlopen(attempt)
        msg = "Sending tracer https message {} response {}".format(
            attempt,
            trace_req.getcode()
        )
        self.wapp_log.info(msg)

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
            self.send_data(local_data)
        except OSError as e:
            self.connected = False
            msg = "Error sending control: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def receive_data(self):
        """Socket receive method.

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
            except json.decoder.JSONDecodeError:
                pass
            except ValueError:
                if data == b'':
                    self.reconnect()
                else:
                    self.wapp_log.info("Value error")
                    self.wapp_log.info(data)
                    error_str = 'Value error'
                    decoded_id = decoded.get('id')
                    self.send_error(error_str, decoded_id)
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
            self.send_data(rpc_network)
            for element in self.packet_awaiting_confirm:
                self.send_data(self.packet_awaiting_confirm[element])
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
        self.wapp_log.info("Sending Error")
        rpc_fail_response = self.rpc.get_rpc_fail_response(
            package.rpc_id,
            package.text
        )
        self.wapp_log.info(rpc_fail_response)
        try:
            self.send_data(rpc_fail_response)
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
            self.send_data(local_data)
            decoded = json.loads(local_data.decode('utf-8'))
            data_decoded = decoded.get('params').get('data').get('data')
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
            self.send_data(rpc_success_response)
            self.wapp_log.debug("Sending Successful")

        except OSError as e:
            self.connected = False
            msg = "Error sending response: {}".format(e)
            self.wapp_log.error(msg, exc_info=True)

    def close(self):
        """
        Close the connection.

        Closes the socket object connection.
        """
        self.wapp_log.debug("Closing connection...")
        self.connected = False
        if self.my_socket:
            self.my_socket.close()
            self.my_socket = None
        if self.my_raw_socket:
            self.my_raw_socket.close()
            self.my_raw_socket = None

    def init_ok(self):
        """
        Return an ok from connecting.

        Return a message to signify that the connection was started
        successfully.

        Returns:
            A positive response.

        """
        decoded = self.receive_data()

        self.wapp_log.debug("Received after assembly: {}".format(decoded))

        if decoded is None:
            self.wapp_log.info("Server disconnected")
            return False

        if decoded.get('result', False):
            decoded_result = decoded.get('result')
            self.wapp_log.debug('Init result {}'.format(decoded_result))
            return True

        elif decoded.get('error'):
            type = decoded.get('error').get('message')
            msg = decoded.get('error').get('data').get('message')
            message = "{}: {}".format(type, msg)
            self.wapp_log.error(message, exc_info=False)
            raise Exception("Init failed: {}".format(message))
            return False

        else:
            self.wapp_log.error(decoded, exc_info=True)
            return False
