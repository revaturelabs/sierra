# Sierra Microservices

> CloudFormation template generator for microservices

## Development

First, install pipenv (using Python3):

```bash
$ pip install pipenv
```

If you're using MacOS, you can install using Homebrew instead:

```bash
$ brew install pipenv
```

Then, clone this repo and install the dependencies:

```bash
$ git clone https://github.com/revaturelabs/sierra.git
$ cd sierra/microservices/
$ pipenv install --dev
```

Finally activate the pipenv environment. You should activate the environment whenever you run this project.

```bash
$ pipenv shell
```

To run tests, run either of the following:

```bash
$ # Run the py.test command directly
$ pytest
$
$ # Or invoke it indirectly through the test file
$ ./sierra_test.py
```
