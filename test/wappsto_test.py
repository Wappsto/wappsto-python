#!/usr/bin/env python3
import os
import ast
import json
import pytest
import wappsto
import urllib.parse
from mock import Mock
from unittest.mock import patch

from wappsto.connection import message_data
from wappsto.object_instantiation import status
from wappsto.connection.network_classes.errors import wappsto_errors

ADDRESS = "wappsto.com"
PORT = 11006
TEST_JSON = "test_JSON/test_json.json"
TEST_JSON_prettyprint = "test_JSON/test_json_prettyprint.json"


def check_for_correct_conn(*args, **kwargs):
    if args[0][0] != ADDRESS or args[0][1] != PORT:
        raise wappsto_errors.ServerConnectionException


def fake_connect(self, address, port):
    wappsto.RETRY_LIMIT = 2
    with patch('ssl.SSLContext.wrap_socket') as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), patch('threading.Thread'), patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), patch('socket.socket'), patch('ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port)


def fix_object(self, callback_exists, testing_object):
    if callback_exists:
        test_callback = Mock(return_value=True)
        testing_object.set_callback(test_callback)
    else:
        testing_object.callback = None
    return testing_object


def create_response(self, verb, callback_exists, trace_id, bulk):
    value = self.service.instance.device_list[0].value_list[0]
    value = fix_object(self, callback_exists, value)
    id = str(value.control_state.uuid)
    url = str(value.report_state.uuid)
    trace = ''

    if verb == "DELETE":
        network = self.service.get_network()
        network = fix_object(self, callback_exists, network)
        url = str(network.uuid)
    
    if verb == "DELETE" or verb == "PUT" or verb == "GET":
        if trace_id is not None:
            trace = '"meta": {"trace": "'+str(trace_id)+'"},'

        message = '{"jsonrpc": "2.0", "id": "1", "params": {"url": "'+url+'",'+trace+' "data": {"meta": {"id": "'+id+'"}, "data": "93"}}, "method": "'+verb+'"}'
    else:
        message = '{"jsonrpc": "2.0", "id": "1", "params": {"url": "/network/b03f246d-63ef-446d-be58-ef1d1e83b338/device/a0e087c1-9678-491c-ac47-5b065dea3ac0/value/7ce2afdd-3be3-4945-862e-c73a800eb209/state/a7b4f66b-2558-4559-9fcc-c60768083164", "data": {"meta": {"id": "a7b4f66b-2558-4559-9fcc-c60768083164", "type": "state", "version": "2.0"}, "type": "Report", "status": "Send", "data": "93", "timestamp": "2020-01-22T08:22:57.216500Z"}}, "method": "??????"}'

    if bulk:
        message = [message, message]
        message = str(message)

    return message


def exists_in_dictionary(key, dict):
    return True if key in dict else False

# ################################## TESTS ################################## #


class TestJsonLoadClass:
    
    @classmethod
    def setup_class(self):
        self.test_json_prettyprint_location = os.path.join(
            os.path.dirname(__file__),
            TEST_JSON_prettyprint)
        self.test_json_location = os.path.join(
            os.path.dirname(__file__),
            TEST_JSON)

    def test_load_prettyprint_json(self):
        # Arrange
        with open(self.test_json_location, "r") as json_file:
            decoded = json.load(json_file)

        # Act
        service = wappsto.Wappsto(json_file_name=self.test_json_prettyprint_location)

        # Assert
        assert service.instance.decoded == decoded


class TestConnClass:

    def setup_method(self):
        self.test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=self.test_json_location)

    @pytest.mark.parametrize("address,port,callback_exists,expected_status,value_changed_to_none,upgradable", [(ADDRESS, PORT, True, status.RUNNING, False, False),
                                                     (ADDRESS, -1, True, status.DISCONNECTING, False, False),
                                                     ("wappstoFail.com", PORT, True, status.DISCONNECTING, False, False),
                                                     (ADDRESS, PORT, False, status.RUNNING, False, False),
                                                     (ADDRESS, -1, False, status.DISCONNECTING, False, False),
                                                     ("wappstoFail.com", PORT, False, status.DISCONNECTING, False, False),
                                                     (ADDRESS, PORT, True, status.RUNNING, True, False),
                                                     (ADDRESS, -1, True, status.DISCONNECTING, True, False),
                                                     ("wappstoFail.com", PORT, True, status.DISCONNECTING, True, False),
                                                     (ADDRESS, PORT, False, status.RUNNING, True, False),
                                                     (ADDRESS, -1, False, status.DISCONNECTING, True, False),
                                                     ("wappstoFail.com", PORT, False, status.DISCONNECTING, True, False),
                                                     (ADDRESS, PORT, True, status.RUNNING, False, True),
                                                     (ADDRESS, -1, True, status.DISCONNECTING, False, True),
                                                     ("wappstoFail.com", PORT, True, status.DISCONNECTING, False, True),
                                                     (ADDRESS, PORT, False, status.RUNNING, False, True),
                                                     (ADDRESS, -1, False, status.DISCONNECTING, False, True),
                                                     ("wappstoFail.com", PORT, False, status.DISCONNECTING, False, True),
                                                     (ADDRESS, PORT, True, status.RUNNING, True, True),
                                                     (ADDRESS, -1, True, status.DISCONNECTING, True, True),
                                                     ("wappstoFail.com", PORT, True, status.DISCONNECTING, True, True),
                                                     (ADDRESS, PORT, False, status.RUNNING, True, True),
                                                     (ADDRESS, -1, False, status.DISCONNECTING, True, True),
                                                     ("wappstoFail.com", PORT, False, status.DISCONNECTING, True, True)])
    def test_connection(self, address, port, callback_exists, expected_status, value_changed_to_none, upgradable):
        # Arrange
        status_service = self.service.get_status()
        fix_object(self, callback_exists, status_service)
        if value_changed_to_none:
            self.service.instance.network_cl.name = None

        # Act
        with patch('os.getenv', return_value=str(upgradable)):
            try:
                fake_connect(self, address, port)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = ast.literal_eval(args[0].decode('utf-8'))
                sent_json = json.loads(arg[0])['params']['data']
            except wappsto_errors.ServerConnectionException:
                sent_json = None
                pass

        # Assert
        if sent_json != None:
            assert not 'None' in str(sent_json)
            assert (upgradable and 'upgradable' in str(sent_json['meta']) or
                    not upgradable and not 'upgradable' in str(sent_json['meta']))
        assert self.service.status.get_status() == expected_status

class TestValueSendClass:

    @classmethod
    def setup_class(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("input,step_size,expected", [(8, 1, "8"),# value on the step
                                                     (8, -1, "8"),
                                                     (-8, 1, "-8"),
                                                     (-8, -1, "-8"),
                                                     (100, 1, "1E+2"),
                                                     (-100, 1, "-1E+2"),
                                                     (0, 1, "0"),
                                                     (-0, 1, "0"),
                                                     (-99.9, 1, "-1E+2"),# decimal value
                                                     (-0.1, 1, "-1"),
                                                     (0.1, 1, "0"),
                                                     (3.3, 1, "3"),
                                                     (3.0, 1, "3"),
                                                     (3.9, 1, "3"),
                                                     (-0.1, 1, "-1"),
                                                     (-3.3, 1, "-4"),
                                                     (-3.0, 1, "-3"),
                                                     (-3.9, 1, "-4"),
                                                     (-101, 1, None),# out of range
                                                     (101, 1, None),
                                                     (3, 2, "2"),# big steps
                                                     (3.999, 2, "2"),
                                                     (4, 2, "4"),
                                                     (-3, 2, "-4"),
                                                     (-3.999, 2, "-4"),
                                                     (-4, 2, "-4"),
                                                     (1, 0.5, "1"),# decimal steps
                                                     (1.01, 0.02, "1"),
                                                     (2.002, 0.02, "2"),
                                                     (2.002, 0.0002, "2.002"),
                                                     (-1, 0.5, "-1"),
                                                     (-1.01, 0.02, "-1.02"),
                                                     (-2.002, 0.02, "-2.02"),
                                                     (-2.002, 0.0002, "-2.002"),
                                                     (2, 1.0e-07, "2"),
                                                     (2, 123.456e-5, "1.9999872")])
    def test_send_value_update(self, input, step_size, expected):
        # Arrange
        self.service.socket.my_socket.send = Mock()
        device = self.service.get_devices()[0]
        value = device.value_list[0]
        value.number_step = step_size

        # Act
        try:
            value.update(input)
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = ast.literal_eval(args[0].decode('utf-8'))
            result = json.loads(arg[0])['params']['data']['data']
        except TypeError:
            result = None

        # Assert
        assert result == expected

    @classmethod
    def teardown_class(self):
        self.service.stop()


class TestReceiveThreadClass:

    @classmethod
    def setup_class(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("id,verb,callback_exists,trace_id,expected_rpc_id,expected_msg_id,expected_trace_id",
                             [(1, 'PUT', True, None, '1', message_data.SEND_SUCCESS, None),
                              (1, 'PUT', False, None, '1', message_data.SEND_FAILED, None),
                              (1, 'DELETE', True, None, '1', message_data.SEND_SUCCESS, None),
                              (1, 'DELETE', False, None, '1', message_data.SEND_SUCCESS, None),
                              (1, 'GET', True, None, '1', message_data.SEND_SUCCESS, None),
                              (1, 'GET', False, None, '1', message_data.SEND_SUCCESS, None),
                              (1, 'wrong_verb', False, None, '1', message_data.SEND_FAILED, None),
                              (1, 'wrong_verb', True, None, '1', message_data.SEND_FAILED, None),
                              (1, 'PUT', True, 321, None, message_data.SEND_TRACE, '321'),
                              (1, 'PUT', False, 321, '1', message_data.SEND_FAILED, None),
                              (1, 'DELETE', True, 321, None, message_data.SEND_TRACE, '321'),
                              (1, 'DELETE', False, 321, None, message_data.SEND_TRACE, '321'),
                              (1, 'GET', True, 321, None, message_data.SEND_TRACE, '321'),
                              (1, 'GET', False, 321, None, message_data.SEND_TRACE, '321'),
                              (1, 'wrong_verb', False, 321, '1', message_data.SEND_FAILED, None),
                              (1, 'wrong_verb', True, 321, '1', message_data.SEND_FAILED, None)
                             ])
    @pytest.mark.parametrize("bulk", [False, True])
    def test_receive_thread_method(self, id, verb, callback_exists, trace_id, 
                                   expected_rpc_id, expected_msg_id, expected_trace_id, bulk):
        # Arrange
        response = create_response(self, verb, callback_exists, trace_id, bulk)
        self.service.socket.my_socket.recv = Mock(side_effect=[response.encode('utf-8'), KeyboardInterrupt])

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        while self.service.socket.sending_queue.qsize() > 0:
            send = self.service.socket.sending_queue.get()
            assert (send.msg_id == message_data.SEND_SUCCESS or 
                    send.msg_id == expected_msg_id)

    @pytest.mark.parametrize("id,type", [(93043873, "error"),(93043873, "result")])
    def test_receive_thread_other(self, id, type):
        # Arrange
        response = '{"jsonrpc": "2.0", "id": "'+ str(id) +'", "'+type+'": {"value": "True", "meta": {"server_send_time": "2020-01-22T08:22:55.315Z"}}}'
        self.service.socket.packet_awaiting_confirm[str(id)] = response
        self.service.socket.my_socket.recv = Mock(side_effect=[response.encode('utf-8'), KeyboardInterrupt])

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert len(self.service.socket.packet_awaiting_confirm) == 0

    @classmethod
    def teardown_class(self):
        self.service.stop()


class TestSendThreadClass:

    @classmethod
    def setup_class(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("id,type", [(93043873, message_data.SEND_SUCCESS),
                                         (93043873, message_data.SEND_REPORT),
                                         (93043873, message_data.SEND_FAILED),
                                         (93043873, message_data.SEND_RECONNECT),
                                         (93043873, message_data.SEND_CONTROL)])
    @pytest.mark.parametrize("messages_in_queue", [1, 2])
    def test_send_thread(self, id, type, messages_in_queue):
        # Arrange
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                type,
                rpc_id=id
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.add_id_to_confirm_list = Mock()

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except KeyboardInterrupt:
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = args[0].decode('utf-8')

        # Assert
        assert self.service.socket.sending_queue.qsize() == 0
        
        requests = ast.literal_eval(arg)
        assert messages_in_queue == len(requests)
        for request in requests:
            request = json.loads(request)
            if type == message_data.SEND_SUCCESS:
                assert request['id'] == id
                assert bool(request['result']) == True
            elif type == message_data.SEND_FAILED:
                assert request['id'] == id
                assert request['error'] == json.loads('{"code": -32020, "message": null}')
            elif type == message_data.SEND_REPORT:
                assert request['params']['data']['type'] == "Report"
                assert request['method'] == "PUT"
            elif type == message_data.SEND_RECONNECT:
                assert request['params']['data']['meta']['type'] == "network"
                assert request['method'] == "POST"
            elif type == message_data.SEND_CONTROL:
                assert request['params']['data']['type'] == "Control"
                assert request['method'] == "PUT"

    @pytest.mark.parametrize("rpc_id,expected_trace_id,type", [(93043873, 332, message_data.SEND_TRACE)])
    def test_send_thread_send_trace(self, rpc_id, expected_trace_id, type):
        # Arrange
        reply = message_data.MessageData(
            type,
            trace_id = expected_trace_id,
            rpc_id=rpc_id
        )
        self.service.socket.sending_queue.put(reply)

        # Act
        with patch('urllib.request.urlopen', side_effect=KeyboardInterrupt) as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                self.service.socket.send_thread()
            except KeyboardInterrupt:
                args, kwargs = urlopen.call_args
                arg = urllib.parse.parse_qs(args[0])
        result_trace_id = int(arg['https://tracer.iot.seluxit.com/trace?id'][0])

        # Assert
        assert result_trace_id == expected_trace_id

    @classmethod
    def teardown_class(self):
        self.service.stop()
