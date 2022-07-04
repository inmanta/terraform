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
import docker
import pytest
from providers.docker.helpers.docker_provider import DockerProvider


@pytest.fixture(scope="package")
def provider() -> DockerProvider:
    return DockerProvider()


@pytest.fixture
def hello_world_image() -> str:
    image_name = "hello-world:latest"
