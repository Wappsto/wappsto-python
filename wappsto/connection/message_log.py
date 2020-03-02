"""
Message log module.

Logs data being sent in case of in connection and sends it when connection is established.

Attributes:
    REMOVE_OLD: Removes the old data.
    REMOVE_RECENT: Doesnt add the most recent data.

"""
import os
import json
import logging
import datetime


REMOVE_OLD = 1
REMOVE_RECENT = 2

LOG_FILE = "event_log.txt"


class MessageLog:
    """
    Message logger.

    Saves data not being sent due to no connection.
    """

    def __init__(self, log_offline, log_location, log_data_limit=1, limit_action=REMOVE_OLD):
        """
        Initialize MessageLog class.

        Sets up message logging enviroment.

        Args:
            log_offline: boolean indicating of data should be logged.
            log_location: location of the logs.
            log_data_limit: limit of data to be saved in log (Megabytes)
            limit_action: action to take when limit is reached

        Raises:
            ServerConnectionException: "Unable to connect to the server.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.log_offline = log_offline
        self.log_data_limit = log_data_limit
        self.limit_action = limit_action

        self.set_location(log_location)

    def set_location(self, log_location):
        """
        Set log location.

        Sets log location and creates log if necassary.

        Args:
            log_location: location of the file.

        """
        self.log_location = log_location + LOG_FILE
        if self.log_offline:
            if os.path.isfile(self.log_location):
                self.wapp_log.debug("Log file found.")
            else:
                try:
                    open(self.log_location, 'w').close()
                except FileNotFoundError:
                    self.log_location = LOG_FILE
                    msg = "Bad log file location has been changed to default: {}".format(self.log_location)
                    self.wapp_log.error(msg)
                    open(self.log_location, 'w').close()
                self.wapp_log.debug("Log file created.")

    def get_file_name(self):
        now = datetime.datetime.now()
        return str(now.year) + "-" + str(now.month) + "-" + str(now.day)

    def add_message(self, data):
        """
        Add message to log.

        Adds message to log if logging is enabled otherwise writes error.

        Args:
            data: JSON communication message data.

        """
        if self.log_offline:
            try:
                data = json.dumps(data)
                file = open(self.log_location, "a")
                file.write(data + " \n")
                file.close()
                self.wapp_log.debug('Raw log Json: {}'.format(data))
            except FileNotFoundError:
                msg = "No log file could be created in: {}".format(self.log_location)
                self.wapp_log.error(msg)
        else:
            self.wapp_log.error('Sending while not connected')

    def check_limit(self):
        """
        Checks limit.

        Checks if save limit is reached and returns True if it has not been reached.

        Returns:
            True if it has not been reached, otherwise False.
        """

    def send_log(self, conn):
        """
        Sends log data.

        If logging is enabled reads all saved messages from log and sends them, later emptying log.

        """
        if self.log_offline:
            try:
                file = open(self.log_location, "r")
                lines = file.readlines()
                file.close()
            except FileNotFoundError:
                msg = "No log file found: {}".format(self.log_location)
                self.wapp_log.error(msg)
            else:
                for line in lines:
                    data = json.loads(line)
                    for data_element in data:
                        conn.create_bulk(data_element)
                self.wapp_log.error("Log data sent.")
                open(self.log_location, 'w').close()
