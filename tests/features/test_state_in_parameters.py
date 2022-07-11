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
from helpers.utils import deploy_model
from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import VersionState
from inmanta.protocol.endpoints import Client
from inmanta.resources import Resource
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.terraform_provider_local
async def test_store(
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
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance("file", purged)
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()

    # Create
    create_model = model()

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is not None
    ), "A state should have been set by now"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"


@pytest.mark.terraform_provider_local
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
    """
    This test tries to create a file in a location that will fail.  The creation should fail and we
    should see the param containing the desired state being created anyway.
    """
    file_path_object = Path("/dev/test-file.txt")

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
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance("file", purged)
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()

    # Create
    create_model = model()

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.failed
    )
    assert not file_path_object.exists()

    param = await local_file.get_state(client, environment)
    assert param is None, "A null state should not be deployed"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"

    assert not file_path_object.exists()


@pytest.mark.terraform_provider_local
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
    """
    This test creates a file, then update it by moving it in a forbidden location.  The update should fail
    but the param containing the state should be updated anyway, showing the current file state, which is null.
    """
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
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance("file", purged)
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()

    # Create
    create_model = model()

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    param = await local_file.get_state(client, environment)
    assert param is not None, "A state should have been set by now"

    # Update
    forbidden_path_object = Path("/dev/test-file.txt")
    local_file.path = str(forbidden_path_object)
    update_model = model()

    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.failed
    )

    param = await local_file.get_state(client, environment)
    assert param is None, (
        "Moving a file actually means removing the old one and creating the new one.  "
        "If we failed to move the file to the new location, we should still manage to "
        "delete the previous one (and remove its state with it).  We don't have a new "
        "state as there is no new file."
    )

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"
