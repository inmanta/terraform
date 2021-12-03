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
import os

import pytest
from providers.gitlab.helpers.gitlab_client import GitlabClient
from providers.gitlab.helpers.gitlab_provider import GitlabProvider


@pytest.fixture(scope="package")
def token(lab_config_session: dict) -> str:
    return os.getenv(lab_config_session["gitlab"]["configuration"]["token_env_var"])


@pytest.fixture(scope="package")
def base_url(lab_config_session: dict) -> str:
    return lab_config_session["gitlab"]["configuration"]["base_url"]


@pytest.fixture(scope="package")
def provider(base_url: str, token: str) -> GitlabProvider:
    return GitlabProvider(base_url, token)


@pytest.fixture(scope="package")
def parent_namespace_id(lab_config_session: dict) -> int:
    return lab_config_session["gitlab"]["values"]["namespace_id"]


@pytest.fixture(scope="package")
def parent_namespace_path(lab_config_session: dict) -> str:
    return lab_config_session["gitlab"]["values"]["namespace_path"]


@pytest.fixture(scope="package")
def project_name(lab_config_session: dict) -> str:
    return lab_config_session["gitlab"]["values"]["project_name"]


@pytest.fixture(scope="package")
def global_client(lab_config_session: dict, base_url: str, token: str) -> GitlabClient:
    gitlab_values = lab_config_session["gitlab"]["values"]
    gitlab_client = GitlabClient(base_url, token)

    yield gitlab_client

    project_path = os.path.join(
        gitlab_values["namespace_path"], gitlab_values["project_name"]
    )
    gitlab_client.delete_project(project_path)


@pytest.fixture(scope="function")
def gitlab_client(
    lab_config_session: dict, global_client: GitlabClient
) -> GitlabClient:
    gitlab_values = lab_config_session["gitlab"]["values"]
    project_path = os.path.join(
        gitlab_values["namespace_path"], gitlab_values["project_name"]
    )
    global_client.delete_project(project_path)
    return global_client
