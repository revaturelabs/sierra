# Sierra Microservices

> CloudFormation template generator for microservices

Put basic description here.

## Requirements

This project does not have any requirements to run. However, to make use of the generated CloudFormation template, you will need to have sufficient permissions to use CloudFormation on an AWS account.

## Install

Installation instructions will be provided soon.

## Usage

```bash
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
