"""
Message log module.

Logs data being sent in case of in connection and sends it when connection is established.

Attributes:
    REMOVE_OLD: Removes the old data.
    REMOVE_RECENT: Doesnt add the most recent data.

"""
import os
import re
import sys
import json
import logging
import datetime
from json.decoder import JSONDecodeError


REMOVE_OLD = 1
REMOVE_RECENT = 2


class MessageLog:
    """
    Message logger.

    Saves data not being sent due to no connection.
    """

    def __init__(self, log_offline, log_location, log_data_limit, limit_action):
        """
        Initialize MessageLog class.

        Sets up message logging enviroment.

        Args:
            log_offline: boolean indicating of data should be logged.
            log_location: location of the logs.
            log_data_limit: limit of data to be saved in log (bytes)
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

        Sets log location and creates log folder if necassary.

        Args:
            log_location: location of the logs.

        """
        if log_location == "":
            self.log_location = "logs"
        else:
            self.log_location = log_location
        if self.log_offline:
            os.makedirs(self.log_location, exist_ok=True)

    def get_log_name(self):
        now = datetime.datetime.now()
        return self.log_location + "/" + str(now.day) + "-" + str(now.month) + "-" + str(now.year) + ".txt"

    def add_message(self, data):
        """
        Add message to log.

        Adds message to log if logging is enabled otherwise writes error.

        Args:
            data: JSON communication message data.

        """
        if self.log_offline:
            try:
                string_data = json.dumps(data)
                if self.log_data_limit >= self.get_size(string_data):
                    file = open(self.get_log_name(), 'a')
                    file.write(string_data + " \n")
                    file.close()
                    self.wapp_log.debug('Raw log Json: {}'.format(string_data))
                else:
                    self.wapp_log.debug('Log limit exeeded.')
                    if self.limit_action == REMOVE_OLD:
                        with open(self.get_log_name(), 'r') as file:
                            lines = file.readlines()
                        with open(self.get_log_name(), 'w') as file:
                            file.writelines(lines[1:])
                        self.wapp_log.debug('Removed old data')
                        self.add_message(data)
                    elif self.limit_action == REMOVE_RECENT:
                        self.wapp_log.debug('Not adding data')
            except FileNotFoundError:
                msg = "No log file could be created in: {}".format(self.log_location)
                self.wapp_log.error(msg)
        else:
            self.wapp_log.error('Sending while not connected')

    def get_size(self, data):
        """
        Gets size of log folder.

        Method loops through all file and gets their total size in the folder.

        Args:
            data: JSON communication message data.

        Returns:
            Total size of the folder.
        """
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.log_location):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)

        total_size += sys.getsizeof(data)
        return total_size

    def send_log(self, conn):
        """
        Sends log data.

        If logging is enabled reads all saved messages from log and sends them, later emptying log.

        """
        if self.log_offline:
            try:
                dir_list = enumerate(os.listdir(self.log_location))
                log_list = [ name for id, name in dir_list if re.search('((|1|2)[0-9]|3[0-1])-((0|)[0-9]|1[0-2])-[0-9][0-9][0-9][0-9]', name) ]
                self.wapp_log.debug("Found log files: " + str(log_list))

                for element in log_list:
                    file_location = self.log_location + "/" + element
                    with open(self.get_log_name(), 'r') as file:
                        lines = file.readlines()

                    for line in lines:
                        data = json.loads(line)
                        for data_element in data:
                            conn.create_bulk(data_element)
                    self.wapp_log.debug("file: " + file_location + " data sent.")
                    os.remove(file_location)
            except JSONDecodeError:
                error = "Json decoding error while reading file: {}".format(file_location)
                self.wapp_log.error(error)
            except FileNotFoundError:
                error = "Log directory could not be found: {}".format(self.log_location)
                self.wapp_log.error(error)
