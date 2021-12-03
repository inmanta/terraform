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


class FortiosFirewallPolicy(TerraformResource):
    def __init__(
        self,
        name: str,
        policy_name: str,
        action: str,
        dst_addr: str,
        dst_intf: str,
        src_addr: str,
        src_intf: str,
        services: List[str],
        provider: FortiosProvider,
    ) -> None:
        super().__init__("fortios_firewall_policy", name, provider)
        self.policy_name = policy_name
        self.action = action
        self.dst_addr = dst_addr
        self.dst_intf = dst_intf
        self.src_addr = src_addr
        self.src_intf = src_intf
        self.services = services

    @property
    def config(self) -> dict:
        return dict(
            name=self.policy_name,
            action=self.action,
            dstintf=[dict(name=self.dst_intf)],
            dstaddr=[dict(name=self.dst_addr)],
            srcintf=[dict(name=self.src_intf)],
            srcaddr=[dict(name=self.src_addr)],
            service=[dict(name=service) for service in self.services],
        )
