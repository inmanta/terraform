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
from typing import List

from helpers.terraform_resource import TerraformResource
from providers.fortios.helpers.fortios_provider import FortiosProvider


class SwitchPort:
    def __init__(self, name: str, mac_addr: str, vlan: str) -> None:
        self.name = name
        self.mac_addr = mac_addr
        self.vlan = vlan


class FortiosSwitchControllerManagedSwitch(TerraformResource):
    def __init__(
        self,
        name: str,
        switch_id: str,
        ports: List[SwitchPort],
        provider: FortiosProvider,
    ) -> None:
        super().__init__(
            "fortios_switchcontroller_managedswitch", name, provider, switch_id
        )
        self.switch_id = switch_id
        self.ports = ports

    @property
    def config(self) -> dict:
        return dict(
            switch_id=self.switch_id,
            fsw_wan1_admin="enable",
            fsw_wan1_peer="fortilink",
            type="physical",
            ports=[
                dict(
                    switch_id=self.switch_id,
                    speed_mask=207,
                    port_name=port.name,
                    vlan=port.vlan,
                    export_to="root",
                    type="physical",
                    mac_addr=port.mac_addr,
                    allowed_vlans=[dict(vlan_name="quarantine")],
                    untagged_vlans=[dict(vlan_name="quarantine")],
                )
                for port in self.ports
            ],
        )
