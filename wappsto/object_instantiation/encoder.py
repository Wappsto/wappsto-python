"""
The wappsto Encoding module.

Handles encoding object instances to a JSON file for the purpose of saving
them and any modifications made to them.
"""
import logging


class WappstoEncoder:
    """
    The wappsto encoding class.

    Handles encoding the current runtime object instances into JSON. This
    allows the system to be saved as a parsable JSON file similar to the one
    used to start the package.
    """

    def __init__(self):
        """
        Initialize WappstoEncoding.

        Initializes the WappstoEncoding class, which handles encoding the
        various parts of the system into a JSON file.
        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

    def encode(self, instance):
        """
        Encode instance.

        Encodes objects from the runtime instances and returns the result so
        it can be saved.

        Args:
            instance: Reference to the instance class that holds the object
                instances.

        Returns:
            An encoded JSON result.

        """
        encoded_result = {}
        encoded_result.update(self.encode_network(instance.network_cl))

        for device in instance.device_list:
            encoded_device = self.encode_device(device)
            encoded_result['device'].append(encoded_device)

        return encoded_result

    def encode_network(self, network):
        """
        Encode instance of Network class.

        Handles the condoing of the network instance, contains a template to
        encode the network with.

        Args:
            network: Reference to the instance of the Network class.

        Returns:
            The encoded JSON result.

        """
        encoded_network = {
            "meta": {
                "type": "network",
                "version": "2.0",
                "id": ""
            },
            "name": "",
            "device": []
        }
        encoded_network['meta']['id'] = network.uuid
        encoded_network['name'] = network.name
        self.wapp_log.debug("Network JSON: {}".format(encoded_network))

        return encoded_network

    def encode_device(self, device):
        """
        Encode instance of Device class.

        Handles the encondoing of the device instance, contains a template to
        encode the device with.

        Args:
            device: Reference to the instance of the Device class.

        Returns:
            The encoded JSON result.

        """
        encoded_device = {
            "meta": {
                "type": "device",
                "version": "2.0",
                "id": ""
            },
            "name": "",
            "product": "",
            "serial": "",
            "description": "",
            "protocol": "",
            "communication": "",
            "version": "",
            "manufacturer": "",
            "value": []
        }

        encoded_device['meta']['id'] = device.uuid
        encoded_device['name'] = device.name
        encoded_device['product'] = device.product
        encoded_device['protocol'] = device.protocol
        encoded_device['serial'] = device.serial_number
        encoded_device['meta']['version'] = device.version
        encoded_device['manufacturer'] = device.manufacturer
        encoded_device['communication'] = device.communication
        encoded_device['description'] = device.description

        for value in device.value_list:
            encoded_value = self.encode_value(value)
            encoded_device['value'].append(encoded_value)
        self.wapp_log.debug("Device JSON: {}".format(encoded_device))

        return encoded_device

    def encode_value(self, value):
        """
        Encode instance of Value class.

        Handles the encodoing of the value instance, contains a template to
        encode the value with.

        Args:
            value: Reference to the instance of the Value class.

        Returns:
            The encoded JSON result.

        """
        encoded_value = {
            "meta": {
                "type": "value",
                "version": "2.0",
                "id": ""
            },
            "name": "",
            "permission": "",
            "type": ""
        }

        encoded_value['meta']['id'] = value.uuid
        encoded_value['name'] = value.name
        encoded_value['type'] = value.type_of_value
        encoded_value['permission'] = value.permission

        if value.data_type == 'string':
            encoded_value.update({"string": {}, "state": []})
            if (value.string_encoding is not None
                    and value.string_max is not None):
                encoded_value['string'].update({"encoding": "", "max": "1"})
                encoded_value['string']['encoding'] = value.string_encoding
                encoded_value['string']['max'] = value.string_max
            # TODO (Dimitar): Remove later if unneeded
            # MAY BE NEEDED, LEAVING HERE FOR NOW
            # elif value.string_max is None:
            #     encoded_value['string'].update({"encoding": ""})
            #     encoded_value['string']['encoding'] = value.string_encoding
            # elif value.string_encoding is None:
            #     encoded_value['string'].update({"max": ""})
            #     encoded_value['string']['max'] = value.string_max
        elif value.data_type == 'blob':
            encoded_value.update({"blob": {}, "state": []})
            if value.blob_encoding is not None and value.blob_max is not None:
                encoded_value['blob'].update({"encoding": "", "max": "1"})
                encoded_value['blob']['encoding'] = value.blob_encoding
                encoded_value['blob']['max'] = value.blob_max
            # TODO (Dimitar): Remove later if unneeded
            # MAY BE NEEDED, LEAVING HERE FOR NOW
            # elif value.blob_max is None:
            #     encoded_value['blob'].update({"encoding": ""})
            #     encoded_value['blob']['encoding'] = value.blob_encoding
            # elif value.blob_encoding is None:
            #     encoded_value['blob'].update({"max": ""})
            #     encoded_value['blob']['max'] = value.blob_max
        elif value.data_type == 'number':
            encoded_value.update({"number": {}, "state": []})
            if (
                value.number_min is not None
                and value.number_max is not None
                and value.number_step is not None
                and value.number_unit is not None
            ):
                encoded_value.update({
                    'number': {
                        "min": "",
                        "max": "1",
                        "step": "",
                        "unit": ""
                    },
                    "state": []
                })
                encoded_value['number']['unit'] = value.number_unit

            # TODO (Dimitar): Remove later if unneeded
            # MAY BE NEEDED, LEAVING HERE FOR NOW
            # else:
            #     encoded_value.update({
            #         'number': {
            #             "min": "",
            #             "max": "1",
            #             "step": ""
            #         },
            #         "state": []
            #     })
            encoded_value['number']['min'] = value.number_min
            encoded_value['number']['max'] = value.number_max
            encoded_value['number']['step'] = value.number_step

        encoded_state = None
        if value.report_state:
            encoded_state = self.encode_state(
                value.report_state,
                value.init_value
            )
            encoded_value['state'].append(encoded_state)
        if value.control_state:
            encoded_state = self.encode_state(
                value.control_state,
                value.init_value
            )
            encoded_value['state'].append(encoded_state)
        self.wapp_log.debug("Value JSON: {}".format(encoded_value))

        return encoded_value

    def encode_state(self, state, init_value):
        """
        Encode instance of State class.

        Handles the encodoing of the value instance, contains a template to
        encode the value with.

        Args:
            state: Reference to the instance of the State class.
            init_value: The data in the State.

        Returns:
            The encoded JSON result.

        """
        encoded_state = {
            "meta": {
                "type": "state",
                "version": "2.0",
                "id": "",
                "contract": []
            },
            "data": "",
            "type": "",
            "timestamp": ""
        }
        encoded_state['meta']['id'] = state.uuid
        encoded_state['data'] = init_value
        encoded_state['type'] = state.state_type
        encoded_state['timestamp'] = state.timestamp
        self.wapp_log.debug("State JSON: {}".format(encoded_state))

        return encoded_state
