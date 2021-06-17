#!/bin/env python3

# This code are based on the assumption that there have been
# created a `black (custom)` in the `IoT Rapid Prototyping` Wap
# That contains a Device by name: `EchoDevice` &
# a string value by name: `Moeller`, that have a report & control state.
# the config json & certificates have been downloaded.
# save and unpack in the download folder alongside this code file.
#
# NOTE: Remember to change the ConfigFile name.

import datetime
import logging
import wappsto

logging.basicConfig(level=logging.DEBUG)

service = wappsto.Wappsto(
    json_file_name="NameOfTheConfigFile.json"  # Typical a UUID.json
)


def network_callback(network, event):
    print(f"Network have been {event} from Wappsto.")
    service.terminated.set()
    exit(1)


service.get_network().set_callback(network_callback)


device = service.get_device("EchoDevice")


def echo_cb(value, action_type):
    """This is the Callback function for value: 'Moeller'."""
    if action_type == 'refresh':
        new_value = device.get_value("Moeller").get_data() + " Refreshed!"
        print("\rRefreshing Moeller to: '{new_value}'")
        device.get_value("Moeller").update(
            data_value=new_value,
            timestamp=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        )
    elif action_type == 'set':
        print(f"\rMessage from Wappsto: {value}")
        device.get_value("Moeller").update(
            value.get_control_state().data,
            datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        )


device.get_value("Moeller").set_callback(echo_cb)


service.start(blocking=True)
