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
from providers.fortios.helpers.fortios_switchcontroller_managedswitch import (
    FortiosSwitchControllerManagedSwitch,
    SwitchPort,
)
from providers.fortios.helpers.fortios_system_interface import FortiosSystemInterface
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def assert_managed_switch_ports_configured(
    fortios_client: FortiosClient, managed_switch: FortiosSwitchControllerManagedSwitch
) -> bool:
    switch_config = fortios_client.get_switch_controller_managed_switch(
        managed_switch.switch_id
    )
    switch_ports = {port["port-name"]: port for port in switch_config["ports"]}

    for port in managed_switch.ports:
        assert port.name in switch_ports.keys()

        switch_port = switch_ports[port.name]
        assert switch_port["mac-addr"] == port.mac_addr
        assert switch_port["vlan"] == port.vlan


@pytest.mark.asyncio
async def test_ports_update(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: FortiosProvider,
    prefix: str,
    vlan_range: List[int],
    ip_range: IPNetwork,
    physical_switch: dict,
    physical_switch_id: str,
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
        parent="fortilink",
        vlan_id=vlan_range[0],
        provider=provider,
    )

    fortios_managed_switch = FortiosSwitchControllerManagedSwitch(
        name="my switch",
        switch_id=physical_switch_id,
        ports=[
            SwitchPort(
                name=port.get("name"), mac_addr=port.get("mac_addr"), vlan="default"
            )
            for port in physical_switch.get("ports")
        ],
        provider=provider,
    )

    def model() -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + fortios_system_interface.model_instance(
                "interface",
                False,
                provides=["switch"],
            )
            + "\n"
            + fortios_managed_switch.model_instance(
                "switch",
                False,
                requires=["interface"],
            )
        )
        LOGGER.debug(m)
        return m

    # The resource state is imported, it triggers an update
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_vap_action = await fortios_managed_switch.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_vap_action.change == Change.updated

    assert_managed_switch_ports_configured(
        fortios_client, managed_switch=fortios_managed_switch
    )

    # Update
    fortios_managed_switch.ports[0].vlan = fortios_system_interface.interface_name
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_vap_action = await fortios_managed_switch.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_vap_action.change == Change.updated

    assert_managed_switch_ports_configured(
        fortios_client, managed_switch=fortios_managed_switch
    )

    # No change
    delete_model = model()
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert last_vap_action == await fortios_managed_switch.get_last_action(
        client, environment, is_deployment_with_change
    )

    assert_managed_switch_ports_configured(
        fortios_client, managed_switch=fortios_managed_switch
    )
