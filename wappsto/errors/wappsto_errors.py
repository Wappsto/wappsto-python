"""
Custom Exception module.

This module contains custom exceptions used throughout the wappsto module.
"""


class DeviceNotFoundException(Exception):
    """
    Exception to signify Device not being found.

    This custom Exception extends the Exception class and implements no
    custom methods.

    Attributes:
        pass: The Exception has no custom body,
        just extends the Exception superclass.

    """

    pass


class ValueNotFoundException(Exception):
    """
    Exception to signify a value not being found.

    This custom Exception extends the Exception class and implements no
    custom methods.

    Attributes:
        pass: The Exception has no custom body,
        just extends the Exception superclass.

    """

    pass


class ServerConnectionException(Exception):
    """
    Exception to signify a server connection issue.

    This custom Exception extends the Exception class and implements no
    custom methods.

    Attributes:
        pass: The Exception has no custom body,
        just extends the Exception superclass.

    """

    pass


class CallbackNotCallableException(Exception):
    """
    Exception to signify Callback not being callable.

    This custom Exception extends the Exception class and implements no
    custom methods.

    Attributes:
        pass: The Exception has no custom body,
        just extends the Exception superclass.

    """

    pass
