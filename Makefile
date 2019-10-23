TEST_PATH=./test

.PHONY: clean-pyc clean-build

clean-pyc:
	find . -name '*.pyc' -exec rm --force {} +
	find . -name '*.pyo' -exec rm --force {} +
	find . -name '*~'    -exec rm --force {} +

clean-build:
	rm --force --recursive build/
	rm --force --recursive dist/
	rm --force --recursive *.egg-info

build:
	python3 setup.py sdist bdist_wheel

publish: build
	@echo "Please make sure that you have set 'TWINE_PASSWORD'."
	@echo "You can find the password here: https://phabricator.iot.seluxit.com/w/python_package_index/"
	python3 -m twine upload -u seluxit dist/*

install:
	pip install --user --requirement requirements.txt
