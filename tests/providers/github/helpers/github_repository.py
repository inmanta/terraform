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
from providers.github.helpers.github_provider import GithubProvider


class GithubRepository(TerraformResource):
    def __init__(
        self,
        name: str,
        repository_name: str,
        description: str,
        provider: GithubProvider,
        template_owner: str = "fergusmacd",
        template_repository: str = "template-repo-terraform",
    ) -> None:
        super().__init__("github_repository", name, provider)
        self.repository_name = repository_name
        self.description = description
        self.template_owner = template_owner
        self.template_repository = template_repository

    @property
    def config(self) -> dict:
        return {
            "name": self.repository_name,
            "description": self.description,
            "visibility": "public",
            "template": [
                {
                    "owner": self.template_owner,
                    "repository": self.template_repository,
                },
            ],
        }
