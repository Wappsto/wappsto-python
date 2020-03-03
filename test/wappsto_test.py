"""
The test module.

Tests wappsto project functionality.
"""
import os
import math
import json
import pytest
import wappsto
import jsonschema
import urllib.parse
from mock import Mock
from unittest.mock import patch

from wappsto import status
from wappsto.connection import message_data
from wappsto.connection.network_classes.errors import wappsto_errors

ADDRESS = "wappsto.com"
PORT = 11006
TEST_JSON = "test_JSON/test_json.json"
TEST_JSON_prettyprint = "test_JSON/test_json_prettyprint.json"


def check_for_correct_conn(*args, **kwargs):
    """
    Check if connection is valid.

    Reviews the provided address and port, if it does not correspond to expected values raises the same exception,
    that would be raised when inputting wrong details.

    Args:
        args: arguments that method was called with
        kwargs: key worded arguments

    """
    if args[0][0] != ADDRESS or args[0][1] != PORT:
        raise wappsto_errors.ServerConnectionException


def fake_connect(self, address, port):
    """
    Creates fake connection.

    Mocks the connection so no call would leave this environment, also makes application faster for tests.

    Args:
        self: the instance of the calling object
        address: address used for connecting to server
        port: port used for connecting to server

    """
    wappsto.RETRY_LIMIT = 2
    with patch('ssl.SSLContext.wrap_socket') as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), patch('threading.Thread'), \
            patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), \
                patch('socket.socket'), \
                patch('ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port)


def fix_object(callback_exists, testing_object):
    """
    Add callback to object.

    Depending on callback_exists variable, either adds mock to callback or sets it to None.

    Args:
        callback_exists: boolean indicating if callback should exist.
        testing_object: object to whom callback needs to be set.

    """
    if callback_exists:
        test_callback = Mock(return_value=True)
        testing_object.set_callback(test_callback)
    else:
        testing_object.callback = None


def get_object(self, object_name):
    """
    Get object from newtwork.

    Get object based on the name provided.

    Args:
        object_name: name indicating the object being searched for.

    Returns:
        the found object

    """
    actual_object = None
    if object_name == "network":
        actual_object = self.service.instance.network
    elif object_name == "device":
        actual_object = self.service.instance.network.devices[0]
    elif object_name == "value":
        actual_object = self.service.instance.network.devices[0].values[0]
    elif object_name == "control_state":
        actual_object = self.service.instance.network.devices[0].values[0].get_control_state()
    elif object_name == "report_state":
        actual_object = self.service.instance.network.devices[0].values[0].get_report_state()
    return actual_object


def send_response(self, verb, trace_id, bulk, id, url, data, split_message):
    """
    Sends response.

    Sends responses to be used in receive tests based on the parameters provided.

    Args:
        verb: specifies if request is DELETE/PUT/POST/GET
        trace_id: id used for tracing messages
        bulk: Boolean value indicating if multiple messages should be sent at once.
        id: specifies id used in message
        url: url sent in message parameters
        data: data to be sent
        split_message: Boolean value indicating if message should be sent in parts

    Returns:
        the generated message

    """
    trace = ''

    if verb == "DELETE" or verb == "PUT" or verb == "GET":
        if trace_id is not None:
            trace = {"trace": str(trace_id)}

        message = {"jsonrpc": "2.0",
                   "id": "1",
                   "params": {
                       "url": str(url),
                       "meta": trace,
                       "data": {
                           "meta": {
                               "id": id},
                           "data": data}},
                   "method": verb}
    else:
        if verb == "error" or verb == "result":
            if data:
                message_value = {'data': data,
                                 'type': 'Control',
                                 'timestamp': '2020-01-20T09:20:21.092Z',
                                 'meta': {
                                     'type': 'state',
                                     'version': '2.0',
                                     'id': id,
                                     'manufacturer': '31439b87-040b-4b41-b5b8-f3774b2a1c19',
                                     'updated': '2020-02-18T09:14:12.880+00:00',
                                     'created': '2020-01-20T09:20:21.290+00:00',
                                     'revision': 1035,
                                     'contract': [],
                                     'owner': 'bb10f0f1-390f-478e-81c2-a67f58de88be'}}
            else:
                message_value = "True"
            message = {"jsonrpc": "2.0",
                       "id": str(id),
                       verb: {
                           "value": message_value,
                           "meta": {
                               "server_send_time": "2020-01-22T08:22:55.315Z"}}}
            self.service.socket.packet_awaiting_confirm[str(id)] = message
        else:
            message = {"jsonrpc": "2.0", "id": "1", "params": {}, "method": "??????"}

    if bulk:
        message = [message, message]
    message = json.dumps(message)

    if split_message:
        message_size = math.ceil(len(message) / 2)
        message1 = message[:message_size]
        message2 = message[message_size:]
        wappsto.connection.communication.RECEIVE_SIZE = message_size
        self.service.socket.my_socket.recv = Mock(side_effect=[message1.encode('utf-8'),
                                                               message2.encode('utf-8'),
                                                               KeyboardInterrupt])
    else:
        self.service.socket.my_socket.recv = Mock(side_effect=[message.encode('utf-8'),
                                                               KeyboardInterrupt])


def validate_json(json_schema, arg):
    """
    Validates json.

    Validates json and returns Boolean value indicating if it is valid.

    Args:
        json_schema: Schema to validate message against
        arg: sent message

    Returns:
        Boolean value indicating if message is valid

    """
    schema_location = os.path.join(
        os.path.dirname(__file__),
        "schema/" + json_schema + ".json")
    with open(schema_location, "r") as json_file:
        schema = json.load(json_file)
    base_uri = os.path.join(os.path.dirname(__file__), "schema")
    base_uri = base_uri.replace("\\", "/")
    base_uri = "file:///" + base_uri + "/"
    resolver = jsonschema.RefResolver(base_uri, schema)
    try:
        for i in arg:
            jsonschema.validate(i, schema, resolver=resolver)
        return True
    except jsonschema.exceptions.ValidationError:
        return False

# ################################## TESTS ################################## #


class TestJsonLoadClass:
    """
    TestJsonLoadClass instance.

    Tests loading json files in wappsto.

    """

    @classmethod
    def setup_class(self):
        """
        Sets up the class.

        Sets locations to be used in test.

        """
        self.test_json_prettyprint_location = os.path.join(
            os.path.dirname(__file__),
            TEST_JSON_prettyprint)
        self.test_json_location = os.path.join(
            os.path.dirname(__file__),
            TEST_JSON)

    def test_load_prettyprint_json(self):
        """
        Tests loading pretty print json.

        Loads pretty print json file and checks if it is read the same way as normal json file.

        """
        # Arrange
        with open(self.test_json_location, "r") as json_file:
            decoded = json.load(json_file)

        # Act
        service = wappsto.Wappsto(json_file_name=self.test_json_prettyprint_location)

        # Assert
        assert service.instance.decoded == decoded


class TestConnClass:
    """
    TestConnClass instance.

    Tests connecting to wappsto server.

    """

    def setup_method(self):
        """
        Sets up each method.

        Sets location to be used in test and initializes service.

        """
        self.test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=self.test_json_location)

    @pytest.mark.parametrize("""address,port,callback_exists,expected_status,
                             value_changed_to_none,upgradable""", [
        (ADDRESS, PORT, True, status.RUNNING, False, False),
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
    @pytest.mark.parametrize("valid_json", [True, False])
    def test_connection(self, address, port, callback_exists, expected_status,
                        value_changed_to_none, upgradable, valid_json):
        """
        Tests connection.

        Tests if connecting works es expected within different setup.

        Args:
            address: address used for connecting to server
            port: port used for connecting to server
            callback_exists: specifies if object should have callback
            expected_status: status expected after execution of the test
            value_changed_to_none: specifies if value should be replaced with none
            upgradable: specifies if object is upgradable
            valid_json: Boolean indicating if the sent json should be valid

        """
        # Arrange
        status_service = self.service.get_status()
        fix_object(callback_exists, status_service)
        if value_changed_to_none:
            self.service.instance.network.name = None
        if not valid_json:
            self.service.instance.network.uuid = None

        # Act
        with patch('os.getenv', return_value=str(upgradable)):
            try:
                fake_connect(self, address, port)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode('utf-8'))
                sent_json = arg[-1]['params']['data']
            except wappsto_errors.ServerConnectionException:
                sent_json = None
                arg = []
                pass

        # Assert
        if sent_json is not None:
            assert validate_json("request", arg) == valid_json
            assert 'None' not in str(sent_json)
            assert (upgradable and 'upgradable' in str(sent_json['meta'])
                    or not upgradable and 'upgradable' not in str(sent_json['meta']))
        assert self.service.status.get_status() == expected_status


class TestValueSendClass:
    """
    TestValueSendClass instance.

    Tests sending value to wappsto server.

    """

    def setup_method(self):
        """
        Sets up each method.

        Sets location to be used in test, initializes service and creates connection.

        """
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("input,step_size,expected", [
        (8, 1, "8"),  # value on the step
        (8, -1, "8"),
        (-8, 1, "-8"),
        (-8, -1, "-8"),
        (100, 1, "100"),
        (-100, 1, "-100"),
        (0, 1, "0"),
        (-0, 1, "0"),
        (-99.9, 1, "-100"),  # decimal value
        (-0.1, 1, "-1"),
        (0.1, 1, "0"),
        (3.3, 1, "3"),
        (3.0, 1, "3"),
        (3.9, 1, "3"),
        (0.02442002442002442, 1, "0"),
        (-0.1, 1, "-1"),
        (-3.3, 1, "-4"),
        (-3.0, 1, "-3"),
        (-3.9, 1, "-4"),
        (-101, 1, None),  # out of range
        (101, 1, None),
        (3, 2, "2"),  # big steps
        (3.999, 2, "2"),
        (4, 2, "4"),
        (-3, 2, "-4"),
        (-3.999, 2, "-4"),
        (-4, 2, "-4"),
        (1, 0.5, "1"),  # decimal steps
        (1.01, 0.02, "1"),
        (2.002, 0.02, "2"),
        (2.002, 0.0002, "2.002"),
        (-1, 0.5, "-1"),
        (-1.01, 0.02, "-1.02"),
        (-2.002, 0.02, "-2.02"),
        (-2.002, 0.0002, "-2.002"),
        (2, 1.0e-07, "2"),
        (2, 123.456e-5, "1.9999872"),
        (1, 9.0e-20, "0.99999999999999999999"),
        (0.02442002442002442001001, 0.00000000000002, "0.02442002442002")])
    def test_send_value_update_number_type(self, input, step_size, expected):
        """
        Tests sending update for number value.

        Tests if expected message is being sent.

        Args:
            input: value to be updated
            step_size: step size value should follow
            expected: value expected to be sent

        """
        # Arrange
        self.service.socket.my_socket.send = Mock()
        device = self.service.get_devices()[0]
        value = device.values[0]
        value.data_type == "number"
        value.number_step = step_size

        # Act
        try:
            value.update(input)
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))
            result = arg[0]['params']['data']['data']
        except TypeError:
            result = None
            arg = []

        # Assert
        assert validate_json("request", arg) is True
        assert result == expected

    @pytest.mark.parametrize("input,max,expected", [
        ("test", 10, "test"),  # value under max
        ("", 10, ""),
        ("", 0, ""),  # value on max
        ("testtestte", 10, "testtestte"),
        ("", None, ""),  # no max
        ("testtesttesttesttesttest", None,
         "testtesttesttesttesttest"),
        (None, 10, None),  # no value
        (None, None, None),
        ("test", 1, None)])  # value over max
    @pytest.mark.parametrize("type", ["string", "blob"])
    def test_send_value_update_text_type(self, input, max, expected, type):
        """
        Tests sending update for text/blob value.

        Tests if expected message is being sent.

        Args:
            input: value to be updated
            max: maximum length of the message
            expected: value expected to be sent
            type: indicates if it is string or blob types of value

        """
        # Arrange
        self.service.socket.my_socket.send = Mock()
        device = self.service.get_devices()[0]
        value = device.values[0]
        value.data_type = type
        value.string_max = max
        value.blob_max = max

        # Act
        try:
            value.update(input)
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))
            result = arg[0]['params']['data']['data']
        except TypeError:
            result = None

        # Assert
        assert result == expected


class TestReceiveThreadClass:
    """
    TestReceiveThreadClass instance.

    Tests receiving messages from wappsto server.

    """

    def setup_method(self):
        """
        Sets up each method.

        Sets location to be used in test, initializes service and creates connection.

        """
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("trace_id", [None, '321'])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_FAILED])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_wrong_verb(self, trace_id, expected_msg_id, bulk,
                                       split_message):
        """
        Tests receiving message with wrong verb.

        Tests what would happen if wrong verb would be provided in incoming message.

        Args:
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        send_response(self, "wrong_verb", trace_id, bulk, None, None, None, split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            assert message.msg_id == expected_msg_id

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, '321'])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["value", "wrong"])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("data", ["44"])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_Put(self, callback_exists, trace_id,
                                expected_msg_id, object_name, bulk, data,
                                split_message):
        """
        Tests receiving message with PUT verb.

        Tests what would happen if PUT method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            bulk: Boolean value indicating if multiple messages should be sent at once
            data: data value provided in the message
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object(callback_exists, actual_object)
            actual_object.control_state.data = '1'
            id = str(actual_object.control_state.uuid)
            url = str(actual_object.report_state.uuid)
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = url = '1'

        send_response(self, 'PUT', trace_id, bulk, id, url, data, split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if actual_object:
            if callback_exists:
                assert actual_object.callback.call_args[0][1] == 'set'
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            if message.msg_id == message_data.SEND_SUCCESS:
                message.data == data
            assert (message.msg_id == message_data.SEND_TRACE
                    or message.msg_id == expected_msg_id)
            if message.msg_id == message_data.SEND_TRACE:
                assert message.trace_id == trace_id

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, '321'])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["value", "wrong"])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_Get(self, callback_exists, trace_id,
                                expected_msg_id, object_name, bulk,
                                split_message):
        """
        Tests receiving message with GET verb.

        Tests what would happen if GET method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object(callback_exists, actual_object)
            id = str(actual_object.control_state.uuid)
            url = str(actual_object.report_state.uuid)
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = url = '1'

        send_response(self, 'GET', trace_id, bulk, id, url, "1", split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if actual_object:
            if callback_exists:
                assert actual_object.callback.call_args[0][1] == 'refresh'
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            assert (message.msg_id == message_data.SEND_TRACE
                    or message.msg_id == expected_msg_id)
            if message.msg_id == message_data.SEND_TRACE:
                assert message.trace_id == trace_id

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, '321'])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state", "wrong"])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_Delete(self, callback_exists, trace_id,
                                   expected_msg_id, object_name, bulk,
                                   split_message):
        """
        Tests receiving message with DELETE verb.

        Tests what would happen if DELETE method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object(callback_exists, actual_object)
            id = url = str(actual_object.uuid)
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = url = '1'

        send_response(self, 'DELETE', trace_id, bulk, id, url, "1", split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if trace_id:
            assert any(message.msg_id == message_data.SEND_TRACE for message in self.service.socket.sending_queue.queue)
        if actual_object:
            if callback_exists:
                assert actual_object.callback.call_args[0][1] == 'remove'
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            assert (message.msg_id == message_data.SEND_TRACE
                    or message.msg_id == expected_msg_id)
            if message.msg_id == message_data.SEND_TRACE:
                assert message.trace_id == trace_id

    @pytest.mark.parametrize("id", ["93043873"])
    @pytest.mark.parametrize("data", ["55"])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_result(self, id, data, bulk, split_message):
        """
        Tests receiving success message.

        Tests what would happen if result response would be provided in incoming message.

        Args:
            id: id of the message
            data: value state should be in
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        state = self.service.instance.network.devices[0].values[0].control_state
        state.data = 1
        send_response(self, 'result', None, bulk, state.uuid, None, data, split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert state.data == data
        assert len(self.service.socket.packet_awaiting_confirm) == 0

    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_error(self, bulk, split_message):
        """
        Tests receiving error message.

        Tests what would happen if error response would be provided in incoming message.

        Args:
            id: id of the message
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        send_response(self, 'error', None, bulk, "93043873", None, None, split_message)

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
    """
    TestSendThreadClass instance.

    Tests sending messages to wappsto server.

    """

    def setup_method(self):
        """
        Sets up each method.

        Sets location to be used in test, initializes service and creates connection.

        """
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_data_limit_exeeded", [True, False])
    def test_send_thread_success(self, messages_in_queue, valid_message, log_offline,
                                 connected, log_data_limit_exeeded):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location="",
                                       log_data_limit=1)
        fake_connect(self, ADDRESS, PORT)
        if log_data_limit_exeeded:
            file_size = [self.service.message_log.log_data_limit + 1, 0]
        else:
            file_size = [0]
        if valid_message:
            rpc_id = 1
        else:
            rpc_id = None
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                message_data.SEND_SUCCESS,
                rpc_id=rpc_id
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.message_log.wapp_log.error = Mock(side_effect=KeyboardInterrupt)
        bulk_size = wappsto.connection.communication.MAX_BULK_SIZE
        self.service.socket.connected = connected

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("builtins.open") as opened_file, \
                patch("sys.getsizeof", return_value=0), \
                patch("os.path.getsize", side_effect=file_size):
                opened_file.write = Mock(side_effect=KeyboardInterrupt)
                with patch("builtins.open", return_value=opened_file):
                    self.service.socket.send_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                args, kwargs = opened_file.write.call_args
                args = args[0]
            arg = json.loads(args)
            assert len(arg) <= bulk_size
            assert self.service.socket.sending_queue.qsize() == max(messages_in_queue - bulk_size, 0)
            assert validate_json("successResponse", arg) == valid_message
            for request in arg:
                assert request.get("id", None) == rpc_id
                assert bool(request["result"]) is True
        else:
            args, kwargs = self.service.message_log.wapp_log.error.call_args
            assert args[0] == "Sending while not connected"

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    def test_send_thread_report(self, messages_in_queue, valid_message):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            type: Type of message being sent
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid

        """
        # Arrange
        if valid_message:
            value = "test_info"
        else:
            value = None
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                message_data.SEND_REPORT,
                state_id=self.service.get_network().uuid,
                data=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.add_id_to_confirm_list = Mock()
        bulk_size = wappsto.connection.communication.MAX_BULK_SIZE

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except KeyboardInterrupt:
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))

        # Assert
        assert len(arg) <= bulk_size
        assert self.service.socket.sending_queue.qsize() == max(messages_in_queue - bulk_size, 0)
        assert validate_json("request", arg) == valid_message
        for request in arg:
            assert request['params']['data'].get('data', None) == value
            assert request['params']['data']['type'] == "Report"
            assert request['method'] == "PUT"

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    def test_send_thread_failed(self, messages_in_queue, valid_message):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            type: Type of message being sent
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid

        """
        # Arrange
        if valid_message:
            rpc_id = 1
        else:
            rpc_id = None
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                message_data.SEND_FAILED,
                rpc_id=rpc_id
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        bulk_size = wappsto.connection.communication.MAX_BULK_SIZE

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except KeyboardInterrupt:
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))

        # Assert
        assert len(arg) <= bulk_size
        assert self.service.socket.sending_queue.qsize() == max(messages_in_queue - bulk_size, 0)
        assert validate_json("errorResponse", arg) == valid_message
        for request in arg:
            assert request.get('id', None) == rpc_id
            assert request['error'] == {"code": -32020}

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    def test_send_thread_reconnect(self, messages_in_queue, valid_message):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            type: Type of message being sent
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid

        """
        # Arrange
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = self.service.get_network().uuid = 1
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                message_data.SEND_RECONNECT
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.add_id_to_confirm_list = Mock()
        bulk_size = wappsto.connection.communication.MAX_BULK_SIZE

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except KeyboardInterrupt:
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))

        # Assert
        assert len(arg) <= bulk_size
        assert self.service.socket.sending_queue.qsize() == max(messages_in_queue - bulk_size, 0)
        assert validate_json("request", arg) == valid_message
        for request in arg:
            assert request['params']['data']['meta'].get('id', None) == value
            assert request['params']['data']['meta']['type'] == "network"
            assert request['method'] == "POST"

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    def test_send_thread_control(self, messages_in_queue, valid_message):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            type: Type of message being sent
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid

        """
        # Arrange
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = 1
        i = 0
        while i < messages_in_queue:
            i += 1
            reply = message_data.MessageData(
                message_data.SEND_CONTROL,
                state_id=value,
                data=""
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        bulk_size = wappsto.connection.communication.MAX_BULK_SIZE

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.send_thread()
        except KeyboardInterrupt:
            args, kwargs = self.service.socket.my_socket.send.call_args
            arg = json.loads(args[0].decode('utf-8'))

        # Assert
        assert len(arg) <= bulk_size
        assert self.service.socket.sending_queue.qsize() == max(messages_in_queue - bulk_size, 0)
        assert validate_json("request", arg) == valid_message
        for request in arg:
            assert request['params']['data']['meta'].get('id', None) == value
            assert request['params']['data']['type'] == "Control"
            assert request['method'] == "PUT"

    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    @pytest.mark.parametrize("messages_in_queue", [1, 2])
    def test_send_thread_delete(self, object_name, messages_in_queue):
        """
        Tests sending DELETE message.

        Tests what would happen when sending DELETE message.

        Args:
            object_name: name of the object to be updated
            messages_in_queue: value indicating how many messages should be sent at once

        """
        # Arrange
        actual_object = get_object(self, object_name)

        if object_name == "control_state" or object_name == "report_state":
            url = '/network/{}/device/{}/value/{}/state/{}'.format(
                actual_object.parent.parent.parent.uuid,
                actual_object.parent.parent.uuid,
                actual_object.parent.uuid,
                actual_object.uuid)
        if object_name == "value":
            url = '/network/{}/device/{}/value/{}'.format(
                actual_object.parent.parent.uuid,
                actual_object.parent.uuid,
                actual_object.uuid)
        if object_name == "device":
            url = '/network/{}/device/{}'.format(
                actual_object.parent.uuid,
                actual_object.uuid)
        if object_name == "network":
            url = '/network/{}'.format(
                actual_object.uuid)

        actual_object.delete()

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
            requests = json.loads(arg)

        # Assert
        for request in requests:
            assert request['params']['url'] == url
        assert self.service.socket.sending_queue.qsize() == 0

    @pytest.mark.parametrize("expected_trace_id", [
        (332)])
    def test_send_thread_send_trace(self, expected_trace_id):
        """
        Tests sending trace message.

        Tests what would happen when sending trace message.

        Args:
            expected_trace_id: trace id expected to be sent

        """
        # Arrange
        reply = message_data.MessageData(
            message_data.SEND_TRACE,
            trace_id=expected_trace_id,
            rpc_id=93043873
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
