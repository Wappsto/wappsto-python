"""
Message log module.

Logs data being sent in case of in connection and sends it when connection is established.

Attributes:
    REMOVE_OLD: Removes the old data.
    REMOVE_RECENT: Doesnt add the most recent data.

    HOUR_PERIOD: Indicates that log should be compacted once an hour.
    DAY_PERIOD: Indicates that log should be compacted once a day.
    MONTH_PERIOD: Indicates that log should be compacted once a month.

"""
import os
import re
import sys
import json
import time
import zipfile
import logging
import datetime
from json.decoder import JSONDecodeError


REMOVE_OLD = 1
REMOVE_RECENT = 2

HOUR_PERIOD = 3
DAY_PERIOD = 2
MONTH_PERIOD = 1

TIME_BETWEEN_LOG_SEND = 0.1  # time to wait before sending next logged message (seconds)


class OfflineEventStorage:
    """
    Offline event storage.

    Saves data not being sent due to not having connection.
    """

    def __init__(self, log_offline, log_location, log_data_limit, limit_action, compression_period):
        """
        Initialize OfflineEventStorage class.

        Sets up message logging enviroment.

        Args:
            log_offline: boolean indicating if data should be logged
            log_location: location of the logs
            log_data_limit: limit of data to be saved in log [in Megabytes]
            limit_action: action to take when limit is reached
            compression_period: period for compressing data [day, hour]

        Raises:
            ServerConnectionException: "Unable to connect to the server.

        """
        self.wapp_log = logging.getLogger(__name__)
        self.wapp_log.addHandler(logging.NullHandler())

        self.log_offline = log_offline
        self.log_data_limit = log_data_limit
        self.limit_action = limit_action
        self.compression_period = compression_period

        self.set_location(log_location)

    def set_location(self, log_location):
        """
        Set log location.

        Sets log location and creates log folder if necassary.

        Args:
            log_location: location of the logs.

        """
        self.log_location = log_location
        os.makedirs(self.log_location, exist_ok=True)

    def get_file_path(self, file_name):
        """
        Gets path to the file.

        Concatenates location of the logs and file name.

        Args:
            file_name: name of the file.

        Returns:
            path to the file.

        """
        return os.path.join(self.log_location, file_name)

    def get_log_name(self):
        """
        Gets name of the newest log.

        Creates and returns the name of the log.

        Returns:
            name of the latest log.

        """
        now = datetime.datetime.now()
        if self.compression_period >= MONTH_PERIOD:
            file_name = str(now.year) + "-" + str(now.month)
        if self.compression_period >= DAY_PERIOD:
            file_name += "-" + str(now.day)
        if self.compression_period >= HOUR_PERIOD:
            file_name += "-" + str(now.hour)
        file_name += ".txt"
        return file_name

    def get_logs(self):
        """
        Gets log files in the location.

        Gets all files from directory and return ones that follow log file format.

        Returns:
            list of log file names.

        """
        file_list = os.listdir(self.log_location)
        pattern = "[0-9][0-9][0-9][0-9]-([0-9]|1[0-2])"
        return [file_name for id, file_name in enumerate(file_list) if re.search(pattern, file_name)]

    def compact_logs(self):
        """
        Compacts all logs to save space.

        Uses all logs received from "get_logs" method and compacts the ones that
        are of type text (after compacting the text file is deleted).

        """
        all_logs = self.get_logs()
        text_logs = [file_name for id, file_name in enumerate(all_logs) if re.search(".txt$", file_name)]
        for file_name in text_logs:
            file_path = self.get_file_path(file_name)
            with zipfile.ZipFile(file_path.replace(".txt", ".zip"), "w") as zip_file:
                zip_file.write(file_path, file_name)
            os.remove(file_path)

    def get_oldest_log_name(self):
        """
        Gets the oldest log's name.

        Uses all logs received from "get_logs" method and sorts them, taking the first (oldest).

        Returns:
            name of the file.

        """
        all_logs = self.get_logs()
        all_logs.sort()
        file_name = all_logs[0]
        return file_name

    def get_text_log(self, file_name):
        """
        Gets name of the file.

        Checks if the file is compacted, if it is then it is unzipped and new name is returned,
        otherwise same file is returned.

        Args:
            file_name: name of the file.

        Returns:
            name of the file.

        """
        if re.search(".zip$", file_name):
            file_path = self.get_file_path(file_name)
            with zipfile.ZipFile(file_path, "r") as zip_file:
                zip_file.extractall(self.log_location)
            os.remove(file_path)
            file_name = file_name.replace(".zip", ".txt")
        return file_name

    def remove_data(self, file_name):
        """
        Removes data.

        Removes lines from the file, but if the number of lines to remove
        exceeds lines in file or file is not text format the file is deleted.

        Args:
            file_name: name of the file.

        """
        file_path = self.get_file_path(file_name)
        if not re.search(".txt$", file_name):
            os.remove(file_path)
            self.wapp_log.debug("Removed old data")
            return

        with open(file_path, "r") as file:
            lines = file.readlines()
        if len(lines) > 1:
            with open(file_path, "w") as file:
                file.writelines(lines[1:])
        else:
            os.remove(file_path)
        self.wapp_log.debug("Removed old data")

    def add_message(self, data):
        """
        Add message to log.

        Adds message to log if logging is enabled otherwise writes error.

        Args:
            data: JSON message data.

        """
        if not self.log_offline:
            self.wapp_log.error("Sending while not connected")
            return

        try:
            string_data = json.dumps(data)
            if (self.log_data_limit * 1000000) >= self.get_size(string_data):
                file_name = self.get_log_name()
                file_path = self.get_file_path(file_name)
                if not os.path.isfile(file_path):
                    # compact data if log for this period doesnt exist
                    self.compact_logs()
                with open(file_path, "a") as file:
                    file.write(string_data + " \n")
                self.wapp_log.debug("Raw log Json: {}".format(string_data))
            else:
                self.wapp_log.debug("Log limit exeeded.")
                if self.limit_action == REMOVE_OLD:
                    file_name = self.get_oldest_log_name()
                    self.remove_data(file_name)
                    self.add_message(data)
                elif self.limit_action == REMOVE_RECENT:
                    self.wapp_log.debug("Not adding data")
        except FileNotFoundError:
            msg = "No log file could be created in: {}".format(self.log_location)
            self.wapp_log.error(msg)

    def get_size(self, data):
        """
        Gets size of log folder.

        Method loops through all files and gets their total size in the folder,
        later also adds size of the data you are trying to save.

        Args:
            data: JSON message data.

        Returns:
            Total size of the folder after changes.

        """
        total_size = 0
        for dirpath, dirnames, file_names in os.walk(self.log_location):
            for file_name in file_names:
                file_path = os.path.join(dirpath, file_name)
                # skip if it is link
                if not os.path.islink(file_path):
                    total_size += os.path.getsize(file_path)

        total_size += sys.getsizeof(data)
        return total_size

    def send_log(self, conn):
        """
        Sends log data.

        If logging is enabled reads all saved messages from log and sends them, later emptying log.

        Args:
            conn: reference to ClientSocket object.

        """
        if self.log_offline:
            try:
                log_list = self.get_logs()
                self.wapp_log.debug("Found log files: " + str(log_list))

                for file_name in log_list:
                    file_name = self.get_text_log(file_name)
                    file_path = self.get_file_path(file_name)
                    with open(file_path, "r") as file:
                        lines = file.readlines()
                    for line in lines:
                        try:
                            data = json.loads(line)
                            for data_element in data:
                                if conn.connected:
                                    time.sleep(TIME_BETWEEN_LOG_SEND)
                                    conn.send_data.create_bulk(data_element)
                                else:
                                    raise ConnectionError
                        except JSONDecodeError:
                            error = "Json decoding error while reading : {}".format(line)
                            self.wapp_log.error(error)
                    self.wapp_log.debug("Data sent from file: " + file_path)
                    os.remove(file_path)
            except FileNotFoundError:
                error = "Log directory could not be found: {}".format(self.log_location)
                self.wapp_log.error(error)
            except ConnectionError:
                # todo maybe should remove sent messages from file being read (so it wouldnt be sent twice)
                self.wapp_log.debug("No connection to the server: Logs are no longer being sent")
