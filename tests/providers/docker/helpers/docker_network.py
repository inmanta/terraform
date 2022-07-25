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
import ipaddress
from typing import Optional

from helpers.terraform_resource import TerraformResource
from providers.docker.helpers.docker_provider import DockerProvider


class DockerNetwork(TerraformResource):
    def __init__(
        self,
        name: str,
        provider: DockerProvider,
        terraform_id: Optional[str] = None,
        send_event: bool = False,
        *,
        network_name: str,
        gateway: Optional[ipaddress.IPv4Interface] = None,
        driver: Optional[str] = None,
        internal: Optional[bool] = None,
        attachable: Optional[bool] = None,
        check_duplicate: Optional[bool] = None,
    ) -> None:
        super().__init__(
            "docker_network",
            name,
            provider,
            terraform_id=terraform_id,
            send_event=send_event,
        )

        self.network_name = network_name
        self.gateway = gateway
        self.driver = driver
        self.internal = internal
        self.attachable = attachable
        self.check_duplicate = check_duplicate

    @property
    def config(self) -> dict:
        return {
            "name": self.network_name,
            "attachable": self.attachable,
            "check_duplicate": self.check_duplicate,
            "driver": self.driver,
            "internal": self.internal,
            "ipam_config": [
                {
                    "gateway": str(self.gateway.ip),
                    "ip_range": str(self.gateway.network),
                    "subnet": str(self.gateway.network),
                },
            ]
            if self.gateway is not None
            else None,
        }
