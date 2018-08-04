ifdef COMSPEC
	RM=RD /S /Q
	TARGET=dist/sierra.exe
else
	RM=rm -rf
	TARGET=dist/sierra
endif

all: setup lint test compile

clean:
	$(RM) .pytest_cache
	$(RM) __pycache__
	$(RM) build
	$(RM) dist

setup:
	pipenv install --dev

lint:
	pipenv run flake8 sierra.py

test:
	pipenv run pytest

compile: $(TARGET)

$(TARGET): sierra.py sierra.spec
	pipenv run pyinstaller sierra.spec
