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
from helpers.terraform_resource import TerraformResource
from netaddr import IPAddress
from providers.fortios.helpers.fortios_provider import FortiosProvider


class FortiosSystemInterface(TerraformResource):
    def __init__(
        self,
        name: str,
        interface_name: str,
        description: str,
        interface_type: str,
        ip_address: IPAddress,
        ip_mask: IPAddress,
        parent: str,
        vlan_id: int,
        provider: FortiosProvider,
    ) -> None:
        super().__init__("fortios_system_interface", name, provider)
        self.interface_name = interface_name
        self.description = description
        self.interface_type = interface_type
        self.ip_address = ip_address
        self.ip_mask = ip_mask
        self.parent = parent
        self.vlan_id = vlan_id

    @property
    def config(self) -> dict:
        return dict(
            ip=f"{str(self.ip_address)} {str(self.ip_mask)}",
            name=self.interface_name,
            type=self.interface_type,
            vdom="root",
            mode="static",
            interface=self.parent,
            vlanid=self.vlan_id,
            description=self.description,
        )
