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
from netaddr import IPNetwork
from providers.checkpoint.helpers.checkpoint_provider import CheckpointProvider


class CheckpointManagementNetwork(TerraformResource):
    def __init__(
        self,
        name: str,
        subnet_name: str,
        subnet4: IPNetwork,
        provider: CheckpointProvider,
    ) -> None:
        super().__init__("checkpoint_management_network", name, provider)
        self.subnet_name = subnet_name
        self.subnet4 = subnet4

    @property
    def config(self) -> dict:
        return {
            "name": self.subnet_name,
            "subnet4": str(self.subnet4.ip),
            "mask_length4": self.subnet4.prefixlen,
        }
