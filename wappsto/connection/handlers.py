"""
Receive and send handling module.

Handles building sending and receiving data messages and adding them to the
sending queue.
"""
import random
import logging
from . import send_data


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
    trace = send_data.SendData(
        send_data.SEND_TRACE,
        parent=parent,
        trace_id=trace_id,
        data=data,
        text="ok",
        control_value_id=control_value_id)
    sending_queue.put(trace)


def send_report(
        incoming_value,
        sending_queue,
        network,
        device,
        value,
        state,
        trace_id=None):
    """
    Send a report message to the server.

    Sends a report message to the server containing data about the state of the
    specific value in a specific device. Puts a report message into
    sending_queue.

    Args:
        incoming_value: Value received from the server.
        sending_queue: The queue requests are being added to.
        network: Network the device is on.
        device: Device the value is on.
        value: Value the state belongs to.
        state: State of the device.
        trace_id: Trace ID used to create a URL for debugging (default: {None})

    """
    report = send_data.SendData(
        send_data.SEND_REPORT,
        data=str(incoming_value),
        network_id=network.uuid,
        device_id=device.uuid,
        value_id=value.uuid,
        state_id=state.uuid,
        trace_id=trace_id
    )
    sending_queue.put(report)


def get_control(incoming_value, network, device, value, state, trace_id=None):
    """
    Send a control message to the server.

    Sends a control message to the server containing data about a change in the
    state of the value of the specific device.

    Args:
        incoming_value: Value received from the server.
        network: Network the device is on.
        device: Device the value is on.
        value: Value the state belongs to.
        state: State of the device.
        trace_id: Trace ID used to create a URL for debugging.
            (default: {None})

    Returns:
        The result of the control request.

    """
    control = send_data.SendData(
        send_data.SEND_CONTROL,
        data=str(incoming_value),
        network_id=network.uuid,
        device_id=device.uuid,
        value_id=value.uuid,
        state_id=state.uuid,
        trace_id=trace_id
    )
    return control


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
            network_n = self.instance.network_cl.name
            random_int = random.randint(1, 25000)
            random_id = "{}".format(network_n + random_int)
        for device in self.instance.device_list:
            for value in device.value_list:
                if value.control_state is not None:
                    if value.control_state.uuid == control_id:
                        if value.send_control(data_value=incoming_value):
                            send_trace(
                                sending_queue,
                                value.uuid,
                                trace_id,
                                incoming_value,
                                control_value_id=random_id
                            )
                            control = get_control(
                                incoming_value,
                                self.instance.network_cl,
                                device,
                                value,
                                value.control_state,
                                random_id
                            )
                            sending_queue.put(control)
                            return True
                        else:
                            return False
                else:
                    self.wapp_log.warning("Value is read only.")

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
            random_int = str(random.randint(1, 25000))
            network_name = self.instance.network_cl.name

            random_id = "{}{}".format(network_name, random_int)

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
                        value.last_update_of_report = value.get_now()
                        send_report(
                            current_value,
                            sending_queue,
                            self.instance.network_cl,
                            device,
                            value,
                            value.report_state,
                            random_id
                        )
                        if value.callback is not None:
                            value.callback(value, 'report')
                        return True
                    else:
                        self.wapp_log.warning("Value ID mismatch.")
                else:
                    self.wapp_log.warning("Value is write only.")

        self.wapp_log.warning("Unhandled get {}".format(report_id))
        return False
