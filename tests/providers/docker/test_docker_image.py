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
from typing import Callable, Dict, List, Optional
from uuid import UUID

import docker
import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from providers.docker.helpers.docker_image import DockerImage
from providers.docker.helpers.docker_provider import DockerProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.terraform_provider_docker
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: DockerProvider,
    cache_agent_dir: str,
    hello_world_image: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    docker_client = docker.APIClient(base_url=provider.host)

    image = DockerImage(
        "hello-world",
        provider=provider,
        image_name=hello_world_image,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + image.model_instance("image", purged)
        )
        LOGGER.info(m)
        return m

    assert not docker_client.images(hello_world_image)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_action = await image.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert docker_client.images(hello_world_image)

    # Repair
    docker_client.remove_image(hello_world_image)
    assert not docker_client.images(hello_world_image)

    assert (
        await deploy_model(project, create_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await image.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert docker_client.images(hello_world_image)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_action = await image.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged

    assert not docker_client.images(hello_world_image)
