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
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def test_config_serialization(project: Project):
    model = """
        import terraform::config

        terraform::config::Block(
            name="root",
            attributes={"name": "Albert"},
            children=[
                terraform::config::Block(
                    name="children",
                    attributes={"name": "Bob", "age": 12},
                    nesting_mode="set",
                ),
                terraform::config::Block(
                    name="children",
                    attributes={"name": "Alice", "age": 14},
                    nesting_mode="set",
                ),
                terraform::config::Block(
                    name="pets",
                    attributes={"type": "dog"},
                    nesting_mode="dict",
                    key="Brutus",
                ),
                terraform::config::Block(
                    name="favorite_dishes",
                    attributes={"name": "Pizza"},
                    nesting_mode="list",
                    key="1",
                    children=[
                        terraform::config::Block(
                            name="content",
                            attributes={"salt": "yes", "sugar": "no"},
                        ),
                    ],
                ),
                terraform::config::Block(
                    name="favorite_dishes",
                    attributes={"name": "Pasta"},
                    nesting_mode="list",
                    key="2",
                )
            ],
            parent=null,
        )
    """
    project.compile(model, no_dedent=False)

    blocks = project.get_instances("terraform::config::Block")
    root_block = next(iter(block for block in blocks if block.name == "root"))

    assert root_block._config["name"] == "Albert"
    assert root_block._config["pets"] == {
        "Brutus": {
            "type": "dog",
        },
    }
    assert root_block._config["favorite_dishes"] == [
        {"name": "Pizza", "content": {"salt": "yes", "sugar": "no"}},
        {"name": "Pasta"},
    ]

    alice = {
        "name": "Alice",
        "age": 14,
    }
    bob = {
        "name": "Bob",
        "age": 12,
    }
    assert root_block._config["children"] == [alice, bob] or root_block._config[
        "children"
    ] == [bob, alice]


def test_deprecated_config(project: Project) -> None:
    model = """
        import terraform::config

        terraform::config::Block(
            name="root",
            attributes={},
            deprecated=true,
            parent=null,
        )
    """

    # Compile a first time to setup the project
    project.compile(model, no_dedent=False)

    # Compile a second time in a separate process to catch the logs
    result = subprocess.Popen(
        [sys.executable, "-m", "inmanta.app", "-v", "compile"],
        cwd=project._test_project_dir,
        encoding="utf-8",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = result.communicate()
    assert result.returncode == 0, stderr
    assert stdout in [
        (
            "inmanta_plugins.terraformWARNING The usage of config 'root' at "
            f"{project._test_project_dir}/main.cf:3 is deprecated\n"
        ),
        (
            # prior to https://github.com/inmanta/inmanta-core/commit/64798acc8abcc3b7b31ab657f1d04e1974209d6f
            "inmanta_plugins.terraformWARNING The usage of config 'root' at "
            "./main.cf:3 is deprecated\n"
        ),
    ]


@pytest.mark.terraform_provider_local
async def test_block_config(
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
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={"hashicorp-local-2.1.0": "localhost"},
        code_loader=False,
        agent_names=["hashicorp-local-2.1.0"],
    )

    file_path_object = Path(function_temp_dir) / Path("test-file.txt")

    model = f"""
        import terraform
        import terraform::config

        # Overwritting agent config to disable autostart.  Agents have to be started
        # manually in the tests.
        prov_agent_config = std::AgentConfig(
            autostart=false,
            agentname="hashicorp-local-2.1.0",
            uri="local:",
            provides=prov,
        )

        prov = terraform::Provider(
            namespace="hashicorp",
            type="local",
            version="2.1.0",
            alias="",
            auto_agent=false,
            agent_config=prov_agent_config,
            manual_config=false,
            root_config=terraform::config::Block(
                name="root",
                attributes={{}},
            ),
        )

        res = terraform::Resource(
            type="local_file",
            name="test",
            purged=false,
            send_event=true,
            provider=prov,
            requires=prov,
            manual_config=false,
            root_config=terraform::config::Block(
                name="root",
                attributes={{
                    "filename": "{file_path_object}",
                    "content": "test",
                }},
            ),
        )
    """

    assert not file_path_object.exists()

    # Create
    assert (
        await deploy_model(project, model, client, environment) == VersionState.success
    )

    assert file_path_object.exists()
    assert file_path_object.read_text("utf-8") == "test"
