#!/usr/bin/env python3

import logging
import json
import time
import datetime
import socket
import ssl
import select
import queue
import threading
import sys
import os
from random import randint

# Bypassing top-level import issues
from pathlib import Path
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

try:
    sys.path.remove(str(parent))
except ValueError:
    # Already removed
    pass

from wappsto.object_instantiation import instantiate
from wappsto.object_instantiation import status
from wappsto.connection import send_data
from wappsto.connection import seluxit_rpc
from wappsto.connection import handlers

ssl_server_cert = "test/certificates/ca.crt"
ssl_client_cert = "test/certificates/client.crt"
ssk_key = "test/certificates/client.key"

logging.basicConfig(level=logging.DEBUG,
                    format="%(levelname)s in %(filename)s:%(funcName)s "
                    "at line %(lineno)d occured at "
                    + "%(asctime)s\n\n\t%(message)s\n\n"
                    "Full Path: %(pathname)s\nProcess Name: %(processName)s\n",
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("./server_logging", mode='w')])
logger = logging.getLogger(__name__)

class MockServer:

    def __init__(self, address, port):
        self.address = address
        self.port = port

        self.running = True
        self.connected = False
        self.file_to_load = os.path.join(os.path.dirname(__file__),
                                         'test_JSON/62606aea-fc31-4706-8074-83a705fb29e5.json')
        self.instance = instantiate.Instantiator(json_file_name=self.file_to_load, load_from_state_file=False, status=status.Status(), guide=False, path_to_calling_file='')
        self.lock_await = threading.Lock()
        self.lock_thread_await = threading.Lock()
        self.sending_queue = queue.Queue()
        self.rpc = seluxit_rpc.SeluxitRpc(False)
        self.handlers = handlers.Handlers(self.instance)
        self.packet_awaiting_confirm = {}
        self.add_trace_to_report_list = {}
        self.list_of_message_ids = []
        self.conn = None
        self.socket_base = None
        self.set_sockets()

    def reset_list_of_message_ids(self):
        self.list_of_message_ids = []

    def decode_incoming_JSON(self, data):
        return json.loads(data)

    def generate_random_id(self):
        range_start = 10**(12-1)
        range_end = (10**12)-1
        return randint(range_start, range_end)

    def write_to_file(self, message):
        f = open("results.txt", "a")
        f.write(message)
        f.close()

    def add_id_to_confirm_list(self, data):
        self.lock_await.acquire()
        decoded = json.loads(data.decode('utf-8'))
        self.packet_awaiting_confirm[decoded.get('id')] = decoded
        self.lock_await.release()

    def remove_id_from_confirm_list(self, id):
        self.lock_await.acquire()
        self.packet_awaiting_confirm = self.packet_awaiting_confirm.pop(id)
        self.lock_await.release()

    def incoming_report_request(self, data):
        return_id = data.get('id')
        try:
            get_url_id = data.get('params').get('url')
        except AttributeError as e:
            error_str = 'Error received incorrect format in get'
            msg = "Report Request from url ID: {}".format(get_url_id)
            logger.info(msg)
            return self.handle_incoming_error(data, e, error_str, return_id)

        try:
            trace_id = data.get('params').get('meta').get('trace')
            logger.info("Report GET found trace id: {}"
                               .format(trace_id))
        except AttributeError:
            trace_id = None

        network_id = None
        device_id = None
        value_id = None
        state_id = None
        result = get_url_id.split('/')
        for item in result:
            if item == 'network':
                network_id = result[2]
            if item == 'device':
                device_id = result[4]
            if item == 'value':
                value_id = result[6]
            if item == 'state':
                state_id = result[8]

        self.build_get_state_reply(data, state_id)
        
        # else:
        #     error = 'Non-existing ID for get'
        #     self.send_error(error, return_id)

    def build_get_state_reply(self, data, state_id):

        state_type = None
        state_data = None
        for device in self.instance.device_list:
            for value in device.value_list:
                if value.report_state is not None:
                    if value.report_state.uuid == state_id:
                        state_type = value.report_state.state_type
                        state_data = value.init_value
                if value.control_state is not None:
                    if value.control_state.uuid == state_id:
                        state_type = value.control_state.state_type
                        state_data = value.init_value

        message_id = 1
        request_id = data.get('params').get('data').get('meta').get('id')
        manufacturer_id = '31439b87-040b-4b41-b5b8-f3774b2a1c19'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        created_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        updated_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        server_send_time = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        reply_base = '{"jsonrpc":"2.0","id":' + str(message_id) + ',"result":{"value":{"meta":{"type":"state","version":"2.0","id":"' + request_id + '","manufacturer":"' + manufacturer_id + '","updated":"' + updated_timestamp + '","created":"'+ created_timestamp +'","revision":1,"contract":[]},"type":"' + state_type + '", "status":"Send","data":"' + state_data + '","timestamp":"' + timestamp + '"},"meta":{"server_send_time":"' + server_send_time + '"}' + '}' + '}'
        self.sending_queue.put(bytes(reply_base, 'utf-8'))

    def send_trace(self, sending_queue, parent, trace_id, data, control_value_id=None):
        pass

    def incoming_control(self, data):
        return_id = data.get('id')
        try:
            control_id = data.get('params').get('data').get('meta').get('id')
        except AttributeError as e:
            error_str = 'Error received incorrect format in put'
            return self.handle_incoming_error(data, e, error_str, return_id)
        logger.info("Control Request from control id: " + control_id)

        try:
            local_data = data.get('params').get('data')
        except AttributeError:
            error = 'Error received incorrect format in put, data missing'
            self.send_error(error, return_id)
            return
        try:
            trace_id = data.get('params').get('meta').get('trace')
            logger.info("Control found trace id: " + trace_id)
        except AttributeError:
            # ignore
            trace_id = None

        if self.handle_incoming_put(
                control_id,
                local_data,
                self.sending_queue,
                trace_id
        ):
            self.send_success_reply(return_id)
        else:
            error = 'Invalid value range or non-existing ID'
            self.send_error(error, return_id)

    def validate_initialization(self, data):

        if data['params']['url'].endswith('/network'):
            if data['params']['data']['meta']['id'] == self.instance.network_cl.uuid:
                self.send_success_reply(self.rpc.get_next_random_id())
        for device in self.instance.device_list:
            if data['params']['url'].endswith('/device'):
                if data['params']['data']['meta']['id'] == device.uuid:
                    self.send_success_reply(self.rpc.get_next_random_id())

            for value in device.value_list:
                if data['params']['url'].endswith('/value/'):
                    if data['params']['data']['meta']['id'] == value.uuid:
                        self.send_success_reply(self.rpc.get_next_random_id())

                elif data['params']['url'].endswith('/state'):
                    if value.report_state is not None:
                        if data['params']['data']['meta']['id'] == value.report_state.uuid:
                            self.send_success_reply(self.rpc.get_next_random_id())
                    if value.control_state is not None:
                        if data['params']['data']['meta']['id'] == value.control_state.uuid:
                            self.send_success_reply(self.rpc.get_next_random_id())
        if (not data['params']['url'].endswith('/network')
            and not data['params']['url'].endswith('/device')
            and not data['params']['url'].endswith('/value/')
            and not data['params']['url'].endswith('/state')):
            self.send_error('Could not initialize', self.rpc.get_next_random_id())

    def create_outgoing_put(self):
        self.OUTGOING_PUT = True

    def send_error(self, error_str, return_id):
        error_reply = send_data.SendData(
            send_data.SEND_FAILED,
            rpc_id=return_id,
            text=error_str
        )
        self.sending_queue.put(error_reply)

    def send_success(self, package):
        try:
            rpc_success_response = self.rpc.get_rpc_success_response(
                package.rpc_id
            )
            self.send_data(rpc_success_response)
            logger.info("Sending Successful")

        except OSError as e:
            self.connected = False
            msg = "Error sending response: {}".format(e)
            logger.error(msg, exc_info=True)

    def send_success_reply(self, return_id):
        success_reply = send_data.SendData(
            send_data.SEND_SUCCESS,
            rpc_id=return_id
        )
        self.sending_queue.put(success_reply)

    def send_failed(self, package):
        logger.info("Sending Error")
        rpc_fail_response = self.rpc.get_rpc_fail_response(
            package.rpc_id,
            package.text
        )
        logger.info(rpc_fail_response)
        try:
            self.send_data(rpc_fail_response)
        except OSError as e:
            self.connected = False
            msg = "Error sending failed response: {}".format(e)
            logger.error(msg, exc_info=True)


    def send_report(self, package):
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
            logger.info('Sending report value: {}'.format(data_decoded))
        except OSError as e:
            self.connected = False
            msg = "Error sending report: {}".format(e)
            logger.error(msg, exc_info=True)

    def send_control(self, package):
        logger.info("Sending control message")
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
            logger.error(msg, exc_info=True)

    def send_data(self, data):
        logger.debug('Raw Send Json: {}'.format(data))
        self.conn.send(data)

    def set_sockets(self):
        self.socket_base = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_base.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_ssl = ssl.wrap_socket(
            self.socket_base,
            ca_certs=ssl_server_cert,
            certfile=ssl_client_cert,
            keyfile=ssk_key,
            server_side=True
        )
        self.socket_ssl.bind((self.address, self.port))
        self.socket_ssl.listen(5)
        self.connected = True

    def reset_sockets(self):
        logger.info("Client Disconnect")
        self.connected = False
        logger.info("Resetting list of message ids")
        self.reset_list_of_message_ids()
        while not self.connected:
            logger.info("Resetting sockets")
            self.socket_base.shutdown(socket.SHUT_RDWR)
            self.socket_ssl.shutdown(socket.SHUT_RDWR)
            try:
                self.set_sockets()
            except Exception as e:
                msg = "Failed to reset sockets {}".format(e)
                logger.error(msg, exc_info=True)
            self.connected = True

    def send_thread(self):
        logger.info("Sender Started.")
        current_thread = threading.currentThread()
        while getattr(current_thread, "running", True):
        # while True:
            if not self.sending_queue.empty():
                package = self.sending_queue.get_nowait()
                if self.connected:
                    if type(package) == bytes:
                        self.send_data(package)

                    elif package.msg_id == send_data.SEND_SUCCESS:
                        self.send_success(package)

                    elif package.msg_id == send_data.SEND_REPORT:
                        self.send_report(package)

                    elif package.msg_id == send_data.SEND_FAILED:
                        self.send_failed(package)

                    elif package.msg_id == send_data.SEND_CONTROL:
                        self.send_control(package)

                    elif package.msg_id == send_data.SEND_TRACE:
                        pass

                    else:
                        logger.info("Unhandled send")

                self.sending_queue.task_done()

        logger.debug("Sender Stopped.")

        # if self.conn is not None:
        #     self.conn.shutdown(socket.SHUT_RDWR)
        # if self.socket_base is not None:
        #     self.socket_base.shutdown(socket.SHUT_RDWR)
        # return

    def refresh_button(self, name_of_value):
        for device in self.instance.device_list:
            a_value = device.get_value(name_of_value)
            if a_value.report_state is not None:
                server_send_time = datetime.datetime.utcnow().strftime(
                    '%Y-%m-%dT%H:%M:%S.%fZ')
                a_value.report_state.timestamp = server_send_time
                reply_base = '{"jsonrpc":"2.0","id":"'+str(self.rpc.get_next_random_id())+'","method":"GET","params":{"url":"/network/'+str(device.get_parent_network().uuid)+'/device/'+str(device.uuid)+'/value/'+str(a_value.uuid)+'/state/'+str(a_value.report_state.uuid)+'","data":""}}'
                self.add_id_to_confirm_list(bytes(reply_base, 'utf-8'))
                self.sending_queue.put(bytes(reply_base, 'utf-8'))

    def handle_incoming_put(self, control_id, local_data, sending_queue,
                            trace_id):
        for device in self.instance.device_list:
            for value in device.value_list:
                if local_data['type'] == 'Report':
                    if value.report_state is not None:
                        if value.report_state.uuid == local_data['meta']['id']:
                            value.last_update_of_report = local_data['timestamp']
                            value.data_value = local_data['data']
                            return True
                if local_data['type'] == 'Control':
                    if value.control_state is not None:
                        if value.control_state.uuid == local_data['meta']['id']:
                            value.last_update_of_control = local_data[
                                'timestamp']
                            value.data_value = local_data['data']
                            return True

    def receive_thread(self):
        logger.info("Receiver Started.")
        current_thread = threading.currentThread()
        while getattr(current_thread, "running", True):
        # while True:
            self.reset_list_of_message_ids()
            self.conn, _ = self.socket_ssl.accept()
            current_thread = threading.currentThread()
            while getattr(current_thread, "running", True):
            # while True:
                try:
                    data = self.conn.recv(2000)
                    decoded = json.loads(data.decode('utf-8'))
                    decoded_id = decoded.get('id')
                    self.list_of_message_ids.append(decoded_id)
                    try:
                        logger.debug('Raw received Json: {}'
                                            .format(decoded))
                        if decoded.get('method', False) == 'PUT':
                            self.incoming_control(decoded)

                        elif decoded.get('method', False) == 'GET':
                            self.incoming_report_request(decoded)

                        elif decoded.get('method', False) == 'POST':
                            self.validate_initialization(decoded)

                        elif decoded.get('error', False):
                            decoded_error = decoded.get('error')
                            msg = "Error: {}".format(decoded_error.get('message'))
                            logger.error(msg)
                            self.remove_id_from_confirm_list(decoded_id)

                        elif decoded.get('result', False):
                            msg = "Successful reply for id {}".format(decoded_id)
                            logger.debug(msg)
                            self.remove_id_from_confirm_list(decoded_id)

                        else:
                            logger.info("Unhandled method")
                            error_str = 'Unknown method'
                            self.send_error(error_str, decoded_id)

                    except ValueError:
                        logger.info("Value error")
                        logger.info(data)
                        error_str = 'Value error'
                        self.send_error(error_str, decoded_id)

                except ValueError:
                    if data == b'':
                        break
                    else:
                        logger.info("Value error")
                        logger.info(data)
                        error_str = 'Value error'
                        self.send_error(error_str, decoded_id)

                except ConnectionResetError as e:
                    msg = "Received Reset: {}".format(e)
                    logger.error(msg, exc_info=True)
                    # self.reset_sockets()

                except OSError as oe:
                    msg = "Received OS Error: {}".format(oe)
                    logger.error(msg, exc_info=True)
                    # self.reset_sockets()
        logger.debug("Receiver Stopped.")
        # if self.conn is not None:
        #     self.conn.shutdown(socket.SHUT_RDWR)
        # if self.socket_base is not None:
        #     self.socket_base.shutdown(socket.SHUT_RDWR)
        # return

    def run(self):
        self.receiving_thread = threading.Thread(target=self.receive_thread)
        self.receiving_thread.setDaemon(True)
        self.sending_thread = threading.Thread(target=self.send_thread)
        self.sending_thread.setDaemon(True)
        self.receiving_thread.start()
        self.sending_thread.start()

        logger.info("Server on.")

    def threaded_run(self):
        self.server_thread = threading.Thread(target=self.run, daemon=True)
        self.server_thread.start()

    def stop(self):
        logger.debug("Stopping server.")
        self.sending_thread.running = False
        self.sending_thread.join()
        self.receiving_thread.running = False
        self.receiving_thread.join()
        self.socket_base.close()
        self.socket_ssl.close()