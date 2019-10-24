#!/usr/bin/env python3
import os
import sys
import time
import json
import pytest
import socket
import wappsto
import datetime
from mock import Mock
from test import fake_socket
from test import mock_wappsto_server
from wappsto.connection.seluxit_rpc import SeluxitRpc
from wappsto.connection.network_classes.state import State
from wappsto.connection.network_classes.device import Device
from wappsto.connection.network_classes.errors.wappsto_errors import ServerConnectionException as ServerConnectionException
from wappsto.connection.network_classes.errors.wappsto_errors import CallbackNotCallableException as CallbackNotCallableException
# Bypassing top-level import issues
from pathlib import Path
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))
try:
    sys.path.remove(str(parent))
except ValueError:
    pass




def fake_set(self):
    self.wapp_log.info("Totally SSL wrapped the socket. Totally.")
    return self.my_raw_socket


class TestInstantiation:

    def setup_method(self):
        self.json_ok_two_devices = os.path.join(
            os.path.dirname(__file__),
            'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json'
        )
        self.json_incorrect = os.path.join(
            os.path.dirname(__file__),
            'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json'
        )

    def test_instantiation_device_list_passes(self):

        assert len(wappsto.Wappsto(json_file_name=self.json_ok_two_devices).instance.device_list) > 0

    def test_instantiation_device_list_2_devices_passes(self):

        assert len(wappsto.Wappsto(json_file_name=self.json_ok_two_devices).instance.device_list) == 2

    def test_instantiation_parsing_fails(self):

        with pytest.raises(json.decoder.JSONDecodeError):
            wappsto.Wappsto(json_file_name=self.json_incorrect)

    def test_instantiation_parsing_invalid_JSON_errors(self):
        with pytest.raises(Exception):
            wappsto.Wappsto(json_file_name=self.json_incorrect)

    def test_instantiation_parsing_file_not_found_errors(self):

        with pytest.raises(FileNotFoundError):
            wappsto.Wappsto(json_file_name="blabla")


class TestDevice:

    @classmethod
    def setup_method(self):
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json')
        self.json_incorrect = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json')
        self.wapp = wappsto.Wappsto(json_file_name=self.json_ok_two_devices)

    def test_finding_device_passes(self):
        device = self.wapp.get_device("test_device_all_fieldsasdasd")
        assert device is not None

    def test_finding_device_errors(self):
        self.test_wapp = wappsto.Wappsto(json_file_name=self.json_ok_two_devices)
        with pytest.raises(Exception):
            self.test_wapp.get_device("asdfasf")

    def test_set_value_callback_passes(self):
        device = self.wapp.get_device("test_device_all_fieldsasdasd")
        value = device.get_value("test_value_with_number")
        def value_callback(self):
            pass
        value.set_callback(value_callback)
        assert value.callback == value_callback

    def test_set_value_callback_with_return_passes(self):
        device = self.wapp.get_device("test_device_all_fieldsasdasd")
        value = device.get_value("test_value_with_number")
        def value_callback(self):
            return 3
        value.set_callback(value_callback)
        assert value.callback(self) == 3


class TestValue:

    @classmethod
    def setup_method(self):
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json')
        self.wapp = wappsto.Wappsto(json_file_name=self.json_ok_two_devices)

    def test_finding_value_passes(self):
        device = self.wapp.get_device("test_device_all_fieldsasdasd")
        value = device.get_value("test_value_with_number")
        assert value is not None

    def test_device1_value_length_is_3_passes(self):
        device1 = self.wapp.get_device("test_device_all_fieldsasdasd")
        assert len(device1.value_list) == 3

    def test_device2_value_length_is_3_passes(self):
        device2 = self.wapp.get_device("test_device_not_all_fields")
        assert len(device2.value_list) == 3

    def test_value_wrong_type_of_value_error_logs(self, caplog):
        value_to_test = None
        for device in self.wapp.instance.device_list:
            for value in device.value_list:
                if value.control_state is not None:
                    if value.number_min is not None:
                        value_to_test = value
        value_to_test.send_control('asd')

        assert 'Invalid type of value. Must be a number.' in caplog.text

    def test_value_string_over_max_error_logs(self, caplog):
        value_to_test = None
        for device in self.wapp.instance.device_list:
            for value in device.value_list:
                if value.control_state is not None:
                    if value.string_max is not None:
                        if value.string_max < 3:
                            value_to_test = value
        msg = 'asd'
        value_to_test.send_control(msg)

        assert 'Value {} not in correct range for {}'.format(msg, value_to_test.name) in caplog.text

    def test_set_not_callable_callback_errors(self, caplog):
         for device in self.wapp.instance.device_list:
            for value in device.value_list:
                if value.name == 'test_value_with_number':
                    with pytest.raises(CallbackNotCallableException):
                        value.set_callback(3)


class TestState:
    @classmethod
    def setup_method(self):
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json')
        self.wapp = wappsto.Wappsto(json_file_name=self.json_ok_two_devices)

    def test_finding_state_passes(self):
        device = self.wapp.get_device("test_device_all_fieldsasdasd")
        value = device.get_value("test_value_blob")

        assert value.get_report_state() is not None and value.get_control_state() is not None


class TestStatus:

    @classmethod
    def setup_method(self):
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json')
        self.json_incorrect = os.path.join(os.path.dirname(__file__), 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json')

        self.wapp = wappsto.Wappsto(json_file_name=self.json_ok_two_devices)

    def test_get_status_reference_passes(self):
        status = self.wapp.get_status()

        assert status is not None

    def test_set_status_callback_passes(self):
        status = self.wapp.get_status()

        def status_callback(self):
            pass
        status.set_callback(status_callback)

        assert status.callback is status_callback


class TestSendReceive:

    @pytest.fixture(autouse=True)
    def mock_server_sockets(self, mocker):
        from wappsto.connection.communication import ClientSocket
        mocker.patch.object(socket, 'socket', new=fake_socket.FakeSocket)
        mocker.patch.object(ClientSocket, 'ssl_wrap', new=fake_set)
        mocker.patch.object(ClientSocket, 'init_ok', new=lambda f: True)

    @classmethod
    def setup_class(self):
        one = 'test_JSON/62606aea-fc31-4706-8074-83a705fb29e5.json'
        two = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json'
        three = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json'
        self.json_value_one = os.path.join(os.path.dirname(__file__),one)
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__),two)
        self.json_incorrect = os.path.join(os.path.dirname(__file__), three)
        self.wapp = wappsto.Wappsto(json_file_name=self.json_value_one)

    def test_wappsto_send_receive_response_passes(self, mocker):
        self.wapp.start(address="127.0.0.1", port=8080)
        message_ids = self.wapp.socket.my_socket.list_of_message_ids
        assert len(message_ids) == 15

    def test_wappsto_refresh_button_changes_updates_timestamp_passes(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        device = self.wapp.get_device("Lamp")
        time1 = device.get_value("ON/OFF").last_update_of_report

        def w(value, type):
            if type == "report":
                x = "It is a report callback"
            else:
                x = "It is a control callback"

        device.get_value("ON/OFF").set_callback(w)
        time.sleep(2)
        self.wapp.socket.my_socket.refresh_button("ON/OFF")
        device = self.wapp.get_device("Lamp")
        time2 = device.get_value("ON/OFF").report_state.timestamp
        self.clear_logs()
        assert time1 is not time2

    def test_wappsto_delta_test_first(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        delta = 0.1
        list = []
        values_list = [0, 1, 1, 0, 2]
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_delta(delta)
        for i in range(len(values_list)):
            value.last_controlled = values_list[i]
            value_prepared = value.last_update_of_report[11:-8]
            list.append(datetime.datetime.strptime(value_prepared, '%H:%M:%S'))
            time.sleep(2)
        time.sleep(1)
        self.clear_logs()
        control_set_length = set(list)
        assert len(control_set_length) == 4

    def test_wappsto_delta_test_second(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        delta = 100
        list = []
        values_list = [0, 1, 1, 1, 0]
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_delta(delta)
        for i in range(len(values_list)):
            value.last_controlled = values_list[i]
            value_prepared = value.last_update_of_report[11:-8]
            list.append(datetime.datetime.strptime(value_prepared, '%H:%M:%S'))
            time.sleep(2)
        time.sleep(1)
        self.clear_logs()
        control_set_length = set(list)
        assert len(control_set_length) == 1

    def test_wappsto_period_test(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        refreshment_time = 2
        assert_count = 0
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_period(refreshment_time)
        for i in range(refreshment_time):
            time.sleep(3)
        file = open("server_logging", "r")
        for line in file:
            if "Sending report [PERIOD]." in line:
                assert_count = assert_count + 1
        self.clear_logs()
        assert assert_count in [3, 4]

    def test_wappsto_period_test_with_refreshment(self):
        assert_count = 0
        self.wapp.start(address="127.0.0.1", port=8080)
        refreshment_time = 3
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_period(refreshment_time)
        for i in range(2):
            self.wapp.socket.my_socket.refresh_button("ON/OFF")
            time.sleep(4)
        time.sleep(1)
        file = open("server_logging", "r")
        for line in file:
            if "Sending report [PERIOD]." in line:
                assert_count = assert_count + 1
        self.clear_logs()

        assert assert_count == 3

    def test_wappsto_period_test_with_refreshment_no_period_refresh(self):
        assert_count = 0
        self.wapp.start(address="127.0.0.1", port=8080)
        refreshment_time = 10
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_period(refreshment_time)
        for i in range(3):
            self.wapp.socket.my_socket.refresh_button("ON/OFF")
            time.sleep(2)
        time.sleep(1)
        file = open("server_logging", "r")
        for line in file:
            if "Sending report [PERIOD]." in line:
                assert_count = assert_count + 1
        self.clear_logs()
        assert assert_count == 0

    def test_wappsto_value_incorrect_range(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.send_control(8)
        time.sleep(1)
        assert_count = 0
        file = open("server_logging", "r")
        for line in file:
            if "Invalid number. Range:" in line:
                assert_count = assert_count + 1
        self.clear_logs()
        assert assert_count == 1

    def test_wappsto_value_correct_range(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.send_control(1)
        time.sleep(0.5)
        assert value.data_value == 1

    def test_wappsto_set_delta_for_string_value(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        delta = 10
        value = self.wapp.get_device("Lamp").get_value("Displaying text")
        value.set_delta(delta)
        result = False
        file = open("server_logging", "r")
        for line in file:
            if "Cannot set the delta for this value." in line:
                result = True
        assert result is True
        self.clear_logs()


    def test_wappsto_set_incorrect_delta_type(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        delta = "It is not a number"
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.set_delta(delta)
        result = False
        file = open("server_logging", "r")
        for line in file:
            if "Delta value must be a number" in line:
                result = True
        assert result is True
        self.clear_logs()

    def test_wappsto_set_period_for_value_without_report_state(self):
        self.wapp.start(address="127.0.0.1", port=8080)
        period = 4
        value = self.wapp.get_device("Lamp").get_value("ON/OFF")
        value.report_state = None
        value.set_period(period)
        result = False
        file = open("server_logging", "r")
        for line in file:
            if "Cannot set the period for this value." in line:
                result = True
        assert result is True
        self.clear_logs()

    def clear_logs(self):
        open("server_logging", "w").close()


class TestSaveObjectInstances:

    @pytest.fixture(autouse=True)
    def clean_files(self):
        folder = os.path.join(os.path.dirname(__file__), 'saved_instances/')
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, f)):
                    os.remove(os.path.join(folder, f))

    @pytest.fixture(autouse=True)
    def mock_server_sockets(self, mocker):
        from wappsto.connection.communication import ClientSocket
        mocker.patch.object(socket, 'socket', new=fake_socket.FakeSocket)
        mocker.patch.object(ClientSocket, 'ssl_wrap', new=fake_set)
        mocker.patch.object(ClientSocket, 'init_ok', new=lambda f: True)

    @classmethod
    def setup_class(self):
        one = 'test_JSON/62606aea-fc31-4706-8074-83a705fb29e5.json'
        two = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json'
        three = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json'
        self.json_value_one = os.path.join(os.path.dirname(__file__), one)
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__), two)
        self.json_incorrect = os.path.join(os.path.dirname(__file__), three)
        self.wapp = wappsto.Wappsto(json_file_name=self.json_value_one)
        self.path_to_saved = os.path.join(self.wapp.path_to_calling_file, 'saved_instances/')

    def test_if_file_not_empty_passes(self, capsys):
        self.wapp.start(address="127.0.0.1", port=8080)
        self.wapp.stop()

        result = None
        with open(os.path.join(self.path_to_saved, '62606aea-fc31-4706-8074-83a705fb29e5.json'), "r") as f:
            result = f.read()

        assert result is not None or ""

    def test_directory_creation_passes(self):
        folder = os.path.join(os.path.dirname(__file__), 'saved_instances/')

        if os.path.isdir(folder):
            os.rmdir(folder)

        self.wapp.start(address="127.0.0.1", port=8080)
        self.wapp.stop()

        assert os.path.isdir(folder)


class TestLoadObjectInstances:

    @pytest.fixture(autouse=True)
    def clean_files(self):
        folder = os.path.join(os.path.dirname(__file__), 'saved_instances/')

        if os.path.exists(folder):
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, f)):
                    os.remove(os.path.join(folder, f))

    @pytest.fixture(autouse=True)
    def mock_server_sockets(self, mocker):
        from wappsto.connection.communication import ClientSocket
        mocker.patch.object(socket, 'socket', new=fake_socket.FakeSocket)
        mocker.patch.object(ClientSocket, 'ssl_wrap', new=fake_set)
        mocker.patch.object(ClientSocket, 'init_ok', new=lambda f: True)

    @classmethod
    def setup_class(self):
        one = 'test_JSON/62606aea-fc31-4706-8074-83a705fb29e5.json'
        two = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce.json'
        three = 'test_JSON/e9ec36e2-0bd5-4fef-8e7b-9c200e93ebce_invalid.json'
        self.json_value_one = os.path.join(os.path.dirname(__file__),one)
        self.json_ok_two_devices = os.path.join(os.path.dirname(__file__),two)
        self.json_incorrect = os.path.join(os.path.dirname(__file__), three)
        self.wapp = wappsto.Wappsto(json_file_name=self.json_value_one)
        self.path_to_saved = os.path.join(self.wapp.path_to_calling_file, 'saved_instances/')

    def test_load_files(self):

        self.wapp1 = wappsto.Wappsto(json_file_name=self.json_value_one)
        self.wapp1.start(address="127.0.0.1", port=8080)
        self.wapp1.stop()

        self.wapp2 = wappsto.Wappsto(load_from_state_file=True)
        self.wapp2.start(address="127.0.0.1", port=8080)

        assert self.wapp2.instance is not None

    def test_loading_empty_saved_instances_directory_errors(self, clean_files):
        with pytest.raises(ValueError):
            self.wapp_test = wappsto.Wappsto(load_from_state_file=True)

    @classmethod
    def teardown_method(self):
        for f in os.listdir(self.path_to_saved):
            if os.path.isfile(os.path.join(self.path_to_saved, f)):
                os.remove(os.path.join(self.path_to_saved, f))


class TestValueUnitTests:

    @classmethod
    def setup_method(self):
        self.parent_device = Mock(spec=Device)
        self.parent_device.uuid = "1"
        self.report_state = Mock(spec=State)
        self.report_state.uuid = "1.1.1"
        self.report_state.timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        self.control_state = Mock(spec=State)
        self.control_state.uuid = "1.1.2"
        self.rpc = Mock(spec=SeluxitRpc)
        self.value_number = wappsto.connection.network_classes.value.Value(
            self.parent_device, "1.1", "value_number", "number", "number",
            "rw", 0, 5, 1, 1, "cm", None, None, None, None,
        )

        self.value_blob = wappsto.connection.network_classes.value.Value(
            self.parent_device, "1.2", "value_blob", "blob", "blob",
            "rw", None, None, None, None, None, None, None, "utf-8", "15"
        )

        self.value_string = wappsto.connection.network_classes.value.Value(
            self.parent_device, "1.3", "value_string", "string", "string",
            "rw", None, None, None, None, None, "utf-8", "15", None, None
        )


    def test_value_set_period_report_state_not_exists(self):
        self.value_number.set_period(2)
        assert self.value_number.period is None

    def test_value_set_period_less_than_zero(self):
        self.value_number.set_period(-5)
        assert self.value_number.period is None

    def test_value_set_delta_without_report_state(self):
        self.value_number.set_delta(2)
        assert self.value_number.delta is None

    def test_value_set_delta_with_report_state(self):
        self.value_number.add_report_state(self.report_state)
        self.value_number.set_delta(2)
        assert self.value_number.delta == 2

    def test_value_set_delta_less_than_zero(self):
        self.value_number.add_report_state(self.report_state)
        self.value_number.set_delta(-1)
        assert self.value_number.delta is None

    def test_value_set_delta_for_not_number_type_value(self):
        self.value_blob.add_report_state(self.report_state)
        self.value_blob.set_delta(2)
        assert self.value_blob.delta is None

    def test_callback_is_not_set_after_initialization_blob(self):
        assert self.value_blob.callback is None

    def test_callback_is_not_set_after_initialization_number(self):
        assert self.value_number.callback is None

    def test_callback_is_not_set_after_initialization_string(self):
        assert self.value_string.callback is None

    def test_set_callback_not_callable(self):
        wappsto_errors_folder = wappsto.connection.network_classes.errors
        exc = wappsto_errors_folder.wappsto_errors.CallbackNotCallableException
        with pytest.raises(exc):
            self.value_number.set_callback("Function")

    def test_set_callback_callable(self):
        wappsto_errors_folder = wappsto.connection.network_classes.errors
        exc = wappsto_errors_folder.wappsto_errors.CallbackNotCallableException

        def callback_method(a,b):
            return a+b
        assert self.value_number.set_callback(callback=callback_method) is True

    def test_send_report_difference_bigger_than_delta(self):
        self.value_number.difference = 5
        self.value_number.delta = 2
        self.value_number.rpc = self.rpc
        self.value_number.delta_report = 1
        self.value_number.send_report_delta(self.report_state)
        no_send_logic_calls = self.value_number.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_report_difference_equals_delta(self):
        self.value_number.difference = 5
        self.value_number.delta = 5
        self.value_number.rpc = self.rpc
        self.value_number.delta_report = 1
        self.value_number.send_report_delta(self.report_state)
        no_send_logic_calls = self.value_number.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_report_difference_smaller_than_delta(self):
        self.value_number.difference = 3
        self.value_number.delta = 10
        self.value_number.rpc = self.rpc
        self.value_number.delta_report = 1
        self.value_number.send_report_delta(self.report_state)
        no_send_logic_calls = self.value_number.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 0

    def test_send_control_without_control_state_returns_false(self):
        result = self.value_number.send_control(2)
        assert result is False

    def test_send_control_exceed_allowed_above_number_value_number(self):
        self.value_number.add_control_state(self.control_state)
        result = self.value_number.send_control(10)
        assert result is False

    def test_send_control_exceed_allowed_below_number_value_number(self):
        self.value_number.add_control_state(self.control_state)
        result = self.value_number.send_control(-50)
        assert result is False

    def test_send_control_allowed_number_value_number(self):
        self.value_number.add_control_state(self.control_state)
        self.value_number.rpc = self.rpc
        self.value_number.send_control(2)
        no_send_logic_calls = self.value_number.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_control_string_max_is_none_value_string(self):
        self.value_string.add_control_state(self.control_state)
        self.value_string.rpc = self.rpc
        self.value_string.string_max = None
        self.value_string.send_control("Hello" * 30)
        no_send_logic_calls = self.value_string.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_control_blob_max_is_none_value_blob(self):
        self.value_blob.add_control_state(self.control_state)
        self.value_blob.rpc = self.rpc
        self.value_blob.blob_max = None
        self.value_blob.send_control("Hello" * 20)
        no_send_logic_calls = self.value_blob.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_control_string_max_is_15_value_valid_value_string(self):
        self.value_string.add_control_state(self.control_state)
        self.value_string.rpc = self.rpc
        self.value_string.send_control("Imagination")
        no_send_logic_calls = self.value_string.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1

    def test_send_control_string_max_is_15_value_invalid_value_string(self):
        self.value_string.add_control_state(self.control_state)
        self.value_string.rpc = self.rpc
        self.value_string.send_control("Imagination" * 10)
        no_send_logic_calls = self.value_string.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 0

    def test_send_control_blob_max_is_15_value_valid_value_string(self):
        self.value_blob.add_control_state(self.control_state)
        self.value_blob.rpc = self.rpc
        self.value_blob.send_control("Imagination")
        no_send_logic_calls = self.value_blob.rpc.get_rpc_state.call_count
        assert no_send_logic_calls is 1


class TestRealServerConnection:

    @pytest.fixture(autouse=True)
    def clear_logs(self):
        open("server_logging", "w").close()

    @classmethod
    def setup_class(self):
        self.server = mock_wappsto_server.MockServer("127.0.0.1", 8080)
        self.server.threaded_run()
        one = 'test_JSON/62606aea-fc31-4706-8074-83a705fb29e5.json'
        self.json_value_one = os.path.join(os.path.dirname(__file__), one)
        self.wapp = wappsto.Wappsto(json_file_name=self.json_value_one)

    def test_connection_to_mock_server(self):
        self.wapp.start("127.0.0.1", 8080)
        result = False
        file = open("server_logging", "r")
        for line in file:
            if "Connected to server!" in line:
                result = True
        assert result is True
