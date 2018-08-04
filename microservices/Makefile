RM=rm -rf
TARGET=dist/sierra

all: setup lint compile

clean:
	$(RM) .pytest_cache
	$(RM) __pycache__
	$(RM) build
	$(RM) dist

setup:
	pip install pipenv
	pipenv install --dev

lint:
	pipenv run flake8 sierra/*.py

test:
	pipenv run pytest

compile: $(TARGET)

$(TARGET): sierra.spec sierra/*.py
	pipenv run pyinstaller sierra.spec
