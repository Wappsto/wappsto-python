from setuptools import find_packages, setup

with open("README.md", "r") as file:
    long_description = file.read()

setup(
    name="wappsto",
    version="1.0.3",
    author="Seluxit A/S",
    author_email="support@seluxit.com",
    license="Apache-2.0",
    description="Python Package to connect to wappsto.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wappsto/wappsto-python",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent"
    ],
    packages=find_packages(),
    tests_require=[
        'pytest',
    ],
    python_requires='>3.6.0',
)
