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
from providers.github.helpers.github_client import GithubClient
from providers.github.helpers.github_provider import GithubProvider


@pytest.fixture(scope="package")
def token(lab_config_session: dict) -> str:
    return os.getenv(lab_config_session["github"]["configuration"]["token_env_var"])


@pytest.fixture(scope="package")
def owner(lab_config_session: dict) -> str:
    return lab_config_session["github"]["configuration"]["owner"]


@pytest.fixture(scope="package")
def repository_name(lab_config_session: dict) -> str:
    return lab_config_session["github"]["values"]["repository_name"]


@pytest.fixture(scope="package")
def provider(owner: str, token: str) -> GithubProvider:
    return GithubProvider(owner, token)


@pytest.fixture(scope="package")
def global_client(repository_name: str, owner: str, token: str) -> GithubClient:
    github_client = GithubClient(owner, token)

    yield github_client

    github_client.delete_repository(repository_name)


@pytest.fixture(scope="function")
def github_client(repository_name: str, global_client: GithubClient) -> GithubClient:
    global_client.delete_repository(repository_name)

    return global_client
