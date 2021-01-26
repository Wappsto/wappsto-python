"""
The send_data module.

Handles sending data to the server.

"""
import json
import logging
import random
import ssl
import threading

import urllib.request as request

from . import message_data
from . import seluxit_rpc


MAX_BULK_SIZE = 10
t_url = 'https://tracer.iot.seluxit.com/trace?id={}&parent={}&name={}&status={}'  # noqa: E501


class SendData:
    """The SendData class that handles sending information."""

    def __init__(self, client_socket, automatic_trace):
        """
        Initialize the SendData class.

        Initializes an object of SendData class by passing required
        parameters. While initialization, wapp_log is created.

        Args:
            client_socket: reference to ClientSocket instance.
            automatic_trace: indicates if all messages automaticaly send trace.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.client_socket = client_socket
        self.automatic_trace = automatic_trace
        self.add_trace_to_report_list = {}
        self.bulk_send_list = []
        self.lock = threading.Lock()

    def create_trace(self, parent, trace_id=None):
        """
        Creates trace.

        Creates trace if necessary, by using generated data and existing
        information.

        Args:
            parent: owner of trace.
            trace_id: existing id used for tracing.

        Returns:
            trace id.

        """
        if self.automatic_trace and trace_id is None:
            random_int = random.randint(1, 25000)
            control_value_id = "{}{}".format(self.client_socket.data_manager.network.name,
                                             random_int)

            trace_id = random_int

            trace = message_data.MessageData(
                message_data.SEND_TRACE,
                parent=parent,
                trace_id=trace_id,
                data=None,
                text="ok",
                control_value_id=control_value_id)
            self.send_trace(trace)
        return trace_id

    def create_bulk(self, data):
        """
        Creates bulk message.

        Accomulates all messages in one and once sending_queue is empty or
        bulk limit is reached it is sent.

        Args:
            data: JSON communication message data.

        """
        self.lock.acquire()
        if data is not None:
            self.bulk_send_list.append(data)

        # Logic Checks
        empty_q = self.client_socket.sending_queue.qsize() == 0
        bulk_maxed = len(self.bulk_send_list) >= MAX_BULK_SIZE

        if (empty_q or bulk_maxed):
            free_con_lines = 10 - len(self.client_socket.packet_awaiting_confirm)
            send_size = len(self.bulk_send_list) if len(self.bulk_send_list) <= free_con_lines else free_con_lines
            self.wapp_log.debug("Starting to sending bulk data.")
            self.send_data([self.bulk_send_list.pop(0) for _ in range(send_size)])
        self.lock.release()

    def send_data(self, data):
        """
        Send JSON data.

        Sends the encoded JSON message through the socket.

        Args:
            data: JSON communication message data.

        """
        try:
            for data_element in data:
                self.client_socket.get_object_without_none_values(data_element)
                if len(data_element) == 0:
                    self.wapp_log.debug('Removing data element of length 0: {}'.format(data_element))
                    data.remove(data_element)  # WARNING(MBK): Do not remove from list when looping over it.

            if self.client_socket.connected:
                for data_element in data:
                    if data_element.get("method", "") in ["PUT", "POST", "DELETE"]:
                        self.client_socket.add_id_to_confirm_list(data_element)
                if len(data) > 0:
                    data = json.dumps(data)
                    data = data.encode('utf-8')
                    self.client_socket.my_socket.sendall(data)
                    self.wapp_log.debug('Raw Json Sent: {}'.format(data))
            else:
                self.wapp_log.warning("Data added to storage!")
                self.client_socket.event_storage.add_message(data)
        except OSError as e:
            self.wapp_log.warning("Data added to storage!")
            self.client_socket.event_storage.add_message(data)

            self.client_socket.connected = False
            msg = "Error sending: {}".format(e)
            self.wapp_log.error(msg)
            self.client_socket.request_reconnect()

    def send_thread(self):
        """
        Create a send thread.

        Retrieves packages from the sending queue to
        send data.
        """
        self.wapp_log.debug("SendingThread Started!")

        while True:
            package = self.client_socket.sending_queue.get()
            if package.msg_id == message_data.SEND_SUCCESS:
                self.send_success(package)

            elif package.msg_id == message_data.SEND_FAILED:
                self.send_failed(package)

            elif package.msg_id == message_data.SEND_REPORT:
                self.send_report(package)

            elif package.msg_id == message_data.SEND_CONTROL:
                self.send_control(package)

            elif package.msg_id == message_data.SEND_DELETE:
                self.send_delete(package)

            elif package.msg_id == message_data.SEND_TRACE:
                self.send_trace(package)

            elif package.msg_id == message_data.SEND_RECONNECT:
                self.send_reconnect(package)

            elif package.msg_id == message_data.POKE:
                self.wapp_log.debug("Was Poked.")
                self.create_bulk(None)

            else:
                self.wapp_log.warning("Unhandled send")

            self.client_socket.sending_queue.task_done()

    def send_success(self, package):
        """
        Send a success message.

        Sends a message to notify of a successful.

        Args:
            package: A sending queue item.

        """
        self.wapp_log.info("Sending success for ID: {}".format(package.rpc_id))
        rpc_success_response = seluxit_rpc.get_rpc_success_response(
            package.rpc_id
        )
        self.create_bulk(rpc_success_response)

    def send_failed(self, package):
        """
        Send a fail message.

        Sends a message to notify about a sending failure.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending failed for ID: {}".format(package.rpc_id))
        self.wapp_log.info("Sending failed reason: {}".format(package.text))
        rpc_fail_response = seluxit_rpc.get_rpc_fail_response(
            package.rpc_id,
            package.text
        )
        self.create_bulk(rpc_fail_response)

    def send_report(self, package):
        """
        Send a report.

        Sends a report message from the package.

        Args:
            package: A sending queue item.

        """
        self.wapp_log.info("Sending report message")
        if not package.trace_id:
            if package.value_id in self.add_trace_to_report_list.keys():
                package.trace_id = (
                    self.add_trace_to_report_list.pop(package.value_id)
                )

        package.trace_id = self.create_trace(
            package.network_id, package.trace_id)

        local_data = seluxit_rpc.get_rpc_state(
            package.data,
            package.network_id,
            package.device_id,
            package.value_id,
            package.state_id,
            'Report',
            package.verb,
            trace_id=package.trace_id
        )
        self.create_bulk(local_data)
        data_decoded = local_data.get('params').get('data').get('data')
        self.wapp_log.info('Report value send: {}'.format(data_decoded))

    def send_control(self, package):
        """
        Send data handler.

        Sends the data from outgoing control messages to the appropriate
        handler method.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending control message")
        package.trace_id = self.create_trace(
            package.network_id, package.trace_id)

        local_data = seluxit_rpc.get_rpc_state(
            package.data,
            package.network_id,
            package.device_id,
            package.value_id,
            package.state_id,
            'Control',
            package.verb,
            trace_id=package.trace_id
        )
        self.create_bulk(local_data)

    def send_delete(self, package):
        """
        Send data delete request.

        Sends the data to be deleted.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending delete message")
        package.trace_id = self.create_trace(
            package.network_id, package.trace_id)

        local_data = seluxit_rpc.get_rpc_delete(
            package.network_id,
            package.device_id,
            package.value_id,
            package.state_id,
            package.trace_id
        )
        self.create_bulk(local_data)

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
        msg = "Sending tracer https message {} response {}"
        msg = msg.format(attempt, trace_req.getcode())
        self.wapp_log.debug(msg)

    def send_reconnect(self, package):
        """
        Send a reconnect attempt.

        Sends a request to attempt to reconnect to the server.

        Args:
            package: Sending queue item.

        """
        self.wapp_log.info("Sending reconnect data")
        package.trace_id = self.create_trace(
            package.network_id, package.trace_id)

        rpc_network = seluxit_rpc.get_rpc_network(
            self.client_socket.data_manager.network.uuid,
            self.client_socket.data_manager.network.name,
            package.verb,
            trace_id=package.trace_id
        )
        # NOTE: Need to be send even if bulk is full.
        self.send_data([rpc_network])
        self.wapp_log.info("Reconnect data send")
        self.wapp_log.info("Sending awaiting data")
        self.send_data(list(self.client_socket.packet_awaiting_confirm.values()))
        self.wapp_log.info("Awaiting data send")
