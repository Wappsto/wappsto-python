"""
The RPC(Remote Procedure Call) module.

Handles GET, SET and PUT communication with the server using JSON encoded
messages.

"""
import json
import datetime
import os
import logging
from random import randint


class SeluxitRpc:
    """
    Check connection status.

    Invokes an init_ok() method on reference of connection. If error with
    communication occurs then a connection is closed.

    Args:
        connection: A reference to the socket instance.
        error_msg: Error message while one occurs.

    """

    @staticmethod
    def connection_ok(self, connection, error_msg):
        """
        Check connection status.

        Check the connection status and send an error message if errors have
        occured.

        Args:
            connection: Reference to the connection socket.
            error_msg: Error message to display.

        """
        if not connection.init_ok():
            self.wapp_log.error(error_msg, exc_info=False)
            connection.close()

    @staticmethod
    def create_meta(network, network_id):
        """Create meta.

        Creates and returns a meta data about a network.

        Args:
            network:
            network_id: Identify number of a network.

        Returns:
            meta data dictionary.

        """
        return {
            "id": network_id,
            "type": "{}".format(network),
            "version": "2.0"
        }

    @staticmethod
    def get_rpc_success_response(message_id):
        """Get success response.

        Returns a success, JSON formatted, encoded in utf-8 response.

        Args:
            message_id: Id of a message.

        Returns:
            JSON formatted data.

        """
        success_response = {'jsonrpc': '2.0', 'id': message_id, 'result': True}
        return json.dumps(success_response).encode('utf-8')

    @staticmethod
    def get_rpc_fail_response(message_id, text):
        """Get fail response.

        Returns a fail, JSON formatted, encoded in utf-8 response with a error
        message.

        Args:
            message_id: Id of a message.
            text: A message of error description.

        Returns:
            JSON formatted data.

        """
        error_description = {'code': -32020, 'message': text}
        error_response = {
            'jsonrpc': '2.0',
            'id': message_id,
            'error': error_description
        }
        return json.dumps(error_response).encode('utf-8')

    def __init__(self, save_init):
        """
        Initialize the seluxit_rpc class.

        Initializes an object of seluxit_rpc class by passing required
        parameters. While initialization, wapp_log is created, random_id
        attribute is set to 1. The attribute is increased every time
        information from server is retrieved. Moreover an data_json_rpc
        attribute is created. It is a dictionary that will be used while
        getting information from a server.

        Args:
            save_init: Determines whether or not save json data.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.save_init = save_init
        self.random_id = self.get_next_random_id()
        self.filename = 'Init_json.txt'
        try:
            os.remove(self.filename)
        except OSError:
            pass
        self.data_json_rpc = {
            'jsonrpc': '2.0',
            'id': self.random_id,
            'params': {}
        }

    def get_next_random_id(self):
        """
        Get next random_id.

        Increases random_id attribute by one every time the method is called.

        Returns:
            random_id: A new, incremented value of random_id attribute.

        """
        range_start = 10 ** (8 - 1)
        range_end = (10 ** 8) - 1
        self.random_id = randint(range_start, range_end)
        return self.random_id

    def get_rpc_network(self, network_id, network_name, put=True):
        """
        Retrieve network from server.

        Retrieves network from a server. The method is used while adding a
        network. Depending on request method it fills data_json_rpc dictionary
        with different information.

        Args:
            network_id: Unique identifying number of a network
            network_name: Name of a network
            put: defines if the request method is put {default: True}

        Returns:
            JSON formatted data of network

        """
        network = "network"
        meta = self.create_meta(network, network_id)
        data_inside = {
            "meta": meta,
            'name': network_name
        }

        if put:
            network_parameters = {
                'url': '/{}/{}'.format(network, network_id),
                'data': data_inside
            }
            self.data_json_rpc['method'] = 'PUT'
        else:
            network_parameters = {
                'url': '/{}'.format(network),
                'data': data_inside
            }
            self.data_json_rpc['method'] = 'POST'

        self.data_json_rpc['params'] = network_parameters
        self.data_json_rpc['id'] = self.get_next_random_id()
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_rpc_device(
            self,
            network_id,
            device_id,
            name,
            manufacturer,
            product,
            version,
            serial,
            description,
            protocol,
            communication,
            included,
            put=True
    ):
        """
        Retrieve device from server.

        Retrieves device from a server. The method is used while adding a
        device. It is checked if attributes from meta data are the same as ones
        from objects. Then depending on request method it fills data_json_rpc
        dictionary with different information.

        Args:
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            name: Name of the device.
            manufacturer: The manufacturer of the device.
            product: The product the device belongs to.
            version: The version of the device.
            serial: The device serial number.
            description: The description of the device.
            protocol: The device's protocol.
            communication: The communication type of the device.
            included: Defines if the device is included in the network or not.
            put: Defines if the request is of type PUT. (default: {True})

        Returns:
            JSON formatted data.

        """
        device = "device"
        meta = self.create_meta(device, device_id)
        device_data = {'name': name, "meta": meta, 'included': included}

        if manufacturer:
            device_data['manufacturer'] = manufacturer

        if product:
            device_data['product'] = product

        if version:
            device_data['version'] = version

        if serial:
            device_data['serial'] = serial

        if description:
            device_data['description'] = description

        if protocol:
            device_data['protocol'] = protocol

        if communication:
            device_data['communication'] = communication

        if put:
            self.data_json_rpc['method'] = 'PUT'
            network_parameters = {
                'url': '/network/{}/{}/{}'.format(
                    network_id,
                    device,
                    device_id
                ),
                'data': device_data}
        else:
            self.data_json_rpc['method'] = 'POST'
            network_parameters = {
                'url': '/network/{}/{}'.format(network_id, device),
                'data': device_data
            }

        self.data_json_rpc['params'] = network_parameters
        self.data_json_rpc['id'] = self.get_next_random_id()
        self.wapp_log.info(self.data_json_rpc)
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def base_device_value(
            self,
            name,
            permission,
            value_id,
            special_type,
            base_type
    ):
        """
        Retrieve base value.

        Retrieves base value from a server. Because there
        are three different kinds of values, this method helps to return
        only common attributes between all of them. The method is used while
        getting number, string and blob values.

        Args:
            name: Name of a value.
            permission: Permission of a value
            value_id: Unique identifier of a value
            special_type: Type of value
            base_type: "blob", "string", "number"

        Returns:
            device_value dictionary containing common information about a
            value.

        """
        device_value = {'status': 'ok', 'name': name, 'permission': permission}
        value = "value"
        device_value["meta"] = self.create_meta(value, value_id)

        if not special_type:
            device_value['type'] = name
        else:
            device_value['type'] = special_type

        device_value[base_type] = {}
        return device_value

    def get_rpc_value_string(
            self,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val_len,
            encoding,
            period,
            delta,
            put=True
    ):
        """
        Retrieve string-type value.

        Retrieves string value from a server. Uses functionality of
        base_device_value to get a directory with common attributes of value
        class.

        Args:
            network_id: Name of a value.
            device_id: Permission of a value.
            value_id: Unique identifier of a value.
            name: Type of value.
            specific_type: "blob", "string", "number".
            permission: Permission of a value.
            max_val_len: Maximum length of a value's string.
            encoding: Value's encoding.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.
            put: Defines if the request is of type PUT. (default: {True})

        Returns:
            JSON formatted data of string value.

        """
        device_value = self.base_device_value(
            name,
            permission,
            value_id,
            specific_type,
            'string'
        )

        if max_val_len:
            device_value['string']['max'] = max_val_len

        if period:
            device_value['string']['period'] = period

        if delta:
            device_value['string']['delta'] = delta

        if encoding:
            device_value['string']['encoding'] = encoding

        self.data_json_rpc['id'] = self.get_next_random_id()
        self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_value,
            put
        )
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_rpc_value_number(
            self,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            min_val,
            max_val,
            step,
            period,
            delta,
            unit,
            put=True
    ):
        """
        Retrieve number-type value.

        Retrieves number value from a server. Uses functionality of
        base_device_value to get a directory with common attributes of value
        class.

        Args:
            network_id: Name of a value.
            device_id: Permission of a value.
            value_id: Unique identifier of a value.
            name: Type of value.
            specific_type: "blob", "string", "number".
            permission: Permission of a value.
            min_val: Minimum of a value's number.
            max_val: Maximum of a value's number.
            encoding: Value's encoding.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.
            put: Defines if the request is of type PUT. (default: {True})

        Returns:
            JSON formatted data of a number value.

        """
        device_value = self.base_device_value(
            name,
            permission,
            value_id,
            specific_type,
            'number'
        )
        device_value['number']['min'] = min_val
        device_value['number']['max'] = max_val
        device_value['number']['step'] = step

        if unit:
            device_value['number']['unit'] = unit

        if period:
            device_value['number']['period'] = period

        if delta:
            device_value['number']['delta'] = delta

        self.data_json_rpc['id'] = self.get_next_random_id()
        self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_value,
            put
        )
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_rpc_value_blob(
            self,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val,
            encoding,
            period,
            delta,
            put=True
    ):
        """
        Retrieve blob-type value.

        Retrieves blob value from a server. Uses functionality of
        base_device_value to get a directory with common attributes of value
        class.

        Args:
            network_id: Name of a value.
            device_id: Permission of a value.
            value_id: Unique identifier of a value.
            name: Type of value.
            specific_type: "blob", "string", "number".
            permission: Permission of a value.
            max_val: Maximum of a value's blob.
            encoding: Value's encoding.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.
            put: Defines if the request is of type PUT. (default: {True})

        Returns:
            JSON formatted data of a blob value.

        """
        device_value = self.base_device_value(
            name,
            permission,
            value_id,
            specific_type,
            'blob'
        )

        if max_val:
            device_value['blob']['max'] = max_val

        if period:
            device_value['blob']['period'] = period

        if delta:
            device_value['blob']['delta'] = delta

        if encoding:
            device_value['blob']['encoding'] = encoding

        self.data_json_rpc['id'] = self.get_next_random_id()
        self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_value,
            put
        )
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_rpc_value_set(
            self,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            element,
            period,
            delta,
            put=True
    ):

        # TODO(Dimitar/Jakub): Describe this later, unsure of what it does.
        # (Possibly ask Karsten when he's back)
        """
        [summary].

        [description]

        Args:
            network_id: [description]
            device_id: [description]
            value_id: [description]
            name: [description]
            specific_type: [description]
            permission: [description]
            element: [description]
            period: [description]
            delta: [description]
            put: [description] (default: {True})

        """
        device_value = self.base_device_value(
            name,
            permission,
            value_id,
            specific_type,
            'set'
        )

        if period:
            device_value['set']['period'] = period
        if element:
            device_value['set']['element'] = element
        if delta:
            device_value['set']['delta'] = delta

        self.data_json_rpc['id'] = self.get_next_random_id()

        self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_value,
            put
        )
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_rpc_state(
            self,
            data,
            network_id,
            device_id,
            value_id,
            report_id,
            set_type,
            get=False,
            put=True,
            trace_id=None,
            state_obj=None
    ):
        """
        Retrieve state of the value.

        Retrieves the value state from a server. Uses functionality of
        base_device_value to get a directory with common attributes of value
        class.

        Args:
            data: Data from the state of the value.
            network_id: Unique identifier of the network.
            device_id: Unique identifier of a device.
            value_id: Unique identifier of a value.
            report_id: Unique identifier of the report state.
            set_type: The type to set.
            get: Defines if the request is of type GET. (default: {False})
            put: Defines if the request is of type PUT. (default: {True})
            trace_id: ID of the debug trace. (default: {None})
            state_obj: Reference to the value instance's state instance.
                (default: {None})

        Returns:
            JSON formatted data of the state.

        """
        update = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        device_state = {
            'meta': {},
            'type': '',
            'status': 'Send',
            'data': data,
            'timestamp': update
        }
        state = "state"
        device_state["meta"] = self.create_meta(state, report_id)

        if set_type == 'report':
            if state_obj is not None:
                state_obj.timestamp = update
            set_type = 'Report'
        else:
            if state_obj is not None:
                state_obj.timestamp = update
            set_type = 'Control'

        device_state['type'] = set_type
        self.data_json_rpc['id'] = self.get_next_random_id()
        if get is True and put is False:
            self.create_json_message(
                device_id,
                network_id,
                value_id,
                device_state,
                put=True,
                state=state,
                state_id=report_id,
                trace_id=trace_id,
                get=True
            )
            return json.dumps(self.data_json_rpc).encode('utf-8')
        self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_state,
            put,
            state=state,
            state_id=report_id,
            trace_id=trace_id
        )
        return json.dumps(self.data_json_rpc).encode('utf-8')

    def get_state_control(
            self,
            connection,
            data,
            network_id,
            device_id,
            value_id,
            control_id,
            get=True
    ):
        """
        Retrieve the control state from the server.

        Gets a value's control state information.Uses the generic
        get_rpc_state() method.

        Args:
            connection: A reference to the socket instance.
            data: Data from the value's control state.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            control_id: The value's control state ID.
            get: Defines if the request is of type GET. (default: {True})

        Returns:
            JSON formatted data if any is retrieved, False otherwise.

        """
        json_data = self.get_rpc_state(
            data,
            network_id,
            device_id,
            value_id,
            control_id,
            "control",
            get=get,
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in state control")
        if json_data is not None:
            return json_data
        else:
            return False

    def create_json_message(
            self,
            device_id,
            network_id,
            value_id,
            data,
            put,
            state=None,
            state_id=None,
            trace_id=None,
            get=False
    ):
        """
        Create a JSON encoded message.

        Creates a message that is used for communicating with a server. Both
        for put and post as well as get request methods. The message is build
        as a url and contains information about a network, device, value and
        state.

        Args:
            device_id: Unique identifying number of device.
            natwork_id: Unique identifying number of network.
            value_id: Unique identifying number of value.
            data: Passed data around which a message will be created.
            put: Determines whether or not it is put request.
            state: reference to a state object.
            state_id: Unique identifying number of state.
            trace_id: Id of trace is necessary.
            get: Defines if the request is of type GET. (default: {False})

        """
        network_parameters = {'url': '', 'data': data}
        base_url = '/network/{}/device/{}/value/'.format(
            network_id,
            device_id
        )
        if put:
            if get:
                if state == 'state':
                    network_parameters['url'] = "{}{}/{}/{}".format(
                        base_url,
                        value_id,
                        state,
                        state_id
                    )
                else:
                    network_parameters['url'] = "{}{}".format(
                        base_url,
                        value_id
                    )

                self.data_json_rpc['method'] = 'GET'
                if trace_id:
                    network_parameters['url'] = "{}?trace={}".format(
                        network_parameters['url'],
                        trace_id
                    )
            else:
                if state == 'state':
                    network_parameters['url'] = "{}{}/{}/{}".format(
                        base_url,
                        value_id,
                        state,
                        state_id
                    )
                else:
                    network_parameters['url'] = "{}{}".format(
                        base_url,
                        value_id
                    )
                self.data_json_rpc['method'] = 'PUT'
                if trace_id:
                    network_parameters['url'] = "{}?trace={}".format(
                        network_parameters['url'],
                        trace_id
                    )
        else:
            if state == 'state':
                network_parameters['url'] = "{}{}/{}".format(
                    base_url,
                    value_id,
                    state
                )
            else:
                network_parameters['url'] = base_url
            self.data_json_rpc['method'] = 'POST'

        self.data_json_rpc['params'] = network_parameters

    # Used by initialize
    def add_network(
            self,
            connection,
            network_id,
            network_name
    ):
        """Add an instance of the Network class.

        While initializing adds network to send and receive queue.

        Args:
            connection: A reference to the socket instance.
            network_id: Unique identifying number of the network.
            network_name: Name of the network.

        """
        json_data = self.get_rpc_network(network_id, network_name, put=False)
        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in add network")

    def add_device(
            self,
            connection,
            network_id,
            device_id,
            name,
            manufacturer,
            product,
            version,
            serial,
            description,
            protocol,
            communication,
            included
    ):
        """Add an instance of the Device class.

        While initializing adds a device to the send and receive queue.

        Args:
            connection: A reference to the socket instance.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            name: Name of the device.
            manufacturer: The manufacturer of the device.
            product: The product the device belongs to.
            version: The version of the device.
            serial: The device serial number.
            description: The description of the device.
            protocol: The device's protocol.
            communication: The communication type of the device.
            included: Defines if the device is included in the network or not.

        """
        json_data = self.get_rpc_device(
            network_id,
            device_id,
            name,
            manufacturer,
            product,
            version,
            serial,
            description,
            protocol,
            communication,
            included,
            put=False
        )
        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in add device")

    def send_init_json(self, connection, json_data):
        """Send initial JSON data.

        Sends the initial state of the JSON data before instantiation or
        modification of it.

        Args:
            connection: Reference to the connection socket.
            json_data: Initial JSON data.

        """
        connection.send_data(json_data)
        if self.save_init:
            with open(self.filename, 'a+') as file:
                file.write(str(json_data) + "\n")

    def add_value_string(
            self,
            connection,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val_len,
            encoding,
            period,
            delta
    ):
        """Add an instance of the Value class with a string.

        While initializing adds a value with a string attributes to the send
        and receive queue.

        Args:
            connection: A reference to the socket instance.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            name: Name of the value.
            specific_type: The type of value.
            permission: Permission of a value.
            max_val: Maximum of a value's string.
            encoding: Value's encoding.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.

        """
        json_data = self.get_rpc_value_string(
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val_len,
            encoding,
            period,
            delta,
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in value string")

    def add_value_number(
            self,
            connection,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            min_val,
            max_val,
            step,
            period,
            delta,
            unit
    ):
        """Add an instance of the Value class with a number.

        While initializing adds a value with a number attributes to the send
        and receive queue.

        Args:
            connection: A reference to the socket instance.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            name: Name of the value.
            specific_type: The type of value.
            permission: Permission of a value.
            min_val: Minimum value.
            max_val: Maximum value.
            step: Step between values.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.
            unit: Unit of measurement for the value.

        """
        json_data = self.get_rpc_value_number(
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            min_val,
            max_val,
            step,
            period,
            delta,
            unit,
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in value number")

    def add_value_blob(
            self,
            connection,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val,
            encoding,
            period,
            delta
    ):
        """Add an instance of the Value class with a blob.

        While initializing adds a value with a blob attributes to the send and
        receive queue.

        Args:
            connection: A reference to the socket instance.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            name: Name of the value.
            specific_type: The type of value.
            permission: Permission of a value.
            max_val: Maximum of a value's string.
            encoding: Value's encoding.
            period: Time after which a value should send report.
            delta: Difference between val1 and val2 over time to check for.

        """
        json_data = self.get_rpc_value_blob(
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            max_val,
            encoding,
            period,
            delta,
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in value blob")

    def add_value_set(
            self,
            connection,
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            element,
            period,
            delta
    ):
        # TODO(Dimitar/Jakub): Describe this later, unsure of what it does.
        # (Possibly ask Karsten when he's back)
        """[summary].

        [description]

        Args:
            connection: [description]
            network_id: [description]
            device_id: [description]
            value_id: [description]
            name: [description]
            specific_type: [description]
            permission: [description]
            element: [description]
            period: [description]
            delta: [description]

        """
        json_data = self.get_rpc_value_set(
            network_id,
            device_id,
            value_id,
            name,
            specific_type,
            permission,
            element,
            period,
            delta,
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in value set")

    def add_state_report(
            self,
            connection,
            data,
            network_id,
            device_id,
            value_id,
            report_id
    ):
        """Add an instance of the State class of type Report.

        While initializing adds a State of type Report to the send and
        receive queue.

        Args:
            connection: A reference to the socket instance.
            data: Data from report state.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            report_id: Unique identifying number of the report state.

        """
        json_data = self.get_rpc_state(
            data,
            network_id,
            device_id,
            value_id,
            report_id,
            "report",
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in state report")

    def add_state_control(
            self,
            connection,
            data,
            network_id,
            device_id,
            value_id,
            control_id
    ):
        """Add an instance of the State class of type Control.

        While initializing adds a State of type Control to the send and
        receive queue.

        Args:
            connection: A reference to the socket instance.
            data: Data from report state.
            network_id: Unique identifying number of the network.
            device_id: Unique identifying number of the device.
            value_id: Unique identifying number of the value.
            control_id: Unique identifying number of the control state.

        """
        json_data = self.get_rpc_state(
            data,
            network_id,
            device_id,
            value_id,
            control_id,
            "control",
            put=False
        )

        self.send_init_json(connection, json_data)
        self.connection_ok(self, connection, "Error in state control")
