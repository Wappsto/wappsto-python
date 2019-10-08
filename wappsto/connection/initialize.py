"""
The object instance initialization module.

Stores the initialization functionality for the object instances of the
network, devices, values and states.
"""
import logging


class Initialize:
    """
    The initialize class handles initializing object instances.

    Using references to the RPC, socket and object instances, it sends
    activation messages to the server and enables sending/receiving for the
    network, device, value and state instances.
    """

    def __init__(self, rpc):
        """
        Create an initialization instance.

        The initialize instance contains the initialize_all method that is used
        to activate the object instances so that they can send/receive to the
        server.

        Args:
            rpc: Reference to the RPC instance.

        """
        self.rpc = rpc

    def initialize_all(self, conn, instance):
        """
        Initialize all of the devices on the sending and receiving queue.

        Adds all the devices to the send receive queue by pinging the server
        with their information in order to initialize them.

        Args:
            conn: A reference to the socket instance.
            instance: A reference to the network and device instances.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.network_UUID = instance.network_cl.uuid
        self.network_name = instance.network_cl.name

        # Adds the network to the queue.
        self.rpc.add_network(conn, self.network_UUID, self.network_name)
        msg = "Network {} added to Sending queue {}.".format(
            self.network_name,
            self.rpc
        )
        # All of the debug logs may need relocation to the RPC class.
        self.wapp_log.debug(msg)

        for device in instance.device_list:

            self.device_uuid = device.uuid
            self.device_name = device.name
            self.device_manufacturer = device.manufacturer
            self.device_product = device.product
            self.device_version = device.version
            self.device_serial_number = device.serial_number
            self.device_description = device.description
            self.device_protocol = device.protocol
            self.device_communication = device.communication

            # Passes the attributes of the device to the queue add method.
            self.rpc.add_device(
                conn,
                self.network_UUID,
                self.device_uuid,
                self.device_name,
                self.device_manufacturer,
                self.device_product,
                self.device_version,
                self.device_serial_number,
                self.device_description,
                self.device_protocol,
                self.device_communication,
                "1"
            )

            msg = "Device {} added to sending queue {}".format(
                self.device_name,
                self.rpc
            )
            self.wapp_log.debug(msg)

            for value in device.value_list:

                self.value_uuid = value.uuid
                self.value_name = value.name
                self.value_type_of_value = value.type_of_value
                self.value_data_type = value.data_type
                self.value_permission = value.permission
                self.value_init_value = value.init_value or ""
                self.value_blob_encoding = value.blob_encoding
                self.value_blob_max = value.blob_max
                self.value_string_encoding = value.string_encoding
                self.value_string_max = value.string_max
                self.value_number_max = value.number_max
                self.value_number_min = value.number_min
                self.value_number_step = value.number_step
                self.value_number_unit = value.number_unit

                # Passes the attributes of the value to the queue add method.
                # Checks the type of method to determine which variables.
                if self.value_data_type == 'blob':
                    self.rpc.add_value_blob(
                        conn,
                        self.network_UUID,
                        self.device_uuid,
                        self.value_uuid,
                        self.value_name,
                        self.value_type_of_value,
                        self.value_permission,
                        self.value_blob_max,
                        self.value_blob_encoding,
                        "",
                        ""
                    )
                    msg = self.create_message()
                    self.wapp_log.debug(msg)

                elif self.value_data_type == 'string':
                    self.rpc.add_value_string(
                        conn,
                        self.network_UUID,
                        self.device_uuid,
                        self.value_uuid,
                        self.value_name,
                        self.value_type_of_value,
                        self.value_permission,
                        self.value_string_max,
                        self.value_string_encoding,
                        "",
                        ""
                    )

                    msg = self.create_message()
                    self.wapp_log.debug(msg)

                elif self.value_data_type == 'number':
                    self.rpc.add_value_number(
                        conn,
                        self.network_UUID,
                        self.device_uuid,
                        self.value_uuid,
                        self.value_name,
                        self.value_type_of_value,
                        self.value_permission,
                        self.value_number_max,
                        self.value_number_min,
                        self.value_number_step,
                        "",
                        "",
                        self.value_number_unit
                    )

                    msg = self.create_message()
                    self.wapp_log.debug(msg)

                # Adds the states to the respective control or report queues.

                if value.report_state is not None:
                    self.state_type = value.report_state.state_type
                    self.state_uuid = value.report_state.uuid
                    self.rpc.add_state_report(
                        conn,
                        self.value_init_value,
                        self.network_UUID,
                        self.device_uuid,
                        self.value_uuid,
                        self.state_uuid
                    )

                if value.control_state is not None:
                    self.state_type = value.control_state.state_type
                    self.state_uuid = value.control_state.uuid
                    data = self.rpc.get_state_control(
                        conn,
                        self.value_init_value,
                        self.network_UUID,
                        self.device_uuid,
                        self.value_uuid,
                        self.state_uuid
                    )

                    if value.control_state.uuid in str(data):
                        self.rpc.add_state_control(
                            conn,
                            self.value_init_value,
                            self.network_UUID,
                            self.device_uuid,
                            self.value_uuid,
                            self.state_uuid
                        )

    def create_message(self):
        """
        Create a message.

        Returns a message informing about adding a value to a sending queue

        Returns:
            Formatted string message

        """
        return "Value ({}) {} added to sending queue {}.".format(
            self.value_data_type,
            self.value_name,
            self.rpc
        )
