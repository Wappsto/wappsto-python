#!/usr/bin/env python3
import os
import json
import pytest
import wappsto
import urllib.parse
from mock import Mock
from unittest.mock import patch
import urllib.parse as urlparse
from urllib.parse import parse_qs

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


def stop_if_success_or_failed(*args, **kwargs):
    if args[0].msg_id == send_data.SEND_SUCCESS or args[0].msg_id == send_data.SEND_FAILED:
        raise Exception


def check_if_element_exists(change_indicator, key_name, dict1, dict2):
    result1 = exists_in_dictionary(key_name,dict1)
    result2 = exists_in_dictionary(key_name,dict2)
    return (change_indicator and result1 != result2) or (not change_indicator and result1 == result2)


def fake_connect(self, address, port, send_trace = False):
    wappsto.RETRY_LIMIT = 2
    with patch('wappsto.communication.ssl.SSLContext.wrap_socket') as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), patch('wappsto.communication.socket.socket'), patch('wappsto.communication.ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port, automatic_trace=send_trace)


def get_send_thread_values(type, args, id, send_trace):
    results = []
    if type == 1:
        results.append(TestResult(received = args['id'], expected = id))
        results.append(TestResult(received = bool(args['result']), 
                                  expected = True))
    elif type == 2:
        results.append(TestResult(received = args['id'], expected = id))
        results.append(TestResult(received = args['error'],
                                  expected = json.loads(
                                      '{"code": -32020, "message": null}')))
    elif type == 3:
        results.append(TestResult(received = args['params']['data']['type'],
                                  expected = "Report"))
        results.append(TestResult(received = args['method'], expected = "PUT"))
        results.append(TestResult(received = "?trace=" in str(args['params']['url']), 
                                  expected = send_trace))
    elif type == 4:
        results.append(TestResult(received = args['params']['data']['meta']['type'],
                                  expected = "network"))
        results.append(TestResult(received = args['method'], expected = "POST"))
        results.append(TestResult(received = "?trace=" in str(args['params']['url']), 
                                  expected = send_trace))
    elif type == 5:
        results.append(TestResult(received = args['params']['data']['type'], 
                                  expected = "Control"))
        results.append(TestResult(received = args['method'], expected = "PUT"))
        results.append(TestResult(received = "?trace=" in str(args['params']['url']), 
                                  expected = send_trace))
    return results


def fix_object_callback(callback_exists, testing_object):
    if callback_exists:
        test_callback = Mock(return_value=True)
        testing_object.set_callback(test_callback)
    else:
        testing_object.callback = None
    return testing_object


def create_response(self, verb, callback_exists, trace_id):
    value = self.service.instance.device_list[0].value_list[0]
    value = fix_object_callback(callback_exists, value)
    id = str(value.control_state.uuid)
    url = str(value.report_state.uuid)
    trace = ''

    if verb == "DELETE":
        network = self.service.get_network()
        network = fix_object_callback(callback_exists, network)
        url = str(network.uuid)
    elif verb == "PUT" or verb == "GET":
        pass
        # may be used later
    else:
        return '{"jsonrpc": "2.0", "id": "1", "params": {}, "method": "??????"}'

    if trace_id is not None:
        trace = '"meta": {"trace": "'+trace_id+'"},'

    return '{"jsonrpc": "2.0", "id": "1", "params": {"url": "'+url+'",'+trace+' "data": {"meta": {"id": "'+id+'"}, "data": "93"}}, "method": "'+verb+'"}'


def get_expected_json(self):
    # gets the loaded json and modifies it according to the expected changes when compared to the sent json
    expected_json = json.loads(self.service.instance.decoded.get('data'))
    for device in expected_json['device']:
        device['version'] = '2.0'
        for value in device['value']:
            states = value['state']
            if len(states) > 1:
                for state in states:
                    state['data'] = states[0]['data']
                    del state['meta']['contract']
    return expected_json


def exists_in_dictionary(key, dict):
    return True if key in dict else False


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

    @pytest.mark.parametrize("address,port,expected_status", [(ADDRESS, PORT, status.RUNNING),
                                              (ADDRESS, -1, status.DISCONNECTING),
                                              ("wappstoFail.com", PORT, status.DISCONNECTING),
                                              ("wappstoFail.com", -1, status.DISCONNECTING)])
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("callback_exists", [True, False])
    @pytest.mark.parametrize("value_changed_to_none", [True, False])
    @pytest.mark.parametrize("upgradable", [True, False])
    def test_connection(self, address, port, expected_status, send_trace, callback_exists, value_changed_to_none, upgradable):
        # Arrange
        status_service = self.service.get_status()
        fix_object_callback(callback_exists, status_service)
        expected_json_data = get_expected_json(self)
        urlopen_trace_id = sent_json_trace_id = ''
        if value_changed_to_none:
            self.service.instance.network_cl.name = None

        # Act
        with patch('urllib.request.urlopen') as urlopen, patch('os.getenv', return_value=str(upgradable)):
            try:
                fake_connect(self, address, port, send_trace)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))
                sent_json_data = arg['params']['data']
                
                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']
    
                    parsed_sent_json = urlparse.urlparse(arg['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']

            except wappsto_errors.ServerConnectionException:
                sent_json_data = None
                expected_json_data = None
                send_trace = False

        # Assert
        assert (#trace ids sent in urlopen and request
                urlopen_trace_id == sent_json_trace_id and
                send_trace and urlopen_trace_id != '' or
                not send_trace and urlopen_trace_id == ''
               )
        assert (#compares dictionaries
                (sent_json_data == None and expected_json_data == None) or
                check_if_element_exists(value_changed_to_none, 'name', expected_json_data, sent_json_data) and
                check_if_element_exists(upgradable, 'upgradable', expected_json_data['meta'], sent_json_data['meta'])
               )
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
                                                     (100, 1, "100"),
                                                     (-100, 1, "-100"),
                                                     (0, 1, "0"),
                                                     (-0, 1, "0"),
                                                     (-99.9, 1, "-100"),# decimal value
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
                                                     (-2.002, 0.0002, "-2.002")])
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
            result = arg['params']['data']['data']
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

    @pytest.mark.parametrize("verb,callback_exists,expected_msg_id,trace_id", [('PUT', True, send_data.SEND_SUCCESS, None),
                                       ('DELETE', True, send_data.SEND_SUCCESS, None),
                                       ('GET', True, send_data.SEND_SUCCESS, None),
                                       ('wrong_verb', True, send_data.SEND_FAILED, None),
                                       ('PUT', False, send_data.SEND_FAILED, None),
                                       ('DELETE', False, send_data.SEND_SUCCESS, None),
                                       ('GET', False, send_data.SEND_SUCCESS, None),
                                       ('wrong_verb', False, send_data.SEND_FAILED, None),
                                       ('PUT', True, send_data.SEND_TRACE, '123'),
                                       ('DELETE', True, send_data.SEND_TRACE, '123'),
                                       ('GET', True, send_data.SEND_TRACE, '123'),
                                       ('wrong_verb', True, send_data.SEND_FAILED, '123'),
                                       ('PUT', False, send_data.SEND_FAILED, '123'),
                                       ('DELETE', False, send_data.SEND_TRACE, '123'),
                                       ('GET', False, send_data.SEND_TRACE, '123'),
                                       ('wrong_verb', False, send_data.SEND_FAILED, '123')])
    def test_receive_thread_method(self, verb, callback_exists, expected_msg_id, trace_id):
        # Arrange
        response = create_response(self, verb, callback_exists, trace_id)
        self.service.socket.my_socket.recv = Mock(
            return_value=response.encode('utf-8'))
        self.service.socket.sending_queue.put = Mock(side_effect=stop_if_success_or_failed)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except Exception:
            args = self.service.socket.sending_queue.put.call_args_list

        # Assert
        assert args[0][0][0].msg_id == expected_msg_id

        if expected_msg_id == send_data.SEND_TRACE:
            assert args[0][0][0].trace_id == trace_id
            assert args[1][0][0].msg_id == send_data.SEND_SUCCESS

    @pytest.mark.parametrize("id", [93043873])
    @pytest.mark.parametrize("type", ["error", "result"])
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

    @pytest.mark.parametrize("type,send_trace", [(send_data.SEND_SUCCESS, False),
                                         (send_data.SEND_REPORT, False),
                                         (send_data.SEND_FAILED, False),
                                         (send_data.SEND_RECONNECT, False),
                                         (send_data.SEND_CONTROL, False),
                                         (send_data.SEND_REPORT, True),
                                         (send_data.SEND_RECONNECT, True),
                                         (send_data.SEND_CONTROL, True)])
    @pytest.mark.parametrize("id", [93043873])
    def test_send_thread(self, id, type, send_trace):
        # Arrange
        reply = send_data.SendData(
            type,
            rpc_id=id
        )
        self.service.socket.automatic_trace = send_trace
        self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=Exception)
        urlopen_trace_id = sent_json_trace_id = ''

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                self.service.socket.send_thread()
            except Exception:
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))

                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']
    
                    parsed_sent_json = urlparse.urlparse(arg['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']

        # Assert
        assert urlopen_trace_id == sent_json_trace_id and (
            not send_trace and urlopen_trace_id == '' or
            send_trace and urlopen_trace_id != ''
            )
        for result in get_send_thread_values(type, arg, id, send_trace):
            assert result.received == result.expected

    @pytest.mark.parametrize("rpc_id", [93043873])
    @pytest.mark.parametrize("type", [send_data.SEND_TRACE])
    @pytest.mark.parametrize("trace_id", [332])
    def test_send_thread_send_trace(self, rpc_id, trace_id, type):
        # Arrange
        reply = send_data.SendData(
            type,
            trace_id = trace_id,
            rpc_id=rpc_id
        )
        self.service.socket.sending_queue.put(reply)
        
        # Act
        with patch('urllib.request.urlopen', side_effect=Exception) as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                self.service.socket.send_thread()
            except Exception:
                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_id = urlparse.urlparse(urlopen_args[0])
                    parsed_id = int(parse_qs(parsed_id.query)['id'][0])

        # Assert
        assert parsed_id == trace_id

    @classmethod
    def teardown_class(self):
        self.service.stop()
