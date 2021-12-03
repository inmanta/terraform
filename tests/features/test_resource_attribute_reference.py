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
import hashlib
import logging
from pathlib import Path
from textwrap import dedent
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, is_deployment_with_change, off_main_thread
from providers.local.helpers.local_file import LocalFile
from providers.local.helpers.local_provider import LocalProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
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
    file_duplicate_path_object = Path(function_temp_dir) / Path(
        "test-file-duplicate.txt"
    )

    provider = LocalProvider()
    local_file = LocalFile(
        "my file",
        str(file_path_object),
        "my original content",
        provider,
        send_event=True,
    )

    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    def file_duplicate(
        purged: bool, original_file_reference: str, provider_reference: str
    ) -> str:
        requires = original_file_reference if not purged else "[]"
        provides = original_file_reference if purged else "[]"
        return dedent(
            f"""
                file_id = terraform::Resource(
                    type="local_file",
                    name="file id",
                    config={{
                        "filename": "{str(file_duplicate_path_object)}",
                        "content": terraform::get_resource_attribute_ref(
                            {original_file_reference},
                            ["id"],
                        ),
                    }},
                    purged={str(purged).lower()},
                    provider={provider_reference},
                    requires={requires},
                    provides={provides},
                )
            """.strip(
                "\n"
            )
        )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + local_file.model_instance(
                "file",
                purged,
                provides=["file_id"] if not purged else [],
                requires=["file_id"] if purged else [],
            )
            + "\n"
            + file_duplicate(purged, "file", "provider")
            + "\n"
        )
        LOGGER.info(m)
        return m

    assert not file_path_object.exists()
    assert not file_duplicate_path_object.exists()

    # Create
    create_model = model()
    await off_main_thread(lambda: project.compile(create_model))
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )
    last_local_file_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_local_file_action.change == Change.created

    assert file_path_object.exists()
    assert file_duplicate_path_object.exists()
    assert file_path_object.read_text() == local_file.content
    assert (
        file_duplicate_path_object.read_text()
        == hashlib.sha1(local_file.content.encode("utf-8")).hexdigest()
    )

    # Update
    local_file.content += " (updated)"
    update_model = model()
    await off_main_thread(lambda: project.compile(update_model))
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )
    last_local_file_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_local_file_action.change == Change.updated

    assert file_path_object.exists()
    assert file_duplicate_path_object.exists()
    assert file_path_object.read_text() == local_file.content
    assert (
        file_duplicate_path_object.read_text()
        == hashlib.sha1(local_file.content.encode("utf-8")).hexdigest()
    )

    # Delete
    delete_model = model(True)
    await off_main_thread(lambda: project.compile(delete_model))
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )
    last_local_file_action = await local_file.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_local_file_action.change == Change.purged

    assert not file_path_object.exists()
    assert not file_duplicate_path_object.exists()
