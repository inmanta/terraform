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
from netaddr.ip import IPNetwork
from providers.fortios.helpers.fortios_client import FortiosClient
from providers.fortios.helpers.fortios_provider import FortiosProvider
from providers.fortios.helpers.fortios_system_interface import FortiosSystemInterface
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def system_interface_is_deployed(
    fortios_client: FortiosClient, system_interface: FortiosSystemInterface
) -> bool:
    for interface in fortios_client.get_system_interfaces():
        if interface["name"] == system_interface.interface_name:
            return True

    return False


@pytest.mark.asyncio
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: FortiosProvider,
    prefix: str,
    ip_range: IPNetwork,
    vlan_range: List[int],
    physical_interface: str,
    fortios_client: FortiosClient,
    cache_agent_dir: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    interface_network = next(ip_range.subnet(24))

    fortios_system_interface = FortiosSystemInterface(
        name="my interface",
        interface_name=prefix + "-int1",
        description="This is a test description",
        interface_type="vlan",
        ip_address=next(interface_network.iter_hosts()),
        ip_mask=interface_network.netmask,
        parent=physical_interface,
        vlan_id=vlan_range[0],
        provider=provider,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + fortios_system_interface.model_instance("interface", purged)
        )
        LOGGER.debug(m)
        return m

    assert not system_interface_is_deployed(fortios_client, fortios_system_interface)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_interface_action = await fortios_system_interface.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_interface_action.change == Change.created

    assert system_interface_is_deployed(fortios_client, fortios_system_interface)

    # Update
    fortios_system_interface.description += " (updated)"
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_interface_action = await fortios_system_interface.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_interface_action.change == Change.updated

    assert system_interface_is_deployed(fortios_client, fortios_system_interface)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_interface_action = await fortios_system_interface.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_interface_action.change == Change.purged

    assert not system_interface_is_deployed(fortios_client, fortios_system_interface)
