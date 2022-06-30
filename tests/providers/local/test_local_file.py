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
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.terraform_provider_local
def test_standalone(
    project: Project,
    provider: LocalProvider,
    function_temp_dir: str,
    cache_agent_dir: str,
) -> None:
    """
    The purpose of this test is to make sure that the terraform helpers can be
    used without an inmanta handler (in the generator for example).
    We still import the project fixture so that the plugins get installed in
    the inmanta_plugins package.
    """
    from inmanta_plugins.terraform.tf.terraform_provider import TerraformProvider
    from inmanta_plugins.terraform.tf.terraform_provider_installer import (
        ProviderInstaller,
    )
    from inmanta_plugins.terraform.tf.terraform_resource_client import (
        TerraformResourceClient,
    )
    from inmanta_plugins.terraform.tf.terraform_resource_state import (
        TerraformResourceState,
    )

    cwd = Path(function_temp_dir)

    provider_installer = ProviderInstaller(
        namespace=provider.namespace,
        type=provider.type,
        version=provider.version,
    )
    provider_installer.resolve()
    provider_installer.download(str(cwd / "download.zip"))
    provider_path = provider_installer.install(str(cwd))

    resource_state = TerraformResourceState(
        type_name="local_file",
        resource_id="file",
    )

    generate_file_path = cwd / "file.txt"

    with TerraformProvider(
        provider_path=provider_path,
        log_file_path=str(cwd / "provider.log"),
    ) as p:
        LOGGER.debug(p.schema)
        assert not p.ready
        p.configure({})
        assert p.ready

        client = TerraformResourceClient(
            provider=p,
            resource_state=resource_state,
            logger=LOGGER,
        )
        LOGGER.debug(client.resource_schema)

        assert not generate_file_path.exists()

        client.create_resource(
            {
                "filename": str(generate_file_path),
                "content": "Hello World",
            }
        )

        assert generate_file_path.exists()
        assert generate_file_path.read_text() == "Hello World"

        client.delete_resource()

        assert not generate_file_path.exists()

    assert not p.ready


@pytest.mark.terraform_provider_local
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: LocalProvider,
    function_temp_dir: str,
    cache_agent_dir: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    file_path_object = Path(function_temp_dir) / Path("test-file.txt")

    local_file = LocalFile(
        "my file", str(file_path_object), "my original content", provider
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance("file", purged)
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert file_path_object.exists()
    assert file_path_object.read_text("utf-8") == local_file.content

    # Update
    local_file.content = local_file.content + " (updated)"
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.updated

    assert file_path_object.exists()
    assert file_path_object.read_text("utf-8") == local_file.content

    # Repair
    file_path_object.unlink()

    assert (
        await deploy_model(project, update_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    last_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert file_path_object.exists()
    assert file_path_object.read_text("utf-8") == local_file.content

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged

    assert not file_path_object.exists()
