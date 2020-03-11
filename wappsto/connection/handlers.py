"""
Receive and send handling module.

Handles building sending and receiving data messages and adding them to the
sending queue.
"""
import random
import logging
from . import message_data


def send_trace(sending_queue, parent, trace_id, data, control_value_id=None):
    """
    Add a trace to the sending queue.

    Adds a trace URL to the sending queue for debugging purposes.

    Args:
        sending_queue: The queue requests are being added to.
        parent: Owner of the trace URL.
        trace_id: ID of the trace message.
        data: Trace message data.
        control_value_id: ID of the control state of the value
            (default: {None})

    """
    if trace_id:
        trace = message_data.MessageData(
            message_data.SEND_TRACE,
            parent=parent,
            trace_id=trace_id,
            data=data,
            text="ok",
            control_value_id=control_value_id)
        sending_queue.put(trace)


class Handlers:
    """
    Message data handlers.

    Processes incoming and outgoing PUT, POST and GET messages.
    """

    def __init__(self, data_manager):#
        """
        Initialize the Handler class.

        Create an instance of the Handlers class to handle incoming and
        outgoing communication with the server.

        Args:
            instance: Reference to the object instance class.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.data_manager = data_manager

    def __get_random_id(self):
        network_n = self.data_manager.network.name
        random_int = random.randint(1, 25000)
        return "{}{}".format(network_n, random_int)

    def handle_incoming_put(
            self,
            control_id,
            incoming_value,
            sending_queue,
            trace_id
    ):
        """
        Process an incoming PUT request.

        Handles an incoming PUT request and changes the specific value to
        the incoming value.

        Args:
            control_id: UUID of the Control state.
            incoming_value: Value received from the server.
            sending_queue: The queue requests are being added to.
            trace_id: Trace ID used to create a URL for debugging.
                (default: {None})

        Returns:
            True when successfully handling the request, False otherwise.

        """
        object = self.get_by_id(control_id)
        try:
            if object.parent.control_state == object:
                if object.parent.handle_control(data_value=incoming_value):
                    if trace_id:
                        send_trace(
                            sending_queue,
                            object.parent.uuid,
                            trace_id,
                            incoming_value,
                            control_value_id=self.__get_random_id()
                        )
                    return True
                else:
                    return False
        except AttributeError:
            pass

        msg = "Unhandled put {} : {}".format(control_id, incoming_value)
        self.wapp_log.warning(msg)
        return False

    def handle_incoming_get(self, id, sending_queue, trace_id):
        """
        Process an incoming GET request.

        Handles an incoming GET request and sends the current value to the
        server.

        Args:
            id: UUID of the Report state.
            sending_queue: The queue requests are being added to.
            trace_id: Trace ID used to create a URL for debugging.
                (default: {None})


        Returns:
            True when successfully handling the request, False otherwise.

        """
        object = self.get_by_id(id)
        try:
            if object.parent.report_state == object:
                if trace_id:
                    send_trace(
                        sending_queue,
                        object.parent.uuid,
                        trace_id,
                        object.data,
                        control_value_id=self.__get_random_id()
                    )
                object.parent.handle_refresh()
                return True
        except AttributeError:
            pass

        self.wapp_log.warning("Unhandled get for {}".format(id))
        return False

    def handle_incoming_delete(self, id, sending_queue, trace_id):
        """
        Handle incoming request to delete.

        Deals with requests to delete network/device/value/state, depending on
        the information provided in arguments.

        Args:
            id: ID of element to perform delete action to.
            sending_queue: Reference to queue where alements to be sent are
            saved.
            trace_id: ID used for tracing the performed actions.

        Returns:
            True or False, depending on the result received during execution.

        """
        object = self.get_by_id(id)
        try:
            if object is not None:
                if trace_id:
                    send_trace(
                        sending_queue,
                        id,
                        trace_id,
                        None,
                        control_value_id=self.__get_random_id()
                    )
                return object.handle_delete()
        except AttributeError:
            pass

        self.wapp_log.warning("Unhandled delete for {}".format(id))
        return False

    def get_by_id(self, id):
        """
        Wappsto get by id.

        Retrieves the instance of a class if its id matches the provided one

        Args:
            id: unique identifier used for searching

        Returns:
            A reference to the network/device/value/state object instance.

        """
        message = "Found instance of {} object with id: {}"
        if self.data_manager.network is not None:
            if self.data_manager.network.uuid == id:
                self.wapp_log.debug(message.format("network", id))
                return self.data_manager.network

            for device in self.data_manager.network.devices:
                if device.uuid == id:
                    self.wapp_log.debug(message.format("device", id))
                    return device

                for value in device.values:
                    if value.uuid == id:
                        self.wapp_log.debug(message.format("value", id))
                        return value

                    if value.control_state is not None and value.control_state.uuid == id:
                        self.wapp_log.debug(message.format("control state", id))
                        return value.control_state

                    if value.report_state is not None and value.report_state.uuid == id:
                        self.wapp_log.debug(message.format("report state", id))
                        return value.report_state

        self.wapp_log.warning("Failed to find object with id: {}".format(id))
