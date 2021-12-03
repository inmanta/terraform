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

import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from netaddr import IPNetwork
from providers.checkpoint.common import manual_publish
from providers.checkpoint.helpers.checkpoint_client import CheckpointClient
from providers.checkpoint.helpers.checkpoint_management_host import (
    CheckpointManagementHost,
)
from providers.checkpoint.helpers.checkpoint_management_network import (
    CheckpointManagementNetwork,
)
from providers.checkpoint.helpers.checkpoint_provider import CheckpointProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def host_is_deployed(checkpoint_client: CheckpointClient, name: str) -> bool:
    checkpoint_client.login()
    host = checkpoint_client.show_host(name)
    checkpoint_client.logout()
    return host is not None


@pytest.mark.asyncio
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: CheckpointProvider,
    checkpoint_client: CheckpointClient,
    prefix: str,
    ip_range: IPNetwork,
    cache_agent_dir: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    ips = ip_range.iter_hosts()

    checkpoint_management_network = CheckpointManagementNetwork(
        "my network", prefix + "-network", ip_range, provider
    )
    checkpoint_management_host = CheckpointManagementHost(
        "my host", prefix + "-host", next(ips), provider
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + checkpoint_management_network.model_instance("network", purged)
            + "\n"
            + checkpoint_management_host.model_instance("host", purged)
        )
        LOGGER.debug(m)
        return m

    assert not host_is_deployed(checkpoint_client, checkpoint_management_host.host_name)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_network_action = await checkpoint_management_network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_network_action.change == Change.created

    last_host_action = await checkpoint_management_host.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_host_action.change == Change.created

    manual_publish(checkpoint_client)

    assert host_is_deployed(checkpoint_client, checkpoint_management_host.host_name)

    # Update
    checkpoint_management_host.ip_address = next(ips)
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    assert last_network_action == await checkpoint_management_network.get_last_action(
        client, environment, is_deployment_with_change
    )

    last_host_action = await checkpoint_management_host.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_host_action.change == Change.updated

    manual_publish(checkpoint_client)

    assert host_is_deployed(checkpoint_client, checkpoint_management_host.host_name)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_network_action = await checkpoint_management_network.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_network_action.change == Change.purged

    last_host_action = await checkpoint_management_host.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_host_action.change == Change.purged

    manual_publish(checkpoint_client)

    assert not host_is_deployed(checkpoint_client, checkpoint_management_host.host_name)
