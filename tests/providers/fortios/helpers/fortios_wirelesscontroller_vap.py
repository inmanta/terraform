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


class FortiosWirelessControllerVap(TerraformResource):
    def __init__(
        self,
        name: str,
        vap_name: str,
        ssid: str,
        broadcast_ssid: bool,
        passphrase: str,
        ip_address: IPAddress,
        ip_mask: IPAddress,
        provider: FortiosProvider,
    ) -> None:
        super().__init__("fortios_wirelesscontroller_vap", name, provider)
        self.vap_name = vap_name
        self.ssid = ssid
        self.broadcast_ssid = broadcast_ssid
        self.passphrase = passphrase
        self.ip_address = ip_address
        self.ip_mask = ip_mask

    @property
    def config(self) -> dict:
        return dict(
            ip=f"{str(self.ip_address)} {str(self.ip_mask)}",
            name=self.vap_name,
            ssid=self.ssid,
            broadcast_ssid="enable" if self.broadcast_ssid else "disable",
            security="wap2-only-personal",
            encrypt="AES",
            passphrase=self.passphrase,
            quarantine="disable",
            schedule='"always"',
        )
