from setuptools import find_packages, setup

with open("README.md", "r") as file:
    long_description = file.read()

setup(
      name="wappsto",
      version="1.0.0",
      author="Seluxit",
      author_email="placeholder",
      description="placeholder",
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="placeholder",
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: [placeholder] :: [placeholder]",
        "Operating System :: OS Independent"
      ],
      packages=find_packages()
)
