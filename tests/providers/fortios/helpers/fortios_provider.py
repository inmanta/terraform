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
from helpers.terraform_provider import TerraformProvider


class FortiosProvider(TerraformProvider):
    def __init__(self, hostname: str, token: str) -> None:
        """
        https://registry.terraform.io/providers/fortinetdev/fortios/1.11.0/docs
        """
        super().__init__("fortinetdev", "fortios", "1.11.0")
        self.hostname = hostname
        self.token = token

    @property
    def config(self) -> dict:
        return dict(
            hostname=self.hostname,
            token=self.token,
            insecure=True,
        )
