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
import os
from typing import Callable, Dict, List, Optional
from uuid import UUID

import pytest
from helpers.utils import deploy_model, is_deployment_with_change
from providers.gitlab.helpers.gitlab_client import GitlabClient
from providers.gitlab.helpers.gitlab_project import GitlabProject
from providers.gitlab.helpers.gitlab_provider import GitlabProvider
from pytest_inmanta.plugin import Project

from inmanta.agent.agent import Agent
from inmanta.const import Change, VersionState
from inmanta.protocol.endpoints import Client
from inmanta.server.protocol import Server

LOGGER = logging.getLogger(__name__)


def project_is_deployed(path: str, client: GitlabClient) -> bool:
    return client.get_project(path) is not None


@pytest.mark.terraform_provider_gitlab
@pytest.mark.asyncio
async def test_crud(
    project: Project,
    server: Server,
    client: Client,
    environment: str,
    agent_factory: Callable[
        [UUID, Optional[str], Optional[Dict[str, str]], bool, List[str]], Agent
    ],
    provider: GitlabProvider,
    parent_namespace_id: int,
    parent_namespace_path: str,
    gitlab_client: GitlabClient,
    project_name: str,
    cache_agent_dir: str,
):
    await agent_factory(
        environment=environment,
        hostname="node1",
        agent_map={provider.agent: "localhost"},
        code_loader=False,
        agent_names=[provider.agent],
    )

    gitlab_project = GitlabProject(
        "my project",
        project_name,
        "my original description",
        provider,
        parent_namespace_id,
    )

    def model(purged: bool = False) -> str:
        m = (
            "\nimport terraform\n\n"
            + provider.model_instance("provider")
            + "\n"
            + gitlab_project.model_instance("project", purged)
        )
        LOGGER.debug(m)
        return m

    project_path = os.path.join(parent_namespace_path, project_name)

    assert not project_is_deployed(project_path, gitlab_client)

    # Create
    create_model = model()
    assert (
        await deploy_model(project, create_model, client, environment)
        == VersionState.success
    )

    last_action = await gitlab_project.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.created

    assert project_is_deployed(project_path, gitlab_client)

    # Update
    gitlab_project.description = gitlab_project.description + " (updated)"
    update_model = model()
    assert (
        await deploy_model(project, update_model, client, environment)
        == VersionState.success
    )

    last_action = await gitlab_project.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.updated

    assert project_is_deployed(project_path, gitlab_client)

    # Delete
    delete_model = model(purged=True)
    assert (
        await deploy_model(project, delete_model, client, environment)
        == VersionState.success
    )

    last_action = await gitlab_project.get_last_action(
        client, environment, is_deployment_with_change
    )
    assert last_action.change == Change.purged

    assert not project_is_deployed(project_path, gitlab_client)
