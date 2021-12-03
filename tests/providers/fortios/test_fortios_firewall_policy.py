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
from providers.fortios.helpers.fortios_firewall_policy import FortiosFirewallPolicy
from providers.fortios.helpers.fortios_firewallservice_custom import (
    FortiosFirewallServiceCustom,
)
from providers.fortios.helpers.fortios_provider import FortiosProvider
from providers.fortios.helpers.fortios_system_interface import FortiosSystemInterface
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def firewall_policy_is_deployed(
    fortios_client: FortiosClient, firewall_policy: FortiosFirewallPolicy
) -> bool:
    for policy in fortios_client.get_firewall_policies():
        if policy["name"] == firewall_policy.policy_name:
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

    fortios_firewall_address_src = FortiosFirewallAddress(
        name="my firewall address",
        address_name=prefix + "-fa1",
        subnet=IPNetwork("192.168.1.1/26"),
        provider=provider,
    )

    fortios_firewall_address_dst = FortiosFirewallAddress(
        name="my other firewall address",
        address_name=prefix + "-fa2",
        subnet=IPNetwork("192.168.2.1/26"),
        provider=provider,
    )

    interface_networks = ip_range.subnet(24)
    interface_network = next(interface_networks)

    fortios_system_interface_src = FortiosSystemInterface(
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

    interface_network = next(interface_networks)

    fortios_system_interface_dst = FortiosSystemInterface(
        name="my other interface",
        interface_name=prefix + "-int2",
        description="This is a test description",
        interface_type="vlan",
        ip_address=next(interface_network.iter_hosts()),
        ip_mask=interface_network.netmask,
        parent=physical_interface,
        vlan_id=vlan_range[1],
        provider=provider,
    )

    fortios_firewall_service_1 = FortiosFirewallServiceCustom(
        name="my firewall service",
        service_name=prefix + "-fsc1",
        port_range=(456, 465),
        visible=True,
        provider=provider,
    )

    fortios_firewall_service_2 = FortiosFirewallServiceCustom(
        name="my other firewall service",
        service_name=prefix + "-fsc2",
        port_range=(567, 576),
        visible=True,
        provider=provider,
    )

    fortios_firewall_policy = FortiosFirewallPolicy(
        name="my firewall policy",
        policy_name=prefix + "-fp1",
        action="accept",
        dst_addr=fortios_firewall_address_dst.address_name,
        src_addr=fortios_firewall_address_src.address_name,
        dst_intf=fortios_system_interface_dst.interface_name,
        src_intf=fortios_system_interface_src.interface_name,
        services=[fortios_firewall_service_1.service_name],
        provider=provider,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + fortios_firewall_address_src.model_instance(
                "address_src",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_firewall_address_dst.model_instance(
                "address_dst",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_system_interface_src.model_instance(
                "interface_src",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_system_interface_dst.model_instance(
                "interface_dst",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_firewall_service_1.model_instance(
                "service_1",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_firewall_service_2.model_instance(
                "service_2",
                purged,
                provides=["policy"] if not purged else [],
                requires=["policy"] if purged else [],
            )
            + "\n"
            + fortios_firewall_policy.model_instance(
                "policy",
                purged,
                requires=[
                    "address_src",
                    "address_dst",
                    "interface_src",
                    "interface_dst",
                    "service_1",
                    "service_2",
                ]
                if not purged
                else [],
                provides=[
                    "address_src",
                    "address_dst",
                    "interface_src",
                    "interface_dst",
                    "service_1",
                    "service_2",
                ]
                if purged
                else [],
            )
        )
        LOGGER.debug(m)
        return m

    assert not firewall_policy_is_deployed(fortios_client, fortios_firewall_policy)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_firewall_policy_action = await fortios_firewall_policy.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_policy_action.change == Change.created

    assert firewall_policy_is_deployed(fortios_client, fortios_firewall_policy)

    # Update
    fortios_firewall_policy.services.append(fortios_firewall_service_2.service_name)
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_firewall_policy_action = await fortios_firewall_policy.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_policy_action.change == Change.updated

    assert firewall_policy_is_deployed(fortios_client, fortios_firewall_policy)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_firewall_policy_action = await fortios_firewall_policy.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_firewall_policy_action.change == Change.purged

    assert not firewall_policy_is_deployed(fortios_client, fortios_firewall_policy)
