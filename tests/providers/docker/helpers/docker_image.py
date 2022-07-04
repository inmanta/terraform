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
from providers.docker.helpers.docker_provider import DockerProvider


class DockerImage(TerraformResource):
    def __init__(
        self,
        name: str,
        provider: DockerProvider,
        send_event: bool = False,
        *,
        image_name: str,
        force_remove: Optional[bool] = None,
        keep_locally: Optional[bool] = None,
    ) -> None:
        super().__init__("docker_image", name, provider, send_event=send_event)

        self.image_name = image_name
        self.force_remove = force_remove
        self.keep_locally = keep_locally

    @property
    def config(self) -> dict:
        return {
            "name": self.image_name,
            "force_remove": self.force_remove,
            "keep_locally": self.keep_locally,
        }
