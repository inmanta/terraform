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
from helpers.utils import deploy_model, is_deployment, is_deployment_with_change
from providers.docker.helpers.docker_network import DockerNetwork
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
    test_network: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    docker_client = docker.APIClient(base_url=provider.host)

    network = DockerNetwork(
        "test",
        provider=provider,
        network_name=test_network,
        attachable=False,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + network.model_instance("network", purged)
        )
        LOGGER.info(m)
        return m

    assert not docker_client.networks(test_network)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_action = await network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert docker_client.networks(test_network)

    # Import (1)
    # Import existing network when we don't know the state
    networks = docker_client.networks(test_network)
    assert len(networks) == 1
    network.terraform_id = networks[0]["Id"]
    await network.purge_state(client, environment)
    import_model = model()

    assert (
        await deploy_model(project, import_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await network.get_last_action(client, environment, is_deployment)
    assert last_action.change == Change.nochange
    last_state = await network.get_state(client, environment)
    assert last_state is not None

    # No change (1)
    # Import existing network when we know the state
    assert (
        await deploy_model(project, import_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await network.get_last_action(client, environment, is_deployment)
    assert last_action.change == Change.nochange
    last_state = await network.get_state(client, environment)
    assert last_state is not None

    # Repair (1)
    docker_client.remove_network(test_network)
    assert not docker_client.networks(test_network)

    assert (
        await deploy_model(project, create_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert docker_client.networks(test_network)

    # Delete (1)
    # We delete the network, we know its id and its state
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged
    last_state = await network.get_state(client, environment)
    assert last_state is None

    assert not docker_client.networks(test_network)

    # Restore network, with new id
    network.terraform_id = docker_client.create_network(test_network)["Id"]

    # Delete (2)
    # We delete the network, we know its id but not its state
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged
    last_state = await network.get_state(client, environment)
    assert last_state is None

    assert not docker_client.networks(test_network)
