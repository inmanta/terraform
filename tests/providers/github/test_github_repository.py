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
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from providers.github.helpers.github_client import GithubClient
from providers.github.helpers.github_provider import GithubProvider
from providers.github.helpers.github_repository import GithubRepository
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def repository_is_deployed(client: GithubClient, repository_name: str) -> bool:
    return client.get_repository(repository_name) is not None


@pytest.mark.asyncio
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: GithubProvider,
    github_client: GithubClient,
    repository_name: str,
    cache_agent_dir: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    github_repository = GithubRepository(
        "my repo", repository_name, "my original description", provider
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + github_repository.model_instance("repo", purged)
        )
        LOGGER.debug(m)
        return m

    assert not repository_is_deployed(github_client, repository_name)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_action = await github_repository.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert repository_is_deployed(github_client, repository_name)

    # Update
    github_repository.description = github_repository.description + " (updated)"
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_action = await github_repository.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.updated

    assert repository_is_deployed(github_client, repository_name)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_action = await github_repository.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged

    assert not repository_is_deployed(github_client, repository_name)
