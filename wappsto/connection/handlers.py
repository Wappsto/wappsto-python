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

    def __init__(self, instance):
        """
        Initialize the Handler class.

        Create an instance of the Handlers class to handle incoming and
        outgoing communication with the server.

        Args:
            instance: Reference to the object instance class.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.instance = instance

    def __get_random_id(self):
        network_n = self.instance.network_cl.name
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
        random_id = None
        if trace_id:
            random_id = self.__get_random_id()

        for device in self.instance.device_list:
            for value in device.value_list:
                if value.control_state is not None:
                    if value.control_state.uuid == control_id:
                        if value.handle_control(data_value=incoming_value):
                            send_trace(
                                sending_queue,
                                value.uuid,
                                trace_id,
                                incoming_value,
                                control_value_id=random_id
                            )
                            return True
                        else:
                            return False

        msg = "Unhandled put {} : {}".format(control_id, incoming_value)
        self.wapp_log.warning(msg)
        return False

    def handle_incoming_get(self, report_id, sending_queue, trace_id):
        """
        Process an incoming GET request.

        Handles an incoming GET request and sends the current value to the
        server.

        Args:
            report_id: UUID of the Report state.
            sending_queue: The queue requests are being added to.
            trace_id: Trace ID used to create a URL for debugging.
                (default: {None})


        Returns:
            True when successfully handling the request, False otherwise.

        """
        random_id = None
        if trace_id:
            random_id = self.__get_random_id()

        for device in self.instance.device_list:
            for value in device.value_list:
                if value.report_state is not None:
                    if report_id.endswith(value.report_state.uuid):
                        current_value = value.data_value
                        send_trace(
                            sending_queue,
                            value.uuid,
                            trace_id,
                            current_value,
                            control_value_id=random_id
                        )
                        # value.last_update_of_report = value.get_now()
                        value.handle_refresh()
                        return True

        self.wapp_log.warning("Unhandled get {}".format(report_id))
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
        random_id = None
        if trace_id:
            random_id = self.__get_random_id()

            send_trace(
                sending_queue,
                id,
                trace_id,
                None,
                control_value_id=random_id
            )

        if True or self.instance.network_cl.uuid == id:
            return self.instance.network_cl.handle_delete()

        for device in self.instance.device_list:
            if device.uuid == id:
                try:
                    return device.handle_delete()
                except AttributeError:
                    self.wapp_log.warning("Unhandled device delete for {}"
                                          .format(id))
                    return False
            for value in device.value_list:
                if value.uuid == id:
                    try:
                        return value.handle_delete()
                    except AttributeError:
                        self.wapp_log.warning("Unhandled value delete for {}"
                                              .format(id))
                        return False
                for state in value.state_list:
                    if state.uuid == id:
                        try:
                            return state.handle_delete()
                        except AttributeError:
                            msg = "Unhandled state delete for {}".format(id)
                            self.wapp_log.warning(msg)
                            return False

        self.wapp_log.warning("Unhandled delete {}".format(id))
        return False
