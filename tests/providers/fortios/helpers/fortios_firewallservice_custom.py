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
from typing import Tuple

from helpers.terraform_resource import TerraformResource
from providers.fortios.helpers.fortios_provider import FortiosProvider


class FortiosFirewallServiceCustom(TerraformResource):
    def __init__(
        self,
        name: str,
        service_name: str,
        port_range: Tuple[int, int],
        visible: bool,
        provider: FortiosProvider,
    ) -> None:
        super().__init__("fortios_firewallservice_custom", name, provider)
        self.service_name = service_name
        self.port_range = port_range
        self.visibility = "enable" if visible else "disable"

    @property
    def config(self) -> dict:
        return dict(
            name=self.service_name,
            protocol="TCP",
            tcp_portrange=f"{self.port_range[0]}-{self.port_range[1]}",
            visibility=self.visibility,
        )
