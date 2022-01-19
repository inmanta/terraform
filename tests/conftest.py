"""
    Copyright 2021 Inmanta

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

    Contact: code@inmanta.com
"""
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import pytest
import yaml
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item
from helpers.parameter import (
    BooleanTestParameter,
    ParameterNotSetException,
    StringTestParameter,
    TestParameter,
)

from inmanta.agent import config as inmanta_config
from inmanta.agent.agent import Agent

LOGGER = logging.getLogger(__name__)

# Setting up global test parameters
cache_dir = StringTestParameter(
    argument="--terraform-cache-dir",
    environment_variable="INMANTA_TERRAFORM_CACHE_DIR",
    usage="Set fixed cache directory",
)

lab = StringTestParameter(
    argument="--terraform-lab",
    environment_variable="INMANTA_TERRAFORM_LAB",
    usage="Name of the lab to use",
)

provider_parameters = [
    BooleanTestParameter(
        argument=f"--terraform-skip-provider-{provider}",
        environment_variable=f"INMANTA_TERRAFORM_SKIP_PROVIDER_{provider.upper()}",
        usage=f"Skip tests using the {provider} provider",
    )
    for provider in (
        "checkpoint",
        "fortios",
        "github",
        "gitlab",
        "local",
    )
]


def pytest_addoption(parser: Parser) -> None:
    """
    Setting up test parameters
    """
    group = parser.getgroup("terraform", description="Terraform module testing options")
    parameters: List[TestParameter] = [cache_dir, lab]
    parameters.extend(provider_parameters)
    for param in parameters:
        group.addoption(
            param.argument,
            action=param.action,
            help=param.help,
        )


def pytest_configure(config: Config) -> None:
    """
    Registering markers
    """
    for provider_parameter in provider_parameters:
        name = (
            provider_parameter.argument.strip("--")
            .replace("-", "_")
            .replace("_skip_", "_")
        )
        config.addinivalue_line(
            "markers",
            f"{name}: mark test to run only with option {provider_parameter.argument} is not set",
        )


def pytest_runtest_setup(item: Item) -> None:
    """
    Checking if a provider test should be skipped or not
    """
    for provider_parameter in provider_parameters:
        name = (
            provider_parameter.argument.strip("--")
            .replace("-", "_")
            .replace("_skip_", "_")
        )
        if name not in item.keywords:
            # The test is not marked
            continue

        if provider_parameter.resolve(item.config):
            # The test should be skipped
            pytest.skip(
                f"This test is only executed with option {provider_parameter.argument}"
            )


@pytest.fixture(scope="session")
def lab_name(request: pytest.FixtureRequest) -> str:
    return lab.resolve(request.config)


@pytest.fixture(scope="session")
def lab_config_session(lab_name: str) -> dict:
    file_name = f"{lab_name}.yaml"

    with open(f"{os.path.dirname(__file__)}/labs/{file_name}") as file:
        file_content = yaml.safe_load(file)

    return file_content


@pytest.fixture
def lab_config(lab_config_session: Dict[str, Any]) -> dict:
    return deepcopy(lab_config_session)


@pytest.fixture(scope="session")
def session_temp_dir(tmpdir_factory: pytest.TempdirFactory) -> str:
    session_temp_dir = tmpdir_factory.mktemp("session")
    LOGGER.info(f"Session temp dir is: {str(session_temp_dir)}")
    yield str(session_temp_dir)
    session_temp_dir.remove(ignore_errors=True)


@pytest.fixture(scope="function")
def function_temp_dir(session_temp_dir: str) -> str:
    function_temp_dir = Path(session_temp_dir) / Path("function")
    function_temp_dir.mkdir(parents=True, exist_ok=False)
    LOGGER.info(f"Function temp dir is: {function_temp_dir}")
    yield str(function_temp_dir)
    shutil.rmtree(str(function_temp_dir), ignore_errors=True)


@pytest.fixture(scope="function")
def cache_agent_dir(function_temp_dir: str, request: pytest.FixtureRequest) -> str:
    try:
        fixed_cache_dir = cache_dir.resolve(request.config)
    except ParameterNotSetException:
        LOGGER.warning(
            "Fixture 'use_agent_cache_dir' was called without setting a cache directory"
        )
        fixed_cache_dir = function_temp_dir

    LOGGER.info(f"Caching agent files in {fixed_cache_dir}")
    inmanta_config.state_dir.set(fixed_cache_dir)
    yield inmanta_config.state_dir.get()


@pytest.fixture
def agent_factory(
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    no_agent_backoff: None,
) -> Callable[[UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent]:
    """
    Overwriting the existing agent_factory fixture.  This one does what the existing one does,
    and also disable the agent backoff.  This should avoid any rate limiter issue poping in the tests.

    We overwrite this fixture because it is used in all our test needing agents, which might
    potentially have backoff issues.
    """
    return agent_factory
