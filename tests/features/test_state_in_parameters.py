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
from inmanta.resources import Id, Resource
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


async def get_param(
    environment: str, client: Client, param_id: str, resource_id: str
) -> Optional[str]:
    result = await client.get_param(
        tid=environment,
        id=param_id,
        resource_id=resource_id,
    )
    if result.code == 200:
        return result.result["parameter"]["value"]

    if result.code == 404:
        return None

    if result.code == 503:
        # In our specific case, we might get a 503 if the parameter is not set yet
        # https://github.com/inmanta/inmanta-core/blob/5bfe60683f7e21657794eaf222f43e4c53540bb5/src/inmanta/server/agentmanager.py#L799
        return None

    assert False, f"Unexpected response from server: {result.code}, {result.message}"


@pytest.mark.asyncio
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
    from inmanta_plugins.terraform.helpers.const import (
        TERRAFORM_RESOURCE_STATE_PARAMETER,
    )

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

    resource_id = Id.resource_str(resource.id)

    async def get_param_short() -> Optional[str]:
        return await get_param(
            environment=environment,
            client=client,
            param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
            resource_id=resource_id,
        )

    assert (
        await get_param_short() is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    assert await get_param_short() is not None, "A state should have been set by now"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await get_param_short() is None
    ), "The state should have been removed, but wasn't"


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
    """
    This test tries to create a file in a location that will fail.  The creation should fail and we
    should see the param containing the desired state being created anyway.
    """
    from inmanta_plugins.terraform.helpers.const import (
        TERRAFORM_RESOURCE_STATE_PARAMETER,
    )

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

    resource_id = Id.resource_str(resource.id)

    async def get_param_short() -> Optional[str]:
        return await get_param(
            environment=environment,
            client=client,
            param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
            resource_id=resource_id,
        )

    assert (
        await get_param_short() is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.failed
    )
    assert not file_path_object.exists()

    param = await get_param_short()
    assert param is not None, "A state should have been set by now"
    assert param == "null", "The file isn't deployed, his state is null"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await get_param_short() is None
    ), "The state should have been removed, but wasn't"

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
    """
    This test creates a file, then update it by moving it in a forbidden location.  The update should fail
    but the param containing the state should be updated anyway, showing the current file state, which is null.
    """
    from inmanta_plugins.terraform.helpers.const import (
        TERRAFORM_RESOURCE_STATE_PARAMETER,
    )

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

    resource_id = Id.resource_str(resource.id)

    async def get_param_short() -> Optional[str]:
        return await get_param(
            environment=environment,
            client=client,
            param_id=TERRAFORM_RESOURCE_STATE_PARAMETER,
            resource_id=resource_id,
        )

    assert (
        await get_param_short() is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    assert await get_param_short() is not None, "A state should have been set by now"

    # Update
    forbidden_path_object = Path("/dev/test-file.txt")
    local_file.path = str(forbidden_path_object)
    update_model = model()

    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.failed
    )
    param = await get_param_short()
    assert param is not None, "The state should still be there"
    assert param == "null", "The state should be empty as the new file couldn't deploy"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await get_param_short() is None
    ), "The state should have been removed, but wasn't"
