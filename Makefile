# Shortcuts for various dev tasks. Based on makefile from pydantic
.DEFAULT_GOAL := all
isort = isort plugins tests
black = black plugins tests --exclude=plugins/tfplugin5
flake8 = flake8 plugins tests


.PHONY: install
install:
	pip install -U setuptools pip wheel
	pip install -U --pre -r requirements.txt -r requirements.dev.txt

.PHONY: format
format:
	$(isort)
	$(black)
	$(flake8)

.PHONY: pep8
pep8:
	$(flake8)

RUN_MYPY_PLUGINS=MYPYPATH=docs python -m mypy --html-report mypy/out/inmanta_plugins -p inmanta_plugins.terraform
RUN_MYPY_TESTS=MYPYPATH=tests python -m mypy --html-report mypy/out/tests tests

mypy-plugins:
	@ echo -e "Running mypy on the module plugins\n..."
	@ $(RUN_MYPY_PLUGINS)

mypy-tests:
	@ echo -e "Running mypy on the module tests\n..."
	@ $(RUN_MYPY_TESTS)

.PHONY: mypy
mypy: mypy-plugins mypy-tests
