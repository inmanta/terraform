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
from textwrap import dedent
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, off_main_thread
from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_plugin(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    function_temp_dir: str,
    cache_agent_dir: str,
):
    file_path_object = Path(function_temp_dir) / Path("test-file.txt")

    provider = LocalProvider()
    local_file = LocalFile(
        "my file", str(file_path_object), "my original content", provider
    )

    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    def dummy_entity() -> str:
        return dedent(
            """
            entity Dummy:
                bool id_unknown
            end
            implement Dummy using std::none
            """.strip(
                "\n"
            )
        )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance("file", purged)
            + "\n"
            + dummy_entity()
            + "\n"
            + 'Dummy(id_unknown=std::is_unknown(terraform::get_resource_attribute(file, ["id"])))'
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()

    # Create
    create_model = model()

    await off_main_thread(lambda: project.compile(create_model))
    dummy_instance = project.get_instances("__config__::Dummy")[0]
    assert (
        dummy_instance.id_unknown
    ), "The id of the file is supposed to be unknown, but isn't"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    await off_main_thread(lambda: project.compile(create_model))
    dummy_instance = project.get_instances("__config__::Dummy")[0]
    assert (
        not dummy_instance.id_unknown
    ), "The id of the file is supposed to be known, but isn't"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    await off_main_thread(lambda: project.compile(delete_model))
    dummy_instance = project.get_instances("__config__::Dummy")[0]
    assert (
        dummy_instance.id_unknown
    ), "The id of the file is supposed to be unknown, but isn't"
