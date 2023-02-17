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
import asyncio
import json
import logging
import os
import pathlib
import typing
import uuid
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import helpers.utils
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

import inmanta.server
import inmanta.server.protocol
from inmanta import config, protocol
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
        "docker",
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


@pytest.fixture(scope="function")
def function_temp_dir(
    tmpdir_factory: pytest.TempdirFactory,
) -> typing.Generator[str, None, None]:
    function_temp_dir = tmpdir_factory.mktemp("function")
    LOGGER.info(f"Function temp dir is: {function_temp_dir}")
    yield str(function_temp_dir)

    def cleanup(path: pathlib.Path) -> None:
        # Make sure we can do everything we want on the file
        path.chmod(0o777)

        if path.is_file():
            # Delete the file
            path.unlink()
            return

        for inner_path in path.glob("*"):
            # Cleanup everything that is in the folder
            cleanup(inner_path)

        # Cleanup the folder
        path.rmdir()

    # Cleanup our dir
    cleanup(pathlib.Path(str(function_temp_dir)))


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
async def agent_factory(
    no_agent_backoff: None,
    cache_agent_dir: str,
    client: protocol.Client,
    server: inmanta.server.protocol.Server,
    environment: str,
) -> typing.Iterator[
    Callable[[UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent]
]:
    """
    Overwriting the existing agent_factory fixture.  This one does what the existing one does,
    and also disable the agent back off.  This should avoid any rate limiter issue popping in the tests.

    We also make sure that the cache agent dir fixture is loaded, so that any agent process
    being stopped still uses this cached dir.

    We overwrite this fixture because it is used in all our test needing agents, which might
    potentially have back off issues.
    """
    agentmanager = server.get_slice(inmanta.server.SLICE_AGENT_MANAGER)

    config.Config.set("config", "agent-deploy-interval", "0")
    config.Config.set("config", "agent-repair-interval", "0")

    started_agents: typing.List[Agent] = []

    async def create_agent(
        environment: uuid.UUID,
        hostname: Optional[str] = None,
        agent_map: Optional[Dict[str, str]] = None,
        code_loader: bool = False,
        agent_names: List[str] = [],
    ) -> Agent:
        a = Agent(
            hostname=hostname,
            environment=environment,
            agent_map=agent_map,
            code_loader=code_loader,
        )
        for agent_name in agent_names:
            await a.add_end_point_name(agent_name)
        await a.start()
        started_agents.append(a)
        await helpers.utils.retry_limited(
            lambda: a.sessionid in agentmanager.sessions, 10
        )
        return a

    yield create_agent

    async def list_agents() -> typing.List[dict]:
        result = await client.list_agents(tid=environment)
        all_agents = result.result["agents"]
        LOGGER.debug("All agents: %s", json.dumps(all_agents, indent=2))
        return all_agents

    # Get the names of all the manually started agents
    manually_started_agents = {
        val for agent in started_agents for val in agent.agent_map.keys()
    }

    all_agents = await list_agents()
    LOGGER.debug(
        "Stopping %d out of %d agents because they were started manually",
        len(manually_started_agents),
        len(all_agents),
    )
    await asyncio.gather(*[agent.stop() for agent in started_agents])

    async def agents_are_down() -> bool:
        all_agents = await list_agents()
        live_agents = [a for a in all_agents if a["state"] != "down"]
        my_agents = [a for a in live_agents if a["name"] in manually_started_agents]
        if len(my_agents) > 0:
            LOGGER.info(
                "Some of the manually started agent didn't stop yet: %s",
                str([a["name"] for a in my_agents]),
            )
            return False

        LOGGER.info(
            "Done waiting for all agents to start.  Remaining live agents: %s",
            str([a["name"] for a in live_agents]),
        )
        return True

    LOGGER.debug(
        "Waiting for manually started agents to terminate: %s",
        str(manually_started_agents),
    )
    await helpers.utils.retry_limited(agents_are_down, 10)
