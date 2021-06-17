#!/bin/env python3

# This code are based on the assumption that there have been
# created a `black (custom)` in the `IoT Rapid Prototyping` Wap
# That contains a Device by name: `TheDevice` &
# a string value by name: `StringInfo`, that have a report & control state.
# the config json & certificates have been downloaded.
# save and unpack in the download folder alongside this code file.
#
# NOTE: Remember to change the ConfigFile name.

import datetime
import time
import wappsto

service = wappsto.Wappsto(
    json_file_name="NameOfTheConfigFile.json",  # Typical a UUID.json
    abs_config_path="~/Downloads"  # Optional: Just assumes same folder as code.
)

ready = False


def get_timestamp():
    """Return The default timestamp used for Wappsto."""
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def status_cb(status):
    """A Status Callback Example."""
    global ready
    if status.is_running():
        print("\rWappsto connect is up and running.")
        ready = True
    if status.is_disconnecting():
        print("\rWappsto connect have been lost.")


service.get_status().set_callback(status_cb)


def network_callback(network, event):
    print(f"Network have been {event} from Wappsto.")
    print("Exiting info code.")
    service.stop()
    exit(1)


service.get_network().set_callback(network_callback)


device = service.get_device("TheDevice")


def string_info_cb(value, action_type):
    """This is the Callback function for value: 'StringInfo'."""
    if action_type == 'refresh':
        print("\rRefreshing StringInfo to: 'Refreshed!'")
        device.get_value("StringInfo").update(
            data_value="Refreshed!",
            timestamp=get_timestamp()
        )
    elif action_type == 'set':
        value = value.get_control_state().data
        print(f"\rMessage from Wappsto: {value}")


device.get_value("StringInfo").set_callback(string_info_cb)


try:
    service.start()
    while not ready:
        # Waiting for Wappsto to be ready.
        time.sleep(0.5)
    while True:
        data = input("Enter a Message: ")
        if data in ['exit', 'x', 'quit', 'q']:
            break
        device.get_value("StringInfo").update(data, get_timestamp())
finally:
    service.stop()
