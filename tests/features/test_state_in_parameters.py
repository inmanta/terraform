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
import datetime
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

import inmanta.execute.proxy
from inmanta.agent.agent import Agent
from inmanta.const import VersionState
from inmanta.protocol.endpoints import Client
from inmanta.resources import Resource
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


@pytest.mark.terraform_provider_local
@pytest.mark.asyncio
async def test_store(
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

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )
    entity = project.get_instances(local_file.resource_type)[0]

    from inmanta_plugins.terraform import dict_hash

    config_hash = dict_hash(entity.config)

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    state = await local_file.get_state(client, environment)
    assert state is not None, "A state should have been set by now"
    assert state["config_hash"] == config_hash

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"


@pytest.mark.terraform_provider_local
@pytest.mark.asyncio
async def test_create_failed(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    cache_agent_dir: str,
):
    """
    This test tries to create a file in a location that will fail.  The creation should fail and we
    should see the param containing the desired state being created anyway.
    """
    file_path_object = Path("/dev/test-file.txt")

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

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.failed
    )
    assert not file_path_object.exists()

    param = await local_file.get_state(client, environment)
    assert param is None, "A null state should not be deployed"

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"

    assert not file_path_object.exists()


@pytest.mark.terraform_provider_local
@pytest.mark.asyncio
async def test_state_upgrade(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    function_temp_dir: str,
    cache_agent_dir: str,
) -> None:
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

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    param = await local_file.get_state(client, environment)
    assert param is not None, "A state should have been set by now"
    assert param["__state_dict_generation"] == "Albatross"

    # Let's overwrite the state with the old format now
    await local_file.set_state(client, environment, param["state"])

    # We run the deploy once more, it should update the state
    assert (
        await deploy_model(project, create_model, client, environment, full_deploy=True)
        == VersionState.success
    )

    param = await local_file.get_state(client, environment)
    assert param is not None, "A state should have been set by now"
    assert param["__state_dict_generation"] == "Albatross"


@pytest.mark.terraform_provider_local
@pytest.mark.asyncio
async def test_state_extraction(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    function_temp_dir: str,
) -> None:
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

    base_model = (
        "\nimport terraform\nimport terraform::config\n\n"
        + provider.model_instance("provider")
        + "\n"
    )
    file_model = """
        file = terraform::Resource(
            type="local_file",
            name="my file",
            terraform_id=null,
            purged=false,
            manual_config=false,
            send_event=false,
            provider=provider,
        )
    """
    base_model += dedent(file_model.strip("\n"))

    real_config = """
        file.root_config = terraform::config::Block(
            name=null,
            attributes={
                "filename": "/tmp/pytest-of-guillaume/pytest-0/session0/function/test-file.txt",
                "content": "my original content",
            },
        )
    """
    create_model = base_model + dedent(real_config.strip("\n"))

    await off_main_thread(lambda: project.compile(create_model))
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    param = await local_file.get_state(client, environment)
    assert param is not None, "A state should have been set by now"

    # Access the state of the file in the model
    state_model = """
        entity Data:
            string info
        end
        implement Data using std::none

        id = file.root_config._state["id"]

        Data(info=id)
    """
    state_model = dedent(state_model.strip("\n"))

    # Compile this simple model, we should have the id of the file in the Data entity
    await off_main_thread(lambda: project.compile(create_model + "\n" + state_model))
    data = project.get_instances("__config__::Data")
    assert data, "No Data entity found in model"
    assert (
        data[0].info == param["state"]["id"]
    ), "The id in the model doesn't match the one in state"

    # Let's now abuse the state dict a little bit and fake a more complex structure
    state = {
        "name": "bob",
        "id": 123,
        "physiology": {  # This is a single element
            "size": 1.8,
            "weight": 80,
            "hair_color": "brown",
            "generated_whatever": "hello world",
        },
        "hobbies": [  # This will be an unordered set
            {
                "name": "hockey",
                "generated_value": 159,
            },
            {
                "name": "climbing",
                "generated_apple": "yes",
            },
        ],
        "agenda": [  # This will be an ordered list
            {
                "name": "dentist",
                "time": "10AM",
                "generated_pineapple": "azerty",
            },
            {
                "name": "sport",
                "time": "16PM",
                "generated_potato": "HAPHADPIOJH",
            },
        ],
        "friends": {  # This will be a dict
            "alice": {
                "since": "a long time",
                "generated_date": "how the hell do I know?",
            },
        },
    }
    await local_file.set_state(client, environment, state)

    # The new model should build the config block structure matching the state
    fake_config = """
        file.root_config = terraform::config::Block(
            name=null,
            attributes={
                "name": "bob",
            },
        )

        entity Holder:
        end
        Holder.physiology [1] -- terraform::config::Block
        Holder.hockey [1] -- terraform::config::Block
        Holder.climbing [1] -- terraform::config::Block
        Holder.dentist [1] -- terraform::config::Block
        Holder.sport [1] -- terraform::config::Block
        Holder.alice [1] -- terraform::config::Block
        implement Holder using std::none

        Holder(
            physiology=terraform::config::Block(
                parent=file.root_config,
                name="physiology",
                attributes={
                    "size": 1.8,
                    "weight": 80,
                    "hair_color": "brown",
                },
            ),
            hockey=terraform::config::Block(
                parent=file.root_config,
                name="hobbies",
                attributes={"name": "hockey"},
                nesting_mode="set",
            ),
            climbing=terraform::config::Block(
                parent=file.root_config,
                name="hobbies",
                attributes={"name": "climbing"},
                nesting_mode="set",
            ),
            dentist=terraform::config::Block(
                parent=file.root_config,
                name="agenda",
                attributes={"name": "dentist", "time": "10AM"},
                nesting_mode="list",
                key="0",
            ),
            sport=terraform::config::Block(
                parent=file.root_config,
                name="agenda",
                attributes={"name": "sport", "time": "16PM"},
                nesting_mode="list",
                key="1",
            ),
            alice=terraform::config::Block(
                parent=file.root_config,
                name="friends",
                attributes={"since": "a long time"},
                nesting_mode="dict",
                key="alice",
            ),
        )
    """
    fake_config = dedent(fake_config.strip("\n"))

    # The first compile allows us to get the config hash for the tree we built
    await off_main_thread(lambda: project.compile(base_model + "\n" + fake_config))
    root_config = project.get_instances("terraform::Resource")[0].root_config
    holder = project.get_instances("__config__::Holder")[0]
    config_hash = (
        root_config.key
    )  # For "single" config blocks, the key is a hash of the config

    with pytest.raises(inmanta.execute.proxy.UnknownException):
        root_config._state  # The state should be unknown for now

    with pytest.raises(inmanta.execute.proxy.UnknownException):
        holder.physiology._state  # The state should be unknown as well on the child config blocks

    # The state should be unknown as we can not safely

    # Update the state to include the config_hash
    await local_file.set_state(
        client,
        environment,
        {
            "state": state,
            "config_hash": config_hash,
            "__state_dict_generation": "Albatross",
            "created_at": str(datetime.datetime.now()),
            "updated_at": str(datetime.datetime.now()),
        },
    )

    # The second compile allows us to properly get the state in the config blocks
    await off_main_thread(lambda: project.compile(base_model + "\n" + fake_config))
    holder = project.get_instances("__config__::Holder")[0]

    # Checking "single" config block
    assert holder.physiology._state["size"] == state["physiology"]["size"]
    assert (
        holder.physiology._state["generated_whatever"]
        == state["physiology"]["generated_whatever"]
    )

    # Checking "list" config block
    assert holder.hockey._state["name"] == state["hobbies"][0]["name"]
    assert (
        holder.hockey._state["generated_value"]
        == state["hobbies"][0]["generated_value"]
    )

    # Checking "set" config block
    assert holder.dentist._state["name"] == state["agenda"][0]["name"]
    assert (
        holder.dentist._state["generated_pineapple"]
        == state["agenda"][0]["generated_pineapple"]
    )

    # Checking "dict" config block
    assert holder.alice._state["since"] == state["friends"]["alice"]["since"]
    assert (
        holder.alice._state["generated_date"]
        == state["friends"]["alice"]["generated_date"]
    )


@pytest.mark.terraform_provider_local
@pytest.mark.asyncio
async def test_update_failed(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    function_temp_dir: str,
    cache_agent_dir: str,
) -> None:
    """
    This test creates a file, then update it by moving it in a forbidden location.  The update should fail
    but the param containing the state should be updated anyway, showing the current file state, which is null.
    """
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

    project.compile(create_model)
    resource: Resource = project.get_resource(
        local_file.resource_type, resource_name="my file"
    )

    assert resource is not None

    assert (
        await local_file.get_state(client, environment) is None
    ), "There shouldn't be any state set at this point for this resource"

    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    param = await local_file.get_state(client, environment)
    assert param is not None, "A state should have been set by now"

    # Update
    forbidden_path_object = Path("/dev/test-file.txt")
    local_file.path = str(forbidden_path_object)
    update_model = model()

    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.failed
    )

    param = await local_file.get_state(client, environment)
    assert param is None, (
        "Moving a file actually means removing the old one and creating the new one.  "
        "If we failed to move the file to the new location, we should still manage to "
        "delete the previous one (and remove its state with it).  We don't have a new "
        "state as there is no new file."
    )

    # Delete
    delete_model = model(True)

    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    assert (
        await local_file.get_state(client, environment) is None
    ), "The state should have been removed, but wasn't"
