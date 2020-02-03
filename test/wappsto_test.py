#!/usr/bin/env python3
import os
import json
import pytest
import wappsto
from mock import Mock
from unittest.mock import patch

from wappsto.connection import send_data
from wappsto.object_instantiation import status
from wappsto.connection.network_classes.errors import wappsto_errors

ADDRESS = "wappsto.com"
PORT = 11006
TEST_JSON = "test_JSON/b03f246d-63ef-446d-be58-ef1d1e83b338.json"
TEST_JSON_prettyprint = "test_JSON/b03f246d-63ef-446d-be58-ef1d1e83b338_prettyprint.json"


def check_for_correct_conn(*args, **kwargs):
    if args[0][0] != ADDRESS or args[0][1] != PORT:
        raise wappsto_errors.ServerConnectionException


def fake_connect(self, address, port):
    wappsto.RETRY_LIMIT = 2
    with patch('wappsto.communication.ssl.SSLContext.wrap_socket') as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), patch('wappsto.communication.socket.socket'), patch('wappsto.communication.ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port)


def get_send_thread_values(self, type, args, id):
    results = []
    if type == 1:
        results.append(TestResult(args['id'], id))
        results.append(TestResult(bool(args['result']), True))
    elif type == 2:
        results.append(TestResult(args['id'], id))
        results.append(TestResult(args['error'],
                                  json.loads(
                                      '{"code": -32020, "message": null}')))
    elif type == 3:
        results.append(TestResult(args['params']['data']['type'], "Report"))
        results.append(TestResult(args['method'], "PUT"))
    elif type == 4:
        results.append(TestResult(args['params']['data']['meta']['type'],
                                  "network"))
        results.append(TestResult(args['method'], "POST"))
    elif type == 5:
        results.append(TestResult(args['params']['data']['type'], "Control"))
        results.append(TestResult(args['method'], "PUT"))
    return results


def fix_object(self, callback_exists, testing_object):
    if callback_exists:
        test_callback = Mock(return_value=True)
        testing_object.set_callback(test_callback)
    else:
        testing_object.callback = None
    return testing_object


def create_response(self, verb, callback_exists):
    if verb == "DELETE":
        network = self.service.get_network()
        network = fix_object(self, callback_exists, network)
        response = '{"jsonrpc": "2.0", "id": "1", "params": {"url": "' + str(network.uuid) + '"}, "method": "DELETE"}'
    elif verb == "PUT":
        value = self.service.instance.device_list[0].value_list[0]
        value = fix_object(self, callback_exists, value)
        response = '{"jsonrpc": "2.0", "id": "1", "params": {"data": {"meta": {"id": "'+str(value.control_state.uuid)+'"}, "data": "93"}}, "method": "PUT"}'
    elif verb == "GET":
        value = self.service.instance.device_list[0].value_list[0]
        value = fix_object(self, callback_exists, value)
        response = '{"jsonrpc": "2.0", "id": "1", "params": {"url": "' + str(value.report_state.uuid) + '"}, "method": "GET"}'
    else:
        response = '{"jsonrpc": "2.0", "id": "1", "params": {"url": "/network/b03f246d-63ef-446d-be58-ef1d1e83b338/device/a0e087c1-9678-491c-ac47-5b065dea3ac0/value/7ce2afdd-3be3-4945-862e-c73a800eb209/state/a7b4f66b-2558-4559-9fcc-c60768083164", "data": {"meta": {"id": "a7b4f66b-2558-4559-9fcc-c60768083164", "type": "state", "version": "2.0"}, "type": "Report", "status": "Send", "data": "93", "timestamp": "2020-01-22T08:22:57.216500Z"}}, "method": "??????"}'

    return response


class TestResult:
    def __init__(self, received, expected):
        self.received = received
        self.expected = expected

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

    @pytest.mark.parametrize("address,port,callback_exists,expected_status", [(ADDRESS, PORT, True, status.RUNNING),
                                                     (ADDRESS, -1, True, status.DISCONNECTING),
                                                     ("wappstoFail.com", PORT, True, status.DISCONNECTING),
                                                     (ADDRESS, PORT, False, status.RUNNING),
                                                     (ADDRESS, -1, False, status.DISCONNECTING),
                                                     ("wappstoFail.com", PORT, False, status.DISCONNECTING)])
    def test_connection(self, address, port, callback_exists, expected_status):
        # Arrange
        status_service = self.service.get_status()
        fix_object(self, callback_exists, status_service)
        expected_json = json.loads(json.loads(open(self.test_json_location).read()).get('data'))

        # Act
        try:
            fake_connect(self, address, port)
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))
            sent_json = arg['params']['data']
        except wappsto_errors.ServerConnectionException:
            sent_json = None
            expected_json = None
            pass

        # Assert
        assert sent_json == expected_json
        assert self.service.status.get_status() == expected_status


class TestValueSendClass:

    @classmethod
    def setup_class(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("input,step_size,expected", [(8, 1, 8),
                                                     (100, 1, 100),
                                                     (0, 1, 0),
                                                     (-1, 1, None),
                                                     (120, 1, None),
                                                     (-0.1, 1, None),
                                                     (0.1, 1, 0),
                                                     (3.3, 1, 3),
                                                     (3.0, 1, 3),
                                                     (3.9, 1, 3),
                                                     (3, 2, 2),
                                                     (3.999, 2, 2),
                                                     (4, 2, 4),
                                                     (1.01, 0.02, 1.0),
                                                     (2.002, 0.02, 2.0),
                                                     (2.002, 0.0002, 2.002)])
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
            arg = json.loads(args[0].decode('utf-8'))
            result = float(arg['params']['data']['data'])
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

    '''
    Testing test_receive_thread_method specificaly
    '''

    @pytest.mark.parametrize("id,verb,callback_exists,expected",
                             [(1, 'PUT', True, send_data.SEND_SUCCESS),
                              (1, 'PUT', False, send_data.SEND_FAILED),
                              (1, 'DELETE', True, send_data.SEND_SUCCESS),
                              (1, 'DELETE', False, send_data.SEND_SUCCESS),
                              (1, 'GET', True, send_data.SEND_SUCCESS),
                              (1, 'GET', False, send_data.SEND_SUCCESS),
                              (1, 'wrong_verb', False, send_data.SEND_FAILED),
                              (1, 'wrong_verb', True, send_data.SEND_FAILED)])
    def test_receive_thread_method(self, id, verb, callback_exists, expected):
        # Arrange
        response = create_response(self, verb, callback_exists)
        self.service.socket.my_socket.recv = Mock(
            return_value=response.encode('utf-8'))
        self.service.socket.sending_queue.put = Mock(side_effect=Exception)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except Exception:
            args, kwargs = self.service.socket.sending_queue.put.call_args

        # Assert
        assert int(args[0].rpc_id) == id
        assert args[0].msg_id == expected

    '''
    Testing test_receive_thread_other specificaly
    '''

    @pytest.mark.parametrize("id,type", [(93043873, "error"),
                                         (93043873, "result")])
    def test_receive_thread_other(self, id, type):
        # Arrange
        response = '{"jsonrpc": "2.0", "id": "'+ str(id) +'", "'+type+'": {"value": "True", "meta": {"server_send_time": "2020-01-22T08:22:55.315Z"}}}'
        self.service.socket.my_socket.recv = Mock(
            return_value=response.encode('utf-8'))
        self.service.socket.remove_id_from_confirm_list = Mock(
            side_effect=Exception)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except Exception:
            args, kwargs = self.service.socket.remove_id_from_confirm_list.call_args

        # Assert
        assert int(args[0]) == id

    @classmethod
    def teardown_class(self):
        self.service.stop()


class TestSendThreadClass:

    @classmethod
    def setup_class(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    #SEND_TRACE not added yet
    @pytest.mark.parametrize("id,type", [(93043873, send_data.SEND_SUCCESS),
                                         (93043873, send_data.SEND_FAILED),
                                         (93043873, send_data.SEND_REPORT),
                                         (93043873, send_data.SEND_RECONNECT),
                                         (93043873, send_data.SEND_CONTROL)])
    def test_send_thread(self, id, type):
        # Arrange
        reply = send_data.SendData(
            type,
            rpc_id=id
        )
        self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=Exception)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except Exception:
            args, kwargs = self.service.socket.my_socket.send.call_args

        args = json.loads(args[0].decode('utf-8'))

        # Assert
        for result in get_send_thread_values(self, type, args, id):
            assert result.received == result.expected

    @classmethod
    def teardown_class(self):
        self.service.stop()
