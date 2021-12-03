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


class GitlabProvider(TerraformProvider):
    def __init__(self, base_url: str, token: str) -> None:
        """
        https://registry.terraform.io/providers/gitlabhq/gitlab/3.6.0/docs
        """
        super().__init__("gitlabhq", "gitlab", "3.6.0")
        self.base_url = base_url
        self.token = token

    @property
    def config(self) -> dict:
        return {
            "base_url": self.base_url,
            "token": self.token,
        }
