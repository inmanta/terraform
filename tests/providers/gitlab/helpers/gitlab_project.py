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
from typing import Optional

from helpers.terraform_resource import TerraformResource
from providers.gitlab.helpers.gitlab_provider import GitlabProvider


class GitlabProject(TerraformResource):
    def __init__(
        self,
        name: str,
        project_name: str,
        description: str,
        provider: GitlabProvider,
        namespace_id: Optional[int] = None,
    ) -> None:
        super().__init__("gitlab_project", name, provider)
        self.project_name = project_name
        self.namespace_id = namespace_id
        self.description = description

    @property
    def config(self) -> dict:
        return {
            "name": self.project_name,
            "description": self.description,
            "namespace_id": self.namespace_id,
        }
