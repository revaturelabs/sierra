ifdef COMSPEC
	RM=RD /S /Q
	TARGET=dist/sierra.exe
else
	RM=rm -rf
	TARGET=dist/sierra
endif

all: lint test $(TARGET)

clean:
	$(RM) .pytest_cache
	$(RM) __pycache__
	$(RM) build
	$(RM) dist

setup:
	pip3 install --user pipenv
	pipenv install --dev

lint:
	pipenv run flake8 sierra.py

test:
	pipenv run pytest

$(TARGET): sierra.py
	pipenv run pyinstaller sierra.spec
