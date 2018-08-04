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

A basic description of the available Make goals are below. If you are using Windows, replace all occurences of `make` with `nmake` for the following instructions.

```bash
# Run the "full" build lifecycle (setup, lint, compile)
$ make

# Remove all generated files
$ make clean

# Initialize your development environment
$ make setup

# Lint source code files
$ make lint

# Run tests (There are currently no tests for this project)
$ make test

# Generate a single-file executable
$ make compile

# The binary will be inside the dist folder
# If you are using Windows, this will create a .exe file
# If you are using Linux, it will create a binary executable
```

