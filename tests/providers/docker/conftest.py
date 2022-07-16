"""
    Copyright 2022 Inmanta

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
from pathlib import Path

import docker
import pytest
from providers.docker.helpers.docker_provider import DockerProvider
from pytest_inmanta.test_parameter import path_parameter

docker_socket_path = path_parameter.PathTestParameter(
    "--docker-sock-path",
    environment_variable="DOCKER_SOCKET_PATH",
    usage="The path to the docker socket on the host",
    default=Path("/var/run/docker.sock"),
    exists=True,
)


@pytest.fixture(scope="package")
def provider(request: pytest.FixtureRequest) -> DockerProvider:
    return DockerProvider(
        host="unix://" + str(docker_socket_path.resolve(request.config))
    )


@pytest.fixture
def hello_world_image(provider: DockerProvider) -> str:
    image_name = "docker.io/library/hello-world"

    client = docker.APIClient(base_url=provider.host)
    for image in client.images(image_name):
        client.remove_image(image["Id"])

    yield image_name

    for image in client.images(image_name):
        client.remove_image(image["Id"])


@pytest.fixture
def test_network(provider: DockerProvider) -> str:
    network_name = "terraform_test_net"

    client = docker.APIClient(base_url=provider.host)
    for network in client.networks(network_name):
        client.remove_network(network["Id"])

    yield network_name

    for network in client.networks(network_name):
        client.remove_network(network["Id"])
