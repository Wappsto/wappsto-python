"""
The RPC(Remote Procedure Call) module.

Handles GET, SET and PUT communication with the server using JSON encoded
messages.

"""
import json
import datetime
import os
import logging
from jsonrpcclient import requests, response

JSONRPC = "2.0"


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
        success_response = str(response.SuccessResponse(jsonrpc=JSONRPC,
                                                        id=message_id,
                                                        result=True))
        return json.loads(success_response)

    @staticmethod
    def get_rpc_fail_response(message_id, text):
        """
        Get fail response.

        Returns a fail, JSON formatted, encoded in utf-8 response with a error
        message.

        Args:
            message_id: Id of a message.
            text: A message of error description.

        Returns:
            JSON formatted data.

        """
        error_description = {'message': text, 'code': -32020, 'data': ''}
        error_response = str(response.ErrorResponse(jsonrpc=JSONRPC,
                                                    id=message_id,
                                                    error=error_description))
        return json.loads(error_response)

    @staticmethod
    def is_upgradable():
        """
        Check if System is set to upgradable.

        Returns:
            True, if the system is upgradable,
            False, if it is not.

        """
        return True if os.getenv("UPGRADABLE") in ['true', 'True'] else False

    def __init__(self, save_init):
        """
        Initialize the seluxit_rpc class.

        Initializes an object of seluxit_rpc class by passing required
        parameters. While initialization, wapp_log is created.

        Args:
            save_init: Determines whether or not save json data.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.save_init = save_init
        self.filename = 'Init_json.txt'
        try:
            os.remove(self.filename)
        except OSError:
            pass

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
        if SeluxitRpc.is_upgradable():
            meta.update({'upgradable': True})
        data_inside = {
            "meta": meta,
            'name': network_name
        }

        if put:
            data_json_rpc = requests.Request('PUT',
                                             url='/{}/{}'.format(
                                                 network,
                                                 network_id),
                                             data=data_inside)
        else:
            data_json_rpc = requests.Request('POST',
                                             url='/{}'.format(network),
                                             data=data_inside)
        return data_json_rpc

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

        if state_obj is not None:
            state_obj.timestamp = update

        if set_type == 'report':
            set_type = 'Report'
        else:
            set_type = 'Control'

        device_state['type'] = set_type

        if get is True and put is False:
            put = True
        else:
            get = False

        data_json_rpc = self.create_json_message(
            device_id,
            network_id,
            value_id,
            device_state,
            put=put,
            state=state,
            state_id=report_id,
            trace_id=trace_id,
            get=get
        )
        return data_json_rpc

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
            network_id: Unique identifying number of network.
            value_id: Unique identifying number of value.
            data: Passed data around which a message will be created.
            put: Determines whether or not it is put request.
            state: reference to a state object.
            state_id: Unique identifying number of state.
            trace_id: Id of trace is necessary.
            get: Defines if the request is of type GET. (default: {False})

        """
        base_url = '/network/{}/device/{}/value/'.format(network_id, device_id)
        if put:
            if get:
                verb = 'GET'
            else:
                verb = 'PUT'

            if state == 'state':
                url = "{}{}/{}/{}".format(base_url, value_id, state, state_id)
            else:
                url = "{}{}".format(base_url, value_id)

            if trace_id:
                url = "{}?trace={}".format(url, trace_id)
        else:
            verb = 'POST'
            if state == 'state':
                url = "{}{}/{}".format(base_url, value_id, state)
            else:
                url = base_url

        return requests.Request(verb,
                                url=url,
                                data=data)

    def get_rpc_whole_json(self, json_data):
        """
        Creates request containing the whole json file.

        The method is used while starting initializing and it fills
        data_json_rpc dictionary with url and data containing json object.

        Args:
            json_data: Data read from json file.

        Returns:
            JSON formatted data of network

        """
        data_json_rpc = requests.Request('POST',
                                         url='/{}'.format("network"),
                                         data=json_data)
        return data_json_rpc

    def add_whole_json(
            self,
            connection,
            json_data
    ):
        """Add an instance of the whole json file.

        While initializing adds network/device/value/state to send and
        receive queue.

        Args:
            connection: A reference to the socket instance.
            json_data: Data read from json file.

        """
        message = self.get_rpc_whole_json(json_data)
        self.send_init_json(connection, message)

    def send_init_json(self, connection, json_data):
        """Send initial JSON data.

        Sends the initial state of the JSON data before instantiation or
        modification of it.

        Args:
            connection: Reference to the connection socket.
            json_data: Initial JSON data.

        """
        connection.create_bulk(json_data)
        if self.save_init:
            with open(self.filename, 'a+') as file:
                file.write(str(json_data) + "\n")
