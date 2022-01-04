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

from inmanta.agent import config as inmanta_config
from inmanta.agent.agent import Agent

LOGGER = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--cache-dir",
        help="Set fixed cache directory",
    )
    parser.addoption(
        "--lab",
        action="store",
        help="Name of the lab to use. Overrides the value set in the INMANTA_TERRAFORM_LAB environment variable.",
    )


@pytest.fixture(scope="session")
def lab_name(request) -> str:
    pytest_option: Optional[str] = request.config.getoption("--lab")
    lab_name: Optional[str] = (
        pytest_option
        if pytest_option is not None
        else os.environ.get("INMANTA_TERRAFORM_LAB", None)
    )

    if lab_name is None:
        raise Exception("This test requires the --lab option to be set")

    return lab_name


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
    fixed_cache_dir = request.config.getoption("--cache-dir")
    if not fixed_cache_dir:
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
