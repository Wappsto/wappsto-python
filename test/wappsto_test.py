"""
The test module.

Tests wappsto project functionality.
"""
import re
import os
import math
import json
import pytest
import wappsto
import jsonschema
from mock import Mock
from unittest.mock import patch
import urllib.parse as urlparse
from urllib.parse import parse_qs

from wappsto import status
from wappsto.connection import message_data
from wappsto.errors import wappsto_errors
from wappsto.connection import event_storage

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


def fake_connect(self, address, port, send_trace=False):
    """
    Creates fake connection.

    Mocks the connection so no call would leave this environment, also makes application faster for tests.

    Args:
        self: the instance of the calling object
        address: address used for connecting to server
        port: port used for connecting to server
        send_trace: Boolean indicating if trace should be automatically sent

    """
    def check_for_correct_conn(*args, **kwargs):
        if args[0][0] != ADDRESS or args[0][1] != PORT:
            raise wappsto_errors.ServerConnectionException

    wappsto.RETRY_LIMIT = 2
    with patch("ssl.SSLContext.wrap_socket") as context:
        context.connect = Mock(side_effect=check_for_correct_conn)
        with patch('time.sleep', return_value=None), \
            patch('threading.Thread'), \
            patch('threading.Timer'), \
            patch('wappsto.communication.ClientSocket.add_id_to_confirm_list'), \
            patch('wappsto.Wappsto.keep_running'), \
            patch('socket.socket'), \
                patch('ssl.SSLContext.wrap_socket', return_value=context):
            self.service.start(address=address, port=port, automatic_trace=send_trace)


def fix_object_callback(callback_exists, testing_object):
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
        actual_object = self.service.data_manager.network
    elif object_name == "device":
        actual_object = self.service.data_manager.network.devices[0]
    elif object_name == "value":
        actual_object = self.service.data_manager.network.devices[0].values[0]
    elif object_name == "control_state":
        actual_object = self.service.data_manager.network.devices[0].values[0].get_control_state()
    elif object_name == "report_state":
        actual_object = self.service.data_manager.network.devices[0].values[0].get_report_state()
    return actual_object


def send_response(self,
                  verb,
                  trace_id=None,
                  bulk=None,
                  id=None,
                  data=None,
                  split_message=None,
                  type=None,
                  period=None,
                  delta=None):
    """
    Sends response.

    Sends responses to be used in receive tests based on the parameters provided.

    Args:
        verb: specifies if request is DELETE/PUT/POST/GET
        trace_id: id used for tracing messages
        bulk: Boolean value indicating if multiple messages should be sent at once.
        id: specifies id used in message
        data: data to be sent
        split_message: Boolean value indicating if message should be sent in parts
        type: type of module being used.
        delta: delta of value (determines if change was significant enough to be sent)
        period: parameter indicating whether value should be updated periodically

    Returns:
        the generated message

    """
    trace = ""

    if verb == "DELETE" or verb == "PUT" or verb == "GET":
        if trace_id is not None:
            trace = {"trace": str(trace_id)}

        message = {"jsonrpc": "2.0",
                   "id": "1",
                   "params": {
                       "meta": trace,
                       "data": {
                           "meta": {
                               "id": id,
                               "type": type},
                           "data": data,
                           "period": period,
                           "delta": delta}},
                   "method": verb}
    else:
        if verb == "error" or verb == "result":
            if data:
                message_value = {"data": data,
                                 "type": "Control",
                                 "timestamp": "2020-01-20T09:20:21.092Z",
                                 "meta": {
                                     "type": "state",
                                     "version": "2.0",
                                     "id": id,
                                     "manufacturer": "31439b87-040b-4b41-b5b8-f3774b2a1c19",
                                     "updated": "2020-02-18T09:14:12.880+00:00",
                                     "created": "2020-01-20T09:20:21.290+00:00",
                                     "revision": 1035,
                                     "contract": [],
                                     "owner": "bb10f0f1-390f-478e-81c2-a67f58de88be"}}
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
        self.service.socket.my_socket.recv = Mock(side_effect=[message1.encode("utf-8"),
                                                               message2.encode("utf-8"),
                                                               KeyboardInterrupt])
    else:
        self.service.socket.my_socket.recv = Mock(side_effect=[message.encode("utf-8"),
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


def set_up_log(log_location, log_file_exists, file_path, file_size):
    """
    Sets up logs.

    Deletes all log files and creates new one if log file should exist.

    Args:
        log_location: location of the logs
        log_file_exists: boolean indicating if log file should exist
        file_path: path to the file
        file_size: how big is the current size of the folder

    """
    # removes all files
    for root, dirs, files in os.walk(log_location):
        for file in files:
            os.remove(os.path.join(root, file))

    # creates file
    if log_file_exists:
        with open(file_path, "w") as file:
            num_chars = 1024 * 1024 * file_size
            string = "0" * num_chars + "\n"
            file.write(string)


def check_for_logged_info(*args, **kwargs):
    """
    Checks for provided data in logger.

    If the logger is provided with the necessary information,
    KeyboardInterrupt is raised to stop the test.

    Args:
        args: arguments that method was called with
        kwargs: key worded arguments

    """
    if (re.search("^Raw log Json:", args[0])
            or re.search("^Sending while not connected$", args[0])):
        raise KeyboardInterrupt


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

        Loads pretty print json file and checks if it is read the same way
        as normal json file.

        """
        # Arrange
        with open(self.test_json_location, "r") as json_file:
            decoded = json.load(json_file)

        # Act
        service = wappsto.Wappsto(json_file_name=self.test_json_prettyprint_location)

        # Assert
        assert service.data_manager.decoded == decoded

    @pytest.mark.parametrize("object_exists", [True, False])
    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    def test_get_by_id(self, object_exists, object_name):
        """
        Tests getting element  by id.

        Gets id and checks if result is the expected one.

        Args:
            object_exists: indicates if element should exist
            object_name: name of the object to be updated

        """
        # Arrange
        self.service = wappsto.Wappsto(json_file_name=self.test_json_prettyprint_location)
        get_object(self, "network").conn = Mock()
        actual_object = get_object(self, object_name)
        id = actual_object.uuid
        if not object_exists:
            actual_object.delete()

        # Act
        result = self.service.get_by_id(id)

        # Assert
        assert (object_exists and result is not None) or (not object_exists and result is None)


class TestConnClass:
    """
    TestConnClass instance.

    Tests connecting to wappsto server.

    """

    @pytest.mark.parametrize("address,port,expected_status",
                             [(ADDRESS, PORT, status.RUNNING),
                              (ADDRESS, -1, status.DISCONNECTING),
                              ("wappstoFail.com", PORT, status.DISCONNECTING),
                              ("wappstoFail.com", -1, status.DISCONNECTING)])
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("callback_exists", [True, False])
    @pytest.mark.parametrize("value_changed_to_none", [True, False])
    @pytest.mark.parametrize("upgradable", [True, False])
    @pytest.mark.parametrize("valid_json", [True, False])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    def test_connection(self, address, port, expected_status, callback_exists, send_trace,
                        value_changed_to_none, upgradable, valid_json, log_offline,
                        log_location, log_file_exists):
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
            send_trace: Boolean indicating if trace should be automatically sent
            valid_json: Boolean indicating if the sent json should be valid
            log_offline: boolean indicating if data should be logged
            log_location: location of the logs
            log_file_exists: boolean indicating if log file exist

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location)
        status_service = self.service.get_status()
        fix_object_callback(callback_exists, status_service)
        urlopen_trace_id = sent_json_trace_id = ''
        if value_changed_to_none:
            self.service.data_manager.network.name = None
        if not valid_json:
            self.service.data_manager.network.uuid = None

        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        log_location = self.service.event_storage.log_location
        set_up_log(log_location, log_file_exists, file_path, 1)

        def send_log():
            self.service.event_storage.send_log(self.service.socket)

        # Act
        with patch("os.getenv", return_value=str(upgradable)), \
            patch('urllib.request.urlopen') as urlopen, \
                patch("wappsto.communication.ClientSocket.send_logged_data", side_effect=send_log):
            try:
                fake_connect(self, address, port, send_trace)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode("utf-8"))
                sent_json = arg[-1]["params"]["data"]
                if send_trace:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                    parsed_sent_json = urlparse.urlparse(arg[0]['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            except wappsto_errors.ServerConnectionException:
                sent_json = None
                arg = []
                pass

        # Assert
        if sent_json is not None:
            if log_offline:
                assert len(os.listdir(log_location)) == 0
            assert validate_json("request", arg) == valid_json
            assert "None" not in str(sent_json)
            assert sent_json_trace_id == urlopen_trace_id
            assert (send_trace and urlopen_trace_id != ''
                    or not send_trace and urlopen_trace_id == '')
            assert (upgradable and "upgradable" in str(sent_json["meta"])
                    or not upgradable and "upgradable" not in str(sent_json["meta"]))
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
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("delta", [None, 0.1, 1, 100])
    @pytest.mark.parametrize("period", [True, False])
    def test_send_value_update_number_type(self, input, step_size, expected, send_trace, delta, period):
        """
        Tests sending update for number value.

        Tests if expected message is being sent.

        Args:
            input: value to be updated
            step_size: step size value should follow
            expected: value expected to be sent
            send_trace: Boolean indicating if trace should be automatically sent
            delta: delta of value (determines if change was significant enough to be sent)
            period: parameter indicating whether value should be updated periodically

        """
        # Arrange
        with patch('urllib.request.urlopen'):
            fake_connect(self, ADDRESS, PORT, send_trace)
        self.service.socket.my_socket.send = Mock()
        urlopen_trace_id = sent_json_trace_id = ''
        device = self.service.get_devices()[0]
        value = device.values[0]
        value.data_type == "number"
        value.number_step = step_size
        if delta:
            value.last_update_of_report = 0
            value.set_delta(delta)
            if abs(input - value.last_update_of_report) < value.delta:
                # if change is less then delta then no message would be sent
                expected = None

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                if period is True and delta is None:
                    with patch('threading.Timer.start') as start:
                        value.set_period(1)
                        value.timer_elapsed = True
                        if start.called:
                            value.update(input)
                else:
                    value.update(input)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode("utf-8"))
                result = arg[0]["params"]["data"]["data"]

                if send_trace:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                    urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                    parsed_sent_json = urlparse.urlparse(arg[0]['params']['url'])
                    sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            except TypeError:
                result = None
                arg = []

        # Assert
        assert validate_json("request", arg) is True
        assert result == expected
        assert sent_json_trace_id == urlopen_trace_id
        if send_trace and result is not None:
            assert urlopen_trace_id != ''
        else:
            assert urlopen_trace_id == ''

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
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("delta", [None, 0.1, 1, 100])
    @pytest.mark.parametrize("period", [True, False])
    def test_send_value_update_text_type(self, input, max, expected, type, send_trace, delta, period):
        """
        Tests sending update for text/blob value.

        Tests if expected message is being sent.

        Args:
            input: value to be updated
            max: maximum length of the message
            expected: value expected to be sent
            type: indicates if it is string or blob types of value
            send_trace: Boolean indicating if trace should be automatically sent
            delta: delta of value (determines if change was significant enough to be sent)
            period: parameter indicating whether value should be updated periodically

        """
        # Arrange
        with patch('urllib.request.urlopen'):
            fake_connect(self, ADDRESS, PORT, send_trace)
        self.service.socket.my_socket.send = Mock()
        urlopen_trace_id = sent_json_trace_id = ''
        device = self.service.get_devices()[0]
        value = device.values[0]
        value.data_type = type
        value.string_max = max
        value.blob_max = max
        if delta:
            value.last_update_of_report = 0
            value.set_delta(delta)
            # delta should not have eny effect

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                if period is True:
                    with patch('threading.Timer.start') as start:
                        value.set_period(1)
                        value.timer_elapsed = True
                        if start.called:
                            value.update(input)
                else:
                    value.update(input)
                args, kwargs = self.service.socket.my_socket.send.call_args
                arg = json.loads(args[0].decode("utf-8"))
                result = arg[0]["params"]["data"]["data"]

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

    @pytest.mark.parametrize("trace_id", [None, "321"])
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
        send_response(self, "wrong_verb", trace_id=trace_id, bulk=bulk, split_message=split_message)

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
    @pytest.mark.parametrize("trace_id", [None, "321"])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["value", "wrong"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("data", ["44"])
    @pytest.mark.parametrize("split_message", [False, True])
    @pytest.mark.parametrize("type", ["state", "value"])
    @pytest.mark.parametrize("period", [1])
    @pytest.mark.parametrize("delta", [1])
    def test_receive_thread_Put(self, callback_exists, trace_id,
                                expected_msg_id, object_name, object_exists,
                                bulk, data, split_message, type, period, delta):
        """
        Tests receiving message with PUT verb.

        Tests what would happen if PUT method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            object_exists: indicates if object would exists
            bulk: Boolean value indicating if multiple messages should be sent at once
            data: data value provided in the message
            split_message: Boolean value indicating if message should be sent in parts
            type: type of module being used.
            delta: delta of value (determines if change was significant enough to be sent)
            period: parameter indicating whether value should be updated periodically

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object_callback(callback_exists, actual_object)
            actual_object.control_state.data = "1"
            if type == "state":
                id = str(actual_object.control_state.uuid)
            elif type == "value":
                id = str(actual_object.uuid)
            if not object_exists:
                self.service.data_manager.network = None
                expected_msg_id = message_data.SEND_FAILED
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = '1'

        send_response(self, 'PUT', trace_id=trace_id, bulk=bulk, id=id,
                      data=data, split_message=split_message, type=type, period=period,
                      delta=delta)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch('threading.Timer.start'):
                self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if trace_id and object_exists and actual_object:
            assert any(message.msg_id == message_data.SEND_TRACE for message in self.service.socket.sending_queue.queue)
        if actual_object and object_exists:
            if type == "state":
                if callback_exists:
                    assert actual_object.callback.call_args[0][1] == 'set'
            elif type == "value":
                assert actual_object.period == period
                assert actual_object.delta == delta
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            assert (message.msg_id == message_data.SEND_TRACE
                    or message.msg_id == expected_msg_id)
            if message.msg_id == message_data.SEND_TRACE:
                assert message.trace_id == trace_id

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, "321"])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["value", "wrong"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_Get(self, callback_exists, trace_id,
                                expected_msg_id, object_name, object_exists,
                                bulk, split_message):
        """
        Tests receiving message with GET verb.

        Tests what would happen if GET method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            object_exists: indicates if object would exists
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object_callback(callback_exists, actual_object)
            id = str(actual_object.report_state.uuid)
            if not object_exists:
                self.service.data_manager.network = None
                expected_msg_id = message_data.SEND_FAILED
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = '1'

        send_response(self, 'GET', trace_id=trace_id, bulk=bulk, id=id,
                      split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if trace_id and object_exists and actual_object:
            assert any(message.msg_id == message_data.SEND_TRACE for message in self.service.socket.sending_queue.queue)
        if actual_object and object_exists:
            if callback_exists:
                assert actual_object.callback.call_args[0][1] == "refresh"
        assert self.service.socket.sending_queue.qsize() > 0
        while self.service.socket.sending_queue.qsize() > 0:
            message = self.service.socket.sending_queue.get()
            assert (message.msg_id == message_data.SEND_TRACE
                    or message.msg_id == expected_msg_id)
            if message.msg_id == message_data.SEND_TRACE:
                assert message.trace_id == trace_id

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, "321"])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state", "wrong"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    def test_receive_thread_Delete(self, callback_exists, trace_id,
                                   expected_msg_id, object_name, object_exists,
                                   bulk, split_message):
        """
        Tests receiving message with DELETE verb.

        Tests what would happen if DELETE method would be provided in incoming message.

        Args:
            callback_exists: Boolean indicating if object should have callback
            trace_id: id used for tracing
            expected_msg_id: message id expected to be received
            object_name: name of the object to be updated
            object_exists: indicates if object would exists
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts

        """
        # Arrange
        actual_object = get_object(self, object_name)
        if actual_object:
            fix_object_callback(callback_exists, actual_object)
            id = str(actual_object.uuid)
            if not object_exists:
                self.service.data_manager.network = None
                expected_msg_id = message_data.SEND_FAILED
        else:
            expected_msg_id = message_data.SEND_FAILED
            id = '1'

        send_response(self, 'DELETE', trace_id=trace_id, bulk=bulk, id=id,
                      split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if trace_id and object_exists and actual_object:
            assert any(message.msg_id == message_data.SEND_TRACE for message in self.service.socket.sending_queue.queue)
        if actual_object and object_exists:
            if callback_exists:
                assert actual_object.callback.call_args[0][1] == "remove"
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
        state = self.service.data_manager.network.devices[0].values[0].control_state
        state.data = 1
        send_response(self, 'result', bulk=bulk, id=state.uuid, data=data, split_message=split_message)

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
        send_response(self, 'error', bulk=bulk, id="93043873", split_message=split_message)

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

    @pytest.mark.parametrize("value", [1, None])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    def test_send_thread_success(self, messages_in_queue, value, log_offline,
                                 connected, log_location, file_size, limit_action,
                                 log_file_exists):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            value: value to be sent (when None is provided should make json invalid)
            messages_in_queue: How many messages should be sent
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_SUCCESS,
                rpc_id=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                    patch("logging.Logger.debug", side_effect=check_for_logged_info):
                self.service.socket.send_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            assert validate_json("successResponse", arg) == bool(value)
            for request in arg:
                assert request.get("id", None) == value
                assert bool(request["result"]) is True
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("value", ["test_info", None])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_report(self, messages_in_queue, value, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists, send_trace):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent
            value: value to be sent (when None is provided should make json invalid)
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_REPORT,
                state_id=self.service.get_network().uuid,
                data=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                        patch("logging.Logger.debug", side_effect=check_for_logged_info):
                    self.service.socket.send_thread()
            except KeyboardInterrupt:
                pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            if urlopen.called:
                urlopen_args, urlopen_kwargs = urlopen.call_args

                parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                parsed_sent_json = urlparse.urlparse(arg[-1]['params']['url'])
                sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            assert urlopen_trace_id == sent_json_trace_id
            if send_trace:
                assert urlopen_trace_id != ''
            else:
                assert urlopen_trace_id == ''
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == bool(value)
            for request in arg:
                assert request["params"]["data"].get("data", None) == value
                assert request["params"]["data"]["type"] == "Report"
                assert request["method"] == "PUT"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("value", [1, None])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    def test_send_thread_failed(self, messages_in_queue, value, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent
            value: value to be sent (when None is provided should make json invalid)
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_FAILED,
                rpc_id=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                    patch("logging.Logger.debug", side_effect=check_for_logged_info):
                self.service.socket.send_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            assert validate_json("errorResponse", arg) == bool(value)
            for request in arg:
                assert request.get("id", None) == value
                assert request["error"] == {"code": -32020}
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_reconnect(self, messages_in_queue, valid_message, log_offline,
                                   connected, log_location, file_size, limit_action,
                                   log_file_exists, send_trace):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = self.service.get_network().uuid = 1
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_RECONNECT
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                        patch("logging.Logger.debug", side_effect=check_for_logged_info):
                    self.service.socket.send_thread()
            except KeyboardInterrupt:
                pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            if urlopen.called:
                urlopen_args, urlopen_kwargs = urlopen.call_args

                parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                parsed_sent_json = urlparse.urlparse(arg[-1]['params']['url'])
                sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            assert urlopen_trace_id == sent_json_trace_id
            if send_trace:
                assert urlopen_trace_id != ''
            else:
                assert urlopen_trace_id == ''
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == valid_message
            for request in arg:
                assert request["params"]["data"]["meta"].get("id", None) == value
                assert request["params"]["data"]["meta"]["type"] == "network"
                assert request["method"] == "POST"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_control(self, messages_in_queue, valid_message, log_offline,
                                 connected, log_location, file_size, limit_action,
                                 log_file_exists, send_trace):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent
            valid_message: Boolean indicating if the sent json should be valid
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = 1
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_CONTROL,
                state_id=value,
                data=""
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                        patch("logging.Logger.debug", side_effect=check_for_logged_info):
                    self.service.socket.send_thread()
            except KeyboardInterrupt:
                pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            if urlopen.called:
                urlopen_args, urlopen_kwargs = urlopen.call_args

                parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                parsed_sent_json = urlparse.urlparse(arg[-1]['params']['url'])
                sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            assert urlopen_trace_id == sent_json_trace_id
            if send_trace:
                assert urlopen_trace_id != ''
            else:
                assert urlopen_trace_id == ''
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == valid_message
            for request in arg:
                assert request["params"]["data"]["meta"].get("id", None) == value
                assert request["params"]["data"]["type"] == "Control"
                assert request["method"] == "PUT"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    @pytest.mark.parametrize("messages_in_queue", [1, 2, 20])
    @pytest.mark.parametrize("log_offline", [True, False])
    @pytest.mark.parametrize("connected", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [2, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("log_file_exists", [True, False])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_delete(self, object_name, messages_in_queue, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists, send_trace):
        """
        Tests sending DELETE message.

        Tests what would happen when sending DELETE message.

        Args:
            object_name: name of the object to be updated
            messages_in_queue: value indicating how many messages should be sent at once
            log_offline: boolean indicating if data should be logged
            connected: boolean indicating if the is connection to server
            log_location: location of the logs
            file_size: how big is the current size of the folder
            limit_action: action to perform when limit is exeeded
            log_file_exists: boolean indicating if log file exist
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.DAY_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        actual_object = get_object(self, object_name)

        if object_name == "control_state" or object_name == "report_state":
            reply = message_data.MessageData(
                message_data.SEND_DELETE,
                network_id=actual_object.parent.parent.parent.uuid,
                device_id=actual_object.parent.parent.uuid,
                value_id=actual_object.parent.uuid,
                state_id=actual_object.uuid
            )
        if object_name == "value":
            reply = message_data.MessageData(
                message_data.SEND_DELETE,
                network_id=actual_object.parent.parent.uuid,
                device_id=actual_object.parent.uuid,
                value_id=actual_object.uuid
            )
        if object_name == "device":
            reply = message_data.MessageData(
                message_data.SEND_DELETE,
                network_id=actual_object.parent.uuid,
                device_id=actual_object.uuid
            )
        if object_name == "network":
            reply = message_data.MessageData(
                message_data.SEND_DELETE,
                network_id=actual_object.uuid
            )

        for x in range(messages_in_queue):
            self.service.socket.sending_queue.put(reply)

        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.add_id_to_confirm_list = Mock()
        self.service.socket.connected = connected
        self.service.socket.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_name = self.service.event_storage.get_log_name()
        file_path = self.service.event_storage.get_file_path(file_name)
        set_up_log(self.service.event_storage.log_location, log_file_exists, file_path, file_size)

        # Act
        with patch('urllib.request.urlopen') as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                        patch("logging.Logger.debug", side_effect=check_for_logged_info):
                    self.service.socket.send_thread()
            except KeyboardInterrupt:
                pass

        # Assert
        assert os.path.isdir(self.service.event_storage.log_location)
        if connected or log_offline:
            if connected:
                args, kwargs = self.service.socket.my_socket.send.call_args
                args = args[0].decode("utf-8")
            else:
                with open(file_path, "r") as file:
                    args = file.readlines()[-1]
            arg = json.loads(args)
            if urlopen.called:
                urlopen_args, urlopen_kwargs = urlopen.call_args

                parsed_urlopen = urlparse.urlparse(urlopen_args[0])
                urlopen_trace_id = parse_qs(parsed_urlopen.query)['id']

                parsed_sent_json = urlparse.urlparse(arg[-1]['params']['url'])
                sent_json_trace_id = parse_qs(parsed_sent_json.query)['trace']
            assert urlopen_trace_id == sent_json_trace_id
            if send_trace:
                assert urlopen_trace_id != ''
            else:
                assert urlopen_trace_id == ''
            assert len(arg) <= wappsto.connection.communication.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.MAX_BULK_SIZE, 0)
            for request in arg:
                assert request["params"]["url"] is not None
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("trace_id", [(332)])
    def test_send_thread_send_trace(self, trace_id):
        """
        Tests sending trace message.

        Tests what would happen when sending trace message.

        Args:
            trace_id: trace id expected to be sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)
        reply = message_data.MessageData(
            message_data.SEND_TRACE,
            trace_id=trace_id,
            rpc_id=93043873
        )
        self.service.socket.sending_queue.put(reply)

        # Act
        with patch("urllib.request.urlopen", side_effect=KeyboardInterrupt) as urlopen:
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
