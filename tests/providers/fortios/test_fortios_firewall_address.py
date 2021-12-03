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
from providers.fortios.helpers.fortios_firewall_address import FortiosFirewallAddress
from providers.fortios.helpers.fortios_provider import FortiosProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def firewall_address_is_deployed(
    fortios_client: FortiosClient, firewall_address: FortiosFirewallAddress
) -> bool:
    for address in fortios_client.get_firewall_addresses():
        if address["name"] == firewall_address.address_name:
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

    fortios_firewall_address = FortiosFirewallAddress(
        name="my firewall address",
        address_name=prefix + "-fa1",
        subnet=IPNetwork("192.168.1.1/26"),
        provider=provider,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + fortios_firewall_address.model_instance("address", purged)
        )
        LOGGER.debug(m)
        return m

    assert not firewall_address_is_deployed(fortios_client, fortios_firewall_address)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_firewall_service_action = await fortios_firewall_address.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_service_action.change == Change.created

    assert firewall_address_is_deployed(fortios_client, fortios_firewall_address)

    # Update
    fortios_firewall_address.subnet = fortios_firewall_address.subnet.next()
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_firewall_service_action = await fortios_firewall_address.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_service_action.change == Change.updated

    assert firewall_address_is_deployed(fortios_client, fortios_firewall_address)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_firewall_service_action = await fortios_firewall_address.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_service_action.change == Change.purged

    assert not firewall_address_is_deployed(fortios_client, fortios_firewall_address)
