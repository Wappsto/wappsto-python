"""
The value module.

Stores attributes for the value instance and handles value-related
methods.
"""
import logging
import threading
import warnings

from ..connection import message_data
from ..connection import seluxit_rpc
from ..errors import wappsto_errors


def isNaN(num):
    return num != num


class Value:
    """
    Value instance.

    Stores attributes for the value instance and handles value-related
    methods.
    """

    def __init__(
        self,
        parent,
        uuid,
        name,
        type_of_value,
        data_type,
        permission,
        number_max,
        number_min,
        number_step,
        number_unit,
        string_encoding,
        string_max,
        blob_encoding,
        blob_max,
        period,
        delta
    ):
        """
        Initialize the Value class.

        Initializes an object of value class by passing required parameters.

        Args:
            parent: Reference to a device object
            uuid: An unique identifier of a device
            name: A name of a device
            type_of_value: Determines a type of value [e.g temperature, CO2]
            data_type: Defines whether a value is string, blob or number
            permission: Defines permission [read, write, read and write]
            (if data_type is number then these parameters are relevant):
            number_max: Maximum number a value can have
            number_min: Minimum number a value can have
            number_step: Number defining a step
            number_unit: Unit in which a value should be read
            (if data_type is string then these parameters are irrelevant):
            string_encoding: A string encoding of a value
            string_max: Maximum length of string
            (if data_type is blob then these parameters are irrelevant):
            blob_encoding: A blob encoding of a value
            blob_max: Maximum length of a blob

            period: defines the time after which a value should send report
                message. Default: {None})
            delta: defines the a difference of value (default: {None})

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent = parent
        self.uuid = uuid
        self.name = name
        self.type_of_value = type_of_value
        self.data_type = data_type
        self.permission = permission
        # The value shared between state instances.
        self.number_max = number_max
        self.number_min = number_min
        self.number_step = number_step
        self.number_unit = number_unit
        self.string_encoding = string_encoding
        self.string_max = string_max
        self.blob_encoding = blob_encoding
        self.blob_max = blob_max
        self.report_state = None
        self.control_state = None
        self.callback = None

        self.timer = threading.Timer(None, None)
        self.last_update_of_report = None

        # if self._invalid_step(self.number_max):
        #     msg = "Inconsistent max, min & step provided. "
        #     msg += "'(max-min)/step' do not appear to an integer-like."
        #     self.wapp_log.warning(msg)

        if period:
            self.set_period(period)
        if delta:
            self.set_delta(delta)

        msg = "Value {} debug: {}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

    def __getattr__(self, attr):  # pragma: no cover
        """
        Get attribute value.

        When trying to get value from last_controlled warning is raised about
        it being deprecated and calls get_data instead.

        Returns:
            value of get_data

        """
        if attr in ["last_controlled"]:
            warnings.warn("Property {} is deprecated".format(attr))
            return self.get_control_state().data

    def set_period(self, period):
        """
        Set the value reporting period.

        Sets the time defined in second to report a value to
        the server and starts timer.

        Args:
            period: Reporting period.

        """
        if period is None:
            self.wapp_log.warning("Period value is not provided.")
            return

        try:
            period = int(period)
        except ValueError:
            self.wapp_log.error("Period value must be a number.")
            return

        if period < 0:
            self.wapp_log.warning("Period value must not be lower then 0.")
            return

        self.period = period

    def enable_period(self):
        """
        Enable the Period handling if period was set.

        Enable the Period starts the timer that ensures that the
        value are getting updated with the right Periods.
        """
        if self.period is None:
            self.wapp_log.debug("Period was not set.")
            return
        if self.get_report_state() is not None:
            self.__set_timer()
            self.wapp_log.debug("Period successfully set.")
        else:
            self.wapp_log.warning("Cannot set the period for this value.")

    def __set_timer(self):
        """
        Set timer.

        Stop previous timer and sets new one if period value is not None.

        """
        self.timer.cancel()
        if self.period is not None:
            self.timer_elapsed = False
            self.timer = threading.Timer(self.period, self.__timer_done)
            self.timer.start()

    def __timer_done(self):
        self.__set_timer()
        self.timer_elapsed = True
        self.handle_refresh()

    def set_delta(self, delta):
        """
        Set the delta to report between.

        Sets the delta (range) of change to report in. When a change happens
        in the range of this delta it will be reported.

        Args:
            delta: Range to report between.

        """
        if delta is None:
            self.wapp_log.warning("Delta value is not provided.")
            return

        try:
            delta = float(delta)
        except ValueError:
            self.wapp_log.error("Delta value must be a number")
            return

        if delta < 0:
            self.wapp_log.warning("Delta value must not be lower then 0.")
            return

        if self.__is_number_type():
            self.delta = delta

    def enable_delta(self):
        """
        Enable the Delta handling, if delta is set.

        Enable the Delta, ATM do not do anything, other the inform
        if delta will be able to work.
        """
        if self.delta is None:
            self.wapp_log.debug("Delta was not set.")
            return
        if self.get_report_state():
            self.wapp_log.debug("Delta successfully set.")
        else:
            self.wapp_log.warning("Cannot set the delta for this value.")

    def get_parent_device(self):  # pragma: no cover
        """
        Retrieve parent device reference.

        Gets a reference to the device that owns this device.

        Returns:
            Reference to instance of Device class that owns this Value.

        """
        return self.parent

    def add_report_state(self, state):
        """
        Set report state reference to the value list.

        Adds a report state reference to the Value class.

        Args:
            state: Reference to instance of State class.

        """
        self.report_state = state
        msg = "Report state {} has been added.".format(state.parent.name)
        self.enable_period()
        self.enable_delta()
        self.wapp_log.debug(msg)

    def add_control_state(self, state):
        """
        Set control state reference to the value list.

        Adds a control state reference to the Value class.

        Args:
            state: Reference to instance of State class.

        """
        self.control_state = state
        msg = "Control state {} has been added".format(state.parent.name)
        self.wapp_log.debug(msg)

    def get_report_state(self):
        """
        Retrieve child report state reference.

        Gets a reference to the child State class.

        Returns:
            Reference to instance of State class.

        """
        if self.report_state is not None:
            return self.report_state

        msg = "Value {} has no report state.".format(self.name)
        self.wapp_log.warning(msg)

    def get_control_state(self):
        """
        Retrieve child control state reference.

        Gets a reference to the child State class.

        Returns:
            Reference to instance of State class.

        """
        if self.control_state is not None:
            return self.control_state

        msg = "Value {} has no control state.".format(self.name)
        self.wapp_log.warning(msg)

    def set_callback(self, callback):
        """
        Set the callback.

        Sets the callback attribute.

        Args:
            callback: Callback reference.

        Raises:
            CallbackNotCallableException: Custom exception to signify invalid
            callback.

        """
        if not callable(callback):
            msg = "Callback method should be a method"
            self.wapp_log.error("Error setting callback: {}".format(msg))
            raise wappsto_errors.CallbackNotCallableException
        self.callback = callback
        self.wapp_log.debug("Callback {} has been set.".format(callback))
        return True

    def _validate_value_data(self, data_value, err_msg=None):
        # TODO(MBK): Need refactoring, so it also nicely can be used for control validation, in 'receive_Data/incoming_put'
        if err_msg is None:
            err_msg = []
        if self.__is_number_type():
            try:
                if self._outside_range(data_value):
                    msg = "Invalid number. Range: {}-{}. Yours is: {}".format(
                        self.number_min,
                        self.number_max,
                        data_value
                    )
                    err_msg.append(msg)
                    self.wapp_log.warning(msg)
                if self._invalid_step(data_value):
                    msg = "Invalid Step. Step: {}. Min: {}. Value: {}".format(
                        self.number_step,
                        self.number_min,
                        data_value
                    )
                    err_msg.append(msg)
                    self.wapp_log.warning(msg)
                return str(data_value)
            except ValueError:
                msg = "Invalid type of value. Must be a number: {}"
                msg = msg.format(data_value)
                err_msg.append(msg)
                self.wapp_log.error(msg)
                return "NA"

        elif self.__is_string_type():
            if self.string_max is None:
                return data_value

            if len(str(data_value)) <= int(self.string_max):
                return data_value

            msg = "Value for '{}' not in correct range: {}."
            msg = msg.format(self.name, self.string_max)
            err_msg.append(msg)
            self.wapp_log.warning(msg)

        elif self.__is_blob_type():
            if self.blob_max is None:
                return data_value

            if len(str(data_value)) <= int(self.blob_max):
                return data_value

            msg = "Value for '{}' not in correct range: {}."
            msg = msg.format(self.name, self.blob_max)
            err_msg.append(msg)
            self.wapp_log.warning(msg)

        else:
            msg = "Value type '{}' is invalid".format(self.date_type)
            err_msg.append(msg)
            self.wapp_log.error(msg)

    def _outside_range(self, value):
        """
        Check weather or not the value are outside range.

        Args:
            value: The value to be checked.

        Returns:
            True, if outside range.
            False if inside range.
        """
        return not (self.number_min <= float(value) <= self.number_max)

    def _invalid_step(self, value):
        """
        Check weather or not the value are invalid step size.

        Args:
            value: The value to be checked.

        Returns:
            True, if invalid step size.
            False if valid step size.
        """
        x = (float(value)-self.number_min)/self.number_step
        return not (abs(round(x) - x) <= 1e-9)

    def update(self, data_value, timestamp=None):
        """
        Update value.

        Check if value has a state and validates the information in data_value
        if both of these checks pass then method send_state is called.

        Args:
            data_value: the new value.
            timestamp: time of action.

        Returns:
            True/False indicating the result of operation.

        """
        self._update_delta_period_values(data_value)

        if timestamp is None:
            timestamp = seluxit_rpc.time_stamp()

        state = self.get_report_state()
        if state is None:
            self.wapp_log.warning("Value is write only.")
            return False

        self._validate_value_data(data_value)

        state.timestamp = timestamp

        msg = message_data.MessageData(
            message_data.SEND_REPORT,
            data=str(data_value),
            network_id=state.parent.parent.parent.uuid,
            device_id=state.parent.parent.uuid,
            value_id=state.parent.uuid,
            state_id=state.uuid,
            verb=message_data.PUT
        )
        # self.parent.parent.conn.send_data.send_report(msg)
        self.parent.parent.conn.sending_queue.put(msg)

    def _update_delta_period_values(self, data_value):
        if self.period is not None:
            self.__set_timer()
        if self.delta is not None:
            try:
                self.last_update_of_report = float(data_value)
            except ValueError:
                self.last_update_of_report = float("NAN")

    def check_delta_and_period(self, data_value):
        """
        Check if delta and period allows data to be sent.

        Check if value has delta or period, if it has then if it passes
        checks then True is returned, otherwise False is returned.

        Args:
            data_value: the new value.

        Returns:
            True/False indicating the result of operation.

        """
        if self.delta is not None:
            try:
                if isNaN(data_value):
                    raise ValueError("Value is NAN!")
                data_value = float(data_value)
            except ValueError:
                if not isNaN(self.last_update_of_report):
                    return True
                return self.check_period(False)

            if (self.last_update_of_report is None or
               not (abs(data_value - self.last_update_of_report) < self.delta)):
                return True

        return self.check_period(False)

    def check_period(self, return_value):
        """
        Check if period allows data to be sent.

        Check if value has period, if it has then if it passes
        checks then True is returned, otherwise False is returned.

        Args:
            return_value: default return value.

        Returns:
            True/False indicating the result of operation.

        """
        if self.period is not None:
            return self.timer_elapsed
        return return_value

    def get_data(self):
        """
        Get value from report state.

        Check if value has a report state if it has return its data else return
        None.

        Returns:
            Value of report state.

        """
        state = self.get_report_state()
        if state is None:
            return None

        return state.data

    def handle_refresh(self):
        """
        Handles the refresh request.

        Calls __call_callback method with input of 'refresh'

        Returns:
            results of __call_callback

        """
        self.__call_callback('refresh')

    def handle_delete(self):
        """
        Handle delete.

        Calls the __call_callback method with initial input of "remove".

        Returns:
            result of __call_callback method.

        """
        self.__call_callback('remove')

    def delete(self):
        """
        Delete this object.

        Sends delete request for this object and removes its reference
        from parent.

        """
        message = message_data.MessageData(
            message_data.SEND_DELETE,
            network_id=self.parent.parent.uuid,
            device_id=self.parent.uuid,
            value_id=self.uuid
        )
        self.parent.parent.conn.sending_queue.put(message)
        self.parent.values.remove(self)
        self.wapp_log.info("Value removed")

    def __call_callback(self, event):
        if self.callback is not None:
            self.callback(self, event)

    def handle_control(self, data_value):
        """
        Handles the control request.

        Sets data value of control_state object, with value provided and calls
        __call_callback method with input of 'set'.

        Args:
            data_value: the new value.

        Returns:
            results of __call_callback

        """
        # TODO(MBK): Check if the value are within range, and with right step.
        self.control_state.data = data_value

        return self.__call_callback('set')

    def __is_number_type(self):
        """
        Validate data type.

        Checks whether the type of the value is number.

        Returns:
        True if the type is number otherwise false.
        boolean

        """
        return self.data_type == "number"

    def __is_string_type(self):
        """
        Validate data type.

        Checks whether the type of the value is string.

        Returns:
        True if the type is string otherwise false.
        boolean

        """
        return self.data_type == "string"

    def __is_blob_type(self):
        """
        Validate data type.

        Checks whether the type of the value is blob.

        Returns:
        True if the type is blob otherwise false.
        boolean

        """
        return self.data_type == "blob"
