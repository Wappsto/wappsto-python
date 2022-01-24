# Wappsto python module - DEPRECATED

The project is archived. Please migrate to https://github.com/Wappsto/python-wappsto-iot

[![Build Status](https://travis-ci.com/Wappsto/wappsto-python.svg?branch=master)](https://travis-ci.com/Wappsto/wappsto-python)
[![Coverage Status](https://coveralls.io/repos/github/Wappsto/wappsto-python/badge.svg?branch=master)](https://coveralls.io/github/Wappsto/wappsto-python?branch=master)

The wappsto module provide a simple python interface to [wappsto.com](https://wappsto.com/) for IoT Rapid Prototyping.


## Prerequisites

The wappsto module requires two things: A set of certificates for authentication and the JSON data model for representing your data and structure of your physical device. 
The certificates provides the physical device the secure connection to wappsto.com.
The data model provides context and structure for the data stored at wappsto.com and systematic handling of your device. It is an instance of our Unified Data Model (UDM) specifying the structure of your network, devices, values and their states. Be sure to read more about the UDM [here](https://documentation.wappsto.com) before moving on.

These files are automatically generated at wappsto.com when using the [`IoT Rapid Prototyping` web-app (wapp)](https://store.wappsto.com/application/slx_iot_creator) along with working code.
You may choose a blank template to serve as a starting point for your own custom IoT device.


## Getting Started

Working examples of usage can be found in the [example folder](./example).

The following explains the example code found in [info.py](./example/info.py). 


### Basic setup

For the wappsto module to know the desired data model, we need to provide it as a JSON config file as seen below.

```python
service = wappsto.Wappsto(
    json_file_name="NameOfTheConfigFile.json",  # Typical a UUID.json
    abs_config_path="~/Downloads"  # Optional: Just assumes same folder as code.
)
```

The needed certificates for the secure connection are excepted to be found in a folder named: `certificates` in the same level as the JSON config file.


### Optional Status Callback

If you want to know or act upon changes to the connection status of the wappsto module, a callback can be registered.

The below defines a callback that simply lets you know when the connection status have changed.

```python
def status_cb(status):
    """A Status Callback Example."""
    global ready
    if status.is_running():
        print("\rWappsto connect is up and running.")
        ready = True
    if status.is_disconnecting():
        print("\rWappsto connect have been lost.")

# Setting the Status Callback.
service.service.get_status().set_callback(status_cb)
```


### Optional Network Delete callback

You can register a callback at the network level. Currently, only `Delete network` events are supported. 
Such events typically means that the network have been deleted by the user. This could be used to trigger a factory reset, a device reboot, or prompt any other desired behavior.
In this case we just stop the program.

```python 
def network_callback(network, event):
    print(f"network event: {event}")
    if event == "delete":  # Always true for networks
        service.stop()
        exit(1)

# Setting the Network Callback
service.get_network().set_callback(network_callback)
```


### Value Handle Setup

For each value for each device a registered callback is expected.
For a value with a control state, the `set` action_type is needed to be able to react on an attempt to control the device. This is used for controlling a state and prompting the device to act a certain way.
For a value with a report state, the `refresh` `action_type` is needed to renew the value. This is often set up to trigger a device to sample the relevant "sensor" and get the latest data.

In the below, the control state is simply printed upon change and the report state is updated to "Refreshed!" upon a refresh:

```python
device = service.get_device("TheDevice")


def string_info_cb(value, action_type):
    """This is the Callback function for value: 'StringInfo'."""
    if action_type == 'refresh':
        print("\rRefreshing StringInfo to: 'Refreshed!'")
        device.get_value("StringInfo").update(
            data_value="Refreshed!",
            timestamp=get_timestamp()  # In principle redundant
        )
    elif action_type == 'set':
        value = value.get_control_state().data
        print(f"\rMessage from Wappsto: {value}")


device.get_value("StringInfo").set_callback(string_info_cb)
```

When updating the report value, only the value/data is required and the timestamp is optional. If the timestamp is not explicitly given, the wappsto module will set the timestamp to the current time when function is called.


### Main Loop.

If everything is in callbacks and you just want to run forever
you can then call the service.start with the `blocking=True` input,
which is making it blocking until a `SIGINT` or `SIGTERM` is received.
If this is the case, you do not need to call `service.stop()`.
An example of this can be found in the [echo.py](./example/echo.py) example.

Alternatively, the main loop can be stated just after the service is started.

```python
try:
    service.start()
    # NOTE: YOUR CODE GOES HERE!
finally:
    service.stop()
```

In our example we set it up to wait for user input which updates the value:

```python
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
```




### Tips and tricks

If the UUIDs are known for the given Network, Devices or Values you can get them directly with this function:
```python
service.get_by_id("<UUID>")
```

To get the latest value that was reported in for the value: `StringInfo`:
```python
device.get_value("StringInfo").getdata()
```

The data model JSON file may also contain a delta (value change) & period (update time period), for which the value should uphold.
To check this there is a function.
```python
device.get_value("StringInfo").check_delta_and_period(value)
```


The service will by default save the runtime data to a new JSON file, this can be disabled in the stop command as such:
```python
service.stop(save=False)
```


### Installation using pip

The wappsto module can be installed using PIP (Python Package Index) as follows:

```bash
$ pip install -U wappsto
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details.
