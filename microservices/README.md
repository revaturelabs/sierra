# Sierra Microservices

> CloudFormation template generator for microservices

Sierra for Microservices is a Python program that generates CloudFormation templates for microservice applications. These templates provision and allocate AWS resources in proportion to the specifications of the application. Everything from creating Docker hosts to the continuous deployment of containers can be handled by Sierra and CloudFormation.

## Install

To install, follow the [instructions in the wiki](https://github.com/revaturelabs/sierra/wiki/Microservice%3A-Usage).

## Usage

```
$ sierra --help
usage: sierra [-h] [-f FILE] [-o OUT] [--format {yaml,json}] [--compact]

Generate a CloudFormation template for microservices.

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  specify the Sierrafile to use
  -o OUT, --out OUT     a file to write output into
  --format {yaml,json}  specify the output file format
  --compact             make output compact (only for json)
```

## Develop

This project requires Python 3.6.

```bash
# Make sure you have pipenv installed
$ pip install pipenv

# Clone this repo into the current directory
$ git clone https://github.com/revaturelabs/sierra.git

# Navigate to the microservices version of sierra
$ cd sierra/microservices/
```

If you are using Linux, you can use the Makefile included in this repository. A basic description of the available Make goals are below.

```bash
# Run the "full" build lifecycle (setup, lint, compile)
$ make

# Remove all generated files
$ make clean

# Update your development environment
$ make setup

# Lint source code files
$ make lint

# Run tests (There are currently no tests for this project)
$ make test

# Generate a single-file executable
$ make compile
```

If you are using Windows, you will need to write out the full commands. There is no single command for running the full build lifecycle or clean.

```bash
# Update your development environment
$ pipenv install --dev

# Lint source code files
$ pipenv run flake8 sierra

# Run tests (There are currently no tests for this project)
$ pipenv run pytest

# Generate a single-file executable
$ pipenv run pyinstaller sierra.spec
```
