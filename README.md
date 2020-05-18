# wappsto-python

[![Build Status](https://travis-ci.com/Wappsto/wappsto-python.svg?branch=master)](https://travis-ci.com/Wappsto/wappsto-python)
[![Coverage Status](https://coveralls.io/repos/github/Wappsto/wappsto-python/badge.svg?branch=master)](https://coveralls.io/github/Wappsto/wappsto-python?branch=master)

Python module for rapid prototyping for wappsto.com

## Getting Started

Instantiating the wappsto module with input from the command line:
```
service = wappsto.Wappsto(sys.argv[1])
```
Or using a string:
```
service = wappsto.Wappsto("path/to/your/jsonfile.json")
```
Starting the service without custom connection info:
```
service.start()
```
With custom info:
```
service.start(address="127.0.0.1", port=8080)
```
Stopping the service:
```
service.stop()
```
The service will by default save the runtime data to a new JSON file, this can be disabled in the stop command as such:
```
service.stop(save=False)
```

### Prerequisites

One of the requirements to use the wappsto module is to have a JSON file that has information about the network, devices, values and their states. This file can be generated from [the wappsto website](https://wappsto.com/).


### Installation using pip

Wappsto can be insalled using the Pything Package Index (PyPI).

```
$ pip install -U wappsto
```

## Known issues

In rear occasions (frequency ??) SSLError:

    May 18 10:30:16 PQPI-aa20fa15 bash[302]: 2020-05-18 10:30:16,242 - DEBUG: Raw Send Json: b'[{"jsonrpc": "2.0", "method": "PUT", "params": {"url": "/network/aa20fa15-74e2-43bf-995e-fce756579c54/device/3efbc9bd-471a-47f1-8a21-cfae9eec1977/value/847a6a67-8eac-43d0-94a9-9b567837fbbb/state/6d9d63e5-1f3e-4c46-9bb1-42734ae7a292", "data": {"meta": {"id": "6d9d63e5-1f3e-4c46-9bb1-42734ae7a292", "type": "state", "version": "2.0"}, "type": "Report", "status": "Send", "data": "1", "timestamp": "2020-05-18T08:30:16.238466Z"}}, "id": 220}]'
    May 18 10:30:16 PQPI-aa20fa15 bash[302]: 2020-05-18 10:30:16,244 - ERROR: Error sending: [SSL: BAD_LENGTH] bad length (_ssl.c:2337)
    May 18 10:30:16 PQPI-aa20fa15 bash[302]: Traceback (most recent call last):
    May 18 10:30:16 PQPI-aa20fa15 bash[302]:   File "/usr/lib/python3.7/site-packages/wappsto/connection/send_data.py", line 130, in send_data
    May 18 10:30:16 PQPI-aa20fa15 bash[302]:     self.client_socket.my_socket.send(data)
    May 18 10:30:16 PQPI-aa20fa15 bash[302]:   File "/usr/lib/python3.7/ssl.py", line 984, in send
    May 18 10:30:16 PQPI-aa20fa15 bash[302]:     return self._sslobj.write(data)
    May 18 10:30:16 PQPI-aa20fa15 bash[302]: ssl.SSLError: [SSL: BAD_LENGTH] bad length (_ssl.c:2337)


## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details.
