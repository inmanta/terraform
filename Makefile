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

RUN_MYPY_PLUGINS=python -m mypy --html-report mypy/out/inmanta_plugins -p inmanta_plugins.terraform --exclude inmanta_plugins.terraform.tfplugin5.*
RUN_MYPY_TESTS=MYPYPATH=tests python -m mypy --html-report mypy/out/tests tests

mypy-plugins:
	@ echo -e "Running mypy on the module plugins\n..."
	@ mkdir -p inmanta_plugins;\
		touch inmanta_plugins/__init__.py;\
		touch inmanta_plugins/py.typed;\
		stat inmanta_plugins/terraform > /dev/null || ln -s ../plugins inmanta_plugins/terraform
	@ $(RUN_MYPY_PLUGINS)

mypy-tests:
	@ echo -e "Running mypy on the module tests\n..."
	@ $(RUN_MYPY_TESTS)

ci-mypy: mypy-plugins

.PHONY: mypy
mypy: mypy-plugins mypy-tests

tfplugin5:
	cd docs/tf_grpc_plugin/ && python -m grpc_tools.protoc -I proto --python_out=.. --grpc_python_out=.. proto/inmanta_plugins/terraform/tfplugin5/tfplugin5.proto; cd ../..
