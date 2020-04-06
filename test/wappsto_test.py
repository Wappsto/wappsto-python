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
import zipfile
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
        try:
            testing_object.set_callback(None)
        except wappsto_errors.CallbackNotCallableException:
            pass


def get_object(network, name):
    """
    Get object from network.

    Get object based on the name provided.

    Args:
        network: The network from where the data should be found.
        name: Name indicating the object being searched for.

    Returns:
        The found object.

    """
    if name == "network":
        return network.service.data_manager.network
    elif name == "device":
        return network.service.data_manager.network.devices[0]
    elif name == "value":
        return network.service.data_manager.network.devices[0].values[0]
    elif name == "control_state":
        return network.service.data_manager.network.devices[0].values[0].get_control_state()
    elif name == "report_state":
        return network.service.data_manager.network.devices[0].values[0].get_report_state()
    return None


def send_response(instance,
                  verb,
                  trace_id=None,
                  bulk=None,
                  message_id=None,
                  element_id=None,
                  data=None,
                  split_message=None,
                  element_type=None,
                  period=None,
                  delta=None):
    """
    Sends response.

    Sends responses to be used in receive tests based on the parameters provided.

    Args:
        instance: The current Test instance.
        verb: specifies if request is DELETE/PUT/POST/GET
        trace_id: id used for tracing messages
        bulk: Boolean value indicating if multiple messages should be sent at once.
        message_id: id used to indicate the specific message
        element_id: id used for indicating element
        data: data to be sent
        split_message: Boolean value indicating if message should be sent in parts
        element_type: type of module being used.
        period: parameter indicating whether value should be updated periodically
        delta: delta of value (determines if change was significant enough to be sent)

    Returns:
        the generated message.

    """
    trace = ""

    if verb == "DELETE" or verb == "PUT" or verb == "GET":
        if data is None:
            params = None
        else:
            if trace_id is None:
                trace = None
            else:
                trace = {"trace": str(trace_id)}

            if element_id is None:
                meta = None
            else:
                meta = {"id": element_id,
                        "type": element_type}

            params = {"meta": trace,
                      "url": "/{}/{}".format(element_type, element_id),
                      "data": {
                          "meta": meta,
                          "data": data,
                          "period": period,
                          "delta": delta}}

        message = {"jsonrpc": "2.0",
                   "id": message_id,
                   "params": params,
                   "method": verb}
    elif verb == "error" or verb == "result":
        if data:
            message_value = {"data": data,
                             "type": "Control",
                             "timestamp": "2020-01-20T09:20:21.092Z",
                             "meta": {
                                 "type": "state",
                                 "version": "2.0",
                                 "id": element_id}}
        else:
            message_value = "True"
        message = {"jsonrpc": "2.0",
                   "id": message_id,
                   verb: {
                       "value": message_value,
                       "meta": {
                           "server_send_time": "2020-01-22T08:22:55.315Z"}}}
        instance.service.socket.packet_awaiting_confirm[message_id] = message
    else:
        message = {"jsonrpc": "2.0", "id": "1", "params": {}, "method": "??????"}

    if bulk:
        message = [message, message]
    message = json.dumps(message)

    if split_message:
        message_size = math.ceil(len(message) / 2)
        message1 = message[:message_size]
        message2 = message[message_size:]
        wappsto.connection.communication.receive_data.RECEIVE_SIZE = message_size
        instance.service.socket.my_socket.recv = Mock(side_effect=[message1.encode("utf-8"),
                                                                   message2.encode("utf-8"),
                                                                   KeyboardInterrupt])
    else:
        instance.service.socket.my_socket.recv = Mock(side_effect=[message.encode("utf-8"),
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


def set_up_log(self, log_file_exists, file_size, make_zip=False):
    """
    Sets up logs.

    Deletes all log files and creates new one if log file should exist.

    Args:
        self: referece to calling object
        log_file_exists: boolean indicating if log file should exist
        file_size: how big is the current size of the folder
        make_zip: boolean indicating if log file should be zip

    Returns:
        path to the latest file

    """
    file_name = self.service.event_storage.get_log_name()
    file_path = self.service.event_storage.get_file_path(file_name)
    log_location = self.service.event_storage.log_location

    # removes all files
    for root, dirs, files in os.walk(log_location):
        for file in files:
            os.remove(os.path.join(root, file))

    # creates file
    if log_file_exists:
        with open(file_path, "w") as file:
            num_chars = int((1024 * 1024 * file_size) / 10)
            string = ""
            data = "0" * num_chars
            for i in range(10):
                string += '[{"data": "' + data + '"}]\n'
            file.write(string)

        if make_zip:
            with zipfile.ZipFile(file_path.replace(".txt", ".zip"), "w") as zip_file:
                zip_file.write(file_path, file_name)
            os.remove(file_path)

    with open(self.service.event_storage.get_file_path("2000-1.txt"), "w") as file:
        file.write("")

    return file_path


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
            or re.search("^Sending while not connected$", args[0])
            or re.search("^Received message exeeds size limit.$", args[0])
            or re.search("^Unhandled send$", args[0])):
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
        self.test_json_location = os.path.join(
            os.path.dirname(__file__),
            TEST_JSON)

    @pytest.mark.parametrize("valid_location", [True, False])
    @pytest.mark.parametrize("valid_json", [True, False])
    def test_load_json(self, valid_location, valid_json):
        """
        Tests loading json.

        Loads json file and checks if pretty print json is read same way as ordinary file.

        Args:
            valid_location: parameter indicating whether file should be found in the location
            valid_json: parameter indicating whether file should be parsed successfully

        """
        # Arrange
        if not valid_location:
            test_json_location_2 = "wrong_location"
        else:
            if not valid_json:
                test_json_location_2 = os.path.join(
                    os.path.dirname(__file__),
                    "test_JSON/test_json_wrong.json")
            else:
                test_json_location_2 = os.path.join(
                    os.path.dirname(__file__),
                    "test_JSON/test_json_prettyprint.json")

        with open(self.test_json_location, "r") as json_file:
            decoded = json.load(json_file)

        # Act
        try:
            service = wappsto.Wappsto(json_file_name=test_json_location_2)
        except FileNotFoundError:
            service = None
        except json.JSONDecodeError:
            service = None

        # Assert
        assert (valid_location and valid_json) == bool(service)
        if service is not None:
            assert service.data_manager.decoded == decoded

    @pytest.mark.parametrize("object_exists", [True, False])
    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    def test_get_by_id(self, object_exists, object_name):
        """
        Tests getting element by id.

        Gets id and checks if result is the expected one.

        Args:
            object_exists: indicates if element should exist
            object_name: name of the object to be updated

        """
        # Arrange
        self.service = wappsto.Wappsto(json_file_name=self.test_json_location)
        get_object(self, "network").conn = Mock()
        actual_object = get_object(self, object_name)
        id = actual_object.uuid
        if not object_exists:
            actual_object.delete()

        # Act
        result = self.service.get_by_id(id)

        # Assert
        assert (object_exists and result is not None) or (not object_exists and result is None)

    @pytest.mark.parametrize("save_as_string", [True, False])
    def test_load_existing_instance(self, save_as_string):
        """
        Tests loading existing instance.

        Creates new instance and then tries to load it.

        Args:
            save_as_string: indicates if informations inside data should be saved as a string.

        """
        # Arrange
        self.service = wappsto.Wappsto(json_file_name=self.test_json_location)
        saved_network = self.service.data_manager.get_encoded_network()

        file_name = "test.json"
        encoded = saved_network
        if save_as_string:
            encoded = json.dumps(encoded)
            encoded = encoded.replace("\'", "\\\"")
        encoded = json.dumps({"data": encoded})
        path = os.path.join(self.service.data_manager.path_to_calling_file, 'saved_instances')
        os.makedirs(path, exist_ok=True)
        path_open = os.path.join(path, file_name)
        with open(path_open, "w+") as network_file:
            network_file.write(encoded)

        # Act
        self.service = wappsto.Wappsto(json_file_name=file_name, load_from_state_file=True)

        # Assert
        assert saved_network == self.service.data_manager.get_encoded_network()


class TestConnClass:
    """
    TestConnClass instance.

    Tests connecting to wappsto server.

    """

    @pytest.mark.parametrize("address,port,expected_status", [
        (ADDRESS, PORT, status.RUNNING),
        (ADDRESS, -1, status.DISCONNECTING),
        ("wappstoFail.com", PORT, status.DISCONNECTING)])
    @pytest.mark.parametrize("send_trace", [True, False])
    @pytest.mark.parametrize("callback_exists", [True, False])
    @pytest.mark.parametrize("upgradable", [True, False])
    @pytest.mark.parametrize("valid_json", [True, False])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("log_offline,log_file_exists,make_zip", [
        (True, True, True),
        (True, True, False),
        (True, False, False),
        (False, False, False)])
    @pytest.mark.parametrize("load_from_state_file", [True, False])
    def test_connection(self, address, port, expected_status, callback_exists, send_trace,
                        upgradable, valid_json, log_offline, log_location,
                        log_file_exists, load_from_state_file, make_zip):
        """
        Tests connection.

        Tests if connecting works es expected within different setup.

        Args:
            address: address used for connecting to server
            port: port used for connecting to server
            callback_exists: specifies if object should have callback
            expected_status: status expected after execution of the test
            upgradable: specifies if object is upgradable
            send_trace: Boolean indicating if trace should be automatically sent
            valid_json: Boolean indicating if the sent json should be valid
            log_offline: boolean indicating if data should be logged
            log_location: location of the logs
            log_file_exists: boolean indicating if log file exist
            load_from_state_file: Defines if the data should be loaded from saved files
            make_zip: boolean indicating if log file should be zip

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       load_from_state_file=load_from_state_file,
                                       log_offline=log_offline,
                                       log_location=log_location)
        status_service = self.service.get_status()
        fix_object_callback(callback_exists, status_service)
        urlopen_trace_id = sent_json_trace_id = ''
        if not valid_json:
            self.service.data_manager.network.uuid = None

        set_up_log(self, log_file_exists, 1, make_zip)

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
        if callback_exists:
            assert status_service.callback.call_args[0][-1].current_status == expected_status
        assert self.service.status.get_status() == expected_status

    @pytest.mark.parametrize("load_from_state_file", [True, False])
    @pytest.mark.parametrize("save", [True, False])
    def test_close(self, load_from_state_file, save):
        """
        Tests closing connection.

        Tests if closing connecting works es expected within different setup.

        Args:
            load_from_state_file: Defines if the data should be loaded from saved files
            save: Flag to determine whether runtime instances should be saved

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       load_from_state_file=load_from_state_file)
        fake_connect(self, ADDRESS, PORT)
        path = os.path.join(self.service.data_manager.path_to_calling_file, 'saved_instances')
        network_id = self.service.data_manager.json_file_name = "test.json"
        path_open = os.path.join(path, network_id)
        if os.path.exists(path_open):
            os.remove(path_open)

        # Act
        self.service.stop(save)

        # Assert
        assert save == os.path.isfile(path_open)


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
        device = self.service.get_device("device-1")
        value = next(val for val in device.values if val.data_type == "number")
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
        device = self.service.get_device("device-1")
        value = next(val for val in device.values if val.data_type == type)
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

    def teardown_module(self):
        """
        Teardown each method.

        Stops connection.

        """
        self.service.socket.close()


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
            self.service.socket.receive_data.receive_thread()
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
    @pytest.mark.parametrize("object_name", ["value"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("data", ["44", None])
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
        fix_object_callback(callback_exists, actual_object)
        actual_object.control_state.data = "1"
        if type == "state":
            id = str(actual_object.control_state.uuid)
        elif type == "value":
            id = str(actual_object.uuid)
        if not object_exists:
            self.service.data_manager.network = None
            expected_msg_id = message_data.SEND_FAILED

        send_response(self, 'PUT', trace_id=trace_id, bulk=bulk, element_id=id,
                      data=data, split_message=split_message, element_type=type, period=period,
                      delta=delta)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch('threading.Timer.start'):
                self.service.socket.receive_data.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if data is not None:
            if object_exists:
                if trace_id:
                    assert any(message.msg_id == message_data.SEND_TRACE for message
                               in self.service.socket.sending_queue.queue)
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
        else:
            assert self.service.socket.sending_queue.qsize() == 0

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, "321"])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["value"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    @pytest.mark.parametrize("id_exists", [False, True])
    def test_receive_thread_Get(self, callback_exists, trace_id,
                                expected_msg_id, object_name, object_exists,
                                bulk, split_message, id_exists):
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
            id_exists: indicates if id should be in the message

        """
        # Arrange
        rpc_id = "GET-1"
        actual_object = get_object(self, object_name)
        fix_object_callback(callback_exists, actual_object)
        uuid = str(actual_object.report_state.uuid)
        if not object_exists:
            self.service.data_manager.network = None
            expected_msg_id = message_data.SEND_FAILED

        if not id_exists:
            uuid = None

        send_response(self, "GET", message_id=rpc_id, trace_id=trace_id, bulk=bulk, element_id=uuid,
                      element_type="state", data=1, split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_data.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if id_exists:
            if object_exists:
                if trace_id:
                    assert any(message.msg_id == message_data.SEND_TRACE for message
                               in self.service.socket.sending_queue.queue)
                if callback_exists:
                    assert actual_object.callback.call_args[0][1] == "refresh"
            assert self.service.socket.sending_queue.qsize() > 0
            while self.service.socket.sending_queue.qsize() > 0:
                message = self.service.socket.sending_queue.get()
                assert (message.msg_id == message_data.SEND_TRACE
                        or message.msg_id == expected_msg_id)
                if message.msg_id == message_data.SEND_TRACE:
                    assert message.trace_id == trace_id
        else:
            if bulk:
                assert self.service.socket.sending_queue.qsize() == 2
            else:
                assert self.service.socket.sending_queue.qsize() == 1

            while self.service.socket.sending_queue.qsize() > 0:
                message = self.service.socket.sending_queue.get()
                assert (message.msg_id == message_data.SEND_FAILED)
                assert (message.rpc_id == rpc_id)

    @pytest.mark.parametrize("callback_exists", [False, True])
    @pytest.mark.parametrize("trace_id", [None, "321"])
    @pytest.mark.parametrize("expected_msg_id", [message_data.SEND_SUCCESS])
    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    @pytest.mark.parametrize("object_exists", [False, True])
    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    @pytest.mark.parametrize("id_exists", [False, True])
    def test_receive_thread_Delete(self, callback_exists, trace_id,
                                   expected_msg_id, object_name, object_exists,
                                   bulk, split_message, id_exists):
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
            id_exists: indicates if id should be in the message

        """
        # Arrange
        rpc_id = "DELETE-1"
        actual_object = get_object(self, object_name)
        fix_object_callback(callback_exists, actual_object)
        id = str(actual_object.uuid)
        if not object_exists:
            self.service.data_manager.network = None
            expected_msg_id = message_data.SEND_FAILED

        if not id_exists:
            id = None

        send_response(self, 'DELETE', message_id=rpc_id, trace_id=trace_id, bulk=bulk, element_id=id, data=1,
                      element_type='network', split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_data.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        if id_exists:
            if object_exists:
                if trace_id:
                    assert any(message.msg_id == message_data.SEND_TRACE for message
                               in self.service.socket.sending_queue.queue)
                if callback_exists:
                    assert actual_object.callback.call_args[0][1] == "remove"
            assert self.service.socket.sending_queue.qsize() > 0
            while self.service.socket.sending_queue.qsize() > 0:
                message = self.service.socket.sending_queue.get()
                assert (message.msg_id == message_data.SEND_TRACE
                        or message.msg_id == expected_msg_id)
                if message.msg_id == message_data.SEND_TRACE:
                    assert message.trace_id == trace_id
        else:
            if bulk:
                assert self.service.socket.sending_queue.qsize() == 2
            else:
                assert self.service.socket.sending_queue.qsize() == 1

            while self.service.socket.sending_queue.qsize() > 0:
                message = self.service.socket.sending_queue.get()
                assert (message.msg_id == message_data.SEND_FAILED)
                assert (message.rpc_id == rpc_id)

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
        state = self.service.get_devices()[0].get_value("temp").control_state
        state.data = 1
        send_response(self, "result", bulk=bulk, message_id=state.uuid, element_id=state.uuid,
                      data=data, split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_data.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert state.data == data
        assert len(self.service.socket.packet_awaiting_confirm) == 0

    @pytest.mark.parametrize("bulk", [False, True])
    @pytest.mark.parametrize("split_message", [False, True])
    @pytest.mark.parametrize("message_size_exeeded", [False, True])
    def test_receive_thread_error(self, bulk, split_message, message_size_exeeded):
        """
        Tests receiving error message.

        Tests what would happen if error response would be provided in incoming message.

        Args:
            id: id of the message
            bulk: Boolean value indicating if multiple messages should be sent at once
            split_message: Boolean value indicating if message should be sent in parts
            message_size_exeeded: Boolean indicating if message received is too big

        """
        # Arrange
        if message_size_exeeded:
            wappsto.communication.receive_data.MESSAGE_SIZE_BYTES = 0
            messages_in_list = 1
        else:
            messages_in_list = 0
        send_response(self, 'error', bulk=bulk, message_id="93043873", split_message=split_message)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            self.service.socket.receive_data.receive_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert len(self.service.socket.packet_awaiting_confirm) == messages_in_list


class TestSendThreadClass:
    """
    TestSendThreadClass instance.

    Tests sending messages to wappsto server.

    """

    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    def test_send_thread_unhandled(self, messages_in_queue):
        """
        Tests sending message.

        Tests what would happen when sending message.

        Args:
            messages_in_queue: How many messages should be sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                -1
            )
            self.service.socket.sending_queue.put(reply)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.warning", side_effect=check_for_logged_info):
                self.service.socket.send_data.send_thread()
        except KeyboardInterrupt:
            pass

        # Assert
        assert self.service.socket.sending_queue.qsize() == messages_in_queue - 1

    @pytest.mark.parametrize("value", [1, None])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    def test_send_thread_success(self, messages_in_queue, value, log_offline,
                                 connected, log_location, file_size, limit_action,
                                 log_file_exists, make_zip):
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
            make_zip: boolean indicating if log file should be zip

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_SUCCESS,
                rpc_id=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                    patch("logging.Logger.debug", side_effect=check_for_logged_info):
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
            assert validate_json("successResponse", arg) == bool(value)
            for request in arg:
                assert request.get("id", None) == value
                assert bool(request["result"]) is True
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("value", ["test_info", None])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_report(self, messages_in_queue, value, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists, make_zip, send_trace):
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
            make_zip: boolean indicating if log file should be zip
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_REPORT,
                state_id=self.service.get_network().uuid,
                data=value,
                verb=message_data.PUT
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.send_data.automatic_trace = send_trace
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)
        urlopen_trace_id = sent_json_trace_id = ''

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                patch("logging.Logger.debug", side_effect=check_for_logged_info), \
                    patch('urllib.request.urlopen') as urlopen:
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == bool(value)
            for request in arg:
                assert request["params"]["data"].get("data", None) == value
                assert request["params"]["data"]["type"] == "Report"
                assert request["method"] == "PUT"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("value", [1, None])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    def test_send_thread_failed(self, messages_in_queue, value, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists, make_zip):
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
            make_zip: boolean indicating if log file should be zip

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_FAILED,
                rpc_id=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                    patch("logging.Logger.debug", side_effect=check_for_logged_info):
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
            assert validate_json("errorResponse", arg) == bool(value)
            for request in arg:
                assert request.get("id", None) == value
                assert request["error"] == {"code": -32020}
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("upgradable", [True, False])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_reconnect(self, messages_in_queue, valid_message, log_offline,
                                   connected, log_location, file_size, limit_action,
                                   log_file_exists, upgradable, make_zip, send_trace):
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
            upgradable: specifies if object is upgradable
            make_zip: boolean indicating if log file should be zip
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = self.service.get_network().uuid = 1
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_RECONNECT,
                data=value
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.send_data.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch('os.getenv', return_value=str(upgradable)), \
                patch("logging.Logger.error", side_effect=check_for_logged_info), \
                patch("logging.Logger.debug", side_effect=check_for_logged_info), \
                    patch("urllib.request.urlopen") as urlopen:
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == valid_message
            for request in arg:
                assert request["params"]["data"]["meta"].get("id", None) == value
                assert request["params"]["data"]["meta"]["type"] == "network"
                assert request["method"] == "POST"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("valid_message", [True, False])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_control(self, messages_in_queue, valid_message, log_offline,
                                 connected, log_location, file_size, limit_action,
                                 log_file_exists, make_zip, send_trace):
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
            make_zip: boolean indicating if log file should be zip
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
        fake_connect(self, ADDRESS, PORT)
        if valid_message:
            value = self.service.get_network().uuid
        else:
            value = 1
        for x in range(messages_in_queue):
            reply = message_data.MessageData(
                message_data.SEND_CONTROL,
                state_id=value,
                data="",
                verb=message_data.PUT
            )
            self.service.socket.sending_queue.put(reply)
        self.service.socket.my_socket.send = Mock(side_effect=KeyboardInterrupt)
        self.service.socket.connected = connected
        self.service.socket.send_data.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                patch("logging.Logger.debug", side_effect=check_for_logged_info), \
                    patch('urllib.request.urlopen') as urlopen:
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
            assert validate_json("request", arg) == valid_message
            for request in arg:
                assert request["params"]["data"]["meta"].get("id", None) == value
                assert request["params"]["data"]["type"] == "Control"
                assert request["method"] == "PUT"
        else:
            # Message not being sent or saved
            pass

    @pytest.mark.parametrize("object_name", ["network", "device", "value", "control_state", "report_state"])
    @pytest.mark.parametrize("messages_in_queue", [1, 20])
    @pytest.mark.parametrize("log_location", ["test_logs/logs"])
    @pytest.mark.parametrize("file_size", [1, 0])
    @pytest.mark.parametrize("limit_action", [event_storage.REMOVE_OLD])
    @pytest.mark.parametrize("connected,log_offline,log_file_exists,make_zip", [
        (False, True, True, True),
        (False, True, True, False),
        (False, True, False, False),
        (False, False, False, False),
        (True, False, False, False)])
    @pytest.mark.parametrize("send_trace", [True, False])
    def test_send_thread_delete(self, object_name, messages_in_queue, log_offline,
                                connected, log_location, file_size, limit_action,
                                log_file_exists, make_zip, send_trace):
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
            make_zip: boolean indicating if log file should be zip
            send_trace: Boolean indicating if trace should be automatically sent

        """
        # Arrange
        test_json_location = os.path.join(os.path.dirname(__file__), TEST_JSON)
        self.service = wappsto.Wappsto(json_file_name=test_json_location,
                                       log_offline=log_offline,
                                       log_location=log_location,
                                       log_data_limit=1,
                                       limit_action=limit_action,
                                       compression_period=event_storage.HOUR_PERIOD)
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
        self.service.socket.send_data.automatic_trace = send_trace
        urlopen_trace_id = sent_json_trace_id = ''
        file_path = set_up_log(self, log_file_exists, file_size, make_zip)

        # Act
        try:
            # runs until mock object is run and its side_effect raises
            # exception
            with patch("logging.Logger.error", side_effect=check_for_logged_info), \
                patch("logging.Logger.debug", side_effect=check_for_logged_info), \
                    patch('urllib.request.urlopen') as urlopen:
                self.service.socket.send_data.send_thread()
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
            assert len(arg) <= wappsto.connection.communication.send_data.MAX_BULK_SIZE
            assert self.service.socket.sending_queue.qsize() == max(
                messages_in_queue - wappsto.connection.communication.send_data.MAX_BULK_SIZE, 0)
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
            control_value_id=1,
            rpc_id=93043873
        )
        self.service.socket.sending_queue.put(reply)

        # Act
        with patch("urllib.request.urlopen", side_effect=KeyboardInterrupt) as urlopen:
            try:
                # runs until mock object is run and its side_effect raises
                # exception
                self.service.socket.send_data.send_thread()
            except KeyboardInterrupt:
                if urlopen.called:
                    urlopen_args, urlopen_kwargs = urlopen.call_args

                    parsed_id = urlparse.urlparse(urlopen_args[0])
                    parsed_id = int(parse_qs(parsed_id.query)['id'][0])

        # Assert
        assert parsed_id == trace_id
