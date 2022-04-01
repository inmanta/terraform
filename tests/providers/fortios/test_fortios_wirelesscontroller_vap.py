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
import random
import string
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from netaddr.ip import IPNetwork
from providers.fortios.helpers.fortios_client import FortiosClient
from providers.fortios.helpers.fortios_provider import FortiosProvider
from providers.fortios.helpers.fortios_system_interface import FortiosSystemInterface
from providers.fortios.helpers.fortios_wirelesscontroller_vap import (
    FortiosWirelessControllerVap,
)
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def wireless_controller_vap_is_deployed(
    fortios_client: FortiosClient, wireless_controller_vap: FortiosWirelessControllerVap
) -> bool:
    for vap in fortios_client.get_wireless_controller_vap():
        if vap["name"] == wireless_controller_vap.vap_name:
            return True

    return False


@pytest.mark.terraform_provider_fortios
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
    network_addresses = interface_network.iter_hosts()

    fortios_wireless_controller_vap = FortiosWirelessControllerVap(
        name="my vap",
        vap_name=prefix + "-vap1",
        ssid=prefix + " vap1",
        broadcast_ssid=False,
        passphrase="".join(random.choice(string.hexdigits) for _ in range(10)),
        ip_address=next(network_addresses),
        ip_mask=interface_network.netmask,
        provider=provider,
    )

    fortios_system_interface = FortiosSystemInterface(
        name="my interface",
        interface_name=prefix + "-int1",
        description="This is a test description",
        interface_type="vlan",
        ip_address=next(network_addresses),
        ip_mask=interface_network.netmask,
        parent=fortios_wireless_controller_vap.vap_name,
        vlan_id=vlan_range[0],
        provider=provider,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + fortios_wireless_controller_vap.model_instance(
                "vap",
                purged,
                provides=["interface"] if not purged else [],
                requires=["interface"] if purged else [],
            )
            + "\n"
            + fortios_system_interface.model_instance(
                "interface",
                purged,
                provides=["vap"] if purged else [],
                requires=["vap"] if not purged else [],
            )
        )
        LOGGER.debug(m)
        return m

    assert not wireless_controller_vap_is_deployed(
        fortios_client, fortios_wireless_controller_vap
    )

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_vap_action = await fortios_wireless_controller_vap.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_vap_action.change == Change.created

    assert wireless_controller_vap_is_deployed(
        fortios_client, fortios_wireless_controller_vap
    )

    # Update
    fortios_wireless_controller_vap.ssid += " (updated)"
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_vap_action = await fortios_wireless_controller_vap.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_vap_action.change == Change.updated

    assert wireless_controller_vap_is_deployed(
        fortios_client, fortios_wireless_controller_vap
    )

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_vap_action = await fortios_wireless_controller_vap.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_vap_action.change == Change.purged

    assert not wireless_controller_vap_is_deployed(
        fortios_client, fortios_wireless_controller_vap
    )
