#!/usr/bin/env python3
import os
import json
import pytest
import wappsto
from mock import Mock
from unittest.mock import patch
import urllib.parse as urlparse
from urllib.parse import parse_qs

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


def stop_if_success_or_failed(*args, **kwargs):
    if args[0].msg_id == message_data.SEND_SUCCESS or args[0].msg_id == message_data.SEND_FAILED:
        raise Exception


def check_if_element_exists(change_indicator, key_name, dict1, dict2):
    result1 = exists_in_dictionary(key_name, dict1)
    result2 = exists_in_dictionary(key_name, dict2)
    return (change_indicator and result1 != result2) or (not change_indicator and result1 == result2)


def fake_connect(self, address, port, send_trace=False):
    wappsto.RETRY_LIMIT = 2
    with patch('ssl.SSLContext.wrap_socket') as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), patch('threading.Thread'), patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), patch('socket.socket'), patch('ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port, automatic_trace=send_trace)


def fix_object_callback(callback_exists, testing_object):
    if callback_exists:
        test_callback = Mock(return_value=True)
        testing_object.set_callback(test_callback)
    else:
        testing_object.callback = None
    return testing_object


def create_response(self, verb, callback_exists, trace_id, bulk):
    value = self.service.instance.device_list[0].value_list[0]
    value = fix_object_callback(callback_exists, value)
    id = str(value.control_state.uuid)
    url = str(value.report_state.uuid)
    trace = ''

    if verb == "DELETE":
        network = self.service.get_network()
        network = fix_object_callback(callback_exists, network)
        url = str(network.uuid)

    if verb == "DELETE" or verb == "PUT" or verb == "GET":
        if trace_id is not None:
            trace = {"trace": trace_id}

        message = {"jsonrpc": "2.0", "id": "1", "params": {"url": url, "meta": trace, "data": {"meta": {"id": id}, "data": "44"}}, "method": verb}
    else:
        message = {"jsonrpc": "2.0", "id": "1", "params": {"url": "/network/b03f246d-63ef-446d-be58-ef1d1e83b338/device/a0e087c1-9678-491c-ac47-5b065dea3ac0/value/7ce2afdd-3be3-4945-862e-c73a800eb209/state/a7b4f66b-2558-4559-9fcc-c60768083164", "data": {"meta": {"id": "a7b4f66b-2558-4559-9fcc-c60768083164", "type": "state", "version": "2.0"}, "type": "Report", "status": "Send", "data": "44", "timestamp": "2020-01-22T08:22:57.216500Z"}}, "method": "??????"}

    if bulk:
        message = [message, message]
    message = json.dumps(message)

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

    @pytest.mark.parametrize("address,port,expected_status",
                             [(ADDRESS, PORT, status.RUNNING),
                              (ADDRESS, -1, status.DISCONNECTING),
                              ("wappstoFail.com", PORT, status.DISCONNECTING),
                              ("wappstoFail.com", -1, status.DISCONNECTING)])
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("callback_exists", [True, False])
    @pytest.mark.parametrize("value_changed_to_none", [True, False])
    @pytest.mark.parametrize("upgradable", [True, False])
    def test_connection(self, address, port, expected_status, send_trace,
                        callback_exists, value_changed_to_none, upgradable):
        # Arrange
        status_service = self.service.get_status()
        fix_object_callback(callback_exists, status_service)
        urlopen_trace_id = sent_json_trace_id = ''
        if value_changed_to_none:
            self.service.instance.network_cl.name = None

        # Act
        with patch('urllib.request.urlopen') as urlopen, patch('os.getenv', return_value=str(upgradable)):
            try:
                fake_connect(self, address, port, send_trace)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))
                sent_json = arg[0]['params']['data']

                if send_trace:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                    parsed_sent_json = urlparse.urlparse(arg[0]['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']

            except wappsto_errors.ServerConnectionException:
                sent_json = None

        # Assert
        if sent_json is not None:
            assert not 'None' in str(sent_json)
            assert sent_json_trace_id == urlopen_trace_id
            assert (send_trace and urlopen_trace_id != '' or
                    not send_trace and urlopen_trace_id == '')
            assert (upgradable and 'upgradable' in str(sent_json['meta']) or
                    not upgradable and not 'upgradable' in str(sent_json['meta']))
        assert self.service.status.get_status() == expected_status

class TestValueSendClass:

    def setup_method(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)

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
                                                     (-2.002, 0.0002, "-2.002"),
                                                     (2, 1.0e-07, "2"),
                                                     (2, 123.456e-5, "1.9999872"),
                                                     (1, 9.0e-20, "0.99999999999999999999")])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_value_update(self, input, step_size, expected, send_trace):
        # Arrange
        with patch('urllib.request.urlopen'):
            fake_connect(self, ADDRESS, PORT, send_trace)
        self.service.socket.message_received = True
        self.service.socket.my_socket.send = Mock()
        urlopen_trace_id = sent_json_trace_id = ''
        device = self.service.get_devices()[0]
        value = device.value_list[0]
        value.number_step = step_size

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                value.update(input)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))
                result = arg[0]['params']['data']['data']
    
                if send_trace:
                    urlopen_args, urlopen_kwargs = urlopen.call_args
    
                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']
    
                    parsed_sent_json = urlparse.urlparse(arg[0]['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            except TypeError:
                result = None

        # Assert
        assert result == expected
        assert sent_json_trace_id == urlopen_trace_id
        if send_trace and result is not None:
            assert urlopen_trace_id != ''
        else:
            assert urlopen_trace_id == ''


class TestReceiveThreadClass:

    def setup_method(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)


    @pytest.mark.parametrize("verb,callback_exists,trace_id,expected_msg_id,expected_data_value",
                             [('PUT', True, None, message_data.SEND_SUCCESS, '44'),
                              ('PUT', False, None, message_data.SEND_FAILED, '44'),
                              ('DELETE', True, None, message_data.SEND_SUCCESS, '1'),
                              ('DELETE', False, None, message_data.SEND_SUCCESS, '1'),
                              ('GET', True, None, message_data.SEND_SUCCESS, '1'),
                              ('GET', False, None, message_data.SEND_SUCCESS, '1'),
                              ('wrong_verb', False, None, message_data.SEND_FAILED, '1'),
                              ('wrong_verb', True, None, message_data.SEND_FAILED, '1'),
                              ('PUT', True, '321', message_data.SEND_TRACE, '44'),
                              ('PUT', False, '321', message_data.SEND_FAILED, '44'),
                              ('DELETE', True, '321', message_data.SEND_TRACE, '1'),
                              ('DELETE', False, '321', message_data.SEND_TRACE, '1'),
                              ('GET', True, '321', message_data.SEND_TRACE, '1'),
                              ('GET', False, '321',  message_data.SEND_TRACE, '1'),
                              ('wrong_verb', False, '321',  message_data.SEND_FAILED, '1'),
                              ('wrong_verb', True, '321', message_data.SEND_FAILED, '1')
                             ])
    @pytest.mark.parametrize("bulk", [False, True])
    def test_receive_thread_method(self, verb, callback_exists, trace_id,
                                   expected_msg_id,
                                   expected_data_value, bulk):
        # Arrange
        value = self.service.instance.device_list[0].value_list[0]
        value.control_state.data = 1
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
            if send.msg_id == message_data.SEND_SUCCESS:
                send.data == expected_data_value
            else:
                assert send.msg_id == expected_msg_id
                if send.msg_id == message_data.SEND_TRACE:
                    assert send.trace_id == trace_id

    @pytest.mark.parametrize("id", [93043873])
    @pytest.mark.parametrize("type", ["error", "result"])
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


class TestSendThreadClass:

    def setup_method(self):
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("type,send_trace", [(message_data.SEND_SUCCESS, False),
                                                 (message_data.SEND_REPORT, False),
                                                 (message_data.SEND_FAILED, False),
                                                 (message_data.SEND_RECONNECT, False),
                                                 (message_data.SEND_CONTROL, False),
                                                 (message_data.SEND_REPORT, True),
                                                 (message_data.SEND_RECONNECT, True),
                                                 (message_data.SEND_CONTROL, True)])
    @pytest.mark.parametrize("value,expected_value", [('test_value','test_value'),
                                                                ('', ''),
                                                                (None, None),
                                                                ([],None)])
    @pytest.mark.parametrize("messages_in_queue", [1, 2])
    def test_send_thread(self, type, messages_in_queue, value, expected_value, send_trace):
        # Arrange
        self.service.socket.message_received = True
        self.service.get_network().name = value
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                type,
                rpc_id=value,
                data=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.add_id_to_confirm_list = Mock()
        self.service.socket.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                self.service.socket.send_thread()
            except KeyboardInterrupt:
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = args[0].decode('utf-8')
                requests = json.loads(arg)

                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))

                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                    parsed_sent_json = urlparse.urlparse(arg[messages_in_queue-1]['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']

        # Assert
        assert urlopen_trace_id == sent_json_trace_id
        if send_trace:
            assert urlopen_trace_id != ''
        else:
            assert urlopen_trace_id == ''
        assert self.service.socket.sending_queue.qsize() == 0
        assert messages_in_queue == len(requests)
        for request in requests:
            if type == message_data.SEND_SUCCESS:
                assert request.get('id', None) == expected_value
                assert bool(request['result']) == True
            elif type == message_data.SEND_FAILED:
                assert request.get('id', None) == expected_value
                assert request['error'] == {"code": -32020}
            elif type == message_data.SEND_REPORT:
                assert request['params']['data'].get('data', None) == expected_value
                assert request['params']['data']['type'] == "Report"
                assert request['method'] == "PUT"
            elif type == message_data.SEND_RECONNECT:
                assert request['params']['data'].get('name', None) == expected_value
                assert request['params']['data']['meta']['type'] == "network"
                assert request['method'] == "POST"
            elif type == message_data.SEND_CONTROL:
                assert request['params']['data'].get('data', None) == expected_value
                assert request['params']['data']['type'] == "Control"
                assert request['method'] == "PUT"

    @pytest.mark.parametrize("rpc_id", [93043873])
    @pytest.mark.parametrize("type", [message_data.SEND_TRACE])
    @pytest.mark.parametrize("trace_id", [332])
    def test_send_thread_send_trace(self, rpc_id, trace_id, type):
        # Arrange
        reply = message_data.MessageData(
            type,
            trace_id=trace_id,
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
                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_id = urlparse.urlparse(urlopen_args[0])
                    parsed_id = int(parse_qs(parsed_id.query)['id'][0])

        # Assert
        assert parsed_id == trace_id
