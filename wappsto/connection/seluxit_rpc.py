"""
The RPC(Remote Procedure Call) module.

Contain RPC utils, for easy of use.

"""
import datetime
import json
import os
import random
import string

from jsonrpcclient import requests, response

from . import message_data

JSONRPC = '2.0'

session_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
session_count = 0


def id_count(verb):
    global session_count
    session_count += 1
    return f"{session_id}_{verb}_{session_count}"


def create_meta(network, network_id):
    """
    Create meta.

    Creates and returns a meta data about a network.

    Args:
        network:
        network_id: Identify number of a network.

    Returns:
        meta data dictionary.

    """
    return {
        'id': network_id,
        'type': '{}'.format(network),
        'version': '2.0'
    }


def get_rpc_success_response(message_id):
    """
    Get success response.

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


def time_stamp():
    """Return The default timestamp used for Wappsto."""
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def is_upgradable():
    """
    Check if System is set to upgradable.

    Returns:
        True, if the system is upgradable,
        False, if it is not.

    """
    return os.getenv("UPGRADABLE", "").upper() == "TRUE"


def get_rpc_network(network_id, network_name, verb,
                    trace_id=None):
    """
    Retrieve network from server.

    Retrieves network from a server. The method is used while adding a
    network. Depending on request method it fills data_json_rpc dictionary
    with different information.

    Args:
        network_id: Unique identifying number of a network
        network_name: Name of a network
        verb: indicates what verb should be used.
        trace_id:  ID of the debug trace {default: None}

    Returns:
        JSON formatted data of network

    """
    meta = create_meta('network', network_id)
    if is_upgradable():
        meta.update({'upgradable': True})
    data_inside = {
        'meta': meta,
        'name': network_name
    }
    url = '/network'

    if verb == message_data.PUT:
        url = '/{}'.format(network_id)

    if trace_id:
        url = "{}?trace={}".format(url, trace_id)

    data_json_rpc = requests.Request(
        verb,
        url=url,
        data=data_inside,
        request_id=id_count(verb)
    )

    return data_json_rpc


def get_rpc_state(
        data,
        network_id,
        device_id,
        value_id,
        state_id,
        set_type,
        verb,
        trace_id=None
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
        state_id: Unique identifier of the state.
        set_type: The type to set.
        verb: indicates what verb should be used.
        trace_id: ID of the debug trace. (default: {None})

    Returns:
        JSON formatted data of the state.

    """
    if verb != message_data.GET:
        device_state = {
            'meta': create_meta('state', state_id),
            'type': set_type,
            'status': 'Send',
            'data': data,
            'timestamp': time_stamp()
        }
    else:
        device_state = None

    url = '/network/{}/device/{}/value/{}/state/{}'
    url = url.format(network_id, device_id, value_id, state_id)

    if trace_id:
        url = '{}?trace={}'.format(url, trace_id)

    data_json_rpc = requests.Request(
        verb,
        url=url,
        data=device_state,
        request_id=id_count(verb)
    )
    return data_json_rpc


def get_rpc_delete(network_id,
                   device_id,
                   value_id,
                   state_id,
                   trace_id=None):
    """
    Creates delete request.

    The method is used to create message that could allow to
    delete network or its elements.

    Args:
        network_id: id of the network to delete/modify.
        device_id: id of the device to delete/modify.
        value_id: id of the value to delete/modify.
        state_id: id of the state to delete.
        trace_id: ID of the debug trace. {default: None}

    Returns:
        JSON formatted data of delete message

    """
    # UNSURE(MBK): I feel that there is a more pythonic way of doing this.
    if network_id:
        url = '/network/{}'.format(network_id)
        if device_id:
            url += '/device/{}'.format(device_id)
            if value_id:
                url += '/value/{}'.format(value_id)
                if state_id:
                    url += '/state/{}'.format(state_id)

    if trace_id:
        url = '{}?trace={}'.format(url, trace_id)

    data_json_rpc = requests.Request(
        'DELETE',
        url=url,
        request_id=id_count('DELETE')
    )

    return data_json_rpc


def get_rpc_whole_json(json_data, trace_id=None):
    """
    Creates request containing the whole json file.

    The method is used while starting initializing and it fills
    data_json_rpc dictionary with url and data containing json object.

    Args:
        json_data: Data read from json file.
        trace_id:  ID of the debug trace {default: None}

    Returns:
        JSON formatted data of network

    """
    url = '/{}'.format("network")

    if trace_id:
        url = "{}?trace={}".format(url, trace_id)

    data_json_rpc = requests.Request(
        'POST',
        url=url,
        data=json_data,
        request_id=id_count('POST')
    )
    return data_json_rpc
