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
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy, deploy_model, off_main_thread
from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_failed(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    cache_agent_dir: str,
):
    forbidden_folder = Path("/dev")
    file_path_object = forbidden_folder / Path("test-file.txt")

    provider = LocalProvider()
    local_file = LocalFile(
        "my file", str(file_path_object), "my original content", provider
    )

    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    def model(purged: bool = False) -> str:
        model = "import terraform"

        model += "\n\n" + provider.model_instance("provider")
        model += "\n\n" + local_file.model_instance("file", purged=purged)

        return model

    assert not file_path_object.exists()

    # Trying to create the file where it can't be written
    create_model = model()

    await off_main_thread(lambda: project.compile(create_model))
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.failed
    )
    assert not file_path_object.exists()

    # Trying to delete the resource, the file still doesn't exist
    delete_model = model(purged=True)

    await off_main_thread(lambda: project.compile(delete_model))
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )
    assert not file_path_object.exists()


@pytest.mark.asyncio
async def test_update_failed(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    function_temp_dir: str,
    cache_agent_dir: str,
):
    file_path_object = Path(function_temp_dir) / Path("test-file.txt")

    provider = LocalProvider()
    local_file = LocalFile(
        "my file", str(file_path_object), "my original content", provider
    )

    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    def model(purged: bool = False) -> str:
        model = "import terraform"

        model += "\n\n" + provider.model_instance("provider")
        model += "\n\n" + local_file.model_instance("file", purged=purged)

        return model

    assert not file_path_object.exists()

    # Trying to create the file where it can't be written
    create_model = model()

    await off_main_thread(lambda: project.compile(create_model))
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )
    assert file_path_object.exists()

    # Trying to update the file and place it a forbidden folder
    forbidden_path_object = Path("/dev/test-file.txt")
    local_file.path = str(forbidden_path_object)
    update_model = model()

    await off_main_thread(lambda: project.compile(update_model))
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.failed
    )
    assert (
        not file_path_object.exists()
    ), "The provider should have removed the file from this location"
    assert (
        not forbidden_path_object.exists()
    ), "The provider should have failed to move the file to this location"

    # Triggering a repair, the state should be the bad one
    assert (await deploy(project, client, environment, full_deploy=True)).result[
        "model"
    ]["result"] == VersionState.failed
    assert not file_path_object.exists()
    assert not forbidden_path_object.exists()

    # Trying to delete the resource, the file still doesn't exist
    delete_model = model(purged=True)

    await off_main_thread(lambda: project.compile(delete_model))
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )
    assert not file_path_object.exists()
    assert not forbidden_path_object.exists()
