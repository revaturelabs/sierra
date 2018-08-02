# Sierra Microservices

> CloudFormation template generator for microservices

## Requirements

This project requires Python 3.6.

Your IAM user will need the necessary permissions to use CloudFormation. You will also need to [setup AWS credentials](https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration) on your local workstation.

## Installation

Installation instructions will be provided soon.

## Development

### Setup

First, install pipenv:

```bash
$ pip install pipenv
```

Then, clone this repo and install the dependencies:

```bash
# Clone this repo into the current directory
$ git clone https://github.com/revaturelabs/sierra.git
# Navigate to the microservices version of sierra
$ cd sierra/microservices/
# Install all dependencies, including development only
$ pipenv install --dev
```

Finally activate the pipenv environment. You should activate the environment whenever you run this project.

```bash
$ pipenv shell
```

### Tests

To run tests, run either of the following:

```bash
# Run the py.test command directly
$ pytest

# Or invoke it indirectly through the test file
$ ./sierra_test.py
```

### Compiling

To generate a single-file executable, simply run the following:

```bash
$ pyinstaller sierra.spec
```

If you are using Windows, this will create a .exe file. If you are using Linux, it will create a binary executable.
