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

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details.
