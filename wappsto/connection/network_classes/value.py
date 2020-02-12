"""
The value module.

Stores attributes for the value instance and handles value-related
methods.
"""
import logging
import time
import datetime
import decimal
import re
from math import fabs
from .errors import wappsto_errors


class Value:
    """
    Value instance.

    Stores attributes for the value instance and handles value-related
    methods.
    """

    def __init__(
        self,
        parent_device,
        uuid,
        name,
        type_of_value,
        data_type,
        permission,
        init_value,
        number_max,
        number_min,
        number_step,
        number_unit,
        string_encoding,
        string_max,
        blob_encoding,
        blob_max,
        period=None,
        delta=None
    ):
        """
        Initialize the Value class.

        Initializes an object of value class by passing required parameters.

        Args:
            parent_device: Reference to a device object
            uuid: An unique identifier of a device
            name: A name of a device
            type_of_value: Determines a type of value [e.g temperature, CO2]
            data_type: Defines whether a value is string, blob or number
            permission: Defines permission [read, write, read and write]
            init_value: Initial value after creation of an object
            (if data_type is number then these parameters are relevant):
            number_max: Maximum number a value can have
            number_min: Minimum number a value can have
            number_step: Number defining a step
            number_unit: Unit in which a value should be read
            (if data_type is string then these parameters are relevant):
            string_encoding: A string encoding of a value
            string_max: Maximum length of string
            (if data_type is blob then these parameters are relevant):
            blob_encoding: A blob encoding of a value
            blob_max: Maximum length of a blob

            period: defines the time after which a value should send report
                message. Default: {None})
            delta: defines the a difference of value (default: {None})

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())
        self.parent_device = parent_device
        self.uuid = uuid
        self.name = name
        self.type_of_value = type_of_value
        self.data_type = data_type
        self.permission = permission
        # The value shared between state instances.
        self.init_value = init_value
        self.number_max = number_max
        self.number_min = number_min
        self.number_step = number_step
        self.number_unit = number_unit
        self.string_encoding = string_encoding
        self.string_max = string_max
        self.blob_encoding = blob_encoding
        self.blob_max = blob_max
        self.period = period
        self.delta = delta
        self.report_state = None
        self.control_state = None
        self.callback = self.__callback_not_set
        self.last_update_of_report = self.get_now()
        self.rpc = None
        self.conn = None
        self.reporting_thread = None
        self.last_update_of_control = None
        self.data_value = init_value
        self.difference = 0
        self.delta_report = 0
        self.last_controlled = self.data_value
        self.parent_network_id = parent_device.get_parent_network().uuid
        self.parent_device_id = parent_device.uuid
        self.state_list = []

        msg = "Value {} debug: {}".format(name, str(self.__dict__))
        self.wapp_log.debug(msg)

    def set_period(self, period):
        """
        Set the value reporting period.

        Sets the period to report a value to the server and starts a thread to
        do so.

        Args:
            period: Reporting period.

        """
        try:
            if self.get_report_state() is not None and int(period) > 0:
                self.period = period

            else:
                self.wapp_log.warning("Cannot set the period for this value.")
        except ValueError:
            self.wapp_log.error("Period value must be a number.")

    def set_delta(self, delta):
        """
        Set the delta to report between.

        Sets the delta (range) of change to report in. When a change happens
        in the range of this delta it will be reported.

        Args:
            delta: Range to report between.

        """
        try:
            if (self.__is_number_type()
                    and self.get_report_state()
                    and float(delta) > 0):
                self.delta = delta
            else:
                self.wapp_log.warning("Cannot set the delta for this value.")
        except ValueError:
            self.wapp_log.error("Delta value must be a number")

    def __callback_not_set(self, value, type):
        """
        Message about no callback being set.

        Temporary method to signify that there is no callback set for the
        class.

        Returns:
            "Callback not set" message.

        """
        msg = "Callback for value {} was not set".format(self.name)
        return self.wapp_log.debug(msg)

    def get_parent_device(self):
        """
        Retrieve parent device reference.

        Gets a reference to the device that owns this device.

        Returns:
            Reference to instance of Device class that owns this Value.

        """
        return self.parent_device

    def add_report_state(self, state):
        """
        Set report state reference to the value list.

        Adds a report state reference to the Value class.

        Args:
            state: Reference to instance of State class.

        """
        self.report_state = state
        self.state_list.append(state)
        msg = "Report state {} has been added.".format(state)
        # self.reporting_thread = threading.Thread(target=
        #                                           self.__send_report_thread)
        # self.reporting_thread.setDaemon(True)
        # self.reporting_thread.start()
        self.wapp_log.debug(msg)

    def add_control_state(self, state):
        """
        Set control state reference to the value list.

        Adds a control state reference to the Value class.

        Args:
            state: Reference to instance of State class.

        """
        self.control_state = state
        self.state_list.append(state)
        msg = "Control state {} has been added".format(state)
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
        else:
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
        else:
            msg = "Value {}  has no control state.".format(self.name)
            self.wapp_log.warning(msg)

    def __send_report_delta(self, state):
        """
        Send report message when delta range reached.

        Sends a report message with the current value when the delta range is
        reached.

        Args:
            state: Reference to the report state

        """
        try:
            result = int(self.difference) >= int(self.delta)
            if result and self.rpc is not None and self.delta_report == 1:
                self.__send_logic(state, "report")
                self.wapp_log.info("Sent report [DELTA].")
                self.delta_report = 0
                return True
        except AttributeError:
            pass

    def get_now(self):
        """
        Retrieve current time.

        Using datetime library returns current time.

        Returns:
            Current time in format [%Y-%m-%dT%H:%M:%S.%fZ].

        """
        return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def __send_report_thread(self):
        """
        Send report message.

        Sends a report message with the current value to the server.
        Unless state exists, runs a while loop. It is determined whether or
        not set flag allowing send report because of delta attribute. If delta
        exists: __send_report_delta method is called. If period exists it is
        checked if the sum of period value and last time the value was
        updated is greater than current time. If it does then a report is sent.
        Method is running on separate thread which after each loop sleeps for
        one second.
        """
        state = self.get_report_state()
        value = self.last_controlled
        if state is not None:
            while True:
                if (self.last_controlled is not None
                        and self.__is_number_type()):
                    value_check = self.last_controlled
                    if value != value_check:
                        self.difference = fabs(int(value) - int(value_check))
                        value = value_check
                        self.delta_report = 1
                if self.delta is not None:
                    self.__send_report_delta(state)
                if self.period is not None:
                    try:
                        last_update_timestamp = self.__date_converter(
                            self.last_update_of_report
                        )
                        now = self.get_now()
                        now_timestamp = self.__date_converter(now)
                        the_time = last_update_timestamp + self.period
                        if the_time <= now_timestamp and self.rpc is not None:
                            self.wapp_log.info("Sending report [PERIOD].")
                            self.__send_logic(state, 'report')
                    except Exception as e:
                        self.reporting_thread.join()
                        self.wapp_log.error(e)
                time.sleep(1)

    def set_callback(self, callback):
        """
        Set the callback.

        Sets the callback attribute. It will be called by the __send_logic
        method.

        Args:
            callback: Callback reference.

        Raises:
            CallbackNotCallableException: Custom exception to signify invalid
            callback.

        """
        try:
            if not callable(callback):
                msg = "Callback method should be a method"
                raise wappsto_errors.CallbackNotCallableException(msg)
            self.callback = callback
            self.wapp_log.debug("Callback {} has been set.".format(callback))
            return True
        except wappsto_errors.CallbackNotCallableException as e:
            self.wapp_log.error("Error setting callback: {}".format(e))
            raise

    def __date_converter(self, date):
        """
        Convert date to timestamp.

        Converts passed date to a timestamp, first removed Z and T charts
        from the date, then using functionality of time and datetime
        libraries, changes the date into timestamp and returns it.

        Args:
            date: string format date

        Returns:
            timestamp
            integer

        """
        date_first = re.sub("Z", "", re.sub("T", " ", date))
        date_format = '%Y-%m-%d %H:%M:%S.%f'
        date_datetime = datetime.datetime.strptime(date_first, date_format)
        return time.mktime(date_datetime.timetuple())

    def __validate_value_data(self, data_value):
        if self.__is_number_type():
            try:
                data_value = self.ensure_number_value_follows_steps(data_value)

                if self.number_min <= data_value <= self.number_max:
                    return str(data_value)
                else:
                    msg = "Invalid number. Range: {}-{}. Your: {}".format(
                        self.number_min,
                        self.number_max,
                        str(data_value)
                    )
                    self.wapp_log.warning(msg)
                    return None
            except ValueError:
                msg = "Invalid type of value. Must be a number: {}".format(
                    str(data_value)
                )
                self.wapp_log.error(msg)
                return None
        elif self.__is_string_type():
            if (self.string_max is None
                    or len(str(data_value)) <= int(self.string_max)):
                return data_value
            else:
                msg = ("Value {} not in correct range for {}"
                       .format(data_value, self.name))
                self.wapp_log.warning(msg)
                return None
        elif self.__is_blob_type():
            if (self.blob_max is None
                    or len(str(data_value)) <= int(self.blob_max)):
                return data_value
            else:
                msg = ("Value {} not in correct range for {}"
                       .format(data_value, self.name))
                self.wapp_log.warning(msg)
                return None
        else:
            msg = ("Value type {} is invalid".format(self.date_type))
            self.wapp_log.error(msg)
            return None

    def ensure_number_value_follows_steps(self, data_value):
        """
        Ensure number value follows steps.

        Converts values to decimal and ensures number step is always positive,
        ensures that data value follows steps and removes exes 0's after
        decimal point.

        Args:
            data_value: float value indicating current state of value.

        Returns:
            data_value

        """
        data_value = decimal.Decimal(str(data_value))
        number_step = abs(decimal.Decimal(str(self.number_step)))

        result = (data_value % number_step)
        if result < 0:
            result += number_step
        data_value = data_value - result

        data_value = str(data_value)
        data_value = (data_value.rstrip('0').rstrip('.')
                      if '.' in data_value else data_value)

        return decimal.Decimal(data_value)

    def update(self, data_value, timestamp=None):
        """
        Update value.

        Check if value has a state and validates the information in data_value
        if both of these checks pass then method __send_logic is called.

        Args:
            data_value: the new value.
            timestamp: time of action.

        Returns:
            True/False indicating the result of operation.

        """
        state = self.get_report_state()
        if state is None:
            self.wapp_log.warning("Value is write only.")
            return False

        data_value = self.__validate_value_data(data_value)
        if not data_value:
            return False

        return self.__send_logic(
            state,
            'report',
            data_value=data_value,
            timestamp=timestamp
        )

    def __call_callback(self, type):
        if self.callback is not None:
            self.callback(self, type)
            return True
        return False

    def handle_refresh(self):
        """
        Handles the refresh request.

        Calls __call_callback method with input of 'refresh'

        Returns:
            results of __call_callback

        """
        return self.__call_callback('refresh')

    def handle_control(self, data_value):
        """
        Handles the control request.

        Sets data_value and last_controlled values of this Value object, with
        value provided and calls __call_callback method with input of 'set'.

        Args:
            data_value: the new value.

        Returns:
            results of __call_callback

        """
        self.data_value = data_value
        # self.last_update_of_control = state.timestamp
        self.last_controlled = data_value

        return self.__call_callback('set')

    def __send_logic(self, state, type, data_value=None, timestamp=None):
        """
        Send control or report to a server.

        Sends a control or report message with a new value to the server.
        Updates the time of lasted sent control and sets a new updated value.
        Then invokes callback in order to inform a user about the result of the
        operation.

        Args:
            state: Reference to an instance of a State class.
            type: Determines if the message is report or control
            data_value: A new incoming value.


        Returns:
            True if successfully, False if error occurs.
            boolean

        Raises:
            Exception: If one occurs while sending control message.

        """
        try:
            json_data = self.rpc.get_rpc_state(
                str(data_value),
                self.parent_network_id,
                self.parent_device_id,
                self.uuid,
                state.uuid,
                type,
                state_obj=state
            )
            if timestamp:
                state.timestamp = timestamp
            else:
                state.timestamp = self.get_now()
            self.last_update_of_report = state.timestamp
            return self.rpc.send_init_json(self.conn, json_data)

        except Exception as e:
            msg = "Error reporting state: {}".format(e)
            self.wapp_log.error(msg)
            return False

    def __is_number_type(self):
        """
        Validate data type.

        Checks whether the type of the value is number.

        Returns:
        True if the type is number otherwise false.
        boolean

        """
        if self.data_type == "number":
            return True
        else:
            return False

    def __is_string_type(self):
        """
        Validate data type.

        Checks whether the type of the value is string.

        Returns:
        True if the type is string otherwise false.
        boolean

        """
        if self.data_type == "string":
            return True
        else:
            return False

    def __is_blob_type(self):
        """
        Validate data type.

        Checks whether the type of the value is blob.

        Returns:
        True if the type is blob otherwise false.
        boolean

        """
        if self.data_type == "blob":
            return True
        else:
            return False
